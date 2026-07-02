"""순수 변환 로직 — 태그 분류·시각 변환·채팅→행. API/시트 I/O 없음."""
import datetime
import re

import config

KST = datetime.timezone(datetime.timedelta(hours=9))

# 날짜+이름 태그: 4자리 숫자(MMDD)가 앞 또는 뒤에 붙고 '/'가 없는 태그.
_DATE_TAG = re.compile(r"^\d{4}.+$|^.+\d{4}$")

# 이름 → 스쿼드 역인덱스
_SQUAD_BY_NAME = {
    name: squad
    for squad, names in config.SQUADS.items()
    for name in names
}


def squad_of(manager_name) -> str:
    """담당자 이름 → 스쿼드. 미배정/리더/제외 대상은 '기타'."""
    return _SQUAD_BY_NAME.get((manager_name or "").strip(), "기타")


def classify_tags(tags):
    """태그 목록 → (VOC, 상담사, 기타) 세 리스트.

    - VOC   : '/' 포함 (대분류/소분류)
    - 상담사 : 날짜+이름 형태(예: 0522지은, 소현0522, ~2026-06-28) 또는
               이름만(예: 노지은, 백합 — 2026-06-29부터 새 형식)
    - 기타   : 그 외
    """
    voc, agent, etc = [], [], []
    for t in tags or []:
        t = (t or "").strip()
        if not t:
            continue
        if "/" in t:
            voc.append(t)
        elif _DATE_TAG.match(t) or t in config.ALL_AGENT_NAMES:
            agent.append(t)
        else:
            etc.append(t)
    return voc, agent, etc


def _ms_to_kst(ms):
    """epoch 밀리초 → KST datetime. None/0이면 None."""
    if not ms:
        return None
    return datetime.datetime.fromtimestamp(ms / 1000, KST)


def _dt_str(dt) -> str:
    return dt.strftime("%Y-%m-%d %H:%M:%S") if dt else ""


def _date_str(dt) -> str:
    return dt.strftime("%Y-%m-%d") if dt else ""


def _secs(ms):
    """소요시간 epoch 밀리초 → 초(반올림 정수). None/0이면 ''."""
    if not ms:
        return ""
    return round(ms / 1000)


def _first_response_secs(chat):
    """첫응대시간 = 배정(firstOpenedAt) → 첫응답(firstRepliedAtAfterOpen).

    큐 대기시간을 뺀, 담당자가 채팅을 받은 뒤 실제로 응답하기까지의
    시간. 둘 중 하나라도 없으면(미배정/미응대) ''.
    """
    opened = chat.get("firstOpenedAt")
    replied = chat.get("firstRepliedAtAfterOpen")
    if not opened or not replied:
        return ""
    return _secs(replied - opened)


def chat_to_row(chat, manager_names, collected_at=None):
    """user-chat 객체 → chat_raw 행(리스트). config.CHAT_HEADER 순서.

    manager_names: {managerId: name}
    첫응대시간_초는 배정(firstOpenedAt)~첫응답(firstRepliedAtAfterOpen) 기준
    (_first_response_secs 참고). 평균응답시간·처리시간은 'operation~'
    (미운영시간 제외) 필드를 쓴다 — 채널톡 상담별 통계 화면과 같은 기준.
    """
    collected_at = collected_at or datetime.datetime.now(KST)
    created = _ms_to_kst(chat.get("createdAt"))
    closed = _ms_to_kst(chat.get("closedAt"))
    first_replied = _ms_to_kst(chat.get("firstRepliedAt"))
    first_opened = _ms_to_kst(chat.get("firstOpenedAt"))
    assignee = manager_names.get(chat.get("assigneeId"), "")
    voc, agent, etc = classify_tags(chat.get("tags"))
    reply_count = chat.get("replyCount")
    return [
        _dt_str(collected_at),
        chat.get("id", ""),
        _date_str(created),
        _dt_str(created),
        _date_str(closed),
        chat.get("state", ""),
        assignee,
        squad_of(assignee),
        _dt_str(first_replied),
        _first_response_secs(chat),
        _secs(chat.get("operationAvgReplyTime")),
        _secs(chat.get("operationResolutionTime")),
        reply_count if reply_count is not None else "",
        "; ".join(voc),
        "; ".join(agent),
        "; ".join(etc),
        _dt_str(first_opened),
    ]
