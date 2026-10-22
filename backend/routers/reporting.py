from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.orm import Session as DBSession
from database import get_db, Session as SessionModel
from services.reporting import generate_markdown_report

router = APIRouter(prefix="/reports", tags=["reporting"])

@router.get("/ping")
def ping_reports():
    return {"status": "pong", "service": "reporting"}

@router.get("/{session_id}")
def get_session_report(session_id: int, db: DBSession = Depends(get_db)):
    print(f"DEBUG: Report requested for Session {session_id}")
    """
    Generates a Markdown report for a specific session.
    """
    session = db.query(SessionModel).filter(SessionModel.id == session_id).first()
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    
    # Convert SQLAlchemy models to list of dicts for the service
    messages = []
    for msg in session.messages:
        messages.append({
            "role": msg.role,
            "content": msg.content,
            "tool_data": msg.tool_data
        })
        
    report_md = generate_markdown_report(session.title, messages)
    
    return {"markdown": report_md, "filename": f"Report_Session_{session_id}.md"}
