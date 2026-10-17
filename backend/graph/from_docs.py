"""Auto-build graph entities from manual section titles (deterministic, no LLM).

    python -m backend.graph.from_docs [--subsystem sub:TMF] [--dry-run] [--rebuild]

Per subsystem, doc_chunk titles give two kinds of entity:
  command  `cmd:auto:<sub>:<slug>`  a section that names a command ("ADD DISK Command", "TMFCOM Commands > STATUS TMF",
                                    "PEEK Syntax and Examples > PAGING Option"). Name "<TOOL> <COMMAND>".
  event    `evt:auto:<sub>:<number>` a numbered operator/error message ("Message 3119", "MEAS 3024").
Edges (created_by = 'auto-docs', source_id = the defining section): section -about-> entity, entity -about-> subsystem.
A command that a curated entity already represents (same subsystem, same normalised words) is merged: only the
section -about-> curated edge is added. Curated rows are never modified. Rows owned by this module: props.auto = true
and created_by = 'auto-docs'; `sync` (also run by POST /documents) re-derives them for one subsystem and prunes the stale ones.
"""
import argparse
import re
import sys

import psycopg
from psycopg.types.json import Json

from backend import settings
from backend.graph.query import tokens

CREATED_BY = "auto-docs"
READ_ONLY = {"STATUS", "INFO", "LISTOPENS", "DISPLAY", "SHOW", "HELP"}  # first word; everything else stays 'unknown'

# subsystem -> (tool name used in entity names, title style, chapter the command headings live in, max words)
PROFILES = {
    "sub:TMF": ("TMFCOM", "bare", "TMFCOM Commands", 3),
    "sub:FUP": ("FUP", "bare", "FUP Commands", 1),
    "sub:MEASURE": ("MEASCOM", "verbs", None, 2),
    "sub:PEEK": ("PEEK", "option", "PEEK Syntax and Examples", 1),
    "sub:SCF-STORAGE": ("SCF", "suffix", None, 3),
    "sub:PATHWAY": ("PATHCOM", "suffix", None, 3),
    "sub:TACL": ("TACL", "suffix", None, 3),
}
UNNUMBERED = {"sub:FUP"}  # FUP lists its errors by text; a bare 'Message 1024' there is a page number the chunker mistook
# MEASURE titles are flat (no command chapter), so a heading counts only when its first word is a MEASCOM verb
MEASCOM_VERBS = {"ADD", "ASSUME", "COMMENTS", "DELETE", "ENV", "EXIT", "FC", "HELP", "HISTORY", "INFO", "LIST", "LISTACTIVE",
                 "LISTALL", "LISTENAME", "LISTGNAME", "LISTPNAME", "LOG", "OBEY", "OSSPATH", "OUT", "PAGESIZE", "RESET", "RUN",
                 "SET", "SETPROMPT", "SHOW", "SQLCATALOG", "SQLSCHEMA", "START", "STATUS", "STOP", "SWAPVOL", "SYSTEM", "TIME",
                 "VOLUME", "WARNINGS"}

_PAGE = re.compile(r"\s*\(txt p\.(\d+)\)\s*$")
_PART = re.compile(r"\s*\(part \d+\)")
_WORD = r"[A-Z][A-Z0-9_-]*(?:\[[A-Z|]+\])?"          # TMFCOM verbs, CONFIG[URE], RUN[D|V], REFRESH-CODE
_NOTE = r"(?:General )?(?:Guidelines|Examples?|Usage Notes?|Considerations|Related Commands?|Output Displayed)(?: \([^)]*\))?"
_NOTE_ONLY, _NOTE_TAIL = re.compile(_NOTE), re.compile(r"\s+" + _NOTE + "$")
_MESSAGE = re.compile(r"^(Message|MEAS)\s+(\d{2,5})$")
_OPTION = re.compile(r"^([A-Z]+) Option(?: \([^)]*\))?$")


# ---------------------------------------------------------------- pure parts (unit-tested)
def profile(system_id):
    return PROFILES.get(system_id) or ((system_id or "").split(":", 1)[-1].upper(), "suffix", None, 3)


def split_title(section):
    """'TMFCOM Commands > STATUS TMF (part 2) (txt p.296)' -> (chapter, leaf, page)."""
    s = section or ""
    m = _PAGE.search(s)
    page = int(m.group(1)) if m else 0
    s = _PART.sub("", _PAGE.sub("", s))
    chapter, sep, leaf = s.partition(" > ")
    return (chapter.strip(), leaf.strip(), page) if sep else ("", s.strip(), page)


def expand(head):
    """All spellings of a heading with optional parts: CONFIG[URE] -> [CONFIGURE, CONFIG]; RUN[D|V] -> [RUND, RUNV, RUN]."""
    out = [""]
    for part in re.split(r"(\[[A-Z|]+\])", head):
        if part.startswith("["):
            out = [o + alt for o in out for alt in part[1:-1].split("|")] + out
        else:
            out = [o + part for o in out]
    return list(dict.fromkeys(out))


def _head(piece, style, max_words):
    """The command named by one title piece, or None."""
    p = piece.strip()
    if style == "suffix":
        m = re.fullmatch(r"(.+?) Command", p)
        p = m.group(1) if m else ""
    elif style == "option":
        m = _OPTION.match(p)
        p = m.group(1) if m else ""
    else:  # bare / verbs
        while _NOTE_TAIL.search(p):
            p = _NOTE_TAIL.sub("", p)
        p = re.sub(r"^([A-Z]+): .+$", r"\1", p)        # "COPY: Copy Form"
        p = re.sub(r" entity-type$", "", p)             # MEASCOM "LIST entity-type" names the verb itself
    if not re.fullmatch(rf"{_WORD}(?: {_WORD})*", p) or len(p.split()) > max_words:
        return None
    if style == "verbs" and p.split()[0] not in MEASCOM_VERBS:
        return None
    return p


def command_heads(system_id, chapter, leaf):
    """Command headings named by a section title (a range 'A .. B' names both ends; 'A - note' ignores the note)."""
    _, style, in_chapter, max_words = profile(system_id)
    if in_chapter and chapter != in_chapter:
        return []
    heads = []
    for part in leaf.split(" .. "):
        pieces = part.split(" - ")
        if style == "option":
            pieces = pieces[:1]
        found = []
        for pc in pieces:
            h = _head(pc, style, max_words)
            if h:
                found.append(h)
            elif not _NOTE_ONLY.fullmatch(pc.strip()):
                found = []  # an unrecognised piece: this is not a plain command heading
                break
        heads += [h for h in found if h not in heads]
    return heads


def message_numbers(leaf, text, page=0):
    """[(number as written, title prefix)] for a message section: the ends of 'Message 3150 .. Message 3161' plus the bare
    number lines in the text that fall between them (messages are merged into one section when they are short)."""
    parts = leaf.split(" .. ")
    ends = [(m.group(2), m.group(1)) for m in (_MESSAGE.match(p.strip()) for p in parts) if m]
    if not ends or not _MESSAGE.match(parts[0].strip()):  # 'PURGE Examples .. Message 1024' is a command section
        return []
    lo, hi = min(int(n) for n, _ in ends), max(int(n) for n, _ in ends)
    out, last = list(ends), lo
    for m in re.finditer(r"(?m)^\s*(\d{2,5})\s*$", text or ""):
        n = int(m.group(1))
        if lo < n <= hi and n != page and n > last and m.group(1) not in [o[0] for o in out]:
            out.append((m.group(1), ends[0][1]))
            last = n
    return sorted(out, key=lambda o: int(o[0]))


def slug(s):
    return re.sub(r"[^a-z0-9]+", "-", s.lower()).strip("-") or "x"


def sub_slug(system_id):
    return slug(system_id.split(":", 1)[-1])


def risk_of(head):
    return "read_only" if head.split()[0] in READ_ONLY else "unknown"


def norm_key(prefix, name):
    """Words that identify a command regardless of case, spacing, plural, [optional] parts, tool prefix and arguments:
    'TMFCOM STATUS AUDITTRAIL, DETAIL' and 'STATUS AUDITTRAILS' -> ('status', 'audittrail')."""
    words = []
    for w in re.split(r"[,\\$(]", expand(name)[0])[0].split():
        if len(words) >= 2 and not w.isupper():  # 'FUP LISTOPENS file': a lowercase word after the verb is an argument
            break
        words.append(w)
    t = tokens(" ".join(words))
    pre = tokens(prefix)
    return tuple(t[len(pre):] if t[:len(pre)] == pre else t)


def same_command(auto_key, cur_key):
    """Equal words, or the curated one is the auto command plus arguments (needs >= 2 words so 'STATUS' never absorbs
    'STATUS DISK ...')."""
    return bool(auto_key) and (auto_key == cur_key or (len(auto_key) >= 2 and cur_key[:len(auto_key)] == auto_key))


def aliases_for(prefix, head, taken):
    """Lowercase spellings an operator may type. Never a single word ('add', 'status', 'info'): every alias is the tool
    name plus the command, or a multi-word command on its own; anything already used by another entity is dropped."""
    out = []
    for form in expand(head):
        cands = [f"{prefix} {form}".lower()] + ([form.lower()] if len(form.split()) >= 2 else [])
        for a in cands:
            t = tuple(tokens(a))
            if len(t) >= 2 and t not in taken and a not in out:
                out.append(a)
    return out


def extract_rows(system_id, chunks, curated=(), taken=frozenset()):
    """Pure core. chunks = [(id, section, text)], curated = [{'id','name'}] command entities of this subsystem,
    taken = token tuples already used as a name/alias by other entities.
    Returns {'entities': [...], 'edges': [(src, rel, dst, source_id)], 'merges': [(auto name, curated id)]}."""
    prefix = profile(system_id)[0]
    sub, cur = sub_slug(system_id), [(norm_key(prefix, c["name"]), c["id"]) for c in curated]
    ents, edges, merges, merged = {}, {}, [], {}

    def link(src, dst, source):
        edges.setdefault((src, "about", dst), source)

    for cid, section, text in sorted(chunks, key=lambda c: (split_title(c[1])[2], c[0])):
        chapter, leaf, page = split_title(section)
        for head in command_heads(system_id, chapter, leaf):
            name = f"{prefix} {head}"
            eid = f"cmd:auto:{sub}:{slug(expand(head)[0])}"
            if eid in merged or eid in ents:  # the first section (lowest page) is the defining one
                continue
            key = norm_key(prefix, name)
            hit = next((i for k, i in cur if same_command(key, k)), None)
            if hit:
                merged[eid] = hit
                merges.append((name, hit))
                link(cid, hit, cid)
                continue
            ents[eid] = {"id": eid, "kind": "command", "name": name, "parent_id": system_id,
                         "aliases": aliases_for(prefix, head, taken),
                         "props": {"auto": True, "risk": risk_of(head), "source_id": cid}}
            link(cid, eid, cid)
            link(eid, system_id, cid)
        for num, word in ([] if system_id in UNNUMBERED else message_numbers(leaf, text, page)):
            eid = f"evt:auto:{sub}:{num}"
            if eid in ents:
                continue
            alias = [f"{w.lower()} {num}" for w in ([word] if word == "MEAS" else re.findall(
                rf"(?m)^\W*([A-Z][A-Z-]{{2,}})\s+{num}\b", text or "")[:1]) if w not in ("MESSAGE",)]
            alias = [a for a in alias if tuple(tokens(a)) not in taken]
            # number is a string on purpose: resolve() matches int props.number (EMS events) against bare numbers in questions
            ents[eid] = {"id": eid, "kind": "event", "name": f"{prefix} message {num}", "parent_id": system_id,
                         "aliases": alias, "props": {"auto": True, "number": num, "source_id": cid}}
            link(cid, eid, cid)
            link(eid, system_id, cid)
    return {"entities": list(ents.values()), "edges": [(s, r, d, src) for (s, r, d), src in edges.items()], "merges": merges}


# ---------------------------------------------------------------- db
def _alias_tokens(rows):
    out = set()
    for _id, name, aliases in rows:
        for a in [name, *(aliases or [])]:
            t = tuple(tokens(a))
            if t:
                out.add(t)
    return out


def extract(conn, system_id=None):
    """extract(conn, system_id=None) -> {'entities', 'edges', 'merges'} for one subsystem (or every subsystem with sections).
    Reads only; nothing is written."""
    subs = [system_id] if system_id else subsystems(conn)
    res = {"entities": [], "edges": [], "merges": []}
    for sub in subs:
        chunks = conn.execute("SELECT id, section, text FROM doc_chunk WHERE system_id = %s "
                              "AND (valid_to IS NULL OR valid_to > CURRENT_DATE) ORDER BY id", (sub,)).fetchall()
        curated = [{"id": i, "name": n} for i, n in conn.execute(
            "SELECT id, name FROM entity WHERE kind = 'command' AND parent_id = %s "
            "AND COALESCE(props->>'auto', '') <> 'true'", (sub,))]
        taken = _alias_tokens(conn.execute(
            "SELECT id, name, aliases FROM entity WHERE COALESCE(props->>'auto', '') <> 'true' OR parent_id IS DISTINCT FROM %s",
            (sub,)))
        r = extract_rows(sub, chunks, curated, taken)
        for k in res:
            res[k] += r[k]
    # an alias claimed by two auto entities (different subsystems) would make resolve() tie: drop it from both
    count = {}
    for e in res["entities"]:
        for a in {tuple(tokens(x)) for x in e["aliases"]}:
            count[a] = count.get(a, 0) + 1
    for e in res["entities"]:
        e["aliases"] = [a for a in e["aliases"] if count[tuple(tokens(a))] == 1]
    return res


def sync(conn, system_id):
    """Upsert what extract() finds for one subsystem and prune what no longer holds (sections removed, headings changed):
    stale auto-docs edges go, and so do auto entities left with no section, unless a human/curated edge uses them.
    Idempotent. Caller commits. Returns per-run counts."""
    res = extract(conn, system_id)
    subs = [system_id]
    new_e = new_x = 0
    for e in res["entities"]:
        new_e += conn.execute("INSERT INTO entity (id, kind, name, aliases, parent_id, props) VALUES (%s,%s,%s,%s,%s,%s) "
                              "ON CONFLICT (id) DO NOTHING", (e["id"], e["kind"], e["name"], e["aliases"], e["parent_id"],
                                                              Json(e["props"]))).rowcount
    for src, rel, dst, source in res["edges"]:
        new_x += conn.execute("INSERT INTO edge (src, rel, dst, weight, source_id, created_by) VALUES (%s,%s,%s,1,%s,%s) "
                              "ON CONFLICT (src, rel, dst) DO NOTHING", (src, rel, dst, source, CREATED_BY)).rowcount
    want_e = {e["id"] for e in res["entities"]}
    want_x = {(s, r, d) for s, r, d, _ in res["edges"]}
    gone_x = gone_e = 0
    for sub in subs:
        for s, r, d in conn.execute(
                "SELECT src, rel, dst FROM edge WHERE created_by = %s AND (src IN (SELECT id FROM doc_chunk WHERE system_id = %s) "
                "OR src IN (SELECT id FROM entity WHERE parent_id = %s))", (CREATED_BY, sub, sub)).fetchall():
            if (s, r, d) not in want_x:
                gone_x += conn.execute("DELETE FROM edge WHERE src = %s AND rel = %s AND dst = %s AND created_by = %s",
                                       (s, r, d, CREATED_BY)).rowcount
        for (eid,) in conn.execute("SELECT id FROM entity WHERE props->>'auto' = 'true' AND parent_id = %s", (sub,)).fetchall():
            if eid in want_e:
                continue
            if conn.execute("SELECT 1 FROM edge WHERE (src = %s OR dst = %s) AND created_by NOT IN ('auto', %s) LIMIT 1",
                            (eid, eid, CREATED_BY)).fetchone():
                continue
            conn.execute("DELETE FROM edge WHERE (src = %s OR dst = %s) AND created_by IN ('auto', %s)", (eid, eid, CREATED_BY))
            gone_e += conn.execute("DELETE FROM entity WHERE id = %s", (eid,)).rowcount
    return {"commands": sum(e["kind"] == "command" for e in res["entities"]),
            "messages": sum(e["kind"] == "event" for e in res["entities"]), "merges": res["merges"],
            "entities_new": new_e, "edges_new": new_x, "entities_removed": gone_e, "edges_removed": gone_x}


def subsystems(conn):
    return [r[0] for r in conn.execute("SELECT DISTINCT system_id FROM doc_chunk WHERE system_id LIKE 'sub:%' ORDER BY 1")]


def rebuild(conn):
    """Delete ONLY what this module owns (props.auto entities, created_by = 'auto-docs' edges, auto mentions of those)."""
    ids = [r[0] for r in conn.execute("SELECT id FROM entity WHERE props->>'auto' = 'true'")]
    conn.execute("DELETE FROM edge WHERE created_by = %s", (CREATED_BY,))
    if ids:
        conn.execute("DELETE FROM edge WHERE created_by = 'auto' AND (src = ANY(%s::text[]) OR dst = ANY(%s::text[]))", (ids, ids))
        conn.execute("DELETE FROM entity WHERE id = ANY(%s::text[])", (ids,))
    return len(ids)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--subsystem", help="e.g. sub:TMF (default: every subsystem that has manual sections)")
    ap.add_argument("--dry-run", action="store_true", help="extract and print counts, write nothing")
    ap.add_argument("--rebuild", action="store_true", help="first delete the auto-docs rows, then re-extract")
    a = ap.parse_args(argv)
    with psycopg.connect(settings.DATABASE_URL) as conn:
        if a.dry_run:
            res = extract(conn, a.subsystem)
            per = {}
            for e in res["entities"]:
                per.setdefault(e["parent_id"], {"commands": 0, "messages": 0})["commands" if e["kind"] == "command" else "messages"] += 1
            for sub, c in sorted(per.items()):
                print(f"{sub:18} commands={c['commands']:4} messages={c['messages']:4}")
            print(f"merges={len(res['merges'])} edges={len(res['edges'])} (dry run, nothing written)")
            for name, cid in res["merges"]:
                print(f"  merge {name} -> {cid}")
            return 0
        if a.rebuild:
            print(f"rebuild: removed {rebuild(conn)} auto entities")
        for sub in [a.subsystem] if a.subsystem else subsystems(conn):
            out = sync(conn, sub)
            print(f"{sub:18}", {k: v for k, v in out.items() if k != "merges"}, f"merges={len(out['merges'])}")
            for name, cid in out["merges"]:
                print(f"  merge {name} -> {cid}")
        conn.commit()
    return 0


if __name__ == "__main__":
    sys.exit(main())
