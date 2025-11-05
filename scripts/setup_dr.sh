#!/bin/bash
# ============================================================================
# DR Multi-Region Setup Script (NASA/Google Level)
# ============================================================================
# このスクリプトは以下を実行します:
# 1. プライマリDBでレプリケーション設定
# 2. スタンバイDBの初期化（pg_basebackup）
# 3. 自動フェイルオーバー監視の設定
# 4. Prometheusメトリクス出力の設定
#
# 目標: RPO < 1h, RTO < 4h
# ============================================================================

set -euo pipefail

# ============================================================================
# CONFIGURATION
# ============================================================================
PRIMARY_HOST="${PRIMARY_HOST:-postgres-primary}"
PRIMARY_PORT="${PRIMARY_PORT:-5432}"
PRIMARY_USER="${PRIMARY_USER:-cqox_admin}"
PRIMARY_DB="${PRIMARY_DB:-cqox_prod}"

STANDBY_HOST="${STANDBY_HOST:-postgres-standby}"
STANDBY_PORT="${STANDBY_PORT:-5432}"
STANDBY_DATA_DIR="${STANDBY_DATA_DIR:-/var/lib/postgresql/data-standby}"

REPLICATION_USER="replicator"
REPLICATION_PASSWORD="${REPLICATION_PASSWORD:-CHANGE_ME_REPLICATION_PASSWORD}"

LOG_FILE="${LOG_FILE:-/var/log/cqox/dr_setup.log}"
METRICS_FILE="${METRICS_FILE:-/var/lib/cqox/dr_metrics.prom}"

# ============================================================================
# LOGGING
# ============================================================================
log() {
    echo "[$(date +'%Y-%m-%d %H:%M:%S')] $*" | tee -a "${LOG_FILE}"
}

log_error() {
    echo "[$(date +'%Y-%m-%d %H:%M:%S')] ERROR: $*" | tee -a "${LOG_FILE}" >&2
}

# ============================================================================
# STEP 1: PRIMARY DATABASE SETUP
# ============================================================================
setup_primary() {
    log "========================================="
    log "STEP 1: Setting up PRIMARY database"
    log "========================================="

    # PostgreSQL設定ファイルの更新（レプリケーション有効化）
    log "Configuring postgresql.conf for replication..."
    cat <<EOF | PGPASSWORD="${POSTGRES_PASSWORD}" psql -h "${PRIMARY_HOST}" -U "${PRIMARY_USER}" -d "${PRIMARY_DB}"
-- Enable replication
ALTER SYSTEM SET wal_level = 'replica';
ALTER SYSTEM SET max_wal_senders = 10;
ALTER SYSTEM SET max_replication_slots = 10;
ALTER SYSTEM SET wal_keep_size = '2GB';
ALTER SYSTEM SET hot_standby = on;

-- Archive configuration (for PITR)
ALTER SYSTEM SET archive_mode = on;
ALTER SYSTEM SET archive_command = 'test ! -f /mnt/wal_archive/%f && cp %p /mnt/wal_archive/%f';
ALTER SYSTEM SET archive_timeout = '300s';  -- 5分ごとにWAL切替

-- Synchronous replication (RPO = 0)
-- ALTER SYSTEM SET synchronous_commit = 'remote_apply';
-- ALTER SYSTEM SET synchronous_standby_names = 'standby_us_west_2';

-- For RPO < 1h, we use asynchronous replication with monitoring
ALTER SYSTEM SET synchronous_commit = 'local';

-- Load configuration
SELECT pg_reload_conf();
EOF

    log "✅ Primary configuration updated"

    # レプリケーションスクリプトの実行
    log "Running replication setup SQL..."
    PGPASSWORD="${POSTGRES_PASSWORD}" psql -h "${PRIMARY_HOST}" -U "${PRIMARY_USER}" -d "${PRIMARY_DB}" \
        -f /app/db/replication-setup.sql >> "${LOG_FILE}" 2>&1

    log "✅ Replication setup completed"

    # pg_hba.conf更新（レプリケーション接続許可）
    log "Updating pg_hba.conf for replication..."
    cat <<EOF | PGPASSWORD="${POSTGRES_PASSWORD}" psql -h "${PRIMARY_HOST}" -U "${PRIMARY_USER}" -d "${PRIMARY_DB}"
-- Note: pg_hba.conf must be manually edited to add:
-- host replication replicator 0.0.0.0/0 scram-sha-256
-- Then reload: SELECT pg_reload_conf();
EOF

    log "⚠️  Manual step required: Update pg_hba.conf with:"
    log "   host replication replicator 0.0.0.0/0 scram-sha-256"
}

# ============================================================================
# STEP 2: STANDBY DATABASE INITIALIZATION
# ============================================================================
setup_standby() {
    log "========================================="
    log "STEP 2: Initializing STANDBY database"
    log "========================================="

    # 既存データディレクトリのバックアップ
    if [ -d "${STANDBY_DATA_DIR}" ]; then
        log "Backing up existing data directory..."
        mv "${STANDBY_DATA_DIR}" "${STANDBY_DATA_DIR}.backup.$(date +%s)" || true
    fi

    # pg_basebackupでベースバックアップ取得
    log "Running pg_basebackup from primary..."
    mkdir -p "${STANDBY_DATA_DIR}"

    PGPASSWORD="${REPLICATION_PASSWORD}" pg_basebackup \
        -h "${PRIMARY_HOST}" \
        -p "${PRIMARY_PORT}" \
        -U "${REPLICATION_USER}" \
        -D "${STANDBY_DATA_DIR}" \
        -Fp \
        -Xs \
        -P \
        -R \
        -S "standby_us_west_2" \
        >> "${LOG_FILE}" 2>&1

    log "✅ Base backup completed: ${STANDBY_DATA_DIR}"

    # standby.signalファイル作成（PostgreSQL 12+）
    log "Creating standby.signal..."
    touch "${STANDBY_DATA_DIR}/standby.signal"

    # postgresql.auto.conf更新（レプリケーション接続情報）
    log "Configuring replication connection..."
    cat <<EOF >> "${STANDBY_DATA_DIR}/postgresql.auto.conf"
# Replication Configuration
primary_conninfo = 'host=${PRIMARY_HOST} port=${PRIMARY_PORT} user=${REPLICATION_USER} password=${REPLICATION_PASSWORD} application_name=standby_us_west_2'
primary_slot_name = 'standby_us_west_2'
hot_standby = on
wal_receiver_timeout = 60s
EOF

    log "✅ Standby configuration completed"
    log "⚠️  Manual step required: Start PostgreSQL on standby server"
}

# ============================================================================
# STEP 3: MONITORING SETUP
# ============================================================================
setup_monitoring() {
    log "========================================="
    log "STEP 3: Setting up DR monitoring"
    log "========================================="

    # Prometheusメトリクス収集スクリプト
    cat <<'EOF' > /usr/local/bin/collect_dr_metrics.sh
#!/bin/bash
# DR Metrics collection for Prometheus
METRICS_FILE="${METRICS_FILE:-/var/lib/cqox/dr_metrics.prom}"
PRIMARY_HOST="${PRIMARY_HOST:-postgres-primary}"
PRIMARY_USER="${PRIMARY_USER:-cqox_admin}"
PRIMARY_DB="${PRIMARY_DB:-cqox_prod}"

# Collect metrics from primary
PGPASSWORD="${POSTGRES_PASSWORD}" psql -h "${PRIMARY_HOST}" -U "${PRIMARY_USER}" -d "${PRIMARY_DB}" \
    -t -A -c "SELECT metric_name, metric_value, metric_labels FROM dr_metrics WHERE metric_time > NOW() - INTERVAL '1 minute'" \
    | while IFS='|' read -r name value labels; do
        echo "${name}${labels} ${value}"
    done > "${METRICS_FILE}.tmp"

# Atomic update
mv "${METRICS_FILE}.tmp" "${METRICS_FILE}"
EOF

    chmod +x /usr/local/bin/collect_dr_metrics.sh
    log "✅ Metrics collection script created"

    # cron設定（15秒ごとにメトリクス収集）
    log "Setting up cron for metrics collection (every 15s)..."
    cat <<'EOF' > /etc/cron.d/cqox-dr-metrics
# Collect DR metrics every 15 seconds
* * * * * root /usr/local/bin/collect_dr_metrics.sh
* * * * * root sleep 15 && /usr/local/bin/collect_dr_metrics.sh
* * * * * root sleep 30 && /usr/local/bin/collect_dr_metrics.sh
* * * * * root sleep 45 && /usr/local/bin/collect_dr_metrics.sh
EOF

    log "✅ Cron job configured"

    # DB内のメトリクス収集関数を定期実行（PostgreSQLのcron拡張が必要）
    PGPASSWORD="${POSTGRES_PASSWORD}" psql -h "${PRIMARY_HOST}" -U "${PRIMARY_USER}" -d "${PRIMARY_DB}" <<'EOF'
-- pg_cron extension (if available)
CREATE EXTENSION IF NOT EXISTS pg_cron;

-- Schedule metrics collection every 15 seconds
-- Note: pg_cron minimum interval is 1 minute, so we schedule 4 jobs
SELECT cron.schedule('collect_dr_metrics_00', '* * * * *', 'SELECT collect_dr_metrics()');
SELECT cron.schedule('collect_dr_metrics_15', '* * * * *', 'SELECT pg_sleep(15), collect_dr_metrics()');
SELECT cron.schedule('collect_dr_metrics_30', '* * * * *', 'SELECT pg_sleep(30), collect_dr_metrics()');
SELECT cron.schedule('collect_dr_metrics_45', '* * * * *', 'SELECT pg_sleep(45), collect_dr_metrics()');

-- Schedule alert generation every 60 seconds
SELECT cron.schedule('generate_dr_alerts', '* * * * *', 'SELECT generate_dr_alerts()');

-- Schedule health checks every 60 seconds
SELECT cron.schedule('run_dr_health_checks', '* * * * *', 'SELECT run_dr_health_checks()');
EOF

    log "✅ Monitoring jobs scheduled"
}

# ============================================================================
# STEP 4: FAILOVER AUTOMATION
# ============================================================================
setup_failover_automation() {
    log "========================================="
    log "STEP 4: Setting up failover automation"
    log "========================================="

    # フェイルオーバー監視スクリプト
    cat <<'EOF' > /usr/local/bin/monitor_primary.sh
#!/bin/bash
# Monitor primary database health and trigger failover if needed
set -euo pipefail

PRIMARY_HOST="${PRIMARY_HOST:-postgres-primary}"
PRIMARY_PORT="${PRIMARY_PORT:-5432}"
PRIMARY_USER="${PRIMARY_USER:-cqox_admin}"
PRIMARY_DB="${PRIMARY_DB:-cqox_prod}"

STANDBY_DATA_DIR="${STANDBY_DATA_DIR:-/var/lib/postgresql/data-standby}"
FAILOVER_TRIGGER="${FAILOVER_TRIGGER:-/tmp/trigger_failover}"

LOG_FILE="/var/log/cqox/failover_monitor.log"

log() {
    echo "[$(date +'%Y-%m-%d %H:%M:%S')] $*" | tee -a "${LOG_FILE}"
}

# Primary健全性チェック
check_primary() {
    if PGPASSWORD="${POSTGRES_PASSWORD}" pg_isready -h "${PRIMARY_HOST}" -p "${PRIMARY_PORT}" -U "${PRIMARY_USER}" > /dev/null 2>&1; then
        return 0  # Healthy
    else
        return 1  # Unhealthy
    fi
}

# フェイルオーバー実行
trigger_failover() {
    log "🚨 PRIMARY FAILURE DETECTED - Initiating failover..."
    log "Target RTO: < 4 hours"

    # ステップ1: スタンバイ準備状態確認
    log "Step 1: Checking standby readiness..."
    PGPASSWORD="${POSTGRES_PASSWORD}" psql -h localhost -U "${PRIMARY_USER}" -d "${PRIMARY_DB}" \
        -c "SELECT * FROM check_standby_promotion_readiness()" | tee -a "${LOG_FILE}"

    # ステップ2: スタンバイをプライマリに昇格
    log "Step 2: Promoting standby to primary..."
    pg_ctl promote -D "${STANDBY_DATA_DIR}" >> "${LOG_FILE}" 2>&1

    log "✅ Standby promoted to primary"
    log "⚠️  Manual steps required:"
    log "   1. Update DNS/Load Balancer to point to new primary"
    log "   2. Reconfigure old primary as new standby (when recovered)"
    log "   3. Update application connection strings"
    log "   4. Notify operations team"

    # アラート送信（PagerDuty/Slack/etc）
    # curl -X POST ... (integration code here)
}

# メイン監視ループ
FAILURE_COUNT=0
MAX_FAILURES=3  # 3回連続失敗でフェイルオーバー

while true; do
    if check_primary; then
        FAILURE_COUNT=0
        log "✓ Primary is healthy"
    else
        FAILURE_COUNT=$((FAILURE_COUNT + 1))
        log "✗ Primary check failed (${FAILURE_COUNT}/${MAX_FAILURES})"

        if [ "${FAILURE_COUNT}" -ge "${MAX_FAILURES}" ]; then
            trigger_failover
            break  # フェイルオーバー後は終了
        fi
    fi

    sleep 30  # 30秒ごとにチェック
done
EOF

    chmod +x /usr/local/bin/monitor_primary.sh
    log "✅ Failover monitoring script created"

    # systemdサービス化（継続的監視）
    cat <<'EOF' > /etc/systemd/system/cqox-failover-monitor.service
[Unit]
Description=CQOx DR Failover Monitor
After=network.target

[Service]
Type=simple
User=postgres
ExecStart=/usr/local/bin/monitor_primary.sh
Restart=always
RestartSec=60

[Install]
WantedBy=multi-user.target
EOF

    log "✅ Systemd service configured"
    log "⚠️  Manual step required: systemctl enable cqox-failover-monitor.service"
}

# ============================================================================
# STEP 5: VALIDATION
# ============================================================================
validate_setup() {
    log "========================================="
    log "STEP 5: Validating DR setup"
    log "========================================="

    # レプリケーション状態確認
    log "Checking replication status..."
    PGPASSWORD="${POSTGRES_PASSWORD}" psql -h "${PRIMARY_HOST}" -U "${PRIMARY_USER}" -d "${PRIMARY_DB}" \
        -c "SELECT * FROM replication_status;" | tee -a "${LOG_FILE}"

    # WALアーカイブ状態確認
    log "Checking WAL archive status..."
    PGPASSWORD="${POSTGRES_PASSWORD}" psql -h "${PRIMARY_HOST}" -U "${PRIMARY_USER}" -d "${PRIMARY_DB}" \
        -c "SELECT * FROM wal_archive_status;" | tee -a "${LOG_FILE}"

    # ヘルスチェック実行
    log "Running health checks..."
    PGPASSWORD="${POSTGRES_PASSWORD}" psql -h "${PRIMARY_HOST}" -U "${PRIMARY_USER}" -d "${PRIMARY_DB}" \
        -c "SELECT * FROM run_dr_health_checks();" | tee -a "${LOG_FILE}"

    log "========================================="
    log "✅ DR SETUP COMPLETED"
    log "========================================="
    log ""
    log "Summary:"
    log "  - Primary: ${PRIMARY_HOST}:${PRIMARY_PORT}"
    log "  - Standby: ${STANDBY_HOST}:${STANDBY_PORT}"
    log "  - RPO Target: < 1 hour"
    log "  - RTO Target: < 4 hours"
    log "  - Monitoring: Enabled (Prometheus metrics)"
    log "  - Failover: Automated (3-failure threshold)"
    log ""
    log "Next steps:"
    log "  1. Review pg_hba.conf on primary"
    log "  2. Start PostgreSQL on standby"
    log "  3. Enable failover monitor service"
    log "  4. Configure Prometheus to scrape metrics from ${METRICS_FILE}"
    log "  5. Set up alerting rules in Prometheus/Alertmanager"
    log ""
    log "Documentation: /docs/dr-runbook.md"
}

# ============================================================================
# MAIN EXECUTION
# ============================================================================
main() {
    log "========================================="
    log "CQOx DR Multi-Region Setup"
    log "========================================="
    log "Starting at: $(date)"
    log ""

    # Create log directory
    mkdir -p "$(dirname "${LOG_FILE}")"
    mkdir -p "$(dirname "${METRICS_FILE}")"

    # Execute setup steps
    setup_primary
    setup_standby
    setup_monitoring
    setup_failover_automation
    validate_setup

    log "Setup completed at: $(date)"
}

# Run if not sourced
if [ "${BASH_SOURCE[0]}" = "${0}" ]; then
    main "$@"
fi
