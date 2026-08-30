"""Focused install responsibilities for MongoManager."""
# Source: database_helpers.py — imported helper(s) come from this file.
from agents.data.database_helpers import *


class MongoManagerInstallMixin:
    # Previously downloaded binary, else one already installed.
    def find_binary(self) -> Path:
        """Previously downloaded binary, else one already installed."""
        # From: agents/data/database_helpers.py
        local = self.bin_dir / _platform_executable("mongod")
        if local.exists():
            return local
        which = shutil.which("mongod")
        if which:
            return Path(which)
        if sys.platform.startswith("win"):
            for p in sorted(Path("C:/Program Files/MongoDB/Server").glob(
                    "*/bin/mongod.exe"), reverse=True):
                return p
        return None

    # {version, url, kind} for this platform, from the official feed.
    def resolve_download(self) -> dict:
        """{version, url, kind} for this platform, from the official feed."""
        # From: agents/data/database_helpers.py
        arch = _arch()
        # From: agents/data/database_helpers.py
        targets = _targets()
        try:
            r = requests.get(FEED_URL, timeout=30)
            r.raise_for_status()
            feed = r.json()
            versions = [v for v in feed.get("versions", [])
                        if v.get("production_release")
                        and not v.get("release_candidate")]
            for want in targets:
                for v in versions:
                    for dl in v.get("downloads", []):
                        if (dl.get("target") == want and dl.get("arch") == arch
                                and dl.get("edition") == "base"):
                            url = (dl.get("archive") or {}).get("url")
                            if url:
                                return {"version": v.get("version", "?"),
                                        "url": url,
                                        "kind": "zip" if url.endswith(".zip") else "tgz"}
        except Exception as e:
            self._log("WARN", f"   MongoDB version feed unreachable ({e}) — "
                              f"using {FALLBACK_VERSION}")

        for want in targets:
            url = FALLBACK_URLS.get((want, arch))
            if url:
                return {"version": FALLBACK_VERSION, "url": url,
                        "kind": "zip" if url.endswith(".zip") else "tgz"}
        raise RuntimeError(f"No MongoDB build published for {sys.platform}/{arch}")

    # Fetch just `mongod` into `bin/`. Returns its path.
    def download_binary(self) -> Path:
        """Fetch just `mongod` into `bin/`. Returns its path."""
        info = self.resolve_download()
        self.version = info["version"]
        # From: agents/data/database_helpers.py
        target = self.bin_dir / _platform_executable("mongod")
        self.bin_dir.mkdir(parents=True, exist_ok=True)

        self._log("INFO", f"🍃 MongoDB not found — fetching mongod {self.version}")
        # From: agents/data/database_helpers.py
        self._status("downloading", version=self.version, pct=0)

        tmp = target.with_suffix(target.suffix + ".part")
        try:
            if info["kind"] == "zip":
                moved = self._extract_from_zip(info["url"], tmp)
            else:
                moved = self._extract_from_tgz(info["url"], tmp)
            if not moved:
                raise RuntimeError("mongod not found inside the archive")
            tmp.replace(target)
        finally:
            if tmp.exists():
                tmp.unlink(missing_ok=True)

        if not sys.platform.startswith("win"):
            os.chmod(target, 0o755)

        (self.home / "version.json").write_text(
            json.dumps({"version": self.version, "url": info["url"]}, indent=2),
            encoding="utf-8")
        self._log("INFO", f"   ✅ mongod {self.version} installed → {target}")
        return target

    # Sends one MongoDB installation progress update to the configured callback.
    def _progress(self, done: int, total: int, state: str = "downloading"):
        """Send one MongoDB installation progress update to the configured callback."""
        pct = int(done / total * 100) if total else 0
        if pct >= getattr(self, "_last_pct", -5) + 5:
            self._last_pct = pct
            self._log("INFO", f"   🍃 MongoDB {pct}%  "
                              f"({done/1e6:.1f} / {total/1e6:.1f} MB)")
            # From: agents/data/database_helpers.py
            self._status(state, version=self.version, pct=pct)

    # Inflate only `bin/mongod.exe` using HTTP range reads. Falls back to a full streamed download if the server won't
    # do ranges.
    def _extract_from_zip(self, url: str, out_path: Path) -> bool:
        """
        Inflate only `bin/mongod.exe` using HTTP range reads.

        Falls back to a full streamed download if the server won't do ranges.
        """
        self._last_pct = -5
        try:
            # From: agents/data/database_helpers.py
            reader = _RangeReader(url)
        except Exception as e:
            self._log("WARN", f"   Range requests unavailable ({e}) — "
                              f"downloading the full archive")
            return self._extract_from_zip_full(url, out_path)

        with zipfile.ZipFile(reader) as zf:
            member = next((i for i in zf.infolist()
                           if i.filename.replace("\\", "/").endswith("bin/mongod.exe")),
                          None)
            if member is None:
                return False
            total = member.compress_size
            self._log("INFO", f"   🍃 Pulling {total/1e6:.1f} MB of a "
                              f"{reader.size/1e6:.0f} MB archive (symbols skipped)")
            with zf.open(member) as src, open(out_path, "wb") as dst:
                while True:
                    # From: agents/data/database_helpers.py
                    chunk = src.read(1 << 20)
                    if not chunk:
                        break
                    dst.write(chunk)
                    self._progress(min(reader.transferred, total), total)
        return True

    # Extracts the downloaded MongoDB archive into the managed tools folder.
    def _extract_from_zip_full(self, url: str, out_path: Path) -> bool:
        """Extract the downloaded MongoDB archive into the managed tools folder."""
        tmp_zip = self.home / "archive.zip"
        with requests.get(url, stream=True, timeout=180) as r:
            r.raise_for_status()
            total = int(r.headers.get("Content-Length") or 0)
            done = 0
            with open(tmp_zip, "wb") as f:
                for chunk in r.iter_content(1 << 20):
                    f.write(chunk)
                    done += len(chunk)
                    self._progress(done, total)
        try:
            with zipfile.ZipFile(tmp_zip) as zf:
                member = next((i for i in zf.infolist()
                               if i.filename.replace("\\", "/").endswith("bin/mongod.exe")),
                              None)
                if member is None:
                    return False
                with zf.open(member) as src, open(out_path, "wb") as dst:
                    shutil.copyfileobj(src, dst, 1 << 20)
        finally:
            tmp_zip.unlink(missing_ok=True)
        return True

    # Gzip streams aren't seekable — read through and stop at mongod.
    def _extract_from_tgz(self, url: str, out_path: Path) -> bool:
        """Gzip streams aren't seekable — read through and stop at mongod."""
        self._last_pct = -5
        with requests.get(url, stream=True, timeout=180) as r:
            r.raise_for_status()
            total = int(r.headers.get("Content-Length") or 0)
            r.raw.decode_content = False

            counter = {"n": 0}
            outer = r.raw

            class _Counting:
                """
                Plain read()-only wrapper, deliberately NOT an io.RawIOBase.

                Wrapping a RawIOBase subclass in io.BufferedReader would be a
                trap: BufferedReader pulls from the raw stream via readinto(),
                which io.RawIOBase leaves unimplemented, so the very first read
                raises NotImplementedError. tarfile's stream mode only ever
                calls fileobj.read(size), so a bare object is both correct and
                sufficient.
                """

                # Read the requested data without changing it.
                def read(self, n=-1):
                    """Read the requested data without changing it."""
                    # From: agents/data/database_helpers.py
                    data = outer.read(n if n and n > 0 else 1 << 20)
                    counter["n"] += len(data or b"")
                    return data or b""

            with tarfile.open(fileobj=_Counting(), mode="r|gz") as tf:
                for member in tf:
                    self._progress(counter["n"], total)
                    if not member.isfile():
                        continue
                    if not member.name.replace("\\", "/").endswith("bin/mongod"):
                        continue
                    src = tf.extractfile(member)
                    if src is None:
                        return False
                    with src, open(out_path, "wb") as dst:
                        shutil.copyfileobj(src, dst, 1 << 20)
                    return True
        return False


