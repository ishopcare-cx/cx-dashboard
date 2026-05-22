"""채널톡 Open API v5 클라이언트 — 인증·페이지네이션·재시도."""
import logging
import time

import requests

import config

log = logging.getLogger(__name__)


class ChannelTalk:
    """x-access-key / x-access-secret 헤더 인증. GET 전용(읽기)."""

    def __init__(self, access_key, access_secret):
        self._s = requests.Session()
        self._s.headers.update({
            "x-access-key": access_key,
            "x-access-secret": access_secret,
        })

    def _get(self, path, params=None):
        """GET 호출 + 429(rate limit) 지수 백오프 재시도."""
        url = config.CHANNELTALK_BASE + path
        last = None
        for attempt in range(5):
            r = self._s.get(url, params=params, timeout=30)
            last = r
            if r.status_code == 429:
                wait = 2 ** attempt
                log.warning("429 rate limit — %d초 대기 후 재시도", wait)
                time.sleep(wait)
                continue
            r.raise_for_status()
            return r.json()
        last.raise_for_status()

    def managers(self):
        """{managerId: name} 전체 매니저 맵."""
        out = {}
        since = None
        while True:
            params = {"limit": 100}
            if since:
                params["since"] = since
            d = self._get("/managers", params)
            for m in d.get("managers", []):
                out[m["id"]] = m.get("name", "")
            since = d.get("next")
            if not since:
                break
        return out

    def iter_user_chat_pages(self, state):
        """주어진 state의 user-chat을 페이지(리스트) 단위로 최신순 yield.

        API가 limit보다 적게 쪼개 주므로 next 커서로 끝까지 따라간다.
        호출측이 중간에 break하면 더 이상 페이지를 요청하지 않는다.

        주의: 페이지 내부 정렬은 closedAt 기준이지만 완벽히 단조롭지 않다
        (수 시간 범위로 흔들림). 종료 판정은 개별 채팅이 아니라 페이지
        단위로 해야 한다 — collect_chat.collect() 참고.
        """
        since = None
        while True:
            params = {"state": state, "limit": 500, "sortOrder": "desc"}
            if since:
                params["since"] = since
            d = self._get("/user-chats", params)
            chats = d.get("userChats", [])
            yield chats
            since = d.get("next")
            if not since or not chats:
                break

    def iter_user_chats(self, state):
        """주어진 state의 user-chat을 모두 yield (페이지 평탄화)."""
        for page in self.iter_user_chat_pages(state):
            for c in page:
                yield c
