interface ClauseResult {
  clause: string
  status: string
  evidence?: string
}

interface Props {
  history: ClauseResult[][]
}

export function ClauseDiffViewer({ history }: Props) {
  if (!history || history.length < 2) return null

  const attempt1 = history[history.length - 2]
  const attempt2 = history[history.length - 1]

  // Use the shorter list to avoid index-out-of-bounds when clause counts differ between retries
  const count = Math.min(attempt1.length, attempt2.length)
  const clauses = attempt2.slice(0, count).map((c) => c.clause)

  const statusColor = (s: string) => {
    if (s === 'PRESENT') return '#15803d'
    if (s === 'MISSING') return '#b91c1c'
    return '#6b7280' // neutral grey for any unexpected server value
  }

  return (
    <div style={{ marginTop: '20px' }}>
      <h3 style={{ color: '#e2e8f0', marginBottom: '10px', fontSize: '14px' }}>
        Retry Diff — Clause Changes Between Attempts
      </h3>
      <div style={{ overflowX: 'auto' }}>
        <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '13px' }}>
          <thead>
            <tr>
              {['Clause', 'Attempt 1', 'Attempt 2'].map((h) => (
                <th
                  key={h}
                  style={{
                    padding: '8px 12px',
                    textAlign: 'left',
                    color: '#94a3b8',
                    borderBottom: '1px solid #334155',
                    fontWeight: 600,
                  }}
                >
                  {h}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {clauses.map((clause, idx) => {
              const s1 = attempt1[idx].status
              const s2 = attempt2[idx].status
              const changed = s1 !== s2
              return (
                <tr
                  key={clause}
                  style={{ background: changed ? 'rgba(234, 179, 8, 0.08)' : 'transparent' }}
                >
                  <td style={{ padding: '8px 12px', color: '#e2e8f0' }}>{clause}</td>
                  <td style={{ padding: '8px 12px', color: statusColor(s1), fontWeight: 600 }}>{s1}</td>
                  <td style={{ padding: '8px 12px', color: statusColor(s2), fontWeight: 600 }}>{s2}</td>
                </tr>
              )
            })}
          </tbody>
        </table>
      </div>
    </div>
  )
}
