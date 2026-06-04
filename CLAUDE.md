# CLAUDE.md — CX 대시보드 작업 가이드 (팀 공용)

이 레포를 Claude Code로 열면 이 파일이 자동으로 로드됩니다. **대시보드 화면을 수정하려는 팀원**을 위한 안내입니다. (데이터 파이프라인 전체 설명은 `README.md` 참고)

---

## 무엇을 수정하나 — 거의 항상 `docs/` 세 파일

대시보드 UI는 **빌드 과정 없는 정적 사이트**(Vanilla JS + Chart.js CDN)입니다.

| 파일 | 역할 | 주로 여기서 고침 |
|------|------|------------------|
| `docs/app.js` | 모든 렌더링 로직(탭·카드·표·차트·파이) | 표/차트 내용·동작 |
| `docs/style.css` | 전체 스타일(테마·카드·표·매트릭스) | 색·여백·글자 |
| `docs/index.html` | 상단 탭·기간 선택 등 골격 | 탭 추가/문구 |

> `docs/data.json` 은 **CI가 자동 생성**(`build_data.py`)합니다. **직접 수정 금지** — 손으로 고쳐도 다음 빌드에 덮어써집니다.

---

## 미리보기 (로컬)

```bash
cd docs
python -m http.server 8765
# 브라우저에서 http://localhost:8765
```
`data.json`이 레포에 같이 들어있어 실제 데이터로 바로 보입니다. (Claude Code의 preview 도구가 있으면 그걸 써도 됩니다)

## 배포

**`main`에 commit + push 하면 GitHub Pages가 자동 재배포**합니다(약 1~2분). 별도 빌드/배포 명령 없음.
- 라이브: https://ishopcare-cx.github.io/cx-dashboard/
- 확인 시 **Ctrl+F5**(강력 새로고침)

---

## 디자인 규칙 (이걸 지켜야 일관됩니다)

**팔레트** (`docs/app.js` 상단 상수)
- 인입/주지표 = 인디고 `#6366f1` (`CH_IN`) · 응대/보조 = 틸 `#2dd4bf` (`CH_ANS`) · 비율/강조 = 앰버 `#f59e0b` (`CH_RATE`)
- 파이는 파스텔 `PASTEL_PIE`

**막대·라인 차트** (`drawRespRate`, `drawTrend`)
- **값 라벨 항상 노출** — `barChip()` 헬퍼(흰 칩 + 색 테두리 + 굵은 글씨, 막대 위). 라인 비율은 앰버 알약.
- 둥근 막대, 옅은 가로 그리드, hover 툴팁 off. 데이터 14개 초과 시 막대 라벨 격일로 솎음.
- 라벨 플러그인은 차트마다 `plugins: [ChartDataLabels]`로 등록.

**파이** (`drawPie` + 커스텀 `pieOutLabels` 플러그인)
- 조각 **바깥 = 지시선 + 라벨**, 작은 조각이 몰리면 **좌/우 컬럼 정렬 + 위아래 자동 분산(안티콜리전)**으로 겹침 방지.
- `drawPie(canvas, data, varName, { pctInside })`:
  - 기본(민원) = 조각 안 **건수**, 바깥 **이름 + %**
  - `pctInside: true`(VOC) = 조각 안 **% 만**, 바깥 **이름만**. 얇은 조각은 % 를 자동으로 바깥(이름+%)으로 빼서 겹침 방지.

**VOC 표** (`renderVoc`)
- 위클리 리포트 형식: 2단 헤더(이번/비교 기간) · **인입건수 헤더=분홍 / 전주건수=크림** (`.voc-table`)
- 증감률은 VOC 전용 `fmtVocDelta` — **증가=빨강 / 감소=파랑**(VOC는 늘면 나쁨), 화살표 없이 부호 %
- 단일(퍼포먼스) 모드(`state.mode === 'single'`)에선 비교 컬럼(전주건수·증감률) 숨김
- 표 위에 'VOC 대분류 분포' 파이(상위 10 + 기타, `VOC_PIE_TOPN`)

**가독성** (`docs/style.css`)
- 본문 15px·텍스트 `#111827`, 카드 값 34px + 왼쪽 컬러바 + 증감 배지, 표 헤더 강조·zebra·숫자 굵게
- 개인별 매트릭스(`.ins-matrix`)는 `width: fit-content`로 폭 압축, 숫자 진하게

**핵심 함수 위치** (`docs/app.js`)
- 탭별 렌더: `renderChat` / `renderCall` / `renderVoc` / `renderComplaint`
- 카드: `makeCardGrid` · 표 공통: `tablePanel` · 매트릭스: `squadAgentMatrix`
- 차트: `drawRespRate` · `drawTrend` · `drawPie`(+`pieOutLabels`)

---

## ⚠️ 건드리지 말 것 (데이터 수집 쪽)

다음은 **원 소유자 PC + 계정 + 비밀키**에 묶여 돌아갑니다. **프론트(`docs/`)만 고치는 한 안전**하고, 아래는 손대지 마세요(설정 없으면 어차피 안 돌아감):
- Python 수집 스크립트: `collect_chat.py`, `collect_call.py`, `colabee.py`, `build_data.py`, `config.py` 등
- `.github/workflows/*` (GitHub Actions)
- 로컬 비밀파일(`*_local.json`) — git에 **절대 커밋 금지**(`.gitignore`에 있음)

데이터가 안 보이거나 수집 관련 문제는 코드 수정 대신 **원 담당자(노지은)** 에게 문의.

---

## 작업 순서 (권장)

1. `docs/` 수정 → 로컬 미리보기로 확인
2. 작은 단위로 `main`에 commit + push
3. 1~2분 뒤 라이브 URL에서 Ctrl+F5로 확인
4. 큰 변경이면 브랜치 + PR로 리뷰 받기

커밋 메시지는 한국어로 무엇을 왜 바꿨는지 한 줄이면 충분합니다.
