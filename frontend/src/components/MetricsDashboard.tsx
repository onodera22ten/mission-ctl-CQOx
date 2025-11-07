// frontend/src/components/MetricsDashboard.tsx
import React from "react";
import ObjectiveComparison from "./ObjectiveComparison";

interface MetricsProps {
  result: any;
}

export default function MetricsDashboard({ result }: MetricsProps) {
  if (!result) return null;

  console.log("MetricsDashboard result:", result);

  // CAS スコアの取得
  let casScore = 0;
  if (result.cas?.overall !== undefined) {
    casScore = result.cas.overall;
  } else if (result.cas_score !== undefined) {
    casScore = typeof result.cas_score === 'number' ? result.cas_score : result.cas_score.overall ?? 0;
  } else if (result.CAS !== undefined) {
    casScore = typeof result.CAS === 'number' ? result.CAS : result.CAS.overall ?? 0;
  }

  // 推定器の数
  const estimatorCount = Array.isArray(result.results) ? result.results.length : 0;

  // Quality Gate の合格率
  const gates = result.gates || result.quality_gates || {};
  const gateEntries = Object.entries(gates);
  const passedGates = gateEntries.filter(([_, val]: [string, any]) => val?.pass === true || val === true).length;
  const totalGates = gateEntries.length;
  const gatePassRate = totalGates > 0 ? (passedGates / totalGates) * 100 : 0;

  // 平均 ATE
  const avgATE = Array.isArray(result.results) && result.results.length > 0
    ? result.results.reduce((sum: number, r: any) => sum + (r.tau_hat ?? r.ate ?? 0), 0) / result.results.length
    : 0;

  const metrics = [
    {
      label: "CAS Score",
      value: casScore > 0 ? casScore.toFixed(2) : "N/A",
      unit: casScore > 0 ? "/5.0" : "",
      color: "#3b82f6",
      detail: `${passedGates}/${totalGates} gates passed`
    },
    {
      label: "Estimators",
      value: estimatorCount,
      unit: "models",
      color: "#8b5cf6",
      detail: "causal estimators"
    },
    {
      label: "Quality Gate",
      value: totalGates > 0 ? gatePassRate.toFixed(0) : "N/A",
      unit: totalGates > 0 ? "%" : "",
      color: gatePassRate >= 70 ? "#10b981" : gatePassRate >= 50 ? "#f59e0b" : "#ef4444",
      detail: `${passedGates}/${totalGates} passed`
    },
    {
      label: "Avg ATE",
      value: avgATE.toFixed(2),
      unit: "",
      color: "#f59e0b",
      detail: "treatment effect"
    },
  ];

  return (
    <>
      <div style={{
        display: "grid",
        gridTemplateColumns: "repeat(auto-fit, minmax(200px, 1fr))",
        gap: 16,
        marginBottom: 24,
      }}>
        {metrics.map((metric, idx) => (
          <div
            key={idx}
            style={{
              background: "linear-gradient(135deg, #1e293b 0%, #0f172a 100%)",
              border: `1px solid ${metric.color}40`,
              borderRadius: 12,
              padding: 20,
              position: "relative",
              overflow: "hidden",
            }}
          >
            <div
              style={{
                position: "absolute",
                top: 0,
                left: 0,
                width: "100%",
                height: "4px",
                background: metric.color,
              }}
            />
            <div style={{
              fontSize: 13,
              color: "#94a3b8",
              fontWeight: 500,
              marginBottom: 8,
              textTransform: "uppercase",
              letterSpacing: "0.5px",
            }}>
              {metric.label}
            </div>
            <div style={{ display: "flex", alignItems: "baseline", gap: 4 }}>
              <div style={{
                fontSize: 32,
                fontWeight: 700,
                color: metric.color,
                lineHeight: 1,
              }}>
                {metric.value}
              </div>
              <div style={{
                fontSize: 14,
                color: "#64748b",
                fontWeight: 500,
              }}>
                {metric.unit}
              </div>
            </div>
            <div style={{
              fontSize: 11,
              color: "#64748b",
              marginTop: 6,
              opacity: 0.8,
            }}>
              {metric.detail}
            </div>
          </div>
        ))}
      </div>
      <ObjectiveComparison />
    </>
  );
}
