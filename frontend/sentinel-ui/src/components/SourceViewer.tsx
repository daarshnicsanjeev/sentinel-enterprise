import { useEffect, useRef, useState } from 'react'

interface Props {
  traceId: string
  apiBase: string
  /** Evidence strings to highlight inside the source text. */
  highlights?: string[]
}

interface SourcePayload {
  trace_id: string
  filename: string
  raw_text: string
  truncated?: boolean
}

/** Build a whitespace-tolerant regex for an evidence quote, since PDF/OCR
 * extraction may differ in line breaks from what the chunker stored. */
function evidencePattern(quote: string): RegExp | null {
  const tokens = quote.split(/\s+/).filter(Boolean)
  if (tokens.length === 0) return null
  const escaped = tokens.map((t) => t.replace(/[.*+?^${}()|[\]\\]/g, '\\$&'))
  return new RegExp(escaped.join('\\s+'), 'gi')
}

/** Split text into plain/highlighted segments for the given evidence quotes. */
export function buildSegments(
  text: string,
  highlights: string[],
): Array<{ text: string; marked: boolean }> {
  const ranges: Array<[number, number]> = []
  for (const quote of highlights) {
    const pattern = evidencePattern(quote)
    if (!pattern) continue
    for (const m of text.matchAll(pattern)) {
      if (m.index !== undefined && m[0].length > 0) ranges.push([m.index, m.index + m[0].length])
    }
  }
  if (ranges.length === 0) return [{ text, marked: false }]

  ranges.sort((a, b) => a[0] - b[0])
  const merged: Array<[number, number]> = []
  for (const [s, e] of ranges) {
    const last = merged[merged.length - 1]
    if (last && s <= last[1]) last[1] = Math.max(last[1], e)
    else merged.push([s, e])
  }

  const segments: Array<{ text: string; marked: boolean }> = []
  let pos = 0
  for (const [s, e] of merged) {
    if (s > pos) segments.push({ text: text.slice(pos, s), marked: false })
    segments.push({ text: text.slice(s, e), marked: true })
    pos = e
  }
  if (pos < text.length) segments.push({ text: text.slice(pos), marked: false })
  return segments
}

export function SourceViewer({ traceId, apiBase, highlights = [] }: Props) {
  const [open, setOpen] = useState(false)
  const [source, setSource] = useState<SourcePayload | null>(null)
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)
  const closeButtonRef = useRef<HTMLButtonElement>(null)

  useEffect(() => {
    if (!open) return
    closeButtonRef.current?.focus()
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') setOpen(false)
    }
    document.addEventListener('keydown', onKey)
    return () => document.removeEventListener('keydown', onKey)
  }, [open])

  const show = async () => {
    setOpen(true)
    if (source) return
    setLoading(true)
    setError('')
    try {
      const res = await fetch(`${apiBase}/api/history/${traceId}/source`)
      if (!res.ok) {
        setError(
          res.status === 404
            ? 'Source text is not available for this analysis.'
            : 'Could not load the source document.',
        )
        return
      }
      setSource(await res.json())
    } catch {
      setError('Could not load the source document.')
    } finally {
      setLoading(false)
    }
  }

  return (
    <>
      <button
        onClick={show}
        aria-haspopup="dialog"
        style={{
          marginTop: '10px',
          padding: '6px 14px',
          borderRadius: '6px',
          border: '1px solid #334155',
          background: '#1e293b',
          color: '#e2e8f0',
          fontWeight: 600,
          cursor: 'pointer',
          fontSize: '0.82rem',
        }}
      >
        View Source Document
      </button>

      {open && (
        <div
          role="dialog"
          aria-modal="true"
          aria-labelledby="source-viewer-title"
          style={{
            position: 'fixed',
            inset: 0,
            background: 'rgba(0,0,0,0.7)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            zIndex: 1000,
          }}
        >
          <div
            style={{
              background: '#0f172a',
              border: '1px solid #334155',
              borderRadius: '10px',
              width: 'min(820px, 92vw)',
              maxHeight: '84vh',
              display: 'flex',
              flexDirection: 'column',
              padding: '18px',
            }}
          >
            <div
              style={{
                display: 'flex',
                justifyContent: 'space-between',
                alignItems: 'center',
                marginBottom: '10px',
              }}
            >
              <h3 id="source-viewer-title" style={{ color: '#e2e8f0', fontSize: '0.95rem', margin: 0 }}>
                Source Document{source ? ` — ${source.filename}` : ''}
              </h3>
              <button
                ref={closeButtonRef}
                onClick={() => setOpen(false)}
                aria-label="Close source viewer"
                style={{
                  border: '1px solid #334155',
                  background: '#1e293b',
                  color: '#e2e8f0',
                  borderRadius: '6px',
                  padding: '4px 12px',
                  cursor: 'pointer',
                  fontWeight: 700,
                }}
              >
                Close
              </button>
            </div>

            {highlights.length > 0 && (
              <p style={{ color: '#94a3b8', fontSize: '0.78rem', margin: '0 0 8px' }}>
                Highlighted passages are the exact evidence cited by the compliance agent,
                verified to appear in this document.
              </p>
            )}

            {source?.truncated && (
              <p
                role="note"
                style={{
                  color: '#fbbf24',
                  fontSize: '0.78rem',
                  margin: '0 0 8px',
                  border: '1px solid #92400e',
                  borderRadius: '6px',
                  padding: '6px 10px',
                  background: 'rgba(146, 64, 14, 0.15)',
                }}
              >
                This document was truncated for storage — text and citation highlights
                beyond the stored portion are not shown.
              </p>
            )}

            <div
              style={{ overflowY: 'auto', flex: 1 }}
              aria-live="polite"
              aria-busy={loading}
            >
              {loading && <p style={{ color: '#94a3b8' }}>Loading source text…</p>}
              {error && (
                <p role="alert" style={{ color: '#fca5a5' }}>
                  {error}
                </p>
              )}
              {source && (
                <pre
                  style={{
                    whiteSpace: 'pre-wrap',
                    wordBreak: 'break-word',
                    color: '#cbd5e1',
                    fontSize: '0.82rem',
                    lineHeight: 1.55,
                    fontFamily: 'ui-monospace, monospace',
                    margin: 0,
                  }}
                >
                  {buildSegments(source.raw_text, highlights).map((seg, i) =>
                    seg.marked ? (
                      <mark
                        key={i}
                        style={{ background: '#facc15', color: '#1f2937', padding: '0 2px', borderRadius: '2px' }}
                      >
                        {seg.text}
                      </mark>
                    ) : (
                      <span key={i}>{seg.text}</span>
                    ),
                  )}
                </pre>
              )}
            </div>
          </div>
        </div>
      )}
    </>
  )
}
