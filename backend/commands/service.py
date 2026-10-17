"""Catalog-constrained command proposals with deterministic safety guards."""

from __future__ import annotations

import re
import threading
from dataclasses import dataclass
from pathlib import Path

import yaml

from backend import settings
from backend.simulator.service import NODES, Simulator, simulator


RISK_APPROVAL = {
    "read_only": "one_click",
    "state_changing": "type_node",
    "critical": "second_approver",
}
SUPPORTED_RVUS = {"rvu:L", "rvu:J", "rvu:H"}


@dataclass(frozen=True)
class CatalogEntry:
    entity_id: str
    template_id: str
    command: str
    risk: str
    subsystem: str
    explanation: str
    source_id: str
    aliases: tuple[str, ...]


@dataclass
class ProposalState:
    public: dict
    entry: CatalogEntry
    node_id: str
    approved: bool = False


def load_catalog(path: Path | None = None) -> tuple[CatalogEntry, ...]:
    source = path or settings.ROOT / "kg" / "seed" / "entities.yaml"
    data = yaml.safe_load(source.read_text(encoding="utf-8"))
    entries: list[CatalogEntry] = []
    for item in data.get("entities", []):
        if item.get("kind") != "command":
            continue
        props = item.get("props") or {}
        risk = props.get("risk")
        if risk not in RISK_APPROVAL:
            raise ValueError(f"command {item.get('id')} has unsupported risk {risk}")
        entries.append(
            CatalogEntry(
                entity_id=item["id"],
                template_id=props["template_id"],
                command=props["command"],
                risk=risk,
                subsystem=props["subsystem"],
                explanation=props["explanation"],
                source_id=props["source_id"],
                aliases=tuple(str(alias) for alias in item.get("aliases", [])),
            )
        )
    if not entries:
        raise ValueError(f"no command entries found in {source}")
    return tuple(entries)


class CommandService:
    def __init__(self, sim: Simulator = simulator, catalog: tuple[CatalogEntry, ...] | None = None):
        self.simulator = sim
        self.catalog = catalog or load_catalog()
        self._by_template = {entry.template_id: entry for entry in self.catalog}
        self._lock = threading.RLock()
        self._counter = 1
        self._proposals: dict[str, ProposalState] = {}

    def reset(self) -> None:
        with self._lock:
            self._counter = 1
            self._proposals.clear()

    def propose(self, question: str, context: dict, session_node: str) -> dict:
        node_id = context.get("site") or session_node
        system = context.get("system")
        version = context.get("version")
        if node_id not in NODES:
            raise ValueError(f"unknown node {node_id}")
        if not system:
            raise ValueError("context.system is required")
        if not version:
            raise ValueError("context.version is required")

        entry = self._select(question, system, node_id)
        if entry is None:
            return {"proposals": [], "no_template": True}

        public = self._make(entry, node_id, version, session_node)
        return {"proposals": [public], "no_template": False}

    def _make(self, entry: CatalogEntry, node_id: str, version: str, session_node: str) -> dict:
        command = self._render(entry, node_id)
        with self._lock:
            proposal_id = f"cmd-{self._counter}"
            self._counter += 1
            public = {
                "id": proposal_id,
                "template_id": entry.template_id,
                "command": command,
                "node": NODES[node_id],
                "risk": entry.risk,
                "explanation": entry.explanation,
                "source_id": entry.source_id,
                "guards": {"node_match": node_id == session_node, "rvu_ok": version in SUPPORTED_RVUS},
                "approval": {"required": RISK_APPROVAL[entry.risk]},
            }
            self._proposals[proposal_id] = ProposalState(public, entry, node_id)
        return public

    def read_only(self, system: str) -> list[CatalogEntry]:
        """The read-only (status) catalog commands of a subsystem."""
        return [e for e in self.catalog if e.subsystem == system and e.risk == "read_only"]

    def read_only_commands(self, system: str, node_id: str) -> list[tuple[str, str]]:
        """[(rendered command, explanation)] of the subsystem's read-only commands, for text hints."""
        return [(self._render(e, node_id), e.explanation) for e in self.read_only(system)]

    def status_proposals(self, system: str, context: dict, session_node: str, limit: int = 3) -> list[dict]:
        """Read-only status commands for a subsystem as ordinary proposals (same approval flow)."""
        return [self._make(e, context["site"], context["version"], session_node) for e in self.read_only(system)[:limit]]

    def dryrun(self, proposal_id: str) -> dict:
        state = self._get(proposal_id)
        return {"id": proposal_id, **self.simulator.preview(state.entry.template_id, state.public["command"], state.node_id)}

    def approve(
        self,
        proposal_id: str,
        user_id: str,
        typed_node: str | None,
        second_approver: str | None,
        session_node: str,
    ) -> dict:
        state = self._get(proposal_id)
        if state.node_id != session_node:
            return {
                "status": "rejected",
                "reason": f"Node guard: proposal targets {NODES[state.node_id]} but the session is on {NODES[session_node]}.",
            }
        if not state.public["guards"]["rvu_ok"]:
            return {"status": "rejected", "reason": "The catalog template is not approved for this RVU."}
        approval = state.public["approval"]["required"]
        if approval == "type_node" and typed_node != NODES[state.node_id]:
            return {"status": "rejected", "reason": "Typed node does not match the target node."}
        if approval == "second_approver":
            if not second_approver:
                return {
                    "status": "needs_second_approver",
                    "reason": "Critical command: a second approver must confirm.",
                }
            if second_approver == user_id:
                return {"status": "rejected", "reason": "The requester cannot be the second approver."}
        with self._lock:
            state.approved = True
        return {"status": "approved", "reason": ""}

    def execute(self, proposal_id: str, session_node: str) -> dict:
        state = self._get(proposal_id)
        if state.node_id != session_node:
            raise PermissionError("node guard failed: the session node changed after approval")
        with self._lock:
            if not state.approved:
                raise PermissionError("command has not been approved")
            state.approved = False  # approval is single-use, even if simulation raises
        return self.simulator.execute(state.entry.template_id, state.public["command"], state.node_id)

    def _get(self, proposal_id: str) -> ProposalState:
        with self._lock:
            state = self._proposals.get(proposal_id)
        if state is None:
            raise KeyError(proposal_id)
        return state

    def _select(self, question: str, system: str, node_id: str) -> CatalogEntry | None:
        text = question.lower().strip()
        if re.search(r"\b(what next|next step|then what)\b", text):
            previous = self.simulator.last_template(node_id)
            next_template = {
                "tmfcom.status_audittrail_detail": "tmfcom.status_transaction",
                "tmfcom.status_transaction": "tmfcom.abort_transaction" if node_id == "node:PROD" else None,
                "tmfcom.abort_transaction": "tmfcom.status_tmf",
            }.get(previous)
            entry = self._by_template.get(next_template or "")
            return entry if entry and entry.subsystem == system else None

        candidates = [entry for entry in self.catalog if entry.subsystem == system]
        if not candidates:
            return None
        intent = self._intent_template(text, system)
        if intent:
            return next((entry for entry in candidates if entry.template_id == intent), None)

        words = set(re.findall(r"[a-z0-9$*]+", text))
        scored: list[tuple[int, CatalogEntry]] = []
        for entry in candidates:
            terms = " ".join((entry.command, *entry.aliases)).lower()
            score = sum(1 for word in words if len(word) > 2 and word in terms)
            scored.append((score, entry))
        score, entry = max(scored, key=lambda pair: (pair[0], pair[1].template_id))
        return entry if score else None

    @staticmethod
    def _intent_template(text: str, system: str) -> str | None:
        if system == "sub:TMF":
            if re.search(r"\babort\b.*\btransaction\b|\bkill\b.*\btransaction\b", text):
                return "tmfcom.abort_transaction"
            if re.search(r"\b(active|old|stuck|long.?running|status)\b.*\btransactions?\b", text):
                return "tmfcom.status_transaction"
            if re.search(r"audit|pinn|fill", text):
                return "tmfcom.status_audittrail_detail"
            if re.search(r"begintrans", text):
                return "tmfcom.status_begintrans"
            if re.search(r"\btmf\b|transaction manager", text):
                return "tmfcom.status_tmf"
        if system == "sub:SCF-STORAGE" and re.search(r"disk|mirror|volume|revive", text):
            return "scf.status_disk_detail"
        if system == "sub:PEEK" and re.search(r"cpu|processor", text):
            return "peek.cpu"
        if system == "sub:TACL" and re.search(r"process|terminal|tacl|status", text):
            return "tacl.status_term"
        if system == "sub:FUP" and re.search(r"open|file", text):
            return "fup.listopens"
        if system == "sub:PATHWAY":
            if re.search(r"terminal|term", text):
                return "pathcom.status_term"
            if re.search(r"tcp|pathway|pathcom", text):
                return "pathcom.status_tcp"
        return None

    @staticmethod
    def _render(entry: CatalogEntry, node_id: str) -> str:
        command = entry.command
        command = command.replace("\\node(cpu).seq.num", f"{NODES[node_id]}(1).3.45678")
        command = command.replace("$vol-M", "$DATA01-M").replace("$vol", "$DATA01")
        command = re.sub(r"\bclass\b", "SETTLE-SC", command)
        command = re.sub(r"\bn\b", "2", command)
        return command


command_service = CommandService()
