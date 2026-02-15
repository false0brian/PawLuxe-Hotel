import shutil
import uuid
from datetime import timedelta
from pathlib import Path

import cv2
import numpy as np
from sqlmodel import Session

from app.services import export_service
from app.services.export_service import ExportExcerpt, render_export_video


def _make_video(path: Path, frames: int = 30, fps: float = 15.0) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    writer = cv2.VideoWriter(str(path), cv2.VideoWriter_fourcc(*"mp4v"), fps, (320, 240))
    assert writer.isOpened()
    for i in range(frames):
        frame = np.full((240, 320, 3), i % 255, dtype=np.uint8)
        writer.write(frame)
    writer.release()


def test_render_export_video_if_ffmpeg_available(monkeypatch) -> None:
    if shutil.which("ffmpeg") is None:
        # Environment without ffmpeg binary
        return

    suffix = str(uuid.uuid4())[:8]
    src = Path("storage/uploads") / f"render-src-{suffix}.mp4"
    _make_video(src)

    now = export_service.datetime.now(export_service.timezone.utc)
    excerpts = [
        ExportExcerpt(
            camera_id="cam-x",
            segment_id="seg-x",
            segment_path=str(src),
            clip_start_ts=now,
            clip_end_ts=now + timedelta(seconds=1.5),
            offset_start_sec=0.2,
            duration_sec=1.2,
        )
    ]

    out = render_export_video(export_id=f"render-{suffix}", excerpts=excerpts)
    assert out.exists()
    assert out.suffix == ".mp4"
    assert out.stat().st_size > 0
