from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from app.services import check_pdf_changes, initialize_chain, process_query
import os
from fastapi.responses import StreamingResponse


# FastAPI 앱 초기화
app = FastAPI()

origins = ["*"]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],  # 모든 HTTP 메서드 허용
    allow_headers=["*"],  # 모든 헤더 허용
)

# PDF 파일 경로
PDF_DIR = "app/data/"
VECTOR_DB_PATH = "app/faiss_index"

# PDF 변경 확인 및 데이터베이스 초기화
try:
    documents = None
    if not os.path.exists(f"{VECTOR_DB_PATH}/index.faiss"):
        print("FAISS database not found. Creating one...")
        documents = check_pdf_changes(PDF_DIR)
        if documents is None:
            raise FileNotFoundError(
                "No PDFs found to create FAISS database. Ensure you have PDF files in the specified directory."
            )
    else:
        documents = check_pdf_changes(PDF_DIR)

    chain = initialize_chain(documents)
except Exception as e:
    print(f"Error during initialization: {e}")
    chain = None

# 요청 모델
class QueryRequest(BaseModel):
    session_id: str
    query: str


@app.get("/")
async def root():
    return {"message": "Welcome to the FastAPI Chatbot"}

@app.post("/chat")
async def chat_endpoint(request: QueryRequest):
    """사용자의 질문을 받아 GPT-4 응답 스트리밍 반환"""
    print(request.session_id)
    print(request.query)
    if chain is None:
        raise HTTPException(status_code=500, detail="Chain initialization failed.")

    try:
        response_stream = process_query(request.session_id, request.query, chain)
        return StreamingResponse(response_stream, media_type="text/plain")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
