// Client for the knowledge-capture and document endpoints (docs/API_CONTRACT.md "v3 additions").
// These always call the real API (no mocks): the /knowledge and /documents screens are for checking the backend.
import { API_URL } from "./api";

export interface Person {
  id: string;
  name: string;
  role: string | null;
  availability: string | null;
  active: boolean;
  /** veteran = senior (owns, teaches, signs); emerging = Emerging Veteran (junior in training) */
  level?: "veteran" | "emerging";
}

/** Veterans own and sign knowledge; Emerging Veterans are juniors in training. */
export const isVeteran = (p: Person) => p.level !== "emerging";

export interface NewPerson {
  id: string;
  name: string;
  role: string | null;
  team: string | null;
  years: number | null;
  expertise: string[];
  availability: string | null;
  contact: string | null;
  level?: "veteran" | "emerging";
}

export interface NoteLink {
  rel: string;
  dst: string;
  created_by: string | null;
}

export interface Note {
  id: string;
  owner_id: string;
  owner_name: string;
  entered_by: string | null;
  kind: "note" | "warning_pattern";
  trigger_text: string;
  call_text: string;
  why_text: string;
  not_when_text: string;
  node: "PROD" | "DR" | "ALL";
  subsystem: string;
  status: "draft" | "approved" | "retired";
  captured_via: string | null;
  captured_at: string;
  signed_by: string | null;
  signed_at: string;
  needs_review: boolean;
  links: NoteLink[];
}

export interface NewNote {
  owner_id: string;
  entered_by: string;
  kind: string;
  trigger_text: string;
  call_text: string;
  why_text: string;
  not_when_text: string;
  node: string;
  subsystem: string;
}

export interface TeachMessage {
  role: "veteran" | "assistant";
  text: string;
}

export interface TeachDraft {
  trigger_text: string;
  call_text: string;
  why_text: string;
  not_when_text: string;
  node: "PROD" | "DR" | "ALL";
  subsystem: string;
  kind: "note" | "warning_pattern";
}

/** POST /knowledge/teach: the assistant either asks one follow-up or hands back a draft. */
export type TeachTurn = { type: "question"; text: string } | { type: "draft"; draft: TeachDraft };

export interface Suggestion {
  id: string;
  section: string;
  snippet: string;
}

export interface ApproveResult {
  note: Note;
  auto_links: { rel: string; dst: string; src?: string }[];
  suggested_sections: Suggestion[];
}

export interface DocRow {
  key: string;
  title: string;
  edition: string | null;
  subsystem: string;
  chunks: number;
  removed: number;
  last_loaded: string | null;
}

export interface DiffSummary {
  key: string;
  title: string;
  edition: string;
  subsystem: string;
  subsystem_created: boolean;
  added: number;
  changed: number;
  unchanged: number;
  removed: number;
  changed_ids: string[];
  removed_ids: string[];
  notes_flagged: string[];
}

/** GET /graph (backend/graph/view.py): a live snapshot of the knowledge graph. */
export interface GraphSnapshot {
  counts: {
    entities: Record<string, number>;
    links: Record<string, number>;
    persons: number;
    veterans?: number;
    emerging?: number;
    notes: { approved: number; draft: number; retired: number; needs_review: number };
    doc_sections: number;
    documents: number;
  };
  entities: { id: string; kind: string; name: string; aliases: string[]; parent_id: string | null; links: number }[];
  links: { src: string; rel: string; dst: string; source_id: string | null; created_by: string | null }[];
  links_total: number;
  people?: { id: string; name: string; role: string | null; level: "veteran" | "emerging" }[];
  /** the newest change: a signed note id, or the person whose question or check made the newest learning link */
  latest?: { id: string; ts: string } | null;
  notes: { id: string; owner_name: string; kind: string; scope: string; status: string; needs_review: boolean; signed_at: string; call_text: string }[];
  recent: { ts: string; type: string; text: string }[];
}

async function call<T>(method: "GET" | "POST", path: string, body?: unknown): Promise<T> {
  const form = body instanceof FormData;
  let res: Response;
  try {
    res = await fetch(`${API_URL}${path}`, {
      method,
      headers: body && !form ? { "Content-Type": "application/json" } : undefined,
      body: body ? (form ? (body as FormData) : JSON.stringify(body)) : undefined,
    });
  } catch {
    throw new Error(`Cannot reach the API at ${API_URL}. Is uvicorn running?`);
  }
  if (!res.ok) {
    let detail = await res.text().catch(() => "");
    try {
      const j = JSON.parse(detail) as { detail?: unknown };
      if (typeof j.detail === "string") detail = j.detail;
      else if (j.detail) detail = JSON.stringify(j.detail);
    } catch {
      /* plain text error */
    }
    throw new Error(`${res.status}: ${detail || `${method} ${path} failed`}`);
  }
  return (await res.json()) as T;
}

const enc = encodeURIComponent;

export const admin = {
  persons: () => call<Person[]>("GET", "/persons"),
  addPerson: (p: NewPerson) => call<Person>("POST", "/persons", p),
  notes: (status: "draft" | "approved" | "retired") => call<Note[]>("GET", `/knowledge?status=${status}`),
  addNote: (n: NewNote) => call<Note>("POST", "/knowledge", n),
  teach: (owner_id: string, messages: TeachMessage[]) =>
    call<TeachTurn>("POST", "/knowledge/teach", { owner_id, messages }),
  approve: (id: string, signed_by: string) => call<ApproveResult>("POST", `/knowledge/${enc(id)}/approve`, { signed_by }),
  link: (id: string, doc_id: string, rel: "extends" | "contradicts") =>
    call<Note>("POST", `/knowledge/${enc(id)}/link`, { doc_id, rel }),
  retire: (id: string) => call<Note>("POST", `/knowledge/${enc(id)}/retire`),
  graph: () => call<GraphSnapshot>("GET", "/graph"),
  documents: () => call<DocRow[]>("GET", "/documents"),
  upload: (form: FormData) => call<DiffSummary>("POST", "/documents", form),
};

/** "sub:SCF-STORAGE" -> "SCF-STORAGE" */
export const subName = (id: string) => id.replace(/^sub:/, "");
