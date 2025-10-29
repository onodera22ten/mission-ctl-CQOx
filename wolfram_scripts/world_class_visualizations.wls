#!/usr/bin/env wolframscript
(* World-Class 3D/Animated Visualizations for CQOx *)
(* Phase: Production-Ready Interactive Diagrams *)

Print["=== World-Class WolframONE Visualizations ==="];

outputDir = "reports/world_class/";
If[!DirectoryQ[outputDir], CreateDirectory[outputDir]];

(* ============================================ *)
(* 1. 3D Causal DAG with Interactive Rotation *)
(* ============================================ *)
Print["[1/6] Generating 3D Interactive Causal DAG..."];

(* Define causal structure *)
edges = {
  "Treatment" -> "Outcome",
  "Confounder" -> "Treatment",
  "Confounder" -> "Outcome",
  "Instrumental" -> "Treatment",
  "Mediator" -> "Outcome",
  "Treatment" -> "Mediator",
  "Modifier" -> "Outcome"
};

(* 3D positions *)
vertexCoords = {
  "Treatment" -> {0, 0, 0},
  "Outcome" -> {3, 0, 0},
  "Confounder" -> {1.5, 2, 1.5},
  "Instrumental" -> {-1.5, 0, 1},
  "Mediator" -> {1.5, -1.5, 0},
  "Modifier" -> {3, 1.5, 1}
};

(* Color scheme *)
vertexColors = {
  "Treatment" -> RGBColor[0.2, 0.6, 1],
  "Outcome" -> RGBColor[1, 0.4, 0.4],
  "Confounder" -> RGBColor[0.8, 0.3, 0.8],
  "Instrumental" -> RGBColor[0.3, 0.8, 0.3],
  "Mediator" -> RGBColor[1, 0.7, 0.2],
  "Modifier" -> RGBColor[0.5, 0.8, 0.9]
};

causalDAG3D = Graph3D[edges,
  VertexCoordinates -> vertexCoords,
  VertexSize -> 0.5,
  VertexStyle -> vertexColors,
  VertexLabels -> Placed["Name", Center],
  EdgeStyle -> Directive[Thick, Opacity[0.7], Arrowheads[0.03]],
  ImageSize -> 800,
  ViewPoint -> {2, -2, 1.5},
  Lighting -> "Neutral",
  Background -> Black,
  VertexLabelStyle -> Directive[White, Bold, 14]
];

Export[outputDir <> "causal_dag_3d.png", causalDAG3D, ImageResolution -> 300];

(* Animated rotation *)
animatedDAG = Animate[
  Show[causalDAG3D, ViewPoint -> {2*Cos[t], 2*Sin[t], 1.5}],
  {t, 0, 2*Pi},
  AnimationRate -> 0.3
];
Export[outputDir <> "causal_dag_animated.gif", animatedDAG, "AnimationRepetitions" -> Infinity];

Print["  ✓ 3D DAG: ", outputDir, "causal_dag_3d.png"];
Print["  ✓ Animated: ", outputDir, "causal_dag_animated.gif"];

(* ============================================ *)
(* 2. Time-Varying Treatment Effect Animation *)
(* ============================================ *)
Print["[2/6] Generating TVCE Animation..."];

(* Generate synthetic TVCE data *)
tMax = 20;
timePoints = Range[0, tMax, 0.5];
tvceData = Table[{
  t,
  0.5 + 0.3*Sin[t/3] + 0.1*RandomReal[],
  0.5 + 0.3*Sin[t/3] - 0.05,
  0.5 + 0.3*Sin[t/3] + 0.05
}, {t, timePoints}];

tvceAnimation = Animate[
  ListPlot[
    {
      Take[tvceData[[All, {1, 2}]], Min[Round[frame], Length[tvceData]]],
      Take[tvceData[[All, {1, 3}]], Min[Round[frame], Length[tvceData]]],
      Take[tvceData[[All, {1, 4}]], Min[Round[frame], Length[tvceData]]]
    },
    Joined -> {True, True, True},
    PlotStyle -> {
      Directive[Thick, RGBColor[0.2, 0.6, 1]],
      Directive[Dashed, RGBColor[0.6, 0.6, 0.6]],
      Directive[Dashed, RGBColor[0.6, 0.6, 0.6]]
    },
    PlotRange -> {{0, tMax}, {0, 1.2}},
    ImageSize -> 800,
    Background -> Black,
    Frame -> True,
    FrameStyle -> White,
    PlotLabel -> Style["Time-Varying Causal Effect", White, Bold, 18],
    FrameLabel -> {
      Style["Time", White, 14],
      Style["Treatment Effect (τ)", White, 14]
    },
    GridLines -> Automatic,
    GridLinesStyle -> Directive[Gray, Dashed],
    Filling -> {2 -> {3}},
    FillingStyle -> Directive[Opacity[0.2], RGBColor[0.2, 0.6, 1]],
    Epilog -> {
      White,
      Inset[Style[StringForm["t = ``", Round[frame, 0.1]], White, Bold, 16], {tMax*0.9, 1.1}]
    }
  ],
  {frame, 1, Length[tvceData]},
  AnimationRate -> 5
];

Export[outputDir <> "tvce_animated.gif", tvceAnimation, "AnimationRepetitions" -> Infinity];
Print["  ✓ TVCE Animation: ", outputDir, "tvce_animated.gif"];

(* ============================================ *)
(* 3. 3D CATE Heterogeneity Surface *)
(* ============================================ *)
Print["[3/6] Generating 3D CATE Surface..."];

(* CATE as function of 2 covariates *)
cateFunction[x1_, x2_] := 0.5 + 0.3*Sin[x1] + 0.2*Cos[x2] + 0.1*x1*x2;

cateSurface3D = Plot3D[
  cateFunction[x1, x2],
  {x1, -2, 2},
  {x2, -2, 2},
  PlotStyle -> Directive[Opacity[0.8], Specularity[White, 20]],
  ColorFunction -> "Rainbow",
  Mesh -> 20,
  MeshStyle -> Directive[Thin, Gray],
  Boxed -> False,
  Axes -> True,
  AxesLabel -> {
    Style["Covariate X1", White, 14],
    Style["Covariate X2", White, 14],
    Style["CATE τ(X)", White, 14]
  },
  AxesStyle -> White,
  Background -> Black,
  ImageSize -> 800,
  PlotLabel -> Style["Conditional Average Treatment Effect Surface", White, Bold, 18],
  ViewPoint -> {2, -2, 1.5},
  Lighting -> "Neutral"
];

Export[outputDir <> "cate_surface_3d.png", cateSurface3D, ImageResolution -> 300];

(* Animated rotation *)
cateAnimated = Animate[
  Show[cateSurface3D, ViewPoint -> {2.5*Cos[t], 2.5*Sin[t], 1.5}],
  {t, 0, 2*Pi},
  AnimationRate -> 0.3
];
Export[outputDir <> "cate_surface_animated.gif", cateAnimated, "AnimationRepetitions" -> Infinity];

Print["  ✓ CATE Surface: ", outputDir, "cate_surface_3d.png"];
Print["  ✓ Animated: ", outputDir, "cate_surface_animated.gif"];

(* ============================================ *)
(* 4. Network Diffusion 3D Animation *)
(* ============================================ *)
Print["[4/6] Generating Network Diffusion Animation..."];

(* Generate random network *)
SeedRandom[42];
nNodes = 30;
edges3D = RandomGraph[BarabasiAlbertGraphDistribution[nNodes, 2]];

(* 3D layout *)
coords3D = GraphEmbedding[edges3D, 3, "SpringElectricalEmbedding"];

(* Diffusion simulation *)
nSteps = 20;
seedNode = 1;
infected = {seedNode};

diffusionStates = Reap[
  Do[
    (* Spread to neighbors *)
    newInfected = Union[infected,
      Flatten[Cases[EdgeList[edges3D],
        DirectedEdge[i_, j_] /; MemberQ[infected, i] :> j]]];
    Sow[newInfected];
    infected = newInfected,
    {nSteps}
  ]
][[2, 1]];

(* Create animation *)
diffusionAnimation = Table[
  Graph3D[edges3D,
    VertexCoordinates -> coords3D,
    VertexSize -> 0.3,
    VertexStyle -> Table[
      i -> If[MemberQ[diffusionStates[[Min[step, Length[diffusionStates]]]], i],
        RGBColor[1, 0.2, 0.2],
        RGBColor[0.3, 0.3, 0.3]
      ],
      {i, nNodes}
    ],
    EdgeStyle -> Directive[Gray, Opacity[0.4]],
    ImageSize -> 800,
    Background -> Black,
    PlotLabel -> Style[StringForm["Network Diffusion: Step ``/``", step, nSteps],
      White, Bold, 18],
    ViewPoint -> {2*Cos[step*Pi/10], 2*Sin[step*Pi/10], 1.5}
  ],
  {step, 1, nSteps}
];

Export[outputDir <> "network_diffusion_3d.gif", diffusionAnimation,
  "DisplayDurations" -> 0.2, "AnimationRepetitions" -> Infinity];
Print["  ✓ Network Diffusion: ", outputDir, "network_diffusion_3d.gif"];

(* ============================================ *)
(* 5. Sensitivity Analysis 3D Contour *)
(* ============================================ *)
Print["[5/6] Generating Sensitivity Analysis 3D..."];

(* Rosenbaum sensitivity bounds *)
gammaRange = {1, 3};
confoundingStrength = Table[{gamma, pval},
  {gamma, 1, 3, 0.1},
  {pval, {0.01, 0.05, 0.1}}
];

sensitivityPlot3D = Plot3D[
  0.05 * Exp[-(x - 1)^2 - (y - 1)^2],
  {x, 1, 3},
  {y, 0, 0.5},
  PlotStyle -> Directive[Opacity[0.7]],
  ColorFunction -> Function[{x, y, z},
    If[z > 0.05, RGBColor[0.2, 0.8, 0.2], RGBColor[1, 0.3, 0.3]]],
  Mesh -> None,
  RegionFunction -> Function[{x, y, z}, z < 0.05],
  Boxed -> True,
  Axes -> True,
  AxesLabel -> {
    Style["Γ (Sensitivity)", White, 14],
    Style["Confounding Bias", White, 14],
    Style["p-value", White, 14]
  },
  AxesStyle -> White,
  Background -> Black,
  ImageSize -> 800,
  PlotLabel -> Style["Rosenbaum Sensitivity Analysis", White, Bold, 18],
  ViewPoint -> {2, -2, 1.5}
];

Export[outputDir <> "sensitivity_3d.png", sensitivityPlot3D, ImageResolution -> 300];
Print["  ✓ Sensitivity 3D: ", outputDir, "sensitivity_3d.png"];

(* ============================================ *)
(* 6. Propensity Score 3D Distribution *)
(* ============================================ *)
Print["[6/6] Generating Propensity Score 3D..."];

(* Generate propensity scores *)
SeedRandom[42];
nObs = 500;
treatedScores = RandomVariate[BetaDistribution[5, 2], nObs];
controlScores = RandomVariate[BetaDistribution[2, 5], nObs];

(* 3D histogram *)
propensity3D = Histogram3D[
  {treatedScores, controlScores},
  20,
  ChartStyle -> {
    Directive[Opacity[0.7], RGBColor[0.2, 0.6, 1]],
    Directive[Opacity[0.7], RGBColor[1, 0.4, 0.4]]
  },
  ChartLegends -> {"Treated", "Control"},
  ImageSize -> 800,
  Background -> Black,
  AxesLabel -> {
    Style["Propensity Score", White, 14],
    Style["Group", White, 14],
    Style["Frequency", White, 14]
  },
  AxesStyle -> White,
  PlotLabel -> Style["Propensity Score Overlap (3D)", White, Bold, 18],
  ViewPoint -> {2, -2, 1.5},
  Lighting -> "Neutral"
];

Export[outputDir <> "propensity_3d.png", propensity3D, ImageResolution -> 300];
Print["  ✓ Propensity 3D: ", outputDir, "propensity_3d.png"];

(* ============================================ *)
(* Summary Report *)
(* ============================================ *)
Print["\n=== World-Class Visualizations Complete ==="];
Print["Output directory: ", outputDir];
Print["Generated files:"];
Print["  1. causal_dag_3d.png + animated.gif (3D Interactive DAG)"];
Print["  2. tvce_animated.gif (Time-Varying Effects)"];
Print["  3. cate_surface_3d.png + animated.gif (CATE Heterogeneity)"];
Print["  4. network_diffusion_3d.gif (Network Spillover)"];
Print["  5. sensitivity_3d.png (Rosenbaum Bounds)"];
Print["  6. propensity_3d.png (Propensity Overlap)"];
Print["\nAll visualizations use:"];
Print["  ✓ 3D graphics with rotation"];
Print["  ✓ Animations and dynamic content"];
Print["  ✓ Professional black background"];
Print["  ✓ High resolution (300 DPI)"];
Print["  ✓ Interactive elements"];
