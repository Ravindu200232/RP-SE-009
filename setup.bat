@echo off
setlocal
cd /d "%~dp0"
title AgentForge Setup

where node >nul 2>&1 || (
  echo [AgentForge] Node.js 20+ is required.
  exit /b 1
)
where npm >nul 2>&1 || (
  echo [AgentForge] npm is required.
  exit /b 1
)

set "PY=python"
where python >nul 2>&1 || (
  where py >nul 2>&1 || (
    echo [AgentForge] Python 3.11+ is required.
    exit /b 1
  )
  set "PY=py -3"
)

echo [1/4] Installing Python dependencies...
REM One file at a time, so a wheel that will not build on this machine names
REM itself. Installed as a single command, a failure anywhere stopped all three
REM lists and the message said only that pip had failed - which is how a new
REM machine ended up running with the specification agent's packages missing.
for %%R in ("requirements.txt" "srs-agent\requirements.txt" "deployment-agent\requirements.txt") do (
  echo   - %%~R
  %PY% -m pip install -r %%~R
  if errorlevel 1 (
    echo [AgentForge] Could not install %%~R - see the pip output above.
    exit /b 1
  )
)

echo [2/4] Installing Electron dependencies...
if exist desktop\package-lock.json (
  call npm --prefix desktop ci --no-audit --no-fund
) else (
  call npm --prefix desktop install --no-audit --no-fund
)
if errorlevel 1 exit /b 1

echo [3/4] Installing Studio dependencies...
if exist studio\package-lock.json (
  call npm --prefix studio ci --no-audit --no-fund
) else (
  call npm --prefix studio install --no-audit --no-fund
)
if errorlevel 1 exit /b 1

echo [4/5] Preparing runtime folders...
if not exist production-ready mkdir production-ready
if not exist logs mkdir logs

echo [5/5] Registering Ollama models...
REM The models were only ever on the machine they were first pulled on, so a
REM second machine came up with an empty `ollama list` and a model picker with
REM nothing in it. These are cloud models: a pull fetches a manifest of a few
REM hundred bytes and registers the name, so nothing here downloads weights or
REM costs disk. It does cost about half a minute per model on the round trip,
REM which is why each one is announced and why the ones already registered are
REM skipped - a second run of setup should be quick.
where ollama >nul 2>&1
if errorlevel 1 (
  echo   - Ollama is not installed; skipping. Install it from https://ollama.com
  echo     and re-run setup to register the models.
) else (
  if not exist ollama-models.txt (
    echo   - ollama-models.txt is missing; skipping.
  ) else (
    set "MISSED="
    call ollama list > "%TEMP%\agentforge-models.txt" 2>nul
    for /f "usebackq eol=# tokens=* delims= " %%M in ("ollama-models.txt") do (
      if not "%%M"=="" (
        findstr /b /l /c:"%%M " "%TEMP%\agentforge-models.txt" >nul 2>&1
        if errorlevel 1 (
          echo   - %%M  ... registering
          call ollama pull %%M >nul 2>&1
          if errorlevel 1 call set "MISSED=%%MISSED%% %%M"
        ) else (
          echo   - %%M  already registered
        )
      )
    )
    del "%TEMP%\agentforge-models.txt" >nul 2>&1
    call :report
  )
)

echo AgentForge setup complete. Run start.bat.
exit /b 0

:report
REM Delayed by a call so the loop's own value of MISSED is read, not the one
REM the whole block was parsed with.
if defined MISSED (
  echo.
  echo   Could not pull:%MISSED%
  echo   Cloud models need an Ollama account on this machine - run `ollama signin`
  echo   and then `setup.bat` again. Everything else is installed.
)
exit /b 0
