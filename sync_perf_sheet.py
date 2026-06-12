"""창고 raw 탭 → 'CX 퍼포먼스(26.05~)' 시트의 Call Raw 두 탭에 적재.

매일 06:30 KST (GitHub Actions cron). 창고에 있는 날짜 전체를 순회하므로
토요일·연휴 등 수집 공백이 나중에 채워져도 자동으로 반영된다.
최근 UPSERT_DAYS일 이내 날짜는 기존 행 삭제 후 재기재(upsert) — 더 최신
수집분으로 덮어씀. 그보다 오래된 날짜는 신규만 추가(중복 방지).
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

# 이 기간 이내 날짜는 upsert(삭제 후 재기재), 그 이전은 신규만 추가.
UPSERT_DAYS = 5


def _read(sheet, tab):
    resp = sheet._api.values().get(
        spreadsheetId=sheet._id, range=f"'{tab}'!A:Z").execute()
    return resp.get("values", [])


def _fmt_date(iso):
    y, m, d = iso.split("-")
    return f"{int(y)}. {int(m)}. {int(d)}"


def _norm_date(s):
    m = re.match(r"(\d{4})\D+(\d{1,2})\D+(\d{1,2})", (s or "").strip())
    return f"{int(m[1]):04d}-{int(m[2]):02d}-{int(m[3]):02d}" if m else (s or "").strip()


def _col_offset(rows):
    header = rows[0] if rows else []
    return next((i for i, c in enumerate(header) if (c or "").strip()), 0)


def _warehouse_dates(rows):
    return sorted({
        r[2].strip()
        for r in rows[1:]
        if len(r) > 2 and (r[2] or "").strip()
    })


def _append(perf, tab, rows, off):
    perf._api.values().append(
        spreadsheetId=perf._id, range=f"'{tab}'!{_col_letter(off)}1",
        valueInputOption="USER_ENTERED",
        insertDataOption="INSERT_ROWS",
        body={"values": rows}).execute()


def _sync_tab_all(src_rows, perf, dst_tab, dates, upsert_dates):
    """퍼포먼스 탭에 날짜 목록 일괄 적재. 탭당 시트 읽기 1회."""
    try:
        perf_rows = _read(perf, dst_tab)
    except Exception as e:
        log.warning("'%s' 읽기 실패 — %s", dst_tab, e)
        return
    if not perf_rows:
        log.warning("'%s' 비어있음", dst_tab)
        return
    off = _col_offset(perf_rows)

    # 기존 키 맵 (upsert 대상 날짜의 행 인덱스 + 중복 방지 키)
    upsert_set = set(upsert_dates)
    to_delete_idx = []
    existing_keys = set()
    for i, row in enumerate(perf_rows[1:]):
        if len(row) <= off:
            continue
        nd = _norm_date(row[off])
        if nd in upsert_set:
            to_delete_idx.append(i + 2)   # 1-indexed, skip header
        elif (row[off] or "").strip() and len(row) > off + 1 and (row[off + 1] or "").strip():
            existing_keys.add(f"{nd}|{row[off + 1]}")

    # upsert 대상 행 일괄 삭제 (역순)
    if to_delete_idx:
        meta = perf._api.get(spreadsheetId=perf._id,
                             fields="sheets.properties").execute()
        sheet_id = next(
            (s["properties"]["sheetId"] for s in meta["sheets"]
             if s["properties"]["title"] == dst_tab), None)
        if sheet_id:
            requests = [
                {"deleteDimension": {"range": {
                    "sheetId": sheet_id, "dimension": "ROWS",
                    "startIndex": idx - 1, "endIndex": idx,
                }}}
                for idx in sorted(to_delete_idx, reverse=True)
            ]
            perf._api.batchUpdate(spreadsheetId=perf._id,
                                  body={"requests": requests}).execute()
            log.info("'%s' — upsert 대상 기존 %d행 삭제", dst_tab, len(to_delete_idx))

    # 날짜별 신규 행 수집 후 일괄 append
    all_new = []
    for date in dates:
        out = [
            [_fmt_date(date)] + [(c if c is not None else "") for c in r[3:]]
            for r in src_rows[1:]
            if len(r) >= 4 and (r[2] or "").strip() == date
        ]
        if not out:
            log.info("'%s' — %s 데이터 없음, 건너뜀", dst_tab, date)
            continue
        if date in upsert_set:
            all_new.extend(out)
            log.info("'%s' — %s upsert %d행", dst_tab, date, len(out))
        else:
            fresh = [row for row in out if f"{date}|{row[1]}" not in existing_keys]
            if fresh:
                all_new.extend(fresh)
                log.info("'%s'(열 %s~) ← %d행 추가 (전체 %d행 중 신규, 대상일 %s)",
                         dst_tab, _col_letter(off), len(fresh), len(out), date)
            else:
                log.info("'%s' — %s 이미 기록됨(중복 없음)", dst_tab, date)

    if all_new:
        _append(perf, dst_tab, all_new, off)
        log.info("'%s' — 총 %d행 적재 완료", dst_tab, len(all_new))


def main():
    today = datetime.datetime.now(KST).date()
    today_iso = today.isoformat()
    cutoff = (today - datetime.timedelta(days=UPSERT_DAYS)).isoformat()
    log.info("CX 퍼포먼스 시트 연동 시작 (오늘 %s 미만, upsert >= %s)", today_iso, cutoff)

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
        dates = [d for d in _warehouse_dates(rows) if d < today_iso]
        upsert_dates = [d for d in dates if d >= cutoff]
        log.info("%s 대상일 %d개 (upsert %d개: %s)",
                 src_tab, len(dates), len(upsert_dates), upsert_dates)
        _sync_tab_all(rows, perf, dst_tab, dates, upsert_dates)

    log.info("연동 완료")


if __name__ == "__main__":
    main()
