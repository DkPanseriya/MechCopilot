import json
import os
from typing import List, Optional, Dict
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

router = APIRouter(prefix="/materials", tags=["materials"])

class Material(BaseModel):
    id: str
    name: str
    category: str
    sub_category: str
    density: float
    yield_strength: float
    ultimate_strength: float
    elastic_modulus: float
    poisson: Optional[float] = None
    thermal_expansion: Optional[float] = None
    thermal_conductivity: float
    cost_approx_usd_per_kg: float
    description: str
    source_citation: Optional[str] = None

# Load data on startup
DATA_FILE = os.path.join(os.path.dirname(__file__), "..", "data", "materials.json")
MATERIALS_DB: List[Dict] = []

try:
    with open(DATA_FILE, "r") as f:
        MATERIALS_DB = json.load(f)
except FileNotFoundError:
    print(f"WARNING: Materials database not found at {DATA_FILE}")

@router.get("/", response_model=List[Material])
def get_materials(category: Optional[str] = None):
    """
    Get all materials, optionally filtered by category (e.g., 'Metal', 'Plastic').
    """
    if category:
        return [m for m in MATERIALS_DB if m["category"].lower() == category.lower()]
    return MATERIALS_DB

@router.get("/{material_id}", response_model=Material)
def get_material(material_id: str):
    """
    Get a specific material by ID.
    """
    for m in MATERIALS_DB:
        if m["id"] == material_id:
            return m
    raise HTTPException(status_code=404, detail="Material not found")
