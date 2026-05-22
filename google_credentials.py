"""구글 OAuth refresh token으로 Sheets API 자격증명을 구성한다.

자격증명 3종은 환경변수(GitHub Actions 시크릿) 우선, 없으면 로컬
oauth_local.json(git 추적 제외)에서 로드한다.
"""
import json
import os
from pathlib import Path

_SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]
_TOKEN_URI = "https://oauth2.googleapis.com/token"
_LOCAL_FILE = Path(__file__).parent / "oauth_local.json"
_KEYS = ("client_id", "client_secret", "refresh_token")
_ENV = {
    "client_id": "GOOGLE_OAUTH_CLIENT_ID",
    "client_secret": "GOOGLE_OAUTH_CLIENT_SECRET",
    "refresh_token": "GOOGLE_OAUTH_REFRESH_TOKEN",
}


def _load_config() -> dict:
    """OAuth 자격증명 dict 반환. 환경변수 → 로컬파일 순. 없으면 RuntimeError."""
    env = {k: os.environ.get(_ENV[k]) for k in _KEYS}
    if all(env.values()):
        return env
    if _LOCAL_FILE.exists():
        data = json.loads(_LOCAL_FILE.read_text(encoding="utf-8"))
        if all(data.get(k) for k in _KEYS):
            return {k: data[k] for k in _KEYS}
    raise RuntimeError(
        "구글 OAuth 자격증명 미설정 — 환경변수 GOOGLE_OAUTH_CLIENT_ID/"
        "GOOGLE_OAUTH_CLIENT_SECRET/GOOGLE_OAUTH_REFRESH_TOKEN 또는 "
        "oauth_local.json 필요. setup_google_oauth.py로 발급."
    )


def build_credentials():
    """refresh token 기반 Credentials 생성 (access token 자동 갱신)."""
    from google.oauth2.credentials import Credentials
    c = _load_config()
    return Credentials(
        token=None,
        refresh_token=c["refresh_token"],
        client_id=c["client_id"],
        client_secret=c["client_secret"],
        token_uri=_TOKEN_URI,
        scopes=_SCOPES,
    )
