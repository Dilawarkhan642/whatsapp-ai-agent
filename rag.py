import shutil
import os

from langchain_community.document_loaders import TextLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_chroma import Chroma

# 0. Wipe any existing vector DB so re-running this script doesn't
#    accumulate duplicate/stale chunks from previous runs
if os.path.exists("./chroma_db"):
    shutil.rmtree("./chroma_db")
    print("Old chroma_db removed.")

# 1. Load company knowledge
loader = TextLoader("company_data.txt", encoding="utf-8")
documents = loader.load()

print("Document loaded successfully!")

# 2. Split document into chunks
text_splitter = RecursiveCharacterTextSplitter(
    chunk_size=500,
    chunk_overlap=50
)

chunks = text_splitter.split_documents(documents)

print("Number of chunks:", len(chunks))

# 3. Create embeddings
print("Creating embeddings...")

embeddings = HuggingFaceEmbeddings(
    model_name="sentence-transformers/all-MiniLM-L6-v2"
)

print("Embeddings created successfully!")

# 4. Create Chroma vector database
print("Creating vector database...")

vectorstore = Chroma.from_documents(
    documents=chunks,
    embedding=embeddings,
    persist_directory="./chroma_db"
)

print("Vector database created successfully!")

# 5. Create retriever
retriever = vectorstore.as_retriever(
    search_kwargs={"k": 2}
)

print("Retriever created successfully!")


# 6. Test normal retrieval
queries = [
    "What does vehicle protection cover?",
    "How do I file a claim?",
    "What is the cancellation policy?",
    "How long do refunds take?",
    "What are your support hours?"
]

for query in queries:

    print("\n===================================")
    print("QUESTION:", query)
    print("===================================")

    results = retriever.invoke(query)

    for i, result in enumerate(results):

        print(f"\nResult {i + 1}:")
        print(result.page_content)


# 7. Test similarity search with scores

print("\n\n===================================")
print("SIMILARITY SEARCH TEST")
print("===================================")

test_query = "What is covered under my plan?"

results = vectorstore.similarity_search_with_score(
    test_query,
    k=3
)

for i, (document, score) in enumerate(results):

    print(f"\nResult {i + 1}")
    print("Score:", score)
    print("Content:")
    print(document.page_content)