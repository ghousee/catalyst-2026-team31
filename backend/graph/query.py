"""Deterministic knowledge-graph queries: question text -> entities, entities -> docs / veteran notes / commands / experts.

No LLM. The interface of resolve() and lookup() is fixed (the API layer codes against it).

    resolve(conn, text, ctx)            alias / name / event-number match
    lookup(conn, entity_ids, ctx, k)    walk edges 2 hops, filter by context, return citable material

ctx = {"system": sub-id|None, "version": rvu-id|None, "site": node-id|None}  (ADR-004: system = subsystem,
version = series, site = node). Heuristics and doc chunks are scoped with retrieve.context_where, so a note scoped
to node:PROD is never returned for a node:DR session. Works on psycopg and (for tests) on sqlite3 connections.
"""
import json
import re
import sqlite3

from backend.pipeline.retrieve import context_params, context_where

# ---------------------------------------------------------------- text normalisation
STOP = set("is are was be been the a an of to in on at it its up my our this that we".split())
EMS_PREFIXES = ("tmf", "disk", "pathway", "cpu")
KIND_ORDER = {"event": 0, "metric": 1, "object": 2, "command": 3, "system": 4}
# chunks removed by a document re-upload carry valid_to = the day they disappeared (exclusive end)
DOC_CURRENT = "({0}valid_to IS NULL OR {0}valid_to > CURRENT_DATE)"
HUBS = ("sub:", "node:", "rvu:")          # context anchors: reached, never expanded
SHORT = {"sub:TMF": "TMF", "sub:PATHWAY": "Pathway", "sub:SCF-STORAGE": "Storage", "sub:TACL": "TACL",
         "sub:PEEK": "PEEK", "sub:MEASURE": "Measure", "sub:FUP": "FUP"}
TRAVERSE = ("about", "symptom_of", "fixed_by", "precedes", "depends_on", "diagnosed_by", "mentions", "expert_in")
RISK_ORDER = {"read_only": 0, "state_changing": 1, "critical": 2}
AVAIL_ORDER = {"on_shift": 0, "on_call": 1, "off_shift": 2, "retired": 3, None: 4}
_HEUR_ID = re.compile(r"^[a-z]+:h\d+$")


def _stem(w):
    if w[0] == "$" or any(c.isdigit() for c in w) or len(w) <= 4:
        return w
    for suf in ("ing", "ed"):
        if w.endswith(suf) and len(w) - len(suf) >= 3:
            w = w[: -len(suf)]
            if len(w) > 2 and w[-1] == w[-2] and w[-1] not in "lsz":
                w = w[:-1]
            return w
    if w.endswith("s") and not w.endswith("ss"):
        return w[:-1]
    return w


def tokens(text):
    """Lower-cased, stop-word-free, stemmed tokens; 'TMF185' -> tmf 185; '\\PROD' -> prod; '$AUDIT' stays $audit."""
    t = re.sub(r"\b(%s)(\d{2,4})\b" % "|".join(EMS_PREFIXES), r"\1 \2", text.lower())
    return [_stem(w) for w in re.findall(r"\$?[a-z0-9]+", t) if w not in STOP]


def _j(v, default):
    if v is None:
        return default
    return json.loads(v) if isinstance(v, str) else v


# ---------------------------------------------------------------- db helpers (psycopg or sqlite3)
def _rows(conn, sql, params=None):
    if isinstance(conn, sqlite3.Connection):
        sql = re.sub(r"%\((\w+)\)s", r":\1", sql)
    cur = conn.cursor()
    cur.execute(sql, params or {})
    cols = [getattr(d, "name", None) or d[0] for d in cur.description]
    return [dict(zip(cols, r)) for r in cur.fetchall()]


def _in(prefix, ids):
    ids = list(ids)
    return "(" + ",".join(f"%({prefix}{i})s" for i in range(len(ids))) + ")", {f"{prefix}{i}": v for i, v in enumerate(ids)}


def _entities(conn):
    rows = _rows(conn, "SELECT id, kind, name, aliases, parent_id, props FROM entity")
    for r in rows:
        r["aliases"], r["props"] = _j(r["aliases"], []), _j(r["props"], {})
    return rows


def _subsystem_of(e):
    if e["kind"] == "system":
        return e["id"]
    return e["parent_id"] if (e.get("parent_id") or "").startswith("sub:") else None


# ---------------------------------------------------------------- resolve
def match_entities(ents, text, ctx=None):
    """Pure core of resolve(). ents = entity rows (id, kind, name, aliases, parent_id, props)."""
    ctx = ctx or {}
    toks = tokens(text)
    found = {}  # id -> (score, matched)

    def hit(e, score, matched):
        if e["id"] not in found or found[e["id"]][0] < score:
            found[e["id"]] = (score, matched)

    for e in ents:
        for alias in [e["name"], *e["aliases"]]:
            a = tokens(alias)
            n = len(a)
            if n and any(toks[i:i + n] == a for i in range(len(toks) - n + 1)):
                hit(e, n, alias)

    def ent_sub(i):
        return _subsystem_of(next(x for x in ents if x["id"] == i))

    votes = {}
    for i, (score, _) in found.items():
        s = ent_sub(i)
        if s:
            votes[s] = votes.get(s, 0) + score
    # event numbers: "TMF 185" (prefix names the EMS subsystem) or a bare "185"/"error 1034"
    text_l = text.lower()
    top = max(votes.values(), default=0)
    top_subs = [s for s, v in votes.items() if v == top]
    hint = top_subs[0] if len(top_subs) == 1 else ctx.get("system")
    for m in re.finditer(r"(?<![\w$.])(\d{2,4})(?![\d%])", re.sub(r"\b(%s)(\d{2,4})\b" % "|".join(EMS_PREFIXES), r"\1 \2", text_l)):
        num = int(m.group(1))
        cands = [e for e in ents if e["kind"] == "event" and e["props"].get("number") == num]
        if not cands:
            continue
        prefix = re.findall(r"[a-z]+", text_l[: m.start()])[-1:] or [""]
        by_prefix = [e for e in cands if e["props"].get("ems", "").lower() == prefix[0]]
        by_hint = [e for e in cands if hint and _subsystem_of(e) == hint]
        for e in by_prefix or by_hint or cands:
            hit(e, 2 if by_prefix else 1, f"{e['props'].get('ems', '')} {num}")
    return found


def resolve(conn, text, ctx):
    """See module docstring. Returns {"subsystem", "entities", "nodes_mentioned"}; subsystem is inferred from the
    matched entities only (never copied from ctx); None when nothing matched or two subsystems tie (caller clarifies)."""
    ents = _entities(conn)
    by_id = {e["id"]: e for e in ents}
    found = match_entities(ents, text, ctx)
    nodes = sorted(i for i in found if by_id[i]["kind"] == "site")
    ranked = sorted((i for i in found if by_id[i]["kind"] not in ("site", "version")),
                    key=lambda i: (-found[i][0], KIND_ORDER.get(by_id[i]["kind"], 9), i))
    votes = {}
    for i in ranked:
        s = _subsystem_of(by_id[i])
        if s:
            votes[s] = votes.get(s, 0) + found[i][0]
    top = max(votes.values(), default=0)
    winners = [s for s, v in votes.items() if v == top]
    return {"subsystem": winners[0] if len(winners) == 1 else None,
            "entities": [{"id": i, "kind": by_id[i]["kind"], "name": by_id[i]["name"], "matched": found[i][1]}
                         for i in ranked[:8]],
            "nodes_mentioned": nodes}


# ---------------------------------------------------------------- graph walk (pure)
def id_kind(i):
    if i.startswith("doc:"):
        return "chunk"
    if _HEUR_ID.match(i):
        return "heuristic"
    if ":" not in i:
        return "person"
    return "entity"


def walk(edges, starts, max_depth=2):
    """BFS over TRAVERSE relations (undirected). Entities expand (hubs sub:/node:/rvu: do not); chunks, heuristics
    and persons are leaves. Returns ({id: depth}, [edge dicts actually walked])."""
    depth = {s: 0 for s in starts}
    order, used, queue = list(starts), [], list(starts)
    while queue:
        n = queue.pop(0)
        if id_kind(n) != "entity" or n.startswith(HUBS) or depth[n] >= max_depth:
            continue
        for e in edges:
            if e["rel"] not in TRAVERSE or n not in (e["src"], e["dst"]):
                continue
            other = e["dst"] if e["src"] == n else e["src"]
            if other not in depth:
                depth[other] = depth[n] + 1
                order.append(other)
                queue.append(other)
            if depth[other] == depth[n] + 1 and e not in used:
                used.append(e)
    return {i: depth[i] for i in order}, used


# ---------------------------------------------------------------- lookup
def short(sub):
    """Short display name of a subsystem id; a subsystem created from an upload falls back to its id suffix."""
    return SHORT.get(sub, (sub or "").split(":", 1)[-1])


def scope_text(h):
    node = "all nodes" if h["site_id"] is None else "\\" + h["site_id"].split(":", 1)[1]
    series = "all series" if h["version_id"] is None else h["version_id"].split(":", 1)[1] + "-series"
    return f"{node} · {series} · {short(h['system_id'])}"


def _captured(h):
    detail = h["provenance"].split(":", 1)[1] if ":" in (h["provenance"] or "") else ""
    via = h["captured_via"] or ""
    return f"{via} {detail}".strip() if detail and not re.match(r"\d{4}-", detail) else via


def render_heuristic(h):
    """Plain text handed to the LLM / answer card (one veteran note)."""
    rel = f" Relation to the manual: {h['relation']}." if h["relation"] and h["relation"] != "about" else ""
    nw = f" Does NOT apply when: {h['not_when']}" if h["not_when"] else ""
    return (f"[{h['id']}] {h['owner_name']} ({h['owner_role']}, {h['years']} years), captured via {h['captured_via']} "
            f"{h['captured_at']}, {h['endorsements']} endorsements. Scope: {h['scope']}. When: {h['trigger']} "
            f"Call: {h['call']} Why: {h['why']}{nw}{rel}")


def note_dict(h, rel, disagrees=()):
    """One veteran note as returned by lookup/note_search/fetch_notes. h = heuristic row joined with its owner."""
    out = {"id": h["id"], "owner": h["owner_id"], "owner_name": h["owner_name"], "owner_role": h["owner_role"],
           "years": h["years"], "captured_via": _captured(h), "captured_at": str(h["captured_at"] or ""),
           "endorsements": h["endorsements"], "last_validated": str(h["last_validated"] or ""),
           "scope": scope_text(h), "why": h["why_text"], "call": h["call_text"], "trigger": h["trigger_text"],
           "not_when": h["not_when_text"], "relation": rel, "disagrees_with": list(dict.fromkeys(disagrees)),
           "needs_review": bool(h.get("needs_review"))}
    out["text"] = render_heuristic({**out, "captured_via": h["captured_via"] or ""})
    return out


def _vec(v):
    if isinstance(v, str):
        return json.loads(v)
    return v.to_list() if hasattr(v, "to_list") else [float(x) for x in v]  # pgvector Vector / array / list


def _approved(conn, ids, ctx):
    inl, p = _in("h", ids)
    return _rows(conn, f"SELECT h.*, p.name AS owner_name, p.role AS owner_role, p.years AS years FROM heuristic h "
                       f"JOIN person p ON p.id = h.owner_id WHERE h.id IN {inl} AND h.status = 'approved' "
                       f"AND {context_where('h')}", {**p, **context_params(ctx)})


def fetch_notes(conn, ids, ctx):
    """Approved notes with these ids that are inside the context (same filter as lookup). {id: note}.
    `disagrees_with` lists only partners that are themselves approved and in the context (no id leaks across nodes)."""
    ids = list(dict.fromkeys(ids))
    if not ids:
        return {}
    rows = _approved(conn, ids, ctx)
    inl, p = _in("e", ids)
    edges = _rows(conn, f"SELECT src, rel, dst FROM edge WHERE rel IN ('contradicts', 'extends', 'disagrees_with') "
                        f"AND (src IN {inl} OR dst IN {inl})", p)
    others = [e["dst"] if e["src"] in ids else e["src"] for e in edges if e["rel"] == "disagrees_with"]
    others = [o for o in dict.fromkeys(others) if o not in ids]
    present = {r["id"] for r in rows} | ({r["id"] for r in _approved(conn, others, ctx)} if others else set())
    out = {}
    for h in rows:
        rels = {}
        for e in edges:
            if e["src"] == h["id"] and e["rel"] in ("contradicts", "extends"):
                rels.setdefault(e["rel"], f"{e['rel']}:{e['dst']}")
        dis = [e["dst"] if e["src"] == h["id"] else e["src"] for e in edges
               if e["rel"] == "disagrees_with" and h["id"] in (e["src"], e["dst"])]
        out[h["id"]] = note_dict(h, rels.get("contradicts") or rels.get("extends") or "about",
                                 [o for o in dis if o in present])
    return out


def note_search(conn, qvec, ctx, k=3):
    """Veteran notes nearest to the question vector: approved + inside the context (node/series scoped, same
    context_where as lookup). Brute-force cosine in Python: there are tens of notes, not thousands."""
    params = context_params(ctx)
    rows = _rows(conn, f"SELECT h.id, h.embedding FROM heuristic h WHERE h.status = 'approved' "
                       f"AND h.embedding IS NOT NULL AND {context_where('h')}", params)
    qn = sum(x * x for x in qvec) ** 0.5 or 1.0
    scored = []
    for r in rows:
        v = _vec(r["embedding"])
        vn = sum(x * x for x in v) ** 0.5 or 1.0
        scored.append((sum(a * b for a, b in zip(qvec, v)) / (qn * vn), r["id"]))
    top = sorted(scored, reverse=True)[:k]
    notes = fetch_notes(conn, [i for _, i in top], ctx)
    return [{**notes[i], "score": round(sc, 3)} for sc, i in top if i in notes]


def lookup(conn, entity_ids, ctx, k=10):
    """See module docstring. Raises ValueError if the context has no system and the entities do not imply exactly one."""
    ents = {e["id"]: e for e in _entities(conn)}
    start = [i for i in dict.fromkeys(entity_ids) if i in ents]
    if not (ctx or {}).get("system"):
        subs = {_subsystem_of(ents[i]) for i in start} - {None}
        if len(subs) != 1:
            raise ValueError("context has no resolved system; clarify before looking up")
        ctx = {**(ctx or {}), "system": subs.pop()}
    params = context_params(ctx)
    system = params["system"]
    edges = _rows(conn, "SELECT src, rel, dst, weight, source_id FROM edge")
    depth, used = walk(edges, start)

    # veteran notes: approved + inside the context (node/series scoped), plus disagreeing partners
    cand = [i for i in depth if id_kind(i) == "heuristic"]
    heur = {}

    def fetch_heuristics(ids):
        if not ids:
            return
        inl, p = _in("h", ids)
        sql = (f"SELECT h.*, p.name AS owner_name, p.role AS owner_role, p.years AS years FROM heuristic h "
               f"JOIN person p ON p.id = h.owner_id WHERE h.id IN {inl} AND h.status = 'approved' AND {context_where('h')}")
        for r in _rows(conn, sql, {**p, **params}):
            heur[r["id"]] = r
    fetch_heuristics(cand)
    partners = [e["dst"] if e["src"] in heur else e["src"] for e in edges
                if e["rel"] == "disagrees_with" and (e["src"] in heur or e["dst"] in heur)]
    fetch_heuristics([x for x in dict.fromkeys(partners) if x not in heur])

    hrel = [e for e in edges if e["rel"] in ("extends", "contradicts", "disagrees_with") and e["src"] in heur
            or e["rel"] == "disagrees_with" and e["dst"] in heur]
    heuristics = []
    for h in heur.values():
        # relation shown to the user: contradicts (manual) > disagrees_with (another veteran, both kept) > extends
        rels = {}
        for e in hrel:
            if e["rel"] in ("contradicts", "extends") and e["src"] == h["id"]:
                rels.setdefault(e["rel"], f"{e['rel']}:{e['dst']}")
            elif e["rel"] == "disagrees_with" and h["id"] in (e["src"], e["dst"]):
                o = e["dst"] if e["src"] == h["id"] else e["src"]
                if o in heur:
                    rels.setdefault("disagrees_with", f"disagrees_with:{o}")
        rel = rels.get("contradicts") or rels.get("disagrees_with") or rels.get("extends") or "about"
        dis = [e["dst"] if e["src"] == h["id"] else e["src"] for e in hrel
               if e["rel"] == "disagrees_with" and h["id"] in (e["src"], e["dst"])]
        out = note_dict(h, rel, [o for o in dis if o in heur])
        out["_rank"] = (0 if rel.startswith("contradicts") else 1 if rel.startswith(("disagrees", "extends")) else 2,
                        depth.get(h["id"], 3), -(h["endorsements"] or 0), h["id"])
        heuristics.append(out)
    heuristics.sort(key=lambda x: x["_rank"])
    heuristics = heuristics[:k]
    for x in heuristics:
        del x["_rank"]
    kept_h = {x["id"] for x in heuristics}

    # commands: catalog entities reached by the walk, same subsystem only
    commands = []
    for i in depth:
        e = ents.get(i)
        if e and e["kind"] == "command" and e["props"].get("subsystem") == system and "template_id" in e["props"]:  # not auto-docs commands
            p = e["props"]
            commands.append((depth[i], RISK_ORDER.get(p["risk"], 9), e["name"],
                             {"template_id": p["template_id"], "command": p["command"], "risk": p["risk"],
                              "explanation": p["explanation"], "source_id": p["source_id"], "subsystem": p["subsystem"],
                              "_id": i}))
    commands = [c[3] for c in sorted(commands, key=lambda c: c[:3])][:k]

    # doc chunks: walked leaves first, then what the kept notes extend/contradict, then the commands' own citations
    chunk_ids = [i for i in depth if id_kind(i) == "chunk"]
    chunk_ids += [e["dst"] for e in hrel if e["src"] in kept_h and e["rel"] in ("extends", "contradicts")]
    chunk_ids += [c["source_id"] for c in commands]
    chunk_ids = list(dict.fromkeys(chunk_ids))
    docs = []
    if chunk_ids:
        inl, p = _in("c", chunk_ids)
        got = {r["id"]: r for r in _rows(
            conn, f"SELECT d.id, d.section, d.text, d.system_id, d.edition FROM doc_chunk d "
                  f"WHERE d.id IN {inl} AND {context_where('d')} AND {DOC_CURRENT.format('d.')}", {**p, **params})}
        docs = [got[i] for i in chunk_ids if i in got][:k]
    kept_d = {d["id"] for d in docs}

    # experts: expert_in edges on the walked entities / the system, plus authors of the notes we return
    anchors = {i for i in depth if id_kind(i) == "entity"} | {system}
    weights, why = {}, {}
    for e in edges:
        if e["rel"] == "expert_in" and e["dst"] in anchors:
            weights[e["src"]] = max(weights.get(e["src"], 0), e["weight"] or 0)
            why.setdefault(e["src"], []).append(ents[e["dst"]]["name"] if e["dst"] in ents else e["dst"])
    returned_authors = {h["owner"] for h in heuristics}
    # "author of N notes that apply here" counts the owner's approved notes in this context, not just the returned ones
    authored = {r["owner_id"]: r["n"] for r in _rows(
        conn, f"SELECT h.owner_id, count(*) AS n FROM heuristic h WHERE h.status = 'approved' AND {context_where('h')} "
              f"GROUP BY h.owner_id", params)}
    ids = list(dict.fromkeys([*weights, *returned_authors]))
    experts = []
    if ids:
        inl, p = _in("p", ids)
        for r in _rows(conn, f"SELECT * FROM person WHERE id IN {inl}", p):
            parts = []
            if r["id"] in weights:
                parts.append(f"Resolved up to {int(weights[r['id']])} cases on " + ", ".join(dict.fromkeys(why[r["id"]])))
            if authored.get(r["id"]):
                parts.append(f"author of {authored[r['id']]} approved note(s) that apply here")
            if r["availability"] == "retired":
                parts.append("retired; the captured knowledge is cited")
            experts.append({"id": r["id"], "name": r["name"], "role": r["role"], "team": r["team"], "years": r["years"],
                            "expertise": _j(r["expertise"], []), "availability": r["availability"],
                            "contact": r["contact"], "reason": "; ".join(parts), "active": bool(r["active"]),
                            "_k": (not r["active"], AVAIL_ORDER.get(r["availability"], 4), -weights.get(r["id"], 0))})
        experts.sort(key=lambda x: x["_k"])
        for x in experts:
            del x["_k"]
    kept_p = {x["id"] for x in experts}

    # path: the edges that explain the result (only between things we actually return)
    kept = {i for i in depth if id_kind(i) == "entity"} - {e for e in ents if ents[e]["kind"] == "command"} \
        | {c["_id"] for c in commands} | kept_h | kept_d | kept_p | {system}
    path, seen = [], set()
    for e in [*used, *hrel, *[x for x in edges if x["rel"] == "expert_in" and x["dst"] in anchors]]:
        key = (e["src"], e["rel"], e["dst"])
        # an edge justified by an out-of-context note (e.g. a \PROD note on \DR) must not leak through the path:
        # drop it, except expert_in (who knows what is not node-scoped), which keeps the edge but not the citation
        leaked = id_kind(e["source_id"] or "") == "heuristic" and e["source_id"] not in kept_h
        if key in seen or e["src"] not in kept or e["dst"] not in kept or (leaked and e["rel"] != "expert_in"):
            continue
        seen.add(key)
        path.append({"src": e["src"], "rel": e["rel"], "dst": e["dst"], "source_id": None if leaked else e["source_id"]})
    for c in commands:
        del c["_id"]
    return {"doc_chunks": docs, "heuristics": heuristics, "commands": commands, "experts": experts, "path": path}
