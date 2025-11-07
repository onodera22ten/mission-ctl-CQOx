// frontend/src/lib/domains.ts

export type DomainViz = { key: string; title: string };
export type DomainConfig = {
  required_columns?: string[];
  optional_columns?: string[];
  visualizations?: DomainViz[];
  rename?: Record<string, string>;
};

export async function fetchDomainConfig(name: string): Promise<DomainConfig> {
  const res = await fetch(`/api/domains/${encodeURIComponent(name)}`);
  if (!res.ok) {
    throw new Error(await res.text());
  }
  return res.json();
}

/** 任意：ドメイン一覧が必要な場合に利用 */
export async function fetchDomains(): Promise<string[]> {
  const r = await fetch("/api/domains");
  if (!r.ok) throw new Error(await r.text());
  const j = await r.json();
  return j?.domains ?? [];
}

