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
    """PDF 변경 여부 확인 및 필요시 문서 로드"""
    pdf_files = [os.path.join(pdf_dir, f) for f in os.listdir(pdf_dir) if f.endswith(".pdf")]
    if not pdf_files:
        raise FileNotFoundError("No PDF files found in the specified directory.")

    # Redis에 저장된 파일 해시값 가져오기
    stored_hashes = redis_client.hgetall("pdf_hashes")
    current_hashes = {pdf: calculate_file_hash(pdf) for pdf in pdf_files}

    if stored_hashes == current_hashes:
        # PDF 변경이 없으면 None 반환
        print("No changes in PDFs.")
        return None

    # PDF 변경 시 문서 로드
    print("PDFs have changed. Reloading documents.")
    documents = [] 
    for pdf_file in pdf_files:
        loader = PyPDFLoader(pdf_file)
        documents.extend(loader.load())
        
    print(documents)

    # Redis에 해시값 저장
    redis_client.delete("pdf_hashes")
    redis_client.hmset("pdf_hashes", current_hashes)
    return documents

def initialize_chain(documents=None):
    """Conversational Retrieval Chain 초기화"""
    embeddings = OpenAIEmbeddings()

    if documents or not os.path.exists(f"{VECTOR_DB_PATH}/index.faiss"):
        # 문서가 있을 경우 새로 벡터 생성 후 저장
        print("Creating FAISS database...")
        vectors = FAISS.from_documents(documents, embeddings)
        vectors.save_local(VECTOR_DB_PATH)
    else:
        # 기존 FAISS 데이터 로드
        if not os.path.exists(f"{VECTOR_DB_PATH}/index.faiss"):
            raise FileNotFoundError(
                "FAISS database not found. Ensure you have generated the database by loading documents at least once."
            )
        print("Loading FAISS database...")
        vectors = FAISS.load_local(
            VECTOR_DB_PATH, embeddings, allow_dangerous_deserialization=True
        )

    # 프롬프트 추가
    prompt_template = PromptTemplate(
        input_variables=["context", "question"],
        template=(
            "너는 이력서에 명시 되어있는 사람의 역할을 수행하며, 면접관들과 이력서의 내용을 가지고 "
            "대화를 나눈다는 생각으로 대화를 주고받아. 취업에 맞는 자세를 취해. 또한 넌 질문에 대한 대답만 철저히 하고, 되려 질문은 하지마. 마지막으로 니가 모르는 분야의 질문은 명확하게 모른다고 대답해.\n\n"
            "{context}\n\n질문: {question}\n\n 소속 : {who}"
        )
    )

    chain = ConversationalRetrievalChain.from_llm(
        llm=ChatOpenAI(temperature=0.0, model_name="gpt-4o-mini"),
        retriever=vectors.as_retriever(),
        return_source_documents=False,
        combine_docs_chain_kwargs={"prompt": prompt_template}
    )
    return chain

def process_query(session_id: str, query: str, chain):
    """사용자의 질문 처리 및 Redis를 통한 대화 기록 관리 (최근 3개의 대화만 저장)"""
    history_key = f"chat_history:{session_id}"

    # Redis에서 최근 대화 기록 가져오기
    chat_history = redis_client.lrange(history_key, -6, -1)  # 최근 3개의 질문-응답 페어 가져오기
    formatted_history = [(chat_history[i], chat_history[i + 1]) for i in range(0, len(chat_history), 2)]

    # GPT-4 호출
    result = chain({"question": query, "chat_history": formatted_history, "who" : session_id})

    # Redis에 새로운 질문-응답 추가
    redis_client.rpush(history_key, query, result["answer"])

    # Redis에 대화 기록이 6개(3개의 질문-응답 페어)를 초과하면 오래된 기록 삭제
    redis_client.ltrim(history_key, -6, -1)

    return result["answer"]
