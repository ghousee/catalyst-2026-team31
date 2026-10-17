// Types mirror docs/API_CONTRACT.md (v1 + v2 additions). Field names are exact.

export type Lane = "doc" | "veteran" | "live";

export interface Context {
  system: string; // sub:TMF
  version: string; // rvu:L
  site: string; // node:PROD
  display: string; // "\PROD · L-series · TMF"
  confidence: number;
}

export interface ContextOverride {
  system?: string | null;
  version?: string | null;
  site?: string | null;
}

export interface Claim {
  text: string;
  lane: Lane;
  source_id: string;
  verified: boolean;
  score: number;
}

export interface DocSource {
  id: string;
  kind: "doc";
  title: string;
  part_number?: string;
  section?: string;
  applies_to?: string;
  snippet: string;
}

export interface HeuristicSource {
  id: string;
  kind: "heuristic";
  owner: string;
  owner_name?: string;
  owner_role?: string;
  years?: number;
  captured_via?: string;
  captured_at?: string;
  endorsements?: number;
  last_validated?: string;
  scope?: string;
  why: string;
  provenance?: string; // v1 field
  relation?: string; // e.g. "contradicts:doc:TMF-Reference:ch121.187"
}

export interface LiveSource {
  id: string;
  kind: "live";
  command: string;
  node: string;
  ts: string;
  excerpt: string;
}

export type Source = DocSource | HeuristicSource | LiveSource;

export interface Expert {
  id: string;
  name: string;
  reason: string; // why this person, e.g. "Owns 6 captured TMF patterns for \PROD"
  active: boolean;
  role?: string; // designation, e.g. "Senior NonStop Operator"
  team?: string;
  years?: number;
  expertise?: string[]; // e.g. ["TMF", "Pathway"]
  availability?: "on_shift" | "off_shift" | "on_call" | "retired";
  contact?: string; // how to reach them, e.g. "ext. 4417 · #nonstop-ops"
}

export interface ChatRequest {
  user_id: string;
  question: string;
  context_override?: ContextOverride;
  ablation?: number;
}

export interface ChatAnswer {
  type: "answer";
  answer_log_id: number;
  context: Context;
  claims: Claim[];
  sources: Source[];
  dropped_claims: number;
  experts: Expert[];
}

export interface ClarifyOption {
  label: string;
  value: ContextOverride;
}

export interface ChatClarify {
  type: "clarify";
  question: string;
  options: ClarifyOption[];
}

export interface ChatRefer {
  type: "refer";
  reason: string;
  context: Context;
  experts: Expert[];
}

export type ChatResponse = ChatAnswer | ChatClarify | ChatRefer;

export interface ReferRequest {
  expert_id: string;
  question: string;
  context: Context | null;
  from_user: string;
}
export interface ReferResponse {
  referral_id: string;
  status: string;
}

// --- v2 ---

export interface NodeRef {
  id: string;
  display: string;
}
export interface Session {
  node: string;
  node_display: string;
  series: string;
  user: string;
  nodes_available: NodeRef[];
}

export type Risk = "read_only" | "state_changing" | "critical";
export type ApprovalKind = "one_click" | "type_node" | "second_approver";

export interface Proposal {
  id: string;
  template_id: string;
  command: string;
  node: string;
  risk: Risk;
  explanation: string;
  source_id: string;
  guards: { node_match: boolean; rvu_ok: boolean };
  approval: { required: ApprovalKind };
}

export interface ProposeRequest {
  question: string;
  context: { system: string; site: string; version: string };
}
export interface ProposeResponse {
  proposals: Proposal[];
  no_template: boolean;
}

export interface BlastRadiusItem {
  entity: string;
  effect: string;
}
export interface DryRun {
  id: string;
  expected_output: string;
  blast_radius: BlastRadiusItem[];
  warnings: string[];
}

export interface ApproveRequest {
  user_id: string;
  typed_node: string | null;
  second_approver: string | null;
}
export interface ApproveResponse {
  status: "approved" | "needs_second_approver" | "rejected";
  reason: string;
}

export interface ExecuteResponse {
  run_id: string;
  output: string;
  ts: string;
  source_id: string;
}

export type Severity = "info" | "warning" | "critical";

export interface Alert {
  id: string;
  ts: string;
  node: string;
  subsystem: string;
  pattern_id: string;
  owner: string;
  owner_name: string;
  severity: Severity;
  lead_time_min: number;
  message: string;
  evidence: Array<{ event?: string; count?: number; metric?: string; value?: number; trend?: string }>;
  fix_claims: Claim[];
  next_commands: Proposal[];
  backtest: { hits: number; of: number; avg_lead_min: number };
  backup_expert: Pick<Expert, "id" | "name"> & Partial<Expert>;
}

export interface MetricSeries {
  metric: string;
  points: Array<[string, number]>;
}
export interface MetricsResponse {
  series: MetricSeries[];
}

export type ScenarioName = "audit_trail_fill" | "disk_revive_stall" | "pathway_no_server" | "cpu_down";
export interface ScenarioRequest {
  scenario: ScenarioName;
  speed: number;
}
