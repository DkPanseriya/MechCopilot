"""Compute endpoints: parametric chart sweeps and data-driven selectors."""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Any, Dict, List, Optional, Union

from physics_kernel import RELATIONS
import selector_services as sel

router = APIRouter(tags=["compute"])


# --- chart sweep ----------------------------------------------------------

class SweepRequest(BaseModel):
    relation: str
    solve_for: str
    sweep_var: str
    sweep_min: float
    sweep_max: float
    steps: int = 30
    sweep_unit: Optional[str] = None
    output_unit: Optional[str] = None
    fixed_inputs: Dict[str, Union[float, int, str]] = {}


@router.post("/chart/sweep")
def chart_sweep(req: SweepRequest):
    if req.relation not in RELATIONS:
        raise HTTPException(404, f"Unknown relation '{req.relation}'")
    rel = RELATIONS[req.relation]
    if req.sweep_var not in rel.variables or req.solve_for not in rel.variables:
        raise HTTPException(400, "sweep_var/solve_for must be variables of the relation")

    n = max(2, min(req.steps, 200))
    span = req.sweep_max - req.sweep_min
    points: List[Dict[str, float]] = []
    y_unit = req.output_unit or ""
    for i in range(n):
        x = req.sweep_min + span * i / (n - 1)
        knowns = dict(req.fixed_inputs)
        knowns[req.sweep_var] = {"value": x, "unit": req.sweep_unit} if req.sweep_unit else x
        try:
            res = rel.solve(knowns, req.solve_for, req.output_unit)
            points.append({"x": x, "y": res["value"]})
            y_unit = res["unit"]
        except Exception:
            continue
    return {
        "relation": req.relation,
        "x_label": req.sweep_var, "x_unit": req.sweep_unit or "",
        "y_label": req.solve_for, "y_unit": y_unit,
        "points": points,
    }


# --- selectors ------------------------------------------------------------

class BearingRequest(BaseModel):
    P: float
    speed_rpm: float = 0.0
    bore_min_mm: float = 0.0
    bore_max_mm: Optional[float] = None


@router.post("/selector/bearing")
def selector_bearing(req: BearingRequest):
    return sel.select_bearing(req.P, req.speed_rpm, req.bore_min_mm, req.bore_max_mm)


class FastenerRequest(BaseModel):
    axial_load_N: float
    grade: str = "8.8"


@router.post("/selector/fastener")
def selector_fastener(req: FastenerRequest):
    return sel.select_fastener(req.axial_load_N, req.grade)
