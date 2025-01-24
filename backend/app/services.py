import os
import hashlib
from redis import Redis
from langchain_openai import OpenAIEmbeddings
from langchain_community.vectorstores import FAISS
from langchain_community.document_loaders import PyPDFLoader
from langchain_community.chat_models import ChatOpenAI
from langchain.chains import ConversationalRetrievalChain
from langchain.prompts import PromptTemplate
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from langchain_teddynote import logging
import kss
from langchain.text_splitter import RecursiveCharacterTextSplitter

# 환경 변수 로드
load_dotenv()

logging.langsmith("portfolio chatbot")

# Redis 클라이언트 초기화
redis_client = Redis(
    host=os.getenv("REDIS_HOST", "localhost"),
    port=int(os.getenv("REDIS_PORT", 6379)),
    decode_responses=True
)

VECTOR_DB_PATH = "app/faiss_index"
app = FastAPI()

class QueryRequest(BaseModel):
    session_id: str
    query: str

def calculate_file_hash(file_path):
    """PDF 파일의 해시값 계산"""
    hasher = hashlib.sha256()
    with open(file_path, "rb") as f:
        hasher.update(f.read())
    return hasher.hexdigest()

def check_pdf_changes(pdf_dir: str):
    """PDF 변경 여부 확인 및 문서 로드 후 적절한 크기의 덩어리로 분할"""
    pdf_files = [os.path.join(pdf_dir, f) for f in os.listdir(pdf_dir) if f.endswith(".pdf")]
    if not pdf_files:
        raise FileNotFoundError("No PDF files found in the specified directory.")

    stored_hashes = redis_client.hgetall("pdf_hashes")
    current_hashes = {pdf: calculate_file_hash(pdf) for pdf in pdf_files}

    # if stored_hashes == current_hashes:
    #     print("No changes in PDFs.")
    #     return None

    print("PDFs have changed. Reloading documents.")
    full_text = ""

    for pdf_file in pdf_files:
        loader = PyPDFLoader(pdf_file)
        raw_documents = loader.load()
        
        for doc in raw_documents:
            full_text += doc.page_content + " "

    # KSS로 문장 분할 후 적절한 크기로 묶음
    sentences = kss.split_sentences(full_text)

    text_splitter = RecursiveCharacterTextSplitter(
        chunk_size=1000,  # 청크 크기를 줄여 응답 속도 개선
        chunk_overlap=200,
        length_function=len,
    )

    chunks = text_splitter.split_text(" ".join(sentences))

    print(f"Total chunks created: {len(chunks)}")

    # Redis에 해시값 저장
    redis_client.delete("pdf_hashes")
    redis_client.hmset("pdf_hashes", current_hashes)
    return chunks

def initialize_chain(documents=None):
    """Conversational Retrieval Chain 초기화"""
    embeddings = OpenAIEmbeddings()

    if documents or not os.path.exists(f"{VECTOR_DB_PATH}/index.faiss"):
        print("Creating FAISS database with optimized chunks...")
        vectors = FAISS.from_texts(documents, embeddings)
        vectors.save_local(VECTOR_DB_PATH)
    else:
        if not os.path.exists(f"{VECTOR_DB_PATH}/index.faiss"):
            raise FileNotFoundError("FAISS database not found. Load documents first.")
        print("Loading FAISS database...")
        vectors = FAISS.load_local(
            VECTOR_DB_PATH, embeddings, allow_dangerous_deserialization=True
        )

    prompt_template = PromptTemplate(
        input_variables=["context", "question"],
        template=(
            "너는 이력서에 명시 되어있는 사람의 역할을 수행하며, 면접관들과 이력서의 내용을 가지고 "
            "대화를 나눈다는 생각으로 대화를 주고받아. 취업에 맞는 자세를 취해. "
            "질문에 대한 대답만 철저히 하고, 질문은 하지마. 모르는 분야의 질문은 명확하게 모른다고 대답해.\n\n"
            "{context}\n\n질문: {question}\n\n 질문자의 소속 : {who}"
        )
    )

    retriever = vectors.as_retriever(search_kwargs={"search_k": 10, "k": 8})
    chain = ConversationalRetrievalChain.from_llm(
        llm=ChatOpenAI(temperature=0.0, model_name="gpt-4o-mini"),
        retriever=retriever,
        return_source_documents=False,
        combine_docs_chain_kwargs={"prompt": prompt_template}
    )
    return chain

def process_query(session_id: str, query: str, chain):
    """사용자의 질문 처리 및 Redis를 통한 캐싱된 대화 기록 관리"""
    history_key = f"chat_history:{session_id}"

    # cached_response = redis_client.get(f"response_cache:{query}")
    # if cached_response:
    #     print("Returning cached response")
    #     return cached_response

    chat_history = redis_client.lrange(history_key, -6, -1)
    formatted_history = [(chat_history[i], chat_history[i + 1]) for i in range(0, len(chat_history), 2)]
    formatted_history = []

    result = chain({"question": query, "chat_history": formatted_history, "who": session_id})
    
    retrieved_documents = result.get("source_documents", [])
    print(f"\n[INFO] Retrieved {len(retrieved_documents)} documents:")
    for idx, doc in enumerate(retrieved_documents):
        print(f"\n[Document {idx + 1}]:\n{doc.page_content}\n")

    redis_client.rpush(history_key, query, result["answer"])
    redis_client.ltrim(history_key, -6, -1)

    # 응답을 캐시하여 향후 속도 향상
    redis_client.setex(f"response_cache:{query}", 3600, result["answer"])

    return result["answer"]

@app.post("/query")
def handle_query(request: QueryRequest):
    try:
        chain = initialize_chain(check_pdf_changes("app/pdf_files"))
        answer = process_query(request.session_id, request.query, chain)
        return {"answer": answer}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
