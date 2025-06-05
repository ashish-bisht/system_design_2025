Workspace Instructions for System Design Prototyping
This document provides setup and management instructions for the system design prototyping environment on a Mac M3 Pro, using Homebrew-installed services: PostgreSQL (14 and 17), FastAPI, Redis CE, and Cassandra. All prototyping is local, with system design focusing on memory, CPU, disk, and network.
System Setup

Hardware: Mac M3 Pro
OS: macOS
Services (installed via Homebrew):
PostgreSQL 14 (/opt/homebrew/opt/postgresql@14)
PostgreSQL 17 (/opt/homebrew/opt/postgresql@17) with Citus
FastAPI (Python, with psycopg==3.2.9)
Redis CE
Cassandra


Python Environment: Virtual environment at ~/system_design_grind/envsource ~/system_design_grind/env/bin/activate



PostgreSQL 14 Primary-Replica Setup

Primary: ~/pg14_primary (port 5432)
Replica: ~/pg14_replica (port 5433)
Role: postgres (superuser, no password for local trust authentication)
Database: testdb

Check Status
/opt/homebrew/opt/postgresql@14/bin/pg_ctl -D ~/pg14_primary status
/opt/homebrew/opt/postgresql@14/bin/pg_ctl -D ~/pg14_replica status

Start Servers
/opt/homebrew/opt/postgresql@14/bin/pg_ctl -D ~/pg14_primary -l ~/pg14_primary.log start
/opt/homebrew/opt/postgresql@14/bin/pg_ctl -D ~/pg14_replica -l ~/pg14_replica.log start

Test Connectivity
/opt/homebrew/opt/postgresql@14/bin/psql -h localhost -p 5432 -U postgres -d testdb
/opt/homebrew/opt/postgresql@14/bin/psql -h localhost -p 5433 -U postgres -d testdb

Notes

Replication: ~/pg14_replica is a read-only replica of ~/pg14_primary via streaming replication.
Configuration:
~/pg14_primary/postgresql.conf: Configured for replication (wal_level = replica, max_wal_senders = 3).
~/pg14_primary/pg_hba.conf: host replication postgres 127.0.0.1/32 trust


Protection: Do not install Citus or modify these instances to keep them independent.

PostgreSQL 17 Citus Cluster Setup

Coordinator: ~/pg17_citus_coordinator (port 5434)
Worker: ~/pg17_citus_worker1 (port 5435)
Role: postgres (superuser, no password for local trust authentication)
Database: testdb
Extension: Citus (for distributed sharding)

Check Status
/opt/homebrew/opt/postgresql@17/bin/pg_ctl -D ~/pg17_citus_coordinator status
/opt/homebrew/opt/postgresql@17/bin/pg_ctl -D ~/pg17_citus_worker1 status

Start Servers
/opt/homebrew/opt/postgresql@17/bin/pg_ctl -D ~/pg17_citus_coordinator -l ~/pg17_citus_coordinator.log start
/opt/homebrew/opt/postgresql@17/bin/pg_ctl -D ~/pg17_citus_worker1 -l ~/pg17_citus_worker1.log start

Test Connectivity
/opt/homebrew/opt/postgresql@17/bin/psql -h localhost -p 5434 -U postgres -d testdb
/opt/homebrew/opt/postgresql@17/bin/psql -h localhost -p 5435 -U postgres -d testdb

Initialize/Reinitialize Coordinator
rm -rf ~/pg17_citus_coordinator
mkdir ~/pg17_citus_coordinator
/opt/homebrew/opt/postgresql@17/bin/initdb -D ~/pg17_citus_coordinator --username=postgres
echo "port = 5434" >> ~/pg17_citus_coordinator/postgresql.conf
echo "shared_preload_libraries = 'citus'" >> ~/pg17_citus_coordinator/postgresql.conf
echo "host all all 127.0.0.1/32 trust" >> ~/pg17_citus_coordinator/pg_hba.conf
echo "host all all ::1/128 trust" >> ~/pg17_citus_coordinator/pg_hba.conf
/opt/homebrew/opt/postgresql@17/bin/pg_ctl -D ~/pg17_citus_coordinator -l ~/pg17_citus_coordinator.log start
/opt/homebrew/opt/postgresql@17/bin/createdb -h localhost -p 5434 -U postgres testdb

Initialize/Reinitialize Worker
rm -rf ~/pg17_citus_worker1
mkdir ~/pg17_citus_worker1
/opt/homebrew/opt/postgresql@17/bin/initdb -D ~/pg17_citus_worker1 --username=postgres
echo "port = 5435" >> ~/pg17_citus_worker1/postgresql.conf
echo "shared_preload_libraries = 'citus'" >> ~/pg17_citus_worker1/postgresql.conf
echo "host all all 127.0.0.1/32 trust" >> ~/pg17_citus_worker1/pg_hba.conf
echo "host all all ::1/128 trust" >> ~/pg17_citus_worker1/pg_hba.conf
/opt/homebrew/opt/postgresql@17/bin/pg_ctl -D ~/pg17_citus_worker1 -l ~/pg17_citus_worker1.log start
/opt/homebrew/opt/postgresql@17/bin/createdb -h localhost -p 5435 -U postgres testdb

Configure Citus Cluster
/opt/homebrew/opt/postgresql@17/bin/psql -h localhost -p 5434 -U postgres -d testdb -c "CREATE EXTENSION citus;"
/opt/homebrew/opt/postgresql@17/bin/psql -h localhost -p 5435 -U postgres -d testdb -c "CREATE EXTENSION citus;"
/opt/homebrew/opt/postgresql@17/bin/psql -h localhost -p 5434 -U postgres -d testdb -c "SELECT master_add_node('localhost', 5434);"
/opt/homebrew/opt/postgresql@17/bin/psql -h localhost -p 5434 -U postgres -d testdb -c "SELECT master_add_node('localhost', 5435);"
/opt/homebrew/opt/postgresql@17/bin/psql -h localhost -p 5434 -U postgres -d testdb -c "SELECT citus_set_node_property('localhost', 5434, 'shouldhaveshards', false);"

Create Distributed Table
/opt/homebrew/opt/postgresql@17/bin/psql -h localhost -p 5434 -U postgres -d testdb

CREATE TABLE users (
    user_id SERIAL PRIMARY KEY,
    name TEXT,
    email TEXT,
    created_at DATE
);
SELECT create_distributed_table('users', 'user_id', shard_count => 4);
INSERT INTO users (user_id, name, email, created_at) VALUES
    (1, 'Alice', 'alice@example.com', '2025-01-15'),
    (2, 'Bob', 'bob@example.com', '2025-02-10');

Notes

Sharding: Handled by Citus (hash-based, user_id as distribution column).
Coordinator: Routes queries, stores metadata, no shards.
Worker: Stores shards, executes queries.
Protection: Independent from PostgreSQL 14 setup.

FastAPI Setup

Location: ~/system_design_grind/database/sharding/main.py
Dependencies: fastapi, uvicorn, psycopg==3.2.9pip install fastapi uvicorn psycopg==3.2.9


Run:uvicorn main:app --reload


Endpoints:
GET /users/{user_id}: Fetch user by ID.
POST /users: Create user.
GET /users/{user_id}/shard: Check shard for user_id.



Troubleshooting

Check Logs:cat ~/pg17_citus_coordinator.log | tail -n 50
cat ~/pg17_citus_worker1.log | tail -n 50


Port Conflicts:lsof -i :5434
lsof -i :5435

Change ports in postgresql.conf if needed (e.g., 5436 for coordinator, 5437 for worker).
Stale Lock Files:rm ~/pg17_citus_coordinator/postmaster.pid
rm ~/pg17_citus_worker1/postmaster.pid


Permissions:chmod 700 ~/pg17_citus_coordinator ~/pg17_citus_worker1
chown ash ~/pg17_citus_coordinator ~/pg17_citus_worker1



System Design Considerations

Memory: Citus coordinator stores metadata; FastAPI minimal. Monitor with Activity Monitor.
CPU: Citus parallelizes queries; FastAPI lightweight. Monitor with htop.
Disk: Shards on worker; check with df -h.
Network: Coordinator routes to worker; monitor with netstat -an | grep 5434.

Recommended Resources

YouTube: “Citus: Scaling PostgreSQL” by Citus Data.
Docs: https://docs.citusdata.com/en/stable/, https://www.psycopg.org/psycopg3/docs/
Book: Designing Data-Intensive Applications by Martin Kleppmann.

