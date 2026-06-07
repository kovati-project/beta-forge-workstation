-- PostgreSQL multi-database initialization for Phase 09 storage stack
-- Databases: langfuse (prompt tracking), n8n (workflows), dify (LLM apps)

CREATE USER langfuse WITH PASSWORD 'langfuse_pass';
CREATE DATABASE langfuse OWNER langfuse;

CREATE USER n8n WITH PASSWORD 'n8n_pass';
CREATE DATABASE n8n OWNER n8n;

CREATE USER dify WITH PASSWORD 'dify_pass';
CREATE DATABASE dify OWNER dify;

-- Grant necessary privileges
GRANT CREATE ON DATABASE langfuse TO langfuse;
GRANT CREATE ON DATABASE n8n TO n8n;
GRANT CREATE ON DATABASE dify TO dify;
