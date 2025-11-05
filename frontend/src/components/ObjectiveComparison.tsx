import React, { useEffect, useState } from "react";
import { runScenario } from "../lib/client";

const ObjectiveComparison = () => {
  const [comparisonData, setComparisonData] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const fetchData = async () => {
      try {
        setLoading(true);
        // デフォルトで realistic_retail_5k を使用
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

    fetchData();
  }, []);

  if (loading) {
    return (
      <div className="p-4 text-center">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-500 mx-auto mb-2"></div>
        <p className="text-gray-600">反実仮想シナリオを実行中...</p>
      </div>
    );
  }

  if (error) {
    return (
      <div className="p-4 bg-red-50 border border-red-200 rounded">
        <h3 className="text-red-700 font-bold">エラー</h3>
        <p className="text-red-600">{error}</p>
      </div>
    );
  }

  if (!comparisonData) {
    return <div className="p-4 text-gray-600">データがありません</div>;
  }

  return (
    <div className="p-6 bg-white rounded-lg shadow">
      <h2 className="text-2xl font-bold mb-4">反実仮想比較 (Counterfactual Comparison)</h2>

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

      {/* 警告表示 - MVP/Mock warnings are filtered out */}
      {comparisonData.warnings && comparisonData.warnings.filter((w: string) =>
        !w.includes('MVP') &&
        !w.includes('mock') &&
        !w.includes('Mock') &&
        !w.includes('Production version requires')
      ).length > 0 && (
        <div className="mb-6 p-4 bg-yellow-50 border border-yellow-200 rounded">
          <h3 className="text-yellow-800 font-semibold mb-2">注意事項</h3>
          <ul className="list-disc list-inside text-yellow-700">
            {comparisonData.warnings.filter((w: string) =>
              !w.includes('MVP') &&
              !w.includes('mock') &&
              !w.includes('Mock') &&
              !w.includes('Production version requires')
            ).map((warning: string, idx: number) => (
              <li key={idx} className="text-sm">{warning}</li>
            ))}
          </ul>
        </div>
      )}

      {/* 図表表示 - S0/S1 Side-by-Side (NASA/Google Standard) */}
      {comparisonData.figures && Object.keys(comparisonData.figures).length > 0 && (
        <div className="mt-6">
          <h3 className="text-lg font-semibold mb-3">可視化 (S0 vs S1 比較)</h3>
          <div className="space-y-6">
            {/* Group figures by panel name (extract base name before __S0 or __S1) */}
            {Object.entries(
              Object.entries(comparisonData.figures).reduce((acc: any, [name, url]) => {
                // Extract panel name: "ate_density__S0" -> "ate_density"
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
              <div key={panelName} className="border rounded-lg p-4 bg-gray-50">
                <h4 className="text-md font-semibold mb-3 text-gray-700">
                  {panelName.replace(/_/g, ' ').toUpperCase()}
                </h4>
                <div className="grid grid-cols-2 gap-4">
                  {/* S0 (Observed) - Left side */}
                  <div className="border-2 border-blue-300 rounded p-2 bg-white">
                    <p className="text-sm font-bold text-blue-700 mb-2">S0 (観測)</p>
                    {urls.s0 ? (
                      // Auto-detect HTML vs image (Wolfram HTML uses iframe)
                      /\.html?(\?|$)/i.test(urls.s0 as string) ? (
                        <iframe
                          src={urls.s0 as string}
                          className="w-full h-64 rounded border-0"
                          title={`${panelName} S0 interactive`}
                        />
                      ) : (
                        <img
                          src={urls.s0 as string}
                          alt={`${panelName} S0`}
                          className="w-full h-64 object-contain rounded bg-white"
                          onError={(e) => {
                            (e.target as HTMLImageElement).style.display = 'none';
                          }}
                        />
                      )
                    ) : (
                      <div className="w-full h-48 flex items-center justify-center bg-gray-200 rounded text-gray-500">
                        データなし
                      </div>
                    )}
                  </div>

                  {/* S1 (Counterfactual) - Right side */}
                  <div className="border-2 border-green-300 rounded p-2 bg-white">
                    <p className="text-sm font-bold text-green-700 mb-2">
                      S1 (反実仮想: {comparisonData.scenario_id})
                    </p>
                    {urls.s1 ? (
                      // Auto-detect HTML vs image (Wolfram HTML uses iframe)
                      /\.html?(\?|$)/i.test(urls.s1 as string) ? (
                        <iframe
                          src={urls.s1 as string}
                          className="w-full h-64 rounded border-0"
                          title={`${panelName} S1 interactive`}
                        />
                      ) : (
                        <img
                          src={urls.s1 as string}
                          alt={`${panelName} S1`}
                          className="w-full h-64 object-contain rounded bg-white"
                          onError={(e) => {
                            (e.target as HTMLImageElement).style.display = 'none';
                          }}
                        />
                      )
                    ) : (
                      <div className="w-full h-48 flex items-center justify-center bg-gray-200 rounded text-gray-500">
                        シナリオ未実行
                      </div>
                    )}
                  </div>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
};

export default ObjectiveComparison;
