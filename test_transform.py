"""transform.py 순수 함수 테스트. pytest 없이도 직접 실행 가능.

    python test_transform.py
"""
from transform import chat_to_row, classify_tags, squad_of


def test_classify_voc_only():
    voc, agent, etc = classify_tags(["주문/청약", "CMS/폐업"])
    assert voc == ["주문/청약", "CMS/폐업"]
    assert agent == []
    assert etc == []


def test_classify_agent_tag_both_orders():
    voc, agent, etc = classify_tags(["0522지은", "소현0522"])
    assert agent == ["0522지은", "소현0522"]
    assert voc == []
    assert etc == []


def test_classify_agent_name_only_tag():
    """2026-06-29부터 상담사태그가 이름만(날짜 없이) 붙는다."""
    voc, agent, etc = classify_tags(["노지은", "백합", "모르는사람"])
    assert agent == ["노지은", "백합"]
    assert etc == ["모르는사람"]
    assert voc == []


def test_classify_mixed_and_blanks():
    voc, agent, etc = classify_tags(
        ["주문/배송", "0521태협", "종료X", "", None])
    assert voc == ["주문/배송"]
    assert agent == ["0521태협"]
    assert etc == ["종료X"]


def test_classify_empty():
    assert classify_tags(None) == ([], [], [])
    assert classify_tags([]) == ([], [], [])


def test_squad_of():
    assert squad_of("노지은") == "CX 2"
    assert squad_of("홍승기") == "CX 1"
    assert squad_of("유영지") == "교육"
    assert squad_of("김유나") == "기타"      # 리더 — 스쿼드 미포함
    assert squad_of("없는사람") == "기타"
    assert squad_of(None) == "기타"


def test_chat_to_row():
    chat = {
        "id": "abc123",
        "state": "closed",
        "createdAt": 1779435144679,
        "closedAt": 1779445981178,
        "firstRepliedAt": 1779445842752,
        "firstOpenedAt": 1779435144679,
        "firstRepliedAtAfterOpen": 1779445731134,
        "assigneeId": "M1",
        "tags": ["주문/청약", "0522지은"],
        "operationWaitingTime": 10586455,
        "operationAvgReplyTime": 3535358,
        "operationResolutionTime": 5406046,
        "replyCount": 3,
    }
    # 헤더: 수집일시,채팅ID,생성일,생성일시,종료일,상태,담당자,스쿼드,
    #       첫응대시각,첫응대시간_초,평균응답시간_초,처리시간_초,응답수,
    #       VOC태그,상담사태그,기타태그,배정일시,배정응답시간_초
    row = chat_to_row(chat, {"M1": "노지은"})
    assert len(row) == 18
    assert row[1] == "abc123"
    assert row[5] == "closed"
    assert row[6] == "노지은"
    assert row[7] == "CX 2"
    assert row[9] == 10586          # 첫응대시간_초(팀) = operationWaitingTime(문의→첫응답)
    assert row[12] == 3
    assert row[13] == "주문/청약"
    assert row[14] == "0522지은"
    assert row[15] == ""
    assert row[16] != ""            # 배정일시 채워짐
    assert row[17] == 10586         # 배정응답시간_초(개인) = firstRepliedAtAfterOpen-firstOpenedAt


def test_chat_to_row_missing_fields():
    """미응대(시간 필드 없음) 채팅도 깨지지 않는다."""
    row = chat_to_row({"id": "x", "state": "opened"}, {})
    assert row[1] == "x"
    assert row[6] == ""             # 담당자 없음
    assert row[7] == "기타"
    assert row[9] == ""             # 첫응대시간 없음(미응대)
    assert row[12] == ""            # 응답수 없음
    assert row[16] == ""            # 배정일시 없음
    assert row[17] == ""            # 배정응답시간 없음


if __name__ == "__main__":
    passed = 0
    for _name, _fn in sorted(globals().items()):
        if _name.startswith("test_") and callable(_fn):
            _fn()
            print("PASS", _name)
            passed += 1
    print(f"\n전체 {passed}개 테스트 통과")
