from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from dotenv import load_dotenv
import os
from groq import Groq
import json

load_dotenv()

if not os.getenv("GROQ_API_KEY"):
    pass # Client will check or it might be set via env var automatically. But good to check.
    # Actually Groq() checks it. 

client = Groq()
MODEL = "llama-3.3-70b-versatile"

class ProcessRequest(BaseModel):
    text: str
    current_time: str
    timezone: str | None = None

class TaskParams(BaseModel):
    iso_datetime: str
    text: str

class TaskResponse(BaseModel):
    task: str  # "notify" or "unknown"
    params: TaskParams | None = None
    error_message: str | None = None

app = FastAPI()

SYSTEM_PROMPT = """
You are an intelligent assistant that analyzes user requests in Russian to schedule notifications.
Your goal is to extract the user's intent, the desired time for the notification, and the notification text itself.

**Instructions:**
1.  Analyze the user's `text`, their `timezone`, and the `current_time` (in UTC).
2.  Determine the target notification time. All calculated times must be in UTC and formatted as an ISO 8601 string (YYYY-MM-DDTHH:MM:SS).
3.  **Default Time:** If the user's request is clearly a reminder but does not specify a time (e.g., "напомни позвонить маме"), assume a default delay of **5 minutes** from the `current_time`.
4.  **Future Scheduling:** If a user specifies a date (e.g., "3 августа") that is in the past for the current year, schedule it for the same date next year. All reminders must be for a future time.
5.  **Reminder Text:** Transform the user's request into a concise and clear reminder text. The tone should be a direct command or a simple statement.
    - "напомни позвонить маме" -> "Позвони маме"
    - "напомни мне выключить суп через час" -> "Выключи суп"
    - "купить молоко" -> "Купи молоко"
6.  **Unclear Requests:** If the request is ambiguous, not a scheduling request, or lacks a clear action, you must return an error.
7.  **Output Format:**
    - On success, return a JSON object: `{"iso_datetime": "...", "text": "..."}`
    - On failure (unclear request, past time, etc.), return: `{"error": "unknown_request"}`

**Examples:**
- User: "Напомни мне завтра в 9 утра сходить в магазин" (Timezone: Europe/Moscow, Current: 2025-12-17T22:00:00)
- Response: `{"iso_datetime": "2025-12-18T06:00:00", "text": "Сходи в магазин"}`

- User: "напомни через 2.5 часа проверить почту" (Current: 2025-12-17T12:00:00)
- Response: `{"iso_datetime": "2025-12-17T14:30:00", "text": "Проверь почту"}`

- User: "позвонить в сервис" (Current: 2025-12-17T10:00:00)
- Response: `{"iso_datetime": "2025-12-17T10:05:00", "text": "Позвони в сервис"}`

- User: "Приветик"
- Response: `{"error": "unknown_request"}`

- User: "напомни вчера"
- Response: `{"error": "unknown_request"}`

Respond ONLY with a single, valid JSON object. Do not add any extra text or formatting like ` ```json `.
"""

@app.post("/process", response_model=TaskResponse)
async def process_text(request: ProcessRequest):
    print(f"DEBUG: Input text: '{request.text}'")
    user_prompt = f"""
    User Request: "{request.text}"
    User Timezone: "{request.timezone or 'UTC'}"
    Current Time (UTC): "{request.current_time}"
    """
    
    try:
        completion = client.chat.completions.create(
            model=MODEL,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt}
            ],
            response_format={"type": "json_object"},
            temperature=0.1
        )
        
        content = completion.choices[0].message.content
        print(f"DEBUG: LLM Response content: '{content}'") 
        if not content:
             raise ValueError("Empty response from LLM")
             
        cleaned_content = content.replace("```json", "").replace("```", "").strip()
        print(f"DEBUG: Cleaned content: '{cleaned_content}'")
        
        data = json.loads(cleaned_content)
        print(f"DEBUG: Parsed JSON: {data.keys()}")

        if "error" in data:
            msg = str(data['error'])
            print(f"DEBUG: Error in data: {msg}")
            return TaskResponse(task="unknown", error_message=msg)

        if "iso_datetime" in data and "text" in data:
            print("DEBUG: Valid notify task detected")
            task_params = TaskParams(
                iso_datetime=data["iso_datetime"],
                text=data["text"]
            )
            return TaskResponse(task="notify", params=task_params)
        else:
            msg = f"Missing keys. Found: {list(data.keys())}"
            print(f"DEBUG: {msg}")
            return TaskResponse(task="unknown", error_message=msg)

    except (json.JSONDecodeError, Exception) as e:
        print(f"Error processing model response: {e}")
        # In production would log stack trace
        raise HTTPException(status_code=500, detail="Failed to process the request with the language model.")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
