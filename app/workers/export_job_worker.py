import argparse
import json
import time

from sqlmodel import Session, select

from app.db.models import ExportJob, utcnow
from app.db.session import engine
from app.services.export_service import (
    build_export_plan,
    build_highlight_plan,
    render_export_video,
    save_manifest,
)


def _process_one(session: Session, job: ExportJob) -> None:
    payload = json.loads(job.payload_json)

    mode = (job.mode or "full").strip().lower()
    global_track_id = job.global_track_id
    padding_seconds = float(payload.get("padding_seconds", 3.0))
    merge_gap_seconds = float(payload.get("merge_gap_seconds", 0.2))
    min_duration_seconds = float(payload.get("min_duration_seconds", 0.3))

    excerpts, summary = build_export_plan(
        session=session,
        global_track_id=global_track_id,
        padding_seconds=padding_seconds,
        merge_gap_seconds=merge_gap_seconds,
        min_duration_seconds=min_duration_seconds,
    )

    render_video = bool(payload.get("render_video", True))
    target_seconds = float(payload.get("target_seconds", 30.0))
    per_clip_seconds = float(payload.get("per_clip_seconds", 4.0))

    if mode == "highlights":
        excerpts = build_highlight_plan(
            excerpts=excerpts,
            target_seconds=target_seconds,
            per_clip_seconds=per_clip_seconds,
        )
        summary["mode"] = "highlights"
        summary["target_seconds"] = target_seconds
        summary["per_clip_seconds"] = per_clip_seconds
        summary["highlight_excerpt_count"] = len(excerpts)

    if not excerpts:
        raise ValueError("No excerpts available for export")

    export_id, manifest_path = save_manifest(
        global_track_id=global_track_id,
        summary=summary,
        excerpts=excerpts,
    )

    video_path = None
    if render_video:
        video_path = render_export_video(export_id=export_id, excerpts=excerpts)

    job.export_id = export_id
    job.manifest_path = str(manifest_path)
    job.video_path = str(video_path) if video_path else None


def run(args: argparse.Namespace) -> None:
    processed = 0
    while True:
        with Session(engine) as session:
            query = (
                select(ExportJob)
                .where(ExportJob.status == "pending")
                .order_by(ExportJob.created_at.asc())
                .limit(1)
            )
            job = session.exec(query).first()
            if not job:
                if args.once:
                    break
                time.sleep(max(args.poll_seconds, 0.2))
                continue

            job.status = "running"
            job.started_at = utcnow()
            job.error_message = None
            session.add(job)
            session.commit()
            session.refresh(job)

            try:
                _process_one(session, job)
                job.status = "done"
                job.finished_at = utcnow()
                job.error_message = None
            except Exception as exc:
                job.status = "failed"
                job.finished_at = utcnow()
                job.error_message = str(exc)
            session.add(job)
            session.commit()
            processed += 1

        if args.once:
            break

    print(json.dumps({"processed_jobs": processed}, ensure_ascii=True))


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Export job queue worker")
    parser.add_argument("--once", action="store_true", help="Process at most one pending job and exit")
    parser.add_argument("--poll-seconds", type=float, default=1.5)
    return parser


if __name__ == "__main__":
    run(build_parser().parse_args())
