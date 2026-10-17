# glossary

## Project terms
- **context fingerprint** — subsystem + series/RVU + node on every chunk/heuristic. See [[schema]], [[ADR-004 context dimensions]].
- **lane** — 📘 doc · 👤 veteran · 🖥 live output · ⚪ refer.
- **refer** — the bot's "I don't know": route to the best expert.
- **context trap** — same question/command, different node/RVU/subsystem; the eval's headline category.
- **trigger** — a veteran's warning pattern the watcher evaluates (heuristic with `is_trigger`).

## NonStop terms (sources in docs/SYSTEM_DESIGN.md §16)
- **HPE NonStop** — fault-tolerant transaction platform (banks/ATMs, POS, telecom). Keeps running through single hardware failures.
- **Node** — one NonStop system on an **Expand** network, named `\PROD`, `\DR`. Commands can target another node with a `\node.` prefix.
- **Series / RVU** — L (NonStop X, x86/virtual), J (Itanium), H (Itanium NS). RVU = release version update.
- **Guardian / OSS** — native environment (`$VOL.SUBVOL.FILE`, TACL) vs POSIX personality (`/usr/...`).
- **TACL** — command shell (`STATUS`, `PPD`, `WHO`, `FILEINFO`, `STOP`).
- **SCF** — Subsystem Control Facility; one shell over STORAGE, EXPAND, TCPIP, Kernel… (`STATUS DISK $DATA01`).
- **PATHCOM / Pathway (TS/MP)** — TP monitor: PATHMON, server classes, TCPs, terminals. Msg 1034 = NO SERVER AVAILABLE.
- **TMF / TMFCOM** — transaction manager; **audit trail** fills when files are pinned (TMF 185) → critically full (187).
- **EMS** — event management; events identified by subsystem + number. Viewed in ViewPoint/OSM.
- **Measure / MEASCOM** — performance counters (`cpu-busy-time`, `cpu-qtime`, `request-qtime`…).
- **PEEK** — per-CPU memory/paging stats (FREE, FREEMIN, FAULTS).
- **FUP** — file utility (`INFO`, `LISTOPENS`, `PURGE`).
- **Process pair** — primary + backup process in different CPUs; backup takes over on CPU failure.
- **Mirror / revive** — mirrored disk volumes; revive re-syncs a downed half.
- **6530** — the NonStop terminal type CAIL emulates (CAIL/Suite).
- **BASE24 / Connex** — ATM/POS switch apps on NonStop (proprietary; not modelled).
