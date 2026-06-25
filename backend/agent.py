import os
import contextvars
import google.generativeai as genai
from typing import List, Dict, Optional
from sqlalchemy.orm import Session
import database

# Try to load environment variables from .env file
def load_dotenv():
    # .env is located at the project root (one level up from backend/)
    env_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".env"))
    if os.path.exists(env_path):
        try:
            with open(env_path, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith("#") and "=" in line:
                        k, v = line.split("=", 1)
                        os.environ[k.strip()] = v.strip().strip("'").strip('"')
        except Exception as e:
            print(f"Error loading .env file: {e}")

load_dotenv()


# Context variable to hold the active database session for tool functions
db_session_cv = contextvars.ContextVar("db_session")

# Define tools/functions for Gemini
def add_todo_tool(
    title: str,
    description: str = "",
    category: str = "General",
    priority: str = "Medium",
    due_date: str = ""
) -> str:
    """Add a new task to the todo list.

    Args:
        title: The title/summary of the task (required).
        description: A description of what the task involves.
        category: The category of the task (e.g. Work, Personal, Shopping, Health, Learning, Finance, Home). If not specified by the user, you MUST infer an appropriate category based on the title and description.
        priority: The priority of the task ('High', 'Medium', 'Low'). If not specified by the user, you MUST automatically decide on an appropriate priority ('High' for urgent/important tasks with tight deadlines, 'Medium' for standard tasks, 'Low' for optional/trivial tasks).
        due_date: Optional due date in YYYY-MM-DD format (if mentioned).
    """
    db = db_session_cv.get()
    todo = database.create_todo(
        db=db,
        title=title,
        description=description,
        category=category,
        priority=priority,
        due_date=due_date
    )
    return f"Successfully added task ID {todo.id}: '{todo.title}' (Category: {todo.category}, Priority: {todo.priority}, Due: {todo.due_date or 'None'})"

def get_todos_tool(
    status: Optional[str] = None,
    category: Optional[str] = None,
    priority: Optional[str] = None
) -> str:
    """Retrieve the list of tasks, optionally filtered by status, category, or priority.

    Args:
        status: Filter by status ('pending' or 'completed').
        category: Filter by category (e.g. Work, Personal, etc.).
        priority: Filter by priority ('High', 'Medium', 'Low').
    """
    db = db_session_cv.get()
    todos = database.get_all_todos(db, status, category, priority)
    if not todos:
        return "No tasks found matching the criteria."

    result = []
    for t in todos:
        status_symbol = "✅" if t.status == "completed" else "⏳"
        due_str = f" | Due: {t.due_date}" if t.due_date else ""
        desc_str = f" ({t.description})" if t.description else ""
        result.append(f"ID: {t.id} | {status_symbol} {t.title}{desc_str} | Category: {t.category} | Priority: {t.priority}{due_str}")
    return "\n".join(result)

def complete_todo_tool(todo_id: int) -> str:
    """Mark a task as completed.

    Args:
        todo_id: The ID of the task to mark as completed (must be an integer).
    """
    db = db_session_cv.get()
    todo = database.update_todo_status(db, todo_id, "completed")
    if todo:
        return f"Successfully completed task #{todo.id}: '{todo.title}'"
    return f"Error: Task with ID {todo_id} not found."

def delete_todo_tool(todo_id: int) -> str:
    """Delete a task from the list.

    Args:
        todo_id: The ID of the task to delete (must be an integer).
    """
    db = db_session_cv.get()
    success = database.delete_todo(db, todo_id)
    if success:
        return f"Successfully deleted task #{todo_id}."
    return f"Error: Task with ID {todo_id} not found."

def update_todo_tool(
    todo_id: int,
    title: Optional[str] = None,
    description: Optional[str] = None,
    category: Optional[str] = None,
    priority: Optional[str] = None,
    due_date: Optional[str] = None,
    status: Optional[str] = None
) -> str:
    """Update details of an existing task.

    Args:
        todo_id: The ID of the task to update.
        title: New title of the task.
        description: New description of the task.
        category: New category.
        priority: New priority ('High', 'Medium', 'Low').
        due_date: New due date in YYYY-MM-DD format.
        status: New status ('pending' or 'completed').
    """
    db = db_session_cv.get()
    if status is not None:
        database.update_todo_status(db, todo_id, status)

    todo = database.update_todo_details(
        db=db,
        todo_id=todo_id,
        title=title,
        description=description,
        category=category,
        priority=priority,
        due_date=due_date
    )
    if todo:
        return f"Successfully updated task #{todo.id}: '{todo.title}' (Category: {todo.category}, Priority: {todo.priority}, Status: {todo.status})"
    return f"Error: Task with ID {todo_id} not found."

# Combine all tools
tools_list = [
    add_todo_tool,
    get_todos_tool,
    complete_todo_tool,
    delete_todo_tool,
    update_todo_tool
]

SYSTEM_INSTRUCTION = """You are a helpful and intelligent AI Todo Assistant.
Your job is to manage the user's tasks using the provided tools.
You can chat in plain English and help the user organize their day.

Key rules:
1. When adding a task, if the user doesn't specify the category or priority, you MUST infer them automatically from the task title/description.
   - For example: "I have to write the report by tonight" -> Category: Work, Priority: High.
   - For example: "Need to buy cookies sometime" -> Category: Shopping, Priority: Low.
2. After invoking any tools, always give the user a clear, friendly summary in plain English explaining what you did, and why you selected specific priorities/categories if you inferred them.
3. If the user asks for a summary or what they should do next, use the list/retrieve tools to check the list, then suggest tasks to focus on (preferring High priority pending tasks).
4. If a tool reports an error (e.g. task not found), report it clearly to the user.
5. Answer queries in clear Markdown format. Keep response concise but informative.
"""

def run_agent_chat(prompt: str, history: List[Dict[str, str]], db_session: Session) -> str:
    """Runs a chat agent step, handling context, API configuration, and automatic function calling."""
    # Set DB session context
    token = db_session_cv.set(db_session)
    try:
        # Dynamically reload from .env in case it was updated
        load_dotenv()
        api_key = os.environ.get("GEMINI_API_KEY", "")
        # Check if API key is empty or placeholder
        if not api_key or "PASTE_YOUR" in api_key:
            return "⚠️ **Gemini API Key is not set or is invalid.** Please set the `GEMINI_API_KEY` environment variable in your terminal/environment before using the chat agent."

        # Configure client
        genai.configure(api_key=api_key)

        # Initialize model
        model = genai.GenerativeModel(
            model_name="gemini-2.5-flash-lite",
            system_instruction=SYSTEM_INSTRUCTION,
            tools=tools_list
        )

        # Format history
        formatted_history = []
        for msg in history:
            role = 'user' if msg.get('role') == 'user' else 'model'
            formatted_history.append({
                'role': role,
                'parts': [msg.get('content', '')]
            })

        # Start chat with automatic function calling enabled
        chat = model.start_chat(history=formatted_history, enable_automatic_function_calling=True)
        response = chat.send_message(prompt)
        return response.text
    except Exception as e:
        return f"⚠️ **An error occurred while communicating with Gemini:**\n\n```\n{str(e)}\n```\n\nPlease check your API key and connection."
    finally:
        # Reset DB session context
        db_session_cv.reset(token)
