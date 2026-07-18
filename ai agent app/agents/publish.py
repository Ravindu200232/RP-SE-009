"""Safe publication of a green staging workspace on Windows.

Windows directory watchers may retain a handle on one generated directory after every child
process has exited.  A whole-tree rename then fails even though every file is movable.  Publication
falls back to verified same-volume child moves, while preserving the previous target as a rollback
backup until the new tree is complete.
"""
from __future__ import annotations

import shutil
from pathlib import Path


def _same_parent(*paths: Path) -> Path:
    parents = {path.resolve(strict=False).parent for path in paths}
    if len(parents) != 1:
        raise ValueError("stage, target, and backup must be siblings in one product directory")
    parent = parents.pop()
    if parent == Path(parent.anchor):
        raise ValueError("refusing publication directly under a filesystem root")
    return parent


def _move_entry(source: Path, destination: Path) -> None:
    """Rename one entry, recursively moving children only for a locked directory handle."""
    try:
        source.rename(destination)
        return
    except PermissionError:
        if not source.is_dir() or destination.exists():
            raise
    destination.mkdir()
    try:
        for child in list(source.iterdir()):
            _move_entry(child, destination / child.name)
    except Exception:
        # Put already-moved children back before propagating the publication failure.
        for child in list(destination.iterdir()):
            _move_entry(child, source / child.name)
        destination.rmdir()
        raise
    # The handle owner may still prevent removal. It is now an empty unpublished shell and does not
    # affect the complete target; a later staging preparation can remove or reuse it.
    try:
        source.rmdir()
    except OSError:
        pass


def publish_stage(stage: Path, target: Path, backup: Path) -> tuple[Path, bool]:
    """Publish ``stage`` and return ``(target, residual_empty_stage_exists)``."""
    stage, target, backup = Path(stage), Path(target), Path(backup)
    _same_parent(stage, target, backup)
    if not stage.is_dir():
        raise FileNotFoundError(f"staging workspace does not exist: {stage}")
    if backup.exists():
        shutil.rmtree(backup)
    moved_old = False
    try:
        if target.exists():
            target.rename(backup)
            moved_old = True
        _move_entry(stage, target)
    except Exception:
        if target.exists():
            stage.mkdir(exist_ok=True)
            for child in list(target.iterdir()):
                _move_entry(child, stage / child.name)
            try:
                target.rmdir()
            except OSError:
                pass
        if moved_old and not target.exists() and backup.exists():
            backup.rename(target)
        raise
    if backup.exists():
        shutil.rmtree(backup)
    residual = stage.exists()
    return target, residual
