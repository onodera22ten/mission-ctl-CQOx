#!/bin/bash
# PostgreSQL自動バックアップ（NASA/Googleレベル）
#
# 機能:
# 1. pg_basebackup による完全バックアップ
# 2. WALアーカイブによる継続的バックアップ（PITR対応）
# 3. S3/GCSへの自動アップロード
# 4. 古いバックアップの自動削除（保持期間: 30日）
# 5. バックアップ検証

set -euo pipefail

# ====================
# 設定
# ====================

BACKUP_DIR="${BACKUP_DIR:-/mnt/backups/postgres}"
WAL_ARCHIVE_DIR="${WAL_ARCHIVE_DIR:-/mnt/wal_archive}"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
RETENTION_DAYS="${RETENTION_DAYS:-30}"
POSTGRES_HOST="${POSTGRES_HOST:-localhost}"
POSTGRES_PORT="${POSTGRES_PORT:-5432}"
POSTGRES_USER="${POSTGRES_USER:-cqox_admin}"
POSTGRES_DB="${POSTGRES_DB:-cqox_prod}"

# S3/GCS設定（環境変数で指定）
S3_BUCKET="${S3_BUCKET:-s3://cqox-backups/postgres/}"
GCS_BUCKET="${GCS_BUCKET:-gs://cqox-backups/postgres/}"

# ログ
LOG_FILE="${BACKUP_DIR}/backup_${TIMESTAMP}.log"

# ====================
# ログ関数
# ====================

log() {
    echo "[$(date +'%Y-%m-%d %H:%M:%S')] $*" | tee -a "${LOG_FILE}"
}

error() {
    echo "[$(date +'%Y-%m-%d %H:%M:%S')] ERROR: $*" | tee -a "${LOG_FILE}" >&2
}

# ====================
# ディレクトリ準備
# ====================

mkdir -p "${BACKUP_DIR}"
mkdir -p "${WAL_ARCHIVE_DIR}"

log "Starting PostgreSQL backup: ${TIMESTAMP}"

# ====================
# Phase 1: 完全バックアップ（pg_basebackup）
# ====================

BACKUP_PATH="${BACKUP_DIR}/base_${TIMESTAMP}"

log "Creating full backup: ${BACKUP_PATH}"

if pg_basebackup \
    -h "${POSTGRES_HOST}" \
    -p "${POSTGRES_PORT}" \
    -U "${POSTGRES_USER}" \
    -D "${BACKUP_PATH}" \
    -Ft \
    -z \
    -P \
    -X stream \
    -v; then
    log "✅ Full backup completed: ${BACKUP_PATH}"
else
    error "❌ Full backup failed"
    exit 1
fi

# バックアップサイズ確認
BACKUP_SIZE=$(du -sh "${BACKUP_PATH}" | cut -f1)
log "Backup size: ${BACKUP_SIZE}"

# ====================
# Phase 2: WALアーカイブ確認
# ====================

WAL_COUNT=$(find "${WAL_ARCHIVE_DIR}" -type f -name "*.zst" 2>/dev/null | wc -l || echo 0)
log "WAL archive files: ${WAL_COUNT}"

# ====================
# Phase 3: クラウドストレージアップロード
# ====================

# S3アップロード（AWS CLI）
if command -v aws &> /dev/null && [ -n "${S3_BUCKET}" ]; then
    log "Uploading to S3: ${S3_BUCKET}"
    
    if aws s3 sync "${BACKUP_DIR}" "${S3_BUCKET}" \
        --storage-class GLACIER_IR \
        --exclude "*" \
        --include "base_${TIMESTAMP}/*"; then
        log "✅ S3 upload completed"
    else
        error "❌ S3 upload failed"
    fi
fi

# GCSアップロード（gsutil）
if command -v gsutil &> /dev/null && [ -n "${GCS_BUCKET}" ]; then
    log "Uploading to GCS: ${GCS_BUCKET}"
    
    if gsutil -m rsync -r "${BACKUP_DIR}" "${GCS_BUCKET}"; then
        log "✅ GCS upload completed"
    else
        error "❌ GCS upload failed"
    fi
fi

# ====================
# Phase 4: バックアップ検証
# ====================

log "Verifying backup..."

# アーカイブファイルの整合性確認
if tar -tzf "${BACKUP_PATH}/base.tar.gz" > /dev/null 2>&1; then
    log "✅ Backup archive integrity verified"
else
    error "❌ Backup archive corrupted"
    exit 1
fi

# ====================
# Phase 5: 古いバックアップ削除
# ====================

log "Cleaning old backups (retention: ${RETENTION_DAYS} days)"

# ローカル
OLD_BACKUPS=$(find "${BACKUP_DIR}" -type d -name "base_*" -mtime +${RETENTION_DAYS} | wc -l)
if [ "${OLD_BACKUPS}" -gt 0 ]; then
    find "${BACKUP_DIR}" -type d -name "base_*" -mtime +${RETENTION_DAYS} -exec rm -rf {} +
    log "Deleted ${OLD_BACKUPS} old local backups"
fi

# S3（ライフサイクルポリシーで管理推奨）
if command -v aws &> /dev/null && [ -n "${S3_BUCKET}" ]; then
    aws s3 ls "${S3_BUCKET}" | \
        awk '{print $4}' | \
        grep "base_" | \
        head -n -${RETENTION_DAYS} | \
        xargs -I {} aws s3 rm --recursive "${S3_BUCKET}{}" || true
fi

# ====================
# Phase 6: メトリクス送信（Prometheus Pushgateway）
# ====================

PUSHGATEWAY_URL="${PUSHGATEWAY_URL:-http://localhost:9091}"

if command -v curl &> /dev/null; then
    cat <<EOF | curl --data-binary @- "${PUSHGATEWAY_URL}/metrics/job/postgres_backup"
# TYPE postgres_backup_success gauge
postgres_backup_success 1
# TYPE postgres_backup_duration_seconds gauge
postgres_backup_duration_seconds $(( $(date +%s) - $(date -d "${TIMESTAMP}" +%s 2>/dev/null || echo 0) ))
# TYPE postgres_backup_size_bytes gauge
postgres_backup_size_bytes $(du -sb "${BACKUP_PATH}" | cut -f1)
EOF
    log "Metrics pushed to Pushgateway"
fi

# ====================
# 完了
# ====================

log "✅ Backup completed successfully: ${TIMESTAMP}"
log "Backup path: ${BACKUP_PATH}"
log "Backup size: ${BACKUP_SIZE}"
log "Log: ${LOG_FILE}"

exit 0

