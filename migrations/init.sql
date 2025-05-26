CREATE TABLE IF NOT EXISTS api_keys (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    key_name VARCHAR(100) UNIQUE NOT NULL,
    key_hash VARCHAR(255) UNIQUE NOT NULL,
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    last_used TIMESTAMP WITH TIME ZONE,
    expires_at TIMESTAMP WITH TIME ZONE,
    permissions VARCHAR(500) DEFAULT 'read,write'
);

CREATE TABLE IF NOT EXISTS operation_logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    api_key_name VARCHAR(100),
    operation VARCHAR(50),
    container_id VARCHAR(20),
    node_name VARCHAR(50),
    status VARCHAR(20),
    message TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    ip_address VARCHAR(45)
);

CREATE INDEX IF NOT EXISTS ix_api_keys_id ON api_keys (id);
CREATE INDEX IF NOT EXISTS ix_api_keys_key_name ON api_keys (key_name);
CREATE INDEX IF NOT EXISTS ix_api_keys_key_hash ON api_keys (key_hash);

CREATE INDEX IF NOT EXISTS ix_operation_logs_id ON operation_logs (id);
CREATE INDEX IF NOT EXISTS ix_operation_logs_api_key_name ON operation_logs (api_key_name);
CREATE INDEX IF NOT EXISTS ix_operation_logs_operation ON operation_logs (operation);
CREATE INDEX IF NOT EXISTS ix_operation_logs_container_id ON operation_logs (container_id);
