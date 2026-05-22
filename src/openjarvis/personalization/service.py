import uuid
from typing import Any, Dict, List

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from .models import Profile
from .preferences import get_active_preferences
from .profiles import (
    get_active_profile,
    list_profiles,
    load_profile,
    save_profile,
    set_active_profile_id,
)
from .routines import get_active_routines

router = APIRouter(prefix="/v1/personalization", tags=["Personalization"])


class SwitchProfileRequest(BaseModel):
    profile_id: str


@router.get("/status")
def get_status() -> Dict[str, Any]:
    active = get_active_profile()
    profiles = list_profiles()
    return {
        "status": "ok",
        "active_profile_id": active.id if active else None,
        "profiles_count": len(profiles),
    }


@router.get("/profiles", response_model=List[Profile])
def get_profiles():
    return list_profiles()


@router.post("/profiles", response_model=Profile)
def create_profile(profile: Profile):
    if not profile.id:
        profile.id = str(uuid.uuid4())
    save_profile(profile)
    # If it's the first profile, make it active
    if len(list_profiles()) == 1:
        set_active_profile_id(profile.id)
    return profile


@router.put("/profiles/{profile_id}", response_model=Profile)
def update_profile(profile_id: str, profile: Profile):
    existing = load_profile(profile_id)
    if not existing:
        raise HTTPException(status_code=404, detail="Profile not found")
    profile.id = profile_id  # Ensure ID matches
    save_profile(profile)
    return profile


@router.get("/active", response_model=Profile)
def get_active():
    profile = get_active_profile()
    if not profile:
        raise HTTPException(status_code=404, detail="No active profile set")
    return profile


@router.post("/active")
def set_active(req: SwitchProfileRequest):
    success = set_active_profile_id(req.profile_id)
    if not success:
        raise HTTPException(status_code=404, detail="Profile not found")
    return {"status": "ok", "active_profile_id": req.profile_id}


@router.get("/preferences/summary")
def get_preferences_summary():
    prefs = get_active_preferences()
    routines = get_active_routines()
    return {
        "preferences": prefs.model_dump(),
        "routines": routines.model_dump(),
    }
