import os
import uuid
import json
import logging
import httpx
import anthropic
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="MediAssist Conversation API")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

claude_client = anthropic.Anthropic()
APPOINTMENTS_API = os.getenv("APPOINTMENTS_API_URL", "http://localhost:8001")
RETRIEVAL_API = os.getenv("RETRIEVAL_API_URL", "http://localhost:8000")

sessions: dict[str, dict] = {}

SYSTEM_PROMPT = """You are MediAssist, an intelligent appointment assistant for City General Hospital. \
You help patients manage their medical appointments and answer questions about hospital services.

You can:
- View a patient's upcoming or all appointments
- Cancel a specific appointment on their behalf
- Answer questions about hospital departments, visiting hours, parking, prescriptions, insurance, and policies
- Guide patients step-by-step through OTP authentication

Authentication rules:
- A patient must authenticate before you can view or cancel their appointments.
- Ask for their email address, call send_otp, then ask for the 6-digit code and call verify_otp.
- Once verify_otp succeeds, you may proceed with their request.

Always be empathetic, professional, and concise — this is a medical context.
Respond in whatever language the patient writes in."""

TOOLS = [
    {
        "name": "send_otp",
        "description": "Send a one-time password to the patient's email to begin identity verification.",
        "input_schema": {
            "type": "object",
            "properties": {
                "email": {"type": "string", "description": "Patient's email address"}
            },
            "required": ["email"],
        },
    },
    {
        "name": "verify_otp",
        "description": "Verify the OTP code the patient received. Returns an auth token on success.",
        "input_schema": {
            "type": "object",
            "properties": {
                "email": {"type": "string"},
                "code": {"type": "string", "description": "6-digit OTP code entered by the patient"},
            },
            "required": ["email", "code"],
        },
    },
    {
        "name": "get_appointments",
        "description": "Retrieve the authenticated patient's hospital appointments.",
        "input_schema": {
            "type": "object",
            "properties": {
                "upcoming_only": {
                    "type": "boolean",
                    "description": "If true, return only future (not past) appointments",
                }
            },
            "required": [],
        },
    },
    {
        "name": "cancel_appointment",
        "description": "Cancel a specific appointment by ID on behalf of the authenticated patient.",
        "input_schema": {
            "type": "object",
            "properties": {
                "appointmentId": {"type": "string", "description": "The appointment ID to cancel"}
            },
            "required": ["appointmentId"],
        },
    },
    {
        "name": "search_faq",
        "description": (
            "Search the hospital knowledge base for information about departments, visiting hours, "
            "parking, prescriptions, insurance, emergency contacts, and appointment policies."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "The patient's question"}
            },
            "required": ["query"],
        },
    },
]


def _safe_json(resp, url: str) -> dict:
    logger.info("Tool response | url=%s status=%s content=%r", url, resp.status_code, resp.content[:300])
    if not resp.content:
        logger.warning("Empty response body | url=%s status=%s", url, resp.status_code)
        return {"error": f"Empty response from service (HTTP {resp.status_code})"}
    if resp.status_code >= 400:
        try:
            detail = resp.json()
        except Exception:
            detail = resp.text
        logger.warning("Error response | url=%s status=%s detail=%s", url, resp.status_code, detail)
        return {"error": f"HTTP {resp.status_code}: {detail}"}
    try:
        return resp.json()
    except Exception as exc:
        logger.error("JSONDecodeError | url=%s error=%s content=%r", url, exc, resp.content)
        return {"error": f"Could not parse service response: {exc}"}


def execute_tool(name: str, tool_input: dict, session: dict) -> str:
    token = session.get("auth_token")
    auth_headers = {"Authorization": f"Bearer {token}"} if token else {}

    try:
        if name == "send_otp":
            url = f"{APPOINTMENTS_API}/auth/send-code"
            logger.info("Calling tool=%s url=%s", name, url)
            resp = httpx.post(url, json={"email": tool_input["email"]}, timeout=10)
            session["pending_email"] = tool_input["email"]
            return json.dumps(_safe_json(resp, url))

        if name == "verify_otp":
            url = f"{APPOINTMENTS_API}/auth/verify-code"
            logger.info("Calling tool=%s url=%s", name, url)
            resp = httpx.post(url, json={"email": tool_input["email"], "code": tool_input["code"]}, timeout=10)
            data = _safe_json(resp, url)
            if data.get("success") and data.get("token"):
                session["auth_token"] = data["token"]
            return json.dumps(data)

        if name == "get_appointments":
            if not token:
                return json.dumps({"error": "Not authenticated. Please verify your identity first."})
            upcoming = 1 if tool_input.get("upcoming_only") else 0
            url = f"{APPOINTMENTS_API}/appointments"
            logger.info("Calling tool=%s url=%s upcoming=%s", name, url, upcoming)
            resp = httpx.get(url, params={"upcoming": upcoming}, headers=auth_headers, timeout=10)
            return json.dumps(_safe_json(resp, url))

        if name == "cancel_appointment":
            if not token:
                return json.dumps({"error": "Not authenticated. Please verify your identity first."})
            url = f"{APPOINTMENTS_API}/cancel-appointment"
            logger.info("Calling tool=%s url=%s appointmentId=%s", name, url, tool_input.get("appointmentId"))
            resp = httpx.post(url, json={"appointmentId": tool_input["appointmentId"]}, headers=auth_headers, timeout=10)
            return json.dumps(_safe_json(resp, url))

        if name == "search_faq":
            url = f"{RETRIEVAL_API}/answer"
            logger.info("Calling tool=%s url=%s query=%r", name, url, tool_input.get("query"))
            resp = httpx.post(url, json={"query": tool_input["query"]}, timeout=30)
            data = _safe_json(resp, url)
            if "error" in data:
                return json.dumps(data)
            return data.get("answer", "No information found for that query.")

        logger.warning("Unknown tool requested: %s", name)
        return json.dumps({"error": f"Unknown tool: {name}"})

    except httpx.RequestError as exc:
        logger.error("Network error in tool=%s: %s", name, exc)
        return json.dumps({"error": f"Service unavailable: {exc}"})
    except Exception as exc:
        logger.error("Unexpected error in tool=%s: %s", name, exc, exc_info=True)
        return json.dumps({"error": f"Unexpected error executing tool: {exc}"})


def _serialize_content(content):
    """Convert SDK content blocks to plain dicts for session storage."""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        out = []
        for block in content:
            if isinstance(block, dict):
                out.append(block)
            elif hasattr(block, "type"):
                if block.type == "text":
                    out.append({"type": "text", "text": block.text})
                elif block.type == "tool_use":
                    out.append({"type": "tool_use", "id": block.id, "name": block.name, "input": block.input})
                elif block.type == "thinking":
                    out.append({"type": "thinking", "thinking": block.thinking})
        return out
    return content


class ChatRequest(BaseModel):
    session_id: str | None = None
    message: str


class ChatResponse(BaseModel):
    session_id: str
    response: str


@app.post("/chat", response_model=ChatResponse)
def chat(request: ChatRequest):
    session_id = request.session_id or str(uuid.uuid4())
    if session_id not in sessions:
        sessions[session_id] = {"messages": [], "auth_token": None, "pending_email": None}

    session = sessions[session_id]
    session["messages"].append({"role": "user", "content": request.message})

    messages = [m.copy() for m in session["messages"]]
    final_text = ""

    while True:
        response = claude_client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=1024,
            system=SYSTEM_PROMPT,
            tools=TOOLS,
            messages=messages,
        )

        if response.stop_reason == "end_turn":
            final_text = next(
                (b.text for b in response.content if hasattr(b, "type") and b.type == "text"),
                "",
            )
            messages.append({"role": "assistant", "content": _serialize_content(response.content)})
            break

        if response.stop_reason == "tool_use":
            messages.append({"role": "assistant", "content": _serialize_content(response.content)})
            tool_results = [
                {
                    "type": "tool_result",
                    "tool_use_id": block.id,
                    "content": execute_tool(block.name, block.input, session),
                }
                for block in response.content
                if hasattr(block, "type") and block.type == "tool_use"
            ]
            messages.append({"role": "user", "content": tool_results})
            continue

        break

    session["messages"] = messages
    return ChatResponse(session_id=session_id, response=final_text)


@app.delete("/session/{session_id}")
def clear_session(session_id: str):
    sessions.pop(session_id, None)
    return {"success": True}


@app.get("/health")
def health():
    return {"status": "ok", "active_sessions": len(sessions)}
