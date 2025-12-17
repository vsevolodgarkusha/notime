from fastapi import FastAPI
from pydantic import BaseModel
from datetime import datetime, timezone
import logging
from dotenv import load_dotenv

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

app = FastAPI()

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

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8001)
