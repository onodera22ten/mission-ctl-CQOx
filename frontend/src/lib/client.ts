// frontend/src/lib/client.ts
/**
 * 正しいAPI呼び出し（GET /roles/profile, mappingは連想形式）
 */
import axios from "axios";

const api = axios.create({
  baseURL: "/api",
  timeout: 60000,
});

// 1) アップロード
export async function uploadFile(file: File) {
  const fd = new FormData();
  fd.append("file", file);
  const { data } = await api.post("/upload", fd);
  return data as {
    ok: boolean;
    dataset_id: string;
    meta: { columns: string[]; dtypes: Record<string, string>; preview: any[] };
    candidates: Record<string, string[]>;
    stats: Array<{ column: string; dtype: string; na: number }>;
  };
}

// 2) ロールプロファイル（GET）
export async function fetchRolesProfile(dataset_id: string) {
  const { data } = await api.get("/roles/profile", { params: { dataset_id } });
  return data as {
    ok: boolean;
    dataset_id: string;
    meta: { columns: string[]; dtypes: Record<string, string>; preview: any[] };
    candidates: Record<string, string[]>;
  };
}

// 2b) 自動ロール推論（Phase 3 新機能）
export async function inferRoles(dataset_id: string, min_confidence = 0.3) {
  const { data } = await api.post("/roles/infer", { dataset_id, min_confidence });
  return data as {
    ok: boolean;
    mapping: Record<string, string>;
    candidates: Record<string, Array<{ column: string; confidence: number; reasons: string[] }>>;
    required_missing: string[];
    confidence: number;
    objective: {
      objective: string;
      confidence: number;
      scores: Record<string, number>;
      evidence: string[];
    };
  };
}

// 3) 総合分析（mappingは {role: column} で渡す）
export async function analyzeComprehensive(args: {
  dataset_id?: string;
  df_path?: string;
  mapping: Record<string, string>;
  preview?: boolean;
  domain?: string;
  cfg_json?: Record<string, any> | string;
}) {
  const payload = { ...args };
  const { data } = await api.post("/analyze/comprehensive", payload);
  return data;
}

export async function compareObjectives(job_ids: string[]) {
  const { data } = await api.get("/compare/objectives", {
    params: { job_ids: job_ids.join(",") },
  });
  return data as {
    ok: boolean;
    comparison_results: any[];
    radar_chart_data: {
      labels: string[];
      datasets: {
        label: string;
        data: number[];
      }[];
    };
  };
}

// デバッグ用スモーク
export async function testAPI(file: File) {
  const up = await uploadFile(file);
  const prof = await fetchRolesProfile(up.dataset_id);
  // 雑に推定（候補が無ければ最初の列を入れる）
  const pick = (k: string, fallback: string) =>
    prof.candidates?.[k]?.[0] ?? fallback;
  const mapping = {
    y: pick("y", prof.meta.columns[0]),
    treatment: pick("treatment", prof.meta.columns[1]),
    unit_id: pick("unit_id", prof.meta.columns[2]),
    time: prof.candidates?.time?.[0],
  } as Record<string, string>;
  return analyzeComprehensive({
    dataset_id: up.dataset_id,
    mapping,
    preview: true,
  });
}

export default api;

