import os
import shutil
import tempfile
from pathlib import Path
from typing import List, Tuple, Optional
from dataclasses import dataclass

import xml.etree.ElementTree as ET

from models import (
    PackageRow,
    STATUS_ACTIVATED,
    STATUS_USERDISABLED,
    STATUS_SYSTEMDISABLED,
)
from categorizer import categorize, derive_source_and_sim, derive_vendor, load_rules

LIMITLESS_PKG = "Microsoft.Limitless_8wekyb3d8bbwe"  # FS24 package id
THUMBNAIL_PATTERNS = [
    "thumbnail.jpg",
    "thumbnail.png",
    "screenshot.jpg",
    "screenshot.png",
    "*.jpg",
    "*.png",
]


@dataclass
class ProfileFile:
    path: Path
    is_profile: bool  # True if in a subfolder (likely gamertag)
    name: str  # subfolder name or "LocalCache"
    mtime: float


def localcache_dir() -> Path:
    return (
        Path(os.getenv("LOCALAPPDATA", "")) / "Packages" / LIMITLESS_PKG / "LocalCache"
    )


def list_content_xml_candidates() -> List[ProfileFile]:
    base = localcache_dir()
    if not base.exists():
        return []
    out: List[ProfileFile] = []
    root = base / "Content.xml"
    if root.exists():
        out.append(ProfileFile(root, False, "LocalCache", root.stat().st_mtime))
    for sub in base.iterdir():
        if sub.is_dir():
            f = sub / "Content.xml"
            if f.exists():
                out.append(ProfileFile(f, True, sub.name, f.stat().st_mtime))
    # Prefer profile files, then newest modified
    out.sort(key=lambda p: (p.is_profile, p.mtime), reverse=True)
    return out


def best_content_xml() -> Optional[Path]:
    cands = list_content_xml_candidates()
    return cands[0].path if cands else None


def find_thumbnail(
    package_name: str, package_source: str, content_xml_path: Path
) -> Optional[Path]:
    """Tries to find a thumbnail for a given package."""
    base_path = content_xml_path.parent.parent
    package_folder = base_path / package_source.capitalize() / package_name

    if not package_folder.exists() or not package_folder.is_dir():
        return None

    for pattern in THUMBNAIL_PATTERNS:
        found = list(package_folder.glob(pattern))
        if found:
            found.sort(
                key=lambda p: (
                    p.name.lower() not in ["thumbnail.jpg", "thumbnail.png"],
                    p.stat().st_size,
                )
            )
            return found[0]
    return None


def find_content_xml(custom_path_str: str | None = None) -> Path | None:
    """Finds Content.xml, prioritizing custom path, then FS24 profile or root LocalCache files."""
    if custom_path_str:
        custom_path = Path(custom_path_str)
        if custom_path.exists() and custom_path.is_file():
            return custom_path

    best = best_content_xml()
    if best:
        return best

    # fallback: scan Packages for any Content.xml using old logic
    base = Path(os.getenv("LOCALAPPDATA", "")) / "Packages"
    if base.exists():
        candidates = list(base.glob("*/LocalCache/Content.xml"))
        if not candidates:
            return None
        candidates.sort(key=lambda p: ("Limitless" not in str(p.parent.parent)))
        return candidates[0]
    return None


def load_packages(xml_path: Path, rules_path: Path) -> Tuple[List[PackageRow], dict]:
    rules = load_rules(rules_path)
    tree = ET.parse(xml_path)
    root = tree.getroot()
    rows: List[PackageRow] = []
    for idx, el in enumerate(root.findall("./Package")):
        name = el.get("name", "").strip()
        status = el.get("active", "").strip() or STATUS_ACTIVATED
        src, sim = derive_source_and_sim(name)
        cat = categorize(name, rules)
        vendor = derive_vendor(name)
        thumb_path = find_thumbnail(name, src, xml_path)
        rows.append(
            PackageRow(
                name=name,
                status=status,
                source=src,
                sim=sim,
                category=cat,
                vendor=vendor,
                raw_index=idx,
                thumbnail_path=thumb_path,
            )
        )
    return rows, rules


def backup_content(xml_path: Path) -> Path:
    """Creates a single backup of the file with a `_backup` suffix."""
    dst = xml_path.with_name(f"{xml_path.stem}_backup{xml_path.suffix}")
    shutil.copy2(xml_path, dst)
    return dst


def save_packages(
    xml_path: Path, all_rows: List[PackageRow], clean_legacy_fs20: bool
) -> int:
    """Saves package statuses to Content.xml, optionally stripping legacy mods."""
    tree = ET.parse(xml_path)
    root = tree.getroot()
    removed_count = 0

    # First, remove legacy FS20 community packages if the setting is enabled
    if clean_legacy_fs20:
        packages_to_remove = []
        for el in root.findall("./Package"):
            if el.get("name", "").startswith("communityfs20-"):
                packages_to_remove.append(el)
        if packages_to_remove:
            for el in packages_to_remove:
                root.remove(el)
            removed_count = len(packages_to_remove)

    # Second, update the status of all remaining packages based on the model
    status_map = {r.name: r.status for r in all_rows}
    for el in root.findall("./Package"):
        name = el.get("name", "").strip()
        if name in status_map:
            el.set("active", status_map[name])

    # Atomic write to prevent data loss if the app crashes mid-save
    tmp_fd, tmp_path = tempfile.mkstemp(
        prefix="Content_", suffix=".xml", dir=str(xml_path.parent)
    )
    os.close(tmp_fd)
    tree.write(tmp_path, encoding="utf-8", xml_declaration=False)

    os.replace(tmp_path, xml_path)
    return removed_count
