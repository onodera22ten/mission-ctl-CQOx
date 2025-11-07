
import React, { useState, useEffect, useCallback } from 'react';
import { debounce } from 'lodash';
import { runScenario } from '../lib/client';

export type ScenarioParams = {
  coverage: number;
  budget_cap: number;
  // 他のパラメータも追加可能
};

interface ScenarioPlaygroundProps {
  initialParams: ScenarioParams;
  onScenarioComplete: (data: any) => void;
  onParamsChange: (params: ScenarioParams) => void;
  datasetId: string;
  scenarioId: string;
  setLoading: (loading: boolean) => void;
}

const ScenarioPlayground: React.FC<ScenarioPlaygroundProps> = ({ initialParams, onScenarioComplete, onParamsChange, datasetId, scenarioId, setLoading }) => {
  const [params, setParams] = useState<ScenarioParams>(initialParams);

  const debouncedRunScenario = useCallback(
    debounce(async (newParams: ScenarioParams) => {
      setLoading(true);
      try {
        const result = await runScenario({
          dataset_id: datasetId,
          scenario: scenarioId,
          mode: 'ope',
          // スライダーの値をシナリオのパラメータとして渡す
          intervention: { coverage: newParams.coverage / 100 }, // 0-1の範囲に変換
          constraints: { budget: { cap: newParams.budget_cap } },
        });
        onScenarioComplete(result);
      } catch (error) {
        console.error('Failed to run scenario:', error);
      } finally {
        setLoading(false);
      }
    }, 300), // 300ms のデバウンス
    [datasetId, scenarioId, onScenarioComplete, setLoading]
  );

  useEffect(() => {
    onParamsChange(params);
    debouncedRunScenario(params);
  }, [params, onParamsChange, debouncedRunScenario]);

  const handleSliderChange = (paramName: keyof ScenarioParams, value: number) => {
    setParams(prevParams => ({ ...prevParams, [paramName]: value }));
  };

  return (
    <div className="p-4 border rounded-lg bg-gray-50 mb-6">
      <h3 className="text-lg font-semibold mb-4">シナリオ・プレイグラウンド (Scenario Playground)</h3>
      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        <div>
          <label htmlFor="coverage" className="block text-sm font-medium text-gray-700">
            Coverage: {params.coverage}%
          </label>
          <input
            type="range"
            id="coverage"
            min="0"
            max="100"
            value={params.coverage}
            onChange={(e) => handleSliderChange('coverage', parseInt(e.target.value, 10))}
            className="w-full h-2 bg-gray-200 rounded-lg appearance-none cursor-pointer"
          />
        </div>
        <div>
          <label htmlFor="budget_cap" className="block text-sm font-medium text-gray-700">
            Budget Cap: {params.budget_cap.toLocaleString()}
          </label>
          <input
            type="range"
            id="budget_cap"
            min="0"
            max="100000000"
            step="100000"
            value={params.budget_cap}
            onChange={(e) => handleSliderChange('budget_cap', parseInt(e.target.value, 10))}
            className="w-full h-2 bg-gray-200 rounded-lg appearance-none cursor-pointer"
          />
        </div>
      </div>
    </div>
  );
};

export default ScenarioPlayground;

