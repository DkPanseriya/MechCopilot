"""Calculator library API: catalog, definitions and runs."""
import traceback
from typing import Any, Dict

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from engineering.core import UNIT_CHOICES, CalcError, run_calculator, to_canonical
from engineering.registry import CATALOG, CATEGORY_ORDER, ordered

router = APIRouter(prefix="/calculators", tags=["calculators"])


def _with_factors():
    """Unit choices plus linear conversion to canonical: canon = v * factor + offset."""
    out = {}
    for dim, choices in UNIT_CHOICES.items():
        rows = []
        for c in choices:
            if dim == "dimensionless":
                f, o = 1.0, 0.0
            else:
                o = to_canonical(0.0, c["value"], dim)
                f = to_canonical(1.0, c["value"], dim) - o
            rows.append({**c, "factor": f, "offset": o})
        out[dim] = rows
    return out


UNITS = _with_factors()


class RunRequest(BaseModel):
    inputs: Dict[str, Any] = {}


@router.get("")
@router.get("/")
def list_calculators():
    calcs = ordered()
    present = []
    for c in calcs:
        if c.category not in present:
            present.append(c.category)
    return {
        "unit_choices": UNITS,
        "categories": present,
        "category_order": CATEGORY_ORDER,
        "calculators": [c.to_dict() for c in calcs],
    }


@router.get("/{calc_id}")
def get_calculator(calc_id: str):
    calc = CATALOG.get(calc_id)
    if not calc:
        raise HTTPException(404, f"Unknown calculator '{calc_id}'")
    return {"unit_choices": UNITS, "calculator": calc.to_dict()}


@router.post("/{calc_id}/run")
def run(calc_id: str, req: RunRequest):
    calc = CATALOG.get(calc_id)
    if not calc:
        raise HTTPException(404, f"Unknown calculator '{calc_id}'")
    try:
        return run_calculator(calc, req.inputs)
    except CalcError as e:
        raise HTTPException(422, str(e))
    except ZeroDivisionError:
        raise HTTPException(422, "Division by zero — check that no required input is zero.")
    except Exception as e:  # surface, don't hide, unexpected failures
        traceback.print_exc()
        raise HTTPException(500, f"{type(e).__name__}: {e}")
