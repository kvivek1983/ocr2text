CREATE TABLE IF NOT EXISTS extractions (
    id                  VARCHAR(36) PRIMARY KEY,
    created_at          TIMESTAMP DEFAULT NOW(),
    image_hash          VARCHAR(64),
    document_type       VARCHAR(50),
    paddle_confidence   FLOAT,
    paddle_raw_text     TEXT,
    paddle_fields       JSONB,
    paddle_time_ms      INTEGER,
    google_confidence   FLOAT,
    google_raw_text     TEXT,
    google_fields       JSONB,
    google_time_ms      INTEGER,
    comparison_score    FLOAT,
    field_comparison    JSONB,
    recommended_engine  VARCHAR(20),
    engine_used         VARCHAR(20),
    request_metadata    JSONB
);

CREATE INDEX IF NOT EXISTS idx_extractions_created_at ON extractions(created_at);
CREATE INDEX IF NOT EXISTS idx_extractions_document_type ON extractions(document_type);
CREATE INDEX IF NOT EXISTS idx_extractions_image_hash ON extractions(image_hash);
