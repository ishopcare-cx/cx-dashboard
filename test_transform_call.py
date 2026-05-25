"""transform_call.py 순수 함수 테스트."""
from transform_call import (
    agent_row, parse_float, parse_hms_to_seconds, parse_int, team_row,
)


def test_parse_hms():
    assert parse_hms_to_seconds("00:01:48") == 108
    assert parse_hms_to_seconds("14:54:35") == 14 * 3600 + 54 * 60 + 35
    assert parse_hms_to_seconds("0") == ""
    assert parse_hms_to_seconds("") == ""
    assert parse_hms_to_seconds(None) == ""
    assert parse_hms_to_seconds("garbage") == ""


def test_parse_int():
    assert parse_int("1,608") == 1608
    assert parse_int("436") == 436
    assert parse_int("") == 0
    assert parse_int(None) == 0
    assert parse_int("abc") == 0


def test_parse_float():
    assert parse_float("94.3") == 94.3
    assert parse_float("94.3%") == 94.3
    assert parse_float("100") == 100.0
    assert parse_float("") == ""
    assert parse_float("abc") == ""


def test_agent_row_normal():
    row = ['2026-05-25', '3008', '박현주', '6', '00:01:58', '00:11:48',
           '0', '00:00:00', '00:00:00', '0', '0',
           '00:00:00', '00:00:00', '0', '00:00:00', '00:00:00']
    out = agent_row(row)
    assert out is not None
    assert out[0] == '2026-05-25_3008'         # 키
    assert out[2] == '2026-05-25'              # 일자
    assert out[3] == '3008'                    # 상담원ID
    assert out[4] == '박현주'                  # 상담원
    assert out[5] == 'CX 2'                    # 스쿼드
    assert out[6] == 6                         # 수신연결
    assert out[7] == 118                       # 평균 1:58 = 118s
    assert out[8] == 708                       # 총 11:48 = 708s


def test_agent_row_skip_sub_total():
    """소계·합계 행은 일자 칸이 '소계'/'합계' — None 반환."""
    assert agent_row(['소계', '11', '00:02:47', '00:30:44', '0',
                     '00:00:00', '00:00:00', '1', '0', '00:00:00',
                     '00:00:00']) is None
    assert agent_row(['합계', '11', '00:02:47', '00:30:44', '0',
                     '00:00:00', '00:00:00', '1', '0', '00:00:00',
                     '00:00:00']) is None


def test_agent_row_skip_short():
    assert agent_row([]) is None
    assert agent_row(['hi']) is None


def test_team_row_normal():
    row = ['1 일', '436', '7', '75', '0', '39', '23',
           '299', '282', '8', '9',
           '94.3', '3', '28.2', '00:03:10', '14:54:35', '0']
    out = team_row(row, '2026-05')
    assert out is not None
    assert out[0] == '2026-05-01'              # 키
    assert out[2] == '2026-05-01'              # 일자
    assert out[3] == 436                       # 총인입
    assert out[9] == 299                       # 연결시도
    assert out[10] == 282                      # 연결성공
    assert out[11] == 8                        # 연결포기
    assert out[13] == 94.3                     # 성공률%
    assert out[14] == 3.0                      # 실패율%
    assert out[15] == 28.2                     # 평균대기(초)
    assert out[16] == 3 * 60 + 10              # 평균통화 = 3:10 = 190s
    assert out[17] == 14 * 3600 + 54 * 60 + 35 # 총통화


def test_team_row_skip():
    assert team_row([], '2026-05') is None
    assert team_row(['소계'], '2026-05') is None
    # 헤더 행 ('분류'로 시작)
    assert team_row(['분류', '총인입'] + ['x'] * 15, '2026-05') is None


if __name__ == "__main__":
    passed = 0
    for _name, _fn in sorted(globals().items()):
        if _name.startswith("test_") and callable(_fn):
            _fn()
            print("PASS", _name)
            passed += 1
    print(f"\n전체 {passed}개 테스트 통과")
