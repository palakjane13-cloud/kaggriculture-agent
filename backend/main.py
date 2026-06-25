import os
from typing import List, Optional
from contextlib import asynccontextmanager
from fastapi import FastAPI, Depends, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session
from pydantic import BaseModel
import database, agent


@asynccontextmanager
async def lifespan(app: FastAPI):
    database.init_db()
    yield

app = FastAPI(title="AI Todo Agent", version="1.0.0", lifespan=lifespan)

app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"])

class TodoCreateSchema(BaseModel):
    title: str
    description: Optional[str] = ""
    category: Optional[str] = "General"
    priority: Optional[str] = "Medium"
    due_date: Optional[str] = ""

class TodoUpdateSchema(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    category: Optional[str] = None
    priority: Optional[str] = None
    due_date: Optional[str] = None
    status: Optional[str] = None

class StatusUpdateSchema(BaseModel):
    status: str

class ChatMessageSchema(BaseModel):
    role: str
    content: str

class ChatRequestSchema(BaseModel):
    message: str
    history: List[ChatMessageSchema] = []

@app.get("/api/todos")
def read_todos(status: Optional[str] = None, category: Optional[str] = None, priority: Optional[str] = None, db: Session = Depends(database.get_db)):
    todos = database.get_all_todos(db, status, category, priority)
    return [todo.to_dict() for todo in todos]

@app.post("/api/todos", status_code=status.HTTP_201_CREATED)
def create_todo(todo: TodoCreateSchema, db: Session = Depends(database.get_db)):
    if not todo.title.strip():
        raise HTTPException(status_code=400, detail="Title cannot be empty")
    new_todo = database.create_todo(db=db, title=todo.title, description=todo.description, category=todo.category, priority=todo.priority, due_date=todo.due_date)
    return new_todo.to_dict()

@app.put("/api/todos/{todo_id}/status")
def update_todo_status_endpoint(todo_id: int, payload: StatusUpdateSchema, db: Session = Depends(database.get_db)):
    if payload.status not in ["pending", "completed"]:
        raise HTTPException(status_code=400, detail="Status must be 'pending' or 'completed'")
    updated = database.update_todo_status(db, todo_id, payload.status)
    if not updated:
        raise HTTPException(status_code=404, detail=f"Todo item with ID {todo_id} not found")
    return updated.to_dict()

@app.put("/api/todos/{todo_id}")
def update_todo_details_endpoint(todo_id: int, todo_data: TodoUpdateSchema, db: Session = Depends(database.get_db)):
    updated = database.update_todo_details(db=db, todo_id=todo_id, title=todo_data.title, description=todo_data.description, category=todo_data.category, priority=todo_data.priority, due_date=todo_data.due_date)
    if todo_data.status is not None:
        updated = database.update_todo_status(db, todo_id, todo_data.status)
    if not updated:
        raise HTTPException(status_code=404, detail=f"Todo item with ID {todo_id} not found")
    return updated.to_dict()

@app.delete("/api/todos/{todo_id}")
def delete_todo_endpoint(todo_id: int, db: Session = Depends(database.get_db)):
    success = database.delete_todo(db, todo_id)
    if not success:
        raise HTTPException(status_code=404, detail=f"Todo item with ID {todo_id} not found")
    return {"message": f"Todo item {todo_id} deleted successfully"}

@app.post("/api/chat")
def chat_with_agent(payload: ChatRequestSchema, db: Session = Depends(database.get_db)):
    if not payload.message.strip():
        raise HTTPException(status_code=400, detail="Message cannot be empty")
    history_dicts = [{"role": msg.role, "content": msg.content} for msg in payload.history]
    agent_response = agent.run_agent_chat(prompt=payload.message, history=history_dicts, db_session=db)
    todos = database.get_all_todos(db)
    return {"response": agent_response, "todos": [t.to_dict() for t in todos]}

# Resolve frontend path relative to this file
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
FRONTEND_DIR = os.path.abspath(os.path.join(CURRENT_DIR, "..", "frontend"))

frontend_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "frontend")
app.mount("/static", StaticFiles(directory=frontend_path), name="static")

@app.get("/")
def read_index():
    index_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "frontend", "index.html")
    if os.path.exists(index_path):
        return FileResponse(index_path)
    return {"message": f"Frontend index.html is missing at {index_path}."}