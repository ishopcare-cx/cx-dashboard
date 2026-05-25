@echo off
REM PC 폴링 — 대시보드 "콜 신규 수집" 클릭 감지 후 collect_call.py 실행.
REM 1분마다 작업스케줄러가 호출. 새 요청 없으면 즉시 종료.
cd /d "%~dp0"
set PYTHONIOENCODING=utf-8
".venv\Scripts\python.exe" poll_collect_call.py >> poll_call.log 2>&1
exit /b %ERRORLEVEL%
