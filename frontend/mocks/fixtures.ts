// Fixtures matching docs/API_CONTRACT.md v2 exactly. All people and data are fictional.
import type { Claim, DocSource, Expert, HeuristicSource, Source } from "@/lib/types";

export const NODES = [
  { id: "node:PROD", display: "\\PROD" },
  { id: "node:DR", display: "\\DR" },
];

export const SUBSYSTEMS: Record<string, string> = {
  "sub:TMF": "TMF",
  "sub:SCF-STORAGE": "Storage",
  "sub:PATHWAY": "Pathway",
  "sub:PEEK": "CPU",
  "sub:TACL": "TACL",
};

export const TRANSID = "\\PROD(1).3.45678";

const doc = (
  id: string,
  title: string,
  part_number: string,
  section: string,
  applies_to: string,
  snippet: string,
): DocSource => ({ id, kind: "doc", title, part_number, section, applies_to, snippet });

export const DOC_SOURCES: DocSource[] = [
  doc(
    "doc:TMF-Reference:ch121.185",
    "TMF Reference Manual",
    "TMF-REF",
    "Event 185 — audit file pinned",
    "L/J-series · all nodes",
    "TMF 185 is reported when an audit trail file cannot be released because a transaction that wrote to it is still active. The file stays pinned until that transaction commits or aborts.",
  ),
  doc(
    "doc:TMF-Reference:ch121.187",
    "TMF Reference Manual",
    "TMF-REF",
    "Event 187 — audit trail critically full",
    "L/J-series · all nodes",
    "When the audit trail is critically full TMF disables BEGINTRANS. Long-running transactions should be allowed to complete or be resolved by the operator.",
  ),
  doc(
    "doc:TMF-Reference:ch4.status-audittrail",
    "TMF Reference Manual",
    "TMF-REF",
    "TMFCOM STATUS AUDITTRAIL",
    "L/J-series · all nodes",
    "STATUS AUDITTRAIL, DETAIL displays the capacity used by the active audit trail and, for each pinned audit file, the reason it cannot be released.",
  ),
  doc(
    "doc:TMF-Reference:ch4.status-transaction",
    "TMF Reference Manual",
    "TMF-REF",
    "TMFCOM STATUS TRANSACTION",
    "L/J-series · all nodes",
    "STATUS TRANSACTION lists active transactions with their transaction identifier, state, age and owning process.",
  ),
  doc(
    "doc:TMF-Reference:ch4.abort-transaction",
    "TMF Reference Manual",
    "TMF-REF",
    "TMFCOM ABORT TRANSACTION",
    "L/J-series · all nodes",
    "ABORT TRANSACTION backs out the named transaction. Applications waiting on the transaction receive an error and are expected to retry.",
  ),
  doc(
    "doc:TMF-Reference:ch4.status-tmf",
    "TMF Reference Manual",
    "TMF-REF",
    "TMFCOM STATUS TMF",
    "L/J-series · all nodes",
    "STATUS TMF reports the TMF subsystem state, BEGINTRANS enablement and the number of active transactions.",
  ),
  doc(
    "doc:SCF-Storage:ch6.status-disk",
    "SCF Reference Manual for the Storage Subsystem",
    "SCF-STOR",
    "STATUS DISK",
    "L-series · all nodes",
    "STATUS DISK, DETAIL shows the state of the primary and mirror drives, the revive status and the process pair path state for a disk volume.",
  ),
  doc(
    "doc:Pathway-Ref:ch5.status-server",
    "Pathway TS/MP System Management Manual",
    "PATHWAY-SM",
    "PATHCOM STATUS SERVER",
    "L/J-series · all nodes",
    "STATUS SERVER * lists every server class with its running, pending and maximum process counts.",
  ),
  doc(
    "doc:PEEK-Ref:ch2.cpu",
    "PEEK Utility Reference",
    "PEEK-REF",
    "PEEK /CPU n/",
    "L-series · all nodes",
    "PEEK displays processor-level counters for the CPU named in the /CPU n/ option, including busy time and queue lengths.",
  ),
  doc(
    "doc:TACL-Ref:ch9.status",
    "TACL Reference Manual",
    "TACL-REF",
    "STATUS, TERM option",
    "L/J-series · all nodes",
    "STATUS *, TERM lists the terminal and process state of every process the current TACL can see.",
  ),
];

const heur = (h: Omit<HeuristicSource, "kind">): HeuristicSource => ({ kind: "heuristic", ...h });

export const MARIA: Pick<HeuristicSource, "owner" | "owner_name" | "owner_role" | "years"> = {
  owner: "maria",
  owner_name: "Maria Rossi",
  owner_role: "Sr. NonStop Operator",
  years: 24,
};

export const HEURISTIC_SOURCES: HeuristicSource[] = [
  heur({
    id: "maria:h7",
    ...MARIA,
    captured_via: "interview",
    captured_at: "2026-09-30",
    endorsements: 3,
    last_validated: "2026-09-30",
    scope: "\\PROD · L-series · TMF",
    why: "Quarter-end settlement batch holds one transaction open for hours.",
    relation: "extends:doc:TMF-Reference:ch121.185",
  }),
  heur({
    id: "maria:h11",
    ...MARIA,
    captured_via: "incident INC-2291 debrief",
    captured_at: "2026-09-30",
    endorsements: 2,
    last_validated: "2026-09-30",
    scope: "\\PROD · L-series · TMF",
    why: "At quarter-end the batch never finishes before the trail fills. Waiting cost us BEGINTRANS twice (2019, 2023).",
    relation: "contradicts:doc:TMF-Reference:ch121.187",
  }),
  heur({
    id: "raj:h3",
    owner: "raj",
    owner_name: "Raj Patel",
    owner_role: "Pathway/TMF Specialist",
    years: 15,
    captured_via: "referral answer",
    captured_at: "2026-10-02",
    endorsements: 1,
    last_validated: "2026-10-02",
    scope: "\\PROD · L-series · Pathway",
    why: "SETTLE-SC is the only server class that holds long transactions; others never do.",
    relation: "extends:doc:Pathway-Ref:ch5.status-server",
  }),
  heur({
    id: "lena:h4",
    owner: "lena",
    owner_name: "Lena Kowalski",
    owner_role: "Storage Specialist",
    years: 19,
    captured_via: "interview",
    captured_at: "2026-09-28",
    endorsements: 4,
    last_validated: "2026-09-28",
    scope: "\\PROD · L-series · Storage",
    why: "A disk that flaps between UP and HARDDOWN after a path error is almost always the cable or the CLIM, not the drive.",
    relation: "extends:doc:SCF-Storage:ch6.status-disk",
  }),
];

export const ALL_STATIC_SOURCES: Source[] = [...DOC_SOURCES, ...HEURISTIC_SOURCES];

export const sourceById = (id: string): Source | undefined => ALL_STATIC_SOURCES.find((s) => s.id === id);

export const E_MARIA: Expert = {
  id: "maria", name: "Maria Rossi", active: false, availability: "retired",
  role: "Senior NonStop Operator", team: "Production Operations", years: 24,
  expertise: ["TMF", "Audit trails", "Quarter-end batch"],
  reason: "Author of 6 captured TMF patterns for \\PROD. Retired 2026-09; her knowledge is cited above.",
};
export const E_RAJ: Expert = {
  id: "raj", name: "Raj Patel", active: true, availability: "on_call",
  role: "NonStop Systems Specialist", team: "Production Operations", years: 15,
  expertise: ["Pathway", "TMF", "\\PROD + \\DR"],
  reason: "Resolved 12 TMF/Pathway incidents on \\PROD and \\DR; on-call backup for Maria's patterns.",
  contact: "ext. 4417 · on-call pager 555-0142",
};
export const E_LENA: Expert = {
  id: "lena", name: "Lena Kowalski", active: true, availability: "on_shift",
  role: "Storage Administrator", team: "Infrastructure", years: 19,
  expertise: ["SCF Storage", "Disk mirrors", "Revives"],
  reason: "Owns disk mirror and revive procedures for both nodes.",
  contact: "ext. 4302 · Infrastructure desk",
};

export const claim = (text: string, lane: Claim["lane"], source_id: string, score = 0.93): Claim => ({
  text,
  lane,
  source_id,
  verified: true,
  score,
});

// --- Command catalog (only the command forms permitted for the demo) ---
export interface CatalogEntry {
  id: string;
  template_id: string;
  command: string;
  risk: "read_only" | "state_changing" | "critical";
  explanation: string;
  source_id: string;
  approval: "one_click" | "type_node" | "second_approver";
  dryrun: { expected_output: string; blast_radius: { entity: string; effect: string }[]; warnings: string[] };
  output: (node: string) => string;
}

const hdr = (node: string) => `TMFCOM - T9084L01 - (01JUL2026)  SYSTEM ${node}\n`;

export const CATALOG: Record<string, CatalogEntry> = {
  "cmd-17": {
    id: "cmd-17",
    template_id: "tmfcom.status_audittrail_detail",
    command: "TMFCOM STATUS AUDITTRAIL, DETAIL",
    risk: "read_only",
    explanation: "Shows capacity used and the first pinned file with its reason.",
    source_id: "doc:TMF-Reference:ch4.status-audittrail",
    approval: "one_click",
    dryrun: {
      expected_output:
        "Active audit trail capacity used: nn%\nFirst pinned file: <file>\nReason: <pin reason>",
      blast_radius: [],
      warnings: [],
    },
    output: (node) =>
      hdr(node) +
      "AUDITTRAIL STATUS\n" +
      "  Active audit trail capacity used: 71%\n" +
      "  Trail                 File               State    Pinned\n" +
      "  MAT                   $AUDIT.ZTMFAT.AA000412  Active   no\n" +
      "  MAT                   $AUDIT.ZTMFAT.AA000411  Full     yes\n" +
      "  First pinned file:    $AUDIT.ZTMFAT.AA000409\n" +
      "  Pinned reason:        long-running transaction\n" +
      "  Oldest active transid: " +
      TRANSID.replace("\\PROD", node) +
      "\n",
  },
  "cmd-18": {
    id: "cmd-18",
    template_id: "tmfcom.status_transaction",
    command: "STATUS TRANSACTION",
    risk: "read_only",
    explanation: "Lists active transactions so the one pinning the audit trail can be identified.",
    source_id: "doc:TMF-Reference:ch4.status-transaction",
    approval: "one_click",
    dryrun: {
      expected_output: "Transid                State    Age      Process\n<transid>              ACTIVE   hh:mm    <owner>",
      blast_radius: [],
      warnings: [],
    },
    output: (node) =>
      hdr(node) +
      "TRANSACTION STATUS   (3 active)\n" +
      "  Transid                 State    Age     Owner\n" +
      "  " + TRANSID.replace("\\PROD", node) + "    ACTIVE   03:27   \\PROD.$SETL1  (SETTLE-SC batch)\n" +
      "  \\PROD(1).3.51203    ACTIVE   00:00   \\PROD.$ATM07\n" +
      "  \\PROD(0).2.88410    ACTIVE   00:00   \\PROD.$POS12\n",
  },
  "cmd-19": {
    id: "cmd-19",
    template_id: "tmfcom.abort_transaction",
    command: `ABORT TRANSACTION ${TRANSID}`,
    risk: "critical",
    explanation: "Backs out the settlement transaction that has pinned the audit trail for 3h27m.",
    source_id: "doc:TMF-Reference:ch4.abort-transaction",
    approval: "second_approver",
    dryrun: {
      expected_output: `Transaction ${TRANSID} would be aborted.\nBackout of approx. 1 settlement batch (14,210 records).`,
      blast_radius: [
        { entity: "Pathway SETTLE-SC", effect: "will retry 1 batch (approx. 14,210 records)" },
        { entity: "Audit trail $AUDIT", effect: "pinned files released once backout completes (~4 min)" },
        { entity: "Nightly settlement report", effect: "delayed until the batch is re-run" },
      ],
      warnings: ["Critical: aborting a transaction cannot be undone.", "Second approver required."],
    },
    output: (node) =>
      hdr(node) +
      `Transaction ${TRANSID.replace("\\PROD", node)} aborted.\n` +
      "Backout in progress: 14,210 records\n" +
      "Backout complete. Audit trail capacity used: 38%\n",
  },
  "cmd-20": {
    id: "cmd-20",
    template_id: "scf.status_disk_detail",
    command: "SCF STATUS DISK $DATA01, DETAIL",
    risk: "read_only",
    explanation: "Shows drive state, mirror and revive status for $DATA01.",
    source_id: "doc:SCF-Storage:ch6.status-disk",
    approval: "one_click",
    dryrun: {
      expected_output: "STORAGE - Detailed Status DISK \\node.$DATA01\nState, Primary/Mirror path, Revive status",
      blast_radius: [],
      warnings: [],
    },
    output: (node) =>
      "SCF - T9082L01 - (01JUL2026)  SYSTEM " + node + "\n" +
      `STORAGE - Detailed Status DISK ${node}.$DATA01\n` +
      "  State................ STARTED\n" +
      "  Primary Path......... UP     Mirror Path........ UP\n" +
      "  Primary Drive........ UP     Mirror Drive....... UP\n" +
      "  Revive............... NONE\n" +
      "  Path errors (24h).... 17 on mirror path\n",
  },
  "cmd-21": {
    id: "cmd-21",
    template_id: "pathcom.status_server_all",
    command: "PATHCOM STATUS SERVER *",
    risk: "read_only",
    explanation: "Lists all server classes with running and pending process counts.",
    source_id: "doc:Pathway-Ref:ch5.status-server",
    approval: "one_click",
    dryrun: { expected_output: "SERVER   RUNNING  PENDING  MAX", blast_radius: [], warnings: [] },
    output: (node) =>
      "PATHCOM - T9153L01 - (01JUL2026)  SYSTEM " + node + "\n" +
      "  SERVER      RUNNING  PENDING  MAX\n" +
      "  ATM-SC           8        0     8\n" +
      "  POS-SC          12        1    16\n" +
      "  SETTLE-SC        2        4     2\n",
  },
  "cmd-22": {
    id: "cmd-22",
    template_id: "peek.cpu",
    command: "PEEK /CPU 2/",
    risk: "read_only",
    explanation: "Shows processor counters for CPU 2.",
    source_id: "doc:PEEK-Ref:ch2.cpu",
    approval: "one_click",
    dryrun: { expected_output: "CPU 2 busy %, ready queue length", blast_radius: [], warnings: [] },
    output: (node) =>
      "PEEK - T9050L01 - (01JUL2026)  SYSTEM " + node + "\n" +
      "  CPU 2   Busy: 58%   Ready queue: 3   Memory used: 71%\n",
  },
  "cmd-23": {
    id: "cmd-23",
    template_id: "tmfcom.status_tmf",
    command: "TMFCOM STATUS TMF",
    risk: "read_only",
    explanation: "Shows TMF state, BEGINTRANS enablement and active transaction count.",
    source_id: "doc:TMF-Reference:ch4.status-tmf",
    approval: "one_click",
    dryrun: { expected_output: "TMF state, BEGINTRANS, active transactions", blast_radius: [], warnings: [] },
    output: (node) =>
      hdr(node) + "  TMF State........ STARTED\n  BEGINTRANS....... ENABLED\n  Active transactions: 3\n",
  },
  "cmd-24": {
    id: "cmd-24",
    template_id: "tacl.status_term",
    command: "TACL STATUS *, TERM",
    risk: "read_only",
    explanation: "Lists terminals and process state visible to this TACL.",
    source_id: "doc:TACL-Ref:ch9.status",
    approval: "one_click",
    dryrun: { expected_output: "Process, terminal, state", blast_radius: [], warnings: [] },
    output: (node) =>
      "TACL - STATUS *, TERM   SYSTEM " + node + "\n" +
      "  $Z0A1   TERM $TERM01   RUNNING\n  $Z0B2   TERM $TERM02   RUNNING\n",
  },
};
