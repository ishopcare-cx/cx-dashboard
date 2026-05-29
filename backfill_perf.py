"""과거 1일치 백필 — CALLRABi에서 그 날짜를 스크랩해 CX 퍼포먼스 Call Raw 2탭에 추가.

회사망 PC에서만 실행 가능(콜라비 스크래핑). 기존 데이터는 건드리지 않고,
같은 (날짜|상담원ID) 행은 중복으로 안 넣는다(append-only, 안전).

사용:  python backfill_perf.py 2026-05-26
       (날짜 생략 시 어제)
"""
import datetime
import logging
import sys

import config
from collect_call import _credentials
from colabee import Colabee
from google_credentials import build_credentials
from sheets import Sheet
from transform import KST
from transform_call import agent_state_row, callraw_time_row
from sync_perf_sheet import _append, _fmt_date, _table_info

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
log = logging.getLogger(__name__)


def _push(perf, dst_tab, rows, date):
    """warehouse 포맷 rows([키,수집일시,일자,상담원ID,…])를 CX 탭에 신규만 추가."""
    out = [[_fmt_date(date)] + [(c if c is not None else "") for c in r[3:]]
           for r in rows if len(r) >= 4]
    if not out:
        log.info("'%s' — %s 데이터 없음 (스크랩 결과 0행)", dst_tab, date)
        return
    info = _table_info(perf, dst_tab)
    if info is None:
        log.warning("'%s' 조회 실패 — 적재 생략", dst_tab)
        return
    off, existing = info
    fresh = [r for r in out if f"{date}|{r[1]}" not in existing]   # ISO 날짜 기준
    if not fresh:
        log.info("'%s' — %s 이미 기록됨(중복)", dst_tab, date)
        return
    _append(perf, dst_tab, fresh, off)
    log.info("'%s' ← %d행 추가 (%s, 스크랩 %d행)", dst_tab, len(fresh), date, len(out))


def main():
    date = (sys.argv[1] if len(sys.argv) > 1
            else (datetime.datetime.now(KST).date()
                  - datetime.timedelta(days=1)).isoformat())
    datetime.date.fromisoformat(date)   # 형식 검증
    log.info("백필 시작 — 대상일 %s", date)

    cfg = _credentials()
    now = datetime.datetime.now(KST)
    with Colabee(cfg["base_url"], cfg["username"], cfg["password"]) as cb:
        log.info("▶ 상담원별 일별 통계 — %s", date)
        agent_table = cb.fetch_agent_daily(date)
        log.info("  %d행", len(agent_table))
        log.info("▶ 상담원 상태 통계(후처리) — %s", date)
        state_table = cb.fetch_agent_state_stat(date)
        log.info("  %d행", len(state_table))

    time_rows = [r for r in (callraw_time_row(row, now) for row in agent_table)
                 if r is not None and len(r) > 2 and r[2] == date]
    acw_rows = [r for r in (agent_state_row(row, date, now) for row in state_table)
                if r is not None]

    creds = build_credentials()
    perf = Sheet(creds, config.PERF_SHEET_ID)
    _push(perf, config.PERF_TIME_TAB, time_rows, date)
    _push(perf, config.PERF_ACW_TAB, acw_rows, date)
    log.info("백필 완료 — %s", date)


if __name__ == "__main__":
    main()
