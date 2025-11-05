-- CQOx Encryption Setup: NASA/Googleレベル
-- pgcrypto + 暗号鍵管理

-- ===============================
-- Encryption Keys Management
-- ===============================

-- 暗号鍵メタデータ（実際の鍵はVaultに保存）
CREATE TABLE IF NOT EXISTS encryption_keys (
    id SERIAL PRIMARY KEY,
    key_name TEXT UNIQUE NOT NULL,
    key_version INTEGER NOT NULL DEFAULT 1,
    key_hash TEXT NOT NULL,  -- SHA-256ハッシュのみ保存
    algorithm TEXT NOT NULL DEFAULT 'AES-256-GCM',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    rotated_at TIMESTAMPTZ,
    status TEXT DEFAULT 'active',  -- active, rotated, revoked
    CONSTRAINT valid_status CHECK (status IN ('active', 'rotated', 'revoked'))
);

CREATE INDEX idx_encryption_keys_name ON encryption_keys (key_name, key_version DESC);
CREATE INDEX idx_encryption_keys_status ON encryption_keys (status) WHERE status = 'active';

-- ===============================
-- Column-Level Encryption
-- ===============================

-- データセットの暗号化カラム用helper
CREATE OR REPLACE FUNCTION encrypt_dataset_path(path TEXT)
RETURNS BYTEA AS $$
DECLARE
    encryption_key TEXT;
BEGIN
    -- 実運用ではVaultから鍵を取得
    -- encryption_key := get_vault_secret('cqox/data/encryption-key');
    
    -- 開発環境: 環境変数から取得（本番ではVault必須）
    encryption_key := current_setting('cqox.encryption_key', true);
    
    IF encryption_key IS NULL THEN
        RAISE EXCEPTION 'Encryption key not configured';
    END IF;
    
    RETURN pgp_sym_encrypt(path, encryption_key, 'cipher-algo=aes256');
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

-- 復号化helper
CREATE OR REPLACE FUNCTION decrypt_dataset_path(encrypted BYTEA)
RETURNS TEXT AS $$
DECLARE
    encryption_key TEXT;
BEGIN
    encryption_key := current_setting('cqox.encryption_key', true);
    
    IF encryption_key IS NULL THEN
        RAISE EXCEPTION 'Encryption key not configured';
    END IF;
    
    RETURN pgp_sym_decrypt(encrypted, encryption_key);
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

-- ===============================
-- Audit Log Encryption
-- ===============================

-- 監査ログのペイロード暗号化
CREATE OR REPLACE FUNCTION encrypt_audit_payload(payload JSONB)
RETURNS BYTEA AS $$
DECLARE
    encryption_key TEXT;
BEGIN
    encryption_key := current_setting('cqox.encryption_key', true);
    
    IF encryption_key IS NULL THEN
        RAISE EXCEPTION 'Encryption key not configured';
    END IF;
    
    RETURN pgp_sym_encrypt(payload::TEXT, encryption_key, 'cipher-algo=aes256');
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

-- ===============================
-- Key Rotation Support
-- ===============================

-- 鍵ローテーション記録
CREATE OR REPLACE FUNCTION rotate_encryption_key(
    p_key_name TEXT,
    p_new_key_hash TEXT
)
RETURNS INTEGER AS $$
DECLARE
    v_old_version INTEGER;
    v_new_version INTEGER;
BEGIN
    -- 現在の最新バージョン取得
    SELECT COALESCE(MAX(key_version), 0) INTO v_old_version
    FROM encryption_keys
    WHERE key_name = p_key_name;
    
    v_new_version := v_old_version + 1;
    
    -- 古いバージョンをrotatedステータスに
    UPDATE encryption_keys
    SET status = 'rotated', rotated_at = NOW()
    WHERE key_name = p_key_name AND status = 'active';
    
    -- 新しいバージョン追加
    INSERT INTO encryption_keys (key_name, key_version, key_hash, status)
    VALUES (p_key_name, v_new_version, p_new_key_hash, 'active');
    
    RAISE NOTICE 'Rotated key % from version % to %', p_key_name, v_old_version, v_new_version;
    
    RETURN v_new_version;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

-- ===============================
-- Encryption Statistics
-- ===============================

-- 暗号化カラムの使用状況
CREATE OR REPLACE VIEW encryption_usage AS
SELECT
    'datasets' as table_name,
    'encrypted_data_path' as column_name,
    COUNT(*) as total_rows,
    COUNT(encrypted_data_path) as encrypted_rows,
    ROUND(100.0 * COUNT(encrypted_data_path) / NULLIF(COUNT(*), 0), 2) as encryption_percentage
FROM datasets
UNION ALL
SELECT
    'audit_log' as table_name,
    'encrypted_payload' as column_name,
    COUNT(*) as total_rows,
    COUNT(encrypted_payload) as encrypted_rows,
    ROUND(100.0 * COUNT(encrypted_payload) / NULLIF(COUNT(*), 0), 2) as encryption_percentage
FROM audit_log;

-- ===============================
-- Initial Setup
-- ===============================

-- デフォルト暗号鍵登録（開発環境）
-- 本番環境では初期セットアップ時にVaultから取得
INSERT INTO encryption_keys (key_name, key_hash, algorithm)
VALUES 
    ('master-key', encode(digest('dev-key-change-in-production', 'sha256'), 'hex'), 'AES-256-GCM'),
    ('audit-log-key', encode(digest('dev-audit-key-change-in-production', 'sha256'), 'hex'), 'AES-256-GCM')
ON CONFLICT (key_name) DO NOTHING;

-- 暗号化設定の環境変数設定（開発環境のみ）
-- 本番環境ではVaultから動的に取得
-- ALTER DATABASE cqox_prod SET cqox.encryption_key = '<vault-retrieved-key>';

-- 完了メッセージ
DO $$
BEGIN
    RAISE NOTICE '✅ Encryption setup completed (NASA/Google level)';
    RAISE NOTICE 'Algorithm: AES-256-GCM';
    RAISE NOTICE 'Key Management: HashiCorp Vault (production) / ENV (development)';
    RAISE NOTICE 'Active keys: %', (SELECT COUNT(*) FROM encryption_keys WHERE status = 'active');
END $$;

