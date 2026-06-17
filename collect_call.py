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

# 매 수집마다 오늘 포함 최근 (BACKFILL_DAYS+1)일을 재수집 → 주말·연휴·실패 갭 보강.
# 평일 수집이라 보통 토·일 2일 갭 → 3이면 3일 연휴(화요일 첫 수집)까지 커버.
BACKFILL_DAYS = 4
# 월초 이 기간(일)엔 수신통계 전월분도 함께 수집 → 월말 주말 영구누락 방지.
MONTH_OVERLAP_DAYS = 4


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


def _window_dates(now):
    """오늘 포함 최근 BACKFILL_DAYS+1일(과거→오늘 순) ISO 리스트.

    수집이 평일만 돌아 주말·연휴·실패분이 빠지므로, 매 수집마다 최근 며칠을
    재수집해 메운다. upsert(키 기준)라 재수집은 무해.
    """
    return [(now.date() - datetime.timedelta(days=i)).isoformat()
            for i in range(BACKFILL_DAYS, -1, -1)]


def _target_months(now):
    """수집할 (year, month) 목록 — 당월 + (월초면) 전월.

    수신통계가 '한 달치'만 줘서, 월말 데이터는 그 달 안에 못 잡으면 영구
    누락된다(월 바뀌면 전월 표를 다시 못 봄). 월초 MONTH_OVERLAP_DAYS일간은
    전월도 함께 긁어 월말 주말 누락을 막는다.
    """
    months = [(now.year, now.month)]
    if now.day <= MONTH_OVERLAP_DAYS:
        prev_last = now.replace(day=1) - datetime.timedelta(days=1)
        months.insert(0, (prev_last.year, prev_last.month))
    return months


def main():
    cfg = _credentials()
    log.info("콜라비 전화 통계 수집 시작")

    # 1) 스크랩 — 팀은 월 단위, 나머지는 최근 며칠 윈도우
    now = datetime.datetime.now(KST)
    dates = _window_dates(now)
    months = _target_months(now)
    log.info("대상 날짜=%s / 월=%s", dates,
             ["%04d-%02d" % m for m in months])

    team_table_by_month = {}
    agent_tables, voc_tables, state_tables = {}, {}, {}
    with Colabee(cfg["base_url"], cfg["username"], cfg["password"]) as cb:
        # 팀(수신통계) — 당월 + (월초면) 전월
        for (y, m) in months:
            ym = "%04d-%02d" % (y, m)
            cur = (y == now.year and m == now.month)
            log.info("▶ 수신통계 일별 분류 — %s%s", ym, "" if cur else " (전월 보강)")
            tbl = cb.fetch_recv_daily() if cur else cb.fetch_recv_daily(y, m)
            log.info("  표 %d행 수신", len(tbl))
            team_table_by_month[ym] = tbl

        # 상담원별·콜 VOC·후처리 — 날짜별(과거→오늘). 후처리는 실패해도 진행.
        for d in dates:
            log.info("▶ 상담원별 일별 통계 — %s", d)
            agent_tables[d] = cb.fetch_agent_daily(d)
            log.info("  표 %d행 수신", len(agent_tables[d]))
            log.info("▶ 상담통계(콜 VOC) — %s", d)
            voc_tables[d] = cb.fetch_counsel_stat(d)
            log.info("  표 %d행 수신", len(voc_tables[d]))
            try:
                log.info("▶ 상담원 상태 통계(후처리) — %s", d)
                state_tables[d] = cb.fetch_agent_state_stat(d)
                log.info("  표 %d행 수신", len(state_tables[d]))
            except Exception as e:
                log.warning("AGENT_STATE_STAT 수집 실패 — %s (%s)", d, e)
                state_tables[d] = []

    # 2) 변환 — 표의 첫 컬럼 일자가 대상일과 맞는 행만(엉뚱한 날짜 혼입 방지)
    agent_rows, time_rows, voc_rows, acw_rows, team_rows = [], [], [], [], []
    for ym, tbl in team_table_by_month.items():
        team_rows += [r for r in (team_row(row, ym, now) for row in tbl)
                      if r is not None]
    for d in dates:
        agent_rows += [r for r in (agent_row(row, now) for row in agent_tables[d])
                       if r is not None and r[2] == d]
        time_rows += [r for r in (callraw_time_row(row, now)
                                  for row in agent_tables[d])
                      if r is not None and r[2] == d]
        voc_rows += [r for r in (call_voc_row(row, d, now)
                                 for row in voc_tables[d]) if r]
        acw_rows += [r for r in (agent_state_row(row, d, now)
                                 for row in state_tables[d]) if r]
    log.info("변환: agent %d행 / team %d행 / voc %d행 / callraw_time %d / acw %d",
             len(agent_rows), len(team_rows), len(voc_rows),
             len(time_rows), len(acw_rows))

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

    # raw 탭 적재 — CX 퍼포먼스 시트 연동(sync_perf_sheet)이 읽어감
    if time_rows:
        sheet.ensure_tab("callraw_time", CALLRAW_TIME_HEADER)
        ct_upd, ct_new = sheet.upsert("callraw_time", CALLRAW_TIME_HEADER,
                                      time_rows, key_col_index=0)
        log.info("callraw_time 적재 — 갱신 %d, 신규 %d", ct_upd, ct_new)
    if acw_rows:
        sheet.ensure_tab("callraw_acw", CALLRAW_ACW_HEADER)
        ca_upd, ca_new = sheet.upsert("callraw_acw", CALLRAW_ACW_HEADER,
                                      acw_rows, key_col_index=0)
        log.info("callraw_acw 적재 — 갱신 %d, 신규 %d", ca_upd, ca_new)


if __name__ == "__main__":
    main()
