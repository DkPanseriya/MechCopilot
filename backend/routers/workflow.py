from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Dict, Any, List, Optional
from physics_kernel import RELATIONS, get_manifest

router = APIRouter(prefix="/workflow", tags=["workflow"])

class StepExecutionRequest(BaseModel):
    relation_name: str
    target_var: str
    inputs: Dict[str, Any] # Can be float or {"value": 1.0, "unit": "mm"}
    target_unit: Optional[str] = None

class StepResponse(BaseModel):
    result: float
    unit: str

@router.get("/manifest")
def get_workflow_manifest():
    """
    Returns the list of available physics relations for the LLM.
    """
    return get_manifest()

@router.post("/step")
def execute_step(request: StepExecutionRequest):
    """
    Executes a single step of a workflow.
    """
    if request.relation_name not in RELATIONS:
        raise HTTPException(status_code=404, detail=f"Relation '{request.relation_name}' not found")
        
    relation = RELATIONS[request.relation_name]

    try:
        # Kernel returns {value, unit, si_value, si_unit} with correct units.
        result = relation.solve(request.inputs, request.target_var, request.target_unit)
        return {
            "result": result["value"],
            "unit": result["unit"],
            "si_value": result["si_value"],
            "si_unit": result["si_unit"],
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
