#!/usr/bin/env wolframscript
(* Dynamic ATE Time-Series Animation - Stunning Visualization *)

(* Generate realistic time-varying treatment effects with confidence intervals *)
timePoints = Range[0, 24, 1];
ateTrue = Table[1.5 + 0.3*Sin[t/3] + 0.1*t, {t, timePoints}];
ateObs = Table[ateTrue[[i]] + RandomReal[{-0.4, 0.4}], {i, Length[timePoints]}];
ciLower = ateObs - 0.5;
ciUpper = ateObs + 0.5;

(* Create animated visualization showing data accumulation *)
frames = Table[
  Module[{currentData, currentCI, p1, p2, combined},
    currentData = Take[Transpose[{timePoints, ateObs}], t];
    currentCI = Take[Transpose[{timePoints, ciLower, ciUpper}], t];

    (* Main ATE plot *)
    p1 = Show[
      (* Confidence band *)
      ListPlot[
        {Transpose[{timePoints[[1;;t]], ciLower[[1;;t]]}],
         Transpose[{timePoints[[1;;t]], ciUpper[[1;;t]]}]},
        Joined -> True,
        Filling -> {1 -> {2}},
        FillingStyle -> Directive[Opacity[0.2], Blue],
        PlotStyle -> None
      ],
      (* True effect (hidden in real analysis) *)
      Plot[1.5 + 0.3*Sin[x/3] + 0.1*x, {x, 0, t},
        PlotStyle -> Directive[Dashed, Gray, Thickness[0.003]],
        PlotLegends -> None
      ],
      (* Observed ATE *)
      ListPlot[currentData,
        Joined -> True,
        PlotStyle -> Directive[Red, Thickness[0.005]],
        PlotMarkers -> {Automatic, 12},
        PlotLegends -> None
      ],
      (* Reference line at 0 *)
      Plot[0, {x, 0, 24},
        PlotStyle -> Directive[Black, Dashed, Thin]
      ],
      PlotRange -> {{0, 24}, {-1, 5}},
      Frame -> True,
      FrameLabel -> {Style["Time Period", 16, Bold],
                     Style["Average Treatment Effect (ATE)", 16, Bold]},
      PlotLabel -> Style[StringForm["Dynamic ATE Evolution\nPeriod: 0 to ``", t],
                        18, Bold],
      GridLines -> {Automatic, Automatic},
      GridLinesStyle -> Directive[LightGray, Dotted],
      ImageSize -> 1000,
      Background -> White
    ];

    (* Statistical summary panel *)
    p2 = Graphics[{
      Text[Style[Column[{
        "Current Statistics:",
        "",
        StringForm["Current ATE: ``", NumberForm[ateObs[[t]], {3, 2}]],
        StringForm["95% CI: [`` , ``]",
          NumberForm[ciLower[[t]], {3, 2}],
          NumberForm[ciUpper[[t]], {3, 2}]],
        "",
        StringForm["Sample Size: ``", t * 50],
        StringForm["Observations: ``", t],
        "",
        If[t > 5,
          StringForm["Trend: ``",
            If[ateObs[[t]] > ateObs[[t-5]], "↑ Increasing", "↓ Decreasing"]],
          "Trend: Accumulating..."
        ]
      }, Alignment -> Left], 14, Bold, FontFamily -> "Helvetica"], {0, 0}]
    }, ImageSize -> 300, PlotRange -> {{-1, 1}, {-1, 1}}];

    GraphicsRow[{p1, p2},
      ImageSize -> 1400,
      Background -> GrayLevel[0.98]]
  ],
  {t, 1, Length[timePoints]}
];

(* Export animation as GIF *)
Export["reports/wolfram_ate_animation.gif", frames,
  "DisplayDurations" -> 0.3,
  "AnimationRepetitions" -> Infinity,
  ImageResolution -> 150
];

(* Also export final frame as high-res PNG *)
Export["reports/wolfram_ate_final.png", Last[frames],
  ImageResolution -> 300, Background -> White];

Print["✅ ATE Animation exported to reports/wolfram_ate_animation.gif"];
Print["✅ Final frame exported to reports/wolfram_ate_final.png"];
