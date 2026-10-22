from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List, Optional
from pydantic import BaseModel
from database import get_db, Session as DbSession, Message as DbMessage
import os
import sys
# Add parent dir to path to allow importing modules from backend root
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from llm_utils import run_llama, parse_llm_response, DynamicTool
from prompts import get_system_prompt
from physics_kernel import get_manifest
import model_provider
from model_provider import to_tool_data

router = APIRouter(prefix="/sessions", tags=["sessions"])

# --- Pydantic Models ---
class MessageSchema(BaseModel):
    role: str
    content: str
    tool_data: Optional[dict] = None

class SessionCreate(BaseModel):
    title: Optional[str] = "New Chat"
    context_type: str = "general" # e.g. "material_selection"

class SessionResponse(BaseModel):
    id: int
    title: str
    context_type: str
    created_at: str
    
    class Config:
        orm_mode = True # Allow ORM objects to be returned

class SessionDetail(SessionResponse):
    messages: List[MessageSchema]

# --- Endpoints ---

@router.post("/", response_model=SessionResponse)
def create_session(session_in: SessionCreate, db: Session = Depends(get_db)):
    """Create a new chat session."""
    new_session = DbSession(
        title=session_in.title,
        context_type=session_in.context_type
    )
    db.add(new_session)
    db.commit()
    db.refresh(new_session)
    return convert_session(new_session)

@router.get("/", response_model=List[SessionResponse])
def list_sessions(db: Session = Depends(get_db)):
    """List all previous sessions."""
    sessions = db.query(DbSession).order_by(DbSession.created_at.desc()).all()
    return [convert_session(s) for s in sessions]

@router.get("/{session_id}", response_model=SessionDetail)
def get_session(session_id: int, db: Session = Depends(get_db)):
    """Get a specific session with history."""
    session = db.query(DbSession).filter(DbSession.id == session_id).first()
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    
    messages = [
        MessageSchema(
            role=m.role, 
            content=m.content, 
            tool_data=m.tool_data
        ) for m in session.messages
    ]
    
    sess_dict = convert_session(session).dict()
    sess_dict["messages"] = messages
    return sess_dict

class SessionUpdate(BaseModel):
    title: str

@router.put("/{session_id}", response_model=SessionResponse)
def update_session(session_id: int, update: SessionUpdate, db: Session = Depends(get_db)):
    """Rename a session."""
    session = db.query(DbSession).filter(DbSession.id == session_id).first()
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    
    session.title = update.title
    session.is_custom_title = True
    db.commit()
    db.refresh(session)
    return convert_session(session)

@router.delete("/{session_id}")
def delete_session(session_id: int, db: Session = Depends(get_db)):
    session = db.query(DbSession).filter(DbSession.id == session_id).first()
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    
    db.delete(session)
    db.commit()
    return {"status": "deleted"}

def convert_session(db_obj):
    return SessionResponse(
        id=db_obj.id,
        title=db_obj.title,
        context_type=db_obj.context_type,
        created_at=str(db_obj.created_at)
    )

class ChatRequest(BaseModel):
    message: str
    tier: str = "efficient" # "efficient" or "deep"
    user_profile: Optional[dict] = None


from fastapi.responses import StreamingResponse
import json

@router.post("/{session_id}/chat")
async def chat_in_session(session_id: int, request: ChatRequest, db: Session = Depends(get_db)):
    # 1. Fetch Session
    session = db.query(DbSession).filter(DbSession.id == session_id).first()
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    
    # 2. Save User Message
    user_msg = DbMessage(session_id=session_id, role="user", content=request.message)
    db.add(user_msg)
    db.commit()
    
    # 3. Construct Prompt (Logic unchanged)
    # 3. Construct Prompt (Logic unchanged)
    manifest = get_manifest()
    manifest_str = str(manifest)
    system_prompt = get_system_prompt(request.tier, request.user_profile, physics_manifest=manifest_str)
    if session.context_type and session.context_type != "general":
         context_instruction = f"\n\nFOCUS CONTEXT: You are assisting with {session.context_type}. Focus all answers on this domain."
         system_prompt += context_instruction

    prompt_text = f"<|begin_of_text|><|start_header_id|>system<|end_header_id|>\n\n{system_prompt}<|eot_id|>"
    
    db.refresh(session)
    history = session.messages
    for msg in history:
        # Avoid duplicate user message if it's already in history (it should be)
        prompt_text += f"<|start_header_id|>{msg.role}<|end_header_id|>\n\n{msg.content}<|eot_id|>"
    prompt_text += "<|start_header_id|>assistant<|end_header_id|>\n\n"

    # Role-based history for the structured (OpenAI) path.
    conv_messages = [{"role": m.role, "content": m.content or ""} for m in history]

    # 4. Stream Generator
    async def generate_stream():
        if not os.getenv("REPLICATE_API_TOKEN") or not os.getenv("OPENAI_API_KEY"):
            from dotenv import load_dotenv
            load_dotenv()

        content = ""
        ui_spec = None
        suggested_title = None

        try:
            if model_provider.use_demo():
                # Offline deterministic provider (default): no external LLM.
                result = model_provider.generate_demo(conv_messages)
                content = result["narration"]
                ui_spec = result["ui_spec"]
                yield f"data: {json.dumps({'type': 'token', 'content': content})}\n\n"
            elif model_provider.supports_structured():
                # Reliable path: validated UISpec, no JSON scraping.
                result = model_provider.generate_structured(
                    conv_messages, system_prompt, request.tier
                )
                content = result["narration"]
                ui_spec = result["ui_spec"]
                # Emit narration in one event (structured path is non-streaming).
                yield f"data: {json.dumps({'type': 'token', 'content': content})}\n\n"
            else:
                # Fallback: Replicate Llama streaming + validate extracted JSON.
                model_id = "meta/meta-llama-3-70b-instruct" if request.tier == "deep" else "meta/meta-llama-3-8b-instruct"
                temp = 0.7 if request.tier == "deep" else 0.6
                full_response = ""
                for chunk in run_llama(prompt_text, model_id, temp):
                    full_response += chunk
                    yield f"data: {json.dumps({'type': 'token', 'content': chunk})}\n\n"

                content, _legacy_tool, suggested_title = parse_llm_response(full_response)
                ui_spec = model_provider.extract_ui_spec_from_text(full_response)
                if ui_spec:
                    yield f"data: {json.dumps({'type': 'replace_content', 'content': content})}\n\n"

            tool_dict = to_tool_data(ui_spec) if ui_spec else None
            if tool_dict:
                yield f"data: {json.dumps({'type': 'tool', 'data': tool_dict})}\n\n"

            # Persist assistant message.
            db.add(DbMessage(
                session_id=session_id,
                role="assistant",
                content=content or "",
                tool_data=tool_dict,
            ))
            if suggested_title and not session.is_custom_title:
                sess = db.query(DbSession).filter(DbSession.id == session_id).first()
                if sess:
                    sess.title = suggested_title
            db.commit()

        except Exception as e:
            print(f"Stream Error: {e}")
            yield f"data: {json.dumps({'type': 'error', 'content': str(e)})}\n\n"

    return StreamingResponse(generate_stream(), media_type="text/event-stream")

