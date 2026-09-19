"""Replace exact comment blocks, asserting every one matched."""
import sys
from pathlib import Path


def apply(path: str, pairs: list[tuple[str, str]]) -> None:
    p = Path(path)
    src = p.read_text(encoding="utf-8")
    before_lines = len(src.splitlines())
    missed = []
    for old, new in pairs:
        if old not in src:
            missed.append(old.strip().splitlines()[0][:70])
            continue
        if src.count(old) != 1:
            missed.append(f"NOT UNIQUE: {old.strip().splitlines()[0][:60]}")
            continue
        src = src.replace(old, new, 1)
    if missed:
        print(f"  {path}: {len(missed)} block(s) did not match:")
        for m in missed:
            print(f"      {m}")
        sys.exit(1)
    p.write_text(src, encoding="utf-8")
    after = len(src.splitlines())
    print(f"  {path}: {len(pairs)} blocks, {before_lines} -> {after} lines "
          f"({before_lines - after} fewer)")
