import uuid
from datetime import datetime, timezone

from sqlmodel import Field, SQLModel


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Animal(SQLModel, table=True):
    __tablename__ = "animals"

    animal_id: str = Field(default_factory=lambda: str(uuid.uuid4()), primary_key=True)
    species: str
    name: str
    owner_id: str | None = None
    active: bool = True
    created_at: datetime = Field(default_factory=utcnow)


class Collar(SQLModel, table=True):
    __tablename__ = "collars"

    collar_id: str = Field(default_factory=lambda: str(uuid.uuid4()), primary_key=True)
    animal_id: str = Field(foreign_key="animals.animal_id", index=True)
    marker_id: str | None = Field(default=None, index=True)
    ble_id: str | None = Field(default=None, index=True)
    uwb_id: str | None = Field(default=None, index=True)
    start_ts: datetime = Field(default_factory=utcnow)
    end_ts: datetime | None = None


class Camera(SQLModel, table=True):
    __tablename__ = "cameras"

    camera_id: str = Field(default_factory=lambda: str(uuid.uuid4()), primary_key=True)
    location_zone: str
    intrinsics_version: str | None = None
    stream_url: str | None = None
    installed_height_m: float | None = None
    tilt_deg: float | None = None
    created_at: datetime = Field(default_factory=utcnow)


class Track(SQLModel, table=True):
    __tablename__ = "tracks"

    track_id: str = Field(default_factory=lambda: str(uuid.uuid4()), primary_key=True)
    camera_id: str = Field(foreign_key="cameras.camera_id", index=True)
    start_ts: datetime = Field(default_factory=utcnow)
    end_ts: datetime | None = None
    quality_score: float | None = None


class TrackObservation(SQLModel, table=True):
    __tablename__ = "track_observations"

    observation_id: str = Field(default_factory=lambda: str(uuid.uuid4()), primary_key=True)
    track_id: str = Field(foreign_key="tracks.track_id", index=True)
    ts: datetime = Field(default_factory=utcnow, index=True)
    bbox: str
    marker_id_read: str | None = None
    appearance_vec_ref: str | None = None


class Position(SQLModel, table=True):
    __tablename__ = "positions"

    position_id: str = Field(default_factory=lambda: str(uuid.uuid4()), primary_key=True)
    animal_id: str = Field(foreign_key="animals.animal_id", index=True)
    ts: datetime = Field(default_factory=utcnow, index=True)
    x_m: float
    y_m: float
    z_m: float | None = None
    method: str = Field(default="Ble")
    cov_matrix: str | None = None


class Association(SQLModel, table=True):
    __tablename__ = "associations"

    association_id: str = Field(default_factory=lambda: str(uuid.uuid4()), primary_key=True)
    global_track_id: str = Field(index=True)
    track_id: str = Field(foreign_key="tracks.track_id", index=True)
    animal_id: str = Field(foreign_key="animals.animal_id", index=True)
    confidence: float = 0.0
    created_at: datetime = Field(default_factory=utcnow)


class GlobalTrackProfile(SQLModel, table=True):
    __tablename__ = "global_track_profiles"

    global_track_id: str = Field(primary_key=True)
    class_id: int = Field(index=True)
    embedding_json: str
    sample_count: int = 1
    updated_at: datetime = Field(default_factory=utcnow, index=True)


class Event(SQLModel, table=True):
    __tablename__ = "events"

    event_id: str = Field(default_factory=lambda: str(uuid.uuid4()), primary_key=True)
    animal_id: str = Field(foreign_key="animals.animal_id", index=True)
    start_ts: datetime = Field(default_factory=utcnow, index=True)
    end_ts: datetime | None = None
    type: str
    severity: str = Field(default="info")
    created_at: datetime = Field(default_factory=utcnow)


class MediaSegment(SQLModel, table=True):
    __tablename__ = "media_segments"

    segment_id: str = Field(default_factory=lambda: str(uuid.uuid4()), primary_key=True)
    camera_id: str | None = Field(default=None, foreign_key="cameras.camera_id", index=True)
    start_ts: datetime = Field(default_factory=utcnow, index=True)
    end_ts: datetime | None = None
    path: str
    codec: str | None = None
    avg_bitrate: float | None = None


class Clip(SQLModel, table=True):
    __tablename__ = "clips"

    clip_id: str = Field(default_factory=lambda: str(uuid.uuid4()), primary_key=True)
    event_id: str | None = Field(default=None, foreign_key="events.event_id", index=True)
    path: str
    start_ts: datetime = Field(default_factory=utcnow, index=True)
    end_ts: datetime | None = None
    derived_from_segments: str | None = None


class VideoAnalysis(SQLModel, table=True):
    __tablename__ = "video_analyses"

    video_id: str = Field(primary_key=True)
    animal_id: str | None = Field(default=None, foreign_key="animals.animal_id", index=True)
    camera_id: str | None = Field(default=None, foreign_key="cameras.camera_id", index=True)
    filename: str
    uploaded_path: str
    encrypted_analysis_path: str
    duration_seconds: float
    fps: float
    total_frames: int
    sampled_frames: int
    avg_motion_score: float
    avg_brightness: float
    created_at: datetime = Field(default_factory=utcnow, index=True)
