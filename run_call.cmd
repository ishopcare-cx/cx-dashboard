@echo off
REM PC 작업 스케줄러용 콜라비 수집 실행기.
REM 실패 시 최대 2회 자동 재시도 (1분 간격).
cd /d "%~dp0"
set PYTHONIOENCODING=utf-8

set ATTEMPT=1
:RETRY
echo [%date% %time%] 시도 %ATTEMPT%회 >> collect_call.log 2>&1
".venv\Scripts\python.exe" collect_call.py >> collect_call.log 2>&1
if %ERRORLEVEL%==0 goto SUCCESS
if %ATTEMPT%==3 goto FAIL
set /a ATTEMPT=%ATTEMPT%+1
timeout /t 60 /nobreak >nul
goto RETRY

:SUCCESS
echo [%date% %time%] 수집 완료 (시도 %ATTEMPT%회) >> collect_call.log 2>&1
exit /b 0

:FAIL
echo [%date% %time%] 3회 시도 모두 실패 >> collect_call.log 2>&1
exit /b 1
