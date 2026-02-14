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
- `GET /api/v1/videos/{video_id}/analysis`

`GET /health`는 인증 없이 확인 가능합니다.

## 암호화 메모
- `ENCRYPTION_KEY`를 지정하면 해당 키를 우선 사용합니다.
- 키 형식이 Fernet base64 표준 키가 아니면 passphrase로 간주해 SHA-256으로 파생합니다.
- `ENCRYPTION_KEY` 미설정 시 `API_KEY` 기반 파생키를 사용합니다(운영에서는 별도 키 권장).
