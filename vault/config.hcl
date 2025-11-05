# HashiCorp Vault Configuration (NASA/Google Level)

# Storage backend
storage "file" {
  path = "/vault/data"
}

# Listener (本番ではTLS必須)
listener "tcp" {
  address     = "0.0.0.0:8200"
  tls_disable = 0  # 本番環境ではTLS有効化必須
  
  # 本番環境用TLS設定（コメント解除して使用）
  # tls_cert_file = "/vault/tls/vault.crt"
  # tls_key_file  = "/vault/tls/vault.key"
}

# API address
api_addr = "http://127.0.0.1:8200"

# UI
ui = true

# Telemetry (Prometheusエクスポート)
telemetry {
  prometheus_retention_time = "30s"
  disable_hostname = true
}

# Seal configuration (本番環境ではAuto Unseal推奨)
# AWS KMS Auto Unseal example:
# seal "awskms" {
#   region     = "us-east-1"
#   kms_key_id = "arn:aws:kms:us-east-1:123456789012:key/..."
# }

# Log level
log_level = "Info"

# Max lease TTL
max_lease_ttl = "768h"
default_lease_ttl = "768h"

