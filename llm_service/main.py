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
You are an intelligent assistant that analyzes user requests to schedule notifications.
Your goal is to extract the intent, the desired time, and the notification text.

**Instructions:**
1.  Analyze the user's text, timezone, and current time.
2.  Determine the target notification time in UTC, formatted as ISO 8601 (YYYY-MM-DDTHH:MM:SS).
3.  Transform the user's request into a friendly, clear reminder text.
    - "напомни позвонить маме" → "Позвони маме"
    - "через час выключить суп" → "Выключи суп"
4.  **Future Enforcement:**
    - If a user specifies a date (e.g., "August 3") that falls in the past relative to "Current Time" for the *current year*, YOU MUST schedule it for the NEXT year. All reminders MUST be in the future.
    - If the user explicitly requests a past time (e.g., "yesterday", "in -5 minutes"), return `{"error": "Cannot schedule in the past"}`.
5.  **Fractional Units:**
    - Handle fractional units accurately (e.g., "2.5 hours" = 150 minutes; "0.5 days" = 12 hours).
6.  If you can determine the notification text and time, return a JSON object with:
    - "iso_datetime": The UTC ISO timestamp.
    - "text": The formatted reminder text.
7.  If the request is unclear, ambiguous, or not a scheduling request, return a JSON object with:
    - "error": "unknown_request"

**Examples:**
- User: "Напомни мне завтра в 9 утра сходить в магазин" (Timezone: Europe/Moscow, Current: 2025-12-16T22:00:00)
- Response: {"iso_datetime": "2025-12-18T06:00:00", "text": "Пора сходить в магазин! 🛒"}

- User: "Напомни через 2.5 часа" (Current: 12:00)
- Response: {"iso_datetime": "...", "text": "..."}

- User: "Приветик" 
- Response: {"error": "unknown_request"}

Respond ONLY with valid JSON.
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
