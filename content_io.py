import os
import shutil
import tempfile
from datetime import datetime
from pathlib import Path
from typing import List, Tuple
import xml.etree.ElementTree as ET

from models import PackageRow, STATUS_ACTIVATED, STATUS_USERDISABLED, STATUS_SYSTEMDISABLED
from categorizer import categorize, derive_source_and_sim, derive_vendor, load_rules

DEFAULT_2024 = Path(os.getenv("LOCALAPPDATA", "")) / "Packages" / "Microsoft.Limitless_8wekyb3d8bbwe" / "LocalCache" / "Content.xml"

def find_content_xml() -> Path | None:
    if DEFAULT_2024.exists():
        return DEFAULT_2024
    # Fallback: scan Packages for *\LocalCache\Content.xml preferring "Limitless"
    base = Path(os.getenv("LOCALAPPDATA", "")) / "Packages"
    if base.exists():
        candidates = list(base.glob("*/LocalCache/Content.xml"))
        if not candidates:
            return None
        # prefer Limitless (MSFS 2024)
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
        rows.append(PackageRow(
            name=name, status=status, source=src, sim=sim, category=cat,
            vendor=vendor, raw_index=idx
        ))
    return rows, rules

def ensure_backup_dir(xml_path: Path) -> Path:
    bdir = xml_path.parent / "_backup"
    bdir.mkdir(exist_ok=True)
    return bdir

def rotate_backups(bdir: Path, keep: int = 10):
    backups = sorted(bdir.glob("Content_*.xml"))
    while len(backups) > keep:
        old = backups.pop(0)
        old.unlink(missing_ok=True)

def backup_content(xml_path: Path) -> Path:
    bdir = ensure_backup_dir(xml_path)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    dst = bdir / f"Content_{ts}.xml"
    shutil.copy2(xml_path, dst)
    rotate_backups(bdir)
    return dst

def save_packages(xml_path: Path, all_rows: List[PackageRow]):
    # Read and rewrite only active attribute, preserving order and other formatting as much as ElementTree allows.
    tree = ET.parse(xml_path)
    root = tree.getroot()
    # Map name -> status for quick lookup
    status_map = {r.name: r.status for r in all_rows}
    for el in root.findall("./Package"):
        name = el.get("name", "").strip()
        if name in status_map:
            el.set("active", status_map[name])

    # Atomic write
    tmp_fd, tmp_path = tempfile.mkstemp(prefix="Content_", suffix=".xml", dir=str(xml_path.parent))
    os.close(tmp_fd)
    tree.write(tmp_path, encoding="utf-8", xml_declaration=False)

    # Replace original
    os.replace(tmp_path, xml_path)
