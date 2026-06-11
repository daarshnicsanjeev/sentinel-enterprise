export function DemoNotice() {
  return (
    <div
      role="note"
      aria-label="Demo mode notice"
      style={{
        display: 'flex',
        alignItems: 'center',
        gap: '10px',
        margin: '10px auto 0',
        maxWidth: '1100px',
        padding: '8px 14px',
        borderRadius: '8px',
        border: '1px solid #1e40af',
        background: 'rgba(30, 64, 175, 0.15)',
        color: '#bfdbfe',
        fontSize: '0.82rem',
        lineHeight: 1.5,
      }}
    >
      <span aria-hidden="true" style={{ fontSize: '1rem' }}>🔓</span>
      <span>
        <strong>Public demo — login disabled.</strong>{' '}
        Sign-in and role-based access (JWT with analyst/admin roles) are intentionally
        switched off here so you can explore every feature without credentials.
        Production deployments enforce authentication and RBAC on all endpoints.
      </span>
    </div>
  )
}
