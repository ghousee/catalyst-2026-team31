// Client for GET /learning/users and GET /learning/{user_id} (docs/API_CONTRACT.md). Always the real API.
import { API_URL } from "./api";

export interface LearningUser { user_id: string; questions: number; last_seen: string }

export interface LearningSubsystem {
  id: string;
  name: string;
  questions: number;
  sections_cited: number;
  notes: { id: string; owner: string }[];
  entities_touched: number;
  entities_total: number;
  coverage: number;
  last_seen: string | null;
}

export interface LearningMap {
  user_id: string;
  totals: {
    questions: number; subsystems_touched: number; subsystems_total: number; notes_seen: number;
    sections_cited: number; entities_touched: number; entities_total: number; coverage: number;
  };
  subsystems: LearningSubsystem[];
  veterans: { id: string; name: string; notes: number }[];
  gaps: { subsystems: string[]; events: { id: string; name: string; subsystem: string }[] };
  recent: { ts: string; question: string; outcome: string; subsystem: string | null }[];
}

async function get<T>(path: string): Promise<T> {
  let res: Response;
  try {
    res = await fetch(`${API_URL}${path}`);
  } catch {
    throw new Error(`Cannot reach API at ${API_URL}`);
  }
  if (!res.ok) {
    const body = await res.json().catch(() => null);
    throw new Error(body?.detail ?? `HTTP ${res.status}`);
  }
  return res.json() as Promise<T>;
}

export const learning = {
  users: () => get<LearningUser[]>("/learning/users"),
  map: (userId: string) => get<LearningMap>(`/learning/${encodeURIComponent(userId)}`),
};
