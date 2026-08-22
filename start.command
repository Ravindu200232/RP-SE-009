#!/bin/bash
# ---------------------------------------------------------------------------
#  AgentForge Studio - start the backend and the UI.  macOS.
#
#  The counterpart of start.bat, and deliberately the same shape: same two
#  servers, same order, same reasons.
#
#    python server.py      the pipeline.  HTTP :7824, WebSocket :7825
#    studio  npm run dev   the UI.        :3000, served under /__agentforge
#
#  The order matters: the studio proxies /__agentforge/api/... straight through
#  to Python on 7824, so a studio that comes up first answers 502 until the
#  backend is listening.  This waits for each one instead of guessing.
#
#  Named .command rather than .sh so Finder will run it on a double-click.
#  Both servers run in this window; Ctrl-C stops both.
# ---------------------------------------------------------------------------
set -u
cd "$(dirname "$0")"

API_PORT=7824
WS_PORT=7825
UI_PORT=3000
UI_URL="http://localhost:${UI_PORT}/__agentforge"

# Pulled only when the machine has no cloud model at all. Any model whose name
# ends `:cloud` or `-cloud` satisfies the check, so an existing choice is never
# overridden.
CLOUD_MODEL="qwen3.5:397b-cloud"

echo
echo "  AgentForge Studio"
echo "  -----------------"
echo

# --- the two that cannot be installed for you -------------------------------
#
# Everything below this can be fetched automatically. These two cannot: they
# are what runs the installer itself, and a machine without them needs a
# person, not a script.
need_or_die() {
    command -v "$1" >/dev/null 2>&1 && return 0
    echo "  [x] $1 is not on PATH. $2"
    echo
    read -r -p "  Press return to close. " _
    exit 1
}
need_or_die python3 "Install Python 3.11+ — https://www.python.org/downloads/"
need_or_die node    "Install Node 20+ — https://nodejs.org/"

echo "  [+] $(python3 --version 2>&1)"
echo "  [+] node $(node --version 2>&1)"

# --- the tools a deployment needs -------------------------------------------
#
# Only what is missing. A tool already on PATH is left completely alone -- no
# version check, no reinstall -- because the machine that has it may have got
# it from somewhere this script does not know about, and replacing a working
# install is a worse outcome than an old one.
#
# None of these is fatal. git and gh are needed by every deployment, aws by the
# two AWS targets and vercel by the Vercel one, but all of that happens on the
# Deploy tab long after the studio is up. Refusing to start over a missing aws
# CLI would block writing an app for someone who only wanted to write an app.
echo
echo "  Checking the deployment tools..."

need() {                      # need <exe> <label> <brew-formula>
    if command -v "$1" >/dev/null 2>&1; then
        echo "  [+] $2"
        return 0
    fi
    if ! command -v brew >/dev/null 2>&1; then
        echo "  [warn] $2 is missing and Homebrew is not installed."
        echo "         Install Homebrew from https://brew.sh, then: brew install $3"
        return 0
    fi
    echo "  [*] $2 missing - installing with Homebrew..."
    if brew install "$3" >/dev/null 2>&1 && command -v "$1" >/dev/null 2>&1; then
        echo "  [+] $2 installed"
    else
        echo "  [warn] could not install $2.  By hand:  brew install $3"
    fi
}

need git    "Git"        git
need gh     "GitHub CLI" gh
need aws    "AWS CLI"    awscli
need ollama "Ollama"     ollama

# Vercel ships on npm rather than Homebrew, so it gets its own block.
if command -v vercel >/dev/null 2>&1; then
    echo "  [+] Vercel CLI"
else
    echo "  [*] Vercel CLI missing - installing with npm..."
    if npm install -g vercel >/dev/null 2>&1 && command -v vercel >/dev/null 2>&1; then
        echo "  [+] Vercel CLI installed"
    else
        echo "  [warn] could not install the Vercel CLI.  Deploying to Vercel will"
        echo "         not work until you run:  npm install -g vercel"
    fi
fi

# --- an Ollama cloud model ---------------------------------------------------
#
# A cloud model is one whose name ends in `:cloud` or `-cloud`. The SRS and the
# QA author both refuse to run on a local model, so without one of these the
# studio starts but two of its tabs cannot do anything.
#
# Pulling one needs an ollama.com account, and signing in is interactive -- so
# this attempts the pull and, if it fails, says exactly which command to run
# rather than pretending to have fixed it.
if command -v ollama >/dev/null 2>&1; then
    existing=$(ollama list 2>/dev/null | awk 'NR>1 {print $1}' \
               | grep -Ei ':cloud$|-cloud$' | head -1 || true)
    if [ -n "${existing}" ]; then
        echo "  [+] cloud model ${existing}"
    else
        echo "  [*] no Ollama cloud model - pulling ${CLOUD_MODEL}..."
        if ollama pull "${CLOUD_MODEL}" >/dev/null 2>&1; then
            echo "  [+] cloud model ${CLOUD_MODEL} ready"
        else
            echo "  [warn] could not pull a cloud model.  The SRS and the test author"
            echo "         need one.  Sign in first, then pull:"
            echo "           ollama signin"
            echo "           ollama pull ${CLOUD_MODEL}"
        fi
    fi
fi

# --- a port already in use is almost always a previous run -------------------
#
# Reused rather than restarted. Spawning a second server on a port that is
# taken does not give you two servers - it gives you one working server and one
# process sitting on a bind error, which reads like a broken start.
inuse() { lsof -nP -iTCP:"$1" -sTCP:LISTEN >/dev/null 2>&1; }

SKIP_API=0
SKIP_UI=0
if inuse "${API_PORT}"; then
    SKIP_API=1
    echo "  [warn] port ${API_PORT} is already in use - reusing that backend."
fi
if inuse "${UI_PORT}"; then
    SKIP_UI=1
    echo "  [warn] port ${UI_PORT} is already in use - reusing that UI."
fi

# --- first run: the studio's dependencies ------------------------------------
if [ ! -d "studio/node_modules" ]; then
    echo
    echo "  [*] studio/node_modules is missing - installing (first run only)..."
    ( cd studio && npm install ) || {
        echo "  [x] npm install failed.  Run it by hand in the studio folder."
        exit 1
    }
fi

# Both children are killed with this window, so closing it never leaves a
# server holding a port that the next run then reports as "already in use".
PIDS=()
cleanup() {
    echo
    echo "  stopping..."
    for pid in "${PIDS[@]:-}"; do kill "${pid}" 2>/dev/null || true; done
}
trap cleanup EXIT INT TERM

# Polls rather than sleeping a fixed amount: `next dev` takes a few seconds on
# a warm cache and the better part of a minute on a cold one, and a fixed wait
# is either too short to be reliable or too long every single time.
waitfor() {                   # waitfor <port> <seconds> <label>
    printf "      waiting for %s on port %s " "$3" "$1"
    for _ in $(seq 1 "$2"); do
        if inuse "$1"; then echo " ok"; return 0; fi
        printf "."
        sleep 1
    done
    echo " timed out"
    return 1
}

echo
if [ "${SKIP_API}" = "1" ]; then
    echo "  [*] backend already up on ${API_PORT}."
else
    echo "  [*] starting the backend..."
    python3 server.py &
    PIDS+=($!)
    waitfor "${API_PORT}" 60 "backend" || {
        echo "  [x] the backend never started listening on ${API_PORT}."
        exit 1
    }
fi

if [ "${SKIP_UI}" = "1" ]; then
    echo "  [*] UI already up on ${UI_PORT}."
else
    echo "  [*] starting the UI..."
    ( cd studio && npm run dev ) &
    PIDS+=($!)
    waitfor "${UI_PORT}" 120 "UI" || {
        echo "  [x] the UI never started listening on ${UI_PORT}."
        exit 1
    }
fi

echo
echo "  Backend : http://localhost:${API_PORT}   (WebSocket :${WS_PORT})"
echo "  UI      : ${UI_URL}"
echo "  Preview : http://localhost:5173         (whatever was built last)"
echo
echo "  Opening the UI..."
open "${UI_URL}" 2>/dev/null || true
echo
echo "  Both servers run in this window.  Ctrl-C stops them."
echo
wait
