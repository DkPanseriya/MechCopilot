from sqlalchemy import create_engine, Column, Integer, String, Text, DateTime, ForeignKey, JSON, Boolean
from sqlalchemy.orm import sessionmaker, declarative_base, relationship
from datetime import datetime
import os

# Ensure DB is created in the backend directory or project root
db_path = os.path.join(os.path.dirname(__file__), "mech_copilot.db")
DATABASE_URL = f"sqlite:///{db_path}"

engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()

class Session(Base):
    __tablename__ = "sessions"
    id = Column(Integer, primary_key=True, index=True)
    title = Column(String, default="New Chat")
    created_at = Column(DateTime, default=datetime.utcnow)
    context_type = Column(String, default="general") # e.g. "material_selection", "stress_analysis"
    is_custom_title = Column(Boolean, default=False)
    
    messages = relationship("Message", back_populates="session", cascade="all, delete-orphan")

class Message(Base):
    __tablename__ = "messages"
    id = Column(Integer, primary_key=True, index=True)
    session_id = Column(Integer, ForeignKey("sessions.id"))
    role = Column(String) # user, assistant, system
    content = Column(Text)
    tool_data = Column(JSON, nullable=True) # Store tool calls/outputs
    created_at = Column(DateTime, default=datetime.utcnow)
    
    session = relationship("Session", back_populates="messages")

def init_db():
    Base.metadata.create_all(bind=engine)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
