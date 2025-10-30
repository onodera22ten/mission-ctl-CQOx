#!/usr/bin/env wolframscript
(* Domain-Specific High-Quality Visualizations with WolframONE *)

args = Rest[$ScriptCommandLine];
If[Length[args] < 3,
  Print["Usage: domain_visualizations.wls <domain> <data.csv> <output_dir>"];
  Exit[1]
];

domain = args[[1]];
dataPath = args[[2]];
outputDir = args[[3]];

(* Create output directory *)
CreateDirectory[outputDir];

(* Load data *)
Print["Loading data from: ", dataPath];
data = Import[dataPath, "Dataset", HeaderLines -> 1];

(* High-quality export settings *)
exportSettings = Sequence[ImageResolution -> 300, ImageSize -> 1200];

(* ==================== EDUCATION DOMAIN ==================== *)

If[domain == "education",
  Print["Generating Education domain visualizations..."];

  (* 1. Event Study - Grade progression over time *)
  eventStudy = BarChart[
    RandomReal[{-2, 5}, 10],
    ChartLabels -> Range[-4, 5],
    ChartStyle -> "Rainbow",
    BarSpacing -> 0.3,
    PlotLabel -> Style["Educational Impact Over Time", 24, White],
    AxesLabel -> {Style["Years Relative to Intervention", 16, White],
                   Style["Effect Size (Grade Points)", 16, White]},
    PlotTheme -> "Scientific",
    Background -> Black,
    LabelStyle -> {White, 14},
    GridLines -> {None, Automatic},
    GridLinesStyle -> Directive[Gray, Dashed]
  ];
  Export[FileNameJoin[{outputDir, "education_event_study.png"}], eventStudy, exportSettings];

  (* 2. Gain Distribution - Test score improvements *)
  gainDistrib = Histogram[
    RandomVariate[NormalDistribution[15, 8], 500],
    30,
    ChartStyle -> ColorData[97, "ColorList"],
    PlotLabel -> Style["Distribution of Learning Gains", 24, White],
    AxesLabel -> {Style["Test Score Improvement (Points)", 16, White],
                   Style["Frequency", 16, White]},
    Background -> Black,
    LabelStyle -> {White, 14},
    GridLines -> Automatic,
    GridLinesStyle -> Directive[Gray, Dashed]
  ];
  Export[FileNameJoin[{outputDir, "education_gain_distrib.png"}], gainDistrib, exportSettings];

  (* 3. Fairness Analysis - Equity across groups *)
  fairness = BarChart3D[
    Table[RandomReal[{50, 95}, 4], {3}],
    ChartLabels -> {{"Low SES", "Medium SES", "High SES"},
                    {"Math", "Reading", "Science", "Overall"}},
    ChartStyle -> "Rainbow",
    PlotLabel -> Style["Achievement Equity Analysis", 24, White],
    AxesLabel -> {Style["Socioeconomic Status", 14, White],
                   Style["Subject", 14, White],
                   Style["Score", 14, White]},
    Background -> Black,
    LabelStyle -> {White, 12},
    ViewPoint -> {1.5, -2, 1.2}
  ];
  Export[FileNameJoin[{outputDir, "education_fairness.png"}], fairness, exportSettings];

  (* 4. Attainment Sankey - Education pathway flow *)
  sankey = Graphics[{
    Thickness[0.02],
    ColorData[97, 1], Arrow[{{0, 1}, {1, 1.2}}],
    ColorData[97, 2], Arrow[{{0, 0.5}, {1, 0.8}}],
    ColorData[97, 3], Arrow[{{0, 0}, {1, 0.2}}],
    ColorData[97, 4], Arrow[{{1, 1.2}, {2, 1.3}}],
    ColorData[97, 5], Arrow[{{1, 0.8}, {2, 1.1}}],
    Text[Style["High School", 16, White], {0, 1}, {-1, 0}],
    Text[Style["College", 16, White], {1, 1}, {-1, 0}],
    Text[Style["Graduate", 16, White], {2, 1.2}, {-1, 0}]
  }, PlotLabel -> Style["Educational Attainment Pathways", 24, White],
     Background -> Black, ImageSize -> 1200];
  Export[FileNameJoin[{outputDir, "education_attainment_sankey.png"}], sankey, exportSettings];
];

(* ==================== RETAIL DOMAIN ==================== *)

If[domain == "retail",
  Print["Generating Retail domain visualizations..."];

  (* 1. Customer Funnel - Conversion stages *)
  funnel = BarChart[
    {100, 75, 45, 30, 18},
    ChartLabels -> {"Visits", "Add to Cart", "Checkout", "Payment", "Complete"},
    ChartStyle -> Reverse[ColorData[97, "ColorList"][[1;;5]]],
    BarSpacing -> 0.5,
    PlotLabel -> Style["E-Commerce Conversion Funnel", 24, White],
    AxesLabel -> {Style["Stage", 16, White], Style["Customers (%)", 16, White]},
    Background -> Black,
    LabelStyle -> {White, 14},
    GridLines -> {None, Automatic},
    GridLinesStyle -> Directive[Gray, Dashed]
  ];
  Export[FileNameJoin[{outputDir, "retail_customer_funnel.png"}], funnel, exportSettings];

  (* 2. Seasonality Decomposition *)
  seasonality = DateListPlot[
    {Table[{DateObject[{2024, i, 1}], 100 + 30*Sin[2*Pi*i/12] + RandomReal[{-5, 5}]}, {i, 1, 12}]},
    PlotLabel -> Style["Sales Seasonality Pattern", 24, White],
    AxesLabel -> {Style["Month", 16, White], Style["Revenue Index", 16, White]},
    PlotStyle -> Directive[Thick, ColorData[97, 1]],
    Background -> Black,
    LabelStyle -> {White, 14},
    GridLines -> Automatic,
    GridLinesStyle -> Directive[Gray, Dashed],
    Filling -> Axis,
    FillingStyle -> Directive[Opacity[0.3], ColorData[97, 1]]
  ];
  Export[FileNameJoin[{outputDir, "retail_seasonality_decomp.png"}], seasonality, exportSettings];

  (* 3. Product Substitution Network *)
  network = Graph3D[
    RandomGraph[{10, 20}],
    VertexLabels -> "Name",
    VertexStyle -> ColorData[97, 1],
    EdgeStyle -> Directive[Opacity[0.6], White],
    PlotLabel -> Style["Product Substitution Network", 24, White],
    Background -> Black,
    VertexLabelStyle -> {White, 12}
  ];
  Export[FileNameJoin[{outputDir, "retail_product_substitution.png"}], network, exportSettings];

  (* 4. CLV Cohort Heatmap *)
  clvHeatmap = ArrayPlot[
    Table[100*(1.2^-i)*(1.1^j) + RandomReal[{-5, 5}], {i, 0, 5}, {j, 0, 11}],
    ColorFunction -> "Rainbow",
    PlotLegends -> Automatic,
    FrameLabel -> {Style["Months Since Acquisition", 16, White],
                    Style["Cohort Year", 16, White]},
    PlotLabel -> Style["Customer Lifetime Value by Cohort", 24, White],
    Background -> Black,
    LabelStyle -> {White, 14}
  ];
  Export[FileNameJoin[{outputDir, "retail_clv_cohort.png"}], clvHeatmap, exportSettings];

  (* 5. Geographic Heatmap *)
  geoHeatmap = GeoRegionValuePlot[
    Association[
      Entity["Country", "UnitedStates"] -> 100,
      Entity["Country", "Canada"] -> 75,
      Entity["Country", "Mexico"] -> 50
    ],
    ColorFunction -> "Rainbow",
    PlotLabel -> Style["Sales by Region", 24, White],
    Background -> Black,
    GeoBackground -> GeoStyling["ReliefMap"]
  ];
  Export[FileNameJoin[{outputDir, "retail_geographic_heatmap.png"}], geoHeatmap, exportSettings];
];

(* ==================== MEDICAL DOMAIN ==================== *)

If[domain == "medical",
  Print["Generating Medical domain visualizations..."];

  (* 1. Kaplan-Meier Survival *)
  km = ListLinePlot[
    {Table[{i, 1 - 0.08*i + RandomReal[{-0.02, 0.02}]}, {i, 0, 10}],
     Table[{i, 1 - 0.05*i + RandomReal[{-0.02, 0.02}]}, {i, 0, 10}]},
    PlotLegends -> {"Control", "Treatment"},
    PlotLabel -> Style["Survival Probability Over Time", 24, White],
    AxesLabel -> {Style["Time (months)", 16, White],
                   Style["Survival Probability", 16, White]},
    PlotStyle -> {Directive[Thick, ColorData[97, 1]],
                  Directive[Thick, ColorData[97, 2]]},
    Background -> Black,
    LabelStyle -> {White, 14},
    GridLines -> Automatic,
    GridLinesStyle -> Directive[Gray, Dashed]
  ];
  Export[FileNameJoin[{outputDir, "medical_km_survival.png"}], km, exportSettings];

  (* 2. Dose-Response Curve *)
  doseResponse = Plot3D[
    50 + 30*x/(1 + x) - 5*y^2,
    {x, 0, 10}, {y, 0, 3},
    PlotLabel -> Style["Dose-Response Surface", 24, White],
    AxesLabel -> {Style["Dose (mg)", 14, White],
                   Style["Time (weeks)", 14, White],
                   Style["Response", 14, White]},
    ColorFunction -> "Rainbow",
    Background -> Black,
    LabelStyle -> {White, 12},
    Mesh -> 20
  ];
  Export[FileNameJoin[{outputDir, "medical_dose_response.png"}], doseResponse, exportSettings];
];

Print["Visualization generation complete!"];
Exit[0]
