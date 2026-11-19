export const fmtDateTime = (iso: string | null | undefined) =>
  iso ? new Date(iso + (iso.endsWith("Z") || /[+-]\d\d:\d\d$/.test(iso) ? "" : "Z")).toLocaleString(undefined,
    { day: "numeric", month: "short", year: "numeric", hour: "2-digit", minute: "2-digit" }) : "—";

export const fmtDay = (iso: string | null | undefined) =>
  iso ? new Date(iso + (iso.endsWith("Z") || /[+-]\d\d:\d\d$/.test(iso) ? "" : "Z")).toLocaleDateString(undefined,
    { day: "numeric", month: "short", year: "numeric" }) : "";

/** 0..1 -> "63", or "—" when the signal is unavailable */
export const pct = (v: number | null | undefined) => (v === null || v === undefined ? "—" : String(Math.round(v * 100)));

export const CATEGORIES = ["Electronics", "Accessories", "Clothing", "Books & stationery", "Keys & cards",
  "Bags", "Bottles & containers", "Wallets & purses", "Umbrellas", "Other"];

export function statusChip(status: string): { cls: string; text: string } {
  switch (status) {
    case "ACTIVE": return { cls: "green", text: "Active" };
    case "RECOVERED": return { cls: "blue", text: "Returned" };
    case "RESOLVED": return { cls: "", text: "Found by owner" };
    case "PENDING": return { cls: "amber", text: "Pending staff review" };
    case "VERIFIED": return { cls: "green", text: "Verified" };
    case "COMPLETED": return { cls: "blue", text: "Completed" };
    case "REJECTED": return { cls: "red", text: "Rejected" };
    case "CANCELLED": return { cls: "", text: "Cancelled" };
    default: return { cls: "", text: status.replace(/_/g, " ").toLowerCase().replace(/^./, c => c.toUpperCase()) };
  }
}

export const CUSTODY_TEXT: Record<string, string> = {
  LEFT_WHERE_FOUND: "Left where found", TEMPORARILY_HOLDING: "With the finder",
  AWAITING_DEPOSIT_CONFIRMATION: "Awaiting deposit confirmation", DEPOSIT_CONFIRMED: "With staff",
};

export function download(blob: Blob, name: string) {
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url; a.download = name; a.click();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}

export function errorText(e: unknown): string {
  const err = e as { details?: { field: string; message: string }[]; message?: string };
  return err.details?.length ? err.details.map(d => `${d.field ? d.field + ": " : ""}${d.message}`).join(" · ") : err.message ?? "Something went wrong.";
}
