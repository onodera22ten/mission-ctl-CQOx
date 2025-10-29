// frontend/src/ui/FiguresPanel.tsx
import React, { useState } from "react";
import ParallelTrends from "../components/figures/ParallelTrends";
import EventStudy from "../components/figures/EventStudy";
import ATEDensity from "../components/figures/ATEDensity";
import PropensityOverlap from "../components/figures/PropensityOverlap";
import BalanceSMD from "../components/figures/BalanceSMD";
import RosenbaumSensitivity from "../components/figures/RosenbaumSensitivity";
import IVFirstStageF from "../components/figures/IVFirstStageF";
import IVStrengthStability from "../components/figures/IVStrengthStability";
import TransportWeights from "../components/figures/TransportWeights";
import TVCE from "../components/figures/TVCE";
import NetworkSpillover from "../components/figures/NetworkSpillover";
import HeterogeneityWaterfall from "../components/figures/HeterogeneityWaterfall";
import QualityGatesBoard from "../components/figures/QualityGatesBoard";
import CASRadar from "../components/figures/CASRadar";
import { FigureImage, Figure } from "../components/figures/Figure";

// Wrapper for FigureImage to match expected props
const GenericFigure: React.FC<{ url: string }> = ({ url }) => (
  <FigureImage src={url} alt="Generated figure" />
);

// Page 1: Main 14 figures (always generated)
const MAIN_FIGURES: Array<[string, string, React.FC<{ url: string }>]> = [
  ["parallel_trends", "Parallel Trends (DID)", ParallelTrends],
  ["event_study", "Event Study", EventStudy],
  ["ate_density", "ATE Density", ATEDensity],
  ["propensity_overlap", "Propensity Overlap", PropensityOverlap],
  ["balance_smd", "Balance SMD", BalanceSMD],
  ["rosenbaum_gamma", "Rosenbaum Sensitivity", RosenbaumSensitivity],
  ["iv_first_stage_f", "IV First-Stage F", IVFirstStageF],
  ["iv_strength_vs_2sls", "IV Strength vs 2SLS", IVStrengthStability],
  ["transport_weights", "Transport Weights", TransportWeights],
  ["tvce_line", "Time-Varying Effect", TVCE],
  ["network_spillover", "Network Spillover", NetworkSpillover],
  ["heterogeneity_waterfall", "Heterogeneity Waterfall", HeterogeneityWaterfall],
  ["quality_gates_board", "Quality Gates Board", QualityGatesBoard],
  ["cas_radar", "CAS Radar", CASRadar],
  ["evalue_sensitivity", "E-value Sensitivity (Fig 41)", GenericFigure],
  ["cate_forest", "CATE Forest (Fig 42)", GenericFigure],
];

// Page 2: Domain-specific figures (26 total)
const DOMAIN_FIGURE_KEYS = [
  // Medical (6)
  "medical_km_survival", "medical_dose_response", "medical_cluster_effect",
  "medical_adverse_events", "medical_iv_candidates", "medical_sensitivity",
  // Education (5)
  "education_event_study", "education_gain_distrib", "education_fairness",
  "education_attainment_sankey", "education_teacher_effect",
  // Retail (5)
  "retail_customer_funnel", "retail_seasonality_decomp", "retail_product_substitution",
  "retail_clv_cohort", "retail_geographic_heatmap",
  // Finance (4)
  "finance_portfolio_returns", "finance_risk_return", "finance_synthetic_did",
  "finance_volatility_regime",
  // Network (3)
  "network_graph", "network_exposure_dist", "network_spillover_heatmap",
  // Policy (3)
  "policy_rollout_map", "policy_staggered_adoption", "policy_welfare_simulation",
];

export default function FiguresPanel({ figures }: { figures: Record<string, string> }) {
  const [currentPage, setCurrentPage] = useState<"main" | "domain">("main");

  // Count available figures
  const mainCount = MAIN_FIGURES.filter(([key]) => figures[key]).length;
  const domainCount = DOMAIN_FIGURE_KEYS.filter(key => figures[key]).length;

  return (
    <div>
      {/* Page Tabs */}
      <div style={{
        display: "flex",
        gap: 12,
        marginBottom: 24,
        borderBottom: "2px solid #334155",
        paddingBottom: 12
      }}>
        <button
          onClick={() => setCurrentPage("main")}
          style={{
            padding: "12px 24px",
            borderRadius: "8px 8px 0 0",
            border: "none",
            background: currentPage === "main"
              ? "linear-gradient(135deg, #3b82f6 0%, #2563eb 100%)"
              : "#1e293b",
            color: "#fff",
            fontWeight: 600,
            fontSize: 15,
            cursor: "pointer",
            transition: "all 0.2s",
            borderBottom: currentPage === "main" ? "3px solid #3b82f6" : "none"
          }}
        >
          📊 Main Figures ({mainCount}/14)
        </button>
        <button
          onClick={() => setCurrentPage("domain")}
          style={{
            padding: "12px 24px",
            borderRadius: "8px 8px 0 0",
            border: "none",
            background: currentPage === "domain"
              ? "linear-gradient(135deg, #8b5cf6 0%, #7c3aed 100%)"
              : "#1e293b",
            color: "#fff",
            fontWeight: 600,
            fontSize: 15,
            cursor: "pointer",
            transition: "all 0.2s",
            borderBottom: currentPage === "domain" ? "3px solid #8b5cf6" : "none"
          }}
        >
          🎯 Domain-Specific ({domainCount}/26)
        </button>
      </div>

      {/* Page 1: Main 14 Figures */}
      {currentPage === "main" && (
        <div>
          <h3 style={{
            fontSize: 18,
            fontWeight: 600,
            marginBottom: 16,
            color: "#e2e8f0",
            display: "flex",
            alignItems: "center",
            gap: 8
          }}>
            <span style={{
              background: "linear-gradient(135deg, #3b82f6 0%, #8b5cf6 100%)",
              WebkitBackgroundClip: "text",
              WebkitTextFillColor: "transparent",
            }}>
              Primary Diagnostic Figures
            </span>
            <span style={{
              fontSize: 14,
              color: "#94a3b8",
              background: "#1e293b",
              padding: "4px 12px",
              borderRadius: 12,
              fontWeight: 500
            }}>
              {mainCount}/14 available
            </span>
          </h3>
          <div style={{
            display: "grid",
            gridTemplateColumns: "repeat(auto-fit, minmax(400px, 1fr))",
            gap: 20,
          }}>
            {MAIN_FIGURES.map(([key, title, Comp]) => {
              const url = figures[key];
              if (!url) return null;
              return (
                <div
                  key={key}
                  style={{
                    background: "linear-gradient(135deg, #1e293b 0%, #0f172a 100%)",
                    padding: 20,
                    borderRadius: 16,
                    border: "1px solid #334155",
                    boxShadow: "0 4px 6px rgba(0, 0, 0, 0.3)",
                    transition: "transform 0.2s, box-shadow 0.2s",
                    cursor: "pointer",
                  }}
                  onMouseEnter={(e) => {
                    e.currentTarget.style.transform = "translateY(-2px)";
                    e.currentTarget.style.boxShadow = "0 8px 12px rgba(0, 0, 0, 0.4)";
                  }}
                  onMouseLeave={(e) => {
                    e.currentTarget.style.transform = "translateY(0)";
                    e.currentTarget.style.boxShadow = "0 4px 6px rgba(0, 0, 0, 0.3)";
                  }}
                >
                  <div style={{
                    fontWeight: 600,
                    marginBottom: 12,
                    fontSize: 16,
                    color: "#e2e8f0",
                    borderBottom: "2px solid #3b82f6",
                    paddingBottom: 8,
                  }}>
                    {title}
                  </div>
                  <Comp url={url} />
                </div>
              );
            })}
          </div>
        </div>
      )}

      {/* Page 2: Domain-Specific 26 Figures */}
      {currentPage === "domain" && (
        <div>
          <h3 style={{
            fontSize: 18,
            fontWeight: 600,
            marginBottom: 16,
            color: "#e2e8f0",
            display: "flex",
            alignItems: "center",
            gap: 8
          }}>
            <span style={{
              background: "linear-gradient(135deg, #8b5cf6 0%, #ec4899 100%)",
              WebkitBackgroundClip: "text",
              WebkitTextFillColor: "transparent",
            }}>
              Domain-Specific Analysis
            </span>
            <span style={{
              fontSize: 14,
              color: "#94a3b8",
              background: "#1e293b",
              padding: "4px 12px",
              borderRadius: 12,
              fontWeight: 500
            }}>
              {domainCount}/26 available
            </span>
          </h3>

          {/* Group by domain */}
          {["medical", "education", "retail", "finance", "network", "policy"].map(domain => {
            const domainFigs = DOMAIN_FIGURE_KEYS.filter(k => k.startsWith(domain) && figures[k]);
            if (domainFigs.length === 0) return null;

            return (
              <div key={domain} style={{ marginBottom: 32 }}>
                <h4 style={{
                  fontSize: 16,
                  fontWeight: 600,
                  marginBottom: 16,
                  color: "#cbd5e1",
                  textTransform: "capitalize",
                  borderLeft: "4px solid #8b5cf6",
                  paddingLeft: 12
                }}>
                  {domain} Domain ({domainFigs.length})
                </h4>
                <div style={{
                  display: "grid",
                  gridTemplateColumns: "repeat(auto-fit, minmax(380px, 1fr))",
                  gap: 16,
                }}>
                  {domainFigs.map(key => (
                    <div
                      key={key}
                      style={{
                        background: "linear-gradient(135deg, #1e293b 0%, #0f172a 100%)",
                        padding: 16,
                        borderRadius: 12,
                        border: "1px solid #334155",
                        boxShadow: "0 2px 4px rgba(0, 0, 0, 0.2)",
                      }}
                    >
                      <div style={{
                        fontWeight: 600,
                        marginBottom: 10,
                        fontSize: 14,
                        color: "#e2e8f0",
                        borderBottom: "1px solid #475569",
                        paddingBottom: 6,
                      }}>
                        {key.replace(domain + "_", "").replace(/_/g, " ").replace(/\b\w/g, l => l.toUpperCase())}
                      </div>
                      <Figure url={figures[key]} />
                    </div>
                  ))}
                </div>
              </div>
            );
          })}

          {domainCount === 0 && (
            <div style={{
              padding: 40,
              textAlign: "center",
              color: "#94a3b8",
              background: "#1e293b",
              borderRadius: 12,
              border: "1px solid #334155"
            }}>
              <div style={{ fontSize: 48, marginBottom: 16 }}>📊</div>
              <div style={{ fontSize: 16, fontWeight: 600, marginBottom: 8 }}>
                No domain-specific figures available
              </div>
              <div style={{ fontSize: 14 }}>
                Domain-specific visualizations will appear here based on your data's domain
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
