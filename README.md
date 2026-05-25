# cx-dashboard

CX팀 대시보드 데이터 파이프라인. **1단계 채팅(채널톡) + 2단계 전화(콜라비)** 자동수집.

## 개요

| 단계 | 데이터 | 어디서 | 어떻게 | 어디로 |
|------|--------|--------|--------|--------|
| ① 채팅 | 채널톡 Open API | api.channel.io (인터넷) | **GitHub Actions** 매일 KST 23:30 | `chat_raw` 탭 |
| ② 전화 | 콜라비 관리자 페이지 HTML 표 | callrabi.ishopcare.co.kr (회사 IP만) | **PC 작업 스케줄러** 평일 KST 17:30 | `call_daily` · `call_team_daily` 탭 |

콜라비는 **회사 IP만 허용**해 GitHub Actions에서 접근 불가 → PC 의존. 채팅은 GHA로 PC 무관.

## ① 채팅 수집

- opened/snoozed/queued 상태는 전량, closed는 최근 `CX_COLLECT_DAYS`일분
  재수집 → `채팅ID` 기준 upsert (상태 변화·시간 지표 갱신 반영)
- 시간 지표는 `operation~`(미운영시간 제외) 필드 사용 — 채널톡 상담별
  통계 화면과 같은 기준

## ② 전화 수집

- Playwright로 콜라비 로그인 → 두 페이지 HTML `<table>` 직접 추출
  (엑셀변환은 AES-256 DRM이라 사용 불가)
- 상담원별 일별: 오늘분 — 매일 누적
- 수신통계 일별 분류: 당월 전체 — 매일 upsert
- 키: `call_daily=일자_상담원ID`, `call_team_daily=일자`

## chat_raw 컬럼

수집일시 · 채팅ID · 생성일 · 생성일시 · 종료일 · 상태 · 담당자 · 스쿼드 ·
첫응대시각 · 첫응대시간_초 · 평균응답시간_초 · 처리시간_초 · 응답수 ·
VOC태그 · 상담사태그 · 기타태그

태그는 3분류: `VOC태그`(`/` 포함), `상담사태그`(날짜+이름), `기타태그`.

## 구성

| 파일 | 역할 |
|------|------|
| `collect_chat.py` · `channeltalk.py` · `transform.py` | ① 채팅 수집 |
| `collect_call.py` · `colabee.py` · `transform_call.py` · `run_call.cmd` | ② 전화 수집 |
| `sheets.py` · `google_credentials.py` · `config.py` | 공통 (시트 쓰기·OAuth·설정) |

## GitHub Actions 시크릿 (① 채팅용)

`CHANNELTALK_ACCESS_KEY` · `CHANNELTALK_ACCESS_SECRET` ·
`GOOGLE_OAUTH_CLIENT_ID` · `GOOGLE_OAUTH_CLIENT_SECRET` ·
`GOOGLE_OAUTH_REFRESH_TOKEN`

## PC 스케줄러 (② 전화용)

Windows 작업 스케줄러 — 작업명 `CXDashboardCall`, 평일 17:30 KST, `run_call.cmd` 실행.
자격증명은 로컬 파일(git 제외): `colabee_local.json`, `oauth_local.json`.

## 로컬 실행 (테스트용)

git 제외 파일 두고 `python collect_chat.py` / `python collect_call.py`:

- `secrets_local.json` — `{"CHANNELTALK_ACCESS_KEY": "...", "CHANNELTALK_ACCESS_SECRET": "..."}`
- `oauth_local.json` — `{"client_id": "...", "client_secret": "...", "refresh_token": "..."}`
- `colabee_local.json` — `{"username": "...", "password": "...", "base_url": "..."}`

## 테스트

```
python test_transform.py
```
