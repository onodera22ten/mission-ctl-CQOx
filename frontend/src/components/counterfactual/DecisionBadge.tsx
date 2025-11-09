/**
 * Decision Badge Component
 *
 * Displays GO/CANARY/HOLD decision with color-coded styling
 */
import React from 'react';

export type Decision = 'GO' | 'CANARY' | 'HOLD';

interface DecisionBadgeProps {
  decision: Decision;
  className?: string;
}

const DECISION_COLORS: Record<Decision, { bg: string; border: string; text: string }> = {
  GO: {
    bg: '#10B981',      // Green
    border: '#059669',
    text: '#fff'
  },
  CANARY: {
    bg: '#F59E0B',      // Orange
    border: '#D97706',
    text: '#fff'
  },
  HOLD: {
    bg: '#EF4444',      // Red
    border: '#DC2626',
    text: '#fff'
  }
};

const DECISION_LABELS: Record<Decision, string> = {
  GO: '✓ GO - Deploy Immediately',
  CANARY: '⚠ CANARY - Gradual Rollout',
  HOLD: '✗ HOLD - Do Not Deploy'
};

export default function DecisionBadge({ decision, className = '' }: DecisionBadgeProps) {
  const colors = DECISION_COLORS[decision];

  return (
    <div
      className={`decision-badge ${className}`}
      style={{
        backgroundColor: colors.bg,
        borderColor: colors.border,
        color: colors.text,
        padding: '20px 40px',
        borderRadius: '16px',
        fontSize: '28px',
        fontWeight: 'bold',
        textAlign: 'center',
        marginBottom: '32px',
        border: `3px solid ${colors.border}`,
        boxShadow: `0 8px 24px ${colors.bg}40`,
        letterSpacing: '0.5px'
      }}
    >
      {DECISION_LABELS[decision]}
    </div>
  );
}
