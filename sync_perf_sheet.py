"""창고 raw 탭 → 'CX 퍼포먼스(26.05~)' 시트의 Call Raw 두 탭에 적재.

매일 06:30 KST (GitHub Actions cron). 창고에 있는 날짜 전체를 순회하므로
토요일·연휴 등 수집 공백이 나중에 채워져도 자동으로 반영된다.
같은 날짜의 기존 행은 삭제 후 재기재(upsert) — 더 최신 수집분으로 덮어씀.
헤더는 손대지 않는다.
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
    """'2026-05-28' → '2026. 5. 28'."""
    y, m, d = iso.split("-")
    return f"{int(y)}. {int(m)}. {int(d)}"


def _norm_date(s):
    m = re.match(r"(\d{4})\D+(\d{1,2})\D+(\d{1,2})", (s or "").strip())
    return f"{int(m[1]):04d}-{int(m[2]):02d}-{int(m[3]):02d}" if m else (s or "").strip()


def _col_offset(rows):
    header = rows[0] if rows else []
    return next((i for i, c in enumerate(header) if (c or "").strip()), 0)


def _append(perf, tab, rows, off):
    perf._api.values().append(
        spreadsheetId=perf._id, range=f"'{tab}'!{_col_letter(off)}1",
        valueInputOption="USER_ENTERED",
        insertDataOption="INSERT_ROWS",
        body={"values": rows}).execute()


def _warehouse_dates(rows):
    return sorted({
        r[2].strip()
        for r in rows[1:]
        if len(r) > 2 and (r[2] or "").strip()
    })


def _delete_date_rows(perf, tab, date):
    """퍼포먼스 시트에서 해당 날짜 행 전부 삭제. 삭제 행수 반환."""
    meta = perf._api.get(spreadsheetId=perf._id, fields="sheets.properties").execute()
    sheet_id = next(
        (s["properties"]["sheetId"] for s in meta["sheets"]
         if s["properties"]["title"] == tab), None)
    if sheet_id is None:
        return 0
    rows = _read(perf, tab)
    if not rows:
        return 0
    off = _col_offset(rows)
    to_delete = [
        i + 2
        for i, row in enumerate(rows[1:])
        if len(row) > off and _norm_date(row[off]) == date
    ]
    if not to_delete:
        return 0
    requests = [
        {"deleteDimension": {"range": {
            "sheetId": sheet_id, "dimension": "ROWS",
            "startIndex": idx - 1, "endIndex": idx,
        }}}
        for idx in sorted(to_delete, reverse=True)
    ]
    perf._api.batchUpdate(spreadsheetId=perf._id, body={"requests": requests}).execute()
    return len(to_delete)


def _get_offset(perf, tab):
    """탭 헤더 시작 열 offset. 읽기 실패 시 None."""
    try:
        rows = _read(perf, tab)
    except Exception as e:
        log.warning("'%s' 읽기 실패 — %s", tab, e)
        return None
    return _col_offset(rows)


def _sync_tab(src_rows, perf, dst_tab, date):
    out = []
    for r in src_rows[1:]:
        if len(r) < 4 or (r[2] or "").strip() != date:
            continue
        out.append([_fmt_date(date)] + [(c if c is not None else "") for c in r[3:]])
    if not out:
        log.info("'%s' — %s 데이터 없음, 건너뜀", dst_tab, date)
        return
    off = _get_offset(perf, dst_tab)
    if off is None:
        log.warning("'%s' 조회 실패 — 안전을 위해 적재 생략", dst_tab)
        return
    deleted = _delete_date_rows(perf, dst_tab, date)
    if deleted:
        log.info("'%s' — %s 기존 %d행 삭제", dst_tab, date, deleted)
    _append(perf, dst_tab, out, off)
    log.info("'%s'(열 %s~) ← %d행 기재 (대상일 %s)",
             dst_tab, _col_letter(off), len(out), date)


def main():
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
