import React from "react";

export type FigureProps = {
  title?: string;
  subtitle?: string;
  src: string;
  alt?: string;
};

// 画像(PNG等)を表示
export function FigureImage({ title, subtitle, src, alt }: FigureProps) {
  return (
    <div style={{ padding: 12 }}>
      {title && <h4 style={{ margin: 0 }}>{title}</h4>}
      {subtitle && <div style={{ opacity: 0.7, fontSize: 12 }}>{subtitle}</div>}
      <img
        src={src}
        alt={alt ?? title ?? src}
        style={{ width: "100%", height: "auto", display: "block",
                 border: "1px dashed #ccc", borderRadius: 8 }}
      />
    </div>
  );
}

// Backward compatibility: export Figure as alias for FigureImage
export const Figure = FigureImage;

// HTML(イベントスタディ等)を埋め込み
export function FigureHTML({ title, subtitle, src }: FigureProps) {
  return (
    <div style={{ padding: 12 }}>
      {title && <h4 style={{ margin: 0 }}>{title}</h4>}
      {subtitle && <div style={{ opacity: 0.7, fontSize: 12 }}>{subtitle}</div>}
      <iframe
        src={src}
        style={{ width: "100%", height: 460, border: "1px dashed #ccc",
                 borderRadius: 8, background: "#fff" }}
      />
    </div>
  );
}

// 利便用のデフォルト（破壊的ではない）
export default { FigureImage, FigureHTML };
