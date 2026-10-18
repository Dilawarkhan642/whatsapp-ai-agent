import base64
import json
from urllib.parse import parse_qs

import httpx

from fastapi import FastAPI, Request, Response
from pydantic import BaseModel
from workers import asgi


app = FastAPI(
    title="Stephen AI Vehicle Protection Agent",
    version="1.0.0"
)


# =========================================================
# REQUEST MODEL (used by the plain /api/chat endpoint)
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
7. Keep responses short because this may be a voice call or a WhatsApp chat.
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

Keep every response short and conversational. Do not describe
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

        # Send the alert straight to the specialist's own WhatsApp
        # number, using the same Meta WhatsApp Cloud API we already
        # use to talk to customers.
        specialist_number = getattr(env, "SPECIALIST_WHATSAPP_NUMBER", None)

        if specialist_number:

            await send_whatsapp_message(env, specialist_number, alert_message)

        else:

            print(
                "SPECIALIST_WHATSAPP_NUMBER is not configured — "
                "alert was only logged above."
            )

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
# SHARED CONVERSATION LOGIC
# =========================================================
#
# Used by BOTH /api/chat (Streamlit) and /whatsapp/webhook
# (Twilio), so memory, tool-calling and the system prompt
# behave identically no matter which channel the customer
# messages Stephen on.

MAX_TOOL_ROUNDS = 3  # safety cap so a tool-call loop can't run forever


async def generate_reply(env, session_id: str, message_parts: list) -> dict:
    """
    Runs one full conversation turn: loads history, calls Gemini
    (handling any function calls), saves history, and returns
    {"success": bool, "response": str, ...}.

    message_parts is a list of Gemini "part" objects for the
    customer's turn — e.g. [{"text": "hi"}] for a text message, or
    [{"inline_data": {"mime_type": "audio/ogg", "data": "..."}}]
    for a voice message.
    """

    try:
        api_key = env.GOOGLE_API_KEY
    except Exception:
        api_key = None

    if not api_key:

        return {
            "success": False,
            "response": "Google API key is not configured."
        }

    contents = await load_history(env, session_id)

    contents.append(
        {
            "role": "user",
            "parts": message_parts
        }
    )

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

            contents.append(
                {
                    "role": "model",
                    "parts": parts
                }
            )

            if not function_calls:

                text_parts = [
                    part["text"]
                    for part in parts
                    if "text" in part
                ]

                final_text = "".join(text_parts).strip()

                break

            response_parts = []

            for call in function_calls:

                tool_name = call["name"]
                tool_args = call.get("args", {})

                tool_result = await execute_tool(
                    tool_name,
                    tool_args,
                    env,
                    session_id
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

        await save_history(env, session_id, contents)

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
# CHAT (used by the Streamlit app)
# =========================================================

@app.post("/api/chat")
async def chat(
    request: ChatRequest,
    fastapi_request: Request
):

    env = fastapi_request.scope["env"]

    result = await generate_reply(
        env,
        request.session_id,
        [{"text": request.message}]
    )

    return result


# =========================================================
# WHATSAPP WEBHOOK (Meta WhatsApp Cloud API)
# =========================================================
#
# Meta requires two things on the same URL:
#   1. GET  — a one-time verification handshake when you register
#             the webhook in the Meta dashboard.
#   2. POST — the actual incoming messages, sent as JSON.
#
# Unlike Twilio, Meta does NOT read your response body as the
# reply. You must actively call the WhatsApp Graph API to send
# a message back.

async def send_whatsapp_message(env, to_number: str, text: str) -> None:

    access_token = getattr(env, "WHATSAPP_ACCESS_TOKEN", None)
    phone_number_id = getattr(env, "WHATSAPP_PHONE_NUMBER_ID", None)

    if not access_token or not phone_number_id:

        print("WhatsApp credentials missing — cannot send reply.")

        return

    url = (
        f"https://graph.facebook.com/v20.0/"
        f"{phone_number_id}/messages"
    )

    payload = {
        "messaging_product": "whatsapp",
        "to": to_number,
        "type": "text",
        "text": {"body": text}
    }

    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json"
    }

    try:

        async with httpx.AsyncClient(timeout=15) as client:

            response = await client.post(
                url,
                json=payload,
                headers=headers
            )

        if response.status_code >= 300:

            print(
                "Failed to send WhatsApp message: "
                f"{response.status_code} {response.text}"
            )

    except Exception as e:

        print(f"Error sending WhatsApp message: {e}")


# =========================================================
# VOICE SUPPORT (incoming audio + ElevenLabs voice replies)
# =========================================================

async def download_whatsapp_media(env, media_id: str):
    """
    Downloads a WhatsApp media file (e.g. a voice note) and
    returns (audio_bytes, mime_type), or (None, None) on failure.
    """

    access_token = getattr(env, "WHATSAPP_ACCESS_TOKEN", None)

    if not access_token:

        return None, None

    headers = {"Authorization": f"Bearer {access_token}"}

    try:

        async with httpx.AsyncClient(timeout=30) as client:

            # Step 1: look up the temporary download URL for this media id.
            meta_response = await client.get(
                f"https://graph.facebook.com/v21.0/{media_id}",
                headers=headers
            )

            if meta_response.status_code != 200:

                print(f"Failed to look up media {media_id}: {meta_response.text}")

                return None, None

            meta_data = meta_response.json()
            media_url = meta_data.get("url")
            mime_type = meta_data.get("mime_type", "audio/ogg")

            if not media_url:

                return None, None

            # Step 2: download the actual audio bytes (also needs auth).
            file_response = await client.get(media_url, headers=headers)

            if file_response.status_code != 200:

                print(f"Failed to download media {media_id}: {file_response.status_code}")

                return None, None

            return file_response.content, mime_type

    except Exception as e:

        print(f"Error downloading WhatsApp media: {e}")

        return None, None


async def generate_speech_workers_ai(env, text: str):
    """
    Converts text to speech using Cloudflare Workers AI (Deepgram
    Aura-1) via the plain REST API and returns MP3 bytes, or None
    on failure. Needs CF_ACCOUNT_ID and CF_API_TOKEN (a Cloudflare
    API token with "Workers AI: Read" permission) as secrets —
    no external account beyond Cloudflare itself.
    """

    account_id = getattr(env, "CF_ACCOUNT_ID", None)
    api_token = getattr(env, "CF_API_TOKEN", None)

    if not account_id or not api_token:

        print("CF_ACCOUNT_ID / CF_API_TOKEN missing — cannot generate speech.")

        return None

    url = (
        f"https://api.cloudflare.com/client/v4/accounts/"
        f"{account_id}/ai/run/@cf/deepgram/aura-1"
    )

    headers = {
        "Authorization": f"Bearer {api_token}",
        "Content-Type": "application/json"
    }

    payload = {"text": text}

    try:

        async with httpx.AsyncClient(timeout=30) as client:

            response = await client.post(url, headers=headers, json=payload)

        content_type = response.headers.get("content-type", "")

        if response.status_code != 200:

            print(f"Workers AI TTS failed: {response.status_code} {response.text}")

            return None

        if "audio" in content_type:

            # Aura-1 returns the raw MP3 bytes directly — no JSON wrapper.
            return response.content

        print(f"Workers AI TTS returned unexpected content: {response.text}")

        return None

    except Exception as e:

        print(f"Error generating speech with Workers AI: {e}")

        return None


async def upload_whatsapp_media(env, audio_bytes: bytes, mime_type: str = "audio/mpeg"):
    """
    Uploads audio bytes to WhatsApp's media endpoint and returns
    the resulting media id, or None on failure.
    """

    access_token = getattr(env, "WHATSAPP_ACCESS_TOKEN", None)
    phone_number_id = getattr(env, "WHATSAPP_PHONE_NUMBER_ID", None)

    if not access_token or not phone_number_id:

        return None

    url = f"https://graph.facebook.com/v21.0/{phone_number_id}/media"

    headers = {"Authorization": f"Bearer {access_token}"}

    files = {
        "file": ("reply.mp3", audio_bytes, mime_type)
    }

    data = {
        "messaging_product": "whatsapp",
        "type": mime_type
    }

    try:

        async with httpx.AsyncClient(timeout=30) as client:

            response = await client.post(
                url,
                headers=headers,
                data=data,
                files=files
            )

        if response.status_code != 200:

            print(f"Failed to upload media: {response.status_code} {response.text}")

            return None

        return response.json().get("id")

    except Exception as e:

        print(f"Error uploading WhatsApp media: {e}")

        return None


async def send_whatsapp_audio(env, to_number: str, media_id: str) -> None:

    access_token = getattr(env, "WHATSAPP_ACCESS_TOKEN", None)
    phone_number_id = getattr(env, "WHATSAPP_PHONE_NUMBER_ID", None)

    if not access_token or not phone_number_id:

        return

    url = f"https://graph.facebook.com/v21.0/{phone_number_id}/messages"

    payload = {
        "messaging_product": "whatsapp",
        "to": to_number,
        "type": "audio",
        "audio": {"id": media_id}
    }

    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json"
    }

    try:

        async with httpx.AsyncClient(timeout=15) as client:

            response = await client.post(url, json=payload, headers=headers)

        if response.status_code >= 300:

            print(f"Failed to send WhatsApp audio: {response.status_code} {response.text}")

    except Exception as e:

        print(f"Error sending WhatsApp audio: {e}")


async def reply_with_voice(env, to_number: str, text: str) -> None:
    """
    Converts text to speech, uploads it to WhatsApp, and sends it
    as a voice message. Falls back to a plain text message if
    speech generation or upload fails for any reason.
    """

    audio_bytes = await generate_speech_workers_ai(env, text)

    if audio_bytes:

        media_id = await upload_whatsapp_media(env, audio_bytes, "audio/mpeg")

        if media_id:

            await send_whatsapp_audio(env, to_number, media_id)

            return

    # Fallback: if anything above failed, still get the customer a reply.
    await send_whatsapp_message(env, to_number, text)


@app.get("/whatsapp/webhook")
async def whatsapp_webhook_verify(fastapi_request: Request):

    env = fastapi_request.scope["env"]

    verify_token = getattr(env, "WHATSAPP_VERIFY_TOKEN", None)

    params = fastapi_request.query_params

    mode = params.get("hub.mode")
    token = params.get("hub.verify_token")
    challenge = params.get("hub.challenge")

    if mode == "subscribe" and token == verify_token and challenge:

        return Response(content=challenge, media_type="text/plain")

    return Response(content="Verification failed", status_code=403)


@app.post("/whatsapp/webhook")
async def whatsapp_webhook_receive(fastapi_request: Request):

    env = fastapi_request.scope["env"]

    try:

        payload = await fastapi_request.json()

        entry = payload["entry"][0]
        change = entry["changes"][0]
        value = change["value"]

        messages = value.get("messages")

        if not messages:

            # This can be a delivery/read status update rather
            # than an actual incoming message — nothing to do.
            return {"status": "ignored"}

        message = messages[0]

        from_number = message["from"]
        message_type = message.get("type")

        # Use the customer's WhatsApp number as their session_id,
        # so their conversation history persists across messages.
        session_id = from_number

        is_voice_message = False
        message_parts = None

        if message_type == "text":

            message_text = message.get("text", {}).get("body", "")

            if message_text:

                message_parts = [{"text": message_text}]

        elif message_type == "audio":

            media_id = message.get("audio", {}).get("id")

            if media_id:

                audio_bytes, mime_type = await download_whatsapp_media(env, media_id)

                if audio_bytes:

                    # Gemini's supported audio mime types don't include
                    # the codec suffix WhatsApp sends (e.g.
                    # "audio/ogg; codecs=opus") — strip it down.
                    clean_mime_type = mime_type.split(";")[0].strip()

                    message_parts = [
                        {
                            "inline_data": {
                                "mime_type": clean_mime_type,
                                "data": base64.b64encode(audio_bytes).decode("utf-8")
                            }
                        }
                    ]

                    is_voice_message = True

        if not message_parts:

            # Unsupported message type (image, document, sticker, etc.)
            # or a voice note we couldn't download — say so plainly.
            await send_whatsapp_message(
                env,
                from_number,
                "Sorry, I can only understand text and voice messages "
                "right now."
            )

            return {"status": "ignored"}

        result = await generate_reply(env, session_id, message_parts)

        reply_text = result.get(
            "response",
            "Sorry, something went wrong."
        )

        # Reply in the same medium the customer used — voice note
        # for voice notes, plain text otherwise.
        if is_voice_message:

            await reply_with_voice(env, from_number, reply_text)

        else:

            await send_whatsapp_message(env, from_number, reply_text)

        return {"status": "ok"}

    except Exception as e:

        print(f"Error handling WhatsApp webhook: {e}")

        return {"status": "error", "error": str(e)}


# =========================================================
# CLOUDFLARE ASGI ENTRYPOINT
# =========================================================

Default = asgi.entrypoint(app)