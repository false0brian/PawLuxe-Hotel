# PawLuxe Hotel Backend

FastAPI 기반 반려동물 멀티카메라 트래킹/저장/Export 백엔드입니다.

## 현재 동작 방식
이 레포는 아래 파이프라인으로 동작합니다.

1. 카메라 등록
- `cameras` 테이블에 카메라 메타데이터(`stream_url`, 설치 정보) 저장

2. 트래킹
- 업로드 파일 기반: `POST /api/v1/videos/track`
- RTSP 실시간 기반: `python -m app.workers.rtsp_tracking_worker`
- 탐지: YOLO(Ultralytics)
- 추적/ReID: Engine `deep_sort`

3. 저장
- `tracks`, `track_observations`, `associations` 적재
- `global_identities`로 `global_track_id -> animal_id` 확정/미확정 상태 관리
- 옵션으로 원본 스트림을 세그먼트 MP4로 저장하고 `media_segments` 적재

4. Export
- 동기 Export API: `POST /api/v1/exports/global-track/{global_track_id}`
- Highlights API: `POST /api/v1/exports/global-track/{global_track_id}/highlights`
- 비동기 잡 큐: `POST /jobs` -> `export_job_worker`가 처리
- 결과 조회/다운로드: `GET /api/v1/exports/{export_id}`

## 트래킹 ID 정책
`rtsp_tracking_worker`의 `--global-id-mode`로 결정됩니다.

- `animal`
: 같은 `animal_id`를 카메라 간 강제 통합 (`global_track_id=animal:<animal_id>`)
- `camera_track`
: 카메라 내부 트랙 기준 (`<camera_id>:<source_track_id>`)
- `reid_auto`
: ReID 임베딩 코사인 유사도로 카메라 간 자동 통합

## 프로젝트 구조 요약
- `app/api/routes.py`: API 라우트
- `app/services/tracking_service.py`: YOLO + DeepSort 추론
- `app/workers/rtsp_tracking_worker.py`: RTSP 실시간 트래킹 워커
- `app/workers/multi_camera_tracking_worker.py`: 멀티카메라 워커 런처
- `app/workers/export_job_worker.py`: 비동기 Export 잡 워커
- `app/services/export_service.py`: Export 계획/렌더링
- `app/db/models.py`: SQLModel 스키마

## DB 테이블
- `animals`
- `collars`
- `cameras`
- `tracks`
- `track_observations`
- `positions`
- `associations`
- `global_track_profiles`
- `global_identities`
- `events`
- `media_segments`
- `clips`
- `video_analyses`
- `export_jobs`

기본 DB는 SQLite(`pawluxe.db`)이며 앱 시작 시 자동 생성됩니다.

## 로컬 실행
```bash
cd /home/brian/PawLuxe-Hotel
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

트래킹 런타임 의존성:
```bash
pip install -r requirements-tracking.txt
```

## PostgreSQL 전환
로컬 Postgres 실행:
```bash
cd /home/brian/PawLuxe-Hotel
docker compose -f docker-compose.postgres.yml up -d
```

`.env`에서 DB URL 변경:
```env
DATABASE_URL=postgresql+psycopg://pawluxe:pawluxe@127.0.0.1:5432/pawluxe
```

앱 재시작 시 SQLModel 테이블이 자동 생성됩니다.

참고:
- 기존 SQLite 데이터는 자동 마이그레이션되지 않습니다.
- 운영 전환 시에는 데이터 이관 스크립트(또는 ETL) 별도 수행이 필요합니다.

SQLite -> Postgres 이관 스크립트:
```bash
python scripts/migrate_sqlite_to_postgres.py \
  --source sqlite:///./pawluxe.db \
  --target postgresql+psycopg://pawluxe:pawluxe@127.0.0.1:5432/pawluxe \
  --on-conflict skip
```

드라이런(쓰기 없이 카운트만 확인):
```bash
python scripts/migrate_sqlite_to_postgres.py \
  --source sqlite:///./pawluxe.db \
  --target postgresql+psycopg://pawluxe:pawluxe@127.0.0.1:5432/pawluxe \
  --dry-run
```

## 주요 API
모든 `/api/v1/*`는 `x-api-key` 헤더 필요 (`GET /health` 제외).

기본 도메인:
- `POST /api/v1/animals`
- `GET /api/v1/animals`
- `POST /api/v1/cameras`
- `GET /api/v1/cameras`
- `POST /api/v1/collars`
- `GET /api/v1/collars`
- `POST /api/v1/tracks`
- `GET /api/v1/tracks`
- `POST /api/v1/tracks/{track_id}/observations`
- `GET /api/v1/tracks/{track_id}/observations`
- `POST /api/v1/associations`
- `GET /api/v1/associations`
- `GET /api/v1/identities/{global_track_id}`
- `PUT /api/v1/identities/{global_track_id}/animal`
- `POST /api/v1/events`
- `GET /api/v1/events`
- `POST /api/v1/positions`
- `POST /api/v1/media-segments`
- `GET /api/v1/media-segments`
- `POST /api/v1/clips`
- `GET /api/v1/clips`
- `GET /api/v1/animals/{animal_id}/timeline`

비디오 처리:
- `POST /api/v1/videos/process`
- `POST /api/v1/videos/track`
- `GET /api/v1/videos/{video_id}/analysis`

Export:
- `POST /api/v1/exports/global-track/{global_track_id}`
- `POST /api/v1/exports/global-track/{global_track_id}/highlights`
- `POST /api/v1/exports/global-track/{global_track_id}/jobs`
- `GET /api/v1/exports/jobs/{job_id}`
- `POST /api/v1/exports/jobs/{job_id}/cancel`
- `POST /api/v1/exports/jobs/{job_id}/retry`
- `GET /api/v1/exports/{export_id}`

## RTSP 워커 실행
```bash
python -m app.workers.rtsp_tracking_worker \
  --camera-id <camera_id> \
  --device cuda:0 \
  --global-id-mode reid_auto \
  --record-segments \
  --record-dir storage/uploads/segments \
  --segment-seconds 20
```

자주 쓰는 옵션:
- `--stream-url`: DB `camera.stream_url` 대신 직접 지정
- `--classes-csv`: 기본 `15,16` (cat,dog)
- `--reid-match-threshold`: `reid_auto` 임계값
- `--fallback-animal-id`: `reid_auto`에서 animal 매핑 없을 때 사용
- `--max-frames`, `--max-seconds`: 테스트 제한

## 멀티카메라 워커 실행
```bash
python -m app.workers.multi_camera_tracking_worker \
  --camera-ids <cam_id_1>,<cam_id_2> \
  --device cuda:0 \
  --global-id-mode reid_auto \
  --reid-match-threshold 0.68 \
  --fallback-animal-id system-reid-auto \
  --record-segments
```

## Export 사용 예
동기 Export:
```bash
curl -X POST "http://localhost:8000/api/v1/exports/global-track/<global_track_id>" \
  -H "x-api-key: replace-with-strong-api-key" \
  -H "Content-Type: application/json" \
  -d '{"padding_seconds":3.0,"merge_gap_seconds":0.2,"min_duration_seconds":0.3,"render_video":false}'
```

Highlights:
```bash
curl -X POST "http://localhost:8000/api/v1/exports/global-track/<global_track_id>/highlights" \
  -H "x-api-key: replace-with-strong-api-key" \
  -H "Content-Type: application/json" \
  -d '{"padding_seconds":2.0,"target_seconds":30.0,"per_clip_seconds":4.0,"merge_gap_seconds":0.2,"min_duration_seconds":0.3}'
```

비동기 잡:
```bash
# 잡 생성
curl -X POST "http://localhost:8000/api/v1/exports/global-track/<global_track_id>/jobs" \
  -H "x-api-key: replace-with-strong-api-key" \
  -H "Content-Type: application/json" \
  -d '{"mode":"highlights","padding_seconds":2.0,"target_seconds":30.0,"per_clip_seconds":4.0,"render_video":true,"timeout_seconds":600,"max_retries":3,"dedupe":true}'

# 워커 실행
python -m app.workers.export_job_worker

# 상태 조회
curl -H "x-api-key: replace-with-strong-api-key" \
  "http://localhost:8000/api/v1/exports/jobs/<job_id>"

# 취소
curl -X POST -H "x-api-key: replace-with-strong-api-key" \
  "http://localhost:8000/api/v1/exports/jobs/<job_id>/cancel"

# 재시도(실패/취소 상태에서만 가능)
curl -X POST -H "x-api-key: replace-with-strong-api-key" \
  "http://localhost:8000/api/v1/exports/jobs/<job_id>/retry"
```

`timeout_seconds`는 잡 전체 처리 시간 제한입니다. 초과 시 `TimeoutError`로 실패 처리되고, `max_retries` 범위 내에서 재시도됩니다.
PostgreSQL에서는 워커가 `FOR UPDATE SKIP LOCKED`로 job을 클레임하여 다중 워커 동시 실행 시 중복 처리 가능성을 줄입니다.
렌더링 완료 후에는 `storage/exports/videos/<export_id>_parts` 임시 디렉토리를 자동 정리합니다.

다운로드:
```bash
curl -L -H "x-api-key: replace-with-strong-api-key" \
  "http://localhost:8000/api/v1/exports/<export_id>?download=manifest" -o export.json

curl -L -H "x-api-key: replace-with-strong-api-key" \
  "http://localhost:8000/api/v1/exports/<export_id>?download=video" -o export.mp4
```

## systemd 상시 운영
추가된 파일:
- `deploy/systemd/pawluxe-rtsp@.service`
- `deploy/systemd/pawluxe-export-worker.service`
- `deploy/systemd/rtsp-worker-common.env`
- `deploy/systemd/rtsp-worker-example.env`
- `deploy/systemd/install_systemd.sh`
- `deploy/systemd/smoke_check.sh`

설치:
```bash
cd /home/brian/PawLuxe-Hotel
sudo bash deploy/systemd/install_systemd.sh
```

설치 스크립트가 현재 사용자와 프로젝트 루트를 자동 인식해 unit 파일에 반영합니다.

카메라 인스턴스 파일:
```bash
cp deploy/systemd/rtsp-worker-example.env deploy/systemd/rtsp-worker-cam1.env
# rtsp-worker-cam1.env에서 CAMERA_ID 수정
```

서비스 시작:
```bash
sudo systemctl enable --now pawluxe-export-worker.service
sudo systemctl enable --now pawluxe-rtsp@cam1.service
```

로그:
```bash
journalctl -u pawluxe-export-worker.service -f
journalctl -u pawluxe-rtsp@cam1.service -f
```

스모크 체크:
```bash
sudo bash deploy/systemd/smoke_check.sh --instance cam1
```
옵션:
- `--restart`: 체크 전에 서비스 재시작
- `--follow-logs`: 마지막 로그 출력 후 tail 모드 진입

## 운영상 주의사항
- SQLite는 단일 노드/중소 트래픽에는 적합하지만, 워커 수가 늘어나면 Postgres 전환 권장.
- `reid_auto`는 완전 무오류가 아니므로 임계값/카메라 배치/조명 조건 튜닝 필요.
- `render_video=true`는 ffmpeg CPU 사용량이 커서 비동기 잡 워커로 처리 권장.
- 카메라 시간 동기(NTP/PTP)가 맞지 않으면 cross-camera ID 품질이 크게 떨어질 수 있음.
