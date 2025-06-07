/
 # PostgreSQL Replication with FastAPI on Mac M3 Pro: A Comprehensive Guide

This article guides you through setting up **PostgreSQL 14.18** replication (asynchronous) on a **Mac M3 Pro**, integrating it with a **FastAPI** application using **psycopg 3.2.9** for writes to the primary database and reads from the replica. Designed for a beginner aiming to master system design, it covers every step, from configuring replication to building a FastAPI app with detailed logging. You’ll learn how to monitor memory, CPU, disk, and network usage, troubleshoot issues, and extend the setup with tools like **Redis** or **Cassandra**.

## Introduction

Database replication creates a live copy of a primary database (leader) on one or more replicas (followers) to improve read performance, availability, and scalability. In this setup:
- **Primary** (`~/pg14_primary`, port 5432): Handles writes (e.g., `INSERT`).
- **Replica** (`~/pg14_replica`, port 5433): Handles reads (e.g., `SELECT`).
- **Replication**: Asynchronous, where the primary commits writes without waiting for the replica.
- **FastAPI**: A Python web framework routes writes to the primary and reads to the replica.
- **Logging**: Detailed logs for HTTP requests, database operations, and replication.

This guide assumes you’re using a **Mac M3 Pro** with **PostgreSQL 14.18**, **FastAPI**, and **psycopg 3.2.9** installed via Homebrew and `pip`.

## System Design Considerations

Replication and FastAPI impact **memory**, **CPU**, **disk**, and **network**:

- **Memory**:
  - Primary stores write-ahead logs (WAL) in memory before sending to replicas.
  - Replica buffers incoming WAL.
  - FastAPI and `psycopg3` use minimal memory for async operations.
  - Your M3 Pro’s 18–36 GB RAM is ample for this local prototype.

- **CPU**:
  - Primary processes writes; replica applies WAL.
  - FastAPI’s async I/O is CPU-efficient.
  - M3 Pro’s 11–12 cores handle both easily.

- **Disk**:
  - Primary writes data and WAL to `~/pg14_primary`.
  - Replica applies WAL to `~/pg14_replica`.
  - Your SSD ensures fast I/O.

- **Network**:
  - WAL is sent over localhost (negligible latency).
  - FastAPI communicates with databases locally, minimizing network overhead.

## Step-by-Step Setup

### Step 1: Configure PostgreSQL Replication

1. **Initialize Data Directories**:
   ```bash
   mkdir -p ~/pg14_primary ~/pg14_replica
   /opt/homebrew/opt/postgresql@14/bin/initdb -D ~/pg14_primary
   /opt/homebrew/opt/postgresql@14/bin/initdb -D ~/pg14_replica
   ```

2. **Configure Primary** (`~/pg14_primary/postgresql.conf`):
   ```conf
   listen_addresses = 'localhost'
   port = 5432
   wal_level = replica
   max_wal_senders = 10
   wal_keep_size = 64
   log_min_messages = debug1
   log_replication_commands = on
   log_line_prefix = '%m [%p] %u@%d '
   log_connections = on
   log_disconnections = on
   log_statement = 'all'
   ```

3. **Configure Primary Authentication** (`~/pg14_primary/pg_hba.conf`):
   ```conf
   host    all             postgres        127.0.0.1/32    md5
   host    replication     replicator      127.0.0.1/32    md5
   ```

4. **Start Primary**:
   ```bash
   /opt/homebrew/opt/postgresql@14/bin/pg_ctl -D ~/pg14_primary -l ~/pg14_primary.log start
   ```

5. **Create Roles**:
   ```bash
   /opt/homebrew/opt/postgresql@14/bin/psql -p 5432 -d postgres
   ```
   ```sql
   CREATE ROLE replicator WITH REPLICATION PASSWORD 'replicator' LOGIN;
   CREATE ROLE postgres WITH SUPERUSER LOGIN PASSWORD 'postgres';
   ```

6. **Copy Primary to Replica**:
   ```bash
   rm -rf ~/pg14_replica/*
   /opt/homebrew/opt/postgresql@14/bin/pg_basebackup -h localhost -p 5432 -U replicator -D ~/pg14_replica --wal-method=stream
   ```

7. **Configure Replica** (`~/pg14_replica/postgresql.conf`):
   ```conf
   listen_addresses = 'localhost'
   port = 5433
   hot_standby = on
   log_min_messages = debug1
   log_line_prefix = '%m [%p] %u@%d '
   log_connections = on
   log_disconnections = on
   log_statement = 'all'
   primary_conninfo = 'host=localhost port=5432 user=replicator password=replicator'
   restore_command = ''
   ```

8. **Create Standby Signal**:
   ```bash
   touch ~/pg14_replica/standby.signal
   ```

9. **Start Replica**:
   ```bash
   /opt/homebrew/opt/postgresql@14/bin/pg_ctl -D ~/pg14_replica -l ~/pg14_replica.log start
   ```

10. **Test Replication**:
    On primary:
    ```bash
    /opt/homebrew/opt/postgresql@14/bin/psql -h localhost -p 5432 -U postgres -d postgres
    ```
    ```sql
    CREATE DATABASE testdb;
    \c testdb
    CREATE TABLE users (id SERIAL PRIMARY KEY, name TEXT);
    INSERT INTO users (name) VALUES ('Bob');
    ```
    On replica:
    ```bash
    /opt/homebrew/opt/postgresql@14/bin/psql -h localhost -p 5433 -U postgres -d testdb
    ```
    ```sql
    SELECT * FROM users;
    ```
    Expected:
    ```
    id | name
    ----+------
     1 | Bob
    ```

11. **Check Replication Status**:
    ```sql
    SELECT * FROM pg_stat_replication;
    ```
    Look for `state = streaming`, `sync_state = async`.

---

### Step 2: Build FastAPI App with Logging

1. **Install Dependencies**:
   ```bash
   pip install fastapi uvicorn "psycopg[binary,pool]>=3.2.9"
   ```

2. **Create FastAPI App**:
   ```bash
   mkdir -p ~/pg14_app && cd ~/pg14_app
   nano main.py
   ```
   Paste:
   ```python
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
   ```

3. **Run FastAPI**:
   ```bash
   cd ~/pg14_app
   uvicorn main:app --host 0.0.0.0 --port 8000
   ```

4. **Test Endpoints**:
   - Write:
     ```bash
     curl -X POST "http://localhost:8000/users" -H "Content-Type: application/json" -d '{"name": "Grace"}'
     ```
     Expected:
     ```json
     {"id": 8, "name": "Grace"}
     ```
   - Read:
     ```bash
     curl http://localhost:8000/users
     ```
     Expected:
     ```json
     [
         {"id": 1, "name": "Bob"},
         {"id": 2, "name": "Charlie"},
         {"id": 3, "name": "Charlie"},
         {"id": 4, "name": "Charlie"},
         {"id": 5, "name": "Charlie"},
         {"id": 6, "name": "Eve"},
         {"id": 7, "name": "Frank"},
         {"id": 8, "name": "Grace"}
     ]
     ```

5. **Check Logs**:
   - **FastAPI** (`~/pg14_app/app.log`):
     ```bash
     cat ~/pg14_app/app.log
     ```
     Example:
     ```
     2025-06-01 23:00:00,123 [INFO] fastapi_app: Starting FastAPI application
     2025-06-01 23:00:00,124 [INFO] fastapi_app: Database connection pools opened
     2025-06-01 23:00:01,125 [INFO] fastapi_app: Request started: POST /users from 127.0.0.1
     2025-06-01 23:00:01,126 [DEBUG] fastapi_app: Creating user with name: Grace
     2025-06-01 23:00:01,127 [INFO] fastapi_app: Inserted user id=8 name=Grace duration=0.002s
     2025-06-01 23:00:01,128 [INFO] fastapi_app: Request completed: POST /users status=200 duration=0.003s
     ```
   - **Primary** (`~/pg14_primary.log`):
     ```bash
     cat ~/pg14_primary.log
     ```
     Look for:
     ```
     LOG:  statement: INSERT INTO users (name) VALUES ('Grace') RETURNING id, name
     ```
   - **Replica** (`~/pg14_replica.log`):
     ```bash
     cat ~/pg14_replica.log
     ```
     Look for:
     ```
     LOG:  statement: SELECT id, name FROM users
     ```

---

## Troubleshooting

1. **Replication Issues**:
   - Check status:
     ```sql
     SELECT * FROM pg_stat_replication;
     ```
   - Check lag:
     ```sql
     SELECT pg_last_wal_receive_lsn(), pg_last_wal_replay_lsn();
     ```
   - Ensure replica is running:
     ```bash
     /opt/homebrew/opt/postgresql@14/bin/pg_ctl -D ~/pg14_replica status
     ```

2. **FastAPI Errors**:
   - If `POST` fails, verify `testdb.users`:
     ```sql
     \c testdb
     \dt
     ```
   - If `GET` fails, test replica:
     ```bash
     /opt/homebrew/opt/postgresql@14/bin/psql -h localhost -p 5433 -U postgres -d testdb
     ```

3. **Authentication**:
   - Check `pg_hba.conf`:
     ```bash
     nano ~/pg14_primary/pg_hba.conf
     nano ~/pg14_replica/pg_hba.conf
     ```
     Ensure:
     ```conf
     host    all             postgres        127.0.0.1/32    md5
     ```

4. **Logs**:
   - FastAPI: `~/pg14_app/app.log`
   - Primary: `~/pg14_primary.log`
   - Replica: `~/pg14_replica.log`

---

## Next Steps

1. **Synchronous Replication**:
   - Enable by setting `synchronous_standby_names = 'replica1'` in `~/pg14_primary/postgresql.conf` and `application_name = replica1` in `~/pg14_replica/postgresql.conf`.
   - Test:
     ```sql
     INSERT INTO users (name) VALUES ('Dave');
     ```

2. **Redis Integration**:
   - Use Redis (installed via `brew`) for caching `GET /users` results:
     ```bash
     redis-server
     ```
     Update FastAPI to cache with `redis-py`.

3. **Cassandra Integration**:
   - Use Cassandra (installed via `brew`) for additional storage, e.g., user activity logs.
     Install driver:
     ```bash
     pip install cassandra-driver
     ```

4. **Advanced FastAPI**:
   - Add authentication (e.g., JWT).
   - Implement rate limiting.
   - Use dependency injection for database connections.

5. **Monitoring**:
   - Use Prometheus for metrics.
   - Visualize logs with Grafana Loki.

---



This setup demonstrates a robust PostgreSQL replication system with FastAPI, leveraging your Mac M3 Pro’s capabilities. You’ve learned to configure asynchronous replication, build a FastAPI app with `psycopg 3.2.9`, and implement detailed logging. Use this article to review, troubleshoot, and extend your prototype with Redis, Cassandra, or advanced features. Happy learning!
