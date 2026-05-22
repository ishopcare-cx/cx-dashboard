"""채널톡 채팅 수집 → 'CX 대시보드 데이터' 시트 chat_raw 탭 적재.

매일 1회 GitHub Actions로 실행. opened/snoozed/queued 상태는 전량,
closed는 최근 config.COLLECT_DAYS일분을 재수집해 채팅ID 기준 upsert한다
(채팅의 상태 변화·시간 지표 갱신을 반영).
"""
import datetime
import json
import logging
import os
import sys
from pathlib import Path

import config
from channeltalk import ChannelTalk
from google_credentials import build_credentials
from sheets import Sheet
from transform import KST, chat_to_row

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
log = logging.getLogger(__name__)


def _channeltalk_keys():
    """채널톡 키 — 환경변수 우선, 없으면 로컬 secrets_local.json."""
    key = os.environ.get("CHANNELTALK_ACCESS_KEY")
    secret = os.environ.get("CHANNELTALK_ACCESS_SECRET")
    if not (key and secret):
        f = Path(__file__).parent / "secrets_local.json"
        if f.exists():
            d = json.loads(f.read_text(encoding="utf-8"))
            key = key or d.get("CHANNELTALK_ACCESS_KEY")
            secret = secret or d.get("CHANNELTALK_ACCESS_SECRET")
    if not (key and secret):
        raise SystemExit(
            "채널톡 키 미설정 — CHANNELTALK_ACCESS_KEY/SECRET 환경변수 또는 "
            "secrets_local.json 필요.")
    return key, secret


def collect(ct):
    """수집 대상 user-chat 목록 반환 (채팅ID 중복 제거)."""
    cutoff = datetime.datetime.now(KST) - datetime.timedelta(
        days=config.COLLECT_DAYS)
    cutoff_ms = int(cutoff.timestamp() * 1000)

    by_id = {}
    # opened/snoozed/queued — 전량 (건수 적음)
    for state in ("opened", "snoozed", "queued"):
        n = 0
        for c in ct.iter_user_chats(state):
            by_id[c["id"]] = c
            n += 1
        log.info("%s: %d건", state, n)
    # closed — closedAt이 cutoff 이상인 채팅. 페이지 단위로 끊는다.
    # 개별 채팅에서 break하면 정렬 흔들림(오래된 채팅 1건이 중간에 끼는
    # 경우)에 일찍 끊긴다 → 페이지 전체의 최신값이 cutoff보다 과거일 때만
    # 중단한다.
    n = pages = 0
    for page in ct.iter_user_chat_pages("closed"):
        if not page:
            break
        pages += 1
        page_max = 0
        for c in page:
            ts = c.get("closedAt") or c.get("createdAt") or 0
            page_max = max(page_max, ts)
            if ts >= cutoff_ms:
                by_id[c["id"]] = c
                n += 1
        if page_max < cutoff_ms:
            break
    log.info("closed(최근 %d일): %d건 / %d페이지",
             config.COLLECT_DAYS, n, pages)
    return list(by_id.values())


def main():
    key, secret = _channeltalk_keys()
    log.info("채널톡 채팅 수집 시작 (창=%d일)", config.COLLECT_DAYS)

    ct = ChannelTalk(key, secret)
    managers = ct.managers()
    log.info("매니저 %d명 로드", len(managers))

    chats = collect(ct)
    rows = [chat_to_row(c, managers) for c in chats]
    log.info("수집 %d건 → 행 변환 완료", len(rows))

    sheet = Sheet(build_credentials(), config.SHEET_ID)
    sheet.ensure_tab(config.CHAT_TAB, config.CHAT_HEADER)
    updated, appended = sheet.upsert(
        config.CHAT_TAB, config.CHAT_HEADER, rows,
        key_col_index=config.CHAT_HEADER.index("채팅ID"))
    log.info("적재 완료 — 갱신 %d행, 신규 %d행", updated, appended)


if __name__ == "__main__":
    main()
