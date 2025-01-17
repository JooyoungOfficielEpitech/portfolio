FROM node:18-alpine

# 필수 패키지 설치
RUN apk add --no-cache python3 build-base

WORKDIR /app

COPY package.json package-lock.json ./
RUN npm install

COPY . .

EXPOSE 3000

CMD ["npm", "run", "dev", "--", "--host", "0.0.0.0"]
