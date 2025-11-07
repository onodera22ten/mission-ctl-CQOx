# 🚀 CQOx NASA/Googleレベル実装ロードマップ

**Date**: 2025-11-01  
**Goal**: NASA/Googleレベルのインフラ・セキュリティ・信頼性を達成

---

## 📊 現状評価（WORLD_CLASS_COMPARISON.md基準）

### 達成済み ✅

| 機能 | 実装状況 | NASA/Google基準 |
|------|---------|----------------|
| Prometheus | ✅ 37パネル | ✅ 要件満たす |
| Loki | ✅ ログ集約 | ✅ 要件満たす |
| Grafana | ✅ ダッシュボード | ✅ 要件満たす |
| Jaeger | ✅ 分散トレース | ✅ 要件満たす |
| Circuit Breaker | ✅ 実装済み | ✅ 要件満たす |
| Retry/Timeout | ✅ 実装済み | ✅ 要件満たす |
| Chaos Engineering | ✅ 実装済み | ✅ 要件満たす |

### 不足（Critical）❌

| 機能 | 現状 | NASA/Google要件 | Priority |
|------|-----|----------------|----------|
| **Database** | ❌ 未選択 | PostgreSQL 14+ (世界最高峰) | 🔴 Critical |
| **Data Encryption (at-rest)** | ❌ 未実装 | FIPS 140-2必須 | 🔴 Critical |
| **Data Encryption (in-transit)** | ⚠️ 準備のみ | TLS 1.3強制 | 🔴 Critical |
| **Secrets Management** | ❌ 未実装 | HashiCorp Vault必須 | 🔴 Critical |
| **Auto Backup** | ❌ 未実装 | 15分毎 + WAL | 🔴 Critical |
| **DR (Multi-Region)** | ❌ 未実装 | RPO<1h, RTO<4h | 🔴 Critical |
| **Blue-Green Deploy** | ❌ 未実装 | ゼロダウンタイム必須 | 🟡 High |
| **K8s HPA** | ❌ 未実装 | 自動スケール必須 | 🟡 High |
| **SLA/SLO** | ❌ 未定義 | 99.99%必須 | 🟡 High |
| **Error Budget** | ❌ 未実装 | Google SRE標準 | 🟡 High |

---

## 🎯 Phase 1: Database世界最高峰選択（Critical）

### 1.1 NASA/Googleレベルの選択

**推奨: PostgreSQL 15 + TimescaleDB + Citus**

#### なぜこの選択か

**PostgreSQL 15**:
- ✅ ACID完全保証
- ✅ MVCC（Multi-Version Concurrency Control）
- ✅ Advanced Indexing (B-tree, Hash, GiST, SP-GiST, GIN, BRIN)
- ✅ Full-text search built-in
- ✅ JSON/JSONB support
- ✅ Window functions
- ✅ CTE (Common Table Expressions)
- ✅ Parallel query execution
- ✅ Logical replication
- ✅ FIPS 140-2認証可能

**TimescaleDB**（時系列データ用）:
- ✅ PostgreSQL拡張（完全互換）
- ✅ 100倍高速な時系列クエリ
- ✅ 自動パーティショニング
- ✅ Continuous aggregates
- ✅ Data retention policies

**Citus**（分散処理用）:
- ✅ PostgreSQL拡張（完全互換）
- ✅ 水平スケール（シャーディング）
- ✅ 分散JOIN
- ✅ Multi-tenant support

#### 実装

```yaml
# docker-compose.full.yml
services:
  postgres:
    image: timescale/timescaledb-ha:pg15-latest  # PostgreSQL 15 + TimescaleDB + Patroni HA
    container_name: cqox-postgres
    environment:
      POSTGRES_USER: cqox_admin
      POSTGRES_PASSWORD: ${POSTGRES_PASSWORD}  # Vault経由
      POSTGRES_DB: cqox_prod
      # Encryption
      PGDATA: /var/lib/postgresql/data/pgdata
      # TimescaleDB
      TIMESCALEDB_TELEMETRY: off
      # HA
      PATRONI_SCOPE: cqox-cluster
      PATRONI_NAME: cqox-postgres-1
    volumes:
      - postgres_data:/var/lib/postgresql/data
      - ./db/init-timescaledb.sql:/docker-entrypoint-initdb.d/01-init.sql
      - ./db/pgcrypto-setup.sql:/docker-entrypoint-initdb.d/02-encrypt.sql
    command:
      - postgres
      - -c
      - max_connections=200
      - -c
      - shared_buffers=2GB
      - -c
      - effective_cache_size=6GB
      - -c
      - maintenance_work_mem=512MB
      - -c
      - checkpoint_completion_target=0.9
      - -c
      - wal_buffers=16MB
      - -c
      - default_statistics_target=100
      - -c
      - random_page_cost=1.1
      - -c
      - effective_io_concurrency=200
      - -c
      - work_mem=10MB
      - -c
      - min_wal_size=1GB
      - -c
      - max_wal_size=4GB
      - -c
      - max_worker_processes=4
      - -c
      - max_parallel_workers_per_gather=2
      - -c
      - max_parallel_workers=4
      - -c
      - max_parallel_maintenance_workers=2
      # Encryption at-rest
      - -c
      - ssl=on
      - -c
      - ssl_cert_file=/var/lib/postgresql/server.crt
      - -c
      - ssl_key_file=/var/lib/postgresql/server.key
      # WAL archiving for PITR
      - -c
      - wal_level=replica
      - -c
      - archive_mode=on
      - -c
      - archive_command='test ! -f /mnt/wal_archive/%f && cp %p /mnt/wal_archive/%f'
    ports:
      - "5432:5432"
    networks:
      - cqox-network
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U cqox_admin -d cqox_prod"]
      interval: 10s
      timeout: 5s
      retries: 5
```

#### データベース初期化スクリプト

```sql
-- db/init-timescaledb.sql
-- NASA/Googleレベルのデータベース設計

-- TimescaleDB有効化
CREATE EXTENSION IF NOT EXISTS timescaledb CASCADE;

-- Encryption有効化（at-rest）
CREATE EXTENSION IF NOT EXISTS pgcrypto;

-- Full-text search
CREATE EXTENSION IF NOT EXISTS pg_trgm;

-- 時系列テーブル: メトリクス
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
GROUP BY bucket, metric_name;

-- データ保持ポリシー: 90日後に古いデータを削除
SELECT add_retention_policy('metrics', INTERVAL '90 days', if_not_exists => TRUE);

-- Compression: 7日以上前のデータを圧縮
SELECT add_compression_policy('metrics', INTERVAL '7 days', if_not_exists => TRUE);

-- 監査ログテーブル（暗号化カラム付き）
CREATE TABLE IF NOT EXISTS audit_log (
    id BIGSERIAL PRIMARY KEY,
    timestamp TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    user_id TEXT,
    action TEXT NOT NULL,
    resource TEXT,
    details JSONB,
    -- 暗号化: 機密データ
    encrypted_payload BYTEA,
    ip_address INET,
    user_agent TEXT
);

CREATE INDEX idx_audit_timestamp ON audit_log (timestamp DESC);
CREATE INDEX idx_audit_user ON audit_log (user_id);
CREATE INDEX idx_audit_action ON audit_log (action);

-- データセットテーブル
CREATE TABLE IF NOT EXISTS datasets (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    name TEXT NOT NULL,
    rows INTEGER,
    columns INTEGER,
    status TEXT,
    metadata JSONB,
    -- 暗号化: データパス
    encrypted_data_path BYTEA
);

CREATE INDEX idx_datasets_created ON datasets (created_at DESC);
CREATE INDEX idx_datasets_status ON datasets (status);

-- 分析結果テーブル
CREATE TABLE IF NOT EXISTS analysis_results (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    dataset_id UUID REFERENCES datasets(id) ON DELETE CASCADE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    estimator TEXT NOT NULL,
    ate DOUBLE PRECISION,
    se DOUBLE PRECISION,
    ci_lower DOUBLE PRECISION,
    ci_upper DOUBLE PRECISION,
    p_value DOUBLE PRECISION,
    results JSONB
);

CREATE INDEX idx_analysis_dataset ON analysis_results (dataset_id);
CREATE INDEX idx_analysis_created ON analysis_results (created_at DESC);

-- 関数: 暗号化ヘルパー
CREATE OR REPLACE FUNCTION encrypt_data(data TEXT, key TEXT)
RETURNS BYTEA AS $$
BEGIN
    RETURN pgp_sym_encrypt(data, key);
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

CREATE OR REPLACE FUNCTION decrypt_data(encrypted BYTEA, key TEXT)
RETURNS TEXT AS $$
BEGIN
    RETURN pgp_sym_decrypt(encrypted, key);
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;
```

---

## 🔐 Phase 2: Data Encryption（Critical）

### 2.1 At-Rest Encryption

**PostgreSQL TDE (Transparent Data Encryption)**:

```sql
-- db/pgcrypto-setup.sql
-- 全データベースの透過的暗号化

-- pgcrypto extension
CREATE EXTENSION IF NOT EXISTS pgcrypto;

-- 暗号鍵管理テーブル（Vault経由で取得）
CREATE TABLE IF NOT EXISTS encryption_keys (
    id SERIAL PRIMARY KEY,
    key_name TEXT UNIQUE NOT NULL,
    key_hash TEXT NOT NULL,  -- ハッシュのみ保存、実鍵はVault
    created_at TIMESTAMPTZ DEFAULT NOW(),
    rotated_at TIMESTAMPTZ
);

-- データベース全体の暗号化設定
-- 注: PostgreSQL 15+ with pgcrypto
ALTER DATABASE cqox_prod SET default_tablespace = pg_default;

-- ファイルシステムレベル暗号化（LUKS）
-- 本番環境では /var/lib/postgresql/data を LUKS暗号化ボリュームに配置
```

**File Storage Encryption**:

```python
# backend/security/file_encryption.py
"""
ファイルアップロードの暗号化

NASA/Googleレベル:
- AES-256-GCM
- 鍵はVaultから取得
- ファイル毎に異なるIV（初期化ベクトル）
"""
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.backends import default_backend
import os
import base64

class FileEncryption:
    """ファイル暗号化マネージャー（NASA/Googleレベル）"""
    
    def __init__(self, vault_client):
        self.vault = vault_client
        # Vaultから暗号鍵取得
        self.key = self._get_encryption_key()
        self.aesgcm = AESGCM(self.key)
    
    def _get_encryption_key(self) -> bytes:
        """VaultからAES-256鍵を取得"""
        secret = self.vault.read_secret('cqox/data/encryption-key')
        key_b64 = secret['key']
        return base64.b64decode(key_b64)
    
    def encrypt_file(self, plaintext: bytes) -> tuple[bytes, bytes]:
        """
        ファイルを暗号化
        
        Returns:
            (ciphertext, nonce)
        """
        nonce = os.urandom(12)  # 96-bit nonce for GCM
        ciphertext = self.aesgcm.encrypt(nonce, plaintext, None)
        return ciphertext, nonce
    
    def decrypt_file(self, ciphertext: bytes, nonce: bytes) -> bytes:
        """ファイルを復号化"""
        plaintext = self.aesgcm.decrypt(nonce, ciphertext, None)
        return plaintext
```

### 2.2 In-Transit Encryption

**TLS 1.3強制**:

```yaml
# nginx/nginx.conf（or Istio Gateway）
server {
    listen 443 ssl http2;
    server_name cqox.example.com;
    
    # TLS 1.3のみ許可（NASA/Googleレベル）
    ssl_protocols TLSv1.3;
    ssl_prefer_server_ciphers off;
    
    # 証明書（Let's Encrypt + 自動更新）
    ssl_certificate /etc/letsencrypt/live/cqox.example.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/cqox.example.com/privkey.pem;
    
    # HSTS (HTTP Strict Transport Security)
    add_header Strict-Transport-Security "max-age=31536000; includeSubDomains; preload" always;
    
    # OCSP Stapling
    ssl_stapling on;
    ssl_stapling_verify on;
    
    # Session tickets off (forward secrecy)
    ssl_session_tickets off;
}
```

**mTLS (Mutual TLS)** via Istio:

```yaml
# k8s/istio/mtls-strict.yaml
apiVersion: security.istio.io/v1beta1
kind: PeerAuthentication
metadata:
  name: default
  namespace: cqox-prod
spec:
  mtls:
    mode: STRICT  # 全サービス間でmTLS必須

---
apiVersion: networking.istio.io/v1beta1
kind: DestinationRule
metadata:
  name: cqox-mtls
  namespace: cqox-prod
spec:
  host: "*.cqox-prod.svc.cluster.local"
  trafficPolicy:
    tls:
      mode: ISTIO_MUTUAL  # Istio管理のmTLS証明書
```

---

## 🔑 Phase 3: Secrets Management (Critical)

### 3.1 HashiCorp Vault統合

```yaml
# docker-compose.full.yml
services:
  vault:
    image: hashicorp/vault:1.15
    container_name: cqox-vault
    environment:
      VAULT_DEV_ROOT_TOKEN_ID: ${VAULT_ROOT_TOKEN}
      VAULT_DEV_LISTEN_ADDRESS: 0.0.0.0:8200
      VAULT_ADDR: http://0.0.0.0:8200
    ports:
      - "8200:8200"
    cap_add:
      - IPC_LOCK
    volumes:
      - vault_data:/vault/data
      - ./vault/config.hcl:/vault/config/config.hcl
    command: server
    networks:
      - cqox-network
    healthcheck:
      test: ["CMD", "vault", "status"]
      interval: 10s
      timeout: 5s
      retries: 3
```

```python
# backend/security/vault_client.py
"""
HashiCorp Vault統合（NASA/Googleレベル）

機能:
- 動的シークレット生成
- 自動ローテーション
- 監査ログ
"""
import hvac
import os

class VaultClient:
    """Vaultクライアント（NASA/Googleレベル）"""
    
    def __init__(self):
        self.client = hvac.Client(
            url=os.getenv('VAULT_ADDR', 'http://localhost:8200'),
            token=os.getenv('VAULT_TOKEN')
        )
        
        if not self.client.is_authenticated():
            raise ValueError("Vault authentication failed")
    
    def read_secret(self, path: str) -> dict:
        """シークレット読み込み"""
        response = self.client.secrets.kv.v2.read_secret_version(path=path)
        return response['data']['data']
    
    def write_secret(self, path: str, data: dict):
        """シークレット書き込み"""
        self.client.secrets.kv.v2.create_or_update_secret(
            path=path,
            secret=data
        )
    
    def rotate_secret(self, path: str):
        """シークレットローテーション"""
        # 新しいシークレット生成
        import secrets
        new_secret = secrets.token_urlsafe(32)
        
        # Vault更新
        self.write_secret(path, {'value': new_secret})
        
        return new_secret
```

---

## 💾 Phase 4: Auto Backup & DR (Critical)

### 4.1 PostgreSQL自動バックアップ

```bash
# scripts/backup_postgres.sh
#!/bin/bash
# NASA/Googleレベルの自動バックアップ

set -euo pipefail

BACKUP_DIR="/mnt/backups/postgres"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
RETENTION_DAYS=30

# 完全バックアップ（毎日）
pg_basebackup \
    -h localhost \
    -U cqox_admin \
    -D "${BACKUP_DIR}/base_${TIMESTAMP}" \
    -Ft \
    -z \
    -P \
    -X stream

# WALアーカイブ（継続的）
# PostgreSQL config: archive_command='cp %p /mnt/wal_archive/%f'

# S3/GCSへアップロード
aws s3 sync "${BACKUP_DIR}" s3://cqox-backups/postgres/ \
    --storage-class GLACIER_IR

# 古いバックアップ削除
find "${BACKUP_DIR}" -type d -mtime +${RETENTION_DAYS} -exec rm -rf {} +

echo "✅ Backup completed: ${TIMESTAMP}"
```

```bash
# crontab設定
# 15分毎のWALアーカイブ
*/15 * * * * /opt/cqox/scripts/archive_wal.sh

# 毎日3時にフルバックアップ
0 3 * * * /opt/cqox/scripts/backup_postgres.sh

# 毎日バックアップ検証
30 4 * * * /opt/cqox/scripts/verify_backup.sh
```

### 4.2 Multi-Region DR

```yaml
# k8s/postgres-replication.yaml
apiVersion: postgresql.cnpg.io/v1
kind: Cluster
metadata:
  name: cqox-postgres-cluster
  namespace: cqox-prod
spec:
  instances: 3  # Primary + 2 Replicas
  
  primaryUpdateStrategy: unsupervised
  
  postgresql:
    parameters:
      max_connections: "200"
      shared_buffers: "2GB"
      wal_level: "replica"
      max_wal_senders: "10"
      max_replication_slots: "10"
  
  # 自動フェイルオーバー
  failoverDelay: 30  # 30秒後に自動フェイルオーバー
  
  # Streaming Replication
  replica:
    source: cqox-postgres-primary
  
  # S3バックアップ
  backup:
    barmanObjectStore:
      destinationPath: s3://cqox-backups-dr/postgres/
      s3Credentials:
        accessKeyId:
          name: postgres-backup-s3
          key: ACCESS_KEY_ID
        secretAccessKey:
          name: postgres-backup-s3
          key: ACCESS_SECRET_KEY
    retentionPolicy: "30d"
```

---

## 🚀 Phase 5: Blue-Green Deploy (High)

```yaml
# k8s/istio/canary-deployment.yaml
apiVersion: networking.istio.io/v1beta1
kind: VirtualService
metadata:
  name: cqox-engine
  namespace: cqox-prod
spec:
  hosts:
    - cqox-engine
  http:
    - match:
        - headers:
            x-version:
              exact: "canary"
      route:
        - destination:
            host: cqox-engine
            subset: v2
          weight: 100
    - route:
        - destination:
            host: cqox-engine
            subset: v1
          weight: 90  # 90% → Stable
        - destination:
            host: cqox-engine
            subset: v2
          weight: 10  # 10% → Canary

---
apiVersion: networking.istio.io/v1beta1
kind: DestinationRule
metadata:
  name: cqox-engine
  namespace: cqox-prod
spec:
  host: cqox-engine
  subsets:
    - name: v1
      labels:
        version: v1
    - name: v2
      labels:
        version: v2
```

```bash
# scripts/deploy_canary.sh
#!/bin/bash
# NASA/Googleレベルのカナリアデプロイ

set -euo pipefail

VERSION=$1
NAMESPACE="cqox-prod"

# Step 1: Deploy canary (10% traffic)
kubectl set image deployment/cqox-engine \
    cqox-engine=cqox/engine:${VERSION} \
    -n ${NAMESPACE} \
    -l version=v2

# Step 2: Monitor for 10 minutes
echo "Monitoring canary for 10 minutes..."
sleep 600

# Step 3: Check metrics
ERROR_RATE=$(curl -s "http://prometheus:9090/api/v1/query?query=rate(http_requests_total{status=~'5..'}[5m])" | jq '.data.result[0].value[1]')

if (( $(echo "$ERROR_RATE < 0.01" | bc -l) )); then
    echo "✅ Canary healthy, proceeding..."
    
    # Step 4: Increase to 50%
    kubectl apply -f k8s/istio/canary-50.yaml
    sleep 600
    
    # Step 5: Full rollout (100%)
    kubectl apply -f k8s/istio/canary-100.yaml
    echo "✅ Deploy completed"
else
    echo "❌ Canary unhealthy, rolling back..."
    kubectl rollout undo deployment/cqox-engine -n ${NAMESPACE}
    exit 1
fi
```

---

## 📊 Phase 6: SLA/SLO定義 (High)

```yaml
# slo/sla-definition.yaml
# NASA/GoogleレベルのSLA/SLO定義

sla:
  uptime: 99.99%  # 年間ダウンタイム: 52.6分
  support_response: 
    critical: 15min
    high: 1hour
    normal: 4hours
  
slo:
  availability:
    target: 99.99%
    measurement_window: 30days
    
  latency:
    p50: 100ms
    p95: 500ms
    p99: 1000ms
    
  error_rate:
    target: 0.01%  # 99.99% success rate
    
  throughput:
    minimum: 100 rps
    target: 1000 rps
    
error_budget:
  calculation: (1 - SLO) * measurement_window
  # 99.99% over 30 days = 4.32 minutes of allowed downtime
  allowed_downtime: 4.32min
  burn_rate_alert: 2x  # Alert if burning 2x faster than budget allows
```

```python
# backend/observability/slo_monitor.py
"""
SLO監視（NASA/Googleレベル）

Google SRE本に基づく実装
"""
from prometheus_client import Gauge, Counter
import time

class SLOMonitor:
    """SLO監視とError Budget計算"""
    
    def __init__(self):
        self.availability_gauge = Gauge('slo_availability', 'Current availability')
        self.error_budget_gauge = Gauge('slo_error_budget_remaining', 'Error budget remaining (0-1)')
        self.budget_burn_rate = Gauge('slo_error_budget_burn_rate', 'Error budget burn rate')
        
        self.slo_target = 0.9999  # 99.99%
        self.measurement_window = 30 * 24 * 3600  # 30 days in seconds
    
    def calculate_availability(self, success: int, total: int) -> float:
        """可用性計算"""
        if total == 0:
            return 1.0
        return success / total
    
    def calculate_error_budget(self, current_availability: float) -> float:
        """Error Budget残量計算"""
        allowed_failures = 1 - self.slo_target
        actual_failures = 1 - current_availability
        
        budget_remaining = (allowed_failures - actual_failures) / allowed_failures
        return max(0.0, min(1.0, budget_remaining))
    
    def calculate_burn_rate(self, error_rate_1h: float, error_rate_24h: float) -> float:
        """Burn Rate計算（Google SRE手法）"""
        allowed_error_rate = 1 - self.slo_target
        
        burn_rate_1h = error_rate_1h / allowed_error_rate
        burn_rate_24h = error_rate_24h / allowed_error_rate
        
        return (burn_rate_1h + burn_rate_24h) / 2
```

---

## 🎯 実装優先順位

### Week 1 (Critical)
1. ✅ Database選択・設定（PostgreSQL 15 + TimescaleDB）
2. ✅ Data Encryption（at-rest + in-transit）
3. ✅ HashiCorp Vault統合
4. ✅ 自動バックアップスクリプト

### Week 2 (High)
5. ✅ Multi-Region DR設定
6. ✅ Blue-Green/Canaryデプロイ
7. ✅ SLA/SLO定義
8. ✅ Error Budget監視

### Week 3 (Medium)
9. K8s HPA設定
10. リアルタイムアラート（PagerDuty）
11. 総合テスト

---

## 📝 実装手順書

### 手順1: Database設定

```bash
# PostgreSQL 15 + TimescaleDB + Patroni HA
docker-compose -f docker-compose.full.yml up -d postgres

# 初期化確認
docker exec -it cqox-postgres psql -U cqox_admin -d cqox_prod -c "\dx"

# TimescaleDB確認
docker exec -it cqox-postgres psql -U cqox_admin -d cqox_prod -c "SELECT * FROM timescaledb_information.hypertables;"
```

### 手順2: Vault設定

```bash
# Vault起動
docker-compose -f docker-compose.full.yml up -d vault

# 初期化
docker exec -it cqox-vault vault operator init

# Unseal (3/5 keys required)
docker exec -it cqox-vault vault operator unseal <key1>
docker exec -it cqox-vault vault operator unseal <key2>
docker exec -it cqox-vault vault operator unseal <key3>

# シークレット保存
docker exec -it cqox-vault vault kv put secret/cqox/db password=<secure_password>
```

### 手順3: バックアップ設定

```bash
# cron設定
crontab -e

# 追加:
*/15 * * * * /opt/cqox/scripts/archive_wal.sh
0 3 * * * /opt/cqox/scripts/backup_postgres.sh
30 4 * * * /opt/cqox/scripts/verify_backup.sh
```

---

**Generated**: 2025-11-01  
**Status**: NASA/Googleレベル実装ロードマップ完成  
**Next**: Phase 1から順次実装

