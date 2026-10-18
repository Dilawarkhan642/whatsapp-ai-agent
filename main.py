from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_chroma import Chroma

from langgraph.graph import StateGraph, MessagesState, START, END
from langgraph.prebuilt import ToolNode, tools_condition

from tools import (
    check_order_status,
    cancel_order,
    check_product
)

import os
from dotenv import load_dotenv


# ==========================================
# 1. Load Environment Variables
# ==========================================

load_dotenv()

GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")

if not GOOGLE_API_KEY:
    raise ValueError(
        "GOOGLE_API_KEY not found. Check your .env file."
    )


# ==========================================
# 2. Gemini
# ==========================================

llm = ChatGoogleGenerativeAI(
    model="gemini-3.6-flash",
    google_api_key=GOOGLE_API_KEY
)


# ==========================================
# 3. Embeddings
# ==========================================

embeddings = HuggingFaceEmbeddings(
    model_name="sentence-transformers/all-MiniLM-L6-v2"
)


# ==========================================
# 4. Chroma Database
# ==========================================

vectorstore = Chroma(
    persist_directory="./chroma_db",
    embedding_function=embeddings
)


# ==========================================
# 5. RAG Retrieval
# ==========================================

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


# ==========================================
# 6. Tools
# ==========================================

tools = [
    check_order_status,
    cancel_order,
    check_product
]

llm_with_tools = llm.bind_tools(tools)


# ==========================================
# 7. System Prompt
# ==========================================

SYSTEM_PROMPT = """
You are a professional AI Customer Service Agent for DK Store.

IMPORTANT RULES:

1. Use the COMPANY CONTEXT for company information.

2. Never invent DK Store products, prices, policies,
shipping information, refund information, or other company facts.

3. When the customer asks about an order status,
use the check_order_status tool.

4. When the customer wants to cancel an order,
use the cancel_order tool.

5. When the customer asks whether a product is available,
use the check_product tool.

6. If the customer asks about an order but does not provide
an order ID, politely ask for the order ID.

7. If information is not available, say:
"I'm sorry, I don't have that information."

8. Be polite, friendly, and concise.

9. Use simple English.

10. Never mention RAG, embeddings, Chroma, vector databases,
similarity scores, or internal technical processes.

COMPANY CONTEXT:

{context}
"""


# ==========================================
# 8. LangGraph State
# ==========================================

class AgentState(MessagesState):
    context: str


# ==========================================
# 9. Retrieval Node
# ==========================================

def retrieve(state: AgentState):

    user_message = state["messages"][-1].content

    documents = retrieve_relevant_documents(
        user_message
    )

    if documents:

        context = "\n\n".join(
            document.page_content
            for document in documents
        )

    else:

        context = "No relevant company information was found."

    return {
        "context": context
    }


# ==========================================
# 10. Agent Node
# ==========================================

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


# ==========================================
# 11. Build LangGraph
# ==========================================

workflow = StateGraph(AgentState)


# Nodes
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


# ==========================================
# 12. Graph Flow
# ==========================================

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


# ==========================================
# 13. Compile Graph
# ==========================================

graph = workflow.compile()


# ==========================================
# 14. Start Chatbot
# ==========================================

print("===================================")
print("     DK Store AI Customer Service")
print("===================================")
print("LangGraph Agent Started")
print("Type 'exit' to close the chatbot.")
print()


# ==========================================
# 15. Chat History
# ==========================================

chat_history = []


# ==========================================
# 16. Chat Loop
# ==========================================

while True:

    user_message = input("Customer: ").strip()


    # Exit
    if user_message.lower() in [
        "exit",
        "quit",
        "bye"
    ]:

        print(
            "Agent: Thank you for contacting DK Store. Goodbye!"
        )

        break


    # Empty input
    if not user_message:

        print(
            "Agent: Please enter your question."
        )

        print()

        continue


    # ======================================
    # Run LangGraph
    # ======================================

    try:

        result = graph.invoke({

            "messages": chat_history + [
                HumanMessage(
                    content=user_message
                )
            ],

            "context": ""

        })


        # Get final AI message
        final_message = result["messages"][-1]


        # ==================================
        # Get Text
        # ==================================

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


        # ==================================
        # Display
        # ==================================

        print(
            "Agent:",
            text
        )

        print()


        # ==================================
        # Save Conversation
        # ==================================

        chat_history = result["messages"]


    except Exception as e:

        print(
            "Agent: Sorry, something went wrong."
        )

        print()

        print(
            "Error:",
            e
        )

        print()