from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from dotenv import load_dotenv
import os
import google.generativeai as genai
import json

load_dotenv()

# Configure the generative AI model
api_key = os.getenv("GOOGLE_API_KEY")
if not api_key:
    raise RuntimeError("GOOGLE_API_KEY environment variable is not set.")
genai.configure(api_key=api_key)
model = genai.GenerativeModel('gemini-2.5-flash')

# --- Pydantic Models ---

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

app = FastAPI()

PROMPT_TEMPLATE = """
Analyze the user's request to schedule a notification.
Based on the user's text, their timezone, and the current time, determine the exact date and time for the notification.

**Instructions:**
1.  The user's request is: "{user_text}"
2.  The user's timezone is: "{user_timezone}" (This could be a name like "Europe/Moscow" or an offset like "-3").
3.  The current time is: "{current_time_iso}" (in UTC).
4.  Your primary task is to correctly interpret relative times like "tomorrow", "tonight", or "in 2 hours" from the user's perspective.
5.  Calculate the final target time in UTC, formatted as an ISO 8601 string (YYYY-MM-DDTHH:MM:SS).
6.  If you can determine the notification text and time, respond with a JSON object containing two keys: "iso_datetime" and "text".
7.  If the user's request is unclear, ambiguous, or not a scheduling request, respond with a JSON object containing one key: "error" with a value of "unknown_request".
8.  Respond ONLY with the JSON object. Do not add any explanatory text or markdown formatting.

**Examples:**
- User Request: "Напомни мне завтра в 9 утра сходить в магазин"
- User Timezone: "Europe/Moscow" (UTC+3)
- Current Time (UTC): "2025-12-16T22:00:00"  // Note: This is 01:00 on Dec 17 in Moscow. "Tomorrow" for the user is Dec 18.
- Your JSON Response: {{"iso_datetime": "2025-12-18T06:00:00", "text": "Сходить в магазин"}} // 9 AM in Moscow is 6 AM UTC.

- User Request: "Привет, как дела?"
- User Timezone: "America/New_York"
- Current Time (UTC): "2025-12-16T20:00:00"
- Your JSON Response: {{"error": "unknown_request"}}
"""

@app.post("/process", response_model=TaskResponse)
async def process_text(request: ProcessRequest):
    prompt = PROMPT_TEMPLATE.format(
        user_text=request.text,
        current_time_iso=request.current_time,
        user_timezone=request.timezone or "UTC"
    )

    try:
        response = model.generate_content(prompt)
        # Clean up the response to get raw JSON
        cleaned_response = response.text.strip().replace("```json", "").replace("```", "").strip()
        
        data = json.loads(cleaned_response)

        if "error" in data:
            return TaskResponse(task="unknown", params=None)

        if "iso_datetime" in data and "text" in data:
            task_params = TaskParams(
                iso_datetime=data["iso_datetime"],
                text=data["text"]
            )
            return TaskResponse(task="notify", params=task_params)
        else:
            # The model returned valid JSON, but not in the expected format
            return TaskResponse(task="unknown", params=None)

    except (json.JSONDecodeError, Exception) as e:
        # Handle cases where the model's response is not valid JSON or another error occurs
        print(f"Error processing model response: {e}")
        raise HTTPException(status_code=500, detail="Failed to process the request with the language model.")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
