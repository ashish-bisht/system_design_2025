# Consistent Hashing and Sharding in FastAPI with Postgres 14

## Introduction
This document outlines a prototype implementation of **consistent hashing** and **sharding** in a FastAPI application using **Postgres 14** and **psycopg 3.2.9**. The goal is to learn distributed systems concepts, including scalability patterns and database design, by building a minimal system that shards user data across multiple Postgres databases. The prototype uses a single `main.py` file, incorporates detailed logging for traceability, and supports sharding by `user_id` (primary) with discussion of `region` sharding (secondary). It’s designed for prototyping on a Mac M3 Pro with monitoring via `Activity Monitor`, `htop`, `df -h`, and `netstat`.

**Objective**:
- Implement consistent hashing to distribute user data across three Postgres shards.
- Use detailed logging to trace hashing, shard selection, and database operations.
- Create new Postgres 14 databases for sharding.
- Support basic CRUD operations (create/read user data).
- Analyze performance (CPU, memory, disk, network).
- Explore sharding by `user_id` and `region`.
- Provide a clear, educational reference for distributed systems concepts.

## Key Concepts

### Consistent Hashing
**Analogy**: Imagine a circular dartboard (hash ring) with three zones (shards: `shard_1`, `shard_2`, `shard_3`). Each dart (user data) has a number (`user_id`) hashed to a position on the board. The dart lands in the nearest zone clockwise. Adding or removing a zone only affects darts near that point, not the entire board.

**Definition**:
- Maps data keys (`user_id`) and nodes (shards) to a circular hash space using a hash function (e.g., MD5).
- Assigns data to the nearest node clockwise.
- Uses **virtual nodes** to balance load (each shard has multiple points on the ring).
- Minimizes data movement when nodes are added or removed compared to modulo-based sharding.

**Benefits**:
- **Scalability**: Minimal data reassignment on node changes.
- ** **Load Balancing**: Virtual nodes ensure even distribution.
- **Fault Tolerance**: Data redistributes to nearby nodes on failure.

**Implementation Details**:
- Uses Python’s `hashlib.md5` for hashing.
- Each shard has 100 virtual nodes for load balancing.
- Logs hash values and node assignments for traceability.

### Sharding
**Definition**: Splitting a database into smaller pieces (shards) to distribute data and load across multiple nodes.
- **By `user_id`**: Hash `user_id` for balanced distribution and fast key-based lookups.
- **By `region`**: Group by region for locality but risks uneven load.
- **Hybrid**: Use `user_id` for sharding, index `region` for queries.

**Benefits**:
- Scales storage and compute beyond a single database.
- Improves performance for shard-specific operations.

**Trade-offs**:
- `user_id` sharding is balanced but complicates cross-shard queries (e.g., all users in a region).
- `region` sharding optimizes locality but risks hotspots (e.g., US shard overloaded).

### Psycopg 3.2.9
- **Role**: Modern PostgreSQL adapter for Python, used with SQLAlchemy.
- **Features**: Efficient, supports async connections, modern Python type hints.
- **Integration**: Used in database URLs (`postgresql+psycopg://...`) for Postgres 14.

## System Design

**Architecture**:
- **FastAPI**: Single `main.py` handles HTTP requests, consistent hashing, and database interactions.
- **Postgres 14**: Three shards (`shard_1`, `shard_2`, `shard_3`) as separate databases.
- **Consistent Hashing**: Python implementation with MD5 and virtual nodes.
- **SQLAlchemy**: Manages database connections/queries with `psycopg 3.2.9`.
- **Logging**: Detailed logs for hashing, shard selection, and database operations.
- **Monitoring**: Use `Activity Monitor`, `htop`, `df -h`, `netstat`.

**Data Model**:
- **Table**: `users`
- **Columns**:
  - `user_id` (BIGINT, primary key)
  - `name` (VARCHAR(100))
  - `region` (VARCHAR(50))
  - `email` (VARCHAR(100))

**Sharding Strategy**:
- **Primary**: Hash `user_id` to assign shards.
- **Secondary**: Discuss `region` sharding or indexing for region-based queries.

**Assumptions**:
- Three local Postgres 14 databases simulate shards.
- Postgres user: `postgres` (no password, local setup).
- Minimal prototype for learning, running on Mac M3 Pro.

## Setup Instructions

### Prerequisites
- **Python 3.10+**: Verify: `python3 --version`.
- **Postgres 14**: Verify: `psql --version`. Ensure running: `pg_ctl -D /opt/homebrew/var/postgres status`.
- **pip**: For installing dependencies.

### Create Project Directory
```bash
mkdir consistent_hashing_prototype
cd consistent_hashing_prototype
python3 -m venv venv
source venv/bin/activate
```

### Install Dependencies
```bash
pip install fastapi==0.115.0 uvicorn==0.30.6 sqlalchemy==2.0.35 psycopg==3.2.9 pydantic==2.9.2
pip freeze > requirements.txt
```

### Set Up Postgres 14 Shards
1. **Start Postgres**:
   ```bash
   pg_ctl -D /opt/homebrew/var/postgres start
   ```
   Adjust data directory if needed (check: `pg_config --pgxs`).

2. **Create Databases**:
   ```bash
   psql -U postgres
   ```
   In `psql`:
   ```sql
   CREATE DATABASE shard_1;
   CREATE DATABASE shard_2;
   CREATE DATABASE shard_3;
   \q
   ```

3. **Create Users Table**:
   For each shard:
   ```bash
   psql -U postgres -d shard_1 -c "CREATE TABLE users (user_id BIGINT PRIMARY KEY, name VARCHAR(100), region VARCHAR(50), email VARCHAR(100));"
   psql -U postgres -d shard_2 -c "CREATE TABLE users (user_id BIGINT PRIMARY KEY, name VARCHAR(100), region VARCHAR(50), email VARCHAR(100));"
   psql -U postgres -d shard_3 -c "CREATE TABLE users (user_id BIGINT PRIMARY KEY, name VARCHAR(100), region VARCHAR(50), email VARCHAR(100));"
   ```

4. **Verify Setup**:
   ```bash
   psql -U postgres -c "\l"
   psql -U postgres -d shard_1 -c "\d users"
   ```

**Performance Notes**:
- **Disk**: ~10–50 MB per shard. Monitor: `df -h /opt/homebrew/var/postgres`.
- **Memory**: ~100–300 MB for three databases. Check: `Activity Monitor`.
- **CPU**: Minimal during setup. Monitor: `htop`.

## Implementation Details

The prototype is a single `main.py` file implementing FastAPI, consistent hashing, SQLAlchemy, and detailed logging. Below is a summary of its components.

### Code Structure
- **Imports**: FastAPI, Pydantic, SQLAlchemy, `psycopg 3.2.9`, `hashlib`, `logging`.
- **Logging**:
  - **INFO**: High-level events (e.g., hash ring init, user creation).
  - **DEBUG**: Detailed steps (e.g., hash values, session creation).
  - **ERROR/WARNING**: Issues (e.g., unknown shard, user not found).
  - Format: `%(asctime)s [%(levelname)s] %(message)s`.
- **Database Configuration**:
  - URLs: `postgresql+psycopg://postgres@localhost/shard_<n>`.
  - SQLAlchemy engines and session makers for each shard.
- **Models and Schemas**:
  - SQLAlchemy: `User` model for `users` table.
  - Pydantic: `UserCreate` (input), `UserResponse` (output).
- **Consistent Hashing**:
  - Class: `ConsistentHashing`.
  - Methods: `_hash` (MD5), `_build_ring` (virtual nodes), `get_node` (shard assignment).
  - 100 virtual nodes per shard.
- **Endpoints**:
  - `POST /users/`: Create user, hash `user_id`, store in shard.
  - `GET /users/{user_id}`: Retrieve user by hashing `user_id`.

### Key Code Snippets
**Consistent Hashing**:
```python
class ConsistentHashing:
    def __init__(self, nodes: List[str], virtual_nodes: int = 100):
        self.ring: Dict[int, str] = {}
        self.nodes = nodes
        self.virtual_nodes = virtual_nodes
        logger.info(f"Initializing consistent hashing with nodes: {nodes}, virtual_nodes: {virtual_nodes}")
        self._build_ring()

    def _hash(self, key: str) -> int:
        hash_value = int(hashlib.md5(key.encode()).hexdigest(), 16)
        logger.debug(f"Hashed key '{key}' to {hash_value}")
        return hash_value

    def get_node(self, key: str) -> str:
        key_hash = self._hash(key)
        for node_hash in sorted(self.ring.keys()):
            if node_hash >= key_hash:
                logger.info(f"Key '{key}' (hash: {key_hash}) assigned to node {self.ring[node_hash]}")
                return self.ring[node_hash]
        node = self.ring[min(self.ring.keys())]
        logger.info(f"Key '{key}' (hash: {key_hash}) wrapped around to node {node}")
        return node
```

**Create User Endpoint**:
```python
@app.post("/users/", response_model=UserResponse)
async def create_user(user: UserCreate):
    logger.info(f"Received request to create user: {user.dict()}")
    shard = consistent_hash.get_node(str(user.user_id))
    session = get_session(shard)
    try:
        db_user = User(**user.dict())
        session.add(db_user)
        logger.debug(f"Added user {user.user_id} to session for shard {shard}")
        session.commit()
        logger.info(f"Committed user {user.user_id} to shard {shard}")
        session.refresh(db_user)
        return db_user
    except Exception as e:
        session.rollback()
        logger.error(f"Failed to create user {user.user_id} in shard {shard}: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        session.close()
        logger.debug(f"Closed session for shard {shard}")
```

### Performance Implications
- **CPU**:
  - Hashing: ~1 µs per key.
  - Queries: ~1–5 ms per request.
  - Monitor: `htop` (expect <10% CPU for 10–100 requests/sec).
- **Memory**:
  - FastAPI: ~50 MB.
  - SQLAlchemy: ~15–30 MB (connection pools).
  - Postgres: ~100–300 MB (three shards).
  - Monitor: `Activity Monitor`.
- **Disk**:
  - ~10–50 MB per shard.
  - Writes increase I/O.
  - Monitor: `df -h /opt/homebrew/var/postgres`.
- **Network**:
  - Local Postgres connections: <1 ms.
  - 1–5 connections per shard.
  - Monitor: `netstat -an | grep 5432`.
- **Psycopg 3.2.9**:
  - Optimized connection handling.
  - Slightly lower memory usage than `psycopg2`.

## Running the Application

1. **Start FastAPI**:
   ```bash
   uvicorn main:app --host 0.0.0.0 --port 8000
   ```

2. **Test Endpoints**:
   - **Create User**:
     ```bash
     curl -X POST http://localhost:8000/users/ \
     -H "Content-Type: application/json" \
     -d '{"user_id": 1, "name": "Alice", "region": "US", "email": "alice@example.com"}'
     ```
   - **Get User**:
     ```bash
     curl http://localhost:8000/users/1
     ```
   - **Expected Output** (JSON):
     ```json
     {"user_id": 1, "name": "Alice", "region": "US", "email": "alice@example.com"}
     ```

3. **Check Logs**:
   Example logs:
   ```
   2025-06-02 13:25:01,123 [INFO] Initializing consistent hashing with nodes: ['shard_1', 'shard_2', 'shard_3'], virtual_nodes: 100
   2025-06-02 13:25:01,124 [DEBUG] Added virtual node shard_1#0 for shard_1 at hash 123456789...
   2025-06-02 13:25:01,150 [INFO] Hash ring built with 300 virtual nodes
   2025-06-02 13:25:02,200 [INFO] Received request to create user: {'user_id': 1, 'name': 'Alice', 'region': 'US', 'email': 'alice@example.com'}
   2025-06-02 13:25:02,201 [DEBUG] Hashed key '1' to 987654321...
   2025-06-02 13:25:02,202 [INFO] Key '1' (hash: 987654321...) assigned to node shard_2
   2025-06-02 13:25:02,203 [DEBUG] Creating session for shard: shard_2
   2025-06-02 13:25:02,204 [DEBUG] Added user 1 to session for shard shard_2
   2025-06-02 13:25:02,205 [INFO] Committed user 1 to shard shard_2
   2025-06-02 13:25:02,206 [DEBUG] Closed session for shard shard_2
   ```

4. **Verify Data**:
   ```bash
   psql -U postgres -d shard_1 -c "SELECT * FROM users;"
   psql -U postgres -d shard_2 -c "SELECT * FROM users;"
   psql -U postgres -d shard_3 -c "SELECT * FROM users;"
   ```

## Sharding Strategies

### Sharding by `user_id`
- **Implementation**: Hash `user_id` to assign shards (current prototype).
- **Pros**:
  - Balanced distribution (assuming sequential/random `user_id`).
  - Fast key-based lookups (e.g., `GET /users/{user_id}`).
  - Minimal data movement when adding/removing shards.
- **Cons**:
  - Region-based queries (e.g., “all users in US”) require querying all shards.
- **Logs**: Trace hash values and shard assignments (e.g., `Key '1' assigned to shard_2`).
- **Performance**:
  - **CPU**: Hashing negligible, queries fast.
  - **Disk**: Balanced writes. Monitor: `df -h`.
  - **Network**: Single shard per request, minimal latency.

### Sharding by `region`
- **Implementation**:
  Modify endpoints to hash `region`:
  ```python
  shard = consistent_hash.get_node(user.region)  # POST
  shard = consistent_hash.get_node(region)       # GET, needs region input
  ```
- **Pros**:
  - Optimizes region-specific queries (e.g., analytics by region).
  - Aligns with geographic database placement (e.g., US shard in US data center).
- **Cons**:
  - Uneven distribution (e.g., US has more users than a small region).
  - Complicates `user_id`-based lookups (requires metadata).
- **Logs**: Would show region hashing (e.g., `Key 'US' assigned to shard_1`).
- **Performance**:
  - **CPU**: Same hashing overhead.
  - **Disk**: Risk of hotspots (e.g., US shard grows faster). Monitor: `df -h`.
  - **Network**: Efficient for region queries, but `user_id` lookups may need additional hops.

### Hybrid Approach
- **Primary**: `user_id` sharding (current implementation).
- **Region Queries**: Add index on `region` in each shard:
  ```bash
  psql -U postgres -d shard_1 -c "CREATE INDEX idx_users_region ON users (region);"
  ```
  Repeat for `shard_2`, `shard_3`.
- **Future**: Use Postgres 17 + Citus for distributed queries by `region`.
- **Performance**:
  - **Memory**: Indexes add ~10–50 MB per shard. Monitor: `Activity Monitor`.
  - **Disk**: Indexes increase storage. Monitor: `df -h`.
  - **Logs**: Query performance improves (monitor query times).

## Monitoring Performance

Use your tools to monitor the system:

1. **CPU**:
   ```bash
   htop
   ```
   - Processes: `python` (FastAPI), `postgres`.
   - Expect <10% CPU for 10–100 requests/sec.
   - Hashing and queries are lightweight.

2. **Memory**:
   - Tool: `Activity Monitor`.
   - FastAPI: ~50 MB.
   - SQLAlchemy: ~15–30 MB (connection pools).
   - Postgres: ~100–300 MB (three shards).

3. **Disk**:
   ```bash
   df -h /opt/homebrew/var/postgres
   ```
   - Ensure >1 GB free per shard.
   - Writes increase I/O during inserts.

4. **Network**:
   ```bash
   netstat -an | grep 5432
   ```
   - Expect 1–5 connections per shard (SQLAlchemy pool).
   - Local connections: <1 ms latency.

**Logs**:
- Help identify bottlenecks (e.g., slow queries, hashing delays).
- Example: `Failed to create user 1 in shard_2: duplicate key` indicates a conflict.

## Scaling and Fault Tolerance

### Adding a Shard
1. **Create New Shard**:
   ```bash
   psql -U postgres -c "CREATE DATABASE shard_4;"
   psql -U postgres -d shard_4 -c "CREATE TABLE users (user_id BIGINT PRIMARY KEY, name VARCHAR(100), region VARCHAR(50), email VARCHAR(100));"
   ```

2. **Update `main.py`**:
   ```python
   DATABASE_URLS = {
       "shard_1": "postgresql+psycopg://postgres@localhost/shard_1",
       "shard_2": "postgresql+psycopg://postgres@localhost/shard_2",
       "shard_3": "postgresql+psycopg://postgres@localhost/shard_3",
       "shard_4": "postgresql+psycopg://postgres@localhost/shard_4",
   }
   SHARDS = ["shard_1", "shard_2", "shard_3", "shard_4"]
   ```

3. **Migrate Data**:
   - Consistent hashing moves ~1/N data (N = number of shards).
   - Example migration script:
     ```python
     from main import get_session, ConsistentHashing, User
     old_shards = ["shard_1", "shard_2", "shard_3"]
     new_shards = ["shard_1", "shard_2", "shard_3", "shard_4"]
     old_hash = ConsistentHashing(nodes=old_shards)
     new_hash = ConsistentHashing(nodes=new_shards)
     for shard in old_shards:
         session = get_session(shard)
         users = session.query(User).all()
         for user in users:
             new_shard = new_hash.get_node(str(user.user_id))
             if new_shard != shard:
                 new_session = get_session(new_shard)
                 new_session.add(user)
                 new_session.commit()
                 session.delete(user)
                 session.commit()
         session.close()
     ```

4. **Performance**:
   - **CPU**: Migration increases usage temporarily. Monitor: `htop`.
   - **Disk**: Data movement increases I/O. Monitor: `df -h`.
   - **Network**: Local migration is fast. Monitor: `netstat`.

### Handling Node Failure
- **Scenario**: A shard (e.g., `shard_2`) fails.
- **Action**:
  1. Remove from `SHARDS` and rebuild hash ring.
  2. Data reassigns to other shards.
  3. Use Postgres primary-replica setup for data recovery.
- **Logs**: Show reassignment (e.g., `Key '1' reassigned to shard_3`).

## Learning Takeaways

- **Consistent Hashing**:
  - Dynamically maps data to nodes, minimizing reshuffling.
  - Virtual nodes improve balance but increase memory (~10–100 KB for 300 virtual nodes).
  - MD5 is simple; consider SHA-256 for production.
  - Logs provide visibility into hash distribution.
- **Sharding**:
  - `user_id` sharding is balanced and simple but lacks locality for region queries.
  - `region` sharding optimizes regional queries but risks imbalance.
  - Indexes or materialized views help with secondary keys.
- **Distributed Systems**:
  - Sharding scales storage/compute but complicates cross-shard queries.
  - Consistent hashing enhances fault tolerance and scalability.
  - Logging is critical for debugging distributed systems.
- **Psycopg 3.2.9**:
  - Efficient, modern PostgreSQL adapter.
  - Seamless with SQLAlchemy, supports async queries.
  - Slightly better memory efficiency than `psycopg2`.
- **Performance**:
  - CPU: Hashing is negligible; queries dominate.
  - Memory: Postgres and connection pools are primary consumers.
  - Disk: Monitor I/O for write-heavy workloads.
  - Network: Local connections are low-latency.

## Next Steps

1. **Test Under Load**:
   - Install `locust`:
     ```bash
     pip install locust
     ```
   - Create `locustfile.py`:
     ```python
     from locust import HttpUser, taskhint: task
     class UserTest(HttpUser):
         @task
         def create_user(self):
             self.client.post("/users/", json={"user_id": 123, "name": "Test", "region": "US", "email": "test@example.com"})
     ```
   - Run: `locust -f locustfile.py`.
   - Monitor: `htop`, `Activity Monitor`, `df -h`, `netstat`.

2. **Add Caching with Redis**:
   - Install: `brew install redis; redis-server`.
   - Cache user data:
     ```python
     import redis
     r = redis.Redis(host='localhost', port=6379)
     def get_user(user_id: int):
         cached = r.get(f"user:{user_id}")
         if cached:
             return UserResponse.parse_raw(cached)
         # Query Postgres, cache result
     ```

3. **Explore Postgres 17 + Citus**:
   - Migrate to Citus for distributed queries (e.g., region aggregates).
   - Citus automates sharding but is less educational for learning manual consistent hashing.

4. **Visualize Shard Distribution**:
   - Query counts:
     ```bash
     for shard in shard_1 shard_2 shard_3; do
         echo "$shard: $(psql -U postgres -d $shard -t -c 'SELECT count(*) FROM users;')"
     done
     ```

5. **Simulate Failures**:
   - Stop a shard: `psql -U postgres -c "SELECT pg_terminate_backend(pg_stat_activity.pid) FROM pg_stat_activity WHERE pg_stat_activity.datname = 'shard_2';"`.
   - Test reassignment via logs.

## Alternative Considerations

- **Why Postgres 14, Not Citus?**: Manual sharding teaches consistent hashing mechanics. Citus abstracts this, reducing learning value for prototyping.
- **Why Not Cassandra?**: Cassandra has built-in consistent hashing, but Postgres leverages your existing setup and SQL familiarity.
- **Region Sharding Challenges**: Requires metadata (e.g., `region_to_shard` table), complicating `user_id` lookups.

## Conclusion
This prototype provides a hands-on way to master **consistent hashing** and **sharding** in a distributed system. By implementing a single-file FastAPI app with Postgres 14 and psycopg 3.2.9, you’ve learned:
- How to distribute data across shards using consistent hashing.
- The trade-offs of sharding by `user_id` vs. `region`.
- The importance of detailed logging for traceability.
- Performance monitoring with `htop`, `Activity Monitor`, `df -h`, and `netstat`.
- Scalability and fault tolerance strategies.

For further exploration, consider load testing, caching, or migrating to Citus. Refer to the logs and this document to revisit the implementation and solidify your understanding.

**Happy learning, Ash!**