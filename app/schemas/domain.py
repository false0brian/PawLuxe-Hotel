from datetime import datetime

from pydantic import BaseModel


class AnimalCreate(BaseModel):
    species: str
    name: str
    owner_id: str | None = None
    active: bool = True


class CameraCreate(BaseModel):
    location_zone: str
    intrinsics_version: str | None = None
    stream_url: str | None = None
    installed_height_m: float | None = None
    tilt_deg: float | None = None


class CollarCreate(BaseModel):
    animal_id: str
    marker_id: str | None = None
    ble_id: str | None = None
    uwb_id: str | None = None
    start_ts: datetime | None = None
    end_ts: datetime | None = None


class TrackCreate(BaseModel):
    camera_id: str
    start_ts: datetime | None = None
    end_ts: datetime | None = None
    quality_score: float | None = None


class TrackObservationCreate(BaseModel):
    ts: datetime | None = None
    bbox: str
    marker_id_read: str | None = None
    appearance_vec_ref: str | None = None


class AssociationCreate(BaseModel):
    global_track_id: str
    track_id: str
    animal_id: str
    confidence: float = 0.0


class EventCreate(BaseModel):
    animal_id: str
    type: str
    severity: str = "info"
    start_ts: datetime | None = None
    end_ts: datetime | None = None


class PositionCreate(BaseModel):
    animal_id: str
    x_m: float
    y_m: float
    z_m: float | None = None
    method: str = "Ble"
    cov_matrix: str | None = None
    ts: datetime | None = None


class MediaSegmentCreate(BaseModel):
    camera_id: str | None = None
    start_ts: datetime | None = None
    end_ts: datetime | None = None
    path: str
    codec: str | None = None
    avg_bitrate: float | None = None


class ClipCreate(BaseModel):
    event_id: str | None = None
    path: str
    start_ts: datetime | None = None
    end_ts: datetime | None = None
    derived_from_segments: str | None = None


class ExportRequest(BaseModel):
    padding_seconds: float = 3.0
    merge_gap_seconds: float = 0.2
    min_duration_seconds: float = 0.3
    render_video: bool = False


class HighlightRequest(BaseModel):
    padding_seconds: float = 2.0
    target_seconds: float = 30.0
    per_clip_seconds: float = 4.0
    merge_gap_seconds: float = 0.2
    min_duration_seconds: float = 0.3


class ExportJobCreate(BaseModel):
    mode: str = "full"  # full | highlights
    padding_seconds: float = 3.0
    merge_gap_seconds: float = 0.2
    min_duration_seconds: float = 0.3
    render_video: bool = True
    target_seconds: float = 30.0
    per_clip_seconds: float = 4.0
