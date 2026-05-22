import json
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional

from .models import Profile

PROFILES_DIR = Path.home() / ".openjarvis" / "state" / "profiles"
ACTIVE_PROFILE_FILE = Path.home() / ".openjarvis" / "state" / "active_profile.json"


def init_profile_storage():
    """Ensure the profiles storage directory exists."""
    PROFILES_DIR.mkdir(parents=True, exist_ok=True)
    ACTIVE_PROFILE_FILE.parent.mkdir(parents=True, exist_ok=True)


def load_profile(profile_id: str) -> Optional[Profile]:
    """Load a profile by ID."""
    file_path = PROFILES_DIR / f"{profile_id}.json"
    if not file_path.exists():
        return None
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            data = json.load(f)
            return Profile(**data)
    except Exception:
        return None


def save_profile(profile: Profile) -> None:
    """Save a profile to disk."""
    init_profile_storage()
    profile.updated_at = datetime.now(timezone.utc).isoformat()
    file_path = PROFILES_DIR / f"{profile.id}.json"
    with open(file_path, "w", encoding="utf-8") as f:
        f.write(profile.model_dump_json(indent=2))


def list_profiles() -> List[Profile]:
    """List all available profiles."""
    if not PROFILES_DIR.exists():
        return []

    profiles = []
    for file_path in PROFILES_DIR.glob("*.json"):
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                profiles.append(Profile(**data))
        except Exception:
            continue
    return profiles


def get_active_profile_id() -> Optional[str]:
    """Get the active profile ID."""
    if not ACTIVE_PROFILE_FILE.exists():
        return None
    try:
        with open(ACTIVE_PROFILE_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
            return data.get("active_profile_id")
    except Exception:
        return None


def set_active_profile_id(profile_id: str) -> bool:
    """Set the active profile ID."""
    init_profile_storage()
    if not (PROFILES_DIR / f"{profile_id}.json").exists():
        return False
    with open(ACTIVE_PROFILE_FILE, "w", encoding="utf-8") as f:
        json.dump({"active_profile_id": profile_id}, f, indent=2)
    return True


def get_active_profile() -> Optional[Profile]:
    """Get the currently active profile."""
    profile_id = get_active_profile_id()
    if profile_id:
        return load_profile(profile_id)
    return None
