"""구글시트(오처리·누락 접수 양식) → 노션 DB 증분 동기화."""
import json
import os
import re
import sys
from datetime import datetime, timezone, timedelta

import requests
from google.auth.transport.requests import Request as GoogleRequest
from googleapiclient.discovery import build

SPREADSHEET_ID = "1LbHX6MHIALyzfUzccArTOg6vnHhcKCbztJHEnF2Ji2o"
SHEET_TAB = "접수"
NOTION_DB_ID = "3702a7ea-0c88-804e-99fc-000be38cc487"
STATE_PAGE_ID = "3732a7ea-0c88-8155-8c59-eb904b67b3ad"
OWNER_SLACK_ID = "D07DLTY3UAF"  # 노지은

KST = timezone(timedelta(hours=9))

VALID_ITEMS = {
    "검수 오처리", "청약 지연", "개시 누락", "TID 누락",
    "휴대용-일비 발송누락", "다운로드 누락(명변제신고)",
    "오출금/환불 누락", "토페해지 오안내", "워크플로 오생성",
    "오출고", "VAN등록 누락",
}
VALID_DEPTS = {"토스CX", "MD", "효성", "CO 청약", "CO운영관리", "CMS", "⚠️확인필요"}
VALID_PERSONS = {
    "이비헌", "박세윤", "원수연", "이시우", "권지연", "문지수", "박정민",
    "양나경", "최유정", "최보원", "이서은", "한백천", "장여원", "태강희",
    "장종원", "정경희", "조현빈", "탁형진", "나혜은",
}


# ── Notion ──────────────────────────────────────────────────────────────────

def _notion_headers():
    return {
        "Authorization": f"Bearer {os.environ['NOTION_TOKEN']}",
        "Notion-Version": "2022-06-28",
        "Content-Type": "application/json",
    }


def get_state():
    """상태 페이지에서 processed_count와 code block id 반환."""
    r = requests.get(
        f"https://api.notion.com/v1/blocks/{STATE_PAGE_ID}/children",
        headers=_notion_headers(), timeout=15,
    )
    r.raise_for_status()
    for block in r.json().get("results", []):
        if block.get("type") == "code":
            raw = block["code"]["rich_text"][0]["plain_text"]
            data = json.loads(raw)
            return data.get("processed_count", 0), block["id"]
    raise RuntimeError("상태 페이지에서 code block(processed_count) 미발견")


def set_state(block_id, count):
    kst_now = datetime.now(KST).strftime("%Y-%m-%dT%H:%M:%S+09:00")
    payload = json.dumps({"processed_count": count, "updated_at": kst_now}, ensure_ascii=False)
    r = requests.patch(
        f"https://api.notion.com/v1/blocks/{block_id}",
        headers=_notion_headers(),
        json={"code": {"rich_text": [{"type": "text", "text": {"content": payload}}]}},
        timeout=15,
    )
    r.raise_for_status()


def create_notion_page(row):
    """행 1개를 노션 DB에 생성. (needs_check, submitter_id) 반환."""
    while len(row) < 8:
        row.append("")

    date_str = (row[0] or "")[:10]
    title    = row[1] or ""
    items_raw   = _split(row[2])
    depts_raw   = _split(row[3])
    persons_raw = _split(row[4])
    note         = row[5] or ""
    submitter_id = row[7] or ""

    items = [v.replace("·", "/") for v in items_raw]

    invalid = (
        [v for v in items    if v not in VALID_ITEMS] +
        [v for v in depts_raw   if v not in VALID_DEPTS] +
        [v for v in persons_raw if v not in VALID_PERSONS]
    )
    needs_check = bool(invalid)
    if needs_check:
        if "⚠️확인필요" not in depts_raw:
            depts_raw.append("⚠️확인필요")
        note = (note + f"\n[자동: 매칭불가 값 = {', '.join(invalid)}]").strip()

    props = {
        "이름":   {"title": [{"text": {"content": title}}]},
        "항목":   {"multi_select": [{"name": v} for v in items      if v in VALID_ITEMS]},
        "담당부서": {"multi_select": [{"name": v} for v in depts_raw   if v in VALID_DEPTS]},
        "담당자": {"multi_select": [{"name": v} for v in persons_raw if v in VALID_PERSONS]},
        "특이사항": {"rich_text": [{"text": {"content": note[:2000]}}]},
    }
    if date_str:
        props["인입 날짜"] = {"date": {"start": date_str}}

    r = requests.post(
        "https://api.notion.com/v1/pages",
        headers=_notion_headers(),
        json={"parent": {"database_id": NOTION_DB_ID}, "properties": props},
        timeout=15,
    )
    r.raise_for_status()
    return needs_check, submitter_id


# ── Google Sheets ────────────────────────────────────────────────────────────

def get_sheet_rows():
    """헤더를 제외한 데이터 행 목록 반환."""
    from google_credentials import build_credentials
    creds = build_credentials()
    GoogleRequest()(creds)  # access token 갱신
    svc = build("sheets", "v4", credentials=creds, cache_discovery=False)
    result = svc.spreadsheets().values().get(
        spreadsheetId=SPREADSHEET_ID,
        range=f"{SHEET_TAB}!A:H",
    ).execute()
    values = result.get("values", [])
    return [r for r in values if r and r[0] not in ("제출일시", "") and r[0].strip()]


# ── Slack ────────────────────────────────────────────────────────────────────

def slack_dm(user_id, text):
    token = os.environ.get("SLACK_BOT_TOKEN", "")
    if not token:
        print(f"[SLACK-DM 스킵] {user_id}: {text}", file=sys.stderr)
        return
    requests.post(
        "https://slack.com/api/chat.postMessage",
        headers={"Authorization": f"Bearer {token}"},
        json={"channel": user_id, "text": text},
        timeout=10,
    )


def _extract_slack_id(raw):
    if not raw:
        return OWNER_SLACK_ID
    m = re.search(r"<@(U[A-Z0-9]+)>", raw)
    if m:
        return m.group(1)
    if re.match(r"U[A-Z0-9]+$", raw.strip()):
        return raw.strip()
    return OWNER_SLACK_ID


def _split(s):
    return [v.strip() for v in re.split(r"[,/]", s or "") if v.strip()]


# ── 메인 ─────────────────────────────────────────────────────────────────────

def main():
    # 1. 상태 읽기
    try:
        processed, state_block_id = get_state()
    except Exception as e:
        slack_dm(OWNER_SLACK_ID, f"[오처리 동기화] 상태 페이지 읽기 실패: {e}")
        sys.exit(1)

    # 2. 시트 읽기
    try:
        rows = get_sheet_rows()
    except Exception as e:
        slack_dm(OWNER_SLACK_ID, f"[오처리 동기화] 구글시트 읽기 실패: {e}")
        sys.exit(1)

    total = len(rows)
    if total <= processed:
        print(f"신규 없음 (total={total}, processed={processed})")
        return

    new_rows = rows[processed:]
    print(f"신규 {len(new_rows)}행 처리 시작 (total={total}, processed={processed})")

    success = 0
    for i, row in enumerate(new_rows):
        title = row[1] if len(row) > 1 else f"행 {processed + i + 1}"
        try:
            needs_check, submitter_id = create_notion_page(row)
            success += 1
            print(f"  [{processed + i + 1}] 완료: {title}")
        except Exception as e:
            slack_id = _extract_slack_id(row[7] if len(row) > 7 else "")
            slack_dm(slack_id,
                f"제출하신 [{title}] 건이 자동 기록에 실패했습니다. 담당자에게 문의해주세요.")
            print(f"  [{processed + i + 1}] 실패: {title} — {e}", file=sys.stderr)

    # 3. 상태 갱신 (성공분만)
    if success > 0:
        set_state(state_block_id, processed + success)

    print(f"완료: {success}/{len(new_rows)}행 처리")
    if success < len(new_rows):
        sys.exit(1)


if __name__ == "__main__":
    main()
