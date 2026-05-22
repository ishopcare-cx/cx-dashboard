# cx-dashboard

CX팀 대시보드 데이터 파이프라인. **1단계 — 채널톡 채팅 수집.**

## 개요

채널톡 Open API로 채팅 상담 데이터를 매일 수집해 구글 스프레드시트
`CX 대시보드 데이터`의 `chat_raw` 탭에 적재한다. **채팅 1건 = 1행.**

- 수집: `collect_chat.py` — GitHub Actions가 매일 KST 23:30 실행
- opened / snoozed / queued 상태는 전량, closed는 최근 `CX_COLLECT_DAYS`일분
  재수집 → `채팅ID` 기준 upsert (상태 변화·시간 지표 갱신 반영)
- 시간 지표는 `operation~`(미운영시간 제외) 필드 사용 — 채널톡 상담별
  통계 화면과 같은 기준

## chat_raw 컬럼

수집일시 · 채팅ID · 생성일 · 생성일시 · 종료일 · 상태 · 담당자 · 스쿼드 ·
첫응대시각 · 첫응대시간_초 · 평균응답시간_초 · 처리시간_초 · 응답수 ·
VOC태그 · 상담사태그 · 기타태그

태그는 3분류: `VOC태그`(`/` 포함), `상담사태그`(날짜+이름), `기타태그`.

## 구성

| 파일 | 역할 |
|------|------|
| `collect_chat.py` | 메인 — 수집·변환·적재 |
| `channeltalk.py` | 채널톡 Open API v5 클라이언트 |
| `transform.py` | 순수 변환 로직(태그 분류·행 생성) |
| `sheets.py` | 구글 시트 upsert |
| `google_credentials.py` | 구글 OAuth 자격증명 |
| `config.py` | 설정(시트 ID·스쿼드·헤더) |

## GitHub Actions 시크릿

`CHANNELTALK_ACCESS_KEY` · `CHANNELTALK_ACCESS_SECRET` ·
`GOOGLE_OAUTH_CLIENT_ID` · `GOOGLE_OAUTH_CLIENT_SECRET` ·
`GOOGLE_OAUTH_REFRESH_TOKEN`

## 로컬 실행

git에서 제외되는 두 파일을 두고 `python collect_chat.py`:

- `secrets_local.json` — `{"CHANNELTALK_ACCESS_KEY": "...", "CHANNELTALK_ACCESS_SECRET": "..."}`
- `oauth_local.json` — `{"client_id": "...", "client_secret": "...", "refresh_token": "..."}`

## 테스트

```
python test_transform.py
```
