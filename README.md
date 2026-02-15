# PawLuxe Hotel Backend

FastAPI 기반 반려동물 트래킹/영상 분석 백엔드입니다.

## 반영 내용 (deep-research-report 기반)
- 카메라 원본 + 메타데이터 분리 저장 구조
- 동물/목걸이/카메라/트랙/포지션/이벤트/미디어 세그먼트 도메인 모델
- 크로스카메라 연계를 위한 association 모델 및 API
- 통합 타임라인(`event + position + video_analysis`) 제공
- 영상 분석 결과 암호화 저장(Fernet)
- API Key 인증(`x-api-key`)

## DB 스키마
SQLModel 기준 테이블:
- `animals`
- `collars`
- `cameras`
- `tracks`
- `track_observations`
- `positions`
- `associations`
- `global_track_profiles`
- `events`
- `media_segments`
- `clips`
- `video_analyses`

기본 DB는 SQLite(`pawluxe.db`)이며 앱 시작 시 자동 생성됩니다.

## 실행
```bash
cd /home/brian/PawLuxe-Hotel
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

YOLO + DeepSort 트래킹까지 사용하려면 추가로 설치:
```bash
pip install -r requirements-tracking.txt
```

## 주요 API
아래 엔드포인트는 `x-api-key` 헤더가 필요합니다.

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
- `POST /api/v1/events`
- `GET /api/v1/events`
- `POST /api/v1/positions`
- `POST /api/v1/media-segments`
- `GET /api/v1/media-segments`
- `POST /api/v1/clips`
- `GET /api/v1/clips`
- `GET /api/v1/animals/{animal_id}/timeline`
- `POST /api/v1/videos/process`
- `POST /api/v1/videos/track`
- `GET /api/v1/videos/{video_id}/analysis`

`GET /health`는 인증 없이 확인 가능합니다.

## 암호화 메모
- `ENCRYPTION_KEY`를 지정하면 해당 키를 우선 사용합니다.
- 키 형식이 Fernet base64 표준 키가 아니면 passphrase로 간주해 SHA-256으로 파생합니다.
- `ENCRYPTION_KEY` 미설정 시 `API_KEY` 기반 파생키를 사용합니다(운영에서는 별도 키 권장).

## YOLO + DeepSort 메모
- `POST /api/v1/videos/track`는 업로드 비디오에서 YOLO 탐지 + Engine의 `deep_sort` ReID를 실행합니다.
- 기본 `classes_csv`는 COCO 기준 반려동물 클래스 `15,16`(cat,dog)입니다.
- `ENGINE_ROOT`는 `/mnt/d/99.C-lab/git/Engine`을 기본값으로 사용합니다.
- `DEEP_SORT_MODEL`은 모델 이름(자동 다운로드) 또는 `.pth` 절대경로를 사용할 수 있습니다.

## RTSP 실시간 워커
카메라 `stream_url`을 계속 읽어 실시간으로 `tracks`, `track_observations`, `associations`를 적재합니다.

실행 예시:
```bash
cd /home/brian/PawLuxe-Hotel
source .venv/bin/activate
python -m app.workers.rtsp_tracking_worker \
  --camera-id <camera_id> \
  --animal-id <animal_id> \
  --device cuda:0 \
  --classes-csv 15,16
```

옵션:
- `--stream-url`: DB `camera.stream_url` 대신 직접 RTSP URL 지정
- `--max-frames`: 테스트용으로 프레임 수 제한
- `--max-seconds`: 테스트용으로 실행 시간 제한
- `--commit-interval-frames`: DB 커밋 주기(기본 30프레임)
- `--global-id-mode`: `animal`(기본) 또는 `camera_track`
  - `animal`: 같은 `animal_id`면 카메라가 달라도 `global_track_id=animal:<animal_id>`로 통합
  - `camera_track`: `global_track_id=<camera_id>:<source_track_id>`
  - `reid_auto`: `deep_sort` ReID 임베딩 코사인 유사도로 카메라 간 자동 통합
- `--reid-match-threshold`: `reid_auto` 매칭 임계값(기본 0.68)
- `--fallback-animal-id`: `reid_auto`에서 animal 매핑이 없을 때 association 저장용 animal_id

멀티카메라 실행 예시:
```bash
python -m app.workers.multi_camera_tracking_worker \
  --camera-ids <camera_id_1>,<camera_id_2> \
  --camera-animal-map '{"<camera_id_1>":"<animal_id>","<camera_id_2>":"<animal_id>"}' \
  --device cuda:0 \
  --global-id-mode animal
```

animal 맵 없이 ReID 자동 통합:
```bash
python -m app.workers.multi_camera_tracking_worker \
  --camera-ids <camera_id_1>,<camera_id_2> \
  --device cuda:0 \
  --global-id-mode reid_auto \
  --reid-match-threshold 0.68 \
  --fallback-animal-id system-reid-auto
```
