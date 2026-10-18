"""Monitoring-tool connectors and alert priority: Prognosis rows, MOMI exports, node/message mapping, High/Medium/Low.
No DB, no network."""
from backend.integrations.mapping import message_refs, node_id
from backend.integrations.momi import parse_export
from backend.integrations.prognosis import parse_rows
from backend.watcher.rules import priority


def test_prognosis_rows_become_alarms():
    rows = [{"ProblemId": "P-1", "NodeName": "\\PROD", "Category": "TMF", "Description": "TMF 185: audit file pinned",
             "Severity": "Major", "TimeRaised": "2026-10-17T14:00:00Z"},
            {"ProblemId": "P-2", "NodeName": "\\PROD", "Description": ""}]
    out = parse_rows(rows)
    assert len(out) == 1 and out[0]["ext_id"] == "P-1" and out[0]["severity"] == "critical" and out[0]["tool"] == "prognosis"
    assert parse_rows({"data": rows})[0]["text"] == "TMF 185: audit file pinned"


def test_momi_template_blocks_and_log_lines():
    block = ("tool=momi\nnode=PROD1\nstate=SET\ndate=2026-10-17\ntime=14:02:11\nalarm=DISK STATE\naction=ACT-CRITICAL\n"
             "entity=$DATA01\ntext=DISK 5032: mirror drive down\n\n"
             "tool=momi\nnode=PROD1\nstate=CLEARED\ndate=2026-10-17\ntime=14:05:00\nalarm=X\ntext=cleared one\n")
    out = parse_export(block)
    assert len(out) == 1 and out[0]["severity"] == "critical" and out[0]["ts"] == "2026-10-17T14:02:11Z"
    log = "2026-10-17\t14:02:11\t\\DR\tProcess $SETL1 is not running\n2026-10-17\t14:03:00\t\\DR\t\n"
    out = parse_export(log)
    assert len(out) == 1 and out[0]["node_text"] == "\\DR"
    assert parse_export("2026-10-17\t14:02:11\t\xa0PROD\tFile $x is 81% full")[0]["node_text"] == "PROD"  # hard space stripped


def test_nodes_and_message_numbers():
    assert (node_id("\\PROD"), node_id("PROD1"), node_id("\\DR"), node_id("SYS7")) == ("node:PROD", "node:PROD", "node:DR", None)
    assert message_refs("TMF 185 then PATHWAY 1034, DISK-5032, cpu 101") == [("TMF", 185), ("PATHWAY", 1034), ("DISK", 5032), ("CPU", 101)]
    assert message_refs("File $DATA1 is 81% full") == []


def test_priority_high_medium_low():
    level, why = priority("pattern", "node:PROD", "evt:TMF-185", ["evt:TMF-187"], 40, "warning")
    assert level == "High" and "on production (\\PROD)" in why and any("leads to" in w for w in why)
    assert priority("chain", "node:DR", "evt:TMF-185", ["evt:TMF-187"], None, "info")[0] == "Medium"
    assert priority("tool", "node:DR", "evt:auto:tmf:7091", [], None, "warning")[0] == "Low"
    assert priority("tool", "node:PROD", "evt:auto:tmf:7091", [], None, "warning")[0] == "Medium"
