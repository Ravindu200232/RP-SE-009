@echo off
rem ---------------------------------------------------------------------------
rem  AgentForge Studio - start the backend and the UI.
rem
rem  Two servers, in that order:
rem
rem    python server.py      the pipeline.  HTTP :7824, WebSocket :7825
rem    studio  npm run dev   the UI.        :3000, served under /__agentforge
rem
rem  The order matters: the studio proxies /__agentforge/api/... straight through
rem  to Python on 7824, so a studio that comes up first answers 502 until the
rem  backend is listening.  This waits for each one instead of guessing.
rem
rem  Each server gets its own window so its log is visible.  Closing a window
rem  stops that server; closing this one does not.
rem ---------------------------------------------------------------------------
setlocal EnableDelayedExpansion
cd /d "%~dp0"
title AgentForge Studio - launcher

set "API_PORT=7824"
set "WS_PORT=7825"
set "UI_PORT=3000"
set "UI_URL=http://localhost:%UI_PORT%/__agentforge"

rem  Pulled only when the machine has no cloud model at all.  Any model whose
rem  name ends `:cloud` or `-cloud` satisfies the check, so an existing choice
rem  is never overridden.
set "CLOUD_MODEL=qwen3.5:397b-cloud"

echo.
echo   AgentForge Studio
echo   -----------------
echo.

rem --- the two that cannot be installed for you -------------------------------
rem
rem  Everything below this can be fetched automatically.  These two cannot:
rem  they are what runs the installer itself, and a machine without them needs
rem  a person, not a script.
where python >nul 2>&1
if errorlevel 1 (
  echo   [x] python is not on PATH.  Install Python 3.11+ and try again.
  echo       https://www.python.org/downloads/
  goto :fail
)
where node >nul 2>&1
if errorlevel 1 (
  echo   [x] node is not on PATH.  Install Node 20+ and try again.
  echo       https://nodejs.org/
  goto :fail
)
for /f "tokens=*" %%v in ('python --version 2^>^&1') do echo   [+] %%v
for /f "tokens=*" %%v in ('node --version 2^>^&1') do echo   [+] node %%v

rem --- the tools a deployment needs ------------------------------------------
rem
rem  Only what is missing.  A tool already on PATH is left completely alone --
rem  no version check, no reinstall -- because the machine that has it may have
rem  got it from somewhere this script does not know about, and replacing a
rem  working install is a worse outcome than an old one.
rem
rem  None of these is fatal.  git and gh are needed by every deployment, aws by
rem  the two AWS targets and vercel by the Vercel one, but all of that happens
rem  on the Deploy tab long after the studio is up.  Refusing to start over a
rem  missing aws CLI would block writing an app for someone who only wanted to
rem  write an app.
echo.
echo   Checking the deployment tools...
call :need git    "Git"            Git.Git
call :need gh     "GitHub CLI"     GitHub.cli
call :need aws    "AWS CLI"        Amazon.AWSCLI
call :need ollama "Ollama"         Ollama.Ollama

rem  Vercel ships on npm rather than winget, so it gets its own line.
where vercel >nul 2>&1
if errorlevel 1 (
  echo   [*] Vercel CLI missing - installing with npm...
  call npm install -g vercel >nul 2>&1
  where vercel >nul 2>&1
  if errorlevel 1 (
    echo   [warn] could not install the Vercel CLI.  Deploying to Vercel will
    echo          not work until you run:  npm install -g vercel
  ) else (
    echo   [+] Vercel CLI installed
  )
) else (
  echo   [+] Vercel CLI
)

rem --- an Ollama cloud model -------------------------------------------------
rem
rem  A cloud model is one whose name ends in `:cloud` or `-cloud`.  The SRS and
rem  the QA author both refuse to run on a local model, so without one of these
rem  the studio starts but two of its tabs cannot do anything.
rem
rem  Pulling one needs an ollama.com account, and signing in is interactive --
rem  so this attempts the pull and, if it fails, says exactly which command to
rem  run rather than pretending to have fixed it.
where ollama >nul 2>&1
if not errorlevel 1 (
  set "HAS_CLOUD="
  for /f "tokens=1" %%m in ('ollama list 2^>nul') do (
    echo %%m | findstr /i /c:":cloud" /c:"-cloud" >nul && set "HAS_CLOUD=%%m"
  )
  if defined HAS_CLOUD (
    echo   [+] cloud model !HAS_CLOUD!
  ) else (
    echo   [*] no Ollama cloud model - pulling %CLOUD_MODEL%...
    call ollama pull %CLOUD_MODEL% 2>nul
    if errorlevel 1 (
      echo   [warn] could not pull a cloud model.  The SRS and the test author
      echo          need one.  Sign in first, then pull:
      echo            ollama signin
      echo            ollama pull %CLOUD_MODEL%
    ) else (
      echo   [+] cloud model %CLOUD_MODEL% ready
    )
  )
)

rem --- a port already in use is almost always a previous run ------------------
rem
rem  Reused rather than restarted.  Spawning a second server on a port that is
rem  taken does not give you two servers - it gives you one working server and
rem  one window sitting on a bind error, which reads like a broken start.
set "SKIP_API=0"
set "SKIP_UI=0"
call :inuse %API_PORT%
if "!PORT_BUSY!"=="1" (
  set "SKIP_API=1"
  echo   [warn] port %API_PORT% is already in use - reusing that backend.
  echo          Close its window first if you wanted a fresh one.
)
call :inuse %UI_PORT%
if "!PORT_BUSY!"=="1" (
  set "SKIP_UI=1"
  echo   [warn] port %UI_PORT% is already in use - reusing that UI.
)

rem --- first run: the studio's dependencies ----------------------------------
if not exist "studio\node_modules" (
  echo.
  echo   [*] studio\node_modules is missing - installing ^(first run only^)...
  pushd studio
  call npm install
  set "NPM_RC=!errorlevel!"
  popd
  if not "!NPM_RC!"=="0" (
    echo   [x] npm install failed.  Run it by hand in the studio folder.
    goto :fail
  )
)

rem --- the backend -----------------------------------------------------------
echo.
if "!SKIP_API!"=="1" (
  echo   [*] backend already up on %API_PORT%.
) else (
  echo   [*] starting the backend...
  start "AgentForge backend  (:%API_PORT% / :%WS_PORT%)" cmd /k python server.py
  call :waitfor %API_PORT% 60 "backend"
  if "!WAIT_OK!"=="0" (
    echo   [x] the backend never started listening on %API_PORT%.
    echo       Look at its window for the reason.
    goto :fail
  )
)

rem --- the UI ----------------------------------------------------------------
if "!SKIP_UI!"=="1" (
  echo   [*] UI already up on %UI_PORT%.
) else (
  echo   [*] starting the UI...
  start "AgentForge studio  (:%UI_PORT%)" cmd /k "cd /d "%~dp0studio" && npm run dev"
  call :waitfor %UI_PORT% 120 "UI"
  if "!WAIT_OK!"=="0" (
    echo   [x] the UI never started listening on %UI_PORT%.
    echo       Look at its window for the reason.
    goto :fail
  )
)

rem --- done ------------------------------------------------------------------
echo.
echo   Backend : http://localhost:%API_PORT%   ^(WebSocket :%WS_PORT%^)
echo   UI      : %UI_URL%
echo   Preview : http://localhost:5173         ^(whatever was built last^)
echo.
echo   Opening the UI...
start "" "%UI_URL%"
echo.
echo   Both servers are running in their own windows.  Close a window to stop
echo   that server.  This one can be closed straight away.
echo.
pause
exit /b 0

rem ---------------------------------------------------------------------------
rem  :need EXE LABEL WINGET_ID
rem
rem  Install EXE through winget, but only when it is not already on PATH.
rem
rem  winget is absent on older Windows 10 and inside some managed images, so a
rem  missing package manager is reported as a missing tool with the id to
rem  install by hand -- not as a failure of the thing the user actually asked
rem  for, which was to start the studio.
rem ---------------------------------------------------------------------------
:need
where %~1 >nul 2>&1
if not errorlevel 1 (
  echo   [+] %~2
  exit /b 0
)
where winget >nul 2>&1
if errorlevel 1 (
  echo   [warn] %~2 is missing and winget is not available.
  echo          Install it by hand:  winget install -e --id %~3
  exit /b 0
)
echo   [*] %~2 missing - installing...
call winget install -e --id %~3 --accept-source-agreements --accept-package-agreements --silent >nul 2>&1
rem  winget puts new executables on the PATH of FUTURE processes, not this one,
rem  so `where` can still miss a package that installed perfectly well. Say so
rem  rather than reporting a failure that a restart would disprove.
where %~1 >nul 2>&1
if errorlevel 1 (
  echo   [warn] %~2 did not appear on PATH.  If the install itself succeeded,
  echo          close this window and run start.bat again.
) else (
  echo   [+] %~2 installed
)
exit /b 0

rem ---------------------------------------------------------------------------
rem  :inuse PORT            -> PORT_BUSY = 1 when something is listening
rem ---------------------------------------------------------------------------
:inuse
set "PORT_BUSY=0"
for /f "tokens=*" %%L in ('netstat -ano ^| findstr /r /c:":%~1 .*LISTENING" 2^>nul') do set "PORT_BUSY=1"
exit /b 0

rem ---------------------------------------------------------------------------
rem  :waitfor PORT SECONDS LABEL   -> WAIT_OK = 1 once the port is listening
rem
rem  Polls rather than sleeping a fixed amount: `next dev` takes a few seconds
rem  on a warm cache and the better part of a minute on a cold one, and a fixed
rem  wait is either too short to be reliable or too long every single time.
rem ---------------------------------------------------------------------------
:waitfor
set "WAIT_OK=0"
set /a "TRIES=%~2"
<nul set /p "=      waiting for %~3 on port %~1 "
for /l %%i in (1,1,!TRIES!) do (
  call :inuse %~1
  if "!PORT_BUSY!"=="1" (
    echo  ok
    set "WAIT_OK=1"
    exit /b 0
  )
  <nul set /p "=."
  timeout /t 1 /nobreak >nul
)
echo  timed out
exit /b 0

:fail
echo.
pause
exit /b 1
