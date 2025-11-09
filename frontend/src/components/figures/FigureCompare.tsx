/**
 * FigureCompare - Stub component for objective comparison
 */
import React from 'react';

interface SmartFigureCompareProps {
  data?: any;
  baselineData?: any;
  scenarioData?: any;
}

export const SmartFigureCompare: React.FC<SmartFigureCompareProps> = ({ data, baselineData, scenarioData }) => {
  if (!data && !baselineData && !scenarioData) {
    return (
      <div style={{ padding: '20px', textAlign: 'center', color: '#94a3b8' }}>
        No comparison data available
      </div>
    );
  }

  return (
    <div style={{ padding: '20px', background: '#1e293b', borderRadius: '8px', border: '1px solid #334155' }}>
      <h3 style={{ color: '#e2e8f0', marginBottom: '16px' }}>Objective Comparison</h3>
      <pre style={{ color: '#94a3b8', fontSize: '12px', overflow: 'auto' }}>
        {JSON.stringify(data || { baseline: baselineData, scenario: scenarioData }, null, 2)}
      </pre>
    </div>
  );
};
