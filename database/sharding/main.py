import hashlib
import logging
from typing import Dict, List
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from sqlalchemy import create_engine, Column, BigInteger, String
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session

# Configure detailed logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler()]
)
logger = logging.getLogger(__name__)

# FastAPI app
app = FastAPI()

# Database configuration with psycopg
DATABASE_URLS = {
    "shard_1": "postgresql+psycopg://postgres@localhost/shard_1",
    "shard_2": "postgresql+psycopg://postgres@localhost/shard_2",
    "shard_3": "postgresql+psycopg://postgres@localhost/shard_3",
}
ENGINES = {name: create_engine(url) for name, url in DATABASE_URLS.items()}
SESSION_MAKERS = {name: sessionmaker(bind=engine) for name, engine in ENGINES.items()}
Base = declarative_base()

# SQLAlchemy model
class User(Base):
    __tablename__ = "users"
    user_id = Column(BigInteger, primary_key=True)
    name = Column(String(100))
    region = Column(String(50))
    email = Column(String(100))

# Pydantic schemas
class UserCreate(BaseModel):
    user_id: int
    name: str
    region: str
    email: str

class UserResponse(BaseModel):
    user_id: int
    name: str
    region: str
    email: str

# Consistent hashing implementation
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

    def _build_ring(self):
        for node in self.nodes:
            for i in range(self.virtual_nodes):
                virtual_node = f"{node}#{i}"
                hash_value = self._hash(virtual_node)
                self.ring[hash_value] = node
                logger.debug(f"Added virtual node {virtual_node} for {node} at hash {hash_value}")
        logger.info(f"Hash ring built with {len(self.ring)} virtual nodes")

    def get_node(self, key: str) -> str:
        if not self.ring:
            logger.error("No nodes in the ring")
            raise ValueError("No nodes in the ring")
        key_hash = self._hash(key)
        for node_hash in sorted(self.ring.keys()):
            if node_hash >= key_hash:
                logger.info(f"Key '{key}' (hash: {key_hash}) assigned to node {self.ring[node_hash]} (node_hash: {node_hash})")
                return self.ring[node_hash]
        node = self.ring[min(self.ring.keys())]
        logger.info(f"Key '{key}' (hash: {key_hash}) wrapped around to node {node}")
        return node

# Initialize consistent hashing
SHARDS = ["shard_1", "shard_2", "shard_3"]
consistent_hash = ConsistentHashing(nodes=SHARDS, virtual_nodes=100)

# Database session helper
def get_session(shard: str) -> Session:
    if shard not in SESSION_MAKERS:
        logger.error(f"Unknown shard: {shard}")
        raise ValueError(f"Unknown shard: {shard}")
    logger.debug(f"Creating session for shard: {shard}")
    return SESSION_MAKERS[shard]()

# FastAPI endpoints
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

@app.get("/users/{user_id}", response_model=UserResponse)
async def get_user(user_id: int):
    logger.info(f"Received request to get user: {user_id}")
    shard = consistent_hash.get_node(str(user_id))
    session = get_session(shard)
    try:
        db_user = session.query(User).filter(User.user_id == user_id).first()
        if not db_user:
            logger.warning(f"User {user_id} not found in shard {shard}")
            raise HTTPException(status_code=404, detail="User not found")
        logger.info(f"Retrieved user {user_id} from shard {shard}")
        return db_user
    finally:
        session.close()
        logger.debug(f"Closed session for shard {shard}")