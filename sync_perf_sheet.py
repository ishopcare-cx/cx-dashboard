"""창고 raw 탭 → 'CX 퍼포먼스(26.05~)' 시트의 Call Raw 두 탭에 적재.

매일 01시 KST (GitHub Actions cron). 창고에 있는 날짜 전체를 순회하므로
토요일·연휴 등 수집 공백이 나중에 채워져도 자동으로 반영된다.
같은 (일자, 상담원ID) 행은 다시 안 쓴다(중복 방지). 헤더는 손대지 않는다.
"""
import datetime
import logging
import re
import sys

import config
from google_credentials import build_credentials
from sheets import Sheet, _col_letter
from transform import KST

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
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


def _norm_date(s):
    """표시형식 무관하게 'YYYY-MM-DD'로 정규화. '2026. 5. 6'·'2026-05-06' 모두 동일.

    중복 방지 키 비교용 — 탭마다 날짜 표시형식이 달라(ISO vs '2026. 5. 26') 정규화 필요.
    """
    m = re.match(r"(\d{4})\D+(\d{1,2})\D+(\d{1,2})", (s or "").strip())
    return f"{int(m[1]):04d}-{int(m[2]):02d}-{int(m[3]):02d}" if m else (s or "").strip()


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
            keys.add(f"{_norm_date(r[off])}|{r[off + 1]}")   # 날짜 정규화 키
    return off, keys


def _append(perf, tab, rows, off):
    perf._api.values().append(
        spreadsheetId=perf._id, range=f"'{tab}'!{_col_letter(off)}1",
        valueInputOption="USER_ENTERED",
        insertDataOption="INSERT_ROWS",
        body={"values": rows}).execute()


def _warehouse_dates(rows):
    """창고 rows(헤더 포함)에서 유니크 날짜(ISO) 목록을 과거→최신 순으로 반환.

    창고 col2(index 2) = 일자(ISO 'YYYY-MM-DD').
    """
    return sorted({
        r[2].strip()
        for r in rows[1:]
        if len(r) > 2 and (r[2] or "").strip()
    })


def _sync_tab(src_rows, perf, dst_tab, date):
    """미리 읽어둔 창고 rows에서 date에 해당하는 행만 골라 dst_tab에 신규만 적재."""
    out = []
    for r in src_rows[1:]:
        if len(r) < 4 or (r[2] or "").strip() != date:
            continue
        # CX 행 = [날짜(시트형식), 상담원ID, …] = 창고 r[3:] 앞에 날짜
        out.append([_fmt_date(date)] + [(c if c is not None else "") for c in r[3:]])
    if not out:
        log.info("'%s' — %s 데이터 없음, 건너뜀", dst_tab, date)
        return
    info = _table_info(perf, dst_tab)
    if info is None:
        log.warning("'%s' 조회 실패 — 안전을 위해 적재 생략", dst_tab)
        return
    off, existing = info
    fresh = [row for row in out if f"{date}|{row[1]}" not in existing]
    if not fresh:
        log.info("'%s' — %s 이미 기록됨(중복 없음)", dst_tab, date)
        return
    _append(perf, dst_tab, fresh, off)
    log.info("'%s'(열 %s~) ← %d행 추가 (전체 %d행 중 신규, 대상일 %s)",
             dst_tab, _col_letter(off), len(fresh), len(out), date)


def main():
    # 오늘(수집 중인 당일)은 아직 완성되지 않은 데이터일 수 있어 제외.
    today = datetime.datetime.now(KST).date().isoformat()
    log.info("CX 퍼포먼스 시트 연동 시작 (오늘 %s 미만 날짜 전체)", today)
    creds = build_credentials()
    warehouse = Sheet(creds, config.SHEET_ID)
    perf = Sheet(creds, config.PERF_SHEET_ID)

    for src_tab, dst_tab in [
        ("callraw_time", config.PERF_TIME_TAB),
        ("callraw_acw",  config.PERF_ACW_TAB),
    ]:
        rows = _read(warehouse, src_tab)
        if len(rows) < 2:
            log.info("창고 '%s' 비어있음 — 건너뜀", src_tab)
            continue
        dates = [d for d in _warehouse_dates(rows) if d < today]
        log.info("%s 대상일 %d개: %s", src_tab, len(dates), dates)
        for date in dates:
            _sync_tab(rows, perf, dst_tab, date)

    log.info("연동 완료")


if __name__ == "__main__":
    main()
