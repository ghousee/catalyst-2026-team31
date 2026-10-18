# Demo script (about 6 minutes)

Before: API + UI running, `python -m backend.graph.load` and `python -m backend.graph.demo_learning` done, browser at
http://localhost:3000 (or :3001). Clear old alerts: Training Simulator → any Start resets them.

## 1. The problem, in one line (15 s)
"Five of twenty senior operators retired in six months. Juniors get the manuals, but not the judgment. We keep the judgment."

## 2. A monitoring tool raises an alarm → the fix is ready (1 min)
1. **You: … → Grace Okafor** (Veteran, switches to `\PROD`). Overview says "Good day, Grace".
2. **Alerts** → right panel "Connected monitoring tools": IR Prognosis (REST poll) and BlackWood MOMI (export folder) both
   **Connected**. Click **TMF 185 on \PROD** (Prognosis).
3. Within 10 s a **HIGH PRIORITY** card: "IR Prognosis: TMF 185 … Usually comes before TMF 187".
   Point at: *Why high* (production, leads to audit trail full, tool says critical) · *steps from Synapse*: Maria's
   do / why / not-when, word for word, plus the manual section · *Check first* commands · who to call.
4. Say: "Prognosis only told us *what*. The *what to do* comes from our graph: a retired veteran's knowledge."
5. Optional: **Any manual message** → even a message no veteran wrote about lands on its exact manual section.

## 3. It warns before the failure (1 min)
Training Simulator → **CPU down and takeover** (the brief's own scenario) → Alerts. CPU 101 → "usually comes before
Pathway 1034" → as load passes 80%: **Grace's warning pattern, about 20 min before failure**, with PEEK/Pathway checks.
`\DR` stays quiet (context never leaks).

## 4. Ask, cite, approve (1 min)
AI Assistant (as Grace): "why is the TMF audit trail filling up?" → answer with `[1]` manual and `[2]` Maria. Proposed
`TMFCOM STATUS AUDITTRAIL, DETAIL` → **Approve for simulation** → Run → output appears as a live citation.
Switch **You → Aisha Rahman** (Emerging Veteran, `\DR`): same assistant, but "can't approve, ask a veteran".

## 5. The AI learns from a veteran → Synapse connects it (1 min)
Knowledge → **Add knowledge / sign-off** → Teach as **Raj**: "On DR, if PATHCOM shows a server class FROZEN after a
restart, thaw it before starting TERMs." Answer the one follow-up → Save draft → **Approve & sign** (only Raj can).
Signed result shows the auto-created links → **See it in Synapse**: the note, now linked to Pathway, the THAW command,
the 1061 event and `\DR` (blue = auto-linked on sign-off). Ask the assistant on `\DR` and it cites the new note.

## 6. How much does a junior actually know? (1 min)
**You → Aisha** → Learning map: what she has *seen* (questions, notes, coverage) and what she *said* she knows.
**Check what I know** → TMF → answer the scenario in her words → graded (Got it / Partly / Missed) → the veteran's
answer is shown (teaching) → **Added to Synapse: aisha knows raj:h8** → See it in Synapse (green link).
"Demonstrated" goes up. Try a wrong answer ("raise FILESPERVOLUME first") → Missed, and why.

## 7. Close (15 s)
"Real manuals, fictional veterans, simulated systems. Plug in a customer's Prognosis URL or MOMI export folder and the
same cards appear with their alarms. Every step is cited; nothing runs without a veteran's approval."

Reset between runs: Training Simulator Start (clears alerts) and
`python -c "from backend.pipeline.answer import connect; c=connect().__enter__(); c.execute(\"delete from edge where rel='knows'\"); c.execute('delete from check_result'); c.commit()"`.
