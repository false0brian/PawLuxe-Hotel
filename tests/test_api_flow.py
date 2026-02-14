import uuid

from fastapi.testclient import TestClient

from app.db.session import init_db
from app.main import app

client = TestClient(app)
HEADERS = {"x-api-key": "change-me"}

init_db()


def test_auth_required() -> None:
    response = client.get("/api/v1/animals")
    assert response.status_code == 401


def test_domain_flow_and_timeline() -> None:
    suffix = str(uuid.uuid4())[:8]

    animal_resp = client.post(
        "/api/v1/animals",
        json={"species": "dog", "name": f"Milo-{suffix}"},
        headers=HEADERS,
    )
    assert animal_resp.status_code == 200
    animal_id = animal_resp.json()["animal_id"]

    camera_resp = client.post(
        "/api/v1/cameras",
        json={"location_zone": f"zone-{suffix}", "installed_height_m": 2.8, "tilt_deg": 25.0},
        headers=HEADERS,
    )
    assert camera_resp.status_code == 200
    camera_id = camera_resp.json()["camera_id"]

    collar_resp = client.post(
        "/api/v1/collars",
        json={"animal_id": animal_id, "marker_id": f"A-{suffix}", "ble_id": f"B-{suffix}"},
        headers=HEADERS,
    )
    assert collar_resp.status_code == 200
    assert collar_resp.json()["animal_id"] == animal_id

    track_resp = client.post(
        "/api/v1/tracks",
        json={"camera_id": camera_id, "quality_score": 0.92},
        headers=HEADERS,
    )
    assert track_resp.status_code == 200
    track_id = track_resp.json()["track_id"]

    observation_resp = client.post(
        f"/api/v1/tracks/{track_id}/observations",
        json={"bbox": "[10,20,100,120]", "marker_id_read": f"A-{suffix}"},
        headers=HEADERS,
    )
    assert observation_resp.status_code == 200
    assert observation_resp.json()["track_id"] == track_id

    association_resp = client.post(
        "/api/v1/associations",
        json={
            "global_track_id": f"global-{suffix}",
            "track_id": track_id,
            "animal_id": animal_id,
            "confidence": 0.95,
        },
        headers=HEADERS,
    )
    assert association_resp.status_code == 200

    position_resp = client.post(
        "/api/v1/positions",
        json={"animal_id": animal_id, "x_m": 1.2, "y_m": 3.4, "method": "Uwb"},
        headers=HEADERS,
    )
    assert position_resp.status_code == 200

    event_resp = client.post(
        "/api/v1/events",
        json={"animal_id": animal_id, "type": "entered_zone", "severity": "info"},
        headers=HEADERS,
    )
    assert event_resp.status_code == 200
    event_id = event_resp.json()["event_id"]

    media_segment_resp = client.post(
        "/api/v1/media-segments",
        json={
            "camera_id": camera_id,
            "path": f"storage/uploads/{suffix}.mp4",
            "codec": "video/mp4",
            "avg_bitrate": 850.5,
        },
        headers=HEADERS,
    )
    assert media_segment_resp.status_code == 200

    clip_resp = client.post(
        "/api/v1/clips",
        json={
            "event_id": event_id,
            "path": f"storage/clips/{suffix}.mp4",
            "derived_from_segments": "seg-a,seg-b",
        },
        headers=HEADERS,
    )
    assert clip_resp.status_code == 200

    timeline_resp = client.get(
        f"/api/v1/animals/{animal_id}/timeline",
        headers=HEADERS,
    )
    assert timeline_resp.status_code == 200
    body = timeline_resp.json()

    kinds = {item["kind"] for item in body["timeline"]}
    assert "event" in kinds
    assert "position" in kinds

    observations_resp = client.get(
        f"/api/v1/tracks/{track_id}/observations",
        headers=HEADERS,
    )
    assert observations_resp.status_code == 200
    assert len(observations_resp.json()) >= 1
