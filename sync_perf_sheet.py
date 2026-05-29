"""창고 raw 탭 → 'CX 퍼포먼스(26.05~)' 시트의 Call Raw 두 탭에 전날치 적재.

매일 01시 KST (GitHub Actions cron). 본인 Google 계정 OAuth로 두 시트 모두 접근.
 - callraw_time → 'Call Raw(콜/상담시간)'  (일자·ID·이름·수신/직통/발신/호전달 건수·통화시간)
 - callraw_acw  → 'Call Raw(후처리)'       (기간·ID·이름·상담시간·후처리·대기·…·작업)

같은 (일자, 상담원ID) 행은 다시 안 쓴다(중복 방지). 헤더는 손대지 않는다.
"""
import datetime
import logging
import sys

import config
from google_credentials import build_credentials
from sheets import Sheet, _col_letter
from transform import KST

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
log = logging.getLogger(__name__)


def _read(sheet, tab):
    resp = sheet._api.values().get(
        spreadsheetId=sheet._id, range=f"'{tab}'!A:Z").execute()
    return resp.get("values", [])


def _fmt_date(iso):
    """'2026-05-28' → '2026. 5. 28' (시트 기존 표기와 동일, 앞자리 0 없음)."""
    y, m, d = iso.split("-")
    return f"{int(y)}. {int(m)}. {int(d)}"


def _table_info(perf, tab):
    """CX 탭의 (헤더 시작 열 offset, 기존 (날짜|상담원ID) 키 집합).

    데이터가 A가 아닌 B열부터 시작할 수 있어, 헤더 첫 비어있지 않은 셀로 offset 감지.
    반환 None이면 읽기 실패(안전상 적재 생략).
    """
    try:
        rows = _read(perf, tab)
    except Exception as e:
        log.warning("'%s' 읽기 실패 — %s", tab, e)
        return None
    if not rows:
        return 0, set()
    header = rows[0]
    off = next((i for i, c in enumerate(header) if (c or "").strip()), 0)
    keys = set()
    for r in rows[1:]:
        if len(r) > off + 1 and (r[off] or "").strip() and (r[off + 1] or "").strip():
            keys.add(f"{r[off]}|{r[off + 1]}")
    return off, keys


def _append(perf, tab, rows, off):
    perf._api.values().append(
        spreadsheetId=perf._id, range=f"'{tab}'!{_col_letter(off)}1",
        valueInputOption="USER_ENTERED",
        insertDataOption="INSERT_ROWS",
        body={"values": rows}).execute()


def _sync(warehouse, perf, src_tab, dst_tab, date):
    """warehouse src_tab에서 date행만 골라 dst_tab에 신규만 append.

    창고 헤더: [키, 수집일시, 일자, 상담원ID, …] → CX 탭은 일자(=날짜)부터.
    날짜는 시트 형식('2026. 5. 28')으로, 데이터 시작 열도 시트에 맞춰 정렬.
    """
    src = _read(warehouse, src_tab)
    if len(src) < 2:
        log.info("창고 '%s' 비어있음 — 건너뜀", src_tab)
        return
    out = []
    for r in src[1:]:
        if len(r) < 4 or (r[2] or "").strip() != date:   # 창고 col2 = 일자(ISO)
            continue
        # CX 행 = [날짜(시트형식), 상담원ID, …] = 창고 r[3:] 앞에 날짜
        out.append([_fmt_date(date)] + [(c if c is not None else "") for c in r[3:]])
    if not out:
        log.info("'%s' — %s 데이터 없음", src_tab, date)
        return
    info = _table_info(perf, dst_tab)
    if info is None:
        log.warning("'%s' 조회 실패 — 안전을 위해 적재 생략", dst_tab)
        return
    off, existing = info
    fresh = [row for row in out if f"{row[0]}|{row[1]}" not in existing]
    if not fresh:
        log.info("'%s' — %s 이미 기록됨(중복 없음)", dst_tab, date)
        return
    _append(perf, dst_tab, fresh, off)
    log.info("'%s'(열 %s~) ← %s: %d행 추가 (전체 %d행 중 신규)",
             dst_tab, _col_letter(off), src_tab, len(fresh), len(out))


def main():
    yesterday = (datetime.datetime.now(KST).date()
                 - datetime.timedelta(days=1)).isoformat()
    log.info("CX 퍼포먼스 시트 연동 — 대상일 %s", yesterday)
    creds = build_credentials()
    warehouse = Sheet(creds, config.SHEET_ID)
    perf = Sheet(creds, config.PERF_SHEET_ID)
    _sync(warehouse, perf, "callraw_time", config.PERF_TIME_TAB, yesterday)
    _sync(warehouse, perf, "callraw_acw", config.PERF_ACW_TAB, yesterday)
    log.info("연동 완료")


if __name__ == "__main__":
    main()
