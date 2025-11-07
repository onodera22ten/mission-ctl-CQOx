-- CQOx Database Initialization
-- Data Warehouse schema for long-term storage

CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- ========================================
-- Datasets table
-- ========================================
CREATE TABLE IF NOT EXISTS datasets (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    dataset_id VARCHAR(255) UNIQUE NOT NULL,
    filename VARCHAR(500),
    uploaded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    rows_count INTEGER,
    columns_count INTEGER,
    file_size_bytes BIGINT,
    metadata JSONB
);

CREATE INDEX idx_datasets_dataset_id ON datasets(dataset_id);
CREATE INDEX idx_datasets_uploaded_at ON datasets(uploaded_at DESC);

-- ========================================
-- Analysis Jobs table
-- ========================================
CREATE TABLE IF NOT EXISTS analysis_jobs (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    job_id VARCHAR(255) UNIQUE NOT NULL,
    dataset_id VARCHAR(255) REFERENCES datasets(dataset_id),
    status VARCHAR(50) DEFAULT 'pending',
    started_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    completed_at TIMESTAMP,
    duration_seconds REAL,
    mapping JSONB,
    config JSONB,
    results JSONB,
    error_message TEXT
);

CREATE INDEX idx_jobs_job_id ON analysis_jobs(job_id);
CREATE INDEX idx_jobs_dataset_id ON analysis_jobs(dataset_id);
CREATE INDEX idx_jobs_status ON analysis_jobs(status);
CREATE INDEX idx_jobs_started_at ON analysis_jobs(started_at DESC);

-- ========================================
-- Estimator Results table
-- ========================================
CREATE TABLE IF NOT EXISTS estimator_results (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    job_id VARCHAR(255) REFERENCES analysis_jobs(job_id),
    estimator_name VARCHAR(100) NOT NULL,
    tau_hat REAL,
    se REAL,
    ci_lower REAL,
    ci_upper REAL,
    p_value REAL,
    execution_time_seconds REAL,
    status VARCHAR(50),
    metadata JSONB,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_estimator_job_id ON estimator_results(job_id);
CREATE INDEX idx_estimator_name ON estimator_results(estimator_name);

-- ========================================
-- Quality Gates table
-- ========================================
CREATE TABLE IF NOT EXISTS quality_gates (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    job_id VARCHAR(255) REFERENCES analysis_jobs(job_id),
    gate_name VARCHAR(100) NOT NULL,
    pass BOOLEAN,
    value REAL,
    threshold REAL,
    message TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_gates_job_id ON quality_gates(job_id);
CREATE INDEX idx_gates_name ON quality_gates(gate_name);
CREATE INDEX idx_gates_pass ON quality_gates(pass);

-- ========================================
-- CAS Scores table
-- ========================================
CREATE TABLE IF NOT EXISTS cas_scores (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    job_id VARCHAR(255) REFERENCES analysis_jobs(job_id),
    overall_score REAL NOT NULL,
    internal_validity REAL,
    external_validity REAL,
    statistical_significance REAL,
    model_stability REAL,
    data_quality REAL,
    grade VARCHAR(20),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_cas_job_id ON cas_scores(job_id);
CREATE INDEX idx_cas_overall ON cas_scores(overall_score DESC);

-- ========================================
-- Observability Metrics table (for 37 panels)
-- ========================================
CREATE TABLE IF NOT EXISTS observability_metrics (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    metric_name VARCHAR(255) NOT NULL,
    metric_value REAL,
    labels JSONB,
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_metrics_name ON observability_metrics(metric_name);
CREATE INDEX idx_metrics_timestamp ON observability_metrics(timestamp DESC);
CREATE INDEX idx_metrics_labels ON observability_metrics USING GIN (labels);

-- ========================================
-- Audit Log table
-- ========================================
CREATE TABLE IF NOT EXISTS audit_log (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    event_type VARCHAR(100) NOT NULL,
    user_id VARCHAR(255),
    dataset_id VARCHAR(255),
    job_id VARCHAR(255),
    action VARCHAR(255),
    details JSONB,
    ip_address INET,
    user_agent TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_audit_event_type ON audit_log(event_type);
CREATE INDEX idx_audit_created_at ON audit_log(created_at DESC);
CREATE INDEX idx_audit_user_id ON audit_log(user_id);

-- ========================================
-- Objective Inference Cache table
-- ========================================
CREATE TABLE IF NOT EXISTS objective_inference_cache (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    dataset_id VARCHAR(255) UNIQUE NOT NULL,
    objective_hints JSONB NOT NULL,
    confidence_scores JSONB,
    column_patterns JSONB,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_objective_cache_dataset_id ON objective_inference_cache(dataset_id);

-- ========================================
-- Initial data / Sample queries
-- ========================================

-- View: Recent jobs with CAS scores
CREATE OR REPLACE VIEW recent_jobs_with_cas AS
SELECT
    aj.job_id,
    aj.dataset_id,
    aj.status,
    aj.started_at,
    aj.completed_at,
    aj.duration_seconds,
    cs.overall_score as cas_score,
    cs.grade as cas_grade,
    COUNT(DISTINCT er.id) as estimator_count,
    COUNT(DISTINCT CASE WHEN qg.pass THEN qg.id END) as gates_passed,
    COUNT(DISTINCT qg.id) as total_gates
FROM analysis_jobs aj
LEFT JOIN cas_scores cs ON aj.job_id = cs.job_id
LEFT JOIN estimator_results er ON aj.job_id = er.job_id
LEFT JOIN quality_gates qg ON aj.job_id = qg.job_id
GROUP BY aj.job_id, aj.dataset_id, aj.status, aj.started_at, aj.completed_at, aj.duration_seconds, cs.overall_score, cs.grade
ORDER BY aj.started_at DESC
LIMIT 100;

-- View: Estimator performance statistics
CREATE OR REPLACE VIEW estimator_performance_stats AS
SELECT
    estimator_name,
    COUNT(*) as total_runs,
    AVG(execution_time_seconds) as avg_execution_time,
    PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY execution_time_seconds) as median_execution_time,
    PERCENTILE_CONT(0.95) WITHIN GROUP (ORDER BY execution_time_seconds) as p95_execution_time,
    AVG(tau_hat) as avg_tau_hat,
    STDDEV(tau_hat) as stddev_tau_hat,
    COUNT(CASE WHEN status = 'success' THEN 1 END) as success_count,
    COUNT(CASE WHEN status = 'error' THEN 1 END) as error_count
FROM estimator_results
GROUP BY estimator_name;

-- View: Quality gate pass rates
CREATE OR REPLACE VIEW quality_gate_pass_rates AS
SELECT
    gate_name,
    COUNT(*) as total_checks,
    COUNT(CASE WHEN pass THEN 1 END) as passed_count,
    ROUND(100.0 * COUNT(CASE WHEN pass THEN 1 END) / COUNT(*), 2) as pass_rate_percent,
    AVG(value) as avg_value,
    AVG(threshold) as avg_threshold
FROM quality_gates
GROUP BY gate_name
ORDER BY pass_rate_percent DESC;

COMMENT ON TABLE datasets IS 'Uploaded CSV datasets metadata';
COMMENT ON TABLE analysis_jobs IS 'Causal analysis job tracking';
COMMENT ON TABLE estimator_results IS 'Individual estimator execution results';
COMMENT ON TABLE quality_gates IS 'Quality gate evaluation results';
COMMENT ON TABLE cas_scores IS 'Causal Assurance Score (CAS) tracking';
COMMENT ON TABLE observability_metrics IS 'System metrics for 37-panel dashboard';
COMMENT ON TABLE audit_log IS 'User action audit trail';
COMMENT ON TABLE objective_inference_cache IS 'Cached objective auto-detection results';
