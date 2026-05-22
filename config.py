"""중앙 설정 — 비밀값은 두지 않는다(환경변수 / google_credentials 사용)."""
import os
from pathlib import Path

BASE_DIR = Path(__file__).parent

# 데이터 창고 스프레드시트 "CX 대시보드 데이터"
SHEET_ID = "1VR0ZjB4S6Qaloqv0Aeeo__SST4Q_xHznKDTPtdCIEsE"
CHAT_TAB = "chat_raw"

# chat_raw 헤더 — 순서 = 시트 컬럼 순서(A열부터)
CHAT_HEADER = [
    "수집일시", "채팅ID", "생성일", "생성일시", "종료일", "상태",
    "담당자", "스쿼드", "첫응대시각", "첫응대시간_초", "평균응답시간_초",
    "처리시간_초", "응답수", "VOC태그", "상담사태그", "기타태그",
]

# 채널톡 Open API v5
CHANNELTALK_BASE = "https://api.channel.io/open/v5"

# 스쿼드 — 상담사(채널톡 매니저 이름) → 스쿼드. 어디에도 없으면 "기타".
SQUADS = {
    "CX 1": ["김슬기", "남궁선", "박우진", "박진호", "백합",
             "이예원", "최치원", "홍승기"],
    "CX 2": ["김소현", "노지은", "박현주", "양혜수", "이광두",
             "이태협", "장승환", "지주영", "홍지혜"],
    "교육": ["유영지"],
}

# 증분 수집 창 — closed 채팅은 최근 N일분만 재수집(상태변화·통계 갱신 반영).
# opened/snoozed/queued는 건수가 적어 매번 전량 수집한다.
COLLECT_DAYS = int(os.environ.get("CX_COLLECT_DAYS", "10"))
