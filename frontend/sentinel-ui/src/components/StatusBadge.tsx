type Decision = "APPROVED" | "REJECTED" | "RE-ROUTE" | "PENDING" | "BLOCKED" | string;

const COLORS: Record<string, string> = {
  APPROVED:  "#15803d",  // green-700  — white contrast ~4.6:1
  REJECTED:  "#b91c1c",  // red-700    — white contrast ~7.0:1
  "RE-ROUTE":"#b45309",  // amber-700  — white contrast ~4.5:1
  PENDING:   "#1d4ed8",  // blue-700   — white contrast ~5.8:1
  BLOCKED:   "#6d28d9",  // violet-700 — white contrast ~5.1:1
  ESCALATE:  "#b45309",  // amber-700  — matches report color intent, ~4.5:1
  SCANNED:   "#0f766e",  // teal-700   — white contrast ~4.8:1
};

interface Props {
  decision: Decision;
}

export function StatusBadge({ decision }: Props) {
  const color = COLORS[decision] ?? "#6b7280";
  return (
    <span
      style={{
        display: "inline-block",
        padding: "4px 14px",
        borderRadius: "9999px",
        background: color,
        color: "#fff",
        fontWeight: 700,
        fontSize: "0.85rem",
        letterSpacing: "0.05em",
        textTransform: "uppercase",
      }}
      aria-label={decision.charAt(0).toUpperCase() + decision.slice(1).toLowerCase()}
    >
      {decision}
    </span>
  );
}
