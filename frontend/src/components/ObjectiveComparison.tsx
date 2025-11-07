
import React, { useState, useCallback } from "react";
import { SmartFigureCompare } from "./figures/FigureCompare";
import ScenarioPlayground, { ScenarioParams } from "./ScenarioPlayground";
import { runScenario } from "../lib/client";

const ObjectiveComparison = () => {
  const [comparisonData, setComparisonData] = useState<any>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [scenarioParams, setScenarioParams] = useState<ScenarioParams>({
    coverage: 30,
    budget_cap: 12000000,
  });

  const handleScenarioComplete = useCallback((data: any) => {
    if (data.status === "completed") {
      setComparisonData(data);
      setError(null);
    } else {
      setError("Scenario execution did not complete successfully");
    }
  }, []);

  const handleParamsChange = (newParams: ScenarioParams) => {
    setScenarioParams(newParams);
  };
  
  // 初期データを読み込むためのuseEffect
  useEffect(() => {
    const fetchInitialData = async () => {
      setLoading(true);
      try {
        const data = await runScenario({
          dataset_id: "realistic_retail_5k",
          scenario: "config/scenarios/S1_geo_budget.yaml",
          mode: "ope",
        });
        if (data.status === "completed") {
          setComparisonData(data);
          setError(null);
        } else {
          setError("Scenario execution did not complete successfully");
        }
      } catch (err: any) {
        console.error("Failed to fetch comparison data:", err);
        setError(err.message || "Failed to load counterfactual comparison");
      } finally {
        setLoading(false);
      }
    };
    fetchInitialData();
  }, []);


  if (error) {
    return (
      <div className="p-4 bg-red-50 border border-red-200 rounded">
        <h3 className="text-red-700 font-bold">エラー</h3>
        <p className="text-red-600">{error}</p>
      </div>
    );
  }

  return (
    <div className="p-6 bg-white rounded-lg shadow">
      <h2 className="text-2xl font-bold mb-4">反実仮想比較 (Counterfactual Comparison)</h2>

      <ScenarioPlayground
        initialParams={scenarioParams}
        onScenarioComplete={handleScenarioComplete}
        onParamsChange={handleParamsChange}
        datasetId="realistic_retail_5k"
        scenarioId="config/scenarios/S1_geo_budget.yaml"
        setLoading={setLoading}
      />
      
      {loading && (
        <div className="p-4 text-center">
          <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-500 mx-auto mb-2"></div>
          <p className="text-gray-600">反実仮想シナリオを実行中...</p>
        </div>
      )}

      {!comparisonData && !loading && (
        <div className="p-4 text-gray-600">データがありません</div>
      )}

      {comparisonData && (
        <>
          {/* シナリオ情報 */}
          <div className="mb-6 p-4 bg-blue-50 rounded">
            <div className="grid grid-cols-2 gap-4">
              <div>
                <span className="font-semibold">シナリオID:</span> {comparisonData.scenario_id}
              </div>
              <div>
                <span className="font-semibold">モード:</span> {comparisonData.mode.toUpperCase()}
              </div>
            </div>
          </div>

          {/* ATE比較 */}
          <div className="grid grid-cols-2 gap-6 mb-6">
            <div className="p-4 bg-gray-50 rounded">
              <h3 className="text-sm font-semibold text-gray-600 mb-2">観測ATE (S0)</h3>
              <p className="text-3xl font-bold text-gray-800">{comparisonData.ate_s0.toFixed(2)}</p>
            </div>
            <div className="p-4 bg-green-50 rounded">
              <h3 className="text-sm font-semibold text-gray-600 mb-2">反実仮想ATE (S1)</h3>
              <p className="text-3xl font-bold text-green-700">{comparisonData.ate_s1.toFixed(2)}</p>
            </div>
          </div>

          {/* 差分表示 */}
          <div className="grid grid-cols-2 gap-6 mb-6">
            <div className="p-4 bg-purple-50 rounded">
              <h3 className="text-sm font-semibold text-gray-600 mb-2">ΔATE</h3>
              <p className="text-2xl font-bold text-purple-700">
                +{comparisonData.delta_ate.toFixed(2)}
              </p>
            </div>
            <div className="p-4 bg-orange-50 rounded">
              <h3 className="text-sm font-semibold text-gray-600 mb-2">Δ利益</h3>
              <p className="text-2xl font-bold text-orange-700">
                ¥{comparisonData.delta_profit.toLocaleString()}
              </p>
            </div>
          </div>

          {/* 警告表示 */}
          {comparisonData.warnings && comparisonData.warnings.length > 0 && (
            <div className="mb-6 p-4 bg-yellow-50 border border-yellow-200 rounded">
              <h3 className="text-yellow-800 font-semibold mb-2">注意事項</h3>
              <ul className="list-disc list-inside text-yellow-700">
                {comparisonData.warnings.map((warning: string, idx: number) => (
                  <li key={idx} className="text-sm">{warning}</li>
                ))}
              </ul>
            </div>
          )}

          {/* 図表表示 */}
          {comparisonData.figures && Object.keys(comparisonData.figures).length > 0 && (
            <div className="mt-6">
              <h3 className="text-lg font-semibold mb-3">可視化 (S0 vs S1 比較)</h3>
              <div className="space-y-6">
                {Object.entries(
                  Object.entries(comparisonData.figures).reduce((acc: any, [name, url]) => {
                    const panelName = name.replace(/__S[01].*$/, '');
                    if (!acc[panelName]) acc[panelName] = {};
                    if (name.includes('__S0')) {
                      acc[panelName].s0 = url;
                    } else if (name.includes('__S1')) {
                      acc[panelName].s1 = url;
                    }
                    return acc;
                  }, {})
                ).map(([panelName, urls]: [string, any]) => (
                  <SmartFigureCompare
                    key={panelName}
                    title={panelName}
                    srcLeft={urls.s0}
                    srcRight={urls.s1}
                    labelRight={`S1 (反実仮想: ${comparisonData.scenario_id})`}
                  />
                ))}
              </div>
            </div>
          )}
        </>
      )}
    </div>
  );
};

export default ObjectiveComparison;

