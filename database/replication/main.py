from fastapi import FastAPI, HTTPException, Request
from pydantic import BaseModel
import psycopg
from psycopg_pool import AsyncConnectionPool
import logging
import time
from contextlib import asynccontextmanager
from typing import Dict, Any
import traceback

# Configure logging
logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[
        logging.FileHandler("app.log"),  # Log to file
        logging.StreamHandler()  # Log to console
    ]
)
logger = logging.getLogger("fastapi_app")

app = FastAPI()

# Connection pools for primary and replica
primary_pool = AsyncConnectionPool(
    conninfo="host=localhost port=5432 dbname=testdb user=postgres password=postgres",
    max_size=10
)
replica_pool = AsyncConnectionPool(
    conninfo="host=localhost port=5433 dbname=testdb user=postgres password=postgres",
    max_size=10
)

# Pydantic model for request validation
class UserCreate(BaseModel):
    name: str

# Middleware to log requests
@app.middleware("http")
async def log_requests(request: Request, call_next):
    start_time = time.time()
    client_ip = request.client.host
    method = request.method
    path = request.url.path
    
    logger.info(f"Request started: {method} {path} from {client_ip}")
    
    try:
        response = await call_next(request)
        duration = time.time() - start_time
        logger.info(f"Request completed: {method} {path} status={response.status_code} duration={duration:.3f}s")
        return response
    except Exception as e:
        duration = time.time() - start_time
        logger.error(f"Request failed: {method} {path} error={str(e)} duration={duration:.3f}s")
        logger.debug(f"Stack trace: {traceback.format_exc()}")
        raise

# Initialize pools on startup
@app.on_event("startup")
async def startup_event():
    logger.info("Starting FastAPI application")
    try:
        await primary_pool.open()
        await replica_pool.open()
        logger.info("Database connection pools opened")
    except Exception as e:
        logger.error(f"Failed to open connection pools: {str(e)}")
        logger.debug(f"Stack trace: {traceback.format_exc()}")
        raise

# Close pools on shutdown
@app.on_event("shutdown")
async def shutdown_event():
    logger.info("Shutting down FastAPI application")
    try:
        await primary_pool.close()
        await replica_pool.close()
        logger.info("Database connection pools closed")
    except Exception as e:
        logger.error(f"Failed to close connection pools: {str(e)}")
        logger.debug(f"Stack trace: {traceback.format_exc()}")

# POST endpoint to create a user (writes to primary)
@app.post("/users", response_model=dict)
async def create_user(user: UserCreate):
    logger.debug(f"Creating user with name: {user.name}")
    start_time = time.time()
    
    async with primary_pool.connection() as conn:
        try:
            async with conn.cursor() as cur:
                await cur.execute(
                    "INSERT INTO users (name) VALUES (%s) RETURNING id, name",
                    (user.name,)
                )
                result = await cur.fetchone()
                await conn.commit()
                duration = time.time() - start_time
                logger.info(f"Inserted user id={result[0]} name={result[1]} duration={duration:.3f}s")
                return {"id": result[0], "name": result[1]}
        except psycopg.Error as e:
            await conn.rollback()
            duration = time.time() - start_time
            logger.error(f"Insert failed: {str(e)} duration={duration:.3f}s")
            logger.debug(f"Stack trace: {traceback.format_exc()}")
            raise HTTPException(status_code=400, detail=f"Insert failed: {str(e)}")

# GET endpoint to list users (reads from replica)
@app.get("/users", response_model=list[dict])
async def get_users():
    logger.debug("Fetching all users")
    start_time = time.time()
    
    async with replica_pool.connection() as conn:
        try:
            async with conn.cursor(row_factory=psycopg.rows.dict_row) as cur:
                await cur.execute("SELECT id, name FROM users")
                users = await cur.fetchall()
                duration = time.time() - start_time
                logger.info(f"Fetched {len(users)} users duration={duration:.3f}s")
                return users
        except psycopg.Error as e:
            duration = time.time() - start_time
            logger.error(f"Query failed: {str(e)} duration={duration:.3f}s")
            logger.debug(f"Stack trace: {traceback.format_exc()}")
            raise HTTPException(status_code=400, detail=f"Query failed: {str(e)}")