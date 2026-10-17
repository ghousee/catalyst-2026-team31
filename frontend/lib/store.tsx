"use client";

import { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState } from "react";
import { api } from "./api";
import { excerptOf, fmtTime } from "./format";
import { getMe } from "./me";
import type {
  ChatAnswer,
  ChatClarify,
  ChatRefer,
  Claim,
  ClarifyOption,
  ContextOverride,
  ExecuteResponse,
  Expert,
  LiveSource,
  Proposal,
  Session,
  Source,
} from "./types";

/** The current user id, read at call time (the top-bar picker can change it). */
export const userId = () => getMe().id;

export interface TermLine {
  id: number;
  kind: "banner" | "prompt" | "cmd" | "out" | "sys";
  text: string;
}

export type ChatMsg =
  | { id: number; kind: "user"; text: string }
  | { id: number; kind: "answer"; question: string; data: ChatAnswer; proposals: Proposal[] | null; noTemplate: boolean }
  | { id: number; kind: "clarify"; question: string; data: ChatClarify; resolved: string | null }
  | { id: number; kind: "refer"; question: string; data: ChatRefer }
  | { id: number; kind: "observation"; source: LiveSource; claim: Claim }
  | { id: number; kind: "proposals"; title: string; proposals: Proposal[] }
  | { id: number; kind: "system"; text: string }
  | { id: number; kind: "error"; text: string };

type DistributiveOmit<T, K extends keyof never> = T extends unknown ? Omit<T, K> : never;
type NewMsg = DistributiveOmit<ChatMsg, "id">;

export interface SourceView {
  id: string;
  loading: boolean;
  error: string | null;
  source: Source | null;
}

interface ConsoleCtx {
  session: Session | null;
  sessionError: string | null;
  override: ContextOverride;
  setOverride: (o: ContextOverride) => void;
  messages: ChatMsg[];
  busy: boolean;
  terminal: TermLine[];
  sourceView: SourceView | null;
  ask: (q: string, ov?: ContextOverride, echo?: boolean) => Promise<void>;
  pickClarify: (msgId: number, question: string, opt: ClarifyOption) => void;
  switchNode: (nodeId: string) => Promise<void>;
  onExecuted: (p: Proposal, res: ExecuteResponse) => void;
  referExpert: (e: Expert, question: string) => Promise<string>;
  openSource: (id: string, inline?: Source[]) => void;
  closeSource: () => void;
  retrySession: () => void;
}

const Ctx = createContext<ConsoleCtx | null>(null);
export const useConsole = () => {
  const c = useContext(Ctx);
  if (!c) throw new Error("useConsole outside provider");
  return c;
};

let seq = 1;
const nid = () => seq++;

export function ConsoleProvider({ children }: { children: React.ReactNode }) {
  const [session, setSession] = useState<Session | null>(null);
  const [sessionError, setSessionError] = useState<string | null>(null);
  const [override, setOverride] = useState<ContextOverride>({});
  const [messages, setMessages] = useState<ChatMsg[]>([]);
  const [busy, setBusy] = useState(false);
  const [terminal, setTerminal] = useState<TermLine[]>([]);
  const [sourceView, setSourceView] = useState<SourceView | null>(null);

  const sessionRef = useRef<Session | null>(null);
  const overrideRef = useRef<ContextOverride>({});
  const cache = useRef(new Map<string, Source>());
  const cmdCount = useRef(1);
  const msgsRef = useRef<ChatMsg[]>([]);
  msgsRef.current = messages;
  sessionRef.current = session;
  overrideRef.current = override;

  const push = useCallback((m: NewMsg) => {
    const id = nid();
    setMessages((prev) => [...prev, { ...m, id } as ChatMsg]);
    return id;
  }, []);
  const patch = useCallback((id: number, f: (m: ChatMsg) => ChatMsg) => {
    setMessages((prev) => prev.map((m) => (m.id === id ? f(m) : m)));
  }, []);
  const term = useCallback((lines: Array<Omit<TermLine, "id">>) => {
    setTerminal((prev) => [...prev, ...lines.map((l) => ({ ...l, id: nid() }))]);
  }, []);

  const loadSession = useCallback(async () => {
    try {
      const s = await api.getSession();
      setSession(s);
      setSessionError(null);
      setTerminal((prev) =>
        prev.length
          ? prev
          : [
              { id: nid(), kind: "banner", text: "CAIL 6530 Terminal Emulator  (simulated session)" },
              { id: nid(), kind: "sys", text: `Connected to ${s.node_display}  series ${s.series.replace("rvu:", "")}  user ${s.user}` },
              { id: nid(), kind: "sys", text: "Read-only display. Commands arrive here only through the approval flow." },
            ],
      );
    } catch (e) {
      setSessionError(e instanceof Error ? e.message : "Session unavailable");
    }
  }, []);

  useEffect(() => {
    void loadSession();
  }, [loadSession]);

  const ask = useCallback(
    async (q: string, ov?: ContextOverride, echo = true) => {
      if (echo) push({ kind: "user", text: q });
      setBusy(true);
      const context_override = { ...overrideRef.current, ...ov };
      try {
        // last few answered turns, so follow-ups ("why?", "what about the commands?") have context
        const history = msgsRef.current
          .filter((m): m is Extract<ChatMsg, { kind: "answer" }> => m.kind === "answer")
          .slice(-3)
          .map((m) => ({ question: m.question, reply: m.data.reply }));
        const res = await api.chat({ user_id: userId(), question: q, context_override, history });
        if (res.type === "clarify") {
          push({ kind: "clarify", question: q, data: res, resolved: null });
        } else if (res.type === "refer") {
          push({ kind: "refer", question: q, data: res });
        } else {
          res.sources.forEach((s) => cache.current.set(s.id, s));
          const id = push({ kind: "answer", question: q, data: res, proposals: null, noTemplate: false });
          api
            .propose({
              question: q,
              context: { system: res.context.system, site: res.context.site, version: res.context.version },
            })
            .then((p) => patch(id, (m) => (m.kind === "answer" ? { ...m, proposals: p.proposals, noTemplate: p.no_template } : m)))
            .catch(() => patch(id, (m) => (m.kind === "answer" ? { ...m, proposals: [], noTemplate: true } : m)));
        }
      } catch (e) {
        push({ kind: "error", text: e instanceof Error ? e.message : "Request failed" });
      } finally {
        setBusy(false);
      }
    },
    [push, patch],
  );

  const pickClarify = useCallback(
    (msgId: number, question: string, opt: ClarifyOption) => {
      patch(msgId, (m) => (m.kind === "clarify" ? { ...m, resolved: opt.label } : m));
      void ask(question, opt.value, false);
    },
    [ask, patch],
  );

  const switchNode = useCallback(
    async (nodeId: string) => {
      const prev = sessionRef.current;
      const s = await api.setSession(nodeId);
      setSession(s);
      setOverride({});
      term([
        { kind: "sys", text: `*** Session switched ${prev?.node_display ?? "?"} -> ${s.node_display}` },
        { kind: "sys", text: `Connected to ${s.node_display}  series ${s.series.replace("rvu:", "")}  user ${s.user}` },
      ]);
      push({
        kind: "system",
        text: `Session switched to ${s.node_display}. Earlier answers and proposals were for ${prev?.node_display ?? "the previous node"} and no longer apply.`,
      });
    },
    [push, term],
  );

  const onExecuted = useCallback(
    (p: Proposal, res: ExecuteResponse) => {
      const s = sessionRef.current;
      const prompt = `${p.node}.${s?.user ?? "OPS"} ${cmdCount.current++}>`;
      term([
        { kind: "cmd", text: `${prompt} ${p.command}` },
        ...res.output
          .replace(/\n+$/, "")
          .split("\n")
          .map((t) => ({ kind: "out" as const, text: t })),
      ]);
      const source: LiveSource = {
        id: res.source_id,
        kind: "live",
        command: p.command,
        node: p.node,
        ts: res.ts,
        excerpt: excerptOf(res.output),
      };
      cache.current.set(source.id, source);
      push({
        kind: "observation",
        source,
        claim: { text: `${source.excerpt} (observed ${fmtTime(res.ts)} on ${p.node})`, lane: "live", source_id: source.id, verified: true, score: 1 },
      });
      api
        .propose({
          question: "what next after this output?",
          context: { system: "sub:TMF", site: s?.node ?? "node:PROD", version: s?.series ?? "rvu:L" },
        })
        .then((r) => {
          if (r.proposals.length) push({ kind: "proposals", title: "Suggested next step", proposals: r.proposals });
        })
        .catch(() => undefined);
    },
    [push, term],
  );

  const referExpert = useCallback(async (e: Expert, question: string) => {
    const r = await api.refer({ expert_id: e.id, question, context: null, from_user: userId() });
    return r.referral_id;
  }, []);

  const openSource = useCallback((id: string, inline?: Source[]) => {
    const hit = inline?.find((s) => s.id === id) ?? cache.current.get(id);
    if (hit) {
      cache.current.set(id, hit);
      setSourceView({ id, loading: false, error: null, source: hit });
      return;
    }
    setSourceView({ id, loading: true, error: null, source: null });
    api
      .getSource(id)
      .then((s) => {
        cache.current.set(id, s);
        setSourceView((v) => (v && v.id === id ? { id, loading: false, error: null, source: s } : v));
      })
      .catch((e) =>
        setSourceView((v) =>
          v && v.id === id ? { id, loading: false, error: e instanceof Error ? e.message : "Source unavailable", source: null } : v,
        ),
      );
  }, []);

  const value = useMemo<ConsoleCtx>(
    () => ({
      session,
      sessionError,
      override,
      setOverride,
      messages,
      busy,
      terminal,
      sourceView,
      ask,
      pickClarify,
      switchNode,
      onExecuted,
      referExpert,
      openSource,
      closeSource: () => setSourceView(null),
      retrySession: () => void loadSession(),
    }),
    [session, sessionError, override, messages, busy, terminal, sourceView, ask, pickClarify, switchNode, onExecuted, referExpert, openSource, loadSession],
  );

  return <Ctx.Provider value={value}>{children}</Ctx.Provider>;
}
