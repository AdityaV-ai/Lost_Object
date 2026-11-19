import type { Match, Timeline } from "../api/types";
import { fmtDay, pct } from "../utils";

const STEPS = ["Report submitted", "Potential match found", "You said “this might be mine”", "Staff verified ownership", "Item returned to you"];

export function Stepper({ t }: { t: Timeline }) {
  const dates = [t.submitted_at, t.first_match_at, t.claimed_at, t.verified_at, t.completed_at];
  return (
    <ol className="stepper" aria-label="Recovery progress" style={{ listStyle: "none", margin: 0 }}>
      {STEPS.map((label, i) => {
        const done = dates[i] !== null, current = t.current_step === i + 1;
        return (
          <li key={label} className={`step${done ? " done" : ""}${current ? " current" : ""}`} aria-current={current ? "step" : undefined}>
            <div className="c">{done ? "✓" : i + 1}</div>{label}
            <small>{done ? fmtDay(dates[i]) : " "}</small>
          </li>
        );
      })}
    </ol>
  );
}

export function Signal({ label, v }: { label: string; v: number | null }) {
  return (
    <div className="sig" title={v === null ? "Not available for this pair" : undefined}>
      <span>{label}</span>
      <div className="bar" role="meter" aria-label={label} aria-valuemin={0} aria-valuemax={100} aria-valuenow={v === null ? undefined : Math.round(v * 100)}>
        <i style={{ width: `${v === null ? 0 : Math.round(v * 100)}%` }} /></div>
      <span>{pct(v)}</span>
    </div>
  );
}

/** The four matching signals. A dash means the signal was unavailable and was excluded from the score. */
export function SignalBars({ m }: { m: Pick<Match, "image_similarity" | "words_photo_similarity" | "text_similarity" | "location_similarity"> }) {
  return (
    <div className="bars">
      <Signal label="Photo" v={m.image_similarity} />
      <Signal label="Words↔photo" v={m.words_photo_similarity} />
      <Signal label="Text" v={m.text_similarity} />
      <Signal label="Location" v={m.location_similarity} />
    </div>
  );
}
