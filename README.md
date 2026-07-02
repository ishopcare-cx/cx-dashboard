# cx-dashboard

CX팀 대시보드 — 채널톡 채팅 + 콜라비 전화 통계 자동수집 + 정적 웹 대시보드.

**🔗 대시보드: https://ishopcare-cx.github.io/cx-dashboard/**

## 개요

| 단계 | 데이터 | 어디서 | 어떻게 | 어디로 |
|------|--------|--------|--------|--------|
| ① 채팅 수집 | 채널톡 Open API | api.channel.io (인터넷) | **GitHub Actions** 매일 KST 23:30 | `chat_raw` 탭 |
| ② 전화 수집 | 콜라비 관리자 페이지 HTML 표 | callrabi.ishopcare.co.kr (회사 IP만) | **PC 작업 스케줄러** 평일 KST 17:30 | `call_daily` · `call_team_daily` · `call_voc_daily` 탭 |
| ③ 대시보드 | `chat_raw`·`call_*` | GitHub Actions (publish-dashboard, KST 23:45) | `build_data.py` → `docs/data.json` → GitHub Pages | 위 URL 접속 |

콜라비는 **회사 IP만 허용**해 GitHub Actions에서 접근 불가 → PC 의존. 채팅·대시보드 빌드는 GHA로 PC 무관.

## 대시보드

상위탭 **채팅 / 콜 / VOC / 민원** × 하위탭 **전체 / 스쿼드별 / 상담사별** + **두 기간 비교**(1번/2번, 증감%). 카드·표·라인차트.

**VOC 탭**: 채널 토글(전체=채팅+콜 합산 / 채팅만 / 콜만) — 위클리 리포트 형식 표 `순위 | 대분류 | 중분류 | 1번 건수 | 2번 건수 | 변화%`.

**민원 탭**: 주차 단위 집계(선택 기간에 겹치는 모든 주차 합산) — 민원유형 파이 + 보상 진행 파이 + 비교 표. 출처는 별도 시트 `cx-민원공유(슬랙) > 2026년 민원데이터`(이미 가공된 피벗) 직접 읽기.

매일 KST 23:45 자동 빌드 + 푸시 시 자동 재빌드.

> 데이터(상담사 이름·실적·VOC 분포)는 저장소 public이라 URL을 아는 누구나 접근 가능. 외부 노출 우려가 생기면 별도 호스팅(Cloudflare Access 등)으로 전환.

## ① 채팅 수집

- opened/snoozed/queued 상태는 전량, closed는 최근 `CX_COLLECT_DAYS`일분
  재수집 → `채팅ID` 기준 upsert (상태 변화·시간 지표 갱신 반영)
- **팀(전체) 지표**는 채널톡 상담통계 화면과 동일 기준: 첫응대시간_초 =
  `operationWaitingTime`(문의→첫응답), 평균응답시간·처리시간도
  `operation~`(미운영시간 제외) 필드 사용. 응대량은 응답 여부와 무관하게
  생성일 기준 전체 채팅 수(=인입, "당일 인입 100% 처리" 전제)
- **상담사별(개인) 지표**는 배정응답시간_초 = 배정(`firstOpenedAt`) →
  첫응답(`firstRepliedAtAfterOpen`) — 큐 대기시간 제외, 팀 지표와
  기준점이 다름(문의 시점이 아니라 배정 시점부터)
- 상담사 귀속(누가·언제 응대했는지)은 `config.TAG_FORMAT_CUTOVER`
  (2026-06-29) 이전/이후로 나뉜다 — 아래 `chat_raw 컬럼` 참고

## ② 전화 수집

- Playwright로 콜라비 로그인 → 세 페이지 HTML `<table>` 직접 추출
  (엑셀변환은 AES-256 DRM이라 사용 불가)
- 상담원별 일별: 오늘분 — 매일 누적
- 수신통계 일별 분류: 당월 전체 — 매일 upsert
- 상담통계(콜 VOC): 어제(확정) + 오늘(스냅샷) 두 번 fetch — `dateFrom`/`dateTo`
  flatpickr API로 단일 날짜씩 조회 후 `#reload`. 표에 일자 컬럼이 없어
  외부에서 주입.
- 키: `call_daily=일자_상담원ID`, `call_team_daily=일자`,
  `call_voc_daily=일자|대|중|소`

## chat_raw 컬럼

수집일시 · 채팅ID · 생성일 · 생성일시 · 종료일 · 상태 · 담당자 · 스쿼드 ·
첫응대시각 · 첫응대시간_초 · 평균응답시간_초 · 처리시간_초 · 응답수 ·
VOC태그 · 상담사태그 · 기타태그 · 배정일시 · 배정응답시간_초

태그는 3분류: `VOC태그`(`/` 포함), `상담사태그`, `기타태그`.

`상담사태그`는 실제 응대한 상담사를 수동 태그로 표시한 것(담당자=`담당자`
컬럼과 다를 수 있음). 2026-06-29 태그 형식이 바뀌어 `build_data.py`가
생성일 기준으로 다르게 해석한다(`config.TAG_FORMAT_CUTOVER`):

| | ~2026-06-28 | 2026-06-29~ |
|---|---|---|
| 태그 형식 | 날짜+이름 (`0522지은`) | 이름만 (`노지은`) |
| 귀속일 | 태그에 박힌 날짜 | `배정일시`(`firstOpenedAt`) 날짜 |
| 이름 매칭 | `config.TAG_NAME_MAP`(짧은이름→전체이름) | `config.ALL_AGENT_NAMES`(전체이름 그대로) |

## 구성

| 파일 | 역할 |
|------|------|
| `collect_chat.py` · `channeltalk.py` · `transform.py` | ① 채팅 수집 |
| `collect_call.py` · `colabee.py` · `transform_call.py` · `run_call.cmd` | ② 전화 수집 |
| `build_data.py` · `docs/index.html` · `docs/app.js` · `docs/style.css` | ③ 대시보드 |
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
