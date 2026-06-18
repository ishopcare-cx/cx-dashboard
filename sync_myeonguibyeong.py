"""#명의변경 슬랙 채널 → 구글시트 자동 기재.

최근 2시간 메시지에서 사업자번호 추출 → G열 매칭 → L·M=완료, O=CX 기재.
O열이 이미 CX인 행은 중복 처리 방지를 위해 건너뜀.
"""
import os
import re
import sys
from datetime import datetime, timezone, timedelta

import requests
from google.auth.transport.requests import Request as GoogleRequest
from googleapiclient.discovery import build

SLACK_CHANNEL_ID = "C07CL4BV9QT"   # #명의변경
SPREADSHEET_ID   = "1k0sqGOSa9CQ1alHG2rMrZHEtx10SWHnp3nz-sJAFhLI"
SHEET_NAME       = "명의변경"
LOOKAHEAD_HOURS  = 2


# ── Slack ─────────────────────────────────────────────────────────────────────

def get_slack_messages():
    token  = os.environ["SLACK_BOT_TOKEN"]
    oldest = (datetime.now(timezone.utc) - timedelta(hours=LOOKAHEAD_HOURS)).timestamp()
    messages, cursor = [], None
    while True:
        params = {"channel": SLACK_CHANNEL_ID, "oldest": oldest, "limit": 200}
        if cursor:
            params["cursor"] = cursor
        r = requests.get(
            "https://slack.com/api/conversations.history",
            headers={"Authorization": f"Bearer {token}"},
            params=params, timeout=15,
        )
        data = r.json()
        if not data.get("ok"):
            raise RuntimeError(f"Slack API 오류: {data.get('error')}")
        messages.extend(data.get("messages", []))
        cursor = data.get("response_metadata", {}).get("next_cursor")
        if not cursor:
            break
    return messages


def extract_bizno(text):
    """메시지에서 사업자번호(10자리) 추출."""
    m = re.search(r"사업자번호[:\s]+(\d{3}-?\d{2}-?\d{5})", text)
    if m:
        return m.group(1).replace("-", "")
    return None


# ── Google Sheets ─────────────────────────────────────────────────────────────

def get_credentials():
    from google_credentials import build_credentials
    creds = build_credentials()
    GoogleRequest()(creds)
    return creds


def get_sheet_rows(creds):
    svc = build("sheets", "v4", credentials=creds, cache_discovery=False)
    result = svc.spreadsheets().values().get(
        spreadsheetId=SPREADSHEET_ID,
        range=f"{SHEET_NAME}!A:P",
    ).execute()
    return result.get("values", [])


def update_row(row_1idx, creds):
    """L·M = 완료, O = CX 기재."""
    svc = build("sheets", "v4", credentials=creds, cache_discovery=False)
    svc.spreadsheets().values().batchUpdate(
        spreadsheetId=SPREADSHEET_ID,
        body={
            "valueInputOption": "USER_ENTERED",
            "data": [
                {"range": f"{SHEET_NAME}!L{row_1idx}:M{row_1idx}", "values": [["완료", "완료"]]},
                {"range": f"{SHEET_NAME}!O{row_1idx}",             "values": [["CX"]]},
            ],
        },
    ).execute()


# ── 메인 ─────────────────────────────────────────────────────────────────────

def main():
    # 1. 슬랙 메시지 읽기
    try:
        messages = get_slack_messages()
    except Exception as e:
        print(f"[오류] Slack 읽기 실패: {e}", file=sys.stderr)
        sys.exit(1)

    # 2. 사업자번호 추출
    biznos = set()
    for msg in messages:
        bno = extract_bizno(msg.get("text", ""))
        if bno:
            biznos.add(bno)

    if not biznos:
        print("처리할 명의변경 메시지 없음")
        return

    print(f"사업자번호 {len(biznos)}개 감지: {', '.join(sorted(biznos))}")

    # 3. 시트 읽기
    try:
        creds = get_credentials()
        rows  = get_sheet_rows(creds)
    except Exception as e:
        print(f"[오류] 시트 읽기 실패: {e}", file=sys.stderr)
        sys.exit(1)

    # 4. 매칭 행 업데이트 (헤더 1행 제외)
    updated = skipped = 0
    for i, row in enumerate(rows[1:], start=2):   # 1-indexed, header=row1
        g_val = (row[6].strip() if len(row) > 6 else "").replace("-", "")
        if g_val not in biznos:
            continue

        o_val = row[14].strip() if len(row) > 14 else ""
        if o_val == "CX":
            skipped += 1
            print(f"  행 {i} ({g_val}): 이미 처리됨")
            continue

        try:
            update_row(i, creds)
            updated += 1
            print(f"  행 {i} ({g_val}): L·M=완료, O=CX 기재 완료")
        except Exception as e:
            print(f"  행 {i} ({g_val}): 업데이트 실패 — {e}", file=sys.stderr)

    print(f"\n결과: {updated}행 업데이트, {skipped}행 중복 스킵")
    if updated == 0 and skipped == 0:
        print("(매칭 행 없음 — 사업자번호가 G열에 없거나 아직 시트에 미등록)")


if __name__ == "__main__":
    main()
