#!/usr/bin/env wolframscript
(* CAS Radar Chart - Mathematically Beautiful Visualization *)

(* CAS (Causal Assurance Score) dimensions *)
dimensions = {"Internal\nValidity", "External\nValidity", "Transport-\nability",
              "Robustness", "Stability"};
scores = {0.85, 0.72, 0.78, 0.81, 0.88};  (* Sample CAS scores *)
threshold = 0.70;  (* Green threshold *)

(* Create beautiful radar chart *)
radarChart = Module[{n, angles, points, thresholdPoints},
  n = Length[scores];
  angles = Table[2*Pi*i/n - Pi/2, {i, 0, n-1}];

  (* Score points *)
  points = Table[scores[[i]]*{Cos[angles[[i]]], Sin[angles[[i]]]}, {i, n}];

  (* Threshold circle points *)
  thresholdPoints = Table[threshold*{Cos[a], Sin[a]}, {a, 0, 2*Pi, 0.01}];

  Graphics[{
    (* Background circles *)
    Table[{GrayLevel[0.95 - i*0.05], Thickness[0.001],
           Circle[{0, 0}, i*0.2]},
      {i, 1, 5}],

    (* Threshold circle *)
    {Dashed, Thickness[0.003], Orange,
     Line[threshold*Table[{Cos[a], Sin[a]}, {a, 0, 2*Pi, 0.01}]]},

    (* Axes *)
    Table[{Gray, Thickness[0.001],
           Line[{{0, 0}, {Cos[angles[[i]]], Sin[angles[[i]]]}}]},
      {i, n}],

    (* Data polygon *)
    {Opacity[0.3], Blue, Polygon[points]},
    {Thickness[0.004], Blue, Line[Append[points, First[points]]]},

    (* Data points *)
    {Red, PointSize[0.025], Point[points]},

    (* Labels *)
    Table[
      Text[Style[dimensions[[i]], 13, Bold],
        1.25*{Cos[angles[[i]]], Sin[angles[[i]]]},
        {-Sign[Cos[angles[[i]]]], -Sign[Sin[angles[[i]]]]}],
      {i, n}
    ],

    (* Score values *)
    Table[
      Text[Style[NumberForm[scores[[i]], {1, 2}], 11, Bold, Blue],
        1.05*scores[[i]]*{Cos[angles[[i]]], Sin[angles[[i]]]}],
      {i, n}
    ],

    (* Circle labels *)
    Table[
      Text[Style[ToString[i*0.2], 9, Gray], {i*0.2 + 0.05, 0.05}],
      {i, 1, 5}
    ]
  },
  PlotRange -> {{-1.4, 1.4}, {-1.4, 1.4}},
  ImageSize -> 800,
  AspectRatio -> 1,
  Background -> White
  ]
];

(* Overall CAS score *)
overallCAS = Mean[scores];
grade = Which[
  overallCAS >= 0.80, "A (Excellent)",
  overallCAS >= 0.70, "B (Good)",
  overallCAS >= 0.60, "C (Acceptable)",
  True, "D (Poor)"
];

(* Summary statistics panel *)
summaryPanel = Graphics[{
  (* Title *)
  Text[Style["CAS Metrics Summary", 18, Bold, FontFamily -> "Helvetica"],
    {0, 0.9}],

  (* Overall score *)
  {RGBColor[0.2, 0.6, 0.3],
   Rectangle[{-0.9, 0.6}, {0.9, 0.75}]},
  Text[Style[StringForm["Overall CAS: `` (Grade: ``)",
    NumberForm[overallCAS, {1, 3}], grade],
    16, Bold, White], {0, 0.675}],

  (* Individual scores *)
  Text[Style[Grid[
    Prepend[
      Table[{dimensions[[i]], NumberForm[scores[[i]], {1, 2}],
             ProgressIndicator[scores[[i]], {0, 1}, ImageSize -> 150]},
        {i, Length[scores]}],
      {"Dimension", "Score", "Progress"}
    ],
    Alignment -> Left,
    Dividers -> {False, {True, True}},
    Spacings -> {2, 1},
    Frame -> All,
    FrameStyle -> LightGray
  ], 12], {0, 0}]
},
ImageSize -> 700,
PlotRange -> {{-1, 1}, {-0.5, 1}},
Background -> GrayLevel[0.98]
];

(* Combine radar chart and summary *)
final = GraphicsRow[{radarChart, summaryPanel},
  ImageSize -> 1600,
  PlotLabel -> Style["CQOx Causal Assurance Score (CAS) - Pentagon Analysis",
    22, Bold, FontFamily -> "Helvetica"],
  Background -> White
];

(* Export *)
Export["reports/wolfram_cas_radar.png", final,
  ImageResolution -> 300, Background -> White];

Print["✅ CAS Radar Chart exported to reports/wolfram_cas_radar.png"];
