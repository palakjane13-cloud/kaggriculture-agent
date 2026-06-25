import datetime
import os
from typing import List, Optional
from sqlalchemy import create_engine, Column, Integer, String, Boolean, DateTime
from sqlalchemy.orm import declarative_base, sessionmaker, Session

CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
DATABASE_URL = f"sqlite:///{os.path.join(CURRENT_DIR, 'todos.db')}"

engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

class TodoItem(Base):
    __tablename__ = "todos"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String, index=True, nullable=False)
    description = Column(String, nullable=True, default="")
    category = Column(String, default="General")
    priority = Column(String, default="Medium")  # High, Medium, Low
    status = Column(String, default="pending")  # pending, completed
    due_date = Column(String, nullable=True, default="")
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

    def to_dict(self):
        return {
            "id": self.id,
            "title": self.title,
            "description": self.description,
            "category": self.category,
            "priority": self.priority,
            "status": self.status,
            "due_date": self.due_date,
            "created_at": self.created_at.isoformat() if self.created_at else None
        }

def init_db():
    Base.metadata.create_all(bind=engine)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# CRUD Helpers
def get_all_todos(db: Session, status: Optional[str] = None, category: Optional[str] = None, priority: Optional[str] = None) -> List[TodoItem]:
    query = db.query(TodoItem)
    if status:
        query = query.filter(TodoItem.status == status)
    if category:
        query = query.filter(TodoItem.category.like(f"%{category}%"))
    if priority:
        query = query.filter(TodoItem.priority == priority)
    return query.order_by(TodoItem.created_at.desc()).all()

def get_todo_by_id(db: Session, todo_id: int) -> Optional[TodoItem]:
    return db.query(TodoItem).filter(TodoItem.id == todo_id).first()

def create_todo(
    db: Session,
    title: str,
    description: str = "",
    category: str = "General",
    priority: str = "Medium",
    due_date: str = ""
) -> TodoItem:
    # Normalize category and priority
    if not category:
        category = "General"
    if not priority or priority not in ["High", "Medium", "Low"]:
        priority = "Medium"
        
    todo = TodoItem(
        title=title,
        description=description,
        category=category,
        priority=priority,
        status="pending",
        due_date=due_date
    )
    db.add(todo)
    db.commit()
    db.refresh(todo)
    return todo

def update_todo_status(db: Session, todo_id: int, status: str) -> Optional[TodoItem]:
    todo = get_todo_by_id(db, todo_id)
    if todo:
        if status in ["pending", "completed"]:
            todo.status = status
            db.commit()
            db.refresh(todo)
    return todo

def update_todo_details(
    db: Session,
    todo_id: int,
    title: Optional[str] = None,
    description: Optional[str] = None,
    category: Optional[str] = None,
    priority: Optional[str] = None,
    due_date: Optional[str] = None
) -> Optional[TodoItem]:
    todo = get_todo_by_id(db, todo_id)
    if todo:
        if title is not None:
            todo.title = title
        if description is not None:
            todo.description = description
        if category is not None:
            todo.category = category
        if priority is not None:
            if priority in ["High", "Medium", "Low"]:
                todo.priority = priority
        if due_date is not None:
            todo.due_date = due_date
        db.commit()
        db.refresh(todo)
    return todo

def delete_todo(db: Session, todo_id: int) -> bool:
    todo = get_todo_by_id(db, todo_id)
    if todo:
        db.delete(todo)
        db.commit()
        return True
    return False
