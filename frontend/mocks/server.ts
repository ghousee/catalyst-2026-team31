// In-browser mock of the FastAPI backend. Scripts the SYSTEM_DESIGN §11 hero demo.
// Request/response shapes follow docs/API_CONTRACT.md v2 exactly.
import type {
  Alert,
  ApproveRequest,
  ApproveResponse,
  ChatRequest,
  ChatResponse,
  Claim,
  Context,
  DryRun,
  ExecuteResponse,
  Expert,
  LiveSource,
  MetricsResponse,
  Proposal,
  ProposeRequest,
  ProposeResponse,
  ReferRequest,
  ReferResponse,
  ScenarioRequest,
  Session,
  Source,
} from "@/lib/types";
import {
  CATALOG,
  CatalogEntry,
  E_LENA,
  E_MARIA,
  E_RAJ,
  NODES,
  SUBSYSTEMS,
  claim,
  sourceById,
} from "./fixtures";

interface Run {
  run_id: string;
  cmdId: string;
  node: string;
  ts: string;
  output: string;
}

const DEMO_BASE = Date.parse("2026-10-17T02:14:05Z");
const START = Date.now();

const state = {
  node: "node:PROD",
  scenarioAt: null as number | null,
  runs: [] as Run[],
  approved: new Set<string>(),
  proposedNode: {} as Record<string, string>,
  runCounter: 42,
  answerCounter: 100,
  referralCounter: 87,
};

const sleep = (ms: number) => new Promise((r) => setTimeout(r, ms));
const lag = () => sleep(120 + Math.random() * 180);
const demoNow = () => new Date(DEMO_BASE + (Date.now() - START)).toISOString().replace(/\.\d+Z$/, "Z");
const nodeDisplay = (id: string) => NODES.find((n) => n.id === id)?.display ?? id;
const lastRun = () => state.runs[state.runs.length - 1];

const EXCERPTS: Record<string, string> = {
  "cmd-17": "Active audit trail capacity used: 71%",
  "cmd-18": "Oldest active transid \\PROD(1).3.45678  ACTIVE  03:27  (SETTLE-SC batch)",
  "cmd-19": "Transaction \\PROD(1).3.45678 aborted. Audit trail capacity used: 38%",
  "cmd-20": "17 path errors on mirror path in 24h; Revive NONE",
  "cmd-21": "SETTLE-SC  RUNNING 2  PENDING 4  MAX 2",
  "cmd-22": "CPU 2  Busy: 58%  Ready queue: 3",
  "cmd-23": "TMF STARTED, BEGINTRANS ENABLED, 3 active transactions",
  "cmd-24": "$Z0A1 TERM $TERM01 RUNNING",
};

function context(system: string, siteId: string, version: string): Context {
  const sub = SUBSYSTEMS[system] ?? "TMF";
  return {
    system,
    version,
    site: siteId,
    display: `${nodeDisplay(siteId)} · ${version.replace("rvu:", "")}-series · ${sub}`,
    confidence: 0.94,
  };
}

function liveSource(run: Run): LiveSource {
  return {
    id: run.run_id,
    kind: "live",
    command: CATALOG[run.cmdId].command,
    node: nodeDisplay(run.node),
    ts: run.ts,
    excerpt: EXCERPTS[run.cmdId],
  };
}

function collectSources(claims: Claim[]): Source[] {
  const out: Source[] = [];
  for (const c of claims) {
    const run = state.runs.find((r) => r.run_id === c.source_id);
    const s = run ? liveSource(run) : sourceById(c.source_id);
    if (s && !out.some((o) => o.id === s.id)) out.push(s);
    // include the doc a veteran claim relates to, so the "relation" is inspectable
    if (s && s.kind === "heuristic" && s.relation) {
      const rel = s.relation.split(/^[a-z]+:/)[1];
      const relSrc = rel ? sourceById(rel) : undefined;
      if (relSrc && !out.some((o) => o.id === relSrc.id)) out.push(relSrc);
    }
  }
  return out;
}

function answer(ctx: Context, claims: Claim[], experts: Expert[], dropped = 0): ChatResponse {
  return {
    type: "answer",
    answer_log_id: state.answerCounter++,
    context: ctx,
    claims,
    sources: collectSources(claims),
    dropped_claims: dropped,
    experts,
  };
}

type Topic = "audit" | "disk" | "pathway" | "cpu" | "tmf" | "tacl" | "unknown";
function topicOf(q: string): Topic {
  const s = q.toLowerCase();
  if (/audit|pinn|filling|fill/.test(s)) return "audit";
  if (/disk|\$data|volume/.test(s)) return "disk";
  if (/pathway|server class|no server/.test(s)) return "pathway";
  if (/cpu|processor/.test(s)) return "cpu";
  if (/tmf|transaction|begintrans/.test(s)) return "tmf";
  if (/terminal|tacl|session/.test(s)) return "tacl";
  return "unknown";
}

function chat(req: ChatRequest): ChatResponse {
  const ov = req.context_override ?? {};
  const siteId = ov.site ?? state.node;
  const version = ov.version ?? "rvu:L";
  const prod = siteId === "node:PROD";
  let topic = topicOf(req.question);

  if (topic === "disk" && !ov.system) {
    return {
      type: "clarify",
      question: "Which disk do you mean — a data volume (SCF Storage) or the TMF audit trail disks?",
      options: [
        { label: "Data volume · Storage", value: { system: "sub:STORAGE", version, site: siteId } },
        { label: "Audit trail disks · TMF", value: { system: "sub:TMF", version, site: siteId } },
      ],
    };
  }
  if (topic === "disk" && ov.system === "sub:TMF") topic = "audit";

  if (topic === "audit") {
    const ctx = context("sub:TMF", siteId, version);
    const claims: Claim[] = [
      claim(
        "TMF event 185 means an audit trail file is pinned: a transaction that wrote to it is still active, so the file cannot be released.",
        "doc",
        "doc:TMF-Reference:ch121.185",
        0.97,
      ),
    ];
    if (prod) {
      claims.push(
        claim(
          "On \\PROD at quarter-end the nightly settlement batch holds one transaction open for hours; check STATUS TRANSACTION for it before adding overflow volumes.",
          "veteran",
          "maria:h7",
          0.94,
        ),
        claim(
          "Do not wait for it to drain: the batch will not finish before the trail fills (TMF 187), so plan to abort the stale transaction.",
          "veteran",
          "maria:h11",
          0.88,
        ),
      );
      const r = state.runs.find((x) => x.cmdId === "cmd-17" && x.node === siteId);
      if (r) claims.push(claim(`${EXCERPTS["cmd-17"]} (observed ${r.ts.slice(11, 16)}Z).`, "live", r.run_id, 0.99));
      return answer(ctx, claims, [E_MARIA, E_RAJ], 1);
    }
    claims.push(
      claim(
        "When the trail is critically full (TMF 187) TMF disables BEGINTRANS; long-running transactions should be allowed to complete or be resolved by the operator.",
        "doc",
        "doc:TMF-Reference:ch121.187",
        0.95,
      ),
    );
    return answer(ctx, claims, [E_RAJ], 0);
  }

  if (topic === "disk") {
    const ctx = context("sub:STORAGE", siteId, version);
    const claims = [
      claim(
        "STATUS DISK, DETAIL shows primary and mirror drive state, path state and revive status for a volume.",
        "doc",
        "doc:SCF-Storage:ch6.status-disk",
        0.96,
      ),
    ];
    if (prod)
      claims.push(
        claim(
          "A disk that flaps between UP and HARDDOWN after path errors is almost always the cable or CLIM, not the drive.",
          "veteran",
          "lena:h4",
          0.9,
        ),
      );
    return answer(ctx, claims, [E_LENA]);
  }
  if (topic === "pathway") {
    const claims = [
      claim("STATUS SERVER * lists every server class with running, pending and maximum process counts.", "doc", "doc:Pathway-Ref:ch5.status-server"),
    ];
    if (prod) claims.push(claim("SETTLE-SC is the only server class that holds long transactions; others never do.", "veteran", "raj:h3", 0.9));
    return answer(context("sub:PATHWAY", siteId, version), claims, [E_RAJ]);
  }
  if (topic === "cpu")
    return answer(
      context("sub:CPU", siteId, version),
      [claim("PEEK /CPU n/ displays busy time and queue lengths for the named processor.", "doc", "doc:PEEK-Ref:ch2.cpu")],
      [E_RAJ],
    );
  if (topic === "tmf")
    return answer(
      context("sub:TMF", siteId, version),
      [claim("STATUS TMF reports TMF state, BEGINTRANS enablement and the active transaction count.", "doc", "doc:TMF-Reference:ch4.status-tmf")],
      [E_RAJ],
    );
  if (topic === "tacl")
    return answer(
      context("sub:TACL", siteId, version),
      [claim("STATUS *, TERM lists the terminal and process state of every process this TACL can see.", "doc", "doc:TACL-Ref:ch9.status")],
      [E_RAJ],
    );

  return {
    type: "refer",
    reason: `No verified answer for ${nodeDisplay(siteId)} · ${version.replace("rvu:", "")}-series. Nothing in the manuals or captured veteran knowledge covers this.`,
    context: context("sub:TMF", siteId, version),
    experts: [E_RAJ, E_MARIA],
  };
}

function toProposal(e: CatalogEntry, nodeId: string): Proposal {
  state.proposedNode[e.id] = nodeId;
  return {
    id: e.id,
    template_id: e.template_id,
    command: e.command,
    node: nodeDisplay(nodeId),
    risk: e.risk,
    explanation: e.explanation,
    source_id: e.source_id,
    guards: { node_match: nodeId === state.node, rvu_ok: true },
    approval: { required: e.approval },
  };
}

function propose(req: ProposeRequest): ProposeResponse {
  const nodeId = req.context.site || state.node;
  const prod = nodeId === "node:PROD";
  const q = req.question.toLowerCase();
  let ids: string[] = [];
  if (/what next|next step/.test(q)) {
    const r = lastRun();
    if (r?.cmdId === "cmd-17") ids = ["cmd-18"];
    else if (r?.cmdId === "cmd-18" && prod) ids = ["cmd-19"];
    else if (r?.cmdId === "cmd-19") ids = ["cmd-23"];
  } else {
    const t = topicOf(req.question);
    const byTopic: Record<Topic, string[]> = {
      audit: ["cmd-17"],
      disk: req.context.system === "sub:STORAGE" ? ["cmd-20"] : req.context.system === "sub:TMF" ? ["cmd-17"] : [],
      pathway: ["cmd-21"],
      cpu: ["cmd-22"],
      tmf: ["cmd-23"],
      tacl: ["cmd-24"],
      unknown: [],
    };
    ids = byTopic[t];
  }
  return { proposals: ids.map((id) => toProposal(CATALOG[id], nodeId)), no_template: ids.length === 0 };
}

function dryrun(id: string): DryRun {
  const e = CATALOG[id];
  if (!e) throw new Error(`Unknown command ${id}`);
  return { id, ...e.dryrun };
}

function approve(id: string, body: ApproveRequest): ApproveResponse {
  const e = CATALOG[id];
  if (!e) throw new Error(`Unknown command ${id}`);
  const target = state.proposedNode[id];
  if (target && target !== state.node)
    return {
      status: "rejected",
      reason: `Node guard: proposal targets ${nodeDisplay(target)} but the session is on ${nodeDisplay(state.node)}. Re-ask on the current node.`,
    };
  if (e.approval === "type_node" && body.typed_node !== nodeDisplay(state.node))
    return { status: "rejected", reason: "Typed node does not match the target node." };
  if (e.approval === "second_approver" && !body.second_approver)
    return { status: "needs_second_approver", reason: "Critical command: a second approver (on-call veteran) must confirm." };
  state.approved.add(id);
  return { status: "approved", reason: "" };
}

function execute(id: string): ExecuteResponse {
  const e = CATALOG[id];
  if (!e) throw new Error(`Unknown command ${id}`);
  if (!state.approved.has(id)) throw new Error("Command has not been approved");
  const node = state.proposedNode[id] ?? state.node;
  const run: Run = {
    run_id: `run:c${state.runCounter++}`,
    cmdId: id,
    node,
    ts: demoNow(),
    output: e.output(nodeDisplay(node)),
  };
  state.runs.push(run);
  state.approved.delete(id); // approval is single-use
  return { run_id: run.run_id, output: run.output, ts: run.ts, source_id: run.run_id };
}

function scenarioSeconds(): number {
  return state.scenarioAt === null ? 0 : (Date.now() - state.scenarioAt) / 1000;
}
function auditNow(): number {
  return Math.min(78, 62 + Math.floor(scenarioSeconds() * 0.15));
}

function alerts(): Alert[] {
  const live = state.scenarioAt !== null || Date.now() - START > 5000;
  if (state.node !== "node:PROD" || !live) return [];
  return [
    {
      id: "al-7",
      ts: "2026-10-17T02:10:00Z",
      node: "\\PROD",
      subsystem: "TMF",
      pattern_id: "maria:h7",
      owner: "maria",
      owner_name: "Maria Rossi",
      severity: "warning",
      lead_time_min: 40,
      message: "Audit trail on track to fill in ~40 min — Maria's quarter-end pattern",
      evidence: [
        { event: "TMF 185", count: 2 },
        { metric: "audit-capacity-pct", value: auditNow(), trend: "rising" },
      ],
      fix_claims: [
        claim("Check STATUS TRANSACTION for the nightly settlement batch before adding overflow volumes.", "veteran", "maria:h7", 0.94),
        claim("TMF 185 means an audit file is pinned by a still-active transaction.", "doc", "doc:TMF-Reference:ch121.185", 0.97),
      ],
      next_commands: [toProposal(CATALOG["cmd-17"], "node:PROD")],
      backtest: { hits: 3, of: 3, avg_lead_min: 41 },
      backup_expert: { id: "raj", name: "Raj Patel" },
    },
  ];
}

function metrics(nodeId: string): MetricsResponse {
  const N = 60;
  const end = Date.parse(demoNow());
  const prod = nodeId === "node:PROD";
  const mk = (metric: string, f: (i: number) => number) => ({
    metric,
    points: Array.from({ length: N }, (_, i) => [
      new Date(end - (N - 1 - i) * 60000).toISOString().replace(/\.\d+Z$/, "Z"),
      Math.round(f(i) * 10) / 10,
    ]) as [string, number][],
  });
  const wob = (i: number, k: number) => Math.sin(i * 1.7 + k) * 1.5;
  return {
    series: [
      mk("audit-capacity-pct", (i) =>
        prod ? Math.min(99, 41 + 21 * (i / (N - 1)) + (i === N - 1 ? auditNow() - 62 : 0) + wob(i, 1) * (i === N - 1 ? 0 : 0.4)) : 22 + wob(i, 1) * 0.3,
      ),
      mk("cpu-busy-time", (i) => (prod ? 52 + 12 * (i / (N - 1)) + wob(i, 2) * 3 : 18 + wob(i, 2))),
      mk("request-qtime", (i) => (prod ? 12 + 16 * (i / (N - 1)) ** 2 + wob(i, 3) : 6 + wob(i, 3) * 0.4)),
    ],
  };
}

function session(): Session {
  return {
    node: state.node,
    node_display: nodeDisplay(state.node),
    series: "rvu:L",
    user: "OPS.NEWHIRE",
    nodes_available: NODES,
  };
}

export const mockApi = {
  async getSession() {
    await lag();
    return session();
  },
  async setSession(node: string) {
    await lag();
    if (!NODES.some((n) => n.id === node)) throw new Error(`Unknown node ${node}`);
    state.node = node;
    return session();
  },
  async chat(req: ChatRequest) {
    await sleep(500 + Math.random() * 400);
    return chat(req);
  },
  async refer(req: ReferRequest): Promise<ReferResponse> {
    await lag();
    void req;
    return { referral_id: `q${state.referralCounter++}`, status: "sent" };
  },
  async propose(req: ProposeRequest) {
    await lag();
    return propose(req);
  },
  async dryrun(id: string) {
    await sleep(400);
    return dryrun(id);
  },
  async approve(id: string, body: ApproveRequest) {
    await lag();
    return approve(id, body);
  },
  async execute(id: string) {
    await sleep(600);
    return execute(id);
  },
  async getAlerts() {
    await sleep(60);
    return alerts();
  },
  async getMetrics(node: string) {
    await sleep(60);
    return metrics(node);
  },
  async runScenario(req: ScenarioRequest) {
    await lag();
    if (req.scenario === "audit_trail_fill") state.scenarioAt = Date.now();
    return { status: "running" };
  },
  async getSource(id: string): Promise<Source> {
    await sleep(80);
    const run = state.runs.find((r) => r.run_id === id);
    const s = run ? liveSource(run) : sourceById(id);
    if (!s) throw new Error(`Unknown source ${id}`);
    return s;
  },
};
