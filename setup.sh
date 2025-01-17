#!/bin/bash

# 프로젝트 이름 및 디렉터리
PROJECT_NAME="fastapi_chatbot_project"
APP_DIR="$PROJECT_NAME/app"

echo "🚀 FastAPI 기반 챗봇 프로젝트를 설정합니다..."

# 1. 프로젝트 디렉터리 생성
mkdir -p $APP_DIR

# 2. `main.py` 생성
echo "🔧 main.py 생성 중..."
cat <<EOL > $APP_DIR/main.py
from fastapi import FastAPI
from app.models import QueryRequest, QueryResponse
from app.services import process_query

app = FastAPI()

@app.get("/")
async def root():
    return {"message": "Welcome to the FastAPI Chatbot"}

@app.post("/query", response_model=QueryResponse)
async def query_endpoint(request: QueryRequest):
    response = process_query(request.session_id, request.query)
    return QueryResponse(response=response)
EOL

# 3. `models.py` 생성
echo "🔧 models.py 생성 중..."
cat <<EOL > $APP_DIR/models.py
from pydantic import BaseModel

class QueryRequest(BaseModel):
    session_id: str
    query: str

class QueryResponse(BaseModel):
    response: str
EOL

# 4. `services.py` 생성
echo "🔧 services.py 생성 중..."
cat <<EOL > $APP_DIR/services.py
import os
from redis import Redis
import openai
from dotenv import load_dotenv

load_dotenv()

openai.api_key = os.getenv("OPENAI_API_KEY")

redis_client = Redis(
    host=os.getenv("REDIS_HOST", "localhost"),
    port=int(os.getenv("REDIS_PORT", 6379)),
    decode_responses=True
)

def process_query(session_id: str, query: str) -> str:
    history_key = f"chat_history:{session_id}"
    chat_history = redis_client.lrange(history_key, 0, -1)
    formatted_history = [{"role": "user" if i % 2 == 0 else "assistant", "content": h} for i, h in enumerate(chat_history)]

    formatted_history.append({"role": "user", "content": query})

    try:
        response = openai.ChatCompletion.create(
            model="gpt-4",
            messages=formatted_history
        )
        answer = response["choices"][0]["message"]["content"]
        redis_client.rpush(history_key, query, answer)
        return answer
    except Exception as e:
        return f"Error: {str(e)}"
EOL

# 5. `requirements.txt` 생성
echo "🔧 requirements.txt 생성 중..."
cat <<EOL > $APP_DIR/requirements.txt
fastapi
uvicorn
redis
openai
python-dotenv
EOL

# 6. `.env` 파일 생성
echo "🔑 환경 변수 파일 생성 중..."
cat <<EOL > $PROJECT_NAME/.env
OPENAI_API_KEY=your_openai_api_key
REDIS_HOST=redis
REDIS_PORT=6379
EOL

# 7. `Dockerfile` 생성
echo "🐳 Dockerfile 생성 중..."
cat <<EOL > $PROJECT_NAME/Dockerfile
FROM python:3.9-slim

WORKDIR /app

COPY app/requirements.txt requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

COPY ./app ./app

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
EOL

# 8. `docker-compose.yml` 생성
echo "🔧 docker-compose.yml 생성 중..."
cat <<EOL > $PROJECT_NAME/docker-compose.yml
version: "3.8"

services:
  backend:
    build:
      context: .
    ports:
      - "8000:8000"
    environment:
      - OPENAI_API_KEY=\${OPENAI_API_KEY}
      - REDIS_HOST=redis
      - REDIS_PORT=6379

  redis:
    image: redis:6.2
    container_name: redis
    ports:
      - "6379:6379"
EOL

# 9. 실행 안내 메시지 출력
echo "✅ FastAPI 기반 챗봇 프로젝트 설정이 완료되었습니다!"
echo "📂 프로젝트 디렉터리: $PROJECT_NAME"
echo "🚀 실행 방법:"
echo "   1. 프로젝트 디렉터리로 이동: cd $PROJECT_NAME"
echo "   2. Docker Compose 실행: docker-compose up --build"
