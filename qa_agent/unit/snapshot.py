"""
The bytes of the files a fix is about to touch, so a bad fix costs nothing.

This is the strongest of the safeguards around automated repair, and also the
cheapest: a dict of at most four small files. Everything else in this
subsystem — the verdict protocol, the deterministic priors, the blast-radius
cap — reduces the *chance* of a wrong edit. This one bounds the *cost* of the
wrong edit that gets through anyway, which is the only guarantee that survives
a model behaving in a way nobody predicted.

Two details are load-bearing:

* **Bytes, not text.** `read_text`/`write_text` round-trip through the
  platform's newline translation, so a restore on Windows can hand back a file
  that differs from the original in every line ending. Then `npm run build`
  re-runs for nothing, every diff is unreadable, and "byte-identical restore"
  is not true. `read_bytes`/`write_bytes` has no such step.
* **Absence is a state worth remembering.** A fix that *creates* a file must be
  undoable too, and the undo is a delete. Recording `None` for a path that did
  not exist is what makes `restore()` total rather than best-effort.
"""
import logging
from pathlib import Path

log = logging.getLogger("qa.snapshot")


class FileSnapshot:
    """Capture, compare, restore. Nothing else."""

    def __init__(self, project_dir):
        self.project_dir = Path(project_dir)
        self._saved = {}

    def capture(self, rels) -> int:
        """
        Remember the current bytes of each path. Already-captured paths keep
        their *first* value.

        That last part matters across rounds: round 2 must be able to restore
        to the state before round 1, not to whatever round 1 left behind. A
        second capture of the same file would otherwise quietly bless a bad
        edit as the new baseline.
        """
        n = 0
        for rel in rels or ():
            key = self._key(rel)
            if not key or key in self._saved:
                continue
            fp = self.project_dir / key
            try:
                self._saved[key] = fp.read_bytes() if fp.is_file() else None
                n += 1
            except Exception as e:
                log.warning(f"snapshot: cannot read {key}: {e}")
        return n

    def _key(self, rel):
        return (rel or "").strip().lstrip("./").replace("\\", "/")

    def paths(self) -> list:
        return sorted(self._saved)

    def __len__(self):
        return len(self._saved)

    def changed(self) -> list:
        """Which captured paths differ from what was captured."""
        out = []
        for key, before in self._saved.items():
            fp = self.project_dir / key
            try:
                now = fp.read_bytes() if fp.is_file() else None
            except Exception:
                now = None
            if now != before:
                out.append(key)
        return sorted(out)

    def restore(self, rels=None) -> list:
        """
        Put the captured bytes back. Returns what was actually reverted.

        A path captured as absent is deleted rather than written, so a fix that
        created a file leaves nothing behind.
        """
        keys = ([self._key(r) for r in rels] if rels is not None
                else list(self._saved))
        done = []
        for key in keys:
            if key not in self._saved:
                continue
            before = self._saved[key]
            fp = self.project_dir / key
            try:
                now = fp.read_bytes() if fp.is_file() else None
                if now == before:
                    continue
                if before is None:
                    if fp.is_file():
                        fp.unlink()
                else:
                    fp.parent.mkdir(parents=True, exist_ok=True)
                    fp.write_bytes(before)
                done.append(key)
            except Exception as e:
                log.warning(f"snapshot: cannot restore {key}: {e}")
        return sorted(done)

    def forget(self, rels=None):
        """Accept the current state as final. Called once a round is kept."""
        if rels is None:
            self._saved.clear()
            return
        for rel in rels:
            self._saved.pop(self._key(rel), None)
