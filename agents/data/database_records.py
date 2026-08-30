"""Focused data responsibilities for MongoManager."""
# Source: database_helpers.py — imported helper(s) come from this file.
from agents.data.database_helpers import *


class MongoManagerDataMixin:
    # Drop a generated app's database so its seed runs again. Generated apps guard `ensureSeeded()` with
    # `countDocuments() > 0`, and `db_name_for()` is a deterministic function of the project name. So a seed corrected
    # after a bad first run can never take effect — the rows are already there. Dropping the database is the only way
    # to let the fix land. Destructive, therefore fenced: * refuses when the user configured their own `MONGODB_URI` —
    # that is their server, possibly with real data, and AgentForge did not create it; * refuses any database whose
    # name is not `agentforge_*`; * the check is repeated inside the Node script, so neither layer can be bypassed by
    # a doctored `.env.local`. Uses the project's own pinned `mongodb` driver via a throwaway script rather than
    # adding a Python driver dependency for one operation.
    def reset_project_db(self, project_dir: Path, node_bin: str = "node") -> dict:
        """
        Drop a generated app's database so its seed runs again.

        Generated apps guard `ensureSeeded()` with `countDocuments() > 0`, and
        `db_name_for()` is a deterministic function of the project name. So a
        seed corrected after a bad first run can never take effect — the rows
        are already there. Dropping the database is the only way to let the fix
        land.

        Destructive, therefore fenced:
          * refuses when the user configured their own `MONGODB_URI` — that is
            their server, possibly with real data, and AgentForge did not create it;
          * refuses any database whose name is not `agentforge_*`;
          * the check is repeated inside the Node script, so neither layer can
            be bypassed by a doctored `.env.local`.

        Uses the project's own pinned `mongodb` driver via a throwaway script
        rather than adding a Python driver dependency for one operation.
        """
        project_dir = Path(project_dir)
        # From: agents/data/database_helpers.py
        if get_uri_override():
            return {"ok": False, "error": "MONGODB_URI is set in Settings — "
                                          "AgentForge will not touch your own database"}
        env = project_dir / ".env.local"
        if not env.exists():
            return {"ok": False, "error": "no .env.local"}
        try:
            db = ""
            for line in env.read_text(encoding="utf-8").splitlines():
                if line.startswith("MONGODB_DB="):
                    db = line.split("=", 1)[1].strip()
        except OSError as e:
            return {"ok": False, "error": str(e)}

        if not db.startswith("agentforge_"):
            return {"ok": False, "error": f"refusing to drop '{db}' — not an "
                                          f"AgentForge-managed database"}

        script = project_dir / ".agentforge-reset.mjs"
        try:
            script.write_text(self._RESET_SCRIPT, encoding="utf-8")
            r = subprocess.run([node_bin, script.name], cwd=str(project_dir),
                               capture_output=True, text=True, encoding="utf-8",
                               errors="replace", timeout=60)
            out = (r.stdout or "").strip().splitlines()
            data = json.loads(out[-1]) if out else {}
            if r.returncode != 0 or not data.get("ok"):
                return {"ok": False, "error": data.get("error")
                        or (r.stderr or "reset failed")[:200]}
            self._log("WARN", f"   🍃 Dropped database {db} "
                              f"({data.get('dropped', 0)} collections) — the "
                              f"app will re-seed on next load")
            return data
        except Exception as e:
            return {"ok": False, "error": str(e)}
        finally:
            script.unlink(missing_ok=True)

    # Download the binary without starting it — the Settings button.
    def prefetch(self) -> bool:
        """Download the binary without starting it — the Settings button."""
        try:
            # From: agents/data/database_install.py
            if self.find_binary():
                self._log("INFO", "   ✅ mongod is already available")
                return True
            # From: agents/data/database_install.py
            self.binary = self.download_binary()
            return True
        except Exception as e:
            self._log("ERROR", f"   ❌ MongoDB download failed: {e}")
            # From: agents/data/database_helpers.py
            self._status("error", error=str(e))
            return False

    # Returns the MongoDB connection URI that should be used for this project.
    def uri_for(self, project: str) -> str:
        """Return the MongoDB connection URI that should be used for this project."""
        # From: agents/data/database_helpers.py
        override = get_uri_override()
        if override:
            return override
        # From: agents/data/database_helpers.py
        return f"mongodb://127.0.0.1:{self.port}/{db_name_for(project)}"

    # Returns a readable snapshot of the managed MongoDB runtime state.
    def status(self) -> dict:
        """Return a readable snapshot of the managed MongoDB runtime state."""
        # From: agents/data/database_install.py
        binary = self.binary or self.find_binary()
        # From: agents/data/database_helpers.py
        return {
            "available": self.available,
            "running": self.is_running_now(),

            "external": self.adopted,
            "override": bool(get_uri_override()),
            "ours": bool(self.proc and self.proc.poll() is None),
            "downloaded": bool(binary),
            "binary": str(binary) if binary else "",
            "version": self.version or "",
            "port": self.port,
            "reason": self.reason,
        }

    # Checks whether the managed MongoDB process is alive and accepting connections now.
    def is_running_now(self) -> bool:
        """Return whether the managed MongoDB process is alive and accepting connections now."""
        # From: agents/data/database_helpers.py
        return self.is_port_open()


