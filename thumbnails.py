
from __future__ import annotations
from pathlib import Path
import os, json, re, time
from typing import Optional, List, Tuple
from threading import Lock, get_ident

from PySide6.QtCore import QObject, Signal, QRunnable

THUMB_EXTS = (".png", ".jpg", ".jpeg", ".webp")
CACHE_DIRNAME = "cache"
CACHE_FILE = "thumbnails.json"


class ThumbSignals(QObject):
    ready = Signal(str)  # package_name

    def __init__(self):
        super().__init__()


class ThumbJob(QRunnable):
    def __init__(
        self,
        name: str,
        source: str,
        sim: str,
        cache: "ThumbCache",
        signals: ThumbSignals,
    ):
        super().__init__()
        self.name = name
        self.source = source
        self.sim = sim
        self.cache = cache
        self.signals = signals

    def run(self):
        try:
            self.cache.ensure_thumbnail_path(self.name, self.source, self.sim)
        finally:
            self.signals.ready.emit(self.name)


class ThumbCache:
    def __init__(self, content_xml_path: Path, thumb_size=(160, 90)):
        self.content_xml_path = content_xml_path
        self.thumb_size = thumb_size

        self.localcache = self._find_localcache_root(content_xml_path)
        self.installed_root = self._installed_packages_root(self.localcache)
        self.app_dir = Path(__file__).parent
        self.cache_dir = self.app_dir / CACHE_DIRNAME
        self.cache_dir.mkdir(exist_ok=True)
        self.cache_path = self.cache_dir / CACHE_FILE

        if not self.cache_path.exists():
            self.cache_path.write_text("{}", encoding="utf-8")

        self._db = self._load_db()
        self._db_lock = Lock()
        self._last_save = 0.0
        I = None
        self._pending = False

        # FS2020 LocalCache + InstalledPackagesPath (for Official FS2020 tab)
        self.fs20_localcache = self._find_msstore_localcache("Microsoft.FlightSimulator_8wekyb3d8bbwe")
        self.fs20_installed = self._installed_packages_root(self.fs20_localcache) if self.fs20_localcache else None

    # ---------- roots / paths ----------

    def _find_localcache_root(self, p: Path) -> Path:
        for parent in p.parents:
            if parent.name.lower() == "localcache":
                return parent
        return (
            Path(os.getenv("LOCALAPPDATA", ""))
            / "Packages"
            / "Microsoft.Limitless_8wekyb3d8bbwe"
            / "LocalCache"
        )

    def _find_msstore_localcache(self, package_id: str) -> Optional[Path]:
        cand = Path(os.getenv("LOCALAPPDATA", "")) / "Packages" / package_id / "LocalCache"
        return cand if cand.exists() else None

    def _installed_packages_root(self, localcache: Optional[Path]) -> Optional[Path]:
        if not localcache:
            return None
        candidates = [
            localcache / "UserCfg.opt",
            localcache.parent / "LocalCache" / "UserCfg.opt",  # profile subdir case
        ]
        for f in candidates:
            if f.exists():
                try:
                    txt = f.read_text(encoding="utf-8", errors="ignore")
                    m = re.search(r'InstalledPackagesPath\s+"([^"]+)"', txt)
                    if m:
                        path = Path(m.group(1)).expanduser()
                        if path.exists():
                            return path
                except Exception:
                    pass
        p = localcache / "Packages"
        return p if p.exists() else None

    def _official24_roots(self) -> List[Path]:
        return [
            (self.installed_root or Path()) / "Official2024" / "OneStore",
            (self.installed_root or Path()) / "Official" / "OneStore",
            self.localcache / "Packages" / "Official2024" / "OneStore",
            self.localcache / "Packages" / "Official" / "OneStore",
            self.localcache.parent / "LocalState" / "packages" / "Official2024" / "OneStore",
            self.localcache.parent / "LocalState" / "packages" / "Official" / "OneStore",
        ]

    def _official20_roots(self) -> List[Path]:
        roots: List[Path] = []
        roots += [
            (self.installed_root or Path()) / "Official2020" / "OneStore",
            (self.installed_root or Path()) / "Official" / "OneStore",
            self.localcache / "Packages" / "Official2020" / "OneStore",
            self.localcache / "Packages" / "Official" / "OneStore",
            self.localcache.parent / "LocalState" / "packages" / "Official2020" / "OneStore",
            self.localcache.parent / "LocalState" / "packages" / "Official" / "OneStore",
        ]
        if self.fs20_installed:
            roots += [
                self.fs20_installed / "Official2020" / "OneStore",
                self.fs20_installed / "Official" / "OneStore",
            ]
        if self.fs20_localcache:
            roots += [
                self.fs20_localcache / "Packages" / "Official2020" / "OneStore",
                self.fs20_localcache / "Packages" / "Official" / "OneStore",
                self.fs20_localcache.parent / "LocalState" / "packages" / "Official2020" / "OneStore",
                self.fs20_localcache.parent / "LocalState" / "packages" / "Official" / "OneStore",
            ]
        roots += [
            Path(r"C:\XboxGames\Microsoft Flight Simulator\Content\Official2020\OneStore"),
            Path(r"C:\XboxGames\Microsoft Flight Simulator\Content\Official\OneStore"),
            Path(r"C:\XboxGames\Microsoft Flight Simulator Premium Deluxe\Content\Official2020\OneStore"),
            Path(r"C:\XboxGames\Microsoft Flight Simulator Premium Deluxe\Content\Official\OneStore"),
        ]
        return roots

    def _community_roots(self) -> List[Path]:
        return [
            (self.installed_root or Path()) / "Community2024",
            (self.installed_root or Path()) / "Community",
            self.localcache / "Packages" / "Community2024",
            self.localcache / "Packages" / "Community",
            self.localcache.parent / "LocalState" / "packages" / "Community2024",
            self.localcache.parent / "LocalState" / "packages" / "Community",
        ]

    # ---------- cache db ----------

    def _load_db(self) -> dict:
        try:
            return json.loads(self.cache_path.read_text(encoding="utf-8"))
        except Exception:
            return {}

    def _save_db_now(self):
        data = json.dumps(self._db, indent=2)
        with self._db_lock:
            parent = self.cache_path.parent
            tmp = parent / f"{self.cache_path.stem}.{os.getpid()}.{get_ident()}.tmp"
            try:
                with open(tmp, "w", encoding="utf-8") as f:
                    f.write(data)
                    f.flush()
                    os.fsync(f.fileno())
            except Exception:
                return
            try:
                os.replace(tmp, self.cache_path)
            except Exception:
                try:
                    with open(self.cache_path, "w", encoding="utf-8") as f:
                        f.write(data)
                finally:
                    try:
                        tmp.unlink(missing_ok=True)
                    except Exception:
                        pass
            self._last_save = time.time()
            self._pending = False

    def _save_db_throttled(self):
        now = time.time()
        if (now - self._last_save) >= 0.5:
            self._save_db_now()
        else:
            self._pending = True

    # ---------- maintenance API ----------

    def forget(self, name: str):
        """Drop a single mapping so it will be re-scanned next time."""
        try:
            removed = self._db.pop(name, None)
            # clean up any legacy cached png if it exists (map-only usually empty)
            png = self.cache_dir / "thumbs" / f"{name}.png"
            if png.exists():
                try:
                    png.unlink()
                except Exception:
                    pass
            if removed is not None:
                self._save_db_now()
        except Exception:
            pass

    def clear_all(self):
        """Clear the entire thumbnail mapping (and any legacy copied PNGs)."""
        self._db.clear()
        tdir = self.cache_dir / "thumbs"
        if tdir.exists():
            for p in tdir.glob("*.png"):
                try:
                    p.unlink()
                except Exception:
                    pass
        self._save_db_now()

    def force_rescan(self, name: str, source: str, sim: str):
        """Convenience: forget and attempt discovery immediately (returns Path or None)."""
        self.forget(name)
        return self.ensure_thumbnail_path(name, source, sim)

    # ---------- public API ----------

    def ensure_thumbnail_path(
        self, package_name: str, source: str, sim: str
    ) -> Optional[Path]:
        entry = self._db.get(package_name)
        if entry:
            orig = Path(entry.get("path", "")) if entry.get("path") else None
            mtime = float(entry.get("mtime", 0.0))
            if orig and orig.exists() and abs(orig.stat().st_mtime - mtime) < 0.001:
                if self._pending:
                    self._save_db_throttled()
                return None

        try:
            src = self._discover_thumbnail(package_name, source, sim)
        except Exception:
            src = None

        if not src:
            # Persist a stub so we don't keep searching every session
            self._db[package_name] = {
                "path": "",
                "mtime": 0.0,
                "source": "none",
            }
            self._save_db_throttled()
            return None

        self._db[package_name] = {
            "path": str(src),
            "mtime": src.stat().st_mtime,
            "source": (
                "layout.json"
                if (
                    src.name.lower().startswith("thumbnail")
                    or "contentinfo" in str(src).lower()
                )
                else "search"
            ),
        }
        self._save_db_throttled()
        return None  # map-only

    def get_cached_png_if_ready(self, package_name: str):
        # Map-only: never returns a cached PNG
        return None

    def get_paths_if_known(self, name: str) -> Tuple[Optional[Path], Optional[Path]]:
        entry = self._db.get(name) or {}
        orig = Path(entry["path"]) if entry.get("path") else None
        return (orig if (orig and orig.exists()) else None, None)

    def get_scan_status(self, name: str) -> str:
        """
        Returns: 'found' | 'missing' | 'unknown'
        """
        entry = self._db.get(name)
        if not entry:
            return "unknown"
        p = entry.get("path") or ""
        if not p:
            return "missing"
        ap = Path(p)
        return "found" if ap.exists() else "missing"

    # ---------- discovery ----------

    def _discover_thumbnail(
        self, package_name: str, source: str, sim: str
    ) -> Optional[Path]:
        def strip_prefix(name: str) -> str:
            for pref in ("fs24-", "fs20-", "communityfs24-", "communityfs20-"):
                if name.lower().startswith(pref):
                    return name[len(pref) :]
            return name

        folder_name = strip_prefix(package_name)
        base_folder = re.split(r"-livery-", folder_name, flags=re.IGNORECASE)[0]

        if source == "official" and sim == "fs24":
            roots = self._official24_roots()
        elif source == "official" and sim == "fs20":
            roots = self._official20_roots()
        else:
            roots = self._community_roots()

        def tokens(s: str) -> set[str]:
            return set(t for t in re.split(r"[-_\s]+", s.lower()) if t)

        want = tokens(base_folder)

        for root in roots:
            # Try our three exact guesses first
            exacts = [root / base_folder, root / folder_name, root / package_name]
            found_dir = next((c for c in exacts if c.exists()), None)

            # Fuzzy fallback if exact folder not found
            if not found_dir and root.exists():
                try:
                    for d in root.iterdir():
                        if d.is_dir() and want.issubset(tokens(d.name)):
                            found_dir = d
                            break
                except Exception:
                    pass

            if not found_dir:
                continue

            candidate = found_dir

            # 1) layout.json (fast & precise)
            via_layout = self._discover_via_layout(candidate)
            if via_layout:
                return via_layout

            # 2) lightweight fallback: any image under ContentInfo/**
            ci = candidate / "ContentInfo"
            if ci.exists():
                for ext in THUMB_EXTS:
                    imgs = list(ci.rglob(f"*{ext}"))
                    if imgs:
                        return imgs[0]

        return None

    def _discover_via_layout(self, pkg_dir: Path) -> Optional[Path]:
        layout = pkg_dir / "layout.json"
        if not layout.exists():
            return None
        try:
            data = json.loads(layout.read_text(encoding="utf-8", errors="ignore"))
            content = data.get("content") or []
        except Exception:
            return None

        rel_paths: List[str] = []
        for item in content:
            if isinstance(item, dict) and isinstance(item.get("path"), str):
                rel_paths.append(item["path"])
            elif isinstance(item, str):
                rel_paths.append(item)
        if not rel_paths:
            return None

        def is_img(p: str) -> bool:
            p = p.lower()
            return p.endswith(THUMB_EXTS)

        pairs = [(rp, rp.lower()) for rp in rel_paths]

        # Priority: ContentInfo thumbnails → screenshots → any ContentInfo image
        for rp, low in pairs:
            if (
                is_img(low)
                and low.startswith("contentinfo/")
                and "/thumbnail" in low
                and low.rsplit("/", 1)[-1].startswith("thumbnail")
            ):
                ap = (pkg_dir / Path(rp)).resolve()
                if ap.exists():
                    return ap
        for rp, low in pairs:
            if is_img(low) and low.startswith("contentinfo/") and "/screenshot" in low:
                ap = (pkg_dir / Path(rp)).resolve()
                if ap.exists():
                    return ap
        for rp, low in pairs:
            if is_img(low) and low.startswith("contentinfo/"):
                ap = (pkg_dir / Path(rp)).resolve()
                if ap.exists():
                    return ap

        # Aircraft-based thumbnails via layout (kept last)
        for rp, low in pairs:
            if (
                is_img(low)
                and low.startswith("simobjects/airplanes/")
                and "thumbnail" in low
            ):
                ap = (pkg_dir / Path(rp)).resolve()
                if ap.exists():
                    return ap

        return None
