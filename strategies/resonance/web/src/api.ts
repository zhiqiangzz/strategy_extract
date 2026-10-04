import type { FlowData, FlowIndex } from "./types";

// Where the flow files are served. Standalone: `cli web` serves them at ./runs/
// next to the built page. Inside another frontend, set VITE_FLOW_BASE to that
// app's endpoint (e.g. "/api/resonance/runs").
const BASE = ((import.meta.env.VITE_FLOW_BASE as string | undefined) ?? "runs").replace(/\/$/, "");

async function getJson<T>(url: string): Promise<T> {
  const res = await fetch(url, { cache: "no-store" });
  if (!res.ok) {
    throw new Error(`${url}: HTTP ${res.status}`);
  }
  return (await res.json()) as T;
}

// Pack dates and symbols that have a flow, newest first.
export async function fetchIndex(): Promise<FlowIndex> {
  return getJson<FlowIndex>(`${BASE}/index.json`);
}

export async function fetchFlow(packDate: string, symbol: string): Promise<FlowData> {
  return getJson<FlowData>(`${BASE}/${packDate}/${symbol}/flow.json`);
}
