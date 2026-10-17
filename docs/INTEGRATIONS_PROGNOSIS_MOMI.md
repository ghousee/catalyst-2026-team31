# Adapters for IR Prognosis and BlackWood MOMI

Research date: 2026-10-17. Companion to `INTEGRATIONS.md` (read that first for the shared architecture: webhook, syslog and SNMP-trap listeners writing one normalised event).

Evidence key:
- **[V]** = read in a page or document this session (URL given).
- **[S]** = search-result summary only, page not opened.
- **[U]** = unverified (inference or general knowledge). Confirm before relying on it.

Payload key: **VERBATIM** = copied from vendor docs. **RECONSTRUCTED** = built by us from documented field names and behaviour. Every sample below is RECONSTRUCTED unless it says VERBATIM. Replace with customer captures as soon as they exist.

Scholarly note: no papers cited, so the LibKey connector was not needed.

---

## 0. Correction (2026-10-17, later the same day): Prognosis DOES have a REST API

The first pass missed it. IR Community posts [S] describe a Prognosis REST API on the Prognosis Web UI server (IIS, Windows):
- Data is exposed as named **datasets**, each a PQL query, defined by an admin in
  `Prognosis\WebUI\IIS\Administration\Config\RestApiDataSets.xml` (restart `IrPrognosisSite` in IIS after editing; test the query with `irpqlcli`).
- Read with `GET https://<prognosis-server>/Prognosis/Rest/v1/data/<datasetId>` → JSON over HTTPS. Datasets can take parameters (e.g. a CPU number).
- Auth: basic auth or the Web UI session cookie; rows are filtered by Prognosis Role Based Security.
- Alerts: IR's own guide exposes **open problems (PROBSUM)** and closed problems as datasets so third-party tools (ServiceNow, OpsRamp) can **pull** them. A Swagger page exists in Prognosis.
- Caveats: the posts are several years old and generic (UC-focused), not NonStop-specific; pages could not be opened (redirect, then a TLS error), so this is search-summary evidence. Confirm with IR/CAIL that their version and licence have the Web UI + REST API and that NonStop problem records are queryable.

**Revised Prognosis adapter, ranked:** (1) poll the REST API for open problems every 10-30 s (pull, simplest, no NonStop change); (2) SNMP traps out (push) if REST is not licensed.
MOMI is unchanged: BlackWood's own overview page lists alarm outputs as on-screen, MOMI log, EMS and email only; no API.

Sources: [Prognosis Alerts via REST API](https://community.ir.com/t5/Prognosis-Blog/Prognosis-Alerts-via-REST-API/ba-p/5963),
[API(s) for Prognosis?](https://community.ir.com/t5/Unified-Communications/API-s-for-Prognosis/td-p/1195),
[Prognosis REST API](https://community.ir.com/t5/Collaborate/Prognosis-REST-API/td-p/2586),
[Swagger tool in Prognosis](https://community.ir.com/t5/General/How-to-use-the-Swagger-tool-in-Prognosis/td-p/8387),
[MOMI overview](https://www.momi.com/website/momi_overview.htm).

## 1. Summary

| | IR Prognosis | BlackWood MOMI |
|---|---|---|
| Documentation access | **Mostly gated.** Public pages say alerts exist and SNMP traps can go out. Product manuals, MIB and REST docs were not reachable. | **Full 649-page user manual is public** (PDF, 6.19e). All MOMI facts below come from it. |
| Confirmed output channels | SNMP traps out (MIB "ptrapmib"). Integration with Tivoli/Netcool, ServiceNow, "any SNMP trap compatible system" (vendor brochure). | Email (SMTP), EMS message, MOMI log file, on-screen alarm. Scripted history/log export to delimited text or HTML. No native SNMP. |
| Not found | REST/Web API, webhook, syslog, Kafka, ODBC export, CSV export. No public evidence either way. | REST, webhook, syslog, ODBC, SNMP (the manual says outright there is none). |
| Real-time path | SNMP trap (push). | Email and EMS (push). |
| Runs on-prem | Prognosis Server installs on each NonStop node. Also deployable in private or public clouds. Needs a Windows/SQL Server stack in at least some editions. | Yes. Server on NonStop, client on Windows. No cloud component. |
| Recommended adapter | SNMP trap receiver, plus a ptrapmib-driven mapper. | SMTP sink (custom email template), then EMS-to-syslog/SNMP as the second path. |
| Biggest unknown | Trap OIDs and varbind layout (needs the MIB). Any non-SNMP output. | Whether CAIL customers actually run MOMI, and which alarms they define. |

"momoi" is almost certainly BlackWood's MOMI (see section 3). A third tool is still unnamed. Candidate from the earlier survey: Idelji Web ViewPoint Enterprise, which does have SNMP, syslog and JSON output (see `INTEGRATIONS.md`).

---

## 2. IR Prognosis (Integrated Research)

### 2.1 What is confirmed

- Product naming: Prognosis, now branded "IR Infrastructure, powered by Prognosis". First built in 1998 for HP NonStop. [V] https://connect2nonstop.com/lets-get-real-time/
- Packaging, from the 2023 IR brochure [V] https://www.ir.com/hubfs/IR%20Infrastructure%20Solution%20overview_final.pdf (text extracted locally):
  - NonStop tier: "Automated operations" with customizable threshold conditions on "more than 1,500 system attributes", generating alerts and letting users automate responses. Disk management with alerts on customized and predefined thresholds.
  - NonStop Plus tier: Batch management ("generating alerts or taking automated actions when jobs fail"), Automated analyst, **Enterprise integration** ("Integrates key performance and availability data from your HPE NonStop systems with enterprise management frameworks, such as IBM Tivoli/Netcool, ServiceNow, and any SNMP trap compatible system"), and an **Application data interface** ("extracts and integrates key performance and status information from your commercially developed applications to enable thresholds and initiate automated actions").
  - NonStop Enterprise tier: Pathway management, Transaction management (TMF and RDF), Software inventory, Load balancing, MQ management, User accounting.
  - Architecture claim: "distributed architecture allows delivery of real-time metrics at dynamic intervals, filtered at the source and routed to where it is required".
  - So integration to SNMP/ServiceNow is a **licensed package tier**, not necessarily in every deployment. Ask which tier the customer has.
- Platform components, 2021 article [V] https://www.nonstopinsider.com/the-power-of-the-prognosis-platform/:
  - Prognosis Edge: agents that "collect, filter, mask, transform, and transmit" data to the Server and Cloud.
  - Prognosis Server: "central real-time data processing and analytics engine"; "installed directly on each HPE NonStop Server Node". Also deployed in public and private clouds.
  - Prognosis Cloud: IR's SaaS extension.
- Alert sizes: roughly 17,000 data elements usable for alerts, dashboards and reports; nearly 4,000 out-of-the-box dashboards and reports. [V] https://connect2nonstop.com/lets-get-real-time/ (vendor marketing numbers).
- Alert form: "a flashing red light or simply an alert entry on a console log"; Prognosis "contributes much-needed alert information" to enterprise tools. [V] https://www.ir.com/blog/hpe-nonstop/get-greater-insight-into-nonstop-operations
- SNMP traps out, from an IR community thread (about 7 years old at time of the search result; the page itself could not be opened: it redirects and then returns 403/404 from our tools) [S] https://community.ir.com/t5/General/SNMP-Traps-Out-Variables/td-p/6839:
  - Prognosis has an "SNMP Traps Out" destination and a MIB called **ptrapmib**.
  - A user reported the MIB has **no fixed variable for the monitored device's IP address**.
  - The answer: include extra data via "Including Field Values" under SNMP Traps Out for NonStop. It only works when the threshold's underlying record has such a field (for example an IP field).
  - Implication: trap content is **configured per threshold**, and the varbinds beyond the fixed ones depend on the record type. Our adapter must tolerate variable varbinds.
- Windows/SQL Server dependency noted by the US VA Technical Reference Model for Prognosis 10.3 to 11.8: Microsoft SQL Server, .NET, IIS, Windows Server, HTTP/LDAP/TCP; collected data can be stored in databases. The page mentions no API. [V] https://www.oit.va.gov/Services/TRM/ToolPage.aspx?tid=8880 (this describes the VoIP/UC-heavy Prognosis server, so may not match a NonStop-only install.)
- Iris for NonStop: embedded in the Prognosis Platform, available with Prognosis 13.3, natural-language questions over system health and capacity. Announced 2026-06-17. No API, MCP or on-prem data-residency statement found. [S] https://www.aap.com.au/aapreleases/cision20260617ae85909/
- IR's ServiceNow two-way integration press release (2023-05-31) is for **IR Collaborate** (unified comms), not Prognosis NonStop. Do not assume it applies. [S] https://www.aap.com.au/aapreleases/cision20230531ae15408

### 2.2 What we could not find (state plainly: unknown, not "absent")

Searches for the following across IR, community, GitHub and general web returned nothing relevant: Prognosis REST/Web API, webhook or HTTP action in alert rules, syslog output, Kafka/stream output, ODBC export, CSV export, email alert format, Splunk integration, the ptrapmib file itself, its enterprise OID, and trap OIDs. IR's documentation and community appear to require a customer login. Treat each as **[U]**.

### 2.3 Typical NonStop alert content

No public Prognosis sample was found. From the brochure's module list, alert subjects are: CPU/process/disk/file thresholds, batch job failure, Pathway components, TMF and RDF state, MQ components, and custom application data. Naming of the individual alerts is unknown [U].

### 2.4 Recommended adapters (ranked)

1. **SNMP trap receiver (UDP 162), v2c and v3.** The only Prognosis output channel with public evidence, and it is push. Needs the ptrapmib file to decode varbinds. Until the MIB arrives, store raw OIDs plus values.
2. **Customer-side relay (only if the site already has it).** If the customer already forwards Prognosis traps to Netcool/ServiceNow/another manager, ask for a second trap destination pointed at us. No change to Prognosis logic needed.
3. **Ask IR/CAIL directly** about a documented REST/Web API or database view for metrics. Do not build against anything undocumented.
4. **Do not plan** on reading Prognosis SQL databases directly or scraping its UI.

### 2.5 Field mapping (Prognosis trap to our schema)

Because ptrapmib is unavailable, the mapping below uses SNMPv2c standard varbinds (documented in RFC 3416, not Prognosis) plus **placeholders** for Prognosis-specific ones.

| Our field | Source | Confidence |
|---|---|---|
| `ts` | `sysUpTime`-based is useless; use trap receive time, unless a timestamp varbind exists in ptrapmib | [U] |
| `source_tool` | constant `prognosis` | n/a |
| `kind` | `alert` for threshold traps | [U] |
| `node` | UDP source IP is the Prognosis server, not the NonStop node. Node name must come from a varbind or via "Including Field Values". Per the community thread there is no device-IP varbind. | [S] |
| `subsystem` | derive from threshold/record type varbind (CPU, DISK, PATHWAY, TMF, ...) | [U] |
| `name/number` | `snmpTrapOID.0` and/or an alert/threshold name varbind | [U] |
| `value` | included field values (per-threshold) | [S] |
| `severity` | severity varbind if present; else map from trap OID | [U] |
| `text` | description varbind; else concatenated field values | [U] |
| `raw` | full varbind list as `{oid: value}` JSON | n/a |

### 2.6 Sample payloads

**P1. RECONSTRUCTED. Prognosis SNMPv2c trap as decoded by our receiver.** Prognosis varbind names, OIDs and values are invented placeholders. Only the structure (`sysUpTime.0`, `snmpTrapOID.0`, then enterprise varbinds) is standard SNMPv2c.

```json
{
  "transport": "snmp", "version": "v2c", "community": "public",
  "src_ip": "10.20.30.40",
  "varbinds": [
    {"oid": "1.3.6.1.2.1.1.3.0", "type": "TimeTicks", "value": 123456789},
    {"oid": "1.3.6.1.6.3.1.1.4.1.0", "type": "OID", "value": "<ptrapmib::thresholdTrap OID, UNKNOWN>"},
    {"oid": "<ptrapmib::alertName, UNKNOWN>", "type": "OctetString", "value": "CPU Busy High"},
    {"oid": "<ptrapmib::severity, UNKNOWN>", "type": "Integer", "value": 3},
    {"oid": "<ptrapmib::message, UNKNOWN>", "type": "OctetString", "value": "\\PROD1 CPU 3 busy 97% exceeds 90%"}
  ]
}
```

**P2. RECONSTRUCTED. Our normalised event from P1.**

```json
{"ts":"2026-10-17T14:02:11Z","node":"\\PROD1","subsystem":"CPU","kind":"alert",
 "name":"CPU Busy High","value":97,"severity":"major",
 "text":"\\PROD1 CPU 3 busy 97% exceeds 90%","source_tool":"prognosis",
 "raw":{"varbinds":"as P1"}}
```

No verbatim Prognosis payload exists in anything we could read.

### 2.7 Asks (Prognosis)

1. The **ptrapmib** MIB file(s) and any other IR MIBs shipped with the version they run.
2. Prognosis version, and which license tier has Enterprise integration (NonStop Plus or above per the brochure).
3. Screenshots or export of the **SNMP Traps Out** destination setup and of 5 to 10 real thresholds that use it, including "Including Field Values" choices.
4. 20 to 50 **real trap captures** (Wireshark/tcpdump, or a text log from their current trap receiver such as Netcool).
5. A second SNMP trap destination pointed at our host, with version, community or v3 user, auth/priv passphrases, engine ID.
6. IR documentation: "SNMP Traps Out", "Including Field Values", any "Web Services/API" guide, any "Database/Data Export" guide. Ask explicitly whether IR offers a REST API or webhook action in the customer's version.
7. List of alert names/thresholds operators care about for the demo scenarios.
8. Whether Prognosis Server runs on the NonStop node, a Windows server, or IR Cloud for them (affects the trap source IP and network path).
9. Confirm whether IR is a partner or a competitor of CAIL given Iris.

---

## 3. BlackWood MOMI

### 3.1 What it is [V]

- Company: BlackWood Systems, Inc. Site https://www.blackwood-systems.com/website/momi_software.htm. Support address in the manual: support@blackwood-systems.com.
- Product: MOMI, a system management tool for HPE NonStop (Guardian/NSK). Tagline in the manual: "When Your System Demands Quick Attention...". Acronym expansion (Multi-system Online Measure Interface) is from a third-party list only [S] https://www.acronymfinder.com/Multi_System-Online-Measure-Interface-(performance-monitor-product-for-the-HP-NonStop-System)-(MOMI).html.
- Current release: 6.19e (PC client 6.19e, NonStop server 6.19b). Copyright 1999-2026. [V] https://www.blackwood-systems.com/momi/documentation/6.19e/PDF/MOMI_user.pdf (downloaded and text-extracted locally; the PDF is about 120 MB).
- Architecture [V, same manual]: client/server. The server runs on NonStop as a fault-tolerant process pair; the client runs on Windows 10 or later (Delphi). They talk over TCP/IP sockets with AES encryption. There is no web UI.
- Monitored areas, from the manual's screen list [V]: CPUs, memory, processes and process entities, Enscribe and SQL/MP files, disk entities (Measure-based; the manual references the MEASURE entity), TMF state and rate, EMS messages from $0 and $ZLOG, spooler, TCP/IP, OSS, Expand (lines, paths, connections), user-defined diagrams, plus history charts. Pathway: the manual mentions a Pathway TCP object keyword and EMS Pathway subsystem. Measure counters are used for process and disk data.
- Related fact: the manual's Acknowledgments say a **CAIL terminal emulator was once bundled** with MOMI ("provided courtesy of CAIL... no longer provided and was removed from the MOMI installation package"). So CAIL knows MOMI users, and the `NOCAIL` client option still exists. [V] same PDF.
- Another party is "Cool Waters Cyber (UK)" as European distributor [V] https://www.cool-waters.co.uk/momi.
- No other NonStop product called "momoi" was found. Leave a note to confirm with CAIL.

### 3.2 Alerting, exactly as documented [V]

All from the Alarms chapter of the user manual (page refs in the PDF: Alarm Overview 255, Define/Alarm 513, Define/Action 521, Email 527, SNMP Trap Recommendation 609).

- Alarms are threshold or state definitions: "MOMI Alarms are the ability to set thresholds and trigger notifications." Examples: CPU down, process not running, disk file percent full, EMS-text matches, spooler, tape and others.
- Each alarm links to a **Times** object (monitoring windows in 1/2-hour slots over 7 days) and an **Action**.
- An Action can do any or all of: (a) show on the PC client Alarms/Active screen, (b) write to the MOMI log, (c) **write an EMS message** (to $0 or another collector), (d) **send email** to an address or group.
- Alarm lifecycle: Set and Cleared. A second email can go out on clear. Escalation intervals turn the on-screen colour yellow then red.
- Alarm text, verbatim examples: `Process $a is not running` and `File $data1.proddb.account is 81% full over threshold of 80%`.
- The **EMS / User defined** alarm type triggers on text in EMS events (Include/Exclude if ANY/ALL, not case sensitive, optional count-within-time). MOMI ignores EMS events with SSID `BWS` (its own) to prevent loops.
- Custom message templates for EMS and email use variables inside `<% ... %>`, not case sensitive. Documented variables: `Alarm-Text`, `Alarm-Text-Extra`, `Alarm-Text-Extra-ML`, `Alarm-Text-All-ML`, `Alarm-Text-Extra-All-ML`, `Alarm-Date` and `Alarm-Time` (each with optional `-GMT`; formats yyyy-mm-dd and hh:mm:ss), `Alarm-Name`, `Alarm-Description`, `Action-Name`, `Action-Description`, `Entity-Name`, and `Ancestor` (process-state alarms).
- EMS output from alarms: the CONFMOMI keyword `ALARM-EMS-EVENT-NBR` sets the event number (recommended range 20000 to 32767; default zero). The manual says MOMI "logs its information as text with an event number of zero" by default.
- Email transport CONFMOMI keywords: `ALARM-SMTP-SERVER-ADDR` and `ALARM-EMAIL-ADDRESS-FROM` (both required), `ALARM-DOMAIN-NAME`, `ALARM-SMTP-PORT` (default 25), `ALARM-SMTP-SERVER-USERNAME`/`-PASSWORD`, `ALARM-SMTP-BIND-ADDR`, `ALARM-SMTP-TCPIP-NAME`, `ALARM-SMTP-SERVER-TIMEOUT`, `ALARM-EMAIL-SUBJECT` (if absent, subject is "MOMI Alarm"; empty string means the first line of the alarm message becomes the subject).
- SMTP specifics: the **NonStop** sends the mail (not the PC). "MOMI does not specify any authentication. The SMTP server must allow unauthenticated access" unless username/password are set (server 6.04+). Auth is PLAIN with no encryption.
- SNMP: "**MOMI does not have the ability to directly generate SNMP traps.**" The manual recommends this chain: MOMI alarm writes an EMS message, an EMS distributor reads it, passes it to the NonStop SNMP agent, which emits the trap. The manual gives an example (SNMPAGT process, `scf add trapdest`, an EMS filter compiled with EMF, and `emsdist ... type printing, collector $0, filter ...`). Uses the standard NonStop SNMP agent, so it needs the HPE manual for trap layout.
- Not found anywhere in the manual: REST API, webhook, syslog, ODBC/SQL access to MOMI data. The grep for these terms returned nothing.

### 3.3 Data export [V]

- **History export**: "History / Export Data" produces raw MOMI history as delimited text (TAB by default, configurable) or HTML. Column order is fixed, columns selectable; new columns are appended at the end. Output options include headers, GMT or local time, "rated" values, file name. Exports can be saved as scripts and run unattended by launching the PC client: `MOMI.EXE script-history=<name>`. The client exits when done.
- **Log export**: `MOMI.EXE script-log=<name>` exports the MOMI log (LOG01DB). Export file names may contain `<date>` (YYYYMMDD).
- Numeric fields intended as strings (for example CPU,PIN) carry a leading hard space (ASCII 160) in exports. A parser must strip it.
- These exports run on a **Windows PC** with a client, not push. They are batch/scheduled (use Windows Task Scheduler [U]).
- Alarm definitions can be exported to a text file (alarm and supporting definitions) via List/Export. Useful to us: it tells us which alarms a site has. [V]
- MOMI data live in Enscribe files on NonStop (`LOG01DB` log, `HSTnnDB` history). Reading them directly needs NonStop access, which our design avoids. [V]
- Client Access/security: alarm configuration is limited to the user that started the MOMI server unless Client Access is on. [V]

### 3.4 Recommended adapters (ranked)

1. **SMTP sink with a custom email template (best).** Documented, real-time, push, on-prem, needs one customer config change. We run a small SMTP listener (port configurable via `ALARM-SMTP-PORT`). MOMI allows unauthenticated SMTP, which fits a sink. Email subject and body can be rewritten with `<%var%>` into a **machine-parseable** `key=value` or JSON body. Caveat: the sender is the NonStop (resolver and route needed), no TLS in MOMI's client, so keep the sink on the internal LAN.
2. **Alarm Action to EMS, then EMS distributor to a shipper (syslog/Kafka/SNMP).** Documented. Fits the shared EMS path already planned in `INTEGRATIONS.md`. Pair it with ONS or the manual's SNMP recipe if the site wants traps. Note events will have SSID owner BWS (confirm), and default event number zero.
3. **SNMP via the manual's EMS-to-SNMP recipe** to our trap receiver. Works but heavier and trap layout depends on the HPE agent, not MOMI.
4. **Scheduled `script-history`/`script-log` exports** into a watched folder for metrics and for replay/backfill. Batch only. Good for building the demo dataset, weak for real time.
5. **Not recommended:** reading LOG01DB or history files directly.

### 3.5 Field mapping (MOMI to our schema)

| Our field | SMTP/template source | EMS source | Export (history) |
|---|---|---|---|
| `ts` | `Alarm-Date` + `Alarm-Time` (use `-GMT` variants) | EMS event timestamp | date/time column (GMT option) |
| `source_tool` | `momi` | `momi` | `momi` |
| `node` | add a literal system name in the template (no system variable is documented) | EMS node field | system column [U] |
| `subsystem` | derive from alarm type (put in `Alarm-Name`/`Alarm-Description` by convention) | EMS SSID (owner BWS) | entity type |
| `kind` | `alert` (Set) or `alert` with cleared flag | `event` | `metric` |
| `name/number` | `Alarm-Name` | event number (default 0 or `ALARM-EMS-EVENT-NBR`) | entity/counter name |
| `value` | parse from `Alarm-Text` ("81% full over threshold of 80%"), else null | text | numeric columns |
| `severity` | not a MOMI field. Map from the Action name (use `Action-Name` as the severity label by convention) | EMS emphasis/action attribute | n/a |
| `text` | `Alarm-Text` + `Alarm-Text-Extra` | EMS text | n/a |
| entity | `Entity-Name` | text | process/disk/CPU column |
| `raw` | full email, headers and body | full EMS text | the TSV line |

Severity convention: MOMI has no severity attribute in the alarm text itself. We should define one Action per severity level (for example `ACT-CRITICAL`, `ACT-WARN`) and put `<%Action-Name%>` in the template.

### 3.6 Sample payloads

**M1. VERBATIM (alarm text strings only, from the manual).**

```
Process $a is not running
File $data1.proddb.account is 81% full over threshold of 80%
```

**M2. RECONSTRUCTED. Recommended custom email body** (subject uses `ALARM-EMAIL-SUBJECT ""`, so the first line of the message becomes the subject; variable names are the documented ones, the layout is ours).

```
Subject: MOMI|ACT-CRITICAL|SET|PROD1|File $data1.proddb.account is 81% full over threshold of 80%

tool=momi
node=PROD1
state=SET
date=<%Alarm-Date-GMT%>
time=<%Alarm-Time-GMT%>
alarm=<%Alarm-Name%>
action=<%Action-Name%>
entity=<%Entity-Name%>
text=<%Alarm-Text%>
extra=<%Alarm-Text-Extra%>
```

What our sink would receive for a disk alarm:

```
tool=momi
node=PROD1
state=SET
date=2026-10-17
time=14:02:11
alarm=DISKFILE - PERCENT FULL [$DATA1.PRODDB.ACCOUNT]
action=ACT-CRITICAL
entity=$data1.proddb.account
text=File $data1.proddb.account is 81% full over threshold of 80%
extra=
```

**M3. RECONSTRUCTED. Normalised event from M2.**

```json
{"ts":"2026-10-17T14:02:11Z","node":"PROD1","subsystem":"DISK","kind":"alert",
 "name":"DISKFILE - PERCENT FULL","value":81,"severity":"critical",
 "text":"File $data1.proddb.account is 81% full over threshold of 80%",
 "source_tool":"momi","raw":"<full SMTP message>"}
```

**M4. RECONSTRUCTED. History export line** (TAB-delimited, columns are selectable and fixed in order; actual column set not read, so names are placeholders).

```
2026-10-17 14:00:00<TAB>PROD1<TAB>CPU<TAB>3<TAB>busy<TAB>97.2
```

(Remember the leading ASCII 160 on string-type numeric fields such as CPU,PIN.)

### 3.7 Asks (MOMI)

1. Confirm "momoi" means BlackWood MOMI, and which customers run it. If a customer says it is something else, get the vendor name.
2. MOMI version (6.19e is current; the email password feature needs server 6.04+; EMS-text AND logic needs 6.04+).
3. The **alarm definition export** (List/Export text file) and a screenshot of Alarms/Active.
4. A customer admin with MOMI alarm-configuration rights to: set `ALARM-SMTP-SERVER-ADDR` to our sink host (and `ALARM-SMTP-PORT` if non-25), `ALARM-EMAIL-ADDRESS-FROM`; create an Email entry for us; add one Action per severity using our template.
5. Confirm the NonStop can route to our host on the SMTP port (NonStop resolver and TCPIP process; `ALARM-SMTP-TCPIP-NAME` and `ALARM-SMTP-BIND-ADDR` for CLIM sites).
6. 20 sample alarm emails (existing format) and 20 EMS messages generated by MOMI alarm actions, including the `ALARM-EMS-EVENT-NBR` value if set.
7. One `script-history` export and one `script-log` export (small files, anonymised).
8. Which MOMI alarms and monitoring windows the senior operators trust, so we can seed patterns.
9. Whether the site wants SNMP: if so, their SNMP agent set-up and the HPE NonStop SNMP agent MIB.

---

## 4. Third tool (unknown)

Not named by CAIL yet. Ask. The best-documented candidate from `INTEGRATIONS.md` is Idelji Web ViewPoint Enterprise (SNMP v1/v2c/v3, Syslog, JSON, SMTP). No new research here.

---

## 5. Implementation notes

- **SMTP sink** is a new listener beyond the three in `INTEGRATIONS.md`. Python `aiosmtpd` is a candidate (library name from general knowledge [U]). It would accept unauthenticated mail on an internal port and run the `key=value` parser.
- **SNMP decoding** needs the customer MIB. Keep a per-tool mapping config keyed by trap OID, with a raw fallback.
- **Demo replay**: re-emit M2 as real SMTP messages to the sink, and P1 as real SNMP traps, same path as production.
- **Severity**: define our canonical levels (`critical`, `major`, `minor`, `warning`, `info`) and put the per-tool translation table in config.

---

## 6. Sources

Read in full or extracted locally:
- https://www.blackwood-systems.com/momi/documentation/6.19e/PDF/MOMI_user.pdf (MOMI 6.19e user manual, 649 pages; all MOMI details)
- https://www.blackwood-systems.com/website/momi_software.htm (release page, docs links)
- https://www.ir.com/hubfs/IR%20Infrastructure%20Solution%20overview_final.pdf (IR NonStop brochure 2023)
- https://connect2nonstop.com/lets-get-real-time/ (Prognosis overview)
- https://www.nonstopinsider.com/the-power-of-the-prognosis-platform/ (platform components)
- https://www.ir.com/blog/hpe-nonstop/get-greater-insight-into-nonstop-operations (alerting quotes)
- https://www.oit.va.gov/Services/TRM/ToolPage.aspx?tid=8880 (Prognosis versions, SQL Server dependency)
- https://ftp.hp.com/pub/softlib/NonStopOpMsgsMnl/ch69.html (ONS: EMS to SNMP; no OIDs)

Search summaries only:
- https://community.ir.com/t5/General/SNMP-Traps-Out-Variables/td-p/6839 (ptrapmib; page not opened, 403/404 and a redirect to help.ir.com)
- https://www.aap.com.au/aapreleases/cision20260617ae85909/ (Iris for NonStop)
- https://www.aap.com.au/aapreleases/cision20230531ae15408 (IR Collaborate ServiceNow, not Prognosis NonStop)
- https://www.acronymfinder.com/Multi_System-Online-Measure-Interface-(performance-monitor-product-for-the-HP-NonStop-System)-(MOMI).html
- https://www.cool-waters.co.uk/momi

---

## 7. Unverified list

**Prognosis**
- Every output channel except SNMP traps (and the brochure's ServiceNow/Netcool integration, whose mechanism is unknown): REST/Web API, webhook, syslog, Kafka, ODBC, CSV, email format, Splunk.
- ptrapmib contents: OIDs, varbind names, severity encoding, timestamp varbind, enterprise OID.
- Whether SNMP v2c or v3 or both are offered on traps out.
- Alert names and severities typical of a NonStop site.
- Whether the ServiceNow integration is SNMP-based or a separate connector.
- Where Prognosis Server runs per customer, and whether Iris data stays on-prem.
- The community thread's content beyond the search-summary excerpt, and whether its advice is current.

**MOMI**
- That "momoi" = BlackWood MOMI.
- The exact acronym expansion (third-party list only).
- Whether customers run MOMI at all, and their alarm definitions.
- The exact column set of history exports, and the exact EMS text/token layout of MOMI's alarm EMS messages (owner, subsystem name, emphasis). Only "SSID BWS" and "event number zero by default" are documented.
- Whether a system name variable exists for templates (none appeared in the documented variable list).
- Whether the SMTP sink approach survives site mail relays or firewalls (site-specific).
- The Windows Task Scheduler suggestion for scheduled exports (our inference).

**Cross-cutting**
- "Real-time" for MOMI email depends on alarm check intervals (MOMI polls some data at configurable intervals), not on SMTP.
- Whether both tools expose a severity concept compatible with ours (Prognosis: unknown; MOMI: none natively).
