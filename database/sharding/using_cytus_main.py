from fastapi import FastAPI
import psycopg
from psycopg.rows import dict_row

app = FastAPI()

def get_db_connection():
    return psycopg.connect(
        host="localhost",
        port=5434,  # Update to 5436 if coordinator port changed
        user="postgres",
        dbname="testdb",
        row_factory=dict_row
    )

@app.get("/users/{user_id}")
async def get_user(user_id: int):
    with get_db_connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute("SELECT * FROM users WHERE user_id = %s", (user_id,))
            user = cursor.fetchone()
    return user or {}

@app.post("/users")
async def create_user(name: str, email: str, created_at: str):
    with get_db_connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute(
                "INSERT INTO users (name, email, created_at) VALUES (%s, %s, %s) RETURNING user_id",
                (name, email, created_at)
            )
            user_id = cursor.fetchone()[0]["user_id"]
            conn.commit()
    return {"user_id": user_id, "name": name, "email": email, "created_at": created_at}

@app.get("/users/{user_id}/shard")
async def get_user_shard(user_id: int):
    try:
        with get_db_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT shardid
                    FROM pg_dist_shard
                    WHERE logicalrelid = 'users'::regclass
                    AND shardminvalue::bigint <= hashtext(%s)::bigint
                    AND shardmaxvalue::bigint >= hashtext(%s)::bigint
                    """,
                    (str(user_id), str(user_id))
                )
                shard = cursor.fetchone()
                if not shard:
                    return {"error": "Shard not found"}
                shard_id = shard["shardid"]

                cursor.execute(
                    """
                    SELECT nodename, nodeport
                    FROM citus_shards
                    WHERE table_name = 'users' AND shardid = %s
                    """,
                    (shard_id,)
                )
                node = cursor.fetchone()
                return {
                    "user_id": user_id,
                    "shard_id": shard_id,
                    "node": f"{node['nodename']}:{node['nodeport']}" if node else "Unknown"
                }
    except psycopg.Error as e:
        return {"error": str(e)}