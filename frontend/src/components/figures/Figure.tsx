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
        style={{ width: "100%", height: 380, objectFit: "contain", display: "block",
                 border: "1px dashed #ccc", borderRadius: 8, background: "#fff" }}
      />
    </div>
  );
}

// .html/.htm は <iframe>、それ以外は <img> に自動切替
export function SmartFigure({ title, subtitle, src, alt }: FigureProps) {
  const isHTML = typeof src === "string" && /\.html?(\?|$)/i.test(src);
  return isHTML
    ? <FigureHTML title={title} subtitle={subtitle} src={src} />
    : <FigureImage title={title} subtitle={subtitle} src={src} alt={alt} />;
}

// 後方互換: 既存コードは Figure を使い続ければ○（≒自動切替にスマート化）
export const Figure = SmartFigure;

// HTML(イベントスタディ等)を埋め込み
export function FigureHTML({ title, subtitle, src }: FigureProps) {
  return (
    <div style={{ padding: 12 }}>
      {title && <h4 style={{ margin: 0 }}>{title}</h4>}
      {subtitle && <div style={{ opacity: 0.7, fontSize: 12 }}>{subtitle}</div>}
      <iframe
        src={src}
        style={{ width: "100%", height: 380, border: "1px dashed #ccc",
                 borderRadius: 8, background: "#fff" }}
      />
    </div>
  );
}

// 利便用のデフォルト（破壊的ではない）
export default { FigureImage, FigureHTML, SmartFigure };
