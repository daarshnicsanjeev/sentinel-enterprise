import { useState } from "react";

interface Props {
  traceId: string;
  apiBase: string;
}

export function FeedbackWidget({ traceId, apiBase }: Props) {
  const [step, setStep] = useState<"idle" | "comment" | "done">("idle");
  const [comment, setComment] = useState("");
  const [submitted, setSubmitted] = useState<"positive" | "negative" | null>(null);
  const [error, setError] = useState(false);

  const submit = async (rating: "positive" | "negative", commentText = "") => {
    try {
      const res = await fetch(`${apiBase}/api/feedback/${traceId}`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ rating, comment: commentText }),
      });
      if (res.ok) {
        setSubmitted(rating);
        setStep("done");
      } else {
        setError(true);
      }
    } catch {
      setError(true);
    }
  };

  if (step === "done" && submitted) {
    return (
      <p
        aria-live="polite"
        style={{ color: "#64748b", fontSize: "0.82rem", marginTop: "16px" }}
      >
        {submitted === "positive"
          ? "✓ Thanks for the positive feedback."
          : "✓ Feedback recorded — we'll review this result."}
      </p>
    );
  }

  if (step === "comment") {
    return (
      <div
        role="group"
        aria-label="Rate this analysis"
        style={{ marginTop: "16px" }}
      >
        <label
          htmlFor={`fb-comment-${traceId}`}
          style={{ color: "#94a3b8", fontSize: "0.82rem", display: "block", marginBottom: "6px" }}
        >
          What was wrong? <span style={{ color: "#475569" }}>(optional)</span>
        </label>
        <textarea
          id={`fb-comment-${traceId}`}
          aria-label="What was wrong"
          value={comment}
          onChange={(e) => setComment(e.target.value.slice(0, 500))}
          rows={2}
          placeholder="e.g. Missed indemnity clause, wrong doc type…"
          style={{
            width: "100%",
            background: "#0f172a",
            border: "1px solid #334155",
            borderRadius: "6px",
            color: "#e2e8f0",
            padding: "8px 10px",
            fontSize: "0.82rem",
            resize: "vertical",
            fontFamily: "inherit",
            boxSizing: "border-box",
          }}
        />
        <div style={{ display: "flex", gap: "8px", marginTop: "8px" }}>
          <button
            onClick={() => submit("negative", comment)}
            aria-label="Submit feedback"
            style={{
              background: "#b91c1c",
              border: "none",
              borderRadius: "6px",
              padding: "6px 16px",
              color: "#fff",
              fontWeight: 700,
              fontSize: "0.82rem",
              cursor: "pointer",
            }}
          >
            Submit feedback
          </button>
          <button
            onClick={() => setStep("idle")}
            aria-label="Cancel feedback"
            style={{
              background: "none",
              border: "1px solid #334155",
              borderRadius: "6px",
              padding: "6px 12px",
              color: "#64748b",
              fontSize: "0.82rem",
              cursor: "pointer",
            }}
          >
            Cancel
          </button>
        </div>
        {error && (
          <span
            role="alert"
            style={{ color: "#dc2626", fontSize: "0.78rem", display: "block", marginTop: "6px" }}
          >
            Could not submit feedback.
          </span>
        )}
      </div>
    );
  }

  // idle — show thumbs buttons
  return (
    <div
      role="group"
      aria-label="Rate this analysis"
      style={{ display: "flex", alignItems: "center", gap: "8px", marginTop: "16px" }}
    >
      <span style={{ color: "#94a3b8", fontSize: "0.82rem" }}>
        Was this analysis helpful?
      </span>
      <button
        onClick={() => submit("positive")}
        aria-label="Mark analysis as helpful"
        style={{
          background: "none",
          border: "1px solid #334155",
          borderRadius: "6px",
          padding: "4px 10px",
          cursor: "pointer",
          fontSize: "1rem",
          color: "#e2e8f0",
        }}
      >
        👍
      </button>
      <button
        onClick={() => setStep("comment")}
        aria-label="Mark analysis as unhelpful"
        style={{
          background: "none",
          border: "1px solid #334155",
          borderRadius: "6px",
          padding: "4px 10px",
          cursor: "pointer",
          fontSize: "1rem",
          color: "#e2e8f0",
        }}
      >
        👎
      </button>
      {error && (
        <span
          role="alert"
          style={{ color: "#dc2626", fontSize: "0.78rem" }}
        >
          Could not submit feedback.
        </span>
      )}
    </div>
  );
}
