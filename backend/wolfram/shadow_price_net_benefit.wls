#!/usr/bin/env wolframscript
(*
  影の価格・純便益の計算（Wolfram即評価）
  
  【日本語サマリ】このモジュールは影の価格と純便益をWolframで即評価する。
  - なぜ必要か: 政策評価で限界効果とコストの比較が必要
  - 何をするか: 数式を定義し、即座に評価可能な形で提供
  - どう検証するか: 既知の値で検証
*)

(* ============================================ *)
(* 影の価格（Shadow Price） *)
(* ============================================ *)

ShadowPrice[tau_Real, cost_Real, lambda_Real:1.0] := Module[{result},
  (* 影の価格 = 限界効果 / 限界コスト *)
  (* 経済学的には：1単位の処置コストあたりの効果 *)
  
  If[cost > 0,
    result = tau / cost,
    (* コストが0の場合はlambdaでスケール *)
    result = tau * lambda
  ];
  
  (* 即評価形式も返す *)
  <|
    "value" -> result,
    "formula" -> HoldForm[\[Tau]/c],
    "evaluated_formula" -> HoldForm[tau/cost],
    "interpretation" -> "Effect per unit cost"
  |>
];

(* ============================================ *)
(* 純便益（Net Benefit） *)
(* ============================================ *)

NetBenefit[tau_Real, cost_Real, lambda_Real:1.0] := Module[{result},
  (* 純便益 = 効果 - lambda * コスト *)
  (* コスト-効果分析の標準指標 *)
  
  result = tau - lambda * cost;
  
  <|
    "value" -> result,
    "formula" -> HoldForm[\[Tau] - \[Lambda] c],
    "evaluated_formula" -> HoldForm[tau - lambda*cost],
    "interpretation" -> If[result > 0, "Positive net benefit", "Negative net benefit"]
  |>
];

(* ============================================ *)
(* 数式表示（LaTeX形式も生成） *)
(* ============================================ *)

FormatShadowPriceFormula[] := TraditionalForm[
  HoldForm[ShadowPrice == \[Tau]/c]
];

FormatNetBenefitFormula[] := TraditionalForm[
  HoldForm[NetBenefit == \[Tau] - \[Lambda] c]
];

(* ============================================ *)
(* 一括計算・可視化 *)
(* ============================================ *)

CalculatePolicyMetrics[tau_Real, cost_Real, lambda_Real:1.0] := Module[{sp, nb},
  sp = ShadowPrice[tau, cost, lambda];
  nb = NetBenefit[tau, cost, lambda];
  
  <|
    "shadow_price" -> sp,
    "net_benefit" -> nb,
    "tau" -> tau,
    "cost" -> cost,
    "lambda" -> lambda,
    "recommendation" -> If[nb["value"] > 0,
      "Adopt policy (positive net benefit)",
      "Reject policy (negative net benefit)"
    ]
  |>
];

(* テスト実行 *)
If[Length[$ScriptCommandLine] > 1,
  args = Rest[$ScriptCommandLine];
  If[Length[args] >= 2,
    tau = ToExpression[args[[1]]];
    cost = ToExpression[args[[2]]];
    lambda = If[Length[args] >= 3, ToExpression[args[[3]]], 1.0];
    
    result = CalculatePolicyMetrics[tau, cost, lambda];
    Print["Shadow Price: ", result["shadow_price"]["value"]];
    Print["Net Benefit: ", result["net_benefit"]["value"]];
    Print["Recommendation: ", result["recommendation"]];
  ]
];

