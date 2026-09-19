"""Local deployment checks never run Docker or Docker Compose."""
from __future__ import annotations

import json
import os
import re
import tempfile
from pathlib import Path

DOCKER = re.compile(r"\bdocker(?:-compose)?(?:\.(?:exe|cmd|bat))?(?=[\s\"';&|]|$)|\bdocker\s*desktop(?:\.exe)?\b", re.I)


def assert_no_local_docker(args: list[str], cwd: Path | str | None = None) -> None:
    name = Path(args[0].replace('\\', '/')).name.lower()
    if name in {'docker', 'docker.exe', 'docker.cmd', 'docker.bat', 'docker-compose', 'docker-compose.exe', 'docker-compose.cmd', 'docker-compose.bat', 'docker desktop.exe', 'dockerdesktop.exe'}:
        raise ValueError('Docker is prohibited on the local PC; use Node checks and the GitHub Actions cloud runner')
    if name.split('.')[0] not in {'npm', 'pnpm', 'yarn', 'bun', 'npx'} or not cwd:
        return
    package = Path(cwd) / 'package.json'
    if package.is_file():
        scripts = json.loads(package.read_text(encoding='utf-8')).get('scripts', {})
        if any(DOCKER.search(str(script)) for script in scripts.values()):
            raise ValueError('Local package scripts contain Docker; move container work to GitHub Actions before local validation')


def docker_block_environment() -> dict[str, str]:
    # Also block indirect `docker` calls from dependency lifecycle scripts.
    folder = Path(tempfile.gettempdir()) / 'agentforge-no-local-docker'
    folder.mkdir(parents=True, exist_ok=True)
    for name in ('docker', 'docker-compose'):
        if os.name == 'nt':
            path = folder / (name + '.cmd')
            text = '@echo off\necho Docker is prohibited on this local PC. Use the cloud runner. 1>&2\nexit /b 1\n'
        else:
            path = folder / name
            text = '#!/bin/sh\necho "Docker is prohibited on this local PC. Use the cloud runner." >&2\nexit 1\n'
        if not path.is_file() or path.read_text(encoding='utf-8') != text:
            path.write_text(text, encoding='utf-8')
        if os.name != 'nt':
            path.chmod(0o700)
    return {'PATH': str(folder), 'DOCKER_HOST': 'tcp://127.0.0.1:1', 'DOCKER_CONTEXT': ''}
