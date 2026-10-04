// The data contract between the judge and this template. It mirrors what
// strategies/resonance/flow.py writes (FLOW_SCHEMA); change the two together.
// 判断层与本模板之间的数据约定，与 strategies/resonance/flow.py 的输出（FLOW_SCHEMA）一一对应，须同步修改。

export const FLOW_SCHEMA = 1;

export type Side = "long" | "short";
/** Who is speaking in a call: a debating side, the moderator or the manager. */
export type Role = Side | "mod" | "mgr";
export type StepKind = "thesis" | "rebuttal" | "defence" | "moderator" | "manager";

/** One top-level section of a recorded prompt. */
export interface PromptBlock {
  label: string;
  note: string;
  chars: number;
}

/** One thing a call returned: a point, a rebuttal, a reply, a ruling. */
export interface StepItem {
  id: string;
  tag: string;
  text: string;
}

/** One model call. Timing, cost and prompt fields are null when its record is not on disk. */
export interface FlowStep {
  id: string;
  role: Role;
  kind: StepKind;
  /** 0 for the opening statements and the manager. */
  round: number;
  phase: string;
  label: string;
  template: string;
  job: string;
  start: string | null;
  end: string | null;
  /** Seconds from the first call's start. */
  t0: number | null;
  t1: number | null;
  seconds: number | null;
  cost: number | null;
  attempts: number | null;
  promptChars: number | null;
  blocks: PromptBlock[];
  result: string;
  items: StepItem[];
  /** What the code did after this call and before the next; empty when nothing. */
  glue: string;
}

export interface FlowExchange {
  round: number;
  speaker: Side;
  kind: string;
  unanswered: boolean;
  tag: string;
  text: string;
  revised: string;
  refs: string[];
}

export interface FlowThread {
  id: string;
  owner: Side;
  strength: string;
  status: string;
  claim: string;
  reasoning: string;
  refs: string[];
  verdict: string | null;
  verdictReason: string;
  exchanges: FlowExchange[];
}

export interface FlowRuling {
  round: number;
  by: "moderator" | "rule";
  continue: boolean;
  reason: string;
  focus: string[];
}

export interface FlowDecision {
  direction: "long" | "short" | "uncertain";
  confidence: number;
  quality: string;
  reversal: boolean | null;
  uncertainIsHighConfidence: boolean;
  summary: string;
  reasoning: string;
  drivers: string[];
  risks: string[];
}

export interface FlowThesis {
  thesis: string;
  confidence: number;
  falsifiers: string[];
}

/** runs/<packDate>/<symbol>/flow.json */
export interface FlowData {
  schema: number;
  symbol: string;
  name: string;
  packDate: string;
  lastSession: string;
  config: { model: string | null; effort: string | null; maxRounds: number | null };
  position: { direction: Side; volume: number } | null;
  decision: FlowDecision;
  rounds: number;
  rulings: FlowRuling[];
  cost: number;
  /** Seconds from the first call's start to the last call's end. */
  wall: number | null;
  /** Second of the day at which the first call started (run machine's local time). */
  clock0: number | null;
  steps: FlowStep[];
  threads: FlowThread[];
  theses: Partial<Record<Side, FlowThesis>>;
  cacheFile: string;
}

export interface FlowIndexSymbol {
  symbol: string;
  name: string;
  direction: string;
  confidence: number;
  rounds: number;
  cost: number | null;
}

/** runs/index.json */
export interface FlowIndex {
  schema: number;
  runs: { packDate: string; symbols: FlowIndexSymbol[] }[];
}
