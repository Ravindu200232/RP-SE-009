"""Read dependency advisories with the project's package manager, without applying fixes."""
from __future__ import annotations

import json
import re
from pathlib import Path

from .security import redact_text
from .tools import run_command

SEVERITIES = ('info', 'low', 'moderate', 'high', 'critical')


def dependency_command(root: Path, manager: str, refresh=False) -> list[str]:
    manager = str(manager or 'npm').split('@')[0]
    if manager == 'yarn':
        package = json.loads((root / 'package.json').read_text(encoding='utf-8'))
        version = re.search(r'yarn@(\d+)', str(package.get('packageManager', '')))
        modern = (version and int(version[1]) > 1) or (root / '.yarnrc.yml').is_file()
        if refresh:
            return ['yarn', 'install', '--mode', 'update-lockfile'] if modern else ['yarn', 'install', '--ignore-scripts']
        return ['yarn', 'npm', 'audit', '--all', '--recursive', '--json'] if modern else ['yarn', 'audit', '--json']
    commands = {
        'npm': ['npm', 'install', '--package-lock-only', '--ignore-scripts', '--no-audit', '--no-fund'] if refresh else ['npm', 'audit', '--json'],
        'pnpm': ['pnpm', 'install', '--lockfile-only', '--ignore-scripts'] if refresh else ['pnpm', 'audit', '--json'],
        'bun': ['bun', 'install', '--lockfile-only', '--ignore-scripts'] if refresh else ['bun', 'audit', '--json'],
    }
    if manager not in commands:
        raise ValueError(f'No dependency audit configured for package manager {manager}')
    return commands[manager]


def parse_report(output: str) -> tuple[dict, bool]:
    try:
        reports = [json.loads(output)]
    except ValueError:
        reports = []
        for line in output.splitlines():
            try:
                reports.append(json.loads(line))
            except ValueError:
                continue
    counts = dict.fromkeys(SEVERITIES, 0)
    recognized = False
    summaries, advisories = [], set()

    def visit(value, name=''):
        nonlocal recognized
        if isinstance(value, list):
            for item in value:
                visit(item, name)
        elif isinstance(value, dict):
            if not value:
                return
            if any(key in value and isinstance(value[key], int) for key in SEVERITIES):
                summaries.append({key: max(0, int(value.get(key, 0))) for key in SEVERITIES})
                recognized = True
            fields = {str(key).lower(): item for key, item in value.items()}
            severity = str(fields.get('severity', '')).lower()
            if severity in counts:
                identity = (fields.get('name') or fields.get('module_name') or name,
                            str(fields.get('id') or fields.get('source') or fields.get('title') or fields.get('url') or ''), severity)
                advisories.add(identity)
                recognized = True
            for key, item in value.items():
                visit(item, str(key))

    for report in reports:
        visit(report)
    if summaries:
        counts = {key: max(summary[key] for summary in summaries) for key in SEVERITIES}
    else:
        for _, _, severity in advisories:
            counts[severity] += 1
    counts['total'] = sum(counts.values())
    return counts, recognized or bool(reports and all(report in ({}, []) for report in reports))


def audit_dependencies(root: Path, manager: str, runner=None) -> dict:
    runner = runner or run_command
    try:
        args = dependency_command(root, manager)
        proc = runner(args, cwd=root, timeout=180, authenticated=False, env={'CI': '1', 'NODE_ENV': ''})
        output = redact_text(proc.stdout + '\n' + proc.stderr)
        findings, recognized = parse_report(proc.stdout)
        passed = recognized and proc.returncode == 0 and findings['total'] == 0
        if not recognized:
            output = 'Dependency audit did not produce a recognized advisory report.\n' + output
        return {'attempted': True, 'passed': passed, 'findings': findings, 'output': output[:16000]}
    except Exception as exc:
        return {'attempted': True, 'passed': False, 'findings': {}, 'output': redact_text(str(exc))[:16000]}


def security_passed(validation: dict, build: dict) -> bool:
    return bool(validation.get('passed') and not validation.get('repairable_warnings')
                and not build.get('dependency_findings', {}).get('total', 0)
                and build.get('dependency_audit', {}).get('passed', True))


def repair_diagnostics(validation: dict, build: dict) -> str:
    return redact_text(json.dumps({
        'security_errors': validation.get('errors', []),
        'security_warnings': validation.get('repairable_warnings', []),
        'dependency_findings': build.get('dependency_findings', {}),
        'dependency_audit': build.get('dependency_audit', {}).get('output', '')[:10000],
        'build_output': build.get('output', '')[-6000:],
    }))
