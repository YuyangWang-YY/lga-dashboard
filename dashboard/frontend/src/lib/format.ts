/**
 * Format a raw gate identifier (e.g. "Gate_61", "Gate_TB_43_43A") into the
 * compact label shown in the UI for AOC operators.
 *
 * Examples:
 *   "Gate_61"           → "61"
 *   "Gate_88B"          → "88B"
 *   "Gate_TA_6"         → "TA6"
 *   "Gate_TB_14"        → "TB14"
 *   "Gate_TB_43_43A"    → "TB43/43A"
 *   null / ""           → "—"
 */
export function formatGate(raw: string | null | undefined): string {
  if (!raw) return "—";
  // Strip leading "Gate_" / "Gate "
  let s = raw.replace(/^Gate[_\s]*/i, "");
  // If the remainder starts with a terminal token "TA"/"TB"/"TC" followed by
  // an underscore, remove that underscore so "TB_14" → "TB14".
  s = s.replace(/^(T[ABC])_/, "$1");
  // Any remaining underscores between gate-number variants become "/".
  s = s.replace(/_/g, "/");
  return s.trim() || "—";
}
