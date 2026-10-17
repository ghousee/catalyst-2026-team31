"""Auto-built graph (backend/graph/from_docs.py): title parsing, dedupe against curated commands, no generic aliases.
Pure functions only (no DB)."""
from backend.graph import from_docs as f
from backend.graph.query import match_entities, tokens


def heads(sub, section):
    chapter, leaf, _ = f.split_title(section)
    return f.command_heads(sub, chapter, leaf)


def test_split_title_strips_page_and_part():
    assert f.split_title("TMFCOM Commands > ADD DUMPS (part 2) (txt p.59)") == ("TMFCOM Commands", "ADD DUMPS", 59)
    assert f.split_title("ADD DISK Command (txt p.199)") == ("", "ADD DISK Command", 199)


def test_commands_per_style():
    assert heads("sub:SCF-STORAGE", "ADD DISK Command (part 13) (txt p.204)") == ["ADD DISK"]
    assert heads("sub:SCF-STORAGE", "ALTER Command .. ALTER DISK Command (txt p.228)") == ["ALTER", "ALTER DISK"]
    assert heads("sub:TMF", "TMFCOM Commands > STATUS AUDITTRAIL - Output Displayed (txt p.297)") == ["STATUS AUDITTRAIL"]
    assert heads("sub:TMF", "TMFCOM Commands > ENABLE AUDITDUMP .. ENABLE AUDITDUMP - ENABLE BEGINTRANS (txt p.169)") == \
        ["ENABLE AUDITDUMP", "ENABLE BEGINTRANS"]
    assert heads("sub:FUP", "FUP Commands > CONFIG[URE] Guidelines (part 2) (txt p.82)") == ["CONFIG[URE]"]
    assert heads("sub:FUP", "FUP Commands > COPY: Copy Form (txt p.86)") == ["COPY"]
    assert heads("sub:PEEK", "PEEK Syntax and Examples > PAGING Option (txt p.59)") == ["PAGING"]
    assert heads("sub:PEEK", "PEEK Syntax and Examples > INIT Option (Super Group Only) (part 2) (txt p.43)") == ["INIT"]
    assert heads("sub:MEASURE", "LIST entity-type (part 3) (txt p.70)") == ["LIST"]
    assert heads("sub:MEASURE", "RUN .. SET PLOT (txt p.104)") == ["RUN", "SET PLOT"]


def test_non_commands_are_rejected():
    assert heads("sub:TMF", "TMFCOM Commands > Examples: (part 4) (txt p.163)") == []
    assert heads("sub:TMF", "TMFCOM Command Reference Summary > ABORT TRANSACTION (txt p.592)") == []  # summary chapter
    assert heads("sub:TMF", "TMFCOM Commands > File Names and Process Identifiers (txt p.40)") == []
    assert heads("sub:FUP", "FUP Commands > INFO DETAIL Listing Format (part 3) (txt p.151)") == []
    assert heads("sub:FUP", "FUP Commands > ERROR - filename: ERR 11 .. ERROR - filename: ERR 59 (txt p.255)") == []
    assert heads("sub:FUP", "FUP Commands > OVERFLOW OF TABLE .. OWNER NOT PRESERVED AT DESTINATION (txt p.267)") == []
    assert heads("sub:FUP", "FUP Overview > CREATE (txt p.47)") == []
    assert heads("sub:SCF-STORAGE", "Adding a Disk (txt p.82)") == []
    assert heads("sub:SCF-STORAGE", "Overview of Storage Subsystem Commands (txt p.190)") == []
    assert heads("sub:TACL", "Built-In Functions and Variables > #ARGUMENT Built-In Function (txt p.421)") == []
    assert heads("sub:PEEK", "PEEK Syntax and Examples > Elements of the PAGING Display (txt p.60)") == []
    assert heads("sub:PEEK", "PEEK Syntax and Examples > CME Option - For releases before H06.16/J06.05 RVU (txt p.38)") == ["CME"]
    assert heads("sub:MEASURE", "CPU 159 (part 2) (txt p.161)") == []
    assert heads("sub:MEASURE", "MEASOPEN (txt p.421)") == []                   # API procedure, not a MEASCOM verb
    assert heads("sub:MEASURE", "Syntax (txt p.81)") == []


def test_messages():
    assert f.message_numbers("Message 3119", "3119\n\ntext", 280) == [("3119", "Message")]
    assert f.message_numbers("Message 3150 .. Message 3161", "3150\n\na\n\n3155\n\nb\n\n3161\n\nc\n311\n", 311) == \
        [("3150", "Message"), ("3155", "Message"), ("3161", "Message")]
    assert f.message_numbers("MEAS 3010 .. MEAS 3011", "x", 456) == [("3010", "MEAS"), ("3011", "MEAS")]
    assert f.message_numbers("Message 00011 .. Message 00012", "", 301) == [("00011", "Message"), ("00012", "Message")]
    assert f.message_numbers("PURGE Examples .. Message 1024", "", 193) == []
    assert f.message_numbers("PEEK Default Listing Format", "", 29) == []


def test_slug_and_dedupe_normalisation():
    assert f.expand("CONFIG[URE]") == ["CONFIGURE", "CONFIG"]
    assert f.expand("RUN[D|V]") == ["RUND", "RUNV", "RUN"]
    assert f.slug("ADD DISK") == "add-disk"
    k = f.norm_key("TMFCOM", "TMFCOM STATUS AUDITTRAIL")
    assert k == f.norm_key("TMFCOM", "TMFCOM STATUS AUDITTRAIL, DETAIL") == f.norm_key("TMFCOM", "STATUS AUDITTRAILS")
    assert f.norm_key("FUP", "FUP LISTOPENS file") == ("listopen",) == f.norm_key("FUP", "FUP LISTOPENS")
    assert f.norm_key("SCF", "SCF STATUS DISK $vol, DETAIL") == f.norm_key("SCF", "STATUS DISK")
    assert f.same_command(("status", "audittrail"), ("status", "audittrail"))
    assert f.same_command(("alter", "audittrail"), ("alter", "audittrail", "mat"))   # curated = command + arguments
    assert not f.same_command(("status",), ("status", "disk"))                       # one word never absorbs another command


CURATED = [{"id": "cmd:tmfcom.status_tmf", "name": "TMFCOM STATUS TMF"}]


def test_extract_reuses_curated_and_links_sections():
    chunks = [("doc:TMF:status-tmf", "TMFCOM Commands > STATUS TMF (txt p.325)", ""),
              ("doc:TMF:add-dumps", "TMFCOM Commands > ADD DUMPS (txt p.58)", ""),
              ("doc:TMF:add-dumps-part-2", "TMFCOM Commands > ADD DUMPS (part 2) (txt p.59)", ""),
              ("doc:TMF:msg-3119", "TMFCOM Messages > Message 3119 (txt p.400)", "3119\n\nbad thing")]
    r = f.extract_rows("sub:TMF", chunks, CURATED)
    ids = {e["id"] for e in r["entities"]}
    assert ids == {"cmd:auto:tmf:add-dumps", "evt:auto:tmf:3119"}               # STATUS TMF merged, not duplicated
    assert r["merges"] == [("TMFCOM STATUS TMF", "cmd:tmfcom.status_tmf")]
    edges = {(s, rel, d): src for s, rel, d, src in r["edges"]}
    assert edges[("doc:TMF:status-tmf", "about", "cmd:tmfcom.status_tmf")] == "doc:TMF:status-tmf"
    assert ("doc:TMF:add-dumps", "about", "cmd:auto:tmf:add-dumps") in edges      # first part defines the entity
    assert ("doc:TMF:add-dumps-part-2", "about", "cmd:auto:tmf:add-dumps") not in edges
    assert ("cmd:auto:tmf:add-dumps", "about", "sub:TMF") in edges
    ev = next(e for e in r["entities"] if e["kind"] == "event")
    assert ev["name"] == "TMFCOM message 3119" and ev["props"] == {"auto": True, "number": "3119", "source_id": "doc:TMF:msg-3119"}
    assert f.extract_rows("sub:TMF", chunks, CURATED) == r                         # deterministic


def test_risk_never_read_only_for_state_changing_verbs():
    for h in ("ADD DISK", "ABORT TRANSACTION", "ALTER AUDITTRAIL", "DELETE DUMPS", "RESET", "STOP", "START TMF", "SET", "PURGE"):
        assert f.risk_of(h) == "unknown"
    for h in ("STATUS TMF", "INFO DISK", "LISTOPENS", "DISPLAY OPERATIONS", "SHOW PLOT", "HELP"):
        assert f.risk_of(h) == "read_only"


def test_no_generic_aliases():
    for head in ("ADD", "STATUS", "INFO", "HELP", "ADD DISK", "STATUS AUDITTRAIL", "CONFIG[URE]", "PAGING"):
        for a in f.aliases_for("TOOL", head, frozenset()):
            assert len(tokens(a)) >= 2, a
    assert f.aliases_for("SCF", "ADD", frozenset()) == ["scf add"]                       # never plain 'add'
    assert "add disk" in f.aliases_for("SCF", "ADD DISK", frozenset())
    assert f.aliases_for("FUP", "CONFIG[URE]", frozenset()) == ["fup configure", "fup config"]
    taken = {tuple(tokens("add disk"))}
    assert "add disk" not in f.aliases_for("SCF", "ADD DISK", taken)                    # another entity already uses it
    chunks = [("doc:S:a", "ADD Command (txt p.1)", ""), ("doc:S:b", "STATUS Command (txt p.2)", ""),
              ("doc:S:c", "INFO DISK Command (txt p.3)", ""), ("doc:S:m", "Message 00011 (txt p.4)", "00011\n\nSTORAGE 00011 x")]
    for e in f.extract_rows("sub:SCF-STORAGE", chunks)["entities"]:
        assert all(len(tokens(a)) >= 2 for a in [e["name"], *e["aliases"]]), e


def test_auto_entities_do_not_hijack_resolve():
    chunks = [("doc:S:a", "ADD Command (txt p.1)", ""), ("doc:S:b", "STATUS Command (txt p.2)", ""),
              ("doc:S:m", "Message 00011 (txt p.4)", "00011\n\nSTORAGE 00011 x")]
    auto = f.extract_rows("sub:SCF-STORAGE", chunks)["entities"]
    ents = [{**e, "props": e["props"]} for e in auto]
    for q in ("add a new volume", "what is the status of the system", "info about the 11 cpus", "show 00011 times"):
        assert match_entities(ents, q) == {}, q
    assert "evt:auto:scf-storage:00011" in match_entities(ents, "got storage 00011 on the console")
