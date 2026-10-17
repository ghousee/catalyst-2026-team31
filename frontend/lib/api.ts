import type {
  Alert,
  ApproveRequest,
  ApproveResponse,
  ChatRequest,
  ChatResponse,
  DryRun,
  ExecuteResponse,
  MetricsResponse,
  ProposeRequest,
  ProposeResponse,
  ReferRequest,
  ReferResponse,
  ScenarioRequest,
  Session,
  Source,
} from "./types";

export const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";
export const USE_MOCKS = process.env.NEXT_PUBLIC_USE_MOCKS !== "false";
// Comma list of endpoint groups served by the real API while everything else stays mocked: session,chat,sources
const REAL = new Set((process.env.NEXT_PUBLIC_REAL_ENDPOINTS ?? "").split(",").map((x) => x.trim()).filter(Boolean));
const mocked = (group?: "session" | "chat" | "sources") => USE_MOCKS && !(group && REAL.has(group));
/** True when chat answers come from the scripted mock, not the backend; the top bar shows a DEMO DATA badge. */
export const CHAT_IS_MOCK = mocked("chat");

export class ApiError extends Error {
  constructor(
    message: string,
    public status?: number,
  ) {
    super(message);
  }
}

async function http<T>(method: "GET" | "POST", path: string, body?: unknown): Promise<T> {
  let res: Response;
  try {
    res = await fetch(`${API_URL}${path}`, {
      method,
      headers: body ? { "Content-Type": "application/json" } : undefined,
      body: body ? JSON.stringify(body) : undefined,
    });
  } catch {
    throw new ApiError(`Cannot reach API at ${API_URL}`);
  }
  if (!res.ok) {
    const detail = await res.text().catch(() => "");
    throw new ApiError(detail || `${method} ${path} failed (${res.status})`, res.status);
  }
  return (await res.json()) as T;
}

const mock = () => import("@/mocks/server").then((m) => m.mockApi);
const enc = encodeURIComponent;

export const api = {
  getSession: (): Promise<Session> => (mocked("session") ? mock().then((m) => m.getSession()) : http("GET", "/session")),
  setSession: (node: string): Promise<Session> =>
    mocked("session") ? mock().then((m) => m.setSession(node)) : http("POST", "/session", { node }),
  chat: (req: ChatRequest): Promise<ChatResponse> =>
    mocked("chat") ? mock().then((m) => m.chat(req)) : http("POST", "/chat", req),
  refer: (req: ReferRequest): Promise<ReferResponse> =>
    mocked() ? mock().then((m) => m.refer(req)) : http("POST", "/refer", req),
  propose: (req: ProposeRequest): Promise<ProposeResponse> =>
    mocked() ? mock().then((m) => m.propose(req)) : http("POST", "/commands/propose", req),
  dryrun: (id: string): Promise<DryRun> =>
    mocked() ? mock().then((m) => m.dryrun(id)) : http("POST", `/commands/${enc(id)}/dryrun`),
  approve: (id: string, body: ApproveRequest): Promise<ApproveResponse> =>
    mocked() ? mock().then((m) => m.approve(id, body)) : http("POST", `/commands/${enc(id)}/approve`, body),
  execute: (id: string): Promise<ExecuteResponse> =>
    mocked() ? mock().then((m) => m.execute(id)) : http("POST", `/commands/${enc(id)}/execute`),
  getAlerts: (): Promise<Alert[]> => (mocked() ? mock().then((m) => m.getAlerts()) : http("GET", "/alerts")),
  getMetrics: (node: string, window = "60m"): Promise<MetricsResponse> =>
    mocked()
      ? mock().then((m) => m.getMetrics(node))
      : http("GET", `/metrics?node=${enc(node)}&window=${enc(window)}`),
  runScenario: (req: ScenarioRequest): Promise<{ status: string }> =>
    mocked() ? mock().then((m) => m.runScenario(req)) : http("POST", "/simulator/scenario", req),
  // NOT in the contract: citation chips for ids that arrive without an inline `sources` entry
  // (proposal.source_id, alert fix_claims). Assumed endpoint; see vault/code/frontend.md.
  getSource: (id: string): Promise<Source> =>
    mocked("sources") ? mock().then((m) => m.getSource(id)) : http("GET", `/sources/${enc(id)}`),
};
