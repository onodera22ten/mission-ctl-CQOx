/**
 * Comparison Panel Component
 *
 * S0 vs S1 side-by-side comparison with ΔProfit display
 */
import React from 'react';
import { formatCurrency, formatPercentage } from '../../lib/money_view';

interface ComparisonPanelProps {
  s0: number;
  s1: number;
  delta: number;
  ci?: [number, number];
  s0_ci?: [number, number];
  s1_ci?: [number, number];
  currency?: 'JPY' | 'USD' | 'EUR';
}

export default function ComparisonPanel({
  s0,
  s1,
  delta,
  ci,
  s0_ci,
  s1_ci,
  currency = 'JPY'
}: ComparisonPanelProps) {
  const deltaPercent = (delta / Math.abs(s0)) * 100;

  return (
    <div style={{
      padding: '24px',
      background: '#1e293b',
      borderRadius: '16px',
      border: '1px solid #334155',
      marginBottom: '24px'
    }}>
      <h3 style={{
        margin: '0 0 20px 0',
        fontSize: '20px',
        fontWeight: 600,
        color: '#e2e8f0',
        borderBottom: '2px solid #3b82f6',
        paddingBottom: '12px'
      }}>
        S0 vs S1 Comparison
      </h3>

      <div style={{
        display: 'grid',
        gridTemplateColumns: 'repeat(auto-fit, minmax(250px, 1fr))',
        gap: '20px'
      }}>
        {/* S0: Baseline */}
        <div style={{
          padding: '20px',
          background: '#0f172a',
          borderRadius: '12px',
          border: '2px solid #475569'
        }}>
          <div style={{
            fontSize: '12px',
            color: '#94a3b8',
            textTransform: 'uppercase',
            letterSpacing: '0.05em',
            marginBottom: '8px',
            fontWeight: 600
          }}>
            S0: Baseline (Observed)
          </div>
          <div style={{
            fontSize: '32px',
            fontWeight: 'bold',
            color: '#e2e8f0',
            marginBottom: '8px'
          }}>
            {formatCurrency(s0, currency)}
          </div>
          {s0_ci && (
            <div style={{
              fontSize: '12px',
              color: '#64748b'
            }}>
              95% CI: [{formatCurrency(s0_ci[0], currency)}, {formatCurrency(s0_ci[1], currency)}]
            </div>
          )}
        </div>

        {/* S1: Scenario */}
        <div style={{
          padding: '20px',
          background: '#0f172a',
          borderRadius: '12px',
          border: '2px solid #475569'
        }}>
          <div style={{
            fontSize: '12px',
            color: '#94a3b8',
            textTransform: 'uppercase',
            letterSpacing: '0.05em',
            marginBottom: '8px',
            fontWeight: 600
          }}>
            S1: Scenario (Counterfactual)
          </div>
          <div style={{
            fontSize: '32px',
            fontWeight: 'bold',
            color: '#e2e8f0',
            marginBottom: '8px'
          }}>
            {formatCurrency(s1, currency)}
          </div>
          {s1_ci && (
            <div style={{
              fontSize: '12px',
              color: '#64748b'
            }}>
              95% CI: [{formatCurrency(s1_ci[0], currency)}, {formatCurrency(s1_ci[1], currency)}]
            </div>
          )}
        </div>

        {/* ΔProfit */}
        <div style={{
          padding: '20px',
          background: delta > 0 ? '#10b98110' : '#ef444410',
          borderRadius: '12px',
          border: `2px solid ${delta > 0 ? '#10b981' : '#ef4444'}`
        }}>
          <div style={{
            fontSize: '12px',
            color: '#94a3b8',
            textTransform: 'uppercase',
            letterSpacing: '0.05em',
            marginBottom: '8px',
            fontWeight: 600
          }}>
            ΔProfit (S1 - S0)
          </div>
          <div style={{
            fontSize: '32px',
            fontWeight: 'bold',
            color: delta > 0 ? '#10b981' : '#ef4444',
            marginBottom: '4px'
          }}>
            {formatCurrency(delta, currency)}
          </div>
          <div style={{
            fontSize: '16px',
            fontWeight: 600,
            color: delta > 0 ? '#10b981' : '#ef4444',
            marginBottom: '8px'
          }}>
            ({formatPercentage(deltaPercent)})
          </div>
          {ci && (
            <div style={{
              fontSize: '12px',
              color: '#64748b'
            }}>
              95% CI: [{formatCurrency(ci[0], currency)}, {formatCurrency(ci[1], currency)}]
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
