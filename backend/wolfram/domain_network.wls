#!/usr/bin/env wolframscript
(* Domain Detection Network - Interactive Knowledge Graph *)

(* Define domains and their keyword relationships *)
domains = {"Medical", "Education", "Retail", "Finance", "Network", "Policy"};

(* Create edges based on shared concepts *)
edges = {
  "Medical" <-> "Policy",        (* Health policy *)
  "Education" <-> "Policy",      (* Education policy *)
  "Retail" <-> "Finance",        (* Commercial finance *)
  "Network" <-> "Policy",        (* Social network policy *)
  "Medical" <-> "Network",       (* Healthcare networks *)
  "Education" <-> "Network",     (* Educational networks *)
  "Retail" <-> "Network",        (* Customer networks *)
  "Finance" <-> "Policy"         (* Financial regulation *)
};

(* Domain characteristics (sample dataset) *)
domainScores = Association[
  "Medical" -> 0.85,
  "Education" -> 0.32,
  "Retail" -> 0.18,
  "Finance" -> 0.45,
  "Network" -> 0.22,
  "Policy" -> 0.51
];

(* Create stunning network graph *)
graph = Graph[edges,
  VertexLabels -> Table[d -> Placed[Style[d, 14, Bold], Center], {d, domains}],
  VertexSize -> Table[d -> 0.5 + domainScores[d]*0.8, {d, domains}],
  VertexStyle -> Table[d ->
    Directive[
      Opacity[0.8],
      Blend[{RGBColor[0.9, 0.3, 0.3], RGBColor[0.3, 0.7, 0.3]}, domainScores[d]]
    ], {d, domains}],
  EdgeStyle -> Directive[Gray, Thickness[0.003], Opacity[0.5]],
  GraphLayout -> {"SpringElectricalEmbedding", "EdgeWeighted" -> True},
  VertexShapeFunction -> "Circle",
  ImageSize -> 900,
  Background -> White
];

(* Add confidence scores as tooltips *)
graphWithTooltips = Graph[edges,
  VertexLabels -> Table[d -> Placed[Style[d, 14, Bold], Center], {d, domains}],
  VertexSize -> Table[d -> 0.5 + domainScores[d]*0.8, {d, domains}],
  VertexStyle -> Table[d ->
    Tooltip[
      Directive[Opacity[0.8],
        Blend[{RGBColor[0.9, 0.3, 0.3], RGBColor[0.3, 0.7, 0.3]}, domainScores[d]]],
      Style[StringForm["`` Confidence: ``%", d, NumberForm[domainScores[d]*100, {3, 1}]], 12]
    ], {d, domains}],
  EdgeStyle -> Directive[Gray, Thickness[0.003], Opacity[0.5]],
  GraphLayout -> {"SpringElectricalEmbedding"},
  ImageSize -> 900,
  Background -> White
];

(* Domain detection algorithm visualization *)
algorithmViz = Graphics[{
  (* Title *)
  Text[Style["Domain Detection: TF-IDF Algorithm", 16, Bold], {0, 0.95}],

  (* Algorithm steps *)
  {LightBlue, Rectangle[{-0.9, 0.7}, {0.9, 0.85}]},
  Text[Style["1. Extract Keywords from Dataset", 12, Bold], {0, 0.775}],

  {LightGreen, Rectangle[{-0.9, 0.5}, {0.9, 0.65}]},
  Text[Style["2. Compute TF-IDF Scores", 12, Bold], {0, 0.575}],

  {LightYellow, Rectangle[{-0.9, 0.3}, {0.9, 0.45}]},
  Text[Style["3. Match Against Domain Dictionaries", 12, Bold], {0, 0.375}],

  {LightRed, Rectangle[{-0.9, 0.1}, {0.9, 0.25}]},
  Text[Style["4. Rank by Confidence Score", 12, Bold], {0, 0.175}],

  (* Top domains *)
  Text[Style["Top Detected Domains:", 14, Bold, FontFamily -> "Helvetica"],
    {0, -0.1}],

  Text[Style[Grid[
    Prepend[
      SortBy[Normal[domainScores], -#[[2]] &][[1;;3]] /.
        {d_, s_} :> {d, NumberForm[s*100, {3, 1}] <> "%",
                      ProgressIndicator[s, {0, 1}, ImageSize -> 200]},
      {"Domain", "Confidence", "Score"}
    ],
    Alignment -> Left,
    Dividers -> {False, {True, True}},
    Spacings -> {2, 1},
    Frame -> All,
    FrameStyle -> Gray
  ], 11], {0, -0.5}]
},
ImageSize -> 700,
PlotRange -> {{-1, 1}, {-0.8, 1}},
Background -> GrayLevel[0.97]
];

(* Combine network and algorithm *)
final = GraphicsRow[{graphWithTooltips, algorithmViz},
  ImageSize -> 1700,
  PlotLabel -> Style["CQOx Domain Detection: Knowledge Graph & TF-IDF Analysis",
    20, Bold, FontFamily -> "Helvetica"],
  Background -> White,
  Spacings -> 20
];

(* Export *)
Export["reports/wolfram_domain_network.png", final,
  ImageResolution -> 300, Background -> White];

(* Also export standalone network *)
Export["reports/wolfram_domain_network_graph.png", graphWithTooltips,
  ImageResolution -> 300, Background -> White];

Print["✅ Domain Network exported to reports/wolfram_domain_network.png"];
Print["✅ Standalone graph exported to reports/wolfram_domain_network_graph.png"];
