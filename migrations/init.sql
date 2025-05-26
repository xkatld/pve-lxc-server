CREATE TABLE IF NOT EXISTS operation_logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    operation VARCHAR(50),
    container_id VARCHAR(20),
    node_name VARCHAR(50),
    status VARCHAR(20),
    message TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    ip_address VARCHAR(45)
);

CREATE INDEX IF NOT EXISTS ix_operation_logs_id ON operation_logs (id);
CREATE INDEX IF NOT EXISTS ix_operation_logs_operation ON operation_logs (operation);
CREATE INDEX IF NOT EXISTS ix_operation_logs_container_id ON operation_logs (container_id);
