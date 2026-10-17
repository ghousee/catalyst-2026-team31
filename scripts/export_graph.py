"""Export the knowledge graph to one self-contained page: docs/knowledge_graph.html.

    python scripts/export_graph.py

Needs the DB (after `python -m backend.graph.load`). Loads one pinned script (vis-network from cdnjs) when opened.
Manual text is NOT exported: doc nodes carry only the section title, edition and id. Veteran notes are our own
fictional content and are included. Edges of kind applies_to (scope plumbing) are left out to keep the picture readable.
"""
import json
import sys
from pathlib import Path

import psycopg

from backend import settings

OUT = Path(__file__).resolve().parents[1] / "docs" / "knowledge_graph.html"
COLORS = {"subsystem": "#6b7280", "event": "#dc2626", "object": "#2563eb", "metric": "#0891b2", "command": "#16a34a",
          "person": "#9333ea", "heuristic": "#f59e0b", "doc": "#94a3b8"}
KIND = {"system": "subsystem"}


def build(conn):
    q = lambda sql: conn.execute(sql).fetchall()
    nodes, ids = {}, set()
    for i, kind, name, aliases, props in q("SELECT id, kind, name, aliases, props FROM entity WHERE kind NOT IN ('site','version')"):
        k = KIND.get(kind, kind)
        nodes[i] = {"id": i, "label": name.split(" - ")[0][:34], "kind": k, "color": COLORS[k],
                    "info": {"name": name, "aliases": aliases or [], **({"props": props} if props else {})}}
    for i, name, role, years, avail in q("SELECT id, name, role, years, availability FROM person"):
        nodes[i] = {"id": i, "label": name, "kind": "person", "color": COLORS["person"],
                    "info": {"name": name, "role": role, "years": years, "availability": avail}}
    for i, owner, status, kind, trig, call, sys_id, ver, site, via in q(
            "SELECT id, owner_id, status, kind, trigger_text, call_text, system_id, version_id, site_id, captured_via FROM heuristic"):
        nodes[i] = {"id": i, "label": i, "kind": "heuristic", "color": COLORS["heuristic"],
                    "info": {"owner": owner, "status": status, "type": kind, "scope": f"{site or 'all nodes'} / {ver or 'all series'} / {sys_id}",
                             "captured_via": via, "when": trig, "call": call}}
    chunks = {r[0]: r for r in q("SELECT id, section, edition FROM doc_chunk WHERE id IN (SELECT src FROM edge UNION SELECT dst FROM edge UNION SELECT source_id FROM edge)")}
    edges = []
    for src, rel, dst, w, sid in q("SELECT src, rel, dst, weight, source_id FROM edge WHERE rel <> 'applies_to'"):
        for end in (src, dst):
            if end in chunks and end not in nodes:
                _, section, edition = chunks[end]
                nodes[end] = {"id": end, "label": (section or end).split(">")[-1].split("(txt")[0].strip()[:30], "kind": "doc",
                              "color": COLORS["doc"], "info": {"id": end, "section": section, "edition": edition}}
        if src in nodes and dst in nodes:
            edges.append({"from": src, "to": dst, "label": rel, "title": f"source: {sid}", "arrows": "to",
                          "info": {"rel": rel, "weight": w, "source_id": sid}})
    return list(nodes.values()), edges


PAGE = """<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Knowledge graph</title>
<script src="https://cdnjs.cloudflare.com/ajax/libs/vis-network/9.1.9/standalone/umd/vis-network.min.js"></script>
<style>
 body{margin:0;font:14px system-ui,sans-serif;display:flex;height:100vh;color:#111}
 #net{flex:1}#side{width:340px;padding:12px 16px;overflow:auto;border-left:1px solid #ddd;background:#fafafa}
 .dot{display:inline-block;width:10px;height:10px;border-radius:50%;margin-right:4px}
 pre{white-space:pre-wrap;font-size:12px} h3{margin:.2em 0} .leg span{display:inline-block;margin:0 10px 4px 0}
 @media(max-width:700px){body{flex-direction:column}#side{width:auto;height:35vh;border:0}}
</style></head><body>
<div id="net"></div>
<div id="side"><h3>Knowledge graph</h3>
<p>Fictional veterans and illustrative knowledge for the demo. Click a node or edge. Doc nodes show section titles only.</p>
<div class="leg" id="leg"></div><pre id="info">Nothing selected.</pre></div>
<script>
const DATA = __DATA__, COLORS = __COLORS__;
document.getElementById('leg').innerHTML = Object.entries(COLORS).map(([k,c])=>`<span><i class="dot" style="background:${c}"></i>${k}</span>`).join('');
const nodes = new vis.DataSet(DATA.nodes.map(n=>({id:n.id,label:n.label,color:n.color,font:{size:12},shape:n.kind==='doc'?'box':'dot',size:n.kind==='subsystem'?22:14})));
const edges = new vis.DataSet(DATA.edges.map((e,i)=>({...e,id:i,font:{size:9,align:'middle'},color:{color:'#9ca3af'},smooth:{type:'continuous'}})));
const net = new vis.Network(document.getElementById('net'),{nodes,edges},{physics:{solver:'forceAtlas2Based',stabilization:{iterations:250}},interaction:{hover:true}});
const out = document.getElementById('info');
net.on('click', p=>{
  if(p.nodes.length){const n=DATA.nodes.find(x=>x.id===p.nodes[0]);out.textContent=n.id+'  ['+n.kind+']\\n\\n'+JSON.stringify(n.info,null,2);}
  else if(p.edges.length){const e=DATA.edges[p.edges[0]];out.textContent=e.from+'\\n  -'+e.label+'->\\n'+e.to+'\\n\\n'+JSON.stringify(e.info,null,2);}
  else out.textContent='Nothing selected.';
});
</script></body></html>
"""


def main():
    with psycopg.connect(settings.DATABASE_URL) as conn:
        nodes, edges = build(conn)
    OUT.write_text(PAGE.replace("__DATA__", json.dumps({"nodes": nodes, "edges": edges}, default=str))
                   .replace("__COLORS__", json.dumps(COLORS)), encoding="utf-8")
    print(f"wrote {OUT} ({len(nodes)} nodes, {len(edges)} edges)")


if __name__ == "__main__":
    sys.exit(main())
