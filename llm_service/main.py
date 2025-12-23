from fastapi import FastAPI, HTTPException, Depends, Header
from pydantic import BaseModel
from dotenv import load_dotenv
import hmac
import os
from groq import Groq
import json
from typing import Optional

load_dotenv()

LLM_INTERNAL_API_KEY = os.getenv("LLM_INTERNAL_API_KEY")
if not LLM_INTERNAL_API_KEY:
    raise RuntimeError("LLM_INTERNAL_API_KEY environment variable is required")


def verify_llm_api_key(
    authorization: Optional[str] = Header(None, alias="Authorization"),
) -> None:
    if not authorization:
        raise HTTPException(status_code=401, detail="Authorization header required")

    token = authorization
    if token.lower().startswith("bearer "):
        token = token[7:]

    if not hmac.compare_digest(token, LLM_INTERNAL_API_KEY):
        raise HTTPException(status_code=401, detail="Invalid API key")


client = Groq()
MODEL = os.getenv("LLM_MODEL", "llama-3.3-70b-versatile")


class ProcessRequest(BaseModel):
    text: str
    current_time: str
    timezone: Optional[str] = None


class TaskParams(BaseModel):
    iso_datetime: str
    text: str


class TaskResponse(BaseModel):
    task: str
    params: Optional[TaskParams] = None
    error_message: Optional[str] = None


app = FastAPI(title="LLM Service", version="2.0.0")


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
async def process_text(
    request: ProcessRequest,
    _: None = Depends(verify_llm_api_key),
):
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
        if not content:
            raise ValueError("Empty response from LLM")

        cleaned_content = content.replace("```json", "").replace("```", "").strip()
        data = json.loads(cleaned_content)

        if "error" in data:
            return TaskResponse(task="unknown", error_message=str(data['error']))

        if "iso_datetime" in data and "text" in data:
            task_params = TaskParams(
                iso_datetime=data["iso_datetime"],
                text=data["text"]
            )
            return TaskResponse(task="notify", params=task_params)

        return TaskResponse(task="unknown", error_message=f"Missing keys. Found: {list(data.keys())}")

    except json.JSONDecodeError:
        raise HTTPException(status_code=500, detail="Failed to parse LLM response as JSON.")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"LLM error: {str(e)}")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
