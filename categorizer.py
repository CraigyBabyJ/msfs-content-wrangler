import json
import re
from pathlib import Path

DEFAULT_RULES = {
    "categories": [
        {"name": "Airport", "patterns": ["-airport-", "airport-"]},
        {"name": "Aircraft", "patterns": ["-aircraft-"]},
        {"name": "Livery", "patterns": ["-livery-"]},
        {"name": "Scenery", "patterns": ["scenery", "cityscape", "landmarks"]},
        {
            "name": "Library",
            "patterns": [
                "commonlibrary",
                "modellib",
                "material-lib",
                "-library-",
                "-lib",
                "lib-",
            ],
        },
        {
            "name": "Missions",
            "patterns": [
                "activities",
                "challenges",
                "mission",
                "training",
                "discovery",
                "travelbook",
            ],
        },
        {"name": "Utilities", "patterns": ["jetways", "toolbar", "gsx", "flow"]},
    ],
    "defaultCategory": "Other",
}


def load_rules(path: Path) -> dict:
    try:
        if path and Path(path).exists():
            return json.loads(Path(path).read_text(encoding="utf-8"))
    except Exception:
        pass
    return DEFAULT_RULES


def categorize(name: str, rules: dict) -> str:
    n = name.lower()
    for cat in rules.get("categories", []):
        for pat in cat.get("patterns", []):
            if pat in n:
                return cat.get("name", "Other")
    return rules.get("defaultCategory", "Other")


def derive_source_and_sim(name: str) -> tuple[str, str]:
    """
    Heuristic from package name:
    - 'communityfs24-*' => ('community','fs24')
    - 'communityfs20-*' => ('community','fs20')
    - 'fs24-*'         => ('official','fs24')
    - 'fs20-*'         => ('official','fs20')
    - otherwise:
        * if it contains 'fs-base' or looks legacy => assume ('official','fs20')
        * fallback to ('official','fs24')
    """
    n = name.lower()

    if n.startswith("communityfs24-"):
        return "community", "fs24"
    if n.startswith("communityfs20-"):
        return "community", "fs20"
    if n.startswith("fs24-"):
        return "official", "fs24"
    if n.startswith("fs20-"):
        return "official", "fs20"

    # Legacy MSFS 2020 official content typically lacks fs24-/fs20- prefix (e.g., fs-base, asobo-aircraft-...)
    legacy2020_hints = (
        "fs-base",
        "asobo-aircraft",
        "asobo-vcockpits",
        "microsoft-",
        "asobo-",
        "wombi",
    )
    if any(h in n for h in legacy2020_hints):
        return "official", "fs20"

    return "official", "fs24"


def derive_vendor(name: str) -> str:
    # Pull vendor-ish chunk after prefix
    base = name
    for p in ["communityfs24-", "communityfs20-", "fs24-", "fs20-"]:
        if base.startswith(p):
            base = base[len(p) :]
            break
    # heuristic: vendor is first token before next '-'
    vendor = base.split("-")[0]
    return vendor.lower()


def save_rules(path: Path, rules: dict) -> None:
    try:
        path = Path(path)
        if path.parent and not path.parent.exists():
            path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(rules, indent=2), encoding="utf-8")
    except Exception:
        # Swallow errors here; caller can show a dialog if needed
        pass
