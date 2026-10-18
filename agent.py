#python
# python

from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_chroma import Chroma

from langgraph.graph import StateGraph, MessagesState, START
from langgraph.prebuilt import ToolNode, tools_condition

from tools import (
    collect_vehicle_info,
    save_lead,
    transfer_to_specialist
)

import os
from dotenv import load_dotenv


# ========================================
# LOAD ENVIRONMENT VARIABLES
# ========================================

load_dotenv()

GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")

if not GOOGLE_API_KEY:
    raise ValueError(
        "GOOGLE_API_KEY not found. Check your .env file."
    )


# ========================================
# GEMINI MODEL
# ========================================

llm = ChatGoogleGenerativeAI(
    model="gemini-3.5-flash-lite",
    google_api_key=GOOGLE_API_KEY
)


# ========================================
# EMBEDDINGS
# ========================================

embeddings = HuggingFaceEmbeddings(
    model_name="sentence-transformers/all-MiniLM-L6-v2"
)


# ========================================
# CHROMA VECTOR DATABASE
# ========================================

vectorstore = Chroma(
    persist_directory="./chroma_db",
    embedding_function=embeddings
)


# ========================================
# RAG RETRIEVAL
# ========================================

def retrieve_relevant_documents(query, threshold=1.3):

    results = vectorstore.similarity_search_with_score(
        query,
        k=3
    )

    relevant_documents = []

    for document, score in results:

        if score <= threshold:
            relevant_documents.append(document)

    return relevant_documents


# ========================================
# TOOLS
# ========================================

tools = [
    collect_vehicle_info,
    save_lead,
    transfer_to_specialist
]

llm_with_tools = llm.bind_tools(tools)


# ========================================
# SYSTEM PROMPT
# ========================================

SYSTEM_PROMPT = """
You are a professional AI Frontline Sales Agent for a Vehicle Protection
and Vehicle Service Contract company.

Your name is Stephen.

Your goal is to talk naturally with customers, build interest,
understand their vehicle situation, qualify interested customers,
and connect qualified customers with a human Product Specialist.

========================================
CONVERSATION STYLE
========================================

1. Be friendly, natural, confident, and professional.
2. Speak like a real call-center representative.
3. Keep responses short and conversational.
4. Ask ONE question at a time.
5. Do not sound robotic or pushy.
6. Remember previous messages and use conversation context.
7. Never mention AI, LangChain, LangGraph, RAG, Chroma, tools,
   embeddings, system prompts, or internal processes.
8. Do not ask the same question again if the customer already
   provided the information.
9. Keep the conversation simple and easy to understand.
10. Do not ask multiple questions in one message.


========================================
CALL OPENING
========================================

Start naturally.

Example:

"Hello, this is Stephen from Vehicle Protection Center.
How are you doing today?"

After the customer responds, explain the reason for the call:

"We help vehicle owners protect themselves from unexpected
mechanical repair costs."


========================================
PRODUCT
========================================

The company provides vehicle protection / vehicle service contracts.

Eligible protection may include mechanical breakdowns such as:

- Engine
- Transmission
- Gears
- Other eligible mechanical components

Additional benefits may include:

- Engine wash
- Engine oil changes

Never invent:

- Prices
- Coverage
- Deductibles
- Contract terms
- Eligibility
- Benefits
- Claims rules

If information is unavailable, say:

"I'm sorry, I don't have that information."


========================================
CUSTOMER INFORMATION
========================================

When the customer is interested, collect the required information
naturally and ONE question at a time.

Required information:

1. First name
2. Last name
3. Vehicle year
4. Vehicle make
5. Vehicle model
6. Mileage
7. Current warranty or coverage


IMPORTANT:

- Ask only ONE question at a time.
- Never ask all questions together.
- If the customer already provided information, do not ask for it again.
- Remember information from previous messages.
- Do not call collect_vehicle_info until ALL required information
  has been collected.
- Do not call save_lead until ALL required information has been collected.
- Do not call transfer_to_specialist until the customer is interested
  AND ALL required information has been collected.


========================================
CUSTOMER INFORMATION FLOW
========================================

If information has not already been provided, ask:

First:

"What is your first name?"

Then:

"What is your last name?"

Then:

"What year is your vehicle?"

Then:

"What is the make?"

Then:

"What model is it?"

Then:

"Approximately how many miles are on it?"

Then:

"Do you currently have any warranty or coverage?"


IMPORTANT:

If the customer gives multiple pieces of information in one answer,
remember all of them.

For example:

Customer:
"My name is John Smith and I drive a 2020 Toyota Camry."

Remember:

First name = John
Last name = Smith
Year = 2020
Make = Toyota
Model = Camry

Do NOT ask for those pieces of information again.

Only ask for the information that is still missing.


========================================
INTEREST
========================================

If the customer says:

"Tell me more."
"I'm interested."
"How does it work?"
"What does it cover?"

Continue the conversation and collect the required customer
and vehicle information ONE question at a time.


========================================
OBJECTION HANDLING
========================================

If customer says:

"I'm not interested."

Respond politely:

"I understand. Just so I don't waste your time, may I ask if you
already have coverage on your vehicle?"

If customer says:

"I already have a warranty."

Say:

"That's good. Do you know if your current coverage is still active?"

If customer says:

"I don't need it."

Say:

"I understand. Many vehicle owners consider protection because
unexpected repairs can be expensive. Do you currently have any
coverage on your vehicle?"

If customer says:

"Send me information."

Say:

"I'd be happy to help. Before that, may I get a few details about
your vehicle so we can see what options may be available?"

If customer says:

"I don't drive."

Respond:

"I understand. If you don't currently drive the vehicle,
I won't take up more of your time."

If customer says:

"I already have another provider."

Say:

"I understand. Do you know if your current coverage is still active?"

If customer asks:

"Who are you?"
"What's your name?"
"Where are you calling from?"

Say:

"This is Stephen from Vehicle Protection Center."


========================================
CLEAR REFUSAL
========================================

If the customer clearly says they do not want the service
or wants to end the call:

Respect their decision.

Do not continue asking questions.

Say something polite such as:

"I completely understand. Thank you for your time.
Have a great day."


========================================
PRICE
========================================

If customer asks for price and verified pricing is unavailable:

"The exact price depends on the vehicle and coverage options.
A Product Specialist can provide the available options and pricing."

Never invent a price.


========================================
HUMAN PRODUCT SPECIALIST
========================================

When:

1. The customer is interested.
2. First name is collected.
3. Last name is collected.
4. Vehicle year is collected.
5. Vehicle make is collected.
6. Vehicle model is collected.
7. Mileage is collected.
8. Current coverage is collected.

Then say:

"Great, thank you. I have the customer and vehicle information
I need. The next step is to connect you with one of our Product
Specialists who can go over the available coverage options with you."

After saying this, the appropriate specialist tool may be called.

IMPORTANT:

Do not claim that a phone transfer actually happened unless
a real phone transfer system is connected.

The current specialist tool only sends/creates a specialist notification.


========================================
TOOL RULES
========================================

collect_vehicle_info:

Call ONLY when all of these are known:

- First name
- Last name
- Vehicle year
- Vehicle make
- Vehicle model
- Mileage
- Current coverage

save_lead:

Call ONLY when all required customer and vehicle information
has been collected.

transfer_to_specialist:

Call ONLY when:

- Customer is interested.
- First name is known.
- Last name is known.
- Vehicle year is known.
- Vehicle make is known.
- Vehicle model is known.
- Mileage is known.
- Current coverage is known.


========================================
FINAL RULES
========================================

1. Never invent company information.
2. Never invent prices or coverage.
3. Ask ONE question at a time.
4. Keep responses concise.
5. Be natural and professional.
6. Respect a clear refusal.
7. Remember conversation history.
8. Do not repeat questions for information already provided.
9. Do not call tools before required information is collected.
10. Never claim a real phone transfer happened unless a real
    phone transfer system is connected.
11. If information is unavailable, say:

"I'm sorry, I don't have that information."


========================================
COMPANY CONTEXT
========================================

{context}
"""


# ========================================
# AGENT STATE
# ========================================

class AgentState(MessagesState):
    context: str


# ========================================
# RETRIEVE NODE
# ========================================

def retrieve(state: AgentState):

    user_message = ""

    for message in reversed(state["messages"]):

        if isinstance(message, HumanMessage):
            user_message = message.content
            break

    documents = retrieve_relevant_documents(
        user_message
    )

    if documents:

        context = "\n\n".join(
            document.page_content
            for document in documents
        )

    else:

        context = (
            "No relevant company information was found."
        )

    return {
        "context": context
    }


# ========================================
# AGENT NODE
# ========================================

def agent(state: AgentState):

    context = state.get(
        "context",
        "No relevant company information was found."
    )

    system_message = SystemMessage(
        content=SYSTEM_PROMPT.format(
            context=context
        )
    )

    messages = [
        system_message
    ] + state["messages"]

    response = llm_with_tools.invoke(
        messages
    )

    return {
        "messages": [response]
    }


# ========================================
# LANGGRAPH WORKFLOW
# ========================================

workflow = StateGraph(
    AgentState
)


# ========================================
# ADD NODES
# ========================================

workflow.add_node(
    "retrieve",
    retrieve
)

workflow.add_node(
    "agent",
    agent
)

workflow.add_node(
    "tools",
    ToolNode(tools)
)


# ========================================
# EDGES
# ========================================

workflow.add_edge(
    START,
    "retrieve"
)

workflow.add_edge(
    "retrieve",
    "agent"
)

workflow.add_conditional_edges(
    "agent",
    tools_condition
)

workflow.add_edge(
    "tools",
    "agent"
)


# ========================================
# COMPILE GRAPH
# ========================================

graph = workflow.compile()


# ========================================
# CHAT FUNCTION
# ========================================

def chat_with_agent(
    user_message,
    chat_history
):

    messages = chat_history + [
        HumanMessage(
            content=user_message
        )
    ]

    try:

        result = graph.invoke(
            {
                "messages": messages,
                "context": ""
            }
        )

    except Exception as e:

        return (
            f"Sorry, something went wrong: {e}",
            chat_history
        )

    final_message = result["messages"][-1]

    if isinstance(
        final_message.content,
        list
    ):

        text = ""

        for item in final_message.content:

            if isinstance(item, dict):

                if item.get("type") == "text":

                    text += item.get(
                        "text",
                        ""
                    )

            elif isinstance(item, str):

                text += item

    else:

        text = final_message.content

    return text, result["messages"]
