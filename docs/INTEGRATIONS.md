# Watcher integrations: how NonStop monitoring tools can feed us

Research date: 2026-10-17. Goal: the WATCHER consumes real-time events from tools CAIL customers already run, inside the customer network, without logging in to NonStop hosts. The tools push to us (or expose a local API). Rule: keep it simple.

Evidence key: **[V]** = read in a fetched page this session. **[S]** = from a search-result summary only (page not opened). **[U]** = unverified (general knowledge or inference; confirm before relying on it).

Scholarly note: the org's LibKey connector is not authorized in this session, and no scholarly papers are cited. All sources are vendor or HPE pages.

---

## 1. What "momoi" is

"MOMI" is almost certainly **MOMI = Multi-system Online Measure Interface**, a NonStop performance monitor and operations utility from **BlackWood Systems** (momi.com / blackwood-systems.com). It is **not an Idelji product**, and no source found links the two companies.

- BlackWood describes MOMI as an "HP NonStop System Performance Monitor and Operations Utility." The current release is 6.19e, with a Windows PC client and a NonStop server PAK. [V] https://www.blackwood-systems.com/website/momi_software.htm and https://www.brightstrand.com/what-we-do/software-tools/ [S]
- The acronym expansion comes from a third-party acronym list. [S] https://www.acronymfinder.com/Multi_System-Online-Measure-Interface-(performance-monitor-product-for-the-HP-NonStop-System)-(MOMI).html
- Cool Waters Cyber (UK) is its European distributor. [V] https://www.cool-waters.co.uk/momi
- Neither vendor page documents alerting, export, SNMP or syslog. See "Unverified".
- Idelji is a separate vendor. Its NonStop products are Web ViewPoint Enterprise, ManAIge, Local/Remote Analyst, and the Shadowbase, Base24, Connex and MQ Monitors. [V] https://idelji.com/about-us/

Recommendation: confirm with CAIL whether they meant BlackWood MOMI or Idelji's Web ViewPoint. The "momoi" spelling could also be a mishearing of Idelji's "My NonStop" web console, which is a required prerequisite for Web ViewPoint Enterprise. [V] https://idelji.com/wvpe-abe-abf-knowledge-base/getting-started-overview/

---

## 2. Summary table

Columns: what data, how we can consume it, real-time (push/stream) or batch, on-prem, and evidence.

| Tool | Data exposed | Consumption methods | Real-time? | Fully on-prem? | Source |
|---|---|---|---|---|---|
| **IR Prognosis** (incl. Iris) | Threshold alerts, real-time telemetry, dashboards, reports | SNMP traps out [V]. Email alerts [S]. Enterprise integration to ServiceNow / Tivoli-Netcool / any SNMP-trap system [S]. REST/syslog/Kafka not found [U] | Push for traps and alerts. Metrics via the Prognosis UI [S] | Prognosis server runs on NonStop plus an IR server [U]. Iris LLM hosting not stated | https://www.ir.com/hubfs/IR%20Infrastructure%20Solution%20overview_final.pdf [S], https://www.aap.com.au/aapreleases/cision20260617ae85909/ [V], https://community.ir.com/t5/General/SNMP-Traps-Out-Variables/td-p/6839 [S] |
| **Idelji Web ViewPoint Enterprise (WVP E)** | Alerts on EMS events and thresholds, alert log, ServiceNow ticketing | **SNMP v1/v2c/v3 traps, Syslog, JSON** to a host:port, SMTP email [V]. Reads EMS live via an EMSLINK connection [S] | Push at alert time | Runs on the NonStop, browser UI. On-prem [V] | https://idelji.com/web-viewpoint-enterprise-abg-help/overview-delivery/, https://idelji.com/web-viewpoint-enterprise-knowledge-base/how-can-i-configure-snmp-protocol/, https://idelji.com/wvpe-abe-abf-knowledge-base/getting-started-overview/ |
| **BlackWood MOMI** | Performance (Measure-based) and operations utility | Not documented in anything we could read [U] | Unknown | PC client plus NonStop server [V] | https://www.blackwood-systems.com/website/momi_software.htm |
| **Idelji ManAIge / Remote Analyst** | AI anomaly detection | No integration detail [V]. Remote Analyst began as a cloud service and was later offered in private clouds [V] | Unknown | Private cloud possible [V] | https://idelji.com/about-us/ |
| **HPE EMS** (collector $0, distributors) | Raw operator events: subsystem, event number, text, timestamp, node | Printing distributor to a file or process [V via Infrasoft]. Custom distributor program [U] | Push, sub-second [V via Infrasoft] | Yes | https://connect2nonstop.com/ulinga-for-kafka-ems-use-case/ |
| **HPE ONS + NonStop SNMP agent** | EMS events translated to SNMP traps | SNMP traps to a network manager [V] | Push | Yes | https://ftp.hp.com/pub/softlib/NonStopOpMsgsMnl/ch69.html |
| **HPE OSM, Measure, Essentials, OneView, GreenLake** | OSM: hardware and subsystem status. Measure: performance counters | No push or API path verified [U] | Unknown | OSM, Measure: yes. GreenLake: cloud, not usable here | Not verified. See "Unverified" |
| **Infrasoft uLinga for Kafka** | Any Guardian IPC data, including EMS, as Kafka messages | Kafka producer on NonStop [V] | Yes, "sub-second" (vendor claim) | Kafka cluster can be on-prem [U] | https://connect2nonstop.com/ulinga-for-kafka-ems-use-case/ |
| **Infrasoft uLinga Nexus (MCP)** | Exposes NonStop apps to AI agents | MCP over HTTPS, OAuth 2.0 / JWT [S] | Request/response, not an event feed | On-prem [U] | https://www.infrasoft.com.au/bridging-worlds-ai-meets-nonstop-through-model-context-protocol/ [S] |
| **comforte SafePoint Logstream / Alarms** | Safeguard, SSH, iTP, EMS, sudo and keystroke logs. Real-time security alarms | **Syslog to Splunk or other collectors** [S]. Alarms: SIEM, syslog, SNMP [S] | Real-time stream | Yes [U] | https://www.comforte.com/resources/fact-sheet-safepoint-logstream [S], https://www.comforte.com/resources/safepoint-alarms [S] |
| **XYPRO XMA / XYGATE** | EMS, Safeguard, Base24, iTP and XYGATE audit data, normalised | **TCP or UDP to a target in native, CEF or custom format** [V]. TLS not mentioned [V] | "Real-time" forwarding [V] | Yes | https://xypro.com/secure-database-management/from-zero-to-hero-integrate-hpe-nonstop-with-splunk/ |
| **ETI-NET Sentinel** | CPU/process/disk metrics (poll as often as 5 s), MQ, TMF, EMS display | Grafana dashboards [V]. No alert push documented [V] | Polled metrics | Yes [U] | https://connect2nonstop.com/new-sentinel-release-enhances-hpe-nonstop-monitoring/ |
| **Insider Technologies (Reflect)** | Unknown | Nothing found [U] | Unknown | Unknown | Search returned nothing |
| **TCM / Lusis** | Unknown | Nothing found [U] | Unknown | Unknown | Search returned nothing |
| **Splunk** | Aggregated logs | HTTP Event Collector (HEC) for inbound; alert webhooks for outbound [U] | Yes | Splunk Enterprise on-prem [U] | https://docs.splunk.com/Documentation/Splunk/latest/Data/UsetheHTTPEventCollector (not fetched; 403) |
| **ServiceNow, Dynatrace, Datadog, PagerDuty** | Incidents, alerts | REST/webhook, mostly SaaS | Yes | Usually cloud. Cannot depend on them [U] | Not fetched |
| **Kafka (generic)** | Any | Consumer API | Yes | Yes | See uLinga row |

Most commonly deployed on NonStop sites: **no source found that ranks deployment.** IR describes Prognosis as "many people's solution of choice" for NonStop. That is vendor marketing. [V] https://www.ir.com/blog/hpe-nonstop/delivering-value-for-nonstop-x-users. Idelji claims Web ViewPoint "became the standard," also marketing. [V] https://idelji.com/about-us/. Ask CAIL which tools its customers actually run.

---

## 3. Per-tool notes

**IR Prognosis / Iris.** IR's NonStop package says it integrates availability and performance data with Tivoli/Netcool, ServiceNow and "any SNMP trap compatible system" [S]. A customer story says admins choose email or SNMP traps to their manager of managers [S]. An IR community thread confirms a "SNMP Traps Out" destination that can include record field values, and a "ptrapmib" MIB. One user reports that the MIB has no variable for the source device IP [S]. Alert Blueprints exist to pull in data from other records [S]. Iris (June 2026, Prognosis 13.3) is an AI layer on top of Prognosis telemetry. It is a competitor in spirit to what we build, and a possible partner [V]. Auth model and any REST/webhook output are unknown.

**Idelji Web ViewPoint Enterprise.** The best-documented push path found. Admin > Delivery has SNMP, Syslog, JSON and SMTP sections. Syslog and JSON each ask only for an IP/DNS name and port [V]. SNMP supports v1, v2c and v3 (noAuth, MD5/SHA auth, DES privacy), default port 162, and ships MIBs in the WVPMIB file [V]. It reads EMS and alerts on specific events [S], and the alert log records forwarding to ServiceNow and automated recovery actions [S]. JSON payload fields, syslog format and trap varbinds are not documented on the pages read [U]. No REST API reference was found [V].

**BlackWood MOMI.** Interactive monitor with a PC client and NonStop server component. No evidence of push output. If a customer uses MOMI only, the fallback is to tap EMS directly (below).

**HPE EMS.** The collector at $0 receives events. A distributor can be started as `EMSDIST /NOWAIT/ COLLECTOR $0, TYPE PRINTING, TEXTOUT <process>`, which sends event text to any Guardian process [V]. This is exactly what uLinga for Kafka uses. Any shipper that accepts Guardian IPC can sit on the other end (Kafka, syslog, or a small forwarder), and no login from our side is needed. The customer's NonStop admin sets it up once. Token detail is in section 4.

**HPE ONS and SNMP agent.** ONS gathers EMS events from $0, translates them into SNMP traps, and sends them via the Tandem SNMP Agent. It stops if the agent stops responding, or if the network manager does not connect within two hours of startup [V]. Mapping rules and MIB are not in the page read [U], so we need the MIB from the customer. Treat ONS as the "native SNMP" path for sites with no commercial tool.

**OSM, Measure, NonStop Essentials, OneView, GreenLake.** No push feed or API could be verified. Treat as out of scope. Measure data is normally read via a tool (Prognosis, MOMI, Idelji). GreenLake is cloud and conflicts with the on-prem constraint.

**comforte SafePoint.** Security-oriented streaming to syslog and Splunk [S]. Useful for security patterns (failed logons, Safeguard changes), less for performance.

**XYPRO XMA.** Forwards normalised EMS, Safeguard and other logs in real time over TCP or UDP in native, CEF or custom format [V]. TLS is not mentioned. Merged Audit can also emit CEF to ArcSight [S] https://www.microfocus.com/marketplace/cybersecurity/content/xypro-xygate-merged-audit-xma. XS1 forwards correlated incidents rather than raw events (vendor claim) [S] https://connect2nonstop.com/proactive-security-and-threat-detection-its-not-that-siemple/.

**ETI-NET Sentinel.** Polls CPU, process and disk metrics every 5 s and stores them for Grafana [V]. No alert push documented. Any metric pull would depend on Grafana or its datastore, which is unverified.

**Insider Technologies, TCM/Lusis.** Nothing found. Ask CAIL whether customers use them.

**uLinga Nexus (MCP).** Lets AI agents call into NonStop apps over HTTPS with OAuth 2.0 and JWT [S]. Useful later for the copilot to query live data, not for the event watcher. It would break our "no NonStop access" rule if used for polling.

**Generic enterprise tools.** Splunk, ServiceNow, Dynatrace, Datadog and PagerDuty are downstream consumers. Where a customer already forwards NonStop data into Splunk, a Splunk alert webhook to our endpoint is a valid fourth path, but we could not fetch their docs this session [U].

---

## 4. Recommended architecture (keep it simple)

One small service ("watcher-ingest") with **three listeners that all write the same normalised event** to one queue, then the matcher runs on it. No Kafka unless a customer already has it.

```
  Prognosis ---SNMP trap---------+
  WVP E ------SNMP/Syslog/JSON---+--> [ UDP 162 trap rx ]  --+
  XMA/comforte --Syslog/CEF-----+--> [ TCP/UDP 514 syslog ] -+--> normalise --> event queue --> pattern matcher --> alert + fix + citations
  EMS distributor -> shipper ---+--> [ HTTPS POST /ingest ] -+
  (Kafka consumers: optional 4th adapter, only if site has uLinga/Kafka)
```

1. **HTTP webhook** `POST /ingest/{source}` with JSON. Covers WVP E JSON, Splunk or ServiceNow webhooks, custom forwarders, and the demo replayer.
2. **Syslog listener**, UDP and TCP 514, RFC 3164 and 5424, with a CEF parser. Covers WVP E syslog, XMA, comforte Logstream, EMS via a syslog shipper.
3. **SNMP trap receiver**, UDP 162, v2c and v3. Covers Prognosis, WVP E, ONS. Needs the customer's MIBs to turn varbinds into field names. If a MIB is missing, store raw OIDs and map by OID in config.

Rationale: every tool with a verified push path in section 2 uses one of these three.

### Normalised event schema

| Field | Type | Notes |
|---|---|---|
| `event_id` | string | UUID we assign |
| `source_tool` | enum | `prognosis`, `wvpe`, `momi`, `xma`, `comforte`, `ems_raw`, `snmp_generic`, `replay` |
| `source_kind` | enum | `event`, `alert`, `metric` |
| `transport` | enum | `webhook`, `syslog`, `snmp` |
| `ts_event` | ISO-8601 UTC | Time the tool says it occurred |
| `ts_received` | ISO-8601 UTC | When we got it |
| `node` | string | NonStop system or node name |
| `subsystem` | string | For EMS: subsystem ID, such as TMF, DISK, TCPIP |
| `event_number` | int or null | EMS event number |
| `severity` | enum | `critical`, `major`, `minor`, `warning`, `info`, mapped per tool |
| `entity` | string | Process, disk, CPU, CLIM, Pathway server, or MQ queue, if present |
| `text` | string | Human-readable message |
| `metric` | object or null | `{name, value, unit, threshold, comparator}` |
| `dedupe_key` | string | Hash of node + subsystem + event_number + entity, for suppressing repeats |
| `raw` | string/object | Original payload, kept for citation and audit |
| `tags` | list | Free text, for example `customer:acme`, `env:prod` |

### Sample shapes

All three are **illustrative, not documented formats**. Replace once real samples arrive.

EMS (fields as understood: subsystem, event number, text, timestamp, node. The Operator Messages Manual confirms that displayed events carry an SSID and event number [S] https://ftp.hp.com/pub/softlib/NonStopOpMsgsMnl/ch01.html; token layout [U]):
```json
{"source_tool":"ems_raw","source_kind":"event","ts_event":"2026-10-17T14:02:11Z","node":"\\PROD1",
 "subsystem":"TMF","event_number":4107,"severity":"major","entity":"$AUDIT01","text":"<EMS text>"}
```

Prognosis alert (field names unverified, [U]):
```json
{"source_tool":"prognosis","source_kind":"alert","node":"\\PROD1","severity":"critical",
 "entity":"CPU 3","metric":{"name":"cpu_busy","value":97,"unit":"%","threshold":90,"comparator":">"},
 "text":"CPU busy above threshold"}
```

Syslog (generic RFC 5424; actual WVP E and XMA text formats unknown [U]):
```
<131>1 2026-10-17T14:02:11Z prod1 wvpe - - - [alert] Disk $DATA03 full 96%
```

---

## 5. Demo replay plan (same code path as production)

1. Record a **JSONL feed** (one raw event per line plus `delay_ms` or an absolute timestamp) built from the sample payloads above, or from a real customer export when CAIL provides one.
2. Write a replayer script (about 50 lines) with a `--speed` multiplier. For each line it re-emits the **original wire format**:
   - webhook events: HTTPS POST to `/ingest/{source}`
   - syslog events: send the line to UDP/TCP 514 (Linux `logger -n host -P 514`, or a socket)
   - SNMP events: `snmptrap -v2c -c public host:162 ...` (net-snmp) with the same OIDs
3. Tag replayed events `source_tool: replay` only in `tags`, not by skipping the parser, so the demo exercises the listeners, normaliser and matcher exactly as live traffic would.
4. Script 3 to 5 scenarios that match the senior-operator warning patterns in the vault (for example: audit-trail filling, then TMF disabled; CPU saturation preceding a takeover). Each shows the alert, the fix, and the citations.
5. Keep one **recorded real feed** (anonymised) as the regression set once we have it.

---

## 6. Asks for CAIL and customers

1. Which monitoring tools each target customer actually runs, and whether "momoi" means BlackWood MOMI or something else.
2. A **sample export or alert log** from each tool (Prognosis alert export, WVP E alert log, EMS dump via EMSDIST or EMSTEXT output). Anonymised is fine.
3. **MIB files**: IR's `ptrapmib`, Idelji's `WVPMIB`, and the HPE ONS/SNMP agent MIB.
4. **Prognosis documentation**: "SNMP Traps Out" setup and any alert forwarding options, and the version (Iris needs 13.3).
5. Customer NonStop admin to configure **one outbound path** (WVP E Delivery > Syslog/JSON/SNMP, a Prognosis SNMP trap destination, or an EMS distributor to a shipper), pointed at our host.
6. **Network rules**: NonStop or tool host to our server on UDP 162, TCP/UDP 514 and TCP 443 (or our chosen port), one direction only.
7. SNMP details: version, community string (v2c) or v3 user/auth/privacy passphrases and engineID.
8. If TLS is wanted: server certificate or CA arrangements for HTTPS and syslog-over-TLS (not confirmed supported by XMA or WVP E).
9. Severity mapping and **which EMS subsystems and Prognosis alert names matter** to the senior operators.
10. Whether the site already has Kafka, uLinga, or Splunk in the middle that we can subscribe to instead.
11. Whether Iris is licensed there. Confirm with CAIL whether IR is a partner or a competitor before any integration is proposed.

---

## 7. Sources

- https://www.blackwood-systems.com/website/momi_software.htm (MOMI releases, install, licensing)
- https://www.cool-waters.co.uk/momi (MOMI distributor)
- https://www.acronymfinder.com/Multi_System-Online-Measure-Interface-(performance-monitor-product-for-the-HP-NonStop-System)-(MOMI).html (acronym, search summary)
- https://www.brightstrand.com/what-we-do/software-tools/ (MOMI description, search summary)
- https://idelji.com/about-us/ (Idelji products)
- https://idelji.com/web-viewpoint-enterprise-abg-help/overview-delivery/ (WVP E delivery methods)
- https://idelji.com/web-viewpoint-enterprise-knowledge-base/how-can-i-configure-snmp-protocol/ (WVP E SNMP)
- https://idelji.com/wvpe-abe-abf-knowledge-base/getting-started-overview/ (WVP E JSON/Syslog/ServiceNow/Splunk/Moog)
- https://idelji.com/web-viewpoint-enterprise-abg-help/do-i-have-an-option-of-viewing-alerts-that-were-generated-i-e-alert-logs/ (alert log, search summary)
- https://mcautonomy.com/2019/11/web-viewpoint-enterprise-help/ (EMSLINK, 2019, search summary)
- https://www.ir.com/hubfs/IR%20Infrastructure%20Solution%20overview_final.pdf (Prognosis integrations, search summary; PDF not machine-readable here)
- https://www.aap.com.au/aapreleases/cision20260617ae85909/ (Iris launch)
- https://www.ir.com/blog/hpe-nonstop/delivering-value-for-nonstop-x-users (Prognosis positioning)
- https://community.ir.com/t5/General/SNMP-Traps-Out-Variables/td-p/6839 (Prognosis SNMP traps out, search summary)
- https://ftp.hp.com/pub/softlib/NonStopOpMsgsMnl/ch69.html (ONS, EMS to SNMP)
- https://ftp.hp.com/pub/softlib/NonStopOpMsgsMnl/ch01.html (EMS messages, search summary)
- https://connect2nonstop.com/ulinga-for-kafka-ems-use-case/ (EMSDIST to Kafka)
- https://www.infrasoft.com.au/bridging-worlds-ai-meets-nonstop-through-model-context-protocol/ (uLinga Nexus, search summary)
- https://www.comforte.com/resources/fact-sheet-safepoint-logstream and https://www.comforte.com/resources/safepoint-alarms (search summaries; direct fetch failed)
- https://xypro.com/secure-database-management/from-zero-to-hero-integrate-hpe-nonstop-with-splunk/ (XMA forwarding)
- https://connect2nonstop.com/proactive-security-and-threat-detection-its-not-that-siemple/ (XS1, search summary)
- https://www.microfocus.com/marketplace/cybersecurity/content/xypro-xygate-merged-audit-xma (CEF to ArcSight, search summary)
- https://connect2nonstop.com/new-sentinel-release-enhances-hpe-nonstop-monitoring/ (ETI-NET Sentinel 1.1)
- https://docs.splunk.com/Documentation/Splunk/latest/Data/UsetheHTTPEventCollector (fetch returned 403, not read)

---

## 8. Unverified list

- That "momoi" means BlackWood MOMI. This is our best inference, not CAIL's confirmation.
- Whether MOMI has any alert, export, SNMP or syslog output. No documentation found.
- Prognosis: REST/webhook/syslog/Kafka output, auth model, alert field names, severity values, trap varbinds, where the server runs, and on-prem status of Iris and its LLM.
- WVP E: JSON payload schema, syslog message format, trap varbinds, TLS support, any REST API.
- EMS token layout and field names, distributor filter syntax, and any native EMS-to-syslog feature. Nothing found on EMS to syslog from HPE itself.
- ONS to SNMP mapping rules and MIB contents.
- OSM, Measure, NonStop Essentials, OneView: any push or API path. Not researched successfully.
- Insider Technologies Reflect, TCM/Lusis: nothing found.
- comforte and XYPRO TLS support, and the exact syslog format from each.
- Sentinel alert output (none documented).
- ServiceNow, Dynatrace, Datadog, PagerDuty, Splunk HEC specifics: not fetched. Treated as downstream consumers only.
- Which tools are most common on NonStop sites: no independent source found.
- All "sub-second" and "real-time" statements are vendor claims.
