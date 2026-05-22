"""1회용 — 로컬에서 OAuth 동의 흐름을 돌려 refresh token을 발급한다.

[사전 준비]
1. 구글 클라우드 콘솔에서 프로젝트 생성 후 "Google Sheets API" 사용 설정.
2. OAuth 동의화면 구성 — 회사 워크스페이스 계정이면 "내부(Internal)" 권장
   (그래야 refresh token이 만료되지 않음. "테스트" 상태는 7일마다 만료).
3. "OAuth 2.0 클라이언트 ID" 생성 — 유형 "데스크톱 앱".
4. 받은 JSON을 이 파일과 같은 폴더에 client_secret.json 으로 저장.

[실행]
    python setup_google_oauth.py
브라우저가 열리면 대상 시트를 편집할 수 있는 구글 계정으로 로그인·동의한다.
완료되면 GitHub 시크릿에 등록할 값 3개가 출력된다.
"""
from pathlib import Path

from google_auth_oauthlib.flow import InstalledAppFlow

SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]
SECRET_FILE = Path(__file__).parent / "client_secret.json"


def main():
    if not SECRET_FILE.exists():
        raise SystemExit(
            f"client_secret.json 없음 — {SECRET_FILE} 에 두고 다시 실행하세요.\n"
            "(구글 클라우드 콘솔 > OAuth 2.0 클라이언트 ID(데스크톱 앱)에서 다운로드)"
        )
    flow = InstalledAppFlow.from_client_secrets_file(str(SECRET_FILE), SCOPES)
    # access_type=offline + prompt=consent 로 refresh token 발급을 보장.
    creds = flow.run_local_server(port=0, access_type="offline",
                                  prompt="consent")
    if not creds.refresh_token:
        raise SystemExit(
            "refresh token이 발급되지 않았습니다. 구글 계정 보안설정에서 이 앱의"
            " 권한을 해제한 뒤 다시 실행하세요."
        )
    print("\n=== GitHub 저장소 시크릿에 등록할 값 ===")
    print(f"GOOGLE_OAUTH_CLIENT_ID     = {creds.client_id}")
    print(f"GOOGLE_OAUTH_CLIENT_SECRET = {creds.client_secret}")
    print(f"GOOGLE_OAUTH_REFRESH_TOKEN = {creds.refresh_token}")
    print("\n등록 경로: GitHub 저장소 > Settings > Secrets and variables > Actions")


if __name__ == "__main__":
    main()
