"""특정 날짜의 CX 퍼포먼스 행을 삭제하고 창고에서 재삽입.

사용: python force_resync.py 2026-06-04 2026-06-05
"""
import datetime
import logging
import re
import sys

import config
from google_credentials import build_credentials
from sheets import Sheet, _col_letter
from sync_perf_sheet import _read, _fmt_date, _norm_date, _append, _warehouse_dates

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s",
                    handlers=[logging.StreamHandler(sys.stdout)])
log = logging.getLogger(__name__)


def _get_sheet_id(sheet, tab_name):
    """탭 이름 → sheetId 숫자."""
    meta = sheet._api.get(spreadsheetId=sheet._id, fields="sheets.properties").execute()
    for s in meta.get("sheets", []):
        if s["properties"]["title"] == tab_name:
            return s["properties"]["sheetId"]
    return None


def _delete_rows_for_dates(sheet, tab_name, dates):
    """dates에 해당하는 행을 역순으로 삭제 (행 번호 밀림 방지)."""
    sheet_id = _get_sheet_id(sheet, tab_name)
    if sheet_id is None:
        log.warning("탭 '%s' 없음", tab_name)
        return

    rows = _read(sheet, tab_name)
    if not rows:
        return

    header = rows[0]
    off = next((i for i, c in enumerate(header) if (c or "").strip()), 0)

    # 삭제할 행 인덱스(0-based) 수집 — 역순으로 삭제해야 인덱스 안 밀림
    to_delete = []
    for i, r in enumerate(rows[1:], start=1):
        if len(r) <= off:
            continue
        row_date = _norm_date((r[off] or "").strip())
        if row_date in dates:
            to_delete.append(i)  # 0-based row index in sheet

    if not to_delete:
        log.info("'%s' — 삭제 대상 행 없음", tab_name)
        return

    log.info("'%s' — %d행 삭제 예정: 시트행 %s", tab_name, len(to_delete), to_delete[:5])

    # 역순 정렬 후 batchUpdate deleteRange
    requests = []
    for row_idx in sorted(to_delete, reverse=True):
        requests.append({
            "deleteDimension": {
                "range": {
                    "sheetId": sheet_id,
                    "dimension": "ROWS",
                    "startIndex": row_idx,
                    "endIndex": row_idx + 1,
                }
            }
        })

    sheet._api.batchUpdate(spreadsheetId=sheet._id, body={"requests": requests}).execute()
    log.info("'%s' — %d행 삭제 완료", tab_name, len(to_delete))


def _sync_tab_forced(src_rows, perf, dst_tab, date):
    """창고 rows에서 date 행을 추출해 perf 탭에 삽입 (이미 삭제된 상태)."""
    out = []
    for r in src_rows[1:]:
        if len(r) < 4 or (r[2] or "").strip() != date:
            continue
        out.append([_fmt_date(date)] + [(c if c is not None else "") for c in r[3:]])
    if not out:
        log.info("'%s' — %s 창고 데이터 없음", dst_tab, date)
        return

    rows_all = _read(perf, dst_tab)
    header = rows_all[0] if rows_all else []
    off = next((i for i, c in enumerate(header) if (c or "").strip()), 0)

    _append(perf, dst_tab, out, off)
    log.info("'%s' ← %d행 삽입 완료 (대상일 %s)", dst_tab, len(out), date)


def main():
    if len(sys.argv) < 2:
        print("사용: python force_resync.py 2026-06-04 2026-06-05")
        sys.exit(1)

    target_dates = sys.argv[1:]
    log.info("강제 재삽입 대상일: %s", target_dates)

    creds = build_credentials()
    warehouse = Sheet(creds, config.SHEET_ID)
    perf = Sheet(creds, config.PERF_SHEET_ID)

    for src_tab, dst_tab in [
        ("callraw_time", config.PERF_TIME_TAB),
        ("callraw_acw",  config.PERF_ACW_TAB),
    ]:
        log.info("=== %s → %s ===", src_tab, dst_tab)
        src_rows = _read(warehouse, src_tab)
        if len(src_rows) < 2:
            log.info("창고 '%s' 비어있음", src_tab)
            continue

        _delete_rows_for_dates(perf, dst_tab, set(target_dates))
        for date in target_dates:
            _sync_tab_forced(src_rows, perf, dst_tab, date)

    log.info("완료")


if __name__ == "__main__":
    main()
