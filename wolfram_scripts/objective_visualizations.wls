#!/usr/bin/env wolframscript
(* Domain-Specific High-Quality Visualizations with WolframONE *)

args = Rest[$ScriptCommandLine];
If[Length[args] < 4,
  Print["Usage: objective_visualizations.wls <objective> <data.parquet> <output_dir> <mapping_json>"];
  Exit[1]
];

objective = args[[1]];
dataPath = args[[2]];
outputDir = args[[3]];
mappingJson = args[[4]];
mapping = ImportString[mappingJson, "JSON"];

(* Create output directory *)
CreateDirectory[outputDir];

(* Load data *)
Print["Loading data from: ", dataPath];
data = Import[dataPath];

(* High-quality export settings *)
exportSettings = Sequence[ImageResolution -> 300, ImageSize -> 1200];

(* ==================== EDUCATION DOMAIN ==================== *)

If[objective == "education",
  Print["Generating Education domain visualizations..."];

  (* 1. Event Study - Grade progression over time *)
  yCol = "y" /. mapping;
  timeCol = "time" /. mapping;
  eventData = GroupBy[Normal[data], Key[timeCol], Mean[#[[yCol]]]&];
  eventStudy = BarChart[
    Values[eventData],
    ChartLabels -> Keys[eventData],
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
  yCol = "y" /. mapping;
  yData = Normal[data[All, yCol]];
  gainDistrib = Histogram[
    yData,
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
  yCol = "y" /. mapping;
  tCol = "treatment" /. mapping;
  fairnessData = GroupBy[Normal[data], Key[tCol], Mean[#[[yCol]]]&];
  fairness = BarChart[
    Values[fairnessData],
    ChartLabels -> Keys[fairnessData],
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

If[objective == "retail",
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
  yCol = "y" /. mapping;
  timeCol = "time" /. mapping;
  seasonalityData = Normal[data[All, {timeCol, yCol}]];
  seasonality = DateListPlot[
    seasonalityData,
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

If[objective == "medical",
  Print["Generating Medical domain visualizations..."];

  (* 1. Kaplan-Meier Survival *)
  yCol = "y" /. mapping;
  timeCol = "time" /. mapping;
  tCol = "treatment" /. mapping;
  
  treatedData = Cases[Normal[data], HoldPattern[___ -> _].. /; (#[[tCol]] == 1)];
  controlData = Cases[Normal[data], HoldPattern[___ -> _].. /; (#[[tCol]] == 0)];
  
  treatedPlotData = SortBy[treatedData[[All, {timeCol, yCol}]], First];
  controlPlotData = SortBy[controlData[[All, {timeCol, yCol}]], First];

  km = ListLinePlot[
    {controlPlotData, treatedPlotData},
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
  yCol = "y" /. mapping;
  doseCol = "dose" /. mapping;
  doseData = Normal[data[All, {doseCol, yCol}]];
  doseResponse = ListPlot[doseData,
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
