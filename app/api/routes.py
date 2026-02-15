import json
from datetime import datetime, timedelta
from typing import Any

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile
from fastapi.responses import FileResponse
from sqlmodel import Session, select

from app.core.auth import verify_api_key
from app.db.models import (
    Animal,
    Association,
    Camera,
    Clip,
    Collar,
    Event,
    ExportJob,
    MediaSegment,
    Position,
    Track,
    TrackObservation,
    VideoAnalysis,
    utcnow,
)
from app.db.session import get_session
from app.schemas.domain import (
    AnimalCreate,
    AssociationCreate,
    CameraCreate,
    ClipCreate,
    CollarCreate,
    EventCreate,
    ExportJobCreate,
    ExportRequest,
    HighlightRequest,
    MediaSegmentCreate,
    PositionCreate,
    TrackCreate,
    TrackObservationCreate,
)
from app.services.export_service import (
    build_export_plan,
    build_highlight_plan,
    load_manifest,
    manifest_path_for_export,
    render_export_video,
    save_manifest,
    video_path_for_export,
)
from app.services.storage_service import (
    read_encrypted_analysis,
    save_upload,
    store_encrypted_analysis,
)
from app.services.tracking_service import track_video_with_yolo_deepsort
from app.services.video_service import analyze_video

router = APIRouter(dependencies=[Depends(verify_api_key)])


def _timeline_item(kind: str, ts: datetime, payload: Any) -> dict[str, Any]:
    return {
        "kind": kind,
        "ts": ts,
        "data": payload.model_dump() if hasattr(payload, "model_dump") else payload,
    }


def _build_global_track_id(global_id_mode: str, camera_id: str, source_track_id: int, animal_id: str | None) -> str:
    if global_id_mode == "animal" and animal_id:
        return f"animal:{animal_id}"
    return f"{camera_id}:{source_track_id}"


@router.post("/animals")
def create_animal(payload: AnimalCreate, session: Session = Depends(get_session)) -> Animal:
    animal = Animal(**payload.model_dump())
    session.add(animal)
    session.commit()
    session.refresh(animal)
    return animal


@router.get("/animals")
def list_animals(
    active: bool | None = Query(default=None), session: Session = Depends(get_session)
) -> list[Animal]:
    query = select(Animal)
    if active is not None:
        query = query.where(Animal.active == active)
    return list(session.exec(query))


@router.post("/cameras")
def create_camera(payload: CameraCreate, session: Session = Depends(get_session)) -> Camera:
    camera = Camera(**payload.model_dump())
    session.add(camera)
    session.commit()
    session.refresh(camera)
    return camera


@router.get("/cameras")
def list_cameras(session: Session = Depends(get_session)) -> list[Camera]:
    return list(session.exec(select(Camera)))


@router.post("/collars")
def create_collar(payload: CollarCreate, session: Session = Depends(get_session)) -> Collar:
    if not session.get(Animal, payload.animal_id):
        raise HTTPException(status_code=404, detail="Animal not found")

    data = payload.model_dump()
    data["start_ts"] = payload.start_ts or utcnow()
    collar = Collar(**data)
    session.add(collar)
    session.commit()
    session.refresh(collar)
    return collar


@router.get("/collars")
def list_collars(
    animal_id: str | None = Query(default=None), session: Session = Depends(get_session)
) -> list[Collar]:
    query = select(Collar)
    if animal_id:
        query = query.where(Collar.animal_id == animal_id)
    return list(session.exec(query.order_by(Collar.start_ts.desc())))


@router.post("/tracks")
def create_track(payload: TrackCreate, session: Session = Depends(get_session)) -> Track:
    if not session.get(Camera, payload.camera_id):
        raise HTTPException(status_code=404, detail="Camera not found")

    data = payload.model_dump()
    data["start_ts"] = payload.start_ts or utcnow()
    track = Track(**data)
    session.add(track)
    session.commit()
    session.refresh(track)
    return track


@router.get("/tracks")
def list_tracks(
    camera_id: str | None = Query(default=None), session: Session = Depends(get_session)
) -> list[Track]:
    query = select(Track)
    if camera_id:
        query = query.where(Track.camera_id == camera_id)
    return list(session.exec(query.order_by(Track.start_ts.desc())))


@router.post("/tracks/{track_id}/observations")
def create_track_observation(
    track_id: str,
    payload: TrackObservationCreate,
    session: Session = Depends(get_session),
) -> TrackObservation:
    if not session.get(Track, track_id):
        raise HTTPException(status_code=404, detail="Track not found")

    data = payload.model_dump()
    data["track_id"] = track_id
    data["ts"] = payload.ts or utcnow()
    observation = TrackObservation(**data)
    session.add(observation)
    session.commit()
    session.refresh(observation)
    return observation


@router.get("/tracks/{track_id}/observations")
def list_track_observations(
    track_id: str,
    limit: int = Query(default=200, ge=1, le=1000),
    session: Session = Depends(get_session),
) -> list[TrackObservation]:
    if not session.get(Track, track_id):
        raise HTTPException(status_code=404, detail="Track not found")

    query = (
        select(TrackObservation)
        .where(TrackObservation.track_id == track_id)
        .order_by(TrackObservation.ts.desc())
        .limit(limit)
    )
    return list(session.exec(query))


@router.post("/associations")
def create_association(
    payload: AssociationCreate, session: Session = Depends(get_session)
) -> Association:
    if not session.get(Track, payload.track_id):
        raise HTTPException(status_code=404, detail="Track not found")
    if not session.get(Animal, payload.animal_id):
        raise HTTPException(status_code=404, detail="Animal not found")

    association = Association(**payload.model_dump())
    session.add(association)
    session.commit()
    session.refresh(association)
    return association


@router.get("/associations")
def list_associations(
    animal_id: str | None = Query(default=None),
    global_track_id: str | None = Query(default=None),
    session: Session = Depends(get_session),
) -> list[Association]:
    query = select(Association)
    if animal_id:
        query = query.where(Association.animal_id == animal_id)
    if global_track_id:
        query = query.where(Association.global_track_id == global_track_id)
    return list(session.exec(query.order_by(Association.created_at.desc())))


@router.post("/events")
def create_event(payload: EventCreate, session: Session = Depends(get_session)) -> Event:
    if not session.get(Animal, payload.animal_id):
        raise HTTPException(status_code=404, detail="Animal not found")

    data = payload.model_dump()
    data["start_ts"] = payload.start_ts or utcnow()
    event = Event(**data)
    session.add(event)
    session.commit()
    session.refresh(event)
    return event


@router.get("/events")
def list_events(
    animal_id: str | None = Query(default=None), session: Session = Depends(get_session)
) -> list[Event]:
    query = select(Event)
    if animal_id:
        query = query.where(Event.animal_id == animal_id)
    query = query.order_by(Event.start_ts.desc())
    return list(session.exec(query))


@router.post("/positions")
def create_position(payload: PositionCreate, session: Session = Depends(get_session)) -> Position:
    if not session.get(Animal, payload.animal_id):
        raise HTTPException(status_code=404, detail="Animal not found")

    data = payload.model_dump()
    data["ts"] = payload.ts or utcnow()
    position = Position(**data)
    session.add(position)
    session.commit()
    session.refresh(position)
    return position


@router.post("/media-segments")
def create_media_segment(
    payload: MediaSegmentCreate, session: Session = Depends(get_session)
) -> MediaSegment:
    if payload.camera_id and not session.get(Camera, payload.camera_id):
        raise HTTPException(status_code=404, detail="Camera not found")

    data = payload.model_dump()
    data["start_ts"] = payload.start_ts or utcnow()
    segment = MediaSegment(**data)
    session.add(segment)
    session.commit()
    session.refresh(segment)
    return segment


@router.get("/media-segments")
def list_media_segments(
    camera_id: str | None = Query(default=None), session: Session = Depends(get_session)
) -> list[MediaSegment]:
    query = select(MediaSegment)
    if camera_id:
        query = query.where(MediaSegment.camera_id == camera_id)
    return list(session.exec(query.order_by(MediaSegment.start_ts.desc())))


@router.post("/clips")
def create_clip(payload: ClipCreate, session: Session = Depends(get_session)) -> Clip:
    if payload.event_id and not session.get(Event, payload.event_id):
        raise HTTPException(status_code=404, detail="Event not found")

    data = payload.model_dump()
    data["start_ts"] = payload.start_ts or utcnow()
    clip = Clip(**data)
    session.add(clip)
    session.commit()
    session.refresh(clip)
    return clip


@router.get("/clips")
def list_clips(
    event_id: str | None = Query(default=None), session: Session = Depends(get_session)
) -> list[Clip]:
    query = select(Clip)
    if event_id:
        query = query.where(Clip.event_id == event_id)
    return list(session.exec(query.order_by(Clip.start_ts.desc())))


@router.get("/animals/{animal_id}/timeline")
def get_animal_timeline(
    animal_id: str,
    from_ts: datetime | None = Query(default=None),
    to_ts: datetime | None = Query(default=None),
    session: Session = Depends(get_session),
) -> dict[str, Any]:
    animal = session.get(Animal, animal_id)
    if not animal:
        raise HTTPException(status_code=404, detail="Animal not found")

    events_query = select(Event).where(Event.animal_id == animal_id)
    positions_query = select(Position).where(Position.animal_id == animal_id)
    analyses_query = select(VideoAnalysis).where(VideoAnalysis.animal_id == animal_id)

    if from_ts:
        events_query = events_query.where(Event.start_ts >= from_ts)
        positions_query = positions_query.where(Position.ts >= from_ts)
        analyses_query = analyses_query.where(VideoAnalysis.created_at >= from_ts)
    if to_ts:
        events_query = events_query.where(Event.start_ts <= to_ts)
        positions_query = positions_query.where(Position.ts <= to_ts)
        analyses_query = analyses_query.where(VideoAnalysis.created_at <= to_ts)

    events = list(session.exec(events_query.order_by(Event.start_ts.desc()).limit(200)))
    positions = list(session.exec(positions_query.order_by(Position.ts.desc()).limit(200)))
    analyses = list(session.exec(analyses_query.order_by(VideoAnalysis.created_at.desc()).limit(50)))

    timeline = [
        *[_timeline_item("event", row.start_ts, row) for row in events],
        *[_timeline_item("position", row.ts, row) for row in positions],
        *[_timeline_item("video_analysis", row.created_at, row) for row in analyses],
    ]
    timeline.sort(key=lambda item: item["ts"], reverse=True)

    return {
        "animal": animal,
        "events": events,
        "positions": positions,
        "video_analyses": analyses,
        "timeline": timeline,
    }


@router.post("/videos/process")
async def process_video(
    file: UploadFile = File(...),
    animal_id: str | None = Form(default=None),
    camera_id: str | None = Form(default=None),
    event_type: str | None = Form(default=None),
    session: Session = Depends(get_session),
) -> dict[str, Any]:
    if not file.filename:
        raise HTTPException(status_code=400, detail="File name is required")

    if not file.content_type or not file.content_type.startswith("video/"):
        raise HTTPException(status_code=400, detail="Only video files are allowed")

    if animal_id and not session.get(Animal, animal_id):
        raise HTTPException(status_code=404, detail="Animal not found")
    if camera_id and not session.get(Camera, camera_id):
        raise HTTPException(status_code=404, detail="Camera not found")

    video_id, video_path = await save_upload(file)
    analysis = analyze_video(video_path)
    encrypted_path = store_encrypted_analysis(video_id, analysis)

    now = utcnow()
    analysis_row = VideoAnalysis(
        video_id=video_id,
        animal_id=animal_id,
        camera_id=camera_id,
        filename=file.filename,
        uploaded_path=str(video_path),
        encrypted_analysis_path=str(encrypted_path),
        duration_seconds=analysis["duration_seconds"],
        fps=analysis["fps"],
        total_frames=analysis["total_frames"],
        sampled_frames=analysis["sampled_frames"],
        avg_motion_score=analysis["avg_motion_score"],
        avg_brightness=analysis["avg_brightness"],
        created_at=now,
    )
    session.add(analysis_row)

    segment = MediaSegment(
        camera_id=camera_id,
        start_ts=now,
        end_ts=now + timedelta(seconds=analysis["duration_seconds"]),
        path=str(video_path),
        codec=file.content_type,
    )
    session.add(segment)

    created_event: Event | None = None
    if event_type and animal_id:
        created_event = Event(
            animal_id=animal_id,
            type=event_type,
            severity="info",
            start_ts=now,
            end_ts=now + timedelta(seconds=analysis["duration_seconds"]),
        )
        session.add(created_event)

    session.commit()
    if created_event:
        session.refresh(created_event)

    return {
        "video_id": video_id,
        "filename": file.filename,
        "analysis_encrypted_path": str(encrypted_path),
        "event_id": created_event.event_id if created_event else None,
        "summary": {
            "duration_seconds": analysis["duration_seconds"],
            "fps": analysis["fps"],
            "total_frames": analysis["total_frames"],
            "sampled_frames": analysis["sampled_frames"],
            "avg_motion_score": analysis["avg_motion_score"],
            "avg_brightness": analysis["avg_brightness"],
        },
    }


@router.post("/videos/track")
async def track_video(
    file: UploadFile = File(...),
    camera_id: str = Form(...),
    animal_id: str | None = Form(default=None),
    conf_threshold: float = Form(default=0.25),
    iou_threshold: float = Form(default=0.45),
    frame_stride: int = Form(default=1),
    max_frames: int = Form(default=0),
    classes_csv: str = Form(default="15,16"),
    global_id_mode: str = Form(default="animal"),
    session: Session = Depends(get_session),
) -> dict[str, Any]:
    if not file.filename:
        raise HTTPException(status_code=400, detail="File name is required")

    if not file.content_type or not file.content_type.startswith("video/"):
        raise HTTPException(status_code=400, detail="Only video files are allowed")

    camera = session.get(Camera, camera_id)
    if not camera:
        raise HTTPException(status_code=404, detail="Camera not found")

    if animal_id and not session.get(Animal, animal_id):
        raise HTTPException(status_code=404, detail="Animal not found")

    if frame_stride < 1:
        raise HTTPException(status_code=400, detail="frame_stride must be >= 1")
    if global_id_mode not in {"animal", "camera_track"}:
        raise HTTPException(status_code=400, detail="global_id_mode must be one of: animal, camera_track")

    classes: list[int] | None = None
    classes_csv = classes_csv.strip()
    if classes_csv:
        try:
            classes = [int(value.strip()) for value in classes_csv.split(",") if value.strip()]
        except ValueError as exc:
            raise HTTPException(status_code=400, detail="classes_csv must be comma-separated integers") from exc

    video_id, video_path = await save_upload(file)

    try:
        tracking = track_video_with_yolo_deepsort(
            video_path=video_path,
            conf_threshold=conf_threshold,
            iou_threshold=iou_threshold,
            frame_stride=frame_stride,
            max_frames=max_frames,
            classes=classes,
        )
    except RuntimeError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    now = utcnow()
    analysis_row = VideoAnalysis(
        video_id=video_id,
        animal_id=animal_id,
        camera_id=camera_id,
        filename=file.filename,
        uploaded_path=str(video_path),
        encrypted_analysis_path="",
        duration_seconds=float(tracking["duration_seconds"]),
        fps=float(tracking["fps"]),
        total_frames=int(tracking["total_frames"]),
        sampled_frames=int(tracking["processed_frames"]),
        avg_motion_score=0.0,
        avg_brightness=0.0,
        created_at=now,
    )
    session.add(analysis_row)

    segment = MediaSegment(
        camera_id=camera_id,
        start_ts=now,
        end_ts=now + timedelta(seconds=float(tracking["duration_seconds"])),
        path=str(video_path),
        codec=file.content_type,
    )
    session.add(segment)

    persisted_tracks = 0
    persisted_observations = 0
    persisted_associations = 0
    for source_track in tracking["tracks"]:
        observations = source_track["observations"]
        if not observations:
            continue

        start_ts = now + timedelta(seconds=float(observations[0]["ts_seconds"]))
        end_ts = now + timedelta(seconds=float(observations[-1]["ts_seconds"]))
        track_row = Track(
            camera_id=camera_id,
            start_ts=start_ts,
            end_ts=end_ts,
            quality_score=float(source_track["avg_confidence"]),
        )
        session.add(track_row)
        session.flush()
        persisted_tracks += 1

        for obs in observations:
            bbox_json = json.dumps([round(float(v), 3) for v in obs["bbox_xyxy"]], ensure_ascii=True)
            appearance_ref = f"class:{int(obs['class_id'])};conf:{float(obs['conf']):.6f}"
            row = TrackObservation(
                track_id=track_row.track_id,
                ts=now + timedelta(seconds=float(obs["ts_seconds"])),
                bbox=bbox_json,
                marker_id_read=None,
                appearance_vec_ref=appearance_ref,
            )
            session.add(row)
            persisted_observations += 1

        if animal_id:
            association = Association(
                global_track_id=_build_global_track_id(
                    global_id_mode,
                    camera_id,
                    int(source_track["source_track_id"]),
                    animal_id,
                ),
                track_id=track_row.track_id,
                animal_id=animal_id,
                confidence=float(source_track["avg_confidence"]),
            )
            session.add(association)
            persisted_associations += 1

    session.commit()

    return {
        "video_id": video_id,
        "camera_id": camera_id,
        "animal_id": animal_id,
        "tracking_summary": {
            "fps": tracking["fps"],
            "total_frames": tracking["total_frames"],
            "processed_frames": tracking["processed_frames"],
            "duration_seconds": tracking["duration_seconds"],
            "total_detections": tracking["total_detections"],
            "track_count": tracking["track_count"],
        },
        "db_persisted": {
            "tracks": persisted_tracks,
            "observations": persisted_observations,
            "associations": persisted_associations,
        },
    }


@router.get("/videos/{video_id}/analysis")
def get_analysis(video_id: str, session: Session = Depends(get_session)) -> dict[str, Any]:
    row = session.get(VideoAnalysis, video_id)
    if not row:
        raise HTTPException(status_code=404, detail="Analysis metadata not found")

    try:
        decrypted = read_encrypted_analysis(video_id)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Encrypted analysis file not found") from exc

    return {
        "metadata": row,
        "analysis": decrypted,
    }


@router.post("/exports/global-track/{global_track_id}")
def export_global_track(
    global_track_id: str,
    payload: ExportRequest,
    session: Session = Depends(get_session),
) -> dict[str, Any]:
    try:
        excerpts, summary = build_export_plan(
            session=session,
            global_track_id=global_track_id,
            padding_seconds=payload.padding_seconds,
            merge_gap_seconds=payload.merge_gap_seconds,
            min_duration_seconds=payload.min_duration_seconds,
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    export_id, manifest_path = save_manifest(
        global_track_id=global_track_id,
        summary=summary,
        excerpts=excerpts,
    )

    video_path: str | None = None
    render_error: str | None = None
    if payload.render_video:
        try:
            video_path = str(render_export_video(export_id=export_id, excerpts=excerpts))
        except Exception as exc:
            render_error = str(exc)

    return {
        "export_id": export_id,
        "global_track_id": global_track_id,
        "summary": summary,
        "manifest_path": str(manifest_path),
        "video_path": video_path,
        "render_error": render_error,
    }


@router.post("/exports/global-track/{global_track_id}/highlights")
def export_global_track_highlights(
    global_track_id: str,
    payload: HighlightRequest,
    session: Session = Depends(get_session),
) -> dict[str, Any]:
    try:
        excerpts, summary = build_export_plan(
            session=session,
            global_track_id=global_track_id,
            padding_seconds=payload.padding_seconds,
            merge_gap_seconds=payload.merge_gap_seconds,
            min_duration_seconds=payload.min_duration_seconds,
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    highlights = build_highlight_plan(
        excerpts=excerpts,
        target_seconds=payload.target_seconds,
        per_clip_seconds=payload.per_clip_seconds,
    )
    if not highlights:
        raise HTTPException(status_code=404, detail="No highlight excerpts available")

    summary["mode"] = "highlights"
    summary["target_seconds"] = payload.target_seconds
    summary["per_clip_seconds"] = payload.per_clip_seconds
    summary["highlight_excerpt_count"] = len(highlights)

    export_id, manifest_path = save_manifest(
        global_track_id=global_track_id,
        summary=summary,
        excerpts=highlights,
    )

    video_path: str | None = None
    render_error: str | None = None
    try:
        video_path = str(render_export_video(export_id=export_id, excerpts=highlights))
    except Exception as exc:
        render_error = str(exc)

    return {
        "export_id": export_id,
        "global_track_id": global_track_id,
        "summary": summary,
        "manifest_path": str(manifest_path),
        "video_path": video_path,
        "render_error": render_error,
    }


@router.post("/exports/global-track/{global_track_id}/jobs")
def create_export_job(
    global_track_id: str,
    payload: ExportJobCreate,
    session: Session = Depends(get_session),
) -> ExportJob:
    mode = payload.mode.strip().lower()
    if mode not in {"full", "highlights"}:
        raise HTTPException(status_code=400, detail="mode must be one of: full, highlights")

    job = ExportJob(
        global_track_id=global_track_id,
        mode=mode,
        status="pending",
        payload_json=json.dumps(payload.model_dump(), ensure_ascii=True),
    )
    session.add(job)
    session.commit()
    session.refresh(job)
    return job


@router.get("/exports/jobs/{job_id}")
def get_export_job(job_id: str, session: Session = Depends(get_session)) -> ExportJob:
    job = session.get(ExportJob, job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Export job not found")
    return job


@router.get("/exports/{export_id}")
def get_export(
    export_id: str,
    download: str | None = Query(default=None),
) -> Any:
    manifest_path = manifest_path_for_export(export_id)
    video_path = video_path_for_export(export_id)

    if download:
        kind = download.strip().lower()
        if kind == "manifest":
            if not manifest_path.exists():
                raise HTTPException(status_code=404, detail="Manifest not found")
            return FileResponse(
                path=str(manifest_path),
                media_type="application/json",
                filename=f"{export_id}.json",
            )
        if kind == "video":
            if not video_path.exists():
                raise HTTPException(status_code=404, detail="Video not found")
            return FileResponse(
                path=str(video_path),
                media_type="video/mp4",
                filename=f"{export_id}.mp4",
            )
        raise HTTPException(status_code=400, detail="download must be one of: manifest, video")

    manifest_data = None
    if manifest_path.exists():
        try:
            manifest_data = load_manifest(export_id)
        except Exception:
            manifest_data = None

    return {
        "export_id": export_id,
        "manifest_path": str(manifest_path) if manifest_path.exists() else None,
        "video_path": str(video_path) if video_path.exists() else None,
        "manifest": manifest_data,
    }
