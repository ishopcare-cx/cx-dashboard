# VOC 파이차트 기타 드릴다운 패널 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** VOC 파이차트에서 `기타` 슬라이스를 클릭하면 우측에 세부 항목 테이블 패널이 토글로 열리고 닫힌다.

**Architecture:** `renderVoc()`에서 기타 세부 데이터를 별도 변수로 보존해 `drawPie()`에 전달한다. `drawPie()`는 Chart.js `onClick`을 등록해 `기타` 클릭 시 우측 패널을 토글한다. 패널은 HTML에 미리 숨겨진 상태로 존재하며 JS가 테이블을 채운다.

**Tech Stack:** Vanilla JS, Chart.js (기존), CSS flex

---

## 변경 파일 요약

| 파일 | 변경 내용 |
|------|-----------|
| `docs/index.html` | 파이차트 영역에 flex 래퍼 + 숨김 패널 div 추가 |
| `docs/style.css` | `.pie-flex-wrap`, `#voc-etc-panel` 스타일 추가 |
| `docs/app.js` | `renderVoc()` etcDetails 추출, `drawPie()` onClick 추가, `renderEtcPanel()` 함수 추가 |

---

## Task 1: index.html — 파이차트 영역 레이아웃 변경

**Files:**
- Modify: `docs/index.html`

> `renderVoc()`가 `pieWrap`을 동적으로 생성하므로 index.html에는 정적 뼈대가 없다.  
> 대신 **app.js의 `renderVoc()`** 안에서 DOM을 조립하는 방식으로 진행한다(Task 2에서 처리).  
> 이 Task는 확인용 — index.html을 열어 `voc-pie` 관련 정적 마크업이 없음을 확인한다.

- [ ] **Step 1: index.html에 voc-pie 관련 정적 마크업 없음을 확인**

```bash
grep -n "voc-pie\|voc-etc" docs/index.html
```

예상 출력: 아무것도 없음 (동적 생성 확인).

- [ ] **Step 2: 확인 후 커밋 없이 Task 2로 진행**

---

## Task 2: style.css — 파이 flex 래퍼 & 기타 패널 스타일 추가

**Files:**
- Modify: `docs/style.css`

- [ ] **Step 1: style.css 하단 `/* === 차트 === */` 섹션 아래에 스타일 추가**

`docs/style.css`의 `.chart-wrap` 블록 바로 아래(310번 줄 근처)에 추가:

```css
/* === VOC 기타 드릴다운 패널 === */
.pie-flex-wrap {
  display: flex;
  gap: 16px;
  align-items: flex-start;
  width: 100%;
}
.pie-flex-wrap .chart-wrap {
  flex: 1 1 0;
  min-width: 0;
}
#voc-etc-panel {
  width: 240px;
  flex-shrink: 0;
  background: #fff;
  border: 1px solid #e8eaee;
  border-radius: 8px;
  padding: 12px 14px;
  font-size: 14px;
}
#voc-etc-panel h3 {
  font-size: 13px;
  font-weight: 700;
  color: #374151;
  margin: 0 0 10px 0;
}
#voc-etc-panel table {
  width: 100%;
  border-collapse: collapse;
}
#voc-etc-panel th {
  font-size: 12px;
  color: #6b7280;
  font-weight: 600;
  text-align: center;
  padding: 4px 6px;
  border-bottom: 1px solid #e8eaee;
}
#voc-etc-panel td {
  font-size: 13px;
  text-align: center;
  padding: 5px 6px;
  border-bottom: 1px solid #f3f4f6;
  color: #111827;
}
#voc-etc-panel td:first-child {
  color: #6b7280;
  font-weight: 400;
}
#voc-etc-panel td:nth-child(2) {
  text-align: left;
  font-weight: 700;
}
#voc-etc-panel td:last-child {
  font-variant-numeric: tabular-nums;
  font-weight: 700;
}
#voc-etc-panel tr:last-child td {
  border-bottom: none;
}
```

- [ ] **Step 2: 로컬 서버 실행해 CSS 오류 없음을 확인**

```bash
cd docs && python -m http.server 8765
```

브라우저에서 `http://localhost:8765` 열어 기존 화면이 그대로인지 확인(파이차트 레이아웃 변화 없어야 함 — 아직 JS 변경 전).

- [ ] **Step 3: 커밋**

```bash
git add docs/style.css
git commit -m "style: VOC 기타 드릴다운 패널 스타일 추가"
```

---

## Task 3: app.js — renderVoc()에서 etcDetails 추출 및 DOM 조립

**Files:**
- Modify: `docs/app.js` (renderVoc 함수, 1413~1437번 줄 근처)

현재 코드:
```javascript
const cat1Etc = cat1Sorted.slice(VOC_PIE_TOPN).reduce((s, [, v]) => s + v, 0);
if (cat1Etc > 0) cat1A['기타'] = cat1Etc;
if (Object.keys(cat1A).length) {
  const pieWrap = document.createElement('div');
  pieWrap.className = 'pie-wrap';
  pieWrap.style.flexDirection = 'column';
  pieWrap.innerHTML = `
    <div class="panel" style="width:100%;">
      <h2>VOC 대분류 분포 — ${chLabel} (이번 기간)</h2>
      <div class="chart-wrap" style="height:440px;"><canvas id="voc-pie"></canvas></div>
    </div>`;
  main.appendChild(pieWrap);
  setTimeout(() => drawPie('voc-pie', cat1A, 'vocDistChart', { pctInside: true }), 0);
}
```

- [ ] **Step 1: etcDetails 추출 및 DOM 구조 변경**

위 코드 블록을 아래로 교체한다:

```javascript
const etcDetails = cat1Sorted.slice(VOC_PIE_TOPN); // [[대분류, 건수], ...]
const cat1Etc = etcDetails.reduce((s, [, v]) => s + v, 0);
if (cat1Etc > 0) cat1A['기타'] = cat1Etc;
if (Object.keys(cat1A).length) {
  const pieWrap = document.createElement('div');
  pieWrap.className = 'pie-wrap';
  pieWrap.style.flexDirection = 'column';
  pieWrap.innerHTML = `
    <div class="panel" style="width:100%;">
      <h2>VOC 대분류 분포 — ${chLabel} (이번 기간)</h2>
      <div class="pie-flex-wrap">
        <div class="chart-wrap" style="height:440px;"><canvas id="voc-pie"></canvas></div>
        <div id="voc-etc-panel" hidden></div>
      </div>
    </div>`;
  main.appendChild(pieWrap);
  setTimeout(() => drawPie('voc-pie', cat1A, 'vocDistChart', { pctInside: true, etcDetails }), 0);
}
```

- [ ] **Step 2: 로컬에서 화면 확인**

```bash
cd docs && python -m http.server 8765
```

VOC 탭 → 파이차트가 기존과 동일하게 보이는지 확인(패널은 아직 hidden).

- [ ] **Step 3: 커밋**

```bash
git add docs/app.js
git commit -m "feat: VOC renderVoc에 etcDetails 추출 및 드릴다운 패널 DOM 추가"
```

---

## Task 4: app.js — renderEtcPanel() 함수 및 drawPie() onClick 추가

**Files:**
- Modify: `docs/app.js`

- [ ] **Step 1: renderEtcPanel 함수를 drawPie 함수 바로 위에 추가**

`drawPie` 함수(1333번 줄) 바로 앞에 삽입:

```javascript
function renderEtcPanel(etcDetails) {
  const panel = document.getElementById('voc-etc-panel');
  if (!panel) return;
  if (!etcDetails || etcDetails.length === 0) return;
  const rows = etcDetails.map(([label, count], i) =>
    `<tr>
      <td>${i + 1}</td>
      <td>${label}</td>
      <td>${fmtNum(count)}</td>
    </tr>`
  ).join('');
  panel.innerHTML = `
    <h3>기타 세부 항목</h3>
    <table>
      <thead><tr><th>순위</th><th>대분류</th><th>건수</th></tr></thead>
      <tbody>${rows}</tbody>
    </table>`;
}
```

- [ ] **Step 2: drawPie() 함수에 onClick 핸들러 추가**

`drawPie` 함수의 `options` 객체 안, `plugins` 블록 바로 아래에 `onClick` 추가:

현재:
```javascript
options: {
  maintainAspectRatio: false,
  radius: '70%',
  pctInside: !!opts.pctInside,
  layout: { padding: { top: 24, bottom: 24, left: 130, right: 130 } },
  plugins: {
    legend: { display: false },
    tooltip: { enabled: false },
    datalabels: { display: false },
  },
},
```

변경 후:
```javascript
options: {
  maintainAspectRatio: false,
  radius: '70%',
  pctInside: !!opts.pctInside,
  layout: { padding: { top: 24, bottom: 24, left: 130, right: 130 } },
  plugins: {
    legend: { display: false },
    tooltip: { enabled: false },
    datalabels: { display: false },
  },
  onClick(e, elements) {
    if (!opts.etcDetails || opts.etcDetails.length === 0) return;
    if (!elements.length) return;
    const idx = elements[0].index;
    const clickedLabel = window[chartVar].data.labels[idx];
    if (clickedLabel !== '기타') return;
    const panel = document.getElementById('voc-etc-panel');
    if (!panel) return;
    if (panel.hidden) {
      renderEtcPanel(opts.etcDetails);
      panel.hidden = false;
    } else {
      panel.hidden = true;
    }
  },
},
```

- [ ] **Step 3: 채널 전환 시 패널 닫기 추가**

`renderVoc()` 함수 시작 부분에서 기존 패널 상태를 초기화한다.  
`renderVoc` 함수 안 `main.innerHTML = '';` 또는 초기화 부분을 찾아 아래 코드 추가:

```javascript
// 채널 전환 시 기타 패널 초기화
const prevEtcPanel = document.getElementById('voc-etc-panel');
if (prevEtcPanel) prevEtcPanel.hidden = true;
```

> `main.innerHTML = ''`이 이미 DOM을 초기화하므로 별도 처리 불필요할 수 있음.  
> `renderVoc` 상단에서 `main`을 비우는지 확인 후, 비우지 않는 경우에만 위 코드를 추가한다.

- [ ] **Step 4: 로컬에서 전체 동작 확인**

```bash
cd docs && python -m http.server 8765
```

체크리스트:
1. VOC 탭 진입 → 파이차트 정상 렌더
2. `기타` 슬라이스 클릭 → 우측에 기타 세부 항목 테이블 나타남
3. `기타` 슬라이스 다시 클릭 → 패널 닫힘
4. 다른 슬라이스 클릭 → 패널 변화 없음
5. 채널(전체/채팅/전화) 전환 → 패널 닫힘(DOM 재생성으로 자동 처리)
6. 기타가 없는 경우(항목 10개 이하) → 클릭해도 패널 안 열림

- [ ] **Step 5: 커밋**

```bash
git add docs/app.js
git commit -m "feat: VOC 파이차트 기타 클릭 시 세부 항목 드릴다운 패널 추가"
```

---

## Task 5: 배포 및 라이브 확인

**Files:** 없음 (push만)

- [ ] **Step 1: main 브랜치에 push**

```bash
git push origin main
```

- [ ] **Step 2: 1~2분 후 라이브에서 확인**

```
https://ishopcare-cx.github.io/cx-dashboard/
```

Ctrl+F5 강력 새로고침 후 VOC 탭 → 기타 클릭 동작 확인.
