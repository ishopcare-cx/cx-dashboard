"""콜라비 전화 통계 수집 → 'CX 대시보드 데이터' 시트의 call_daily /
call_team_daily 탭 적재.

매일 1회 GitHub Actions로 실행. 두 페이지를 차례로 스크랩:
 1) CTI > 상담원별통계 > 일별 통계  (오늘분만 표시 — 매일 누적)
 2) IPPBX > 수신통계 > 일별 분류    (당월 전체 표시 — 매일 upsert)

키: call_daily = '일자_상담원ID', call_team_daily = '일자'.
"""
import datetime
import json
import logging
import os
import sys
from pathlib import Path

import config
from colabee import Colabee
from google_credentials import build_credentials
from sheets import Sheet
from transform import KST
from transform_call import (
    CALL_DAILY_HEADER, CALL_TEAM_DAILY_HEADER, CALL_VOC_DAILY_HEADER,
    agent_row, call_voc_row, team_row,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
log = logging.getLogger(__name__)


def _credentials():
    """콜라비 자격증명 — 환경변수 우선, 없으면 colabee_local.json."""
    cfg = {
        "username": os.environ.get("COLABEE_USERNAME"),
        "password": os.environ.get("COLABEE_PASSWORD"),
        "base_url": os.environ.get(
            "COLABEE_BASE_URL", "https://callrabi.ishopcare.co.kr:8070"),
    }
    if not (cfg["username"] and cfg["password"]):
        f = Path(__file__).parent / "colabee_local.json"
        if f.exists():
            d = json.loads(f.read_text(encoding="utf-8"))
            cfg["username"] = cfg["username"] or d.get("username")
            cfg["password"] = cfg["password"] or d.get("password")
            cfg["base_url"] = d.get("base_url", cfg["base_url"])
    if not (cfg["username"] and cfg["password"]):
        raise SystemExit(
            "콜라비 자격증명 미설정 — COLABEE_USERNAME/PASSWORD 환경변수 "
            "또는 colabee_local.json 필요.")
    return cfg


def main():
    cfg = _credentials()
    log.info("콜라비 전화 통계 수집 시작")

    # 1) 스크랩
    now = datetime.datetime.now(KST)
    yesterday = (now.date() - datetime.timedelta(days=1)).isoformat()
    today = now.date().isoformat()
    with Colabee(cfg["base_url"], cfg["username"], cfg["password"]) as cb:
        log.info("▶ 상담원별 일별 통계 페이지")
        agent_table = cb.fetch_agent_daily()
        log.info("  표 %d행 수신", len(agent_table))
        log.info("▶ 수신통계 일별 분류 페이지")
        team_table = cb.fetch_recv_daily()
        log.info("  표 %d행 수신", len(team_table))
        # 콜 VOC — 어제(확정) + 오늘(누적 스냅샷) 두 번 fetch.
        # COUNSEL_STAT 표에 일자 컬럼이 없어 단일 날짜씩 호출.
        log.info("▶ 상담통계(콜 VOC) 페이지 — %s", yesterday)
        voc_y = cb.fetch_counsel_stat(yesterday)
        log.info("  표 %d행 수신", len(voc_y))
        log.info("▶ 상담통계(콜 VOC) 페이지 — %s", today)
        voc_t = cb.fetch_counsel_stat(today)
        log.info("  표 %d행 수신", len(voc_t))

    # 2) 변환
    year_month = now.strftime("%Y-%m")
    agent_rows = [r for r in (agent_row(row, now) for row in agent_table)
                  if r is not None]
    team_rows = [r for r in (team_row(row, year_month, now) for row in team_table)
                 if r is not None]
    voc_rows = (
        [r for r in (call_voc_row(row, yesterday, now) for row in voc_y) if r] +
        [r for r in (call_voc_row(row, today, now) for row in voc_t) if r]
    )
    log.info("변환: agent %d행 / team %d행 / voc %d행 (어제+오늘)",
             len(agent_rows), len(team_rows), len(voc_rows))

    # 3) 적재
    sheet = Sheet(build_credentials(), config.SHEET_ID)
    sheet.ensure_tab("call_daily", CALL_DAILY_HEADER)
    a_upd, a_new = sheet.upsert("call_daily", CALL_DAILY_HEADER, agent_rows,
                                key_col_index=0)
    log.info("call_daily 적재 — 갱신 %d, 신규 %d", a_upd, a_new)

    sheet.ensure_tab("call_team_daily", CALL_TEAM_DAILY_HEADER)
    t_upd, t_new = sheet.upsert("call_team_daily", CALL_TEAM_DAILY_HEADER,
                                team_rows, key_col_index=0)
    log.info("call_team_daily 적재 — 갱신 %d, 신규 %d", t_upd, t_new)

    sheet.ensure_tab("call_voc_daily", CALL_VOC_DAILY_HEADER)
    v_upd, v_new = sheet.upsert("call_voc_daily", CALL_VOC_DAILY_HEADER,
                                voc_rows, key_col_index=0)
    log.info("call_voc_daily 적재 — 갱신 %d, 신규 %d", v_upd, v_new)


if __name__ == "__main__":
    main()
