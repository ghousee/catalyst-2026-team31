import type { ChatMsg } from "@/lib/store";
import { ClaimList } from "./ClaimList";

type ObsMsg = Extract<ChatMsg, { kind: "observation" }>;

export function ObservationCard({ msg }: { msg: ObsMsg }) {
  return (
    <section aria-label="Live observation" className="card space-y-2 border-ok/40 p-3">
      <h4 className="label !text-ok">Observed from command output</h4>
      <ClaimList claims={[msg.claim]} sources={[msg.source]} />
    </section>
  );
}
