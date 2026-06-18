-- PostgreSQL multi-database initialization for Phase 09 storage stack
-- Databases: langfuse (prompt tracking), n8n (workflows), dify (LLM apps)

CREATE USER langfuse WITH PASSWORD '4730ee6db0dff636bd4a09d9234c99af';
CREATE DATABASE langfuse OWNER langfuse;

CREATE USER n8n WITH PASSWORD '3b67b03c2c3a6f85b73114c43b4b2ee5';
CREATE DATABASE n8n OWNER n8n;

CREATE USER dify WITH PASSWORD 'ae59815ef2842cf3ed1304dd4733798f';
CREATE DATABASE dify OWNER dify;

-- Grant necessary privileges
GRANT CREATE ON DATABASE langfuse TO langfuse;
GRANT CREATE ON DATABASE n8n TO n8n;
GRANT CREATE ON DATABASE dify TO dify;
