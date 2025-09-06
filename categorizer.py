import json
import re
from pathlib import Path

DEFAULT_RULES = {
    "categories": [
        {"name": "Airport", "patterns": ["-airport-", "airport-"]},
        {"name": "Aircraft", "patterns": ["-aircraft-"]},
        {"name": "Livery", "patterns": ["-livery-"]},
        {"name": "Scenery", "patterns": ["scenery", "cityscape", "landmarks"]},
        {"name": "Library", "patterns": ["commonlibrary", "modellib", "material-lib", "-library-", "-lib", "lib-"]},
        {"name": "Missions", "patterns": ["activities", "challenges", "mission", "training", "discovery", "travelbook"]},
        {"name": "Utilities", "patterns": ["jetways", "toolbar", "gsx", "flow"]}
    ],
    "defaultCategory": "Other"
}

def load_rules(rules_path: Path) -> dict:
    if rules_path.exists():
        with rules_path.open("r", encoding="utf-8") as f:
            return json.load(f)
    return DEFAULT_RULES

def save_rules(rules_path: Path, rules: dict):
    with rules_path.open("w", encoding="utf-8") as f:
        json.dump(rules, f, indent=2)

def categorize(name: str, rules: dict) -> str:
    lname = name.lower()
    for cat in rules.get("categories", []):
        for pat in cat.get("patterns", []):
            if pat in lname:
                return cat["name"]
    return rules.get("defaultCategory", "Other")

def derive_source_and_sim(name: str):
    # Returns (source, sim)
    if name.startswith("communityfs24-"):
        return "community", "fs24"
    if name.startswith("communityfs20-"):
        return "community", "fs20"
    if name.startswith("fs24-"):
        return "official", "fs24"
    if name.startswith("fs20-"):
        return "official", "fs20"
    # Fallback guesses
    if name.startswith("community"):
        return "community", "fs24"
    return "official", "fs24"

def derive_vendor(name: str) -> str:
    # Pull vendor-ish chunk after prefix
    base = name
    for p in ["communityfs24-", "communityfs20-", "fs24-", "fs20-"]:
        if base.startswith(p):
            base = base[len(p):]
            break
    # heuristic: vendor is first token before next '-'
    vendor = base.split("-")[0]
    return vendor.lower()
