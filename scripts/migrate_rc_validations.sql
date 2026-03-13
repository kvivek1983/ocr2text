-- Migration: Add verification pipeline columns to rc_validations
-- Date: 2026-03-13
-- Description: Adds verification_status, approval_method, govt_match_score,
--   llm_extraction_id, govt_verification_id, ocr_raw_text_front/back,
--   mapper_raw_output, and approved_at columns.
-- NOTE: Run this ONCE on existing databases. New databases get these columns
--   automatically via create_all().

ALTER TABLE rc_validations ADD COLUMN IF NOT EXISTS verification_status VARCHAR(20) NOT NULL DEFAULT 'pending';
ALTER TABLE rc_validations ADD COLUMN IF NOT EXISTS approval_method VARCHAR(20) NOT NULL DEFAULT 'pending';
ALTER TABLE rc_validations ADD COLUMN IF NOT EXISTS approved_at DATETIME NULL;
ALTER TABLE rc_validations ADD COLUMN IF NOT EXISTS govt_match_score FLOAT NULL;
ALTER TABLE rc_validations ADD COLUMN IF NOT EXISTS llm_extraction_id VARCHAR(36) NULL;
ALTER TABLE rc_validations ADD COLUMN IF NOT EXISTS govt_verification_id VARCHAR(36) NULL;
ALTER TABLE rc_validations ADD COLUMN IF NOT EXISTS ocr_raw_text_front TEXT NULL;
ALTER TABLE rc_validations ADD COLUMN IF NOT EXISTS ocr_raw_text_back TEXT NULL;
ALTER TABLE rc_validations ADD COLUMN IF NOT EXISTS mapper_raw_output JSON NULL;

-- Foreign key constraints (optional — skip if DB doesn't support or tables may not exist yet)
-- ALTER TABLE rc_validations ADD CONSTRAINT fk_rc_val_llm_extraction FOREIGN KEY (llm_extraction_id) REFERENCES rc_llm_extractions(id);
-- ALTER TABLE rc_validations ADD CONSTRAINT fk_rc_val_govt_verification FOREIGN KEY (govt_verification_id) REFERENCES rc_govt_verifications(id);
