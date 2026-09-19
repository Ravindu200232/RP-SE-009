"""Command risk policy.

The engine runs unattended, so this is the only thing standing between a
hallucinated cleanup step and the user's disk. Two jobs:

1. `classify` labels a command, which the loop reports alongside the call so a
   watcher can see what a run is actually doing.
2. `BLOCKED` is a hard stop that no configuration lifts. Unattended is not the
   same as unguarded: an autonomous loop that will run `rm -rf /` because a
   small model invented a cleanup step is a liability, not a feature. The
   refusal goes back to the model as an observation, so it re-plans rather
   than stalling.

This is defence in depth, not a security boundary. Shell quoting is endlessly
creative and a determined injection can evade any regex; use OS isolation for
untrusted projects. Local Docker execution is prohibited.
"""
from __future__ import annotations

import re

SAFE = "safe"            # read-only
MODERATE = "moderate"    # mutates the workspace
DANGEROUS = "dangerous"  # destructive or outward-facing
BLOCKED = "blocked"      # never runs

READ_ONLY_COMMANDS = frozenset("""
ls dir pwd cat head tail wc file stat du df echo printf date whoami hostname
uname env printenv which where type basename dirname realpath readlink grep
egrep fgrep findstr rg ag ack find fd locate sort uniq cut tr column jq yq
diff cmp tree node python python3 ruby php go java deno bun ps top free
uptime netstat id groups history man help
""".split())

READ_ONLY_SUBCOMMANDS = {
    "git": {"status", "log", "diff", "show", "branch", "remote", "blame", "describe",
            "rev-parse", "ls-files", "ls-remote", "shortlog", "tag", "config",
            "stash", "reflog", "cat-file", "count-objects"},
    "npm": {"ls", "list", "view", "info", "outdated", "audit", "why", "config",
            "root", "prefix", "bin", "ping", "search", "doctor", "version"},
    "yarn": {"list", "info", "why", "outdated", "versions"},
    "pnpm": {"list", "ls", "why", "outdated", "root", "bin"},
    "pip": {"list", "show", "freeze"},
    "pip3": {"list", "show", "freeze"},
}

# Flags that turn an otherwise read-only interpreter call into a write.
_WRITE_FLAGS = tuple(re.compile(p) for p in (
    r"\s-e\s", r"\s-c\s", r"\s--eval\b", r"\s-i\b", r"\s--in-place\b"))

_BLOCKED = [
    (re.compile(r"\bdocker(?:-compose)?(?:\.(?:exe|cmd|bat))?(?=[\s\"';&|]|$)|\bdocker\s*desktop(?:\.exe)?\b", re.I),
     "Docker is prohibited on the local PC; use Node checks and cloud CI"),
    (re.compile(r"\b(?:format\.com|format)\s+[a-z]:(?:\s|$)", re.I), "disk formatting"),
    (re.compile(r"\bdiskpart(?:\.exe)?\b", re.I), "raw disk management"),
    (re.compile(r"\bRemove-Item\b[^;&|\n]*(?:\$env:USERPROFILE|\$HOME|%USERPROFILE%)", re.I),
     "deletion of a home directory"),
    (re.compile(r"\brm\s+(-[a-zA-Z]*\s+)*(-[a-zA-Z]*r[a-zA-Z]*f|-[a-zA-Z]*f[a-zA-Z]*r)\S*\s+/(\s|$)"),
     "recursive force-delete of the filesystem root"),
    (re.compile(r"\brm\s+-[rRf]{1,2}\s+(/|/\*|~|\$HOME|/home|/etc|/usr|/var|/bin|/sbin|/boot|/lib|/opt|/root)(\s|/?\*?\s*$)"),
     "recursive delete of a system or home directory"),
    (re.compile(r":\(\)\s*\{\s*:\|\s*:\s*&\s*\}\s*;\s*:"), "fork bomb"),
    (re.compile(r"\bmkfs(\.\w+)?\b"), "filesystem format"),
    (re.compile(r"\bdd\b[^|;]*\bof=/dev/(sd|nvme|hd|disk|vd)"), "raw write to a block device"),
    (re.compile(r"\bchmod\s+(-[a-zA-Z]+\s+)*777\s+/(\s|$)"), "world-writable filesystem root"),
    (re.compile(r"\bchown\s+(-[a-zA-Z]+\s+)*\S+\s+/(\s|$)"), "ownership change on the filesystem root"),
    (re.compile(r"\b(curl|wget)\b[^|]*\|\s*(sudo\s+)?(ba|z|k|da)?sh\b"),
     "piping a downloaded script straight into a shell"),
    (re.compile(r"\b(shutdown|reboot|halt|poweroff|init\s+0|init\s+6)\b"), "host power state change"),
    (re.compile(r"\b(userdel|useradd|usermod|passwd|visudo)\b"), "system account modification"),
    (re.compile(r">\s*/etc/(passwd|shadow|sudoers|hosts)\b"), "overwrite of a critical system file"),
    (re.compile(r"\bcrontab\s+-r\b"), "crontab wipe"),
    (re.compile(r"\biptables\b[^|;]*(-F|--flush)"), "firewall flush"),
    (re.compile(r"\bgit\s+push\b[^|;]*(--force|-f)\b[^|;]*\b(main|master|develop|production)\b"),
     "force-push to a protected branch"),
    (re.compile(r"\bgit\s+push\b[^|;]*--mirror\b"), "mirror push"),
]

_DANGEROUS = [
    (re.compile(r"\brm\s+-[rRf]"), "recursive or forced delete"),
    (re.compile(r"\brm\b"), "file deletion"),
    (re.compile(r"\bgit\s+(reset\s+--hard|clean\s+-[a-z]*f|checkout\s+--\s|restore\s)"),
     "discards uncommitted work"),
    (re.compile(r"\bgit\s+push\b"), "publishes commits to a remote"),
    (re.compile(r"\bgit\s+(rebase|filter-branch|reflog\s+expire)\b"), "rewrites git history"),
    (re.compile(r"\bsudo\b"), "runs with elevated privileges"),
    (re.compile(r"\b(npm|yarn|pnpm)\s+publish\b"), "publishes a package to a registry"),
    (re.compile(r"\b(terraform|tofu)\s+(apply|destroy)\b"), "mutates real infrastructure"),
    (re.compile(r"\b(nc|ncat|ssh|scp|rsync|ftp|telnet)\b"), "network access to a remote host"),
    (re.compile(r"\b(kill|killall|pkill)\s+-9\b"), "force-kills processes"),
    (re.compile(r"\btruncate\b|\bshred\b"), "destroys file contents"),
]

_SEPARATORS = re.compile(r"&&|\|\||;|\||\n|(?<![>&])&(?![>&])")
_REDIRECT = re.compile(r"(^|[^0-9<>&])>{1,2}(?!&)")
_NULL_SINK = re.compile(r"(?:^|\s)(?:[12])?>{1,2}\s*(?:nul|/dev/null)(?=\s|$)", re.I)
_ENV_PREFIX = re.compile(r"^(\w+=\S*\s+)+")


def classify(command: str) -> tuple[str, str]:
    """Return `(risk, reason)` for one shell command."""
    text = re.sub(r"\s+", " ", str(command or "")).strip()
    if not text:
        return BLOCKED, "empty command"
    for pattern, reason in _BLOCKED:
        if pattern.search(text):
            return BLOCKED, reason
    for pattern, reason in _DANGEROUS:
        if pattern.search(text):
            return DANGEROUS, reason
    if is_read_only(text):
        return SAFE, "read-only command"
    return MODERATE, "may modify the workspace"


def is_read_only(command: str) -> bool:
    """True only when every segment is read-only.

    `ls && rm -rf build` must not pass merely because it starts with `ls`.
    """
    text = re.sub(r"\s+", " ", str(command or "")).strip()
    if not text:
        return False
    # Sending diagnostics to the platform null sink is still read-only, so
    # strip those before the general "writes to a file" rule applies.
    stripped = _NULL_SINK.sub(" ", text)
    if _REDIRECT.search(stripped):
        return False

    segments = [s.strip() for s in _SEPARATORS.split(stripped) if s and s.strip()]
    if not segments:
        return False

    for segment in segments:
        body = _ENV_PREFIX.sub("", segment).strip()
        parts = body.split()
        binary = parts[0].split("/")[-1].split("\\")[-1] if parts else ""
        if not binary or binary == "sudo":
            return False

        allowed = READ_ONLY_SUBCOMMANDS.get(binary)
        if allowed is not None:
            args = parts[1:]
            if args and all(a.startswith("-") for a in args) and any(
                    a in ("--version", "-v", "--help", "-h") for a in args):
                continue
            sub = next((a for a in args if not a.startswith("-")), None)
            if sub and sub in allowed:
                continue
            return False

        if binary not in READ_ONLY_COMMANDS:
            return False
        if any(p.search(f" {body} ") for p in _WRITE_FLAGS):
            return False
        # A bare interpreter running a script file can do anything.
        if binary in {"node", "python", "python3", "ruby", "php", "deno", "bun", "java", "go"}:
            if any(not a.startswith("-") for a in parts[1:]):
                return False
    return True
