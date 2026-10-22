import os
import sys
import json
from fastapi import APIRouter
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from typing import List, Optional, Literal, Dict, Any
from dotenv import load_dotenv

# --- FIX: Ensure current directory is in path for imports ---
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from prompts import get_system_prompt
from llm_utils import run_llama, parse_llm_response, DynamicTool
from calculations import perform_calculation
from physics_kernel import get_manifest

# Load environment variables
load_dotenv()

router = APIRouter()

# --- Models ---

class ChatMessage(BaseModel):
    role: Literal["user", "assistant", "system"]
    content: Optional[str] = ""

class ChatRequest(BaseModel):
    messages: List[ChatMessage]
    tier: Literal["efficient", "deep"] = "efficient"
    user_profile: Optional[Dict[str, Any]] = None
    agent_role: str = "orchestrator"

class ChatResponse(BaseModel):
    message: ChatMessage
    tool: Optional[DynamicTool] = None

# --- Logic ---


from fastapi.responses import StreamingResponse

@router.post("/chat")
async def chat_endpoint(request: ChatRequest):
    """
    Replicate-Only Chat Endpoint (Streaming).
    Efficient -> Llama 3 8B
    Deep -> Llama 3 70B
    """
    
    if not os.getenv("REPLICATE_API_TOKEN"):
         # Return error as stream? Or just standard error?
         # Frontend expects stream or error.
         # Let's return a JSON error for config missing, or stream it.
         return JSONResponse(status_code=500, content={"message": "REPLICATE_API_TOKEN missing"})

    async def generate_stream():
        # Select System Prompt based on Tier and User Profile
        manifest = get_manifest()
        manifest_str = str(manifest) # Convert list of dicts to string representation for now
        system_prompt = get_system_prompt(request.tier, request.user_profile, request.agent_role, physics_manifest=manifest_str)
        
        # Construct Full Prompt
        full_prompt = f"<|begin_of_text|><|start_header_id|>system<|end_header_id|>\n\n{system_prompt}<|eot_id|>"
        for msg in request.messages:
            full_prompt += f"<|start_header_id|>{msg.role}<|end_header_id|>\n\n{msg.content}<|eot_id|>"
        full_prompt += "<|start_header_id|>assistant<|end_header_id|>\n\n"

        # 1. Select Model & Param
        model_id = "meta/meta-llama-3-70b-instruct" if request.tier == "deep" else "meta/meta-llama-3-8b-instruct"
        temp = 0.7 if request.tier == "deep" else 0.6

        try:
            # 3. Run Replicate (Stream)
            stream = run_llama(full_prompt, model_id, temp)
            
            full_response = ""
            for chunk in stream:
                full_response += chunk
                yield f"data: {json.dumps({'type': 'token', 'content': chunk})}\n\n"
            
            # 4. Parse for Tools (Calculators)
            clean_text, tool_data, _ = parse_llm_response(full_response)
            
            tool_dict = tool_data.dict() if tool_data else None
            
            if tool_dict:
                # If tool found, replace the streaming content with the clean text
                yield f"data: {json.dumps({'type': 'replace_content', 'content': clean_text})}\n\n"
                yield f"data: {json.dumps({'type': 'tool', 'data': tool_dict})}\n\n"

        except Exception as e:
            print(f"Stream Error: {e}")
            yield f"data: {json.dumps({'type': 'error', 'content': str(e)})}\n\n"

    return StreamingResponse(generate_stream(), media_type="text/event-stream")



@router.post("/calculate")
async def calculate_endpoint(payload: Dict[str, Any]):
    """Compute a calculator result server-side via the physics kernel.

    Preferred payload (kernel-native, used by the dynamic calculator card):
        {"relation": "axial_stress", "solve_for": "sigma",
         "inputs": {"F": {"value": 100, "unit": "N"}, "A": ...},
         "output_unit": "MPa"}

    Legacy payload (older tool_name-based calls):
        {"tool_name": "Axial Stress", "inputs": {...}}
    """
    from calculations import calculate_relation

    inputs = payload.get("inputs", {})
    relation = payload.get("relation")

    try:
        if relation:
            return calculate_relation(
                relation,
                payload.get("solve_for"),
                inputs,
                payload.get("output_unit"),
            )
        # Fallback: legacy tool_name dispatch.
        return perform_calculation(payload.get("tool_name", ""), inputs)
    except Exception as e:
        return {"error": str(e)}
