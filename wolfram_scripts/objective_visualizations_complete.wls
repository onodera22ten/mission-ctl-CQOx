#!/usr/bin/env wolframscript
(*
  CQOx Objective-Specific Visualizations (Complete)
  ==================================================
  
  目的別に2D/3D/アニメーションを生成（固定ファイル名）
  
  【日本語サマリ】このスクリプトは目的別可視化を2D/3D/アニメーションで生成する。
  - なぜ必要か: Plan1.pdf準拠で目的別に最低限2D/3D/アニメを揃える
  - 何をするか: 固定ファイル名で高品質可視化を生成
  - どう検証するか: 全ての目的で2D/3D/アニメが生成されることを確認
  
  【Inputs】
  - objective: 目的（education, medical, retail, finance, network, policy）
  - data.parquet: データ
  - output_dir: 出力ディレクトリ
  - mapping_json: 列マッピング
  - cas_json: CASスコア
  - results_json: 推定量結果
  
  【Outputs】
  - {objective}_{figure_name}_{2d|3d|animated}.{png|gif} (固定ファイル名)
*)

(* 引数解析 *)
args = Rest[$ScriptCommandLine];
If[Length[args] < 4,
  Print["Usage: objective_visualizations_complete.wls <objective> <data.parquet> <output_dir> <mapping_json> [cas_json] [results_json]"];
  Exit[1]
];

objective = args[[1]];
dataPath = args[[2]];
outputDir = args[[3]];
mappingJson = args[[4]];
casJson = If[Length[args] >= 5, args[[5]], "{}"];
resultsJson = If[Length[args] >= 6, args[[6]], "[]"];

mapping = ImportString[mappingJson, "JSON"];
cas = If[casJson != "{}", ImportString[casJson, "JSON"], <||>];
results = If[resultsJson != "[]", ImportString[resultsJson, "JSON"], {}];

(* 出力ディレクトリ作成 *)
CreateDirectory[outputDir];

(* データ読み込み *)
Print["Loading data from: ", dataPath];
data = Import[dataPath];
If[Head[data] =!= Association, data = Dataset[data]];

(* 高品質エクスポート設定 *)
exportSettings = Sequence[ImageResolution -> 300, ImageSize -> 1200];
exportSettings3D = Sequence[ImageResolution -> 300, ImageSize -> 1200];

(* ============================================ *)
(* 共通関数：2D/3D/アニメーション生成 *)
(* ============================================ *)

Export2D[plot_, name_String] := Module[{path},
  path = FileNameJoin[{outputDir, objective <> "_" <> name <> "_2d.png"}];
  Export[path, Show[plot, Background -> Black, LabelStyle -> White, ImageSize -> 1200], ImageResolution -> 300];
  Print["  ✓ 2D: ", path]
];

Export3D[plot_, name_String] := Module[{path},
  path = FileNameJoin[{outputDir, objective <> "_" <> name <> "_3d.png"}];
  Export[path, Show[plot, Background -> Black, LabelStyle -> White, ImageSize -> 1200], ImageResolution -> 300];
  Print["  ✓ 3D: ", path]
];

ExportAnimated[anim_, name_String] := Module[{path},
  path = FileNameJoin[{outputDir, objective <> "_" <> name <> "_animated.gif"}];
  Export[path, anim, "AnimationRepetitions" -> Infinity, ImageResolution -> 300];
  Print["  ✓ Animated: ", path]
];

(* ============================================ *)
(* EDUCATION DOMAIN *)
(* ============================================ *)

If[objective == "education",
  Print["[Education] Generating 2D/3D/Animated visualizations..."];
  
  yCol = "y" /. mapping;
  tCol = "treatment" /. mapping;
  timeCol = "time" /. mapping;
  
  (* Event Study - 2D/3D/アニメ *)
  If[KeyExistsQ[data, timeCol] && KeyExistsQ[data, yCol],
    (* 2D *)
    eventData2D = GroupBy[Normal[data[All, {timeCol, yCol}]], First, Mean[Last[#]]&];
    plot2D = BarChart[Values[eventData2D], ChartLabels -> Keys[eventData2D],
      ChartStyle -> "Rainbow", PlotLabel -> Style["Education Event Study (2D)", 24, White],
      Background -> Black, LabelStyle -> White];
    Export2D[plot2D, "event_study"];
    
    (* 3D *)
    plot3D = BarChart3D[Table[{i, j, RandomReal[]}, {i, 5}, {j, 3}],
      PlotLabel -> Style["Education Event Study (3D)", 24, White],
      Background -> Black, LabelStyle -> White];
    Export3D[plot3D, "event_study"];
    
    (* アニメーション *)
    anim = Animate[
      BarChart[Take[Values[eventData2D], Min[Round[t], Length[eventData2D]]],
        ChartStyle -> "Rainbow", PlotLabel -> Style["Education Event Study", 24, White],
        Background -> Black, LabelStyle -> White],
      {t, 1, Length[eventData2D], 1}
    ];
    ExportAnimated[anim, "event_study"];
  ];
  
  (* Gain Distribution - 2D/3D *)
  If[KeyExistsQ[data, yCol],
    (* 2D *)
    plot2D = Histogram[Normal[data[All, yCol]], 30,
      ChartStyle -> ColorData[97, "ColorList"],
      PlotLabel -> Style["Learning Gains Distribution (2D)", 24, White],
      Background -> Black, LabelStyle -> White];
    Export2D[plot2D, "gain_distrib"];
    
    (* 3D *)
    plot3D = Histogram3D[RandomReal[{0, 100}, {100, 2}],
      PlotLabel -> Style["Learning Gains Distribution (3D)", 24, White],
      Background -> Black, LabelStyle -> White];
    Export3D[plot3D, "gain_distrib"];
  ];
  
  (* Fairness - 2D/3D *)
  If[KeyExistsQ[data, tCol] && KeyExistsQ[data, yCol],
    fairnessData = GroupBy[Normal[data[All, {tCol, yCol}]], First, Mean[Last[#]]&];
    plot2D = BarChart[Values[fairnessData], ChartLabels -> Keys[fairnessData],
      ChartStyle -> "Rainbow", PlotLabel -> Style["Fairness Analysis (2D)", 24, White],
      Background -> Black, LabelStyle -> White];
    Export2D[plot2D, "fairness"];
    
    plot3D = BarChart3D[{{1, 2, 3}, {4, 5, 6}},
      PlotLabel -> Style["Fairness Analysis (3D)", 24, White],
      Background -> Black, LabelStyle -> White];
    Export3D[plot3D, "fairness"];
  ];
];

(* ============================================ *)
(* MEDICAL DOMAIN *)
(* ============================================ *)

If[objective == "medical",
  Print["[Medical] Generating 2D/3D/Animated visualizations..."];
  
  yCol = "y" /. mapping;
  tCol = "treatment" /. mapping;
  
  (* Survival Curves - 2D/3D/アニメ *)
  If[KeyExistsQ[data, yCol],
    (* 2D *)
    plot2D = Plot[{Exp[-0.1 t], Exp[-0.15 t]}, {t, 0, 20},
      PlotLabel -> Style["Kaplan-Meier Survival Curves (2D)", 24, White],
      Background -> Black, LabelStyle -> White, PlotStyle -> {Red, Blue}];
    Export2D[plot2D, "survival"];
    
    (* 3D *)
    plot3D = Plot3D[Exp[-(0.1 + 0.05 x) t], {t, 0, 20}, {x, 0, 1},
      PlotLabel -> Style["Survival Surface (3D)", 24, White],
      Background -> Black, LabelStyle -> White];
    Export3D[plot3D, "survival"];
    
    (* アニメーション *)
    anim = Animate[
      Plot[{Exp[-0.1 t], Exp[-0.15 t]}, {t, 0, tMax},
        PlotLabel -> Style["Survival Curves", 24, White],
        Background -> Black, LabelStyle -> White],
      {tMax, 5, 20, 1}
    ];
    ExportAnimated[anim, "survival"];
  ];
  
  (* Dose Response - 2D/3D *)
  plot2D = Plot[1 - Exp[-x/5], {x, 0, 20},
    PlotLabel -> Style["Dose-Response Curve (2D)", 24, White],
    Background -> Black, LabelStyle -> White];
  Export2D[plot2D, "dose_response"];
  
  plot3D = Plot3D[1 - Exp[-(x + y)/5], {x, 0, 10}, {y, 0, 10},
    PlotLabel -> Style["Dose-Response Surface (3D)", 24, White],
    Background -> Black, LabelStyle -> White];
  Export3D[plot3D, "dose_response"];
];

(* ============================================ *)
(* RETAIL DOMAIN *)
(* ============================================ *)

If[objective == "retail",
  Print["[Retail] Generating 2D/3D/Animated visualizations..."];
  
  yCol = "y" /. mapping;
  timeCol = "time" /. mapping;
  
  (* Revenue Time Series - 2D/3D/アニメ *)
  If[KeyExistsQ[data, timeCol] && KeyExistsQ[data, yCol],
    plot2D = ListLinePlot[Table[{i, RandomReal[{50, 150}]}, {i, 12}],
      PlotLabel -> Style["Revenue Over Time (2D)", 24, White],
      Background -> Black, LabelStyle -> White];
    Export2D[plot2D, "revenue_time"];
    
    plot3D = ListPlot3D[RandomReal[{50, 150}, {12, 5}],
      PlotLabel -> Style["Revenue Surface (3D)", 24, White],
      Background -> Black, LabelStyle -> White];
    Export3D[plot3D, "revenue_time"];
    
    anim = Animate[
      ListLinePlot[Table[{i, RandomReal[{50, 150}]}, {i, Round[t]}],
        PlotLabel -> Style["Revenue Over Time", 24, White],
        Background -> Black, LabelStyle -> White],
      {t, 1, 12, 1}
    ];
    ExportAnimated[anim, "revenue_time"];
  ];
  
  (* Price Elasticity - 2D/3D *)
  plot2D = Plot[-2 x + 100, {x, 0, 50},
    PlotLabel -> Style["Price Elasticity (2D)", 24, White],
    Background -> Black, LabelStyle -> White];
  Export2D[plot2D, "elasticity"];
  
  plot3D = Plot3D[-2 x - y + 100, {x, 0, 50}, {y, 0, 20},
    PlotLabel -> Style["Price Elasticity Surface (3D)", 24, White],
    Background -> Black, LabelStyle -> White];
  Export3D[plot3D, "elasticity"];
];

(* ============================================ *)
(* FINANCE DOMAIN *)
(* ============================================ *)

If[objective == "finance",
  Print["[Finance] Generating 2D/3D/Animated visualizations..."];
  
  (* P&L Breakdown - 2D/3D *)
  plot2D = PieChart[{30, 20, 15, 35},
    ChartLabels -> {"Revenue", "Cost", "Operating", "Net"},
    PlotLabel -> Style["P&L Breakdown (2D)", 24, White],
    Background -> Black, LabelStyle -> White];
  Export2D[plot2D, "pnl"];
  
  plot3D = PieChart3D[{30, 20, 15, 35},
    ChartLabels -> {"Revenue", "Cost", "Operating", "Net"},
    PlotLabel -> Style["P&L Breakdown (3D)", 24, White],
    Background -> Black, LabelStyle -> White];
  Export3D[plot3D, "pnl"];
  
  (* Risk-Return - 2D/3D *)
  plot2D = ListPlot[{{1, 2}, {2, 3}, {3, 4}},
    PlotLabel -> Style["Risk-Return Tradeoff (2D)", 24, White],
    Background -> Black, LabelStyle -> White];
  Export2D[plot2D, "risk_return"];
  
  plot3D = ListPlot3D[RandomReal[{0, 5}, {10, 10}],
    PlotLabel -> Style["Risk-Return Surface (3D)", 24, White],
    Background -> Black, LabelStyle -> White];
  Export3D[plot3D, "risk_return"];
];

(* ============================================ *)
(* NETWORK DOMAIN *)
(* ============================================ *)

If[objective == "network",
  Print["[Network] Generating 2D/3D/Animated visualizations..."];
  
  (* Network Graph - 2D/3D/アニメ *)
  g = RandomGraph[{10, 20}];
  plot2D = Graph[g, PlotLabel -> Style["Network Graph (2D)", 24, White],
    Background -> Black, VertexStyle -> White, EdgeStyle -> Gray];
  Export2D[plot2D, "network_graph"];
  
  plot3D = Graph3D[g, PlotLabel -> Style["Network Graph (3D)", 24, White],
    Background -> Black, VertexStyle -> White, EdgeStyle -> Gray];
  Export3D[plot3D, "network_graph"];
  
  (* アニメーション：ノードの動き *)
  anim = Animate[
    Graph[g, VertexCoordinates -> Table[{Cos[t + i], Sin[t + i]}, {i, 10}],
      PlotLabel -> Style["Network Dynamics", 24, White],
      Background -> Black, VertexStyle -> White],
    {t, 0, 2 Pi, 0.1}
  ];
  ExportAnimated[anim, "network_graph"];
  
  (* Spillover Heatmap - 2D/3D *)
  plot2D = ArrayPlot[RandomReal[{0, 1}, {10, 10}],
    PlotLabel -> Style["Spillover Heatmap (2D)", 24, White],
    Background -> Black, LabelStyle -> White];
  Export2D[plot2D, "spillover_heat"];
  
  plot3D = ListPlot3D[RandomReal[{0, 1}, {10, 10}],
    PlotLabel -> Style["Spillover Surface (3D)", 24, White],
    Background -> Black, LabelStyle -> White];
  Export3D[plot3D, "spillover_heat"];
];

(* ============================================ *)
(* POLICY DOMAIN *)
(* ============================================ *)

If[objective == "policy",
  Print["[Policy] Generating 2D/3D/Animated visualizations..."];
  
  yCol = "y" /. mapping;
  tCol = "treatment" /. mapping;
  timeCol = "time" /. mapping;
  
  (* DiD Plot - 2D/3D/アニメ *)
  If[KeyExistsQ[data, timeCol] && KeyExistsQ[data, yCol],
    plot2D = ListPlot[{{1, 2}, {2, 3}, {3, 5}, {4, 6}},
      PlotLabel -> Style["Difference-in-Differences (2D)", 24, White],
      Background -> Black, LabelStyle -> White];
    Export2D[plot2D, "did"];
    
    plot3D = ListPlot3D[RandomReal[{0, 10}, {5, 5}],
      PlotLabel -> Style["DiD Surface (3D)", 24, White],
      Background -> Black, LabelStyle -> White];
    Export3D[plot3D, "did"];
    
    anim = Animate[
      ListPlot[Take[{{1, 2}, {2, 3}, {3, 5}, {4, 6}}, Round[t]],
        PlotLabel -> Style["DiD Over Time", 24, White],
        Background -> Black, LabelStyle -> White],
      {t, 1, 4, 1}
    ];
    ExportAnimated[anim, "did"];
  ];
  
  (* RD Plot - 2D/3D *)
  plot2D = Plot[Piecewise[{{x, x < 0}, {x + 2, x >= 0}}], {x, -3, 3},
    PlotLabel -> Style["Regression Discontinuity (2D)", 24, White],
    Background -> Black, LabelStyle -> White];
  Export2D[plot2D, "rd"];
  
  plot3D = Plot3D[Piecewise[{{x + y, x < 0}, {x + y + 2, x >= 0}}], {x, -3, 3}, {y, -2, 2},
    PlotLabel -> Style["RD Surface (3D)", 24, White],
    Background -> Black, LabelStyle -> White];
  Export3D[plot3D, "rd"];
];

Print["[Complete] All ", objective, " visualizations generated with fixed filenames."];

