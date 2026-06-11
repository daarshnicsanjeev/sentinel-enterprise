import { useState } from 'react'

interface Props {
  apiBase: string
}

const inputStyle: React.CSSProperties = {
  width: '100%',
  padding: '8px 10px',
  borderRadius: '6px',
  border: '1px solid #334155',
  background: '#0f172a',
  color: '#e2e8f0',
  fontSize: '0.85rem',
  boxSizing: 'border-box',
}

const labelStyle: React.CSSProperties = {
  display: 'block',
  color: '#94a3b8',
  fontSize: '0.78rem',
  marginBottom: '4px',
}

export function DemoFeedback({ apiBase }: Props) {
  const [name, setName] = useState('')
  const [email, setEmail] = useState('')
  const [message, setMessage] = useState('')
  const [rating, setRating] = useState<number | null>(null)
  const [status, setStatus] = useState<'idle' | 'sending' | 'done' | 'error'>('idle')
  const [error, setError] = useState('')

  const submit = async (e: React.FormEvent) => {
    e.preventDefault()
    if (message.trim().length < 10) {
      setError('Please write at least 10 characters so the feedback is actionable.')
      return
    }
    setError('')
    setStatus('sending')
    try {
      const res = await fetch(`${apiBase}/api/demo-feedback`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          name: name.trim(),
          email: email.trim(),
          message: message.trim(),
          ...(rating ? { rating } : {}),
        }),
      })
      if (!res.ok) throw new Error(`HTTP ${res.status}`)
      setStatus('done')
    } catch {
      setStatus('error')
      setError('Could not send feedback right now — please try again in a minute.')
    }
  }

  if (status === 'done') {
    return (
      <section
        aria-label="Demo feedback"
        style={{
          margin: '28px auto 12px',
          maxWidth: '1100px',
          padding: '18px',
          borderRadius: '10px',
          border: '1px solid #15803d',
          background: 'rgba(21, 128, 61, 0.12)',
          color: '#86efac',
          textAlign: 'center',
        }}
      >
        <p role="status" style={{ margin: 0, fontWeight: 600 }}>
          ✓ Thank you! Your feedback was delivered to the developer.
        </p>
      </section>
    )
  }

  return (
    <section
      aria-label="Demo feedback"
      style={{
        margin: '28px auto 12px',
        maxWidth: '1100px',
        padding: '18px',
        borderRadius: '10px',
        border: '1px solid #334155',
        background: '#0b1220',
      }}
    >
      <h2 style={{ color: '#e2e8f0', fontSize: '1rem', margin: '0 0 4px' }}>
        Feedback on this demo
      </h2>
      <p style={{ color: '#94a3b8', fontSize: '0.8rem', margin: '0 0 14px' }}>
        Spotted a bug, have a suggestion, or want to talk about this project?
        Your message goes straight to the developer.
      </p>

      <form onSubmit={submit} noValidate>
        <div style={{ display: 'flex', gap: '12px', flexWrap: 'wrap', marginBottom: '10px' }}>
          <div style={{ flex: '1 1 220px' }}>
            <label htmlFor="fb-name" style={labelStyle}>Name (optional)</label>
            <input
              id="fb-name" type="text" value={name} maxLength={200}
              onChange={(e) => setName(e.target.value)} style={inputStyle}
            />
          </div>
          <div style={{ flex: '1 1 220px' }}>
            <label htmlFor="fb-email" style={labelStyle}>Email (optional, for a reply)</label>
            <input
              id="fb-email" type="email" value={email} maxLength={320}
              onChange={(e) => setEmail(e.target.value)} style={inputStyle}
            />
          </div>
        </div>

        <label htmlFor="fb-message" style={labelStyle}>Your feedback *</label>
        <textarea
          id="fb-message" required value={message} maxLength={5000} rows={4}
          onChange={(e) => setMessage(e.target.value)}
          style={{ ...inputStyle, resize: 'vertical', fontFamily: 'inherit' }}
        />

        <fieldset style={{ border: 'none', padding: 0, margin: '12px 0' }}>
          <legend style={labelStyle}>How would you rate this demo? (optional)</legend>
          <div role="radiogroup" aria-label="Demo rating from 1 to 5 stars" style={{ display: 'flex', gap: '6px' }}>
            {[1, 2, 3, 4, 5].map((n) => (
              <button
                key={n}
                type="button"
                role="radio"
                aria-checked={rating === n}
                aria-label={`${n} star${n > 1 ? 's' : ''}`}
                onClick={() => setRating(rating === n ? null : n)}
                style={{
                  width: '38px', height: '38px',
                  borderRadius: '6px',
                  border: rating !== null && n <= rating ? '1px solid #facc15' : '1px solid #334155',
                  background: rating !== null && n <= rating ? 'rgba(250, 204, 21, 0.18)' : '#0f172a',
                  color: rating !== null && n <= rating ? '#facc15' : '#64748b',
                  fontSize: '1.1rem',
                  cursor: 'pointer',
                }}
              >
                ★
              </button>
            ))}
          </div>
        </fieldset>

        {error && (
          <p role="alert" style={{ color: '#fca5a5', fontSize: '0.8rem', margin: '0 0 10px' }}>
            {error}
          </p>
        )}

        <button
          type="submit"
          disabled={status === 'sending'}
          style={{
            padding: '8px 22px',
            borderRadius: '6px',
            border: 'none',
            background: status === 'sending' ? '#334155' : '#0f4c81',
            color: '#fff',
            fontWeight: 700,
            cursor: status === 'sending' ? 'wait' : 'pointer',
            fontSize: '0.85rem',
          }}
        >
          {status === 'sending' ? 'Sending…' : 'Send Feedback'}
        </button>
      </form>
    </section>
  )
}
