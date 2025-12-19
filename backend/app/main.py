from fastapi import FastAPI, Depends, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from datetime import datetime, timezone
from typing import Optional, List
import logging
from dotenv import load_dotenv
from sqlalchemy.orm import Session
from . import models, db
from .db import SessionLocal, engine
from .models import TaskStatus
from .utils import format_user_time

load_dotenv()

logging.basicConfig(level=logging.INFO)

models.Base.metadata.create_all(bind=engine)

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class TaskSchedule(BaseModel):
    telegram_id: int
    chat_id: int
    message_id: int
    text: str
    iso_datetime: str
    timezone: str

class TaskResponse(BaseModel):
    id: int
    description: str
    due_date: str
    display_date: str
    status: str
    created_at: str

class StatusUpdate(BaseModel):
    status: str

class TaskUpdate(BaseModel):
    description: Optional[str] = None
    status: Optional[str] = None
    due_date: Optional[str] = None

class ProcessRequest(BaseModel):
    telegram_id: int
    chat_id: int
    message_id: int
    text: str
    timezone: str

def get_db():
    db_session = SessionLocal()
    try:
        yield db_session
    finally:
        db_session.close()

@app.post("/schedule")
async def schedule_task(task: TaskSchedule, db: Session = Depends(get_db)):
    logging.info(f"Received task: {task} for telegram_id: {task.telegram_id}")

    user = db.query(models.User).filter(models.User.telegram_id == task.telegram_id).first()
    if not user:
        user = models.User(telegram_id=task.telegram_id, timezone=task.timezone)
        db.add(user)
        db.commit()
        db.refresh(user)
    elif user.timezone != task.timezone:
        user.timezone = task.timezone
        db.commit()

    try:
        eta = datetime.fromisoformat(task.iso_datetime)
        if eta.tzinfo is None:
            eta = eta.replace(tzinfo=timezone.utc)

        new_task = models.Task(
            user_id=user.id,
            description=task.text,
            due_date=eta,
            message_id=task.message_id,
            chat_id=task.chat_id,
            status=TaskStatus.CREATED,
        )
        db.add(new_task)
        db.commit()
        db.refresh(new_task)
        
        return {"message": "Задача запланирована", "task_id": new_task.id}

    except ValueError:
        logging.error(f"Could not parse ISO datetime: {task.iso_datetime}")
        raise HTTPException(status_code=400, detail="Неверный формат даты.")

@app.post("/process-async")
async def process_async(request: ProcessRequest):
    from .tasks import process_llm_request
    process_llm_request.delay(
        telegram_id=request.telegram_id,
        chat_id=request.chat_id,
        message_id=request.message_id,
        text=request.text,
        timezone_str=request.timezone,
    )
    return {"message": "Запрос принят в обработку"}

@app.get("/api/tasks", response_model=List[TaskResponse])
async def get_tasks(telegram_id: int, db: Session = Depends(get_db)):
    user = db.query(models.User).filter(models.User.telegram_id == telegram_id).first()
    if not user:
        return []
    
    tasks = db.query(models.Task).filter(models.Task.user_id == user.id).order_by(models.Task.due_date.desc()).all()
    
    return [
        TaskResponse(
            id=t.id,
            description=t.description,
            due_date=t.due_date.isoformat() if t.due_date else "",
            display_date=format_user_time(t.due_date, user.timezone) if t.due_date else "",
            status=t.status.value,
            created_at=t.created_at.isoformat() if t.created_at else "",
        )
        for t in tasks
    ]

@app.patch("/api/tasks/{task_id}")
async def update_task(task_id: int, update: TaskUpdate, db: Session = Depends(get_db)):
    task = db.query(models.Task).filter(models.Task.id == task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="Задача не найдена")
    
    if update.description is not None:
        task.description = update.description
    
    if update.status is not None:
        try:
            task.status = TaskStatus(update.status)
        except ValueError:
            raise HTTPException(status_code=400, detail="Неверный статус")
            
    if update.due_date is not None:
        try:
            eta = datetime.fromisoformat(update.due_date)
            if eta.tzinfo is None:
                eta = eta.replace(tzinfo=timezone.utc)
            task.due_date = eta
        except ValueError:
             raise HTTPException(status_code=400, detail="Неверная дата")

    db.commit()
    db.refresh(task)
    
    return {
        "message": "Задача обновлена",
        "task": {
            "id": task.id,
            "description": task.description,
            "status": task.status.value,
            "due_date": task.due_date.isoformat() if task.due_date else None,
            "display_date": format_user_time(task.due_date, task.user.timezone) if task.due_date and task.user else ""
        }
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8001)
