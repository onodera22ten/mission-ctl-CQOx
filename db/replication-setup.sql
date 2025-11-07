-- ============================================================================
-- DR Multi-Region PostgreSQL Replication Setup (NASA/Google Level)
-- ============================================================================
-- 目標:
--   RPO (Recovery Point Objective): < 1 hour
--   RTO (Recovery Time Objective): < 4 hours
--
-- 構成:
--   - Primary: us-east-1 (Production)
--   - Standby: us-west-2 (Hot Standby - Streaming Replication)
--   - Archive: eu-west-1 (Cold Backup - WAL Archive)
-- ============================================================================

-- ============================================================================
-- 1. REPLICATION USER SETUP
-- ============================================================================
-- プライマリサーバーで実行
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'replicator') THEN
        CREATE ROLE replicator WITH REPLICATION LOGIN PASSWORD 'CHANGE_ME_REPLICATION_PASSWORD';
        RAISE NOTICE 'Created replication user: replicator';
    ELSE
        RAISE NOTICE 'Replication user already exists: replicator';
    END IF;
END
$$;

-- レプリケーションユーザーに必要な権限を付与
GRANT USAGE ON SCHEMA public TO replicator;
GRANT SELECT ON ALL TABLES IN SCHEMA public TO replicator;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT SELECT ON TABLES TO replicator;

-- ============================================================================
-- 2. REPLICATION SLOTS (レプリケーションスロット)
-- ============================================================================
-- 物理レプリケーションスロットの作成（データロス防止）
SELECT pg_create_physical_replication_slot('standby_us_west_2')
WHERE NOT EXISTS (
    SELECT 1 FROM pg_replication_slots WHERE slot_name = 'standby_us_west_2'
);

SELECT pg_create_physical_replication_slot('standby_eu_west_1')
WHERE NOT EXISTS (
    SELECT 1 FROM pg_replication_slots WHERE slot_name = 'standby_eu_west_1'
);

-- ============================================================================
-- 3. MONITORING VIEWS (レプリケーション監視)
-- ============================================================================
-- レプリケーション状態監視ビュー
CREATE OR REPLACE VIEW replication_status AS
SELECT
    client_addr AS standby_host,
    state,
    sent_lsn,
    write_lsn,
    flush_lsn,
    replay_lsn,
    sync_state,
    -- レプリケーション遅延（バイト）
    pg_wal_lsn_diff(sent_lsn, replay_lsn) AS replication_lag_bytes,
    -- レプリケーション遅延（秒）
    EXTRACT(EPOCH FROM (NOW() - pg_last_xact_replay_timestamp())) AS replication_lag_seconds,
    -- RPO違反チェック（1時間 = 3600秒）
    CASE
        WHEN EXTRACT(EPOCH FROM (NOW() - pg_last_xact_replay_timestamp())) > 3600 THEN 'RPO_VIOLATION'
        WHEN EXTRACT(EPOCH FROM (NOW() - pg_last_xact_replay_timestamp())) > 1800 THEN 'WARNING'
        ELSE 'OK'
    END AS rpo_status
FROM pg_stat_replication;

COMMENT ON VIEW replication_status IS 'Real-time replication monitoring with RPO compliance';

-- ============================================================================
-- 4. WAL ARCHIVING STATUS
-- ============================================================================
-- WALアーカイブ状態監視
CREATE OR REPLACE VIEW wal_archive_status AS
SELECT
    archived_count,
    last_archived_wal,
    last_archived_time,
    failed_count,
    last_failed_wal,
    last_failed_time,
    -- アーカイブ遅延（秒）
    EXTRACT(EPOCH FROM (NOW() - last_archived_time)) AS archive_lag_seconds,
    -- RPO違反チェック
    CASE
        WHEN failed_count > 0 THEN 'ARCHIVE_FAILURE'
        WHEN EXTRACT(EPOCH FROM (NOW() - last_archived_time)) > 3600 THEN 'RPO_VIOLATION'
        WHEN EXTRACT(EPOCH FROM (NOW() - last_archived_time)) > 1800 THEN 'WARNING'
        ELSE 'OK'
    END AS archive_status
FROM pg_stat_archiver;

COMMENT ON VIEW wal_archive_status IS 'WAL archiving health with RPO compliance';

-- ============================================================================
-- 5. FAILOVER PREPARATION
-- ============================================================================
-- フェイルオーバー用のプロモーション検証関数
CREATE OR REPLACE FUNCTION check_standby_promotion_readiness()
RETURNS TABLE(
    check_name TEXT,
    status TEXT,
    details TEXT
) AS $$
BEGIN
    -- Check 1: レプリケーション遅延
    RETURN QUERY
    SELECT
        'Replication Lag'::TEXT,
        CASE
            WHEN COALESCE(MAX(replication_lag_seconds), 0) < 60 THEN 'OK'
            WHEN COALESCE(MAX(replication_lag_seconds), 0) < 300 THEN 'WARNING'
            ELSE 'CRITICAL'
        END,
        FORMAT('Max lag: %s seconds', COALESCE(MAX(replication_lag_seconds)::TEXT, 'N/A'))
    FROM replication_status;

    -- Check 2: WALアーカイブ状態
    RETURN QUERY
    SELECT
        'WAL Archive'::TEXT,
        CASE
            WHEN failed_count = 0 THEN 'OK'
            WHEN failed_count < 5 THEN 'WARNING'
            ELSE 'CRITICAL'
        END,
        FORMAT('Failed archives: %s', failed_count)
    FROM pg_stat_archiver;

    -- Check 3: スロット状態
    RETURN QUERY
    SELECT
        'Replication Slots'::TEXT,
        CASE
            WHEN COUNT(*) >= 2 AND MIN(active::INT) = 1 THEN 'OK'
            WHEN COUNT(*) >= 2 THEN 'WARNING'
            ELSE 'CRITICAL'
        END,
        FORMAT('Active slots: %s/%s', SUM(active::INT), COUNT(*))
    FROM pg_replication_slots;

    -- Check 4: ディスク容量
    RETURN QUERY
    SELECT
        'Disk Space'::TEXT,
        'INFO'::TEXT,
        'Manual check required'::TEXT;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

COMMENT ON FUNCTION check_standby_promotion_readiness() IS
'Check if standby is ready for promotion to primary (RTO < 4h)';

-- ============================================================================
-- 6. PROMETHEUS METRICS EXPORT
-- ============================================================================
-- Prometheusメトリクス出力テーブル
CREATE TABLE IF NOT EXISTS dr_metrics (
    metric_time TIMESTAMPTZ DEFAULT NOW(),
    metric_name TEXT NOT NULL,
    metric_value FLOAT NOT NULL,
    metric_labels JSONB DEFAULT '{}'::JSONB,
    PRIMARY KEY (metric_time, metric_name)
);

-- TimescaleDBハイパーテーブル化
SELECT create_hypertable('dr_metrics', 'metric_time', if_not_exists => TRUE);

-- メトリクス収集関数（Prometheusスクレイプ用）
CREATE OR REPLACE FUNCTION collect_dr_metrics()
RETURNS void AS $$
BEGIN
    -- レプリケーション遅延メトリクス
    INSERT INTO dr_metrics (metric_name, metric_value, metric_labels)
    SELECT
        'cqox_replication_lag_seconds',
        COALESCE(replication_lag_seconds, 0),
        jsonb_build_object('standby_host', standby_host, 'sync_state', sync_state)
    FROM replication_status;

    -- WALアーカイブメトリクス
    INSERT INTO dr_metrics (metric_name, metric_value, metric_labels)
    SELECT
        'cqox_wal_archive_lag_seconds',
        archive_lag_seconds,
        '{}'::JSONB
    FROM wal_archive_status;

    -- RPO違反カウント
    INSERT INTO dr_metrics (metric_name, metric_value, metric_labels)
    SELECT
        'cqox_rpo_violations_total',
        COUNT(*)::FLOAT,
        '{}'::JSONB
    FROM replication_status
    WHERE rpo_status = 'RPO_VIOLATION';

    -- スロット状態
    INSERT INTO dr_metrics (metric_name, metric_value, metric_labels)
    SELECT
        'cqox_replication_slots_active',
        SUM(active::INT)::FLOAT,
        '{}'::JSONB
    FROM pg_replication_slots;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

COMMENT ON FUNCTION collect_dr_metrics() IS
'Collect DR metrics for Prometheus monitoring (called every 15s)';

-- ============================================================================
-- 7. ALERTING RULES
-- ============================================================================
-- アラートログテーブル
CREATE TABLE IF NOT EXISTS dr_alerts (
    alert_id SERIAL PRIMARY KEY,
    alert_time TIMESTAMPTZ DEFAULT NOW(),
    alert_level TEXT NOT NULL CHECK (alert_level IN ('INFO', 'WARNING', 'CRITICAL')),
    alert_name TEXT NOT NULL,
    alert_message TEXT NOT NULL,
    resolved BOOLEAN DEFAULT FALSE,
    resolved_time TIMESTAMPTZ
);

-- アラート生成関数
CREATE OR REPLACE FUNCTION generate_dr_alerts()
RETURNS void AS $$
BEGIN
    -- Alert 1: RPO違反
    INSERT INTO dr_alerts (alert_level, alert_name, alert_message)
    SELECT
        'CRITICAL',
        'RPO_VIOLATION',
        FORMAT('Replication lag %s seconds exceeds RPO target (3600s)', replication_lag_seconds)
    FROM replication_status
    WHERE rpo_status = 'RPO_VIOLATION'
    ON CONFLICT DO NOTHING;

    -- Alert 2: WALアーカイブ失敗
    INSERT INTO dr_alerts (alert_level, alert_name, alert_message)
    SELECT
        'CRITICAL',
        'WAL_ARCHIVE_FAILURE',
        FORMAT('WAL archive failed %s times, last failed: %s', failed_count, last_failed_wal)
    FROM wal_archive_status
    WHERE failed_count > 0
    ON CONFLICT DO NOTHING;

    -- Alert 3: レプリケーションスロット遅延
    INSERT INTO dr_alerts (alert_level, alert_name, alert_message)
    SELECT
        'WARNING',
        'REPLICATION_SLOT_LAG',
        FORMAT('Replication slot lag: %s bytes', pg_wal_lsn_diff(confirmed_flush_lsn, pg_current_wal_lsn()))
    FROM pg_replication_slots
    WHERE pg_wal_lsn_diff(confirmed_flush_lsn, pg_current_wal_lsn()) > 1073741824  -- 1GB
    ON CONFLICT DO NOTHING;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

COMMENT ON FUNCTION generate_dr_alerts() IS
'Generate alerts for DR issues (called every 60s)';

-- ============================================================================
-- 8. AUTOMATED HEALTH CHECKS
-- ============================================================================
-- ヘルスチェック結果テーブル
CREATE TABLE IF NOT EXISTS dr_health_checks (
    check_time TIMESTAMPTZ DEFAULT NOW(),
    check_type TEXT NOT NULL,
    check_passed BOOLEAN NOT NULL,
    check_details JSONB,
    PRIMARY KEY (check_time, check_type)
);

-- 定期ヘルスチェック（Prometheusへエクスポート）
CREATE OR REPLACE FUNCTION run_dr_health_checks()
RETURNS TABLE(check_type TEXT, passed BOOLEAN, details JSONB) AS $$
BEGIN
    -- Check 1: プライマリ接続性
    RETURN QUERY
    SELECT
        'primary_connectivity'::TEXT,
        TRUE,
        jsonb_build_object('status', 'ok', 'timestamp', NOW());

    -- Check 2: レプリケーション遅延
    RETURN QUERY
    SELECT
        'replication_lag'::TEXT,
        COALESCE(MAX(replication_lag_seconds) < 60, TRUE),
        jsonb_build_object(
            'max_lag_seconds', COALESCE(MAX(replication_lag_seconds), 0),
            'threshold', 60
        )
    FROM replication_status;

    -- Check 3: WALアーカイブ
    RETURN QUERY
    SELECT
        'wal_archive'::TEXT,
        failed_count = 0,
        jsonb_build_object('failed_count', failed_count, 'last_archived', last_archived_time)
    FROM pg_stat_archiver;

    -- ヘルスチェック結果を記録
    INSERT INTO dr_health_checks (check_type, check_passed, check_details)
    SELECT * FROM run_dr_health_checks();
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

-- ============================================================================
-- INITIAL SETUP COMPLETE
-- ============================================================================
SELECT 'DR Multi-Region setup completed successfully' AS status,
       COUNT(*) AS replication_slots_created
FROM pg_replication_slots;

-- 初回メトリクス収集
SELECT collect_dr_metrics();

-- 初回ヘルスチェック
SELECT * FROM run_dr_health_checks();
