// frontend/src/ui/App.tsx
import React, { useMemo, useState } from "react";
import { ResponsiveContainer, BarChart, Bar, XAxis, YAxis, Tooltip, ReferenceLine, Label } from "recharts";
import { uploadFile, fetchRolesProfile, inferRoles, analyzeComprehensive } from "../lib/client";
import FiguresPanel from "./FiguresPanel";
import MetricsDashboard from "../components/MetricsDashboard";

// 階層構造対応: 具体ドメイン（Level 2）のみ表示
const DOMAINS = ["education", "medical", "policy", "retail", "finance", "network"];

type Mapping = Record<string, string>;

export default function App() {
  const [file, setFile] = useState<File | null>(null);
  const [datasetId, setDatasetId] = useState("");
  const [domain, setDomain] = useState<string>("retail");
  const [profile, setProfile] = useState<any | null>(null);
  const [mapping, setMapping] = useState<Mapping>({});
  const [result, setResult] = useState<any | null>(null);
  const [busy, setBusy] = useState(false);
  const canAnalyze = useMemo(
    () => !!datasetId && !!mapping.y && !!mapping.treatment && !!mapping.unit_id,
    [datasetId, mapping]
  );

  async function onUpload() {
    if (!file) return;
    setBusy(true);
    try {
      const up = await uploadFile(file);
      setDatasetId(up.dataset_id);

      // Phase 3: 自動ロール推論を使用
      const inference = await inferRoles(up.dataset_id);

      // profileには meta情報を保持（UIで列選択に使用）
      setProfile({
        ...inference,
        meta: up.meta, // uploadFileからのmeta情報を追加
      });

      // 推論されたマッピングを設定（キー名をUIの形式に変換）
      const auto: Mapping = {
        y: inference.mapping.outcome || inference.mapping.y || "",
        treatment: inference.mapping.treatment || "",
        unit_id: inference.mapping.unit_id || "",
        time: inference.mapping.time || "",
        cost: inference.mapping.cost || "",
        log_propensity: inference.mapping.propensity || inference.mapping.log_propensity || "",
      };

      // ドメインも自動設定
      if (inference.domain?.domain) {
        setDomain(inference.domain.domain);
      }

      setMapping(auto);
      setResult(null);

      console.log('[Phase 3] Auto inference:', {
        mapping: auto,
        confidence: inference.confidence,
        domain: inference.domain?.domain,
        domainConfidence: inference.domain?.confidence
      });
    } finally {
      setBusy(false);
    }
  }

  async function onAnalyze() {
    if (!canAnalyze) return;
    setBusy(true);
    try {
      const res = await analyzeComprehensive({
        dataset_id: datasetId,
        mapping,
        domain,
      });
      setResult(res);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div style={{ padding: 24, color: "#e5edf7", background: "#0b1323", minHeight: "100vh" }}>
      <div style={{
        marginBottom: 32,
        paddingBottom: 24,
        borderBottom: "2px solid #1e293b",
      }}>
        <h1 style={{
          fontSize: 32,
          fontWeight: 700,
          margin: 0,
          marginBottom: 8,
          background: "linear-gradient(135deg, #3b82f6 0%, #8b5cf6 100%)",
          WebkitBackgroundClip: "text",
          WebkitTextFillColor: "transparent",
        }}>
          CQOx Complete
        </h1>
        <p style={{ margin: 0, color: "#94a3b8", fontSize: 14 }}>
          Causal Inference Dashboard with Quality Assurance
        </p>
      </div>

      <div style={{
        display: "flex",
        gap: 12,
        alignItems: "center",
        flexWrap: "wrap",
        marginBottom: 24,
        padding: 16,
        background: "#1e293b",
        borderRadius: 12,
        border: "1px solid #334155",
      }}>
        <input
          type="file"
          accept=".csv,.tsv,.jsonl,.ndjson,.xlsx,.parquet,.feather,.gz,.bz2"
          onChange={(e) => setFile(e.target.files?.[0] ?? null)}
          style={{
            padding: "8px 12px",
            borderRadius: 8,
            border: "1px solid #475569",
            background: "#0f172a",
            color: "#e2e8f0",
            cursor: "pointer",
          }}
          title="Supported: CSV, TSV, JSONL, XLSX, Parquet, Feather (with .gz/.bz2 compression)"
        />
        <select
          value={domain}
          onChange={(e) => setDomain(e.target.value)}
          style={{
            padding: "8px 12px",
            borderRadius: 8,
            border: "1px solid #475569",
            background: "#0f172a",
            color: "#e2e8f0",
            cursor: "pointer",
          }}
        >
          {DOMAINS.map((d) => (
            <option key={d} value={d}>{d}</option>
          ))}
        </select>
        <button
          onClick={onUpload}
          disabled={!file || busy}
          style={{
            padding: "8px 16px",
            borderRadius: 8,
            border: "none",
            background: !file || busy ? "#475569" : "#3b82f6",
            color: "#fff",
            fontWeight: 600,
            cursor: !file || busy ? "not-allowed" : "pointer",
            transition: "background 0.2s",
          }}
        >
          Upload
        </button>
        <button
          onClick={onAnalyze}
          disabled={!canAnalyze || busy}
          style={{
            padding: "8px 16px",
            borderRadius: 8,
            border: "none",
            background: !canAnalyze || busy ? "#475569" : "#10b981",
            color: "#fff",
            fontWeight: 600,
            cursor: !canAnalyze || busy ? "not-allowed" : "pointer",
            transition: "background 0.2s",
          }}
        >
          Analyze
        </button>
        {datasetId && (
          <span style={{
            padding: "6px 12px",
            background: "#0f172a",
            borderRadius: 6,
            fontSize: 13,
            color: "#94a3b8",
            border: "1px solid #334155",
          }}>
            dataset_id: {datasetId}
          </span>
        )}
      </div>

      {profile && (
        <div style={{ marginTop: 16 }}>
          <h3>Mapping</h3>
          <div style={{ display: "grid", gridTemplateColumns: "160px 1fr", gap: 8, maxWidth: 920 }}>
            {["y", "treatment", "unit_id", "time", "cost", "log_propensity"].map((role) => (
              <React.Fragment key={role}>
                <div>{role}</div>
                <select
                  value={mapping[role] ?? ""}
                  onChange={(e) => setMapping((m) => ({ ...m, [role]: e.target.value }))}
                >
                  <option value="">(none)</option>
                  {profile.meta.columns.map((c: string) => (
                    <option key={c} value={c}>{c}</option>
                  ))}
                </select>
              </React.Fragment>
            ))}
          </div>

        </div>
      )}

      {/* Estimator Validation Panel */}
      {profile?.estimator_validation && (
        <div style={{
          marginTop: 24,
          padding: 20,
          background: "linear-gradient(135deg, #1e293b 0%, #0f172a 100%)",
          borderRadius: 16,
          border: "1px solid #334155",
        }}>
          <div style={{
            display: "flex",
            alignItems: "center",
            gap: 12,
            marginBottom: 16,
            paddingBottom: 12,
            borderBottom: "2px solid #8b5cf6",
          }}>
            <h3 style={{
              margin: 0,
              fontSize: 20,
              fontWeight: 600,
              color: "#e2e8f0",
            }}>
              Estimator Validation
            </h3>
            <span style={{
              padding: "4px 12px",
              background: profile.estimator_validation.runnable?.length >= 5 ? "#10b981" : "#f59e0b",
              borderRadius: 16,
              fontSize: 13,
              fontWeight: 600,
              color: "#fff",
            }}>
              {profile.estimator_validation.count}
            </span>
          </div>

          {/* Runnable Estimators */}
          {profile.estimator_validation.runnable && profile.estimator_validation.runnable.length > 0 && (
            <div style={{ marginBottom: 16 }}>
              <div style={{
                fontSize: 14,
                fontWeight: 600,
                color: "#10b981",
                marginBottom: 8,
              }}>
                ✓ Ready to Run ({profile.estimator_validation.runnable.length})
              </div>
              <div style={{
                display: "flex",
                flexWrap: "wrap",
                gap: 8,
              }}>
                {profile.estimator_validation.runnable.map((est: string) => (
                  <span
                    key={est}
                    style={{
                      padding: "6px 12px",
                      background: "#10b98120",
                      border: "1px solid #10b981",
                      borderRadius: 8,
                      fontSize: 13,
                      color: "#10b981",
                      fontWeight: 500,
                    }}
                  >
                    {est.toUpperCase()}
                  </span>
                ))}
              </div>
            </div>
          )}

          {/* Non-runnable Estimators */}
          {profile.estimator_validation.details && Object.entries(profile.estimator_validation.details).some(
            ([_, val]: [string, any]) => !val.can_run
          ) && (
            <div>
              <div style={{
                fontSize: 14,
                fontWeight: 600,
                color: "#f59e0b",
                marginBottom: 8,
              }}>
                ⚠ Missing Requirements
              </div>
              <div style={{
                display: "grid",
                gap: 12,
              }}>
                {Object.entries(profile.estimator_validation.details)
                  .filter(([_, val]: [string, any]) => !val.can_run)
                  .map(([estimator, val]: [string, any]) => (
                    <div
                      key={estimator}
                      style={{
                        padding: 12,
                        background: "#0f172a",
                        border: "1px solid #475569",
                        borderRadius: 8,
                      }}
                    >
                      <div style={{
                        fontSize: 13,
                        fontWeight: 600,
                        color: "#e2e8f0",
                        marginBottom: 4,
                      }}>
                        {estimator.toUpperCase()}
                      </div>
                      <div style={{
                        fontSize: 12,
                        color: "#94a3b8",
                        marginBottom: 6,
                      }}>
                        {val.name}
                      </div>
                      {val.missing_required && val.missing_required.length > 0 && (
                        <div style={{
                          fontSize: 12,
                          color: "#f87171",
                        }}>
                          Missing: {val.missing_required.join(", ")}
                        </div>
                      )}
                      {val.fallback && (
                        <div style={{
                          fontSize: 11,
                          color: "#94a3b8",
                          marginTop: 4,
                          fontStyle: "italic",
                        }}>
                          Fallback: {val.fallback}
                        </div>
                      )}
                    </div>
                  ))}
              </div>
            </div>
          )}
        </div>
      )}

      {result && (
        <div style={{ marginTop: 32 }}>
          {/* 主要指標ダッシュボード */}
          <MetricsDashboard result={result} />

          {/* Results セクション */}
          <div style={{
            marginBottom: 32,
            padding: 20,
            background: "linear-gradient(135deg, #1e293b 0%, #0f172a 100%)",
            borderRadius: 16,
            border: "1px solid #334155",
          }}>
            <h3 style={{
              margin: 0,
              marginBottom: 16,
              fontSize: 20,
              fontWeight: 600,
              color: "#e2e8f0",
              borderBottom: "2px solid #3b82f6",
              paddingBottom: 8,
            }}>
              Estimation Results
            </h3>
            {Array.isArray(result.results) && result.results.length > 0 ? (
              <div style={{ position: 'relative' }}>
                <div style={{ height: 400, background: "#0f172a", padding: 16, borderRadius: 12, border: "1px solid #1e293b" }}>
                  <ResponsiveContainer width="100%" height="100%">
                    <BarChart data={result.results.map((e: any) => ({ name: e.name ?? e.kind, tau: e.tau_hat ?? e.ate ?? 0 }))}>
                      <XAxis dataKey="name" stroke="#94a3b8" style={{ fontSize: 12 }} />
                      <YAxis stroke="#94a3b8" style={{ fontSize: 12 }} />
                      <Tooltip
                        contentStyle={{
                          background: "#1e293b",
                          border: "1px solid #334155",
                          borderRadius: 8,
                          color: "#e2e8f0",
                        }}
                      />
                      {/* 閾値ライン：Effect Size Threshold |τ| > 0.1 */}
                      <ReferenceLine y={0.1} stroke="#10b981" strokeDasharray="5 5" strokeWidth={2}>
                        <Label value="Effect Threshold (τ=0.1)" position="insideTopRight" fill="#10b981" style={{ fontSize: 11, fontWeight: 600 }} />
                      </ReferenceLine>
                      <ReferenceLine y={-0.1} stroke="#10b981" strokeDasharray="5 5" strokeWidth={2} />
                      {/* 閾値ライン：ゼロライン */}
                      <ReferenceLine y={0} stroke="#64748b" strokeWidth={1.5} />
                      <Bar dataKey="tau" fill="#3b82f6" radius={[8, 8, 0, 0]} />
                    </BarChart>
                  </ResponsiveContainer>
                </div>
                {/* 推定器の通過閾値を表示 */}
                <div style={{
                  marginTop: 12,
                  padding: 12,
                  background: "#1e293b",
                  borderRadius: 8,
                  border: "1px solid #334155",
                  display: "grid",
                  gridTemplateColumns: "repeat(auto-fit, minmax(200px, 1fr))",
                  gap: 8,
                  fontSize: 13
                }}>
                  <div style={{ color: "#94a3b8" }}>
                    <span style={{ fontWeight: 600, color: "#10b981" }}>✓ Significance:</span> p &lt; 0.05
                  </div>
                  <div style={{ color: "#94a3b8" }}>
                    <span style={{ fontWeight: 600, color: "#3b82f6" }}>✓ Effect Size:</span> |τ| &gt; 0.1
                  </div>
                  <div style={{ color: "#94a3b8" }}>
                    <span style={{ fontWeight: 600, color: "#8b5cf6" }}>✓ Precision:</span> SE/|τ| &lt; 0.5
                  </div>
                  <div style={{ color: "#94a3b8" }}>
                    <span style={{ fontWeight: 600, color: "#f59e0b" }}>✓ CI Width:</span> (CI<sub>upper</sub> - CI<sub>lower</sub>)/|τ| &lt; 2.0
                  </div>
                </div>
              </div>
            ) : (
              <pre style={{
                background: "#0f172a",
                padding: 16,
                borderRadius: 8,
                overflow: "auto",
                maxHeight: 400,
                border: "1px solid #1e293b",
                fontSize: 13,
                color: "#94a3b8",
              }}>
                {JSON.stringify(result, null, 2)}
              </pre>
            )}
          </div>

          {/* Figures セクション */}
          {result.figures && (
            <div>
              <h3 style={{
                margin: 0,
                marginBottom: 20,
                fontSize: 20,
                fontWeight: 600,
                color: "#e2e8f0",
                borderBottom: "2px solid #8b5cf6",
                paddingBottom: 8,
              }}>
                Diagnostic Figures
              </h3>
              <FiguresPanel figures={result.figures} />
            </div>
          )}
        </div>
      )}
    </div>
  );
}

