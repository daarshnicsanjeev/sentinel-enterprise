import { useRef, useState, DragEvent } from "react";

interface Props {
  onFile: (file: File) => void;
  disabled: boolean;
}

export function DocumentUpload({ onFile, disabled }: Props) {
  const inputRef = useRef<HTMLInputElement>(null);
  const [dragging, setDragging] = useState(false);

  const handleDrop = (e: DragEvent<HTMLDivElement>) => {
    e.preventDefault();
    setDragging(false);
    const file = e.dataTransfer.files[0];
    if (file) onFile(file);
  };

  return (
    <div
      onDrop={handleDrop}
      onDragOver={(e) => { e.preventDefault(); setDragging(true); }}
      onDragLeave={() => setDragging(false)}
      onClick={() => !disabled && inputRef.current?.click()}
      role="button"
      tabIndex={0}
      aria-label="Upload document — click or drag and drop a file. Supported formats: PDF, Word, Excel, PowerPoint, HTML, plain text, and scanned images (PNG, JPG, TIFF)"
      aria-disabled={disabled}
      className="upload-zone"
      onKeyDown={(e) => {
        if ((e.key === "Enter" || e.key === " ") && !disabled) {
          e.preventDefault();
          inputRef.current?.click();
        }
      }}
      style={{
        border: `2px dashed ${dragging ? "#2563eb" : "#94a3b8"}`,
        borderRadius: "12px",
        padding: "40px 24px",
        textAlign: "center",
        cursor: disabled ? "not-allowed" : "pointer",
        opacity: disabled ? 0.5 : 1,
        background: dragging ? "#eff6ff" : "#f8fafc",
        transition: "border-color 0.2s, background 0.2s",
        userSelect: "none",
      }}
    >
      <div style={{ fontSize: "2.5rem", marginBottom: "8px" }}>📄</div>
      <p style={{ margin: 0, color: "#475569", fontWeight: 500 }}>
        Drag &amp; drop a document here, or click to browse
      </p>
      <p style={{ margin: "4px 0 0", color: "#94a3b8", fontSize: "0.8rem" }}>
        PDF, TXT, DOCX, XLSX, PPTX, HTML, PNG, JPG, TIFF &middot; max 5 MB
      </p>
      <input
        ref={inputRef}
        type="file"
        accept=".pdf,.txt,.docx,.xlsx,.pptx,.html,.htm,.png,.jpg,.jpeg,.tiff,.tif"
        style={{ display: "none" }}
        onChange={(e) => { const f = e.target.files?.[0]; if (f) onFile(f); }}
        disabled={disabled}
      />
    </div>
  );
}
