#python
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_chroma import Chroma

from langchain_core.messages import (
    SystemMessage,
    HumanMessage
)

from langgraph.graph import StateGraph, MessagesState, START
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
# 4. Chroma Vector Database
# ==========================================

vectorstore = Chroma(
    persist_directory="./chroma_db",
    embedding_function=embeddings
)


# ==========================================
# 5. RAG Retrieval
# ==========================================

def retrieve_relevant_documents(
    query,
    threshold=1.3
):

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

system_prompt = """
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
   an order ID, politely ask them for their order ID.

7. If information is not available, say:
   "I'm sorry, I don't have that information."

8. Be polite, friendly, and concise.

9. Use simple English.

10. Do not mention RAG, embeddings, Chroma, vector databases,
    similarity scores, or internal technical processes.

COMPANY CONTEXT:

"""

# ==========================================
# 8. Agent Node
# ==========================================

def agent(state: MessagesState):

    # Find the latest customer message
    user_message = ""

    for message in reversed(state["messages"]):

        if isinstance(message, HumanMessage):
            user_message = message.content
            break

    # Retrieve relevant company information
    documents = retrieve_relevant_documents(
        user_message
    )

    # Build context
    if documents:

        context = "\n\n".join(
            document.page_content
            for document in documents
        )

    else:

        context = (
            "No relevant company information was found."
        )

    # Create system message
    system_message = SystemMessage(
        content=system_prompt.format(
            context=context
        )
    )

    # Send messages to Gemini
    response = llm_with_tools.invoke(
        [
            system_message
        ] + state["messages"]
    )

    # Return new message
    return {
        "messages": [response]
    }



    # Build context
    if documents:

        context = "\n\n".join(
            document.page_content
            for document in documents
        )

    else:

        context = (
            "No relevant company information was found."
        )

    # Create system message
    system_message = SystemMessage(
        content=system_prompt.format(
            context=context
        )
    )

    # Send messages to Gemini
    response = llm_with_tools.invoke(
        [
            system_message
        ] + state["messages"]
    )

      #Return new message
    return {
        "messages": [response]
    }


# ==========================================
# 9. Build LangGraph
# ==========================================

builder = StateGraph(MessagesState)


# ==========================================
# 10. Add Nodes
# ==========================================

builder.add_node(
    "agent",
    agent
)

builder.add_node(
    "tools",
    ToolNode(tools)
)


# ==========================================
# 11. Add Edges
# ==========================================

builder.add_edge(
    START,
    "agent"
)

builder.add_conditional_edges(
    "agent",
    tools_condition
)

builder.add_edge(
    "tools",
    "agent"
)


# ==========================================
# 12. Compile Graph
# ==========================================

graph = builder.compile()


# ==========================================
# 13. Chatbot
# ==========================================

print("===================================")
print("   DK Store LangGraph AI Agent")
print("===================================")
print("Type 'exit' to close.")
print()


# Conversation memory
messages = []


while True:

    user_message = input(
        "Customer: "
    ).strip()


    # ======================================
    # Exit
    # ======================================

    if user_message.lower() in [
        "exit",
        "quit",
        "bye"
    ]:

        print(
            "Agent: Thank you for contacting DK Store. Goodbye!"
        )

        break


    # ======================================
    # Empty Input
    # ======================================

    if not user_message:

        print(
            "Agent: Please enter your question."
        )

        print()

        continue


    # ======================================
    # Add Customer Message
    # ======================================

    messages.append(
        HumanMessage(
            content=user_message
        )
    )


    # ======================================
    # Run LangGraph
    # ======================================

    try:

        result = graph.invoke({
            "messages": messages
        })

        # Update conversation memory
        messages = result["messages"]

        # ==================================
        # Get Final Message
        # ==================================

        final_message = messages[-1]

        # Gemini may return content as a list
        if isinstance(final_message.content, list):

            text = ""

            for item in final_message.content:

                if isinstance(item, dict):

                    if item.get("type") == "text":
                        text += item.get("text", "")

                elif isinstance(item, str):

                    text += item

        else:

            text = final_message.content


        # ==================================
        # Print Final Answer
        # ==================================

        print("Agent:", text)
        print()


    except Exception as e:

        print(
            "Agent: Sorry, something went wrong."
        )

        print("Error:", e)
        print()

