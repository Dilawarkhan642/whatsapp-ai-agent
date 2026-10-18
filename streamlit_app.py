#python
import json
import uuid

import requests

import streamlit as st
import streamlit.components.v1 as components
from streamlit_mic_recorder import speech_to_text


# =========================================================
# CLOUDFLARE WORKER API
# =========================================================

CLOUDFLARE_API_URL = (
    "https://cloudflare-api.stephen-voice-api.workers.dev/api/chat"
)


# =========================================================
# CALL CLOUDFLARE / STEPHEN AI
# =========================================================

def chat_with_cloudflare(message: str, session_id: str) -> str:

    try:

        response = requests.post(
            CLOUDFLARE_API_URL,
            json={
                "message": message,
                "session_id": session_id
            },
            timeout=35
        )

        data = response.json()

        if data.get("success"):

            return data.get(
                "response",
                "Sorry, I could not generate a response."
            )

        return data.get(
            "response",
            "Sorry, I am having trouble connecting right now."
        )

    except requests.exceptions.Timeout:

        return (
            "Sorry, the AI is taking too long to respond. "
            "Please try again."
        )

    except requests.exceptions.ConnectionError:

        return (
            "Sorry, I cannot connect to the AI service right now."
        )

    except Exception as e:

        return f"Connection error: {str(e)}"


# =========================================================
# HTML RENDER HELPER
# =========================================================

def render_html(raw: str) -> None:

    cleaned = "\n".join(
        line.strip()
        for line in raw.strip("\n").split("\n")
    )

    st.markdown(
        cleaned,
        unsafe_allow_html=True
    )


# =========================================================
# TEXT TO SPEECH
# =========================================================

def speak_text(text: str) -> None:

    safe_text = json.dumps(text)

    components.html(
        f"""
        <script>

        window.speechSynthesis.cancel();

        const utterance =
            new SpeechSynthesisUtterance({safe_text});

        utterance.rate = 1.0;
        utterance.pitch = 1.0;
        utterance.volume = 1.0;

        window.speechSynthesis.speak(utterance);

        </script>
        """,
        height=0
    )


# =========================================================
# PAGE CONFIG
# =========================================================

st.set_page_config(
    page_title="Vehicle Protection Center",
    page_icon="🚗",
    layout="wide",
    initial_sidebar_state="expanded"
)


# =========================================================
# SESSION STATE
# =========================================================

if "display_messages" not in st.session_state:

    st.session_state.display_messages = []


if "active_page" not in st.session_state:

    st.session_state.active_page = "Call Center"


# Unique ID for this browser session, sent with every request
# so the Cloudflare Worker / Durable Object can keep track of
# this customer's conversation history.
if "session_id" not in st.session_state:

    st.session_state.session_id = str(uuid.uuid4())


# =========================================================
# PROFESSIONAL CSS
# =========================================================

render_html("""
<style>

/* =====================================================
   GLOBAL
===================================================== */

.stApp {
    background: #f4f7fb;
}

.main .block-container {
    max-width: 1400px;
    padding-top: 25px;
    padding-bottom: 70px;
}


/* =====================================================
   SIDEBAR
===================================================== */

section[data-testid="stSidebar"] {

    background: #111827;

    border-right: 1px solid #1f2937;
}

section[data-testid="stSidebar"] > div {

    padding-top: 20px;
}

section[data-testid="stSidebar"] * {

    color: #e5e7eb;
}


/* =====================================================
   SIDEBAR LOGO
===================================================== */

.sidebar-logo {

    padding: 10px 8px 25px 8px;

    text-align: center;
}

.sidebar-logo-icon {

    width: 55px;
    height: 55px;

    background: #2563eb;

    border-radius: 16px;

    display: flex;

    align-items: center;
    justify-content: center;

    margin: auto;

    font-size: 28px;

    box-shadow:
        0 8px 20px rgba(37, 99, 235, 0.35);
}

.sidebar-logo-title {

    font-size: 18px;

    font-weight: 800;

    margin-top: 12px;

    color: white;
}

.sidebar-logo-subtitle {

    font-size: 11px;

    color: #9ca3af;

    margin-top: 4px;
}


/* =====================================================
   SIDEBAR SECTION
===================================================== */

.sidebar-section {

    font-size: 11px;

    font-weight: 700;

    color: #6b7280;

    text-transform: uppercase;

    letter-spacing: 1px;

    margin:
        18px 8px 8px 8px;
}


/* =====================================================
   SIDEBAR BUTTONS
===================================================== */

section[data-testid="stSidebar"]
div.stButton > button {

    width: 100%;

    background: transparent;

    border: none;

    color: #d1d5db;

    text-align: left;

    border-radius: 10px;

    min-height: 44px;

    padding: 10px 14px;

    font-size: 14px;

    font-weight: 600;

    transition: all 0.2s ease;
}

section[data-testid="stSidebar"]
div.stButton > button:hover {

    background: #1f2937;

    color: white;

    border: none;

    transform: translateX(3px);
}


/* =====================================================
   MAIN HEADER
===================================================== */

.top-header {

    display: flex;

    justify-content: space-between;

    align-items: center;

    background: white;

    border-radius: 18px;

    padding: 20px 25px;

    margin-bottom: 20px;

    border: 1px solid #e5e7eb;

    box-shadow:
        0 4px 16px rgba(0,0,0,0.04);
}


.header-left {

    display: flex;

    align-items: center;

    gap: 14px;
}


.header-icon {

    width: 48px;
    height: 48px;

    background: #eff6ff;

    border-radius: 14px;

    display: flex;

    align-items: center;
    justify-content: center;

    font-size: 25px;
}


.header-title {

    font-size: 26px;

    font-weight: 800;

    color: #111827;

    margin: 0;
}


.header-subtitle {

    font-size: 13px;

    color: #6b7280;

    margin-top: 3px;
}


/* =====================================================
   ONLINE STATUS
===================================================== */

.status {

    display: flex;

    align-items: center;

    gap: 7px;

    background: #ecfdf5;

    color: #047857;

    padding: 9px 14px;

    border-radius: 20px;

    font-size: 13px;

    font-weight: 700;
}


/* =====================================================
   DASHBOARD CARDS
===================================================== */

.stat-card {

    background: white;

    border: 1px solid #e5e7eb;

    border-radius: 16px;

    padding: 18px;

    box-shadow:
        0 3px 12px rgba(0,0,0,0.03);

    transition: 0.2s;
}

.stat-card:hover {

    transform: translateY(-2px);

    box-shadow:
        0 8px 22px rgba(0,0,0,0.06);
}

.stat-icon {

    font-size: 24px;

    margin-bottom: 8px;
}

.stat-title {

    font-size: 12px;

    color: #6b7280;

    font-weight: 600;
}

.stat-value {

    font-size: 22px;

    font-weight: 800;

    color: #111827;

    margin-top: 3px;
}


/* =====================================================
   WELCOME CARD
===================================================== */

.welcome-card {

    background: white;

    border-radius: 18px;

    padding: 25px;

    margin-bottom: 20px;

    border: 1px solid #e5e7eb;

    box-shadow:
        0 3px 12px rgba(0,0,0,0.04);
}

.welcome-title {

    font-size: 21px;

    font-weight: 700;

    color: #111827;
}

.welcome-text {

    color: #6b7280;

    font-size: 14px;

    line-height: 1.7;

    margin-top: 7px;
}


/* =====================================================
   CHAT
===================================================== */

[data-testid="stChatMessage"] {

    padding: 10px 0;
}

[data-testid="stChatMessageContent"] {

    font-size: 15px !important;

    line-height: 1.6 !important;

    color: #111827 !important;
}

[data-testid="stChatMessage"] p {

    font-size: 15px !important;

    color: #111827 !important;
}


/* =====================================================
   CHAT INPUT
===================================================== */

[data-testid="stChatInput"] {

    border-radius: 15px !important;

    border: 1px solid #dbe2ea !important;

    box-shadow:
        0 5px 18px rgba(0,0,0,0.05);
}


/* =====================================================
   MIC BUTTON
===================================================== */

.stButton > button {

    border-radius: 10px;

    font-weight: 600;

    min-height: 42px;

    transition: 0.2s;
}

.stButton > button:hover {

    transform: translateY(-1px);
}


/* =====================================================
   FOOTER
===================================================== */

.footer {

    text-align: center;

    color: #9ca3af;

    font-size: 12px;

    margin-top: 35px;

    padding: 20px;
}


/* =====================================================
   DIVIDER
===================================================== */

.sidebar-divider {

    height: 1px;

    background: #1f2937;

    margin: 15px 5px;
}

</style>
""")


# =========================================================
# LEFT SIDEBAR
# =========================================================

with st.sidebar:

    render_html("""
    <div class="sidebar-logo">

        <div class="sidebar-logo-icon">
            🚗
        </div>

        <div class="sidebar-logo-title">
            Vehicle Protection
        </div>

        <div class="sidebar-logo-subtitle">
            AI Customer Support
        </div>

    </div>

    <div class="sidebar-divider"></div>

    <div class="sidebar-section">
        Main Menu
    </div>
    """)


    if st.button(
        "🏠   Dashboard",
        use_container_width=True
    ):

        st.session_state.active_page = "Dashboard"

        st.rerun()


    if st.button(
        "📞   Call Center",
        use_container_width=True
    ):

        st.session_state.active_page = "Call Center"

        st.rerun()


    if st.button(
        "👤   Customers",
        use_container_width=True
    ):

        st.session_state.active_page = "Customers"

        st.rerun()


    render_html("""
    <div class="sidebar-section">
        Services
    </div>
    """)


    if st.button(
        "🛡️   Coverage Plans",
        use_container_width=True
    ):

        st.session_state.active_page = "Coverage Plans"

        st.rerun()


    if st.button(
        "🚗   Vehicle Eligibility",
        use_container_width=True
    ):

        st.session_state.active_page = "Vehicle Eligibility"

        st.rerun()


    if st.button(
        "🔧   Claims Process",
        use_container_width=True
    ):

        st.session_state.active_page = "Claims Process"

        st.rerun()


    if st.button(
        "💵   Pricing & Quotes",
        use_container_width=True
    ):

        st.session_state.active_page = "Pricing & Quotes"

        st.rerun()


    if st.button(
        "👨‍💼   Product Specialist",
        use_container_width=True
    ):

        st.session_state.active_page = "Product Specialist"

        st.rerun()


    render_html("""
    <div class="sidebar-section">
        System
    </div>
    """)


    if st.button(
        "⚙️   Settings",
        use_container_width=True
    ):

        st.session_state.active_page = "Settings"

        st.rerun()


    st.write("")


    if st.button(
        "🗑️   Clear Conversation",
        use_container_width=True
    ):

        st.session_state.display_messages = []

        # Start a brand-new conversation on the Worker side too,
        # so old history doesn't bleed into the new chat.
        st.session_state.session_id = str(uuid.uuid4())

        st.rerun()


    render_html("""
    <div style="
        position: fixed;
        bottom: 15px;
        left: 25px;
        font-size: 11px;
        color: #6b7280;
    ">
        AI Support v1.0
    </div>
    """)


# =========================================================
# MAIN HEADER
# =========================================================

render_html(f"""
<div class="top-header">

    <div class="header-left">

        <div class="header-icon">
            📞
        </div>

        <div>

            <div class="header-title">
                {st.session_state.active_page}
            </div>

            <div class="header-subtitle">
                Vehicle Protection Center • AI Customer Support
            </div>

        </div>

    </div>

    <div class="status">
        🟢 Online
    </div>

</div>
""")


# =========================================================
# DASHBOARD
# =========================================================

if st.session_state.active_page == "Dashboard":

    st.markdown(
        "### Welcome to your AI Support Dashboard"
    )

    st.write("")

    col1, col2, col3, col4 = st.columns(4)


    with col1:

        render_html("""
        <div class="stat-card">

            <div class="stat-icon">📞</div>

            <div class="stat-title">
                Call Status
            </div>

            <div class="stat-value">
                Ready
            </div>

        </div>
        """)


    with col2:

        render_html("""
        <div class="stat-card">

            <div class="stat-icon">🤖</div>

            <div class="stat-title">
                AI Agent
            </div>

            <div class="stat-value">
                Online
            </div>

        </div>
        """)


    with col3:

        render_html("""
        <div class="stat-card">

            <div class="stat-icon">🎙️</div>

            <div class="stat-title">
                Voice System
            </div>

            <div class="stat-value">
                Active
            </div>

        </div>
        """)


    with col4:

        render_html("""
        <div class="stat-card">

            <div class="stat-icon">👨‍💼</div>

            <div class="stat-title">
                Specialist
            </div>

            <div class="stat-value">
                Available
            </div>

        </div>
        """)


    st.write("")
    st.write("")


    render_html("""
    <div class="welcome-card">

        <div class="welcome-title">
            🚀 AI Call Center
        </div>

        <div class="welcome-text">

            Your AI agent is ready to speak with customers,
            answer vehicle protection questions, collect vehicle
            information and connect customers with a Product Specialist.

        </div>

    </div>
    """)


# =========================================================
# COVERAGE PLANS
# =========================================================

elif st.session_state.active_page == "Coverage Plans":

    render_html("""
    <div class="welcome-card">

        <div class="welcome-title">
            🛡️ Coverage Plans
        </div>

        <div class="welcome-text">

            Customers can ask about available vehicle protection
            plans, covered components and additional benefits.

        </div>

    </div>
    """)

    st.info(
        "The AI agent can explain coverage information "
        "during the conversation."
    )


# =========================================================
# VEHICLE ELIGIBILITY
# =========================================================

elif st.session_state.active_page == "Vehicle Eligibility":

    render_html("""
    <div class="welcome-card">

        <div class="welcome-title">
            🚗 Vehicle Eligibility
        </div>

        <div class="welcome-text">

            The AI agent can collect vehicle year, make, model,
            mileage and current coverage information.

        </div>

    </div>
    """)

    st.info(
        "Vehicle information is collected during the AI conversation."
    )


# =========================================================
# CLAIMS
# =========================================================

elif st.session_state.active_page == "Claims Process":

    render_html("""
    <div class="welcome-card">

        <div class="welcome-title">
            🔧 Claims Process
        </div>

        <div class="welcome-text">

            Customers can ask how the claims process works
            when a covered vehicle component needs repair.

        </div>

    </div>
    """)


# =========================================================
# PRICING
# =========================================================

elif st.session_state.active_page == "Pricing & Quotes":

    render_html("""
    <div class="welcome-card">

        <div class="welcome-title">
            💵 Pricing & Quotes
        </div>

        <div class="welcome-text">

            Pricing depends on the vehicle and selected protection
            plan. The AI can explain the process and transfer the
            customer to a Product Specialist for exact pricing.

        </div>

    </div>
    """)


# =========================================================
# PRODUCT SPECIALIST
# =========================================================

elif st.session_state.active_page == "Product Specialist":

    render_html("""
    <div class="welcome-card">

        <div class="welcome-title">
            👨‍💼 Product Specialist
        </div>

        <div class="welcome-text">

            Once customer vehicle information has been collected,
            the AI agent can prepare the customer for transfer to
            a Product Specialist.

        </div>

    </div>
    """)


# =========================================================
# CUSTOMERS
# =========================================================

elif st.session_state.active_page == "Customers":

    render_html("""
    <div class="welcome-card">

        <div class="welcome-title">
            👤 Customers
        </div>

        <div class="welcome-text">

            Customer information collected during calls can
            eventually be displayed here.

        </div>

    </div>
    """)

    st.info(
        "Customer management can be connected to your lead-saving tool later."
    )


# =========================================================
# SETTINGS
# =========================================================

elif st.session_state.active_page == "Settings":

    render_html("""
    <div class="welcome-card">

        <div class="welcome-title">
            ⚙️ Settings
        </div>

        <div class="welcome-text">

            AI agent and voice settings can be managed here.

        </div>

    </div>
    """)

    st.checkbox(
        "Enable AI Voice Response",
        value=True
    )

    st.checkbox(
        "Enable Conversation Logging",
        value=True
    )


# =========================================================
# CALL CENTER
# =========================================================

elif st.session_state.active_page == "Call Center":


    # -----------------------------------------------------
    # WELCOME
    # -----------------------------------------------------

    if len(st.session_state.display_messages) == 0:

        render_html("""
        <div class="welcome-card">

            <div class="welcome-title">
                👋 Welcome to Vehicle Protection Center
            </div>

            <div class="welcome-text">

                I'm your AI customer support agent. I can help
                customers understand vehicle protection plans,
                discuss coverage, collect vehicle information,
                explain pricing and connect them with a
                Product Specialist.

            </div>

        </div>
        """)


        with st.chat_message(
            "assistant",
            avatar="🤖"
        ):

            st.markdown(
                "Hello! 👋 **This is Stephen from Vehicle Protection "
                "Center. How are you doing today?**"
            )


    # -----------------------------------------------------
    # CHAT HISTORY
    # -----------------------------------------------------

    for message in st.session_state.display_messages:

        if message["role"] == "user":

            with st.chat_message(
                "user",
                avatar="👤"
            ):

                st.markdown(
                    message["content"]
                )

        else:

            with st.chat_message(
                "assistant",
                avatar="🤖"
            ):

                st.markdown(
                    message["content"]
                )


    # -----------------------------------------------------
    # INPUT
    # -----------------------------------------------------

    input_col, mic_col = st.columns(
        [7, 1]
    )


    with input_col:

        typed_input = st.chat_input(
            "Type your message..."
        )


    with mic_col:

        voice_input = speech_to_text(

            language="en",

            start_prompt="🎤",

            stop_prompt="⏹️",

            just_once=True,

            use_container_width=True,

            key="voice_stt"
        )


    if voice_input:

        st.toast(
            "🎙️ Voice message received",
            icon="🎙️"
        )


    user_input = typed_input or voice_input


    # -----------------------------------------------------
    # PROCESS MESSAGE
    # -----------------------------------------------------

    if user_input:

        # USER MESSAGE

        with st.chat_message(
            "user",
            avatar="👤"
        ):

            st.markdown(
                user_input
            )


        st.session_state.display_messages.append(
            {
                "role": "user",
                "content": user_input
            }
        )


        # AI RESPONSE

        with st.chat_message(
            "assistant",
            avatar="🤖"
        ):

            with st.spinner(
                "Stephen is thinking..."
            ):

                response = chat_with_cloudflare(
                    user_input,
                    st.session_state.session_id
                )


            st.markdown(
                response
            )


            # VOICE RESPONSE

            speak_text(
                response
            )


            # SAVE RESPONSE

            st.session_state.display_messages.append(
                {
                    "role": "assistant",
                    "content": response
                }
            )


# =========================================================
# FOOTER
# =========================================================

render_html("""
<div class="footer">

    Vehicle Protection Center AI Support
    &nbsp; • &nbsp;
    AI Voice & Chat Assistant
    &nbsp; • &nbsp;
    Powered by AI

</div>
""")
