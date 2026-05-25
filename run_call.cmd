@echo off
REM PC 작업 스케줄러용 콜라비 수집 실행기.
REM 콜라비 서버는 회사 IP만 허용 → GitHub Actions 불가. PC에서 돌린다.
REM 로컬 자격증명(colabee_local.json, oauth_local.json) 사용.
cd /d "%~dp0"
set PYTHONIOENCODING=utf-8
".venv\Scripts\python.exe" collect_call.py >> collect_call.log 2>&1
exit /b %ERRORLEVEL%
