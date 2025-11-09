/**
 * Quality Gates Panel Component
 *
 * Displays quality gates results with pass/fail status and rationale
 */
import React from 'react';

export interface Gate {
  metric: string;
  status: 'PASS' | 'FAIL' | 'NA';
  value: number;
  threshold: number;
  category: string;
}

export interface QualityGatesData {
  overall: {
    decision: 'GO' | 'CANARY' | 'HOLD';
    pass_rate: number;
    pass_count: number;
    fail_count: number;
  };
  gates: Gate[];
  rationale: string[];
}

interface QualityGatesPanelProps {
  gates: QualityGatesData;
}

const CATEGORY_COLORS: Record<string, string> = {
  IDENTIFICATION: '#3b82f6',    // Blue
  PRECISION: '#8b5cf6',          // Purple
  ROBUSTNESS: '#f59e0b',         // Orange
  DECISION: '#10b981'            // Green
};

export default function QualityGatesPanel({ gates }: QualityGatesPanelProps) {
  const passRate = (gates.overall.pass_rate * 100).toFixed(0);

  return (
    <div style={{
      padding: '24px',
      background: '#1e293b',
      borderRadius: '16px',
      border: '1px solid #334155',
      marginBottom: '24px'
    }}>
      <div style={{
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        marginBottom: '20px',
        paddingBottom: '12px',
        borderBottom: '2px solid #8b5cf6'
      }}>
        <h3 style={{
          margin: 0,
          fontSize: '20px',
          fontWeight: 600,
          color: '#e2e8f0'
        }}>
          Quality Gates
        </h3>
        <div style={{
          padding: '6px 16px',
          background: gates.overall.pass_rate >= 0.7 ? '#10b981' : gates.overall.pass_rate >= 0.5 ? '#f59e0b' : '#ef4444',
          borderRadius: '20px',
          fontSize: '14px',
          fontWeight: 600,
          color: '#fff'
        }}>
          {passRate}% Pass Rate
        </div>
      </div>

      {/* Gates Grid */}
      <div style={{
        display: 'grid',
        gridTemplateColumns: 'repeat(auto-fill, minmax(220px, 1fr))',
        gap: '12px',
        marginBottom: '24px'
      }}>
        {gates.gates.map((gate, idx) => (
          <div
            key={idx}
            style={{
              padding: '14px',
              background: gate.status === 'PASS' ? '#10b98110' : gate.status === 'FAIL' ? '#ef444410' : '#64748b10',
              border: `2px solid ${gate.status === 'PASS' ? '#10b981' : gate.status === 'FAIL' ? '#ef4444' : '#64748b'}`,
              borderRadius: '10px'
            }}
          >
            <div style={{
              fontSize: '13px',
              fontWeight: 600,
              color: '#e2e8f0',
              marginBottom: '6px'
            }}>
              {gate.metric}
            </div>
            <div style={{
              fontSize: '11px',
              color: '#94a3b8',
              marginBottom: '6px'
            }}>
              {gate.value.toFixed(3)} / {gate.threshold.toFixed(3)}
            </div>
            <div style={{
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'space-between'
            }}>
              <span style={{
                fontSize: '10px',
                color: CATEGORY_COLORS[gate.category] || '#64748b',
                fontWeight: 600,
                textTransform: 'uppercase'
              }}>
                {gate.category}
              </span>
              <span style={{
                fontSize: '11px',
                fontWeight: 700,
                color: gate.status === 'PASS' ? '#10b981' : gate.status === 'FAIL' ? '#ef4444' : '#64748b'
              }}>
                {gate.status}
              </span>
            </div>
          </div>
        ))}
      </div>

      {/* Rationale */}
      <div style={{
        padding: '16px',
        background: '#0f172a',
        borderRadius: '10px',
        border: '1px solid #334155'
      }}>
        <h4 style={{
          margin: '0 0 12px 0',
          fontSize: '15px',
          fontWeight: 600,
          color: '#e2e8f0'
        }}>
          Decision Rationale
        </h4>
        <ul style={{
          margin: 0,
          paddingLeft: '20px',
          color: '#94a3b8',
          fontSize: '13px',
          lineHeight: '1.8'
        }}>
          {gates.rationale.map((reason, idx) => (
            <li key={idx} style={{ marginBottom: '6px' }}>
              {reason}
            </li>
          ))}
        </ul>
      </div>
    </div>
  );
}
