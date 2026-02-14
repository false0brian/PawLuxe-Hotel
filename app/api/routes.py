from datetime import datetime, timedelta
from typing import Any

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile
from sqlmodel import Session, select

from app.core.auth import verify_api_key
from app.db.models import (
    Animal,
    Association,
    Camera,
    Clip,
    Collar,
    Event,
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
    MediaSegmentCreate,
    PositionCreate,
    TrackCreate,
    TrackObservationCreate,
)
from app.services.storage_service import (
    read_encrypted_analysis,
    save_upload,
    store_encrypted_analysis,
)
from app.services.video_service import analyze_video

router = APIRouter(dependencies=[Depends(verify_api_key)])


def _timeline_item(kind: str, ts: datetime, payload: Any) -> dict[str, Any]:
    return {
        "kind": kind,
        "ts": ts,
        "data": payload.model_dump() if hasattr(payload, "model_dump") else payload,
    }


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
