from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List, Optional
from pydantic import BaseModel
from database import get_db, SessionLocal, Session as DbSession, Message as DbMessage
import os
import sys
import traceback
# Add parent dir to path to allow importing modules from backend root
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

router = APIRouter(prefix="/sessions", tags=["sessions"])

# --- Pydantic Models ---
class MessageSchema(BaseModel):
    id: Optional[int] = None
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
            id=m.id,
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
def chat_in_session(session_id: int, request: ChatRequest, db: Session = Depends(get_db)):
    import copilot

    session = db.query(DbSession).filter(DbSession.id == session_id).first()
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    history = [{"role": m.role, "content": m.content or "", "tool_data": m.tool_data}
               for m in session.messages]
    db.add(DbMessage(session_id=session_id, role="user", content=request.message))
    db.commit()
    rename = not session.is_custom_title and (session.title or "") in ("", "New Chat", "New Design Session")

    def sse(event: dict) -> str:
        return f"data: {json.dumps(event)}\n\n"

    # Sync generator: Starlette iterates it in a worker thread, so blocking
    # model calls never stall the event loop.
    def generate_stream():
        final = None
        try:
            for event in copilot.respond(request.message, history, request.tier, request.user_profile):
                if event["type"] == "final":
                    final = event
                    continue
                yield sse(event)
        except Exception as e:  # never leave the client hanging
            traceback.print_exc()
            yield sse({"type": "error", "content": f"{type(e).__name__}: {e}"})

        saved_id = None
        if final is not None:
            store = SessionLocal()
            try:
                reply = DbMessage(session_id=session_id, role="assistant",
                                  content=final["content"], tool_data=final["tool_data"])
                store.add(reply)
                if rename:
                    sess = store.query(DbSession).filter(DbSession.id == session_id).first()
                    title = (final.get("title") or request.message).strip()
                    if sess and title:
                        sess.title = title[:60]
                store.commit()
                saved_id = reply.id
            finally:
                store.close()
        if saved_id is not None:  # lets the client save card edits against this reply
            yield sse({"type": "saved", "id": saved_id})
        yield sse({"type": "done"})

    return StreamingResponse(generate_stream(), media_type="text/event-stream")



class ToolEdit(BaseModel):
    calculator: str
    inputs: dict


@router.patch("/{session_id}/messages/{message_id}/tools/{index}")
def edit_tool(session_id: int, message_id: int, index: int, edit: ToolEdit, db: Session = Depends(get_db)):
    """Store the inputs a user changed in a calculator card under an assistant reply.

    The calculation is re-run here, so the conversation records the server's verdict for the
    edited inputs, never one reported by the client."""
    import copilot

    msg = db.query(DbMessage).filter(DbMessage.id == message_id, DbMessage.session_id == session_id).first()
    tools = list((msg.tool_data or {}).get("tools") or []) if msg else []
    if not msg or not 0 <= index < len(tools) or tools[index].get("calculator") != edit.calculator:
        raise HTTPException(status_code=404, detail="Calculator not found in this message")
    try:
        edited = copilot.edit_summary(tools[index], edit.inputs)
    except copilot.CalcError as e:
        raise HTTPException(status_code=422, detail=str(e))
    tools[index] = {**tools[index], "edited": edited}
    msg.tool_data = {**msg.tool_data, "tools": tools}   # new dict so the JSON column is saved
    db.commit()
    return edited
