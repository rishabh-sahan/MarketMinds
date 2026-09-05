"""Config router — read/write DEFAULT_CONFIG and saved presets."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from backend.database import get_db
from backend.models import SavedConfig
from backend.schemas import ConfigResponse, ConfigUpdate, SavedConfigCreate, SavedConfigResponse

router = APIRouter(prefix="/api/config", tags=["config"])


def _get_current_config() -> dict:
    """Return a JSON-safe copy of DEFAULT_CONFIG."""
    from marketminds.default_config import DEFAULT_CONFIG
    # Filter out non-serializable values
    safe = {}
    for k, v in DEFAULT_CONFIG.items():
        if isinstance(v, (str, int, float, bool, list, dict, type(None))):
            safe[k] = v
    return safe


@router.get("", response_model=ConfigResponse)
def get_config():
    """Return the current DEFAULT_CONFIG."""
    return ConfigResponse(config=_get_current_config())


@router.put("", response_model=ConfigResponse)
def update_config(body: ConfigUpdate):
    """Update DEFAULT_CONFIG in-memory (non-persistent — for current session only)."""
    from marketminds.default_config import DEFAULT_CONFIG
    for key, value in body.config.items():
        if key in DEFAULT_CONFIG:
            DEFAULT_CONFIG[key] = value
    return ConfigResponse(config=_get_current_config())


@router.get("/saved", response_model=list[SavedConfigResponse])
def list_saved_configs(db: Session = Depends(get_db)):
    """List all saved config presets."""
    return db.query(SavedConfig).order_by(SavedConfig.created_at.desc()).all()


@router.post("/saved", response_model=SavedConfigResponse, status_code=201)
def save_config(body: SavedConfigCreate, db: Session = Depends(get_db)):
    """Save a named config preset."""
    existing = db.query(SavedConfig).filter(SavedConfig.name == body.name).first()
    if existing:
        existing.config_json = body.config_json
        db.commit()
        db.refresh(existing)
        return existing

    cfg = SavedConfig(name=body.name, config_json=body.config_json)
    db.add(cfg)
    db.commit()
    db.refresh(cfg)
    return cfg


@router.delete("/saved/{config_id}", status_code=204)
def delete_saved_config(config_id: int, db: Session = Depends(get_db)):
    """Delete a saved config preset."""
    cfg = db.query(SavedConfig).filter(SavedConfig.id == config_id).first()
    if not cfg:
        raise HTTPException(status_code=404, detail="Config not found")
    db.delete(cfg)
    db.commit()
