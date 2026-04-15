"""Config API: operating mode management."""

from fastapi import APIRouter
from pydantic import BaseModel

from config import ARRIVAL_THRESHOLDS, DEPARTURE_THRESHOLDS
from api.schemas import ConfigResponse

router = APIRouter()


class ModeUpdate(BaseModel):
    mode: str  # "balanced", "high_precision", "high_recall"


@router.get("/config", response_model=ConfigResponse)
async def get_config():
    """Get current operating configuration."""
    from main import app_state

    mode = app_state.get("mode", "balanced")
    return ConfigResponse(
        mode=mode,
        arrival_threshold=ARRIVAL_THRESHOLDS[mode],
        departure_threshold=DEPARTURE_THRESHOLDS[mode],
    )


@router.post("/config/mode", response_model=ConfigResponse)
async def set_mode(update: ModeUpdate):
    """Set operating mode (balanced, high_precision, high_recall)."""
    from main import app_state

    mode = update.mode.lower()
    if mode not in ARRIVAL_THRESHOLDS:
        valid = list(ARRIVAL_THRESHOLDS.keys())
        raise ValueError(f"Invalid mode '{mode}'. Must be one of {valid}")

    app_state["mode"] = mode

    return ConfigResponse(
        mode=mode,
        arrival_threshold=ARRIVAL_THRESHOLDS[mode],
        departure_threshold=DEPARTURE_THRESHOLDS[mode],
    )
