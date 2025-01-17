from redis import Redis

try:
    redis_client = Redis(host="localhost", port=6379)
    redis_client.ping()
    print("Connected to Redis")
except Exception as e:
    print("Redis connection error:", e)
