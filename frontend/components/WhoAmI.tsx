"use client";

import { ChevronDown } from "lucide-react";
import { useEffect, useState } from "react";
import { admin, type Person } from "@/lib/admin";
import { useDismiss } from "@/lib/hooks";
import { learning, type LearningUser } from "@/lib/learning";
import { setMe, toUserId, useMe } from "@/lib/me";

/** Top-bar picker: who is using the app. Seniors are person rows; a junior is any name (their Learning map is keyed by it). */
export function WhoAmI({ onNewJunior }: { onNewJunior?: () => void }) {
  const me = useMe();
  const [open, setOpen] = useState(false);
  const [persons, setPersons] = useState<Person[]>([]);
  const [juniors, setJuniors] = useState<LearningUser[]>([]);
  const [name, setName] = useState("");
  const ref = useDismiss<HTMLDivElement>(open, () => setOpen(false));

  useEffect(() => {
    if (!open) return;
    admin.persons().then(setPersons).catch(() => setPersons([]));
    learning.users().then(setJuniors).catch(() => setJuniors([]));
  }, [open]);

  const seniorIds = new Set(persons.map((p) => p.id));
  const pick = (id: string, label: string, role: "junior" | "senior") => {
    setMe({ id, name: label, role });
    setOpen(false);
  };
  const startNew = (e: React.FormEvent) => {
    e.preventDefault();
    const id = toUserId(name);
    if (!id) return;
    pick(id, name.trim(), "junior");
    setName("");
    onNewJunior?.();
  };

  return (
    <div ref={ref} className="relative">
      <button type="button" className="btn h-8 gap-1.5 text-[12.5px]" aria-expanded={open} aria-haspopup="dialog" onClick={() => setOpen((o) => !o)}>
        <span className="text-muted">You:</span> <span className="max-w-[140px] truncate font-medium">{me.name}</span>
        <span className="text-muted">· {me.role}</span>
        <ChevronDown size={13} aria-hidden="true" />
      </button>
      {open && (
        <div role="dialog" aria-label="Who are you?" className="absolute right-0 top-10 z-50 w-72 rounded border border-line bg-panel p-3 text-[13px] shadow-lg">
          <form onSubmit={startNew} className="space-y-1.5">
            <p className="font-medium">New here?</p>
            <div className="flex gap-2">
              <input className="field h-8 min-w-0 flex-1" placeholder="Your name" value={name} onChange={(e) => setName(e.target.value)} aria-label="Your name" />
              <button type="submit" className="btn btn-primary h-8" disabled={!toUserId(name)}>Start</button>
            </div>
            <p className="text-[11.5px] text-muted">Starts you as a junior with your own Learning map.</p>
          </form>
          <p className="mt-3 border-t border-line pt-2 text-xs text-muted">Seniors (can teach and sign notes)</p>
          <ul>
            {persons.map((p) => (
              <li key={p.id}>
                <button type="button" className="w-full py-1 text-left hover:text-accent" onClick={() => pick(p.id, p.name, "senior")}>
                  {p.name} <span className="text-xs text-muted">{p.role ?? ""}</span>
                </button>
              </li>
            ))}
          </ul>
          {juniors.some((j) => !seniorIds.has(j.user_id)) && <p className="mt-2 border-t border-line pt-2 text-xs text-muted">Juniors</p>}
          <ul>
            {juniors.filter((j) => !seniorIds.has(j.user_id)).map((j) => (
              <li key={j.user_id}>
                <button type="button" className="w-full py-1 text-left hover:text-accent" onClick={() => pick(j.user_id, j.user_id, "junior")}>
                  {j.user_id} <span className="text-xs text-muted">{j.questions} questions</span>
                </button>
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}
