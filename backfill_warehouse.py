"""창고 시트(CX 대시보드 데이터) 과거일 백필 — 콜라비 재스크랩 → upsert.

월말·주말 누락분 복구용. 회사망 PC에서만 실행(콜라비 접근).
upsert(키 기준)라 재실행해도 안전.

사용:  python backfill_warehouse.py 2026-05-30 2026-05-31 2026-06-01
       (날짜 생략 시 어제 하루)

팀(call_team_daily)은 페이지가 '당월 전체'라 대상일들이 속한 각 달을
연/월 셀렉트로 골라 통째 upsert한다.
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
from transform_call import (
    CALL_DAILY_HEADER, CALL_TEAM_DAILY_HEADER, CALL_VOC_DAILY_HEADER,
    CALLRAW_TIME_HEADER, CALLRAW_ACW_HEADER,
    agent_row, agent_state_row, call_voc_row, callraw_time_row, team_row,
)

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
log = logging.getLogger(__name__)


def main():
    dates = sys.argv[1:] or [
        (datetime.datetime.now(KST).date() - datetime.timedelta(days=1)).isoformat()]
    for d in dates:
        datetime.date.fromisoformat(d)   # 형식 검증
    log.info("백필 대상일: %s", ", ".join(dates))

    cfg = _credentials()
    now = datetime.datetime.now(KST)
    months = sorted({d[:7] for d in dates})   # 'YYYY-MM'

    agent_rows, time_rows, voc_rows, acw_rows, team_rows = [], [], [], [], []
    with Colabee(cfg["base_url"], cfg["username"], cfg["password"]) as cb:
        # 1) 팀(수신통계) — 대상 월별로 통째
        for ym in months:
            y, m = int(ym[:4]), int(ym[5:7])
            log.info("▶ 수신통계 일별 분류 — %s", ym)
            tbl = cb.fetch_recv_daily(y, m)
            log.info("  표 %d행", len(tbl))
            team_rows += [r for r in (team_row(row, ym, now) for row in tbl)
                          if r is not None]

        # 2) 상담원별·VOC·후처리 — 날짜별
        for d in dates:
            log.info("▶ 상담원별 일별 통계 — %s", d)
            at = cb.fetch_agent_daily(d)
            log.info("  표 %d행", len(at))
            agent_rows += [r for r in (agent_row(row, now) for row in at)
                           if r is not None and r[2] == d]
            time_rows += [r for r in (callraw_time_row(row, now) for row in at)
                          if r is not None and r[2] == d]

            log.info("▶ 상담통계(콜 VOC) — %s", d)
            vt = cb.fetch_counsel_stat(d)
            log.info("  표 %d행", len(vt))
            voc_rows += [r for r in (call_voc_row(row, d, now) for row in vt) if r]

            log.info("▶ 상담원 상태 통계(후처리) — %s", d)
            st = cb.fetch_agent_state_stat(d)
            log.info("  표 %d행", len(st))
            acw_rows += [r for r in (agent_state_row(row, d, now) for row in st) if r]

    log.info("변환: agent %d / team %d / voc %d / time %d / acw %d",
             len(agent_rows), len(team_rows), len(voc_rows),
             len(time_rows), len(acw_rows))

    sheet = Sheet(build_credentials(), config.SHEET_ID)
    jobs = [
        ("call_daily", CALL_DAILY_HEADER, agent_rows),
        ("call_team_daily", CALL_TEAM_DAILY_HEADER, team_rows),
        ("call_voc_daily", CALL_VOC_DAILY_HEADER, voc_rows),
        ("callraw_time", CALLRAW_TIME_HEADER, time_rows),
        ("callraw_acw", CALLRAW_ACW_HEADER, acw_rows),
    ]
    for tab, header, rows in jobs:
        if not rows:
            log.info("%s — 적재할 행 없음", tab)
            continue
        sheet.ensure_tab(tab, header)
        upd, new = sheet.upsert(tab, header, rows, key_col_index=0)
        log.info("%s 적재 — 갱신 %d, 신규 %d", tab, upd, new)
    log.info("백필 완료")


if __name__ == "__main__":
    main()
