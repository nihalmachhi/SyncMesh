PRAGMA foreign_keys = ON;
CREATE TABLE IF NOT EXISTS node_state (
 node_id TEXT PRIMARY KEY, local_seq INTEGER NOT NULL DEFAULT 0,
 node_vector TEXT NOT NULL DEFAULT '{}', is_online INTEGER NOT NULL DEFAULT 1
);
CREATE TABLE IF NOT EXISTS entities (
 entity_id TEXT PRIMARY KEY, fields TEXT NOT NULL DEFAULT '{}',
 quantity INTEGER NOT NULL DEFAULT 0, is_deleted INTEGER NOT NULL DEFAULT 0,
 entity_vector TEXT NOT NULL DEFAULT '{}', deleted_vector TEXT,
 deleted_operation_id TEXT, updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS change_log (
 local_id INTEGER PRIMARY KEY AUTOINCREMENT, operation_id TEXT NOT NULL UNIQUE,
 origin_node_id TEXT NOT NULL, origin_seq INTEGER NOT NULL, entity_id TEXT NOT NULL,
 op_type TEXT NOT NULL, payload TEXT NOT NULL, base_vector TEXT NOT NULL,
 wall_clock TEXT NOT NULL, received_at TEXT NOT NULL,
 UNIQUE(origin_node_id, origin_seq)
);
CREATE INDEX IF NOT EXISTS idx_log_origin ON change_log(origin_node_id, origin_seq);
CREATE TABLE IF NOT EXISTS pending_ops (
 operation_id TEXT PRIMARY KEY, origin_node_id TEXT NOT NULL, origin_seq INTEGER NOT NULL,
 raw_operation TEXT NOT NULL, UNIQUE(origin_node_id, origin_seq)
);
CREATE TABLE IF NOT EXISTS conflicts (
 conflict_id TEXT PRIMARY KEY, entity_id TEXT NOT NULL, field TEXT NOT NULL,
 operation_ids TEXT NOT NULL, policy TEXT NOT NULL,
 status TEXT NOT NULL CHECK(status IN ('OPEN','RESOLVED')),
 resolution TEXT, detected_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS sync_log (
 sync_id TEXT PRIMARY KEY, peer_id TEXT NOT NULL, started_at TEXT NOT NULL,
 duration_ms REAL NOT NULL, ops_sent INTEGER NOT NULL, ops_received INTEGER NOT NULL,
 duplicates_ignored INTEGER NOT NULL, conflicts_found INTEGER NOT NULL
);
