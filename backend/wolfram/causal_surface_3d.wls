#!/usr/bin/env wolframscript
(* 3D Causal Effect Surface - World-Class Visualization *)

(* Sample data: Treatment effect varying by two covariates *)
data = Flatten[Table[{x, y,
   2 + 0.5*x - 0.3*y + 0.1*x*y + RandomReal[{-0.3, 0.3}]},
   {x, 0, 10, 0.5}, {y, 0, 10, 0.5}], 1];

(* Create interpolation function *)
f = Interpolation[data];

(* Create stunning 3D surface plot *)
plot = Plot3D[f[x, y], {x, 0, 10}, {y, 0, 10},
  PlotStyle -> Directive[Specularity[White, 30], Opacity[0.9]],
  ColorFunction -> "TemperatureMap",
  ColorFunctionScaling -> True,
  Mesh -> 15,
  MeshStyle -> Directive[Gray, Opacity[0.3]],
  Lighting -> {{"Ambient", White},
    {"Directional", RGBColor[1, 0.8, 0.6], ImageScaled[{2, 0, 2}]},
    {"Directional", RGBColor[0.6, 0.8, 1], ImageScaled[{-2, -2, 2}]}},
  PlotRange -> All,
  BoxRatios -> {1, 1, 0.6},
  AxesLabel -> {Style["Covariate X₁", 16, Bold],
                Style["Covariate X₂", 16, Bold],
                Style["Treatment Effect τ", 16, Bold]},
  PlotLabel -> Style["3D Causal Effect Surface\nHeterogeneous Treatment Effects", 18, Bold],
  ImageSize -> 1200,
  ViewPoint -> {1.8, -2.5, 1.2},
  Background -> GrayLevel[0.95]
];

(* Add contour projection at bottom *)
contours = ContourPlot[f[x, y], {x, 0, 10}, {y, 0, 10},
  Contours -> 10,
  ColorFunction -> "TemperatureMap",
  ContourStyle -> Directive[Thickness[0.002], Opacity[0.6]],
  ImageSize -> 400
];

(* Combine into final visualization *)
final = GraphicsRow[{plot, contours},
  ImageSize -> 1600,
  PlotLabel -> Style["CQOx: Advanced Causal Inference Visualization", 20, Bold, FontFamily -> "Helvetica"]
];

(* Export as high-quality PNG *)
Export["reports/wolfram_causal_surface_3d.png", final,
  ImageResolution -> 300, Background -> White];

Print["✅ 3D Causal Surface exported to reports/wolfram_causal_surface_3d.png"];
