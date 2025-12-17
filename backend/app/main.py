from fastapi import FastAPI
from pydantic import BaseModel
from datetime import datetime, timezone
import logging
from dotenv import load_dotenv
from fastapi.middleware.cors import CORSMiddleware # Import CORSMiddleware

from .tasks import send_notification

load_dotenv()

logging.basicConfig(level=logging.INFO)

# --- Pydantic Models to match the new task structure ---

class TaskParams(BaseModel):
    iso_datetime: str
    text: str

class Task(BaseModel):
    task: str
    params: TaskParams | None = None

# New Pydantic model for a task item
class TaskItem(BaseModel):
    id: int
    title: str
    completed: bool

app = FastAPI()

# Add CORS middleware for frontend development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], # Allows all origins
    allow_credentials=True,
    allow_methods=["*"], # Allows all methods
    allow_headers=["*"], # Allows all headers
)

@app.post("/schedule")
async def schedule_task(task: Task, chat_id: int):
    logging.info(f"Received task: {task} for chat_id: {chat_id}")
    
    if task.task == "notify" and task.params:
        try:
            # The LLM provides the ETA in ISO format. We parse it and ensure it's timezone-aware (UTC).
            eta = datetime.fromisoformat(task.params.iso_datetime)
            if eta.tzinfo is None:
                eta = eta.replace(tzinfo=timezone.utc)
            
            # Ensure the ETA is in the future by comparing it to the current aware UTC time
            if eta > datetime.now(timezone.utc):
                send_notification.apply_async(args=[chat_id, task.params.text], eta=eta)
                return {"message": "Notification scheduled"}
            else:
                logging.warning(f"Attempted to schedule a task in the past: {eta}")
                return {"message": "Cannot schedule tasks in the past."}

        except ValueError:
            logging.error(f"Could not parse ISO datetime: {task.params.iso_datetime}")
            return {"message": "Invalid datetime format."}
            
    return {"message": "Unknown or invalid task"}

# New endpoint to get a list of tasks
@app.get("/api/tasks", response_model=list[TaskItem])
async def get_tasks():
    # For now, return a hardcoded list of tasks
    # In a real application, this would come from a database
    tasks_list = [
        {"id": 1, "title": "Buy groceries", "completed": False},
        {"id": 2, "title": "Walk the dog", "completed": True},
        {"id": 3, "title": "Finish report", "completed": False},
    ]
    return tasks_list

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8001)
