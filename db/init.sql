-- ─────────────────────────────────────────────────────────────────────────────
-- AI Code Review Crew — MySQL Schema
-- Auto-executed on first container start via /docker-entrypoint-initdb.d/
-- ─────────────────────────────────────────────────────────────────────────────

CREATE DATABASE IF NOT EXISTS code_review
  CHARACTER SET utf8mb4
  COLLATE utf8mb4_unicode_ci;

USE code_review;

-- ── Review runs ───────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS review_runs (
    id              INT UNSIGNED    NOT NULL AUTO_INCREMENT PRIMARY KEY,
    run_id          CHAR(36)        NOT NULL DEFAULT (UUID()),
    title           VARCHAR(500)    NOT NULL,
    context         TEXT,
    input_type      ENUM('file','diff','snippet') NOT NULL,
    filename        VARCHAR(500),
    pr_url          VARCHAR(1000),
    llm_provider    VARCHAR(50)     NOT NULL DEFAULT 'ollama',
    llm_model       VARCHAR(100)    NOT NULL,
    embed_model     VARCHAR(100)    NOT NULL,
    report_path     VARCHAR(1000),
    google_doc_url  VARCHAR(1000),
    duration_secs   DECIMAL(8,2),
    created_at      DATETIME        NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE KEY uq_run_id (run_id),
    INDEX idx_created_at (created_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ── Per-agent outputs ─────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS agent_outputs (
    id              INT UNSIGNED    NOT NULL AUTO_INCREMENT PRIMARY KEY,
    run_id          CHAR(36)        NOT NULL,
    agent_name      VARCHAR(100)    NOT NULL,
    raw_output      MEDIUMTEXT      NOT NULL,
    token_count     INT,
    duration_secs   DECIMAL(8,2),
    created_at      DATETIME        NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY fk_ao_run_id (run_id) REFERENCES review_runs(run_id) ON DELETE CASCADE,
    INDEX idx_ao_run_id (run_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ── Structured findings ───────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS findings (
    id              INT UNSIGNED    NOT NULL AUTO_INCREMENT PRIMARY KEY,
    run_id          CHAR(36)        NOT NULL,
    severity        ENUM('critical','high','medium','low','info') NOT NULL,
    category        ENUM('security','architecture','testing','documentation') NOT NULL,
    title           VARCHAR(500)    NOT NULL,
    description     TEXT,
    line_ref        VARCHAR(200),
    remediation     TEXT,
    created_at      DATETIME        NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY fk_f_run_id (run_id) REFERENCES review_runs(run_id) ON DELETE CASCADE,
    INDEX idx_f_run_id  (run_id),
    INDEX idx_f_severity (severity)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ── KB ingestion log ──────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS kb_ingestions (
    id              INT UNSIGNED    NOT NULL AUTO_INCREMENT PRIMARY KEY,
    collection_name VARCHAR(200)    NOT NULL,
    source_dir      VARCHAR(500)    NOT NULL,
    doc_count       INT             NOT NULL DEFAULT 0,
    chunk_count     INT             NOT NULL DEFAULT 0,
    embed_model     VARCHAR(100)    NOT NULL,
    embed_dim       INT             NOT NULL,
    ingested_at     DATETIME        NOT NULL DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_kb_collection (collection_name)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;