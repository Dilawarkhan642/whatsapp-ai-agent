import json

import httpx

from fastapi import FastAPI, Request
from pydantic import BaseModel
from workers import asgi

app = FastAPI(
    title="Stephen AI Vehicle Protection Agent",
    version="1.0.0"
)

# =========================================================
# REQUEST MODEL
# =========================================================

class ChatRequest(BaseModel):
    message: str
    session_id: str

# =========================================================
# STEPHEN SYSTEM PROMPT
# =========================================================

SYSTEM_PROMPT = """
You are Stephen, a professional frontline AI agent for a Vehicle Protection Center.

Your job is to:

1. Greet the customer naturally.
2. Build interest in vehicle protection.
3. Explain the service simply.
4. Ask for vehicle year, make, model and mileage.
5. Ask whether the customer currently has vehicle coverage.
6. Ask for first name and last name.
7. Keep responses short because this is a voice call.
8. Do not overwhelm the customer.
9. Once you have first name, last name, year, make, model, mileage
   and current coverage, call the collect_vehicle_info function to
   confirm the details back to the customer.
10. After collect_vehicle_info has been called and the customer
    confirms the details are correct, call save_lead to store them,
    then call transfer_to_specialist to hand the customer off to a
    human Product Specialist.
11. Speak naturally like a friendly US call-center representative.
12. Never ask the customer for information they already gave you
    earlier in this conversation.

Keep every spoken response short and conversational. Do not describe
function calls to the customer; just use them silently and continue
the conversation naturally.
"""

# =========================================================
# TOOL DECLARATIONS (Gemini function-calling schema)
# =========================================================

VEHICLE_INFO_PROPERTIES = {
    "first_name": {"type": "STRING", "description": "Customer's first name"},
    "last_name": {"type": "STRING", "description": "Customer's last name"},
    "year": {"type": "STRING", "description": "Vehicle year"},
    "make": {"type": "STRING", "description": "Vehicle make"},
    "model": {"type": "STRING", "description": "Vehicle model"},
    "mileage": {"type": "STRING", "description": "Vehicle mileage"},
    "current_coverage": {
        "type": "STRING",
        "description": "Customer's current vehicle coverage status"
    }
}

VEHICLE_INFO_REQUIRED = [
    "first_name", "last_name", "year", "make",
    "model", "mileage", "current_coverage"
]

TOOL_DECLARATIONS = [
    {
        "functionDeclarations": [
            {
                "name": "collect_vehicle_info",
                "description": (
                    "Collect and confirm the customer's personal and "
                    "vehicle information once all fields have been "
                    "gathered in conversation."
                ),
                "parameters": {
                    "type": "OBJECT",
                    "properties": VEHICLE_INFO_PROPERTIES,
                    "required": VEHICLE_INFO_REQUIRED
                }
            },
            {
                "name": "save_lead",
                "description": (
                    "Save the customer's information as a sales lead "
                    "after they confirm their details are correct."
                ),
                "parameters": {
                    "type": "OBJECT",
                    "properties": VEHICLE_INFO_PROPERTIES,
                    "required": VEHICLE_INFO_REQUIRED
                }
            },
            {
                "name": "transfer_to_specialist",
                "description": (
                    "Notify a human Product Specialist that a qualified "
                    "customer is ready for assistance, after the lead "
                    "has been saved."
                ),
                "parameters": {
                    "type": "OBJECT",
                    "properties": VEHICLE_INFO_PROPERTIES,
                    "required": VEHICLE_INFO_REQUIRED
                }
            }
        ]
    }
]

# =========================================================
# HOME / STATUS
# =========================================================

@app.get("/")
async def root():

    return {
        "status": "online",
        "agent": "Stephen",
        "service": "Vehicle Protection Center"
    }

@app.get("/api/status")
async def status():

    return {
        "status": "online",
        "agent": "Stephen",
        "service": "Vehicle Protection Center"
    }

# =========================================================
# HISTORY HELPERS (Cloudflare KV)
# =========================================================
#
# History is stored in Gemini's own "contents" format:
#   [{"role": "user"|"model", "parts": [...]}, ...]
# so it can be sent straight back to the API on every turn,
# including function-call / function-response turns.

HISTORY_TTL_SECONDS = 60 * 60 * 6  # keep a session's history for 6 hours

async def load_history(env, session_id: str) -> list:

    try:

        raw = await env.CHAT_HISTORY.get(session_id)

        if raw:

            return json.loads(raw)

    except Exception:

        pass

    return []

async def save_history(env, session_id: str, contents: list) -> None:

    try:

        await env.CHAT_HISTORY.put(
            session_id,
            json.dumps(contents),
            expiration_ttl=HISTORY_TTL_SECONDS
        )

    except Exception:

        # Don't block the customer's reply just because
        # history couldn't be persisted this turn.
        pass

# =========================================================
# TOOL EXECUTION (ported from tools.py)
# =========================================================

async def execute_tool(name: str, args: dict, env, session_id: str) -> str:

    first_name = args.get("first_name", "")
    last_name = args.get("last_name", "")
    year = args.get("year", "")
    make = args.get("make", "")
    model = args.get("model", "")
    mileage = args.get("mileage", "")
    current_coverage = args.get("current_coverage", "")

    if name == "collect_vehicle_info":

        return (
            f"Customer information collected successfully. "
            f"Name: {first_name} {last_name}. "
            f"Vehicle: {year} {make} {model}. "
            f"Mileage: {mileage}. "
            f"Current coverage: {current_coverage}."
        )

    if name == "save_lead":

        lead = {
            "first_name": first_name,
            "last_name": last_name,
            "year": year,
            "make": make,
            "model": model,
            "mileage": mileage,
            "current_coverage": current_coverage,
            "session_id": session_id
        }

        print("\n========== NEW LEAD ==========")
        print(lead)
        print("==============================\n")

        # Persist the lead in KV if a LEADS namespace is bound,
        # so it survives beyond the Worker's console logs.
        leads_kv = getattr(env, "LEADS", None)

        if leads_kv is not None:

            try:

                await leads_kv.put(
                    f"lead:{session_id}",
                    json.dumps(lead)
                )

            except Exception as e:

                print(f"Could not save lead to KV: {e}")

        return "Customer lead saved successfully."

    if name == "transfer_to_specialist":

        alert_message = (
            f"NEW SPECIALIST ALERT\n"
            f"Customer: {first_name} {last_name}\n"
            f"Vehicle: {year} {make} {model}\n"
            f"Mileage: {mileage}\n"
            f"Current coverage: {current_coverage}\n"
            f"Customer is qualified and ready for a Product Specialist."
        )

        print("\n========== SPECIALIST ALERT ==========")
        print(alert_message)
        print("=======================================\n")

        webhook_url = getattr(env, "SPECIALIST_ALERT_WEBHOOK_URL", None)

        if webhook_url:

            try:

                async with httpx.AsyncClient(timeout=5) as client:

                    await client.post(
                        webhook_url,
                        json={"text": alert_message}
                    )

            except Exception as e:

                print(f"Could not send specialist alert webhook: {e}")

        return (
            "Thank you. I have your information. "
            "A Product Specialist can now assist you "
            "with the available options."
        )

    return f"Unknown tool: {name}"

# =========================================================
# GEMINI CALL HELPER
# =========================================================

GEMINI_URL_TEMPLATE = (
    "https://generativelanguage.googleapis.com/v1beta/models/"
    "gemini-3.5-flash-lite:generateContent?key={api_key}"
)

async def call_gemini(contents: list, api_key: str) -> dict:

    url = GEMINI_URL_TEMPLATE.format(api_key=api_key)

    payload = {
        "systemInstruction": {
            "parts": [{"text": SYSTEM_PROMPT}]
        },
        "contents": contents,
        "tools": TOOL_DECLARATIONS,
        "generationConfig": {
            "temperature": 0.4,
            "maxOutputTokens": 200
        }
    }

    async with httpx.AsyncClient(timeout=30) as client:

        response = await client.post(url, json=payload)

    return {
        "status_code": response.status_code,
        "data": response.json()
    }

# =========================================================
# CHAT
# =========================================================

MAX_TOOL_ROUNDS = 3  # safety cap so a tool-call loop can't run forever

@app.post("/api/chat")
async def chat(
    request: ChatRequest,
    fastapi_request: Request
):

    env = fastapi_request.scope["env"]

    try:
        api_key = env.GOOGLE_API_KEY
    except Exception:
        api_key = None

    if not api_key:

        return {
            "success": False,
            "response": "Google API key is not configured."
        }

    # -----------------------------------------------------
    # LOAD HISTORY + APPEND USER MESSAGE
    # -----------------------------------------------------

    contents = await load_history(env, request.session_id)

    contents.append(
        {
            "role": "user",
            "parts": [{"text": request.message}]
        }
    )

    # -----------------------------------------------------
    # CALL GEMINI, HANDLING FUNCTION CALLS IN A LOOP
    # -----------------------------------------------------

    try:

        final_text = None

        for _ in range(MAX_TOOL_ROUNDS):

            result = await call_gemini(contents, api_key)

            if result["status_code"] != 200:

                return {
                    "success": False,
                    "response":
                        "Sorry, I am having trouble connecting right now.",
                    "error": result["data"]
                }

            data = result["data"]

            candidate = data["candidates"][0]
            parts = candidate["content"]["parts"]

            function_calls = [
                part["functionCall"]
                for part in parts
                if "functionCall" in part
            ]

            # Record the model's turn (text and/or function calls)
            # in history exactly as returned.
            contents.append(
                {
                    "role": "model",
                    "parts": parts
                }
            )

            if not function_calls:

                # Plain text reply — conversation turn is done.
                text_parts = [
                    part["text"]
                    for part in parts
                    if "text" in part
                ]

                final_text = "".join(text_parts).strip()

                break

            # Execute every requested tool call and feed the
            # results back to Gemini as a function response turn.
            response_parts = []

            for call in function_calls:

                tool_name = call["name"]
                tool_args = call.get("args", {})

                tool_result = await execute_tool(
                    tool_name,
                    tool_args,
                    env,
                    request.session_id
                )

                response_parts.append(
                    {
                        "functionResponse": {
                            "name": tool_name,
                            "response": {"result": tool_result}
                        }
                    }
                )

            contents.append(
                {
                    "role": "user",
                    "parts": response_parts
                }
            )

        if final_text is None:

            final_text = (
                "Sorry, I need a moment to process that. "
                "Could you say that again?"
            )

        # -------------------------------------------------
        # SAVE UPDATED HISTORY
        # -------------------------------------------------

        await save_history(env, request.session_id, contents)

        return {
            "success": True,
            "response": final_text
        }

    except Exception as e:

        return {
            "success": False,
            "response": "Sorry, something went wrong.",
            "error": str(e)
        }

# =========================================================
# CLOUDFLARE ASGI ENTRYPOINT
# =========================================================

Default = asgi.entrypoint(app)


