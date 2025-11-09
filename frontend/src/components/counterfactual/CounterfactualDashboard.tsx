/**
 * Counterfactual Dashboard - Main Component
 *
 * Integrated dashboard for counterfactual scenario evaluation
 * Features:
 * - Scenario selection
 * - OPE/g-Computation evaluation
 * - S0 vs S1 comparison
 * - Quality Gates display
 * - Decision Card export
 */
import React, { useState, useEffect } from 'react';
import { runScenario, listScenarios, runBatchScenarios, exportDecisionCard } from '../../lib/client';
import DecisionBadge, { Decision } from './DecisionBadge';
import ComparisonPanel from './ComparisonPanel';
import QualityGatesPanel, { QualityGatesData } from './QualityGatesPanel';

interface Scenario {
  id: string;
  path: string;
  label: string;
}

interface ScenarioResult {
  status: string;
  scenario_id: string;
  mode: string;
  ate_s0: number;
  ate_s1: number;
  delta_ate: number;
  delta_profit: number;
  quality_gates?: QualityGatesData;
  decision?: Decision;
  warnings: string[];
  figures: Record<string, string>;
}

interface CounterfactualDashboardProps {
  datasetId: string;
}

export default function CounterfactualDashboard({ datasetId }: CounterfactualDashboardProps) {
  const [scenarios, setScenarios] = useState<Scenario[]>([]);
  const [selectedScenario, setSelectedScenario] = useState<string | null>(null);
  const [result, setResult] = useState<ScenarioResult | null>(null);
  const [loading, setLoading] = useState(false);
  const [mode, setMode] = useState<'ope' | 'gcomp'>('ope');
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    loadScenarios();
  }, [datasetId]);

  async function loadScenarios() {
    try {
      const data = await listScenarios(datasetId);
      setScenarios(data.scenarios);
      if (data.scenarios.length > 0) {
        setSelectedScenario(data.scenarios[0].path);
      }
    } catch (err) {
      console.error('Failed to load scenarios:', err);
      setError('Failed to load scenarios');
    }
  }

  async function handleRunScenario() {
    if (!selectedScenario) return;

    setLoading(true);
    setError(null);

    try {
      const res = await runScenario({
        dataset_id: datasetId,
        scenario: selectedScenario,
        mode
      });
      setResult(res as ScenarioResult);
    } catch (err: any) {
      console.error('Failed to run scenario:', err);
      setError(err?.response?.data?.detail || 'Scenario execution failed');
    } finally {
      setLoading(false);
    }
  }

  async function handleExportDecisionCard(format: 'json' | 'html' | 'pdf' = 'html') {
    if (!result) return;

    try {
      const cardData = await exportDecisionCard({
        dataset_id: datasetId,
        scenario_id: result.scenario_id,
        format
      });
      alert(`Decision Card generated: ${cardData.path}`);
    } catch (err: any) {
      console.error('Failed to export decision card:', err);
      alert(err?.response?.data?.detail || 'Failed to export decision card');
    }
  }

  return (
    <div style={{
      padding: '24px',
      color: '#e5edf7',
      background: '#0b1323',
      minHeight: '100vh'
    }}>
      {/* Header */}
      <div style={{
        marginBottom: '32px',
        paddingBottom: '24px',
        borderBottom: '2px solid #1e293b'
      }}>
        <h1 style={{
          fontSize: '32px',
          fontWeight: 700,
          margin: '0 0 8px 0',
          background: 'linear-gradient(135deg, #3b82f6 0%, #8b5cf6 100%)',
          WebkitBackgroundClip: 'text',
          WebkitTextFillColor: 'transparent'
        }}>
          Counterfactual Evaluation
        </h1>
        <p style={{
          margin: 0,
          color: '#94a3b8',
          fontSize: '14px'
        }}>
          Scenario Analysis with Quality Gates & Decision Support
        </p>
      </div>

      {/* Control Panel */}
      <div style={{
        display: 'flex',
        flexDirection: 'column',
        gap: '16px',
        marginBottom: '32px',
        padding: '20px',
        background: '#1e293b',
        borderRadius: '12px',
        border: '1px solid #334155'
      }}>
        {/* Scenario Selection */}
        <div>
          <label style={{
            display: 'block',
            marginBottom: '8px',
            fontSize: '14px',
            fontWeight: 600,
            color: '#94a3b8'
          }}>
            Select Scenario
          </label>
          <select
            value={selectedScenario || ''}
            onChange={(e) => setSelectedScenario(e.target.value)}
            disabled={loading}
            style={{
              width: '100%',
              padding: '10px 14px',
              borderRadius: '8px',
              border: '1px solid #475569',
              background: '#0f172a',
              color: '#e2e8f0',
              fontSize: '14px',
              cursor: loading ? 'not-allowed' : 'pointer'
            }}
          >
            {scenarios.map((scenario) => (
              <option key={scenario.path} value={scenario.path}>
                {scenario.label} ({scenario.id})
              </option>
            ))}
          </select>
        </div>

        {/* Mode Selection & Run Button */}
        <div style={{
          display: 'flex',
          gap: '12px',
          alignItems: 'center'
        }}>
          <div style={{ flex: '0 0 200px' }}>
            <label style={{
              display: 'block',
              marginBottom: '8px',
              fontSize: '14px',
              fontWeight: 600,
              color: '#94a3b8'
            }}>
              Evaluation Mode
            </label>
            <select
              value={mode}
              onChange={(e) => setMode(e.target.value as 'ope' | 'gcomp')}
              disabled={loading}
              style={{
                width: '100%',
                padding: '10px 14px',
                borderRadius: '8px',
                border: '1px solid #475569',
                background: '#0f172a',
                color: '#e2e8f0',
                fontSize: '14px',
                cursor: loading ? 'not-allowed' : 'pointer'
              }}
            >
              <option value="ope">OPE (Fast ~300ms)</option>
              <option value="gcomp">g-Computation (Precise ~2s)</option>
            </select>
          </div>

          <div style={{ flex: '0 0 auto', alignSelf: 'flex-end' }}>
            <button
              onClick={handleRunScenario}
              disabled={!selectedScenario || loading}
              style={{
                padding: '10px 32px',
                borderRadius: '8px',
                border: 'none',
                background: !selectedScenario || loading ? '#475569' : '#10b981',
                color: '#fff',
                fontWeight: 600,
                fontSize: '14px',
                cursor: !selectedScenario || loading ? 'not-allowed' : 'pointer',
                transition: 'background 0.2s'
              }}
            >
              {loading ? 'Evaluating...' : 'Run Scenario'}
            </button>
          </div>

          {result && (
            <div style={{ flex: '0 0 auto', alignSelf: 'flex-end' }}>
              <button
                onClick={() => handleExportDecisionCard('html')}
                style={{
                  padding: '10px 24px',
                  borderRadius: '8px',
                  border: '1px solid #3b82f6',
                  background: '#3b82f620',
                  color: '#3b82f6',
                  fontWeight: 600,
                  fontSize: '14px',
                  cursor: 'pointer',
                  transition: 'background 0.2s'
                }}
              >
                Export Decision Card
              </button>
            </div>
          )}
        </div>
      </div>

      {/* Error Display */}
      {error && (
        <div style={{
          padding: '16px',
          background: '#7f1d1d',
          border: '1px solid #ef4444',
          borderRadius: '8px',
          color: '#fca5a5',
          marginBottom: '24px',
          fontSize: '14px'
        }}>
          <strong>Error:</strong> {error}
        </div>
      )}

      {/* Results */}
      {result && (
        <div>
          {/* Decision Badge */}
          {result.decision && <DecisionBadge decision={result.decision} />}

          {/* Comparison Panel */}
          <ComparisonPanel
            s0={result.ate_s0}
            s1={result.ate_s1}
            delta={result.delta_profit}
            currency="JPY"
          />

          {/* Quality Gates */}
          {result.quality_gates && (
            <QualityGatesPanel gates={result.quality_gates} />
          )}

          {/* Warnings */}
          {result.warnings && result.warnings.length > 0 && (
            <div style={{
              padding: '16px',
              background: '#78350f',
              border: '1px solid #f59e0b',
              borderRadius: '8px',
              marginBottom: '24px'
            }}>
              <h4 style={{
                margin: '0 0 8px 0',
                fontSize: '14px',
                fontWeight: 600,
                color: '#fbbf24'
              }}>
                Warnings
              </h4>
              <ul style={{
                margin: 0,
                paddingLeft: '20px',
                color: '#fde68a',
                fontSize: '13px'
              }}>
                {result.warnings.map((warning, idx) => (
                  <li key={idx}>{warning}</li>
                ))}
              </ul>
            </div>
          )}

          {/* Metadata */}
          <div style={{
            padding: '16px',
            background: '#1e293b',
            border: '1px solid #334155',
            borderRadius: '8px',
            fontSize: '12px',
            color: '#94a3b8'
          }}>
            <strong>Mode:</strong> {result.mode.toUpperCase()} |{' '}
            <strong>Scenario ID:</strong> {result.scenario_id} |{' '}
            <strong>Status:</strong> {result.status}
          </div>
        </div>
      )}
    </div>
  );
}
