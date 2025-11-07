-- CQOx Database Schema: NASA/Googleレベル
-- PostgreSQL 15 + TimescaleDB + pgcrypto

-- ===============================
-- Extensions
-- ===============================

-- TimescaleDB: 時系列データの高速処理
CREATE EXTENSION IF NOT EXISTS timescaledb CASCADE;

-- pgcrypto: データ暗号化
CREATE EXTENSION IF NOT EXISTS pgcrypto;

-- Full-text search
CREATE EXTENSION IF NOT EXISTS pg_trgm;

-- UUID generation
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- ===============================
-- Time-Series Tables
-- ===============================

-- Metrics（メトリクス：Prometheus風）
CREATE TABLE IF NOT EXISTS metrics (
    time TIMESTAMPTZ NOT NULL,
    metric_name TEXT NOT NULL,
    value DOUBLE PRECISION,
    labels JSONB,
    PRIMARY KEY (time, metric_name)
);

-- TimescaleDB hypertable化（自動パーティショニング）
SELECT create_hypertable('metrics', 'time', if_not_exists => TRUE);

-- Continuous aggregate: 5分毎の集計
CREATE MATERIALIZED VIEW IF NOT EXISTS metrics_5min
WITH (timescaledb.continuous) AS
SELECT
    time_bucket('5 minutes', time) AS bucket,
    metric_name,
    AVG(value) as avg_value,
    MAX(value) as max_value,
    MIN(value) as min_value,
    COUNT(*) as count
FROM metrics
GROUP BY bucket, metric_name
WITH NO DATA;

-- Refresh policy: 5分毎に自動更新
SELECT add_continuous_aggregate_policy('metrics_5min',
  start_offset => INTERVAL '1 hour',
  end_offset => INTERVAL '5 minutes',
  schedule_interval => INTERVAL '5 minutes',
  if_not_exists => TRUE);

-- Data retention: 90日後に古いデータを削除
SELECT add_retention_policy('metrics', INTERVAL '90 days', if_not_exists => TRUE);

-- Compression: 7日以上前のデータを圧縮
SELECT add_compression_policy('metrics', INTERVAL '7 days', if_not_exists => TRUE);

-- ===============================
-- Audit Log (NASA/Googleレベル)
-- ===============================

CREATE TABLE IF NOT EXISTS audit_log (
    id BIGSERIAL PRIMARY KEY,
    timestamp TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    user_id TEXT,
    action TEXT NOT NULL,
    resource TEXT,
    result TEXT,
    details JSONB,
    -- 暗号化カラム（機密データ）
    encrypted_payload BYTEA,
    -- Network info
    ip_address INET,
    user_agent TEXT,
    -- トレーサビリティ
    trace_id TEXT,
    span_id TEXT
);

CREATE INDEX idx_audit_timestamp ON audit_log (timestamp DESC);
CREATE INDEX idx_audit_user ON audit_log (user_id);
CREATE INDEX idx_audit_action ON audit_log (action);
CREATE INDEX idx_audit_trace ON audit_log (trace_id);

-- ===============================
-- Application Tables
-- ===============================

-- Datasets（データセット管理）
CREATE TABLE IF NOT EXISTS datasets (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    name TEXT NOT NULL,
    rows INTEGER,
    columns INTEGER,
    status TEXT DEFAULT 'pending',
    metadata JSONB,
    -- 暗号化: データパス（ファイルパスを暗号化）
    encrypted_data_path BYTEA,
    -- 所有者
    owner_id TEXT,
    -- 削除フラグ（論理削除）
    deleted_at TIMESTAMPTZ
);

CREATE INDEX idx_datasets_created ON datasets (created_at DESC);
CREATE INDEX idx_datasets_status ON datasets (status) WHERE deleted_at IS NULL;
CREATE INDEX idx_datasets_owner ON datasets (owner_id) WHERE deleted_at IS NULL;

-- 自動updated_at更新
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ language 'plpgsql';

CREATE TRIGGER update_datasets_updated_at BEFORE UPDATE ON datasets
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- Analysis Results（分析結果）
CREATE TABLE IF NOT EXISTS analysis_results (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    dataset_id UUID REFERENCES datasets(id) ON DELETE CASCADE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    estimator TEXT NOT NULL,
    -- 推定値
    ate DOUBLE PRECISION,
    se DOUBLE PRECISION,
    ci_lower DOUBLE PRECISION,
    ci_upper DOUBLE PRECISION,
    p_value DOUBLE PRECISION,
    -- 詳細結果（JSON）
    results JSONB,
    -- メタデータ
    duration_ms INTEGER,
    status TEXT DEFAULT 'completed'
);

CREATE INDEX idx_analysis_dataset ON analysis_results (dataset_id);
CREATE INDEX idx_analysis_created ON analysis_results (created_at DESC);
CREATE INDEX idx_analysis_estimator ON analysis_results (estimator);

-- ===============================
-- Encryption Functions
-- ===============================

-- 暗号化ヘルパー（AES-256対称暗号化）
CREATE OR REPLACE FUNCTION encrypt_data(data TEXT, key TEXT)
RETURNS BYTEA AS $$
BEGIN
    RETURN pgp_sym_encrypt(data, key, 'cipher-algo=aes256');
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

-- 復号化ヘルパー
CREATE OR REPLACE FUNCTION decrypt_data(encrypted BYTEA, key TEXT)
RETURNS TEXT AS $$
BEGIN
    RETURN pgp_sym_decrypt(encrypted, key);
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

-- ===============================
-- SLO/Error Budget Tracking
-- ===============================

CREATE TABLE IF NOT EXISTS slo_metrics (
    time TIMESTAMPTZ NOT NULL,
    service TEXT NOT NULL,
    endpoint TEXT,
    success_count INTEGER DEFAULT 0,
    total_count INTEGER DEFAULT 0,
    latency_p50 DOUBLE PRECISION,
    latency_p95 DOUBLE PRECISION,
    latency_p99 DOUBLE PRECISION,
    PRIMARY KEY (time, service, endpoint)
);

SELECT create_hypertable('slo_metrics', 'time', if_not_exists => TRUE);

-- SLO 1時間集計
CREATE MATERIALIZED VIEW IF NOT EXISTS slo_1hour
WITH (timescaledb.continuous) AS
SELECT
    time_bucket('1 hour', time) AS bucket,
    service,
    SUM(success_count) as success_count,
    SUM(total_count) as total_count,
    CASE 
        WHEN SUM(total_count) > 0 
        THEN (SUM(success_count)::FLOAT / SUM(total_count)::FLOAT)
        ELSE 1.0
    END as availability,
    AVG(latency_p95) as avg_latency_p95,
    MAX(latency_p99) as max_latency_p99
FROM slo_metrics
GROUP BY bucket, service
WITH NO DATA;

SELECT add_continuous_aggregate_policy('slo_1hour',
  start_offset => INTERVAL '3 hours',
  end_offset => INTERVAL '1 hour',
  schedule_interval => INTERVAL '1 hour',
  if_not_exists => TRUE);

-- ===============================
-- Security: Row-Level Security
-- ===============================

-- RLS有効化（Multi-Tenant対応）
ALTER TABLE datasets ENABLE ROW LEVEL SECURITY;
ALTER TABLE analysis_results ENABLE ROW LEVEL SECURITY;

-- ポリシー: ユーザーは自分のデータのみアクセス可能
CREATE POLICY datasets_isolation ON datasets
    FOR ALL
    USING (owner_id = current_user OR current_user = 'cqox_admin');

CREATE POLICY analysis_isolation ON analysis_results
    FOR ALL
    USING (
        dataset_id IN (
            SELECT id FROM datasets WHERE owner_id = current_user
        ) OR current_user = 'cqox_admin'
    );

-- ===============================
-- Initial Data & Validation
-- ===============================

-- バージョン確認
SELECT version();
SELECT extname, extversion FROM pg_extension WHERE extname IN ('timescaledb', 'pgcrypto', 'pg_trgm', 'uuid-ossp');

-- Hypertable確認
SELECT * FROM timescaledb_information.hypertables;

-- 完了メッセージ
DO $$
BEGIN
    RAISE NOTICE '✅ CQOx Database initialized successfully (NASA/Google level)';
    RAISE NOTICE 'PostgreSQL: %', version();
    RAISE NOTICE 'TimescaleDB: %', (SELECT extversion FROM pg_extension WHERE extname = 'timescaledb');
END $$;

