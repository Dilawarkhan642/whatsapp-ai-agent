# AI Vehicle Protection Agent ("Stephen")

A conversational AI sales agent for a vehicle protection company. The agent, named **Stephen**, talks to customers by text or voice, answers questions from company knowledge, collects the customer's vehicle details, saves the lead and hands qualified customers to a human specialist.

The project has two parts: a **cloud API** (Cloudflare Workers) and a **local LangGraph + RAG agent**, plus a **Streamlit** front end with voice input.

## Features

- Natural, short, one-question-at-a-time conversations (system prompt tuned for a call-center style)
- Collects first name, last name, vehicle year, make, model, mileage and current coverage, then confirms the details with the customer
- Gemini function calling: `collect_vehicle_info`, `save_lead`, `transfer_to_specialist`
- Chat history per session and lead storage in Cloudflare KV
- Retrieval-augmented generation (RAG): company knowledge is split into chunks, embedded and stored in ChromaDB, and the most relevant chunks are added to the prompt
- Streamlit app with typed and voice input (speech-to-text) and spoken replies (browser text-to-speech)

## Project structure

| File | What it does |
| --- | --- |
| `app.py` | FastAPI app for Cloudflare Python Workers. Endpoints: `GET /`, `GET /api/status`, `POST /api/chat`. Calls Gemini, runs the tools, stores history and leads in KV |
| `streamlit_app.py` | Web UI ("Vehicle Protection Center") with text and voice input; sends messages to the deployed Worker |
| `agent.py` | LangGraph agent with a retrieve step, the Gemini model and the lead tools (`chat_with_agent`) |
| `langgraph_agent.py`, `main.py` | Earlier LangGraph agent versions with a retrieve node and order/product tools |
| `rag.py` | Builds the ChromaDB vector database from `company_data.txt` (chunks of 500 characters, 50 overlap, `all-MiniLM-L6-v2` embeddings) and tests retrieval |

## Tech stack

Python, FastAPI, Cloudflare Workers and KV, Google Gemini, LangChain, LangGraph, ChromaDB, Hugging Face sentence-transformers, Streamlit.

## Setup

1. Create a virtual environment and install the dependencies:
```
   pip install -r requirements.txt
```
2. Copy `.env.example` to `.env` and add your Google API key:
```
   GOOGLE_API_KEY=your-key-here
```
3. Put your company knowledge in `company_data.txt` and build the vector database:
```
   python rag.py
```
4. Run the Streamlit app:
```
   streamlit run streamlit_app.py
```

### Cloudflare Worker (`app.py`)

The Worker needs two KV namespaces bound as `CHAT_HISTORY` and `LEADS`, and a secret named `GOOGLE_API_KEY` (set it with `wrangler secret put GOOGLE_API_KEY`). Keys are never stored in this repository.

## Notes

- The local agents import tool functions from a `tools.py` module that is not included in this repository, and `company_data.txt` is not included either.
- Secrets live in `.env` / Cloudflare secrets and are excluded from Git.
