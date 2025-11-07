// frontend/src/ui/TasksPanel.tsx
import React, { useState } from "react";
import { Figure } from "../components/figures/Figure";

// Task definitions matching catalog.yaml
const TASKS = [
  {
    key: "diagnostics",
    name: "Diagnostics",
    color: "#3b82f6",
    panels: [
      "quality_gates_board",
      "cas_radar",
      "love_plot",
      "covariate_correlation",
      "propensity_overlap",
      "prediction_vs_residual",
      "missing_map",
      "outlier_impact",
      "missing_mechanism",
    ],
  },
  {
    key: "causal_estimation",
    name: "Estimation",
    color: "#10b981",
    panels: ["ate_bar", "ate_density", "prior_vs_posterior", "stratified_ate"],
  },
  {
    key: "heterogeneity",
    name: "Heterogeneity",
    color: "#8b5cf6",
    panels: [
      "cate_forest",
      "evalue_sensitivity",
      "evalue_curve",
      "heterogeneity_waterfall",
      "cate_hist",
      "cate_quantile",
      "dose_response",
      "importance_shap",
    ],
  },
  {
    key: "policy",
    name: "Policy",
    color: "#f59e0b",
    panels: [
      "policy_did",
      "policy_rd",
      "policy_geo",
      "cost_effect_curve",
      "profit_curve",
    ],
  },
  {
    key: "time_varying",
    name: "Time-Varying",
    color: "#06b6d4",
    panels: ["tvce_timeseries", "event_study", "sequential_event_study"],
  },
  {
    key: "iv",
    name: "IV (Instrumental Variables)",
    color: "#ec4899",
    panels: ["iv_first_stage_f", "iv_strength_vs_2sls", "weak_iv_diagnostics"],
  },
  {
    key: "robustness",
    name: "Robustness",
    color: "#ef4444",
    panels: ["rosenbaum_gamma", "evalue_curve", "confounding_sensitivity_heatmap"],
  },
  {
    key: "network",
    name: "Network",
    color: "#14b8a6",
    panels: ["network_spillover"],
  },
  {
    key: "transportability",
    name: "Transport",
    color: "#a855f7",
    panels: ["transport_weights", "transport_validity"],
  },
];

// Panel display names
const PANEL_NAMES: Record<string, string> = {
  quality_gates_board: "Quality Gates Board",
  cas_radar: "CAS Radar (5-Axis)",
  love_plot: "Love Plot (SMD)",
  covariate_correlation: "Covariate Correlation",
  propensity_overlap: "Propensity Overlap",
  prediction_vs_residual: "Prediction vs Residual",
  missing_map: "Missing Data Map",
  outlier_impact: "Outlier Impact",
  missing_mechanism: "Missing Mechanism Test",

  ate_bar: "ATE Bar with CI",
  ate_density: "ATE Density (by group)",
  prior_vs_posterior: "Prior vs Posterior (Bayesian)",
  stratified_ate: "Stratified ATE",

  cate_forest: "CATE Forest (Heterogeneity)",
  evalue_sensitivity: "E-value Sensitivity Analysis",
  heterogeneity_waterfall: "Heterogeneity Waterfall (Top 10)",
  cate_hist: "CATE Histogram/Density",
  cate_quantile: "CATE Quantile Bar",
  dose_response: "Dose-Response Curve",
  importance_shap: "Importance (SHAP-like)",

  policy_did: "Difference-in-Differences (Policy)",
  policy_rd: "Regression Discontinuity (Policy)",
  policy_geo: "Geographic Policy Impact",
  cost_effect_curve: "Cost-Effect Curve",
  profit_curve: "Profit Curve",

  tvce_timeseries: "Time-Varying Effect (TVCE)",
  event_study: "Event Study Coefficients",
  sequential_event_study: "Sequential Event Study",

  iv_first_stage_f: "IV First Stage F-statistic",
  iv_strength_vs_2sls: "IV Strength vs 2SLS Comparison",
  weak_iv_diagnostics: "Weak IV Diagnostics (F-test)",

  rosenbaum_gamma: "Rosenbaum Γ Curve",
  evalue_curve: "E-value Sensitivity",
  confounding_sensitivity_heatmap: "Confounding Sensitivity Heatmap",

  network_spillover: "Network Spillover Effects",

  transport_weights: "Transport Weights Distribution",
  transport_validity: "Transport Validity Diagnostics",
};

interface TasksPanelProps {
  figures: Record<string, string>;
  availablePanels?: string[];
}

export default function TasksPanel({ figures, availablePanels }: TasksPanelProps) {
  const [currentTask, setCurrentTask] = useState<string>("diagnostics");

  // Count available panels per task
  const taskAvailability = TASKS.map((task) => {
    const taskPanels = task.panels.filter((p) => figures[p]);
    return {
      ...task,
      availableCount: taskPanels.length,
      totalCount: task.panels.length,
    };
  });

  // Filter to current task's panels
  const currentTaskDef = TASKS.find((t) => t.key === currentTask);
  const currentPanels = currentTaskDef?.panels.filter((p) => figures[p]) || [];

  return (
    <div>
      {/* Task Tabs */}
      <div
        style={{
          display: "flex",
          gap: 8,
          marginBottom: 24,
          borderBottom: "2px solid #334155",
          paddingBottom: 12,
          overflowX: "auto",
          flexWrap: "wrap",
        }}
      >
        {taskAvailability.map((task) => (
          <button
            key={task.key}
            onClick={() => setCurrentTask(task.key)}
            disabled={task.availableCount === 0}
            style={{
              padding: "10px 20px",
              borderRadius: "8px 8px 0 0",
              border: "none",
              background:
                currentTask === task.key
                  ? `linear-gradient(135deg, ${task.color} 0%, ${task.color}dd 100%)`
                  : task.availableCount > 0
                  ? "#1e293b"
                  : "#0f172a",
              color: task.availableCount > 0 ? "#fff" : "#64748b",
              fontWeight: 600,
              fontSize: 13,
              cursor: task.availableCount > 0 ? "pointer" : "not-allowed",
              transition: "all 0.2s",
              borderBottom:
                currentTask === task.key ? `3px solid ${task.color}` : "none",
              opacity: task.availableCount > 0 ? 1 : 0.5,
              display: "flex",
              alignItems: "center",
              gap: 6,
            }}
          >
            <span style={{ fontSize: 16 }}>{task.icon}</span>
            <span>{task.name}</span>
            <span
              style={{
                fontSize: 11,
                background: task.availableCount > 0 ? "#334155" : "#1e293b",
                padding: "2px 8px",
                borderRadius: 8,
                fontWeight: 500,
              }}
            >
              {task.availableCount}/{task.totalCount}
            </span>
          </button>
        ))}
      </div>

      {/* Current Task Panels */}
      {currentPanels.length > 0 ? (
        <div>
          <h3
            style={{
              fontSize: 18,
              fontWeight: 600,
              marginBottom: 16,
              color: "#e2e8f0",
              display: "flex",
              alignItems: "center",
              gap: 12,
            }}
          >
            <span style={{ fontSize: 24 }}>{currentTaskDef?.icon}</span>
            <span
              style={{
                background: `linear-gradient(135deg, ${currentTaskDef?.color} 0%, ${currentTaskDef?.color}dd 100%)`,
                WebkitBackgroundClip: "text",
                WebkitTextFillColor: "transparent",
              }}
            >
              {currentTaskDef?.name}
            </span>
            <span
              style={{
                fontSize: 14,
                color: "#94a3b8",
                background: "#1e293b",
                padding: "4px 12px",
                borderRadius: 12,
                fontWeight: 500,
              }}
            >
              {currentPanels.length} panels available
            </span>
          </h3>

          <div
            style={{
              display: "grid",
              gridTemplateColumns: "repeat(auto-fit, minmax(400px, 1fr))",
              gap: 20,
            }}
          >
            {currentPanels.map((panelKey) => (
              <div
                key={panelKey}
                style={{
                  background:
                    "linear-gradient(135deg, #1e293b 0%, #0f172a 100%)",
                  padding: 20,
                  borderRadius: 16,
                  border: "1px solid #334155",
                  boxShadow: "0 4px 6px rgba(0, 0, 0, 0.3)",
                  transition: "transform 0.2s, box-shadow 0.2s",
                }}
                onMouseEnter={(e) => {
                  e.currentTarget.style.transform = "translateY(-2px)";
                  e.currentTarget.style.boxShadow =
                    "0 8px 12px rgba(0, 0, 0, 0.4)";
                }}
                onMouseLeave={(e) => {
                  e.currentTarget.style.transform = "translateY(0)";
                  e.currentTarget.style.boxShadow =
                    "0 4px 6px rgba(0, 0, 0, 0.3)";
                }}
              >
                <div
                  style={{
                    fontWeight: 600,
                    marginBottom: 12,
                    fontSize: 15,
                    color: "#e2e8f0",
                    borderBottom: `2px solid ${currentTaskDef?.color}`,
                    paddingBottom: 8,
                  }}
                >
                  {PANEL_NAMES[panelKey] || panelKey}
                </div>
                <Figure src={figures[panelKey]} />
              </div>
            ))}
          </div>
        </div>
      ) : (
        <div
          style={{
            padding: 60,
            textAlign: "center",
            color: "#94a3b8",
            background: "#1e293b",
            borderRadius: 16,
            border: "1px solid #334155",
          }}
        >
          <div style={{ fontSize: 56, marginBottom: 20 }}>
            {currentTaskDef?.icon}
          </div>
          <div style={{ fontSize: 18, fontWeight: 600, marginBottom: 12 }}>
            No panels available for {currentTaskDef?.name}
          </div>
          <div style={{ fontSize: 14, opacity: 0.8 }}>
            This task requires additional data roles or conditions that are not
            currently met.
          </div>
        </div>
      )}
    </div>
  );
}
