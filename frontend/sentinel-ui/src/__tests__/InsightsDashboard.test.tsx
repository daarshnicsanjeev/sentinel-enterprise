/**
 * TDD spec for InsightsDashboard component (Phase G).
 * Run: node_modules\.bin\vitest run src/__tests__/InsightsDashboard.test.tsx
 */
import { render, screen, fireEvent, waitFor, within } from '@testing-library/react'
import { vi } from 'vitest'
import { InsightsDashboard } from '../components/InsightsDashboard'

// ── Mock data ────────────────────────────────────────────────────────────────

const MOCK_METRICS = {
  feedback: { total: 12, positive: 8, negative: 4, negative_rate_pct: 33.3 },
}

const MOCK_FEEDBACK_ROWS = [
  {
    trace_id: 'tr1',
    rating: 'negative' as const,
    comment: 'wrong clause detected',
    created_at: '2026-05-01T10:00:00',
    filename: 'contract.pdf',
    decision: 'ROUTE_TO_LEGAL',
    doc_type: 'NDA',
  },
  {
    trace_id: 'tr2',
    rating: 'positive' as const,
    comment: '',
    created_at: '2026-05-02T10:00:00',
    filename: 'nda_signed.pdf',
    decision: 'APPROVE',
    doc_type: 'NDA',
  },
]

const PENDING_REC = {
  rec_id: 'rec-pending',
  doc_type: 'NDA',
  rec_type: 'missing_rule' as const,
  proposed: 'indemnity clause',
  evidence_count: 3,
  confidence: 'high' as const,
  rationale: '3 users flagged a missing indemnity clause.',
  status: 'pending' as const,
  created_at: '2026-05-01T10:00:00',
  resolved_at: null,
}

const APPROVED_REC = {
  ...PENDING_REC,
  rec_id: 'rec-approved',
  status: 'approved' as const,
  resolved_at: '2026-05-02T10:00:00',
}

const REJECTED_REC = {
  ...PENDING_REC,
  rec_id: 'rec-rejected',
  doc_type: 'LEGAL_CONTRACT',
  proposed: 'arbitration clause',
  status: 'rejected' as const,
  resolved_at: '2026-05-02T10:00:00',
}

const UNDONE_REC = {
  ...PENDING_REC,
  rec_id: 'rec-undone',
  status: 'undone' as const,
  resolved_at: '2026-05-03T10:00:00',
}

// ── Fetch mock helpers ────────────────────────────────────────────────────────

/**
 * Sets up the three initial data-load fetches that InsightsDashboard fires on mount.
 * Returns the mock so callers can chain additional `mockImplementationOnce` calls.
 */
function mockInitialLoad(recs = [PENDING_REC]) {
  return vi.spyOn(global, 'fetch').mockImplementation((url) => {
    const u = url.toString()
    if (u.includes('/api/metrics/summary')) {
      return Promise.resolve({
        ok: true,
        json: async () => MOCK_METRICS,
      } as Response)
    }
    if (u.includes('/api/feedback/summary')) {
      return Promise.resolve({
        ok: true,
        json: async () => MOCK_FEEDBACK_ROWS,
      } as Response)
    }
    if (u.includes('/api/admin/insights/recommendations')) {
      return Promise.resolve({
        ok: true,
        json: async () => recs,
      } as Response)
    }
    return Promise.resolve({ ok: true, json: async () => ({}) } as Response)
  })
}

function makeSseStream(messages: { type: string; message: string }[]) {
  const encoder = new TextEncoder()
  return new ReadableStream({
    start(controller) {
      for (const msg of messages) {
        controller.enqueue(encoder.encode(`data: ${JSON.stringify(msg)}\n\n`))
      }
      controller.close()
    },
  })
}

afterEach(() => {
  vi.restoreAllMocks()
})

// ── Section A: Stats cards ────────────────────────────────────────────────────

describe('InsightsDashboard — stats cards', () => {
  it('renders Total Feedback card', async () => {
    mockInitialLoad()
    render(<InsightsDashboard />)
    await waitFor(() => expect(screen.getByText('Total Feedback')).toBeInTheDocument())
  })

  it('renders Positive stat card', async () => {
    mockInitialLoad()
    render(<InsightsDashboard />)
    await waitFor(() => expect(screen.getByText('👍 Positive')).toBeInTheDocument())
  })

  it('renders Negative stat card', async () => {
    mockInitialLoad()
    render(<InsightsDashboard />)
    await waitFor(() => expect(screen.getByText('👎 Negative')).toBeInTheDocument())
  })

  it('renders Negative Rate stat card', async () => {
    mockInitialLoad()
    render(<InsightsDashboard />)
    await waitFor(() => expect(screen.getByText('Negative Rate')).toBeInTheDocument())
  })

  it('shows actual stat values from API', async () => {
    mockInitialLoad()
    render(<InsightsDashboard />)
    await waitFor(() => {
      expect(screen.getByText('12')).toBeInTheDocument()  // total
      expect(screen.getByText('8')).toBeInTheDocument()   // positive
      expect(screen.getByText('4')).toBeInTheDocument()   // negative
    })
  })
})

// ── Section B: Feedback detail table ─────────────────────────────────────────

describe('InsightsDashboard — feedback detail table', () => {
  it('renders column headers', async () => {
    mockInitialLoad()
    render(<InsightsDashboard />)
    await waitFor(() => {
      expect(screen.getByText('Rating')).toBeInTheDocument()
      expect(screen.getByText('Filename')).toBeInTheDocument()
      expect(screen.getByText('Decision')).toBeInTheDocument()
      expect(screen.getByText('Comment')).toBeInTheDocument()
      expect(screen.getByText('Date')).toBeInTheDocument()
    })
  })

  it('renders feedback rows with filename', async () => {
    mockInitialLoad()
    render(<InsightsDashboard />)
    await waitFor(() => {
      expect(screen.getByText('contract.pdf')).toBeInTheDocument()
      expect(screen.getByText('nda_signed.pdf')).toBeInTheDocument()
    })
  })

  it('renders negative emoji for negative feedback', async () => {
    mockInitialLoad()
    render(<InsightsDashboard />)
    await waitFor(() => {
      const cells = screen.getAllByText('👎')
      expect(cells.length).toBeGreaterThanOrEqual(1)
    })
  })

  it('renders positive emoji for positive feedback', async () => {
    mockInitialLoad()
    render(<InsightsDashboard />)
    await waitFor(() => {
      const cells = screen.getAllByText('👍')
      expect(cells.length).toBeGreaterThanOrEqual(1)
    })
  })

  it('renders comment text in table', async () => {
    mockInitialLoad()
    render(<InsightsDashboard />)
    await waitFor(() => {
      expect(screen.getByText('wrong clause detected')).toBeInTheDocument()
    })
  })

  it('shows empty state when no feedback rows', async () => {
    vi.spyOn(global, 'fetch').mockImplementation((url) => {
      const u = url.toString()
      if (u.includes('/api/metrics/summary'))
        return Promise.resolve({ ok: true, json: async () => ({ feedback: { total: 0, positive: 0, negative: 0, negative_rate_pct: 0 } }) } as Response)
      if (u.includes('/api/feedback/summary'))
        return Promise.resolve({ ok: true, json: async () => [] } as Response)
      if (u.includes('/api/admin/insights/recommendations'))
        return Promise.resolve({ ok: true, json: async () => [] } as Response)
      return Promise.resolve({ ok: true, json: async () => ({}) } as Response)
    })
    render(<InsightsDashboard />)
    await waitFor(() =>
      expect(screen.getByText(/no feedback yet/i)).toBeInTheDocument()
    )
  })
})

// ── Section C: Run Review Agent ───────────────────────────────────────────────

describe('InsightsDashboard — run review agent', () => {
  it('renders Run Review Agent button with aria-label', async () => {
    mockInitialLoad()
    render(<InsightsDashboard />)
    await waitFor(() =>
      expect(screen.getByRole('button', { name: /run review agent/i })).toBeInTheDocument()
    )
  })

  it('renders min evidence select with aria-label', async () => {
    mockInitialLoad()
    render(<InsightsDashboard />)
    await waitFor(() =>
      expect(screen.getByRole('combobox', { name: /minimum evidence threshold/i })).toBeInTheDocument()
    )
  })

  it('SSE log list is not shown before running', async () => {
    mockInitialLoad()
    render(<InsightsDashboard />)
    await waitFor(() => screen.getByRole('button', { name: /run review agent/i }))
    expect(screen.queryByRole('list', { name: /review agent log/i })).not.toBeInTheDocument()
  })

  it('displays SSE log messages after clicking run', async () => {
    const fetchMock = mockInitialLoad()
    render(<InsightsDashboard />)
    await waitFor(() => screen.getByRole('button', { name: /run review agent/i }))

    // Override fetch for the SSE run-review call
    fetchMock.mockImplementationOnce(() =>
      Promise.resolve({
        ok: true,
        body: makeSseStream([
          { type: 'progress', message: 'Checking NDA…' },
          { type: 'done', message: 'Review complete.' },
        ]),
      } as unknown as Response)
    )

    fireEvent.click(screen.getByRole('button', { name: /run review agent/i }))

    await waitFor(() =>
      expect(screen.getByRole('list', { name: /review agent log/i })).toBeInTheDocument()
    )
    await waitFor(() => {
      expect(screen.getByText('Checking NDA…')).toBeInTheDocument()
      expect(screen.getByText('Review complete.')).toBeInTheDocument()
    })
  })

  it('shows error log when fetch fails', async () => {
    const fetchMock = mockInitialLoad()
    render(<InsightsDashboard />)
    await waitFor(() => screen.getByRole('button', { name: /run review agent/i }))

    fetchMock.mockImplementationOnce(() =>
      Promise.resolve({ ok: false, body: null } as unknown as Response)
    )

    fireEvent.click(screen.getByRole('button', { name: /run review agent/i }))

    await waitFor(() =>
      expect(screen.getByRole('list', { name: /review agent log/i })).toBeInTheDocument()
    )
    await waitFor(() =>
      expect(screen.getByText(/error starting review agent/i)).toBeInTheDocument()
    )
  })
})

// ── Section D: Pending recommendations ───────────────────────────────────────

describe('InsightsDashboard — pending recommendations', () => {
  it('shows Pending Recommendations section heading with count', async () => {
    mockInitialLoad([PENDING_REC])
    render(<InsightsDashboard />)
    await waitFor(() =>
      expect(screen.getByText(/Pending Recommendations \(1\)/i)).toBeInTheDocument()
    )
  })

  it('renders proposed value of pending recommendation', async () => {
    mockInitialLoad([PENDING_REC])
    render(<InsightsDashboard />)
    await waitFor(() =>
      expect(screen.getByText('indemnity clause')).toBeInTheDocument()
    )
  })

  it('renders rationale of pending recommendation', async () => {
    mockInitialLoad([PENDING_REC])
    render(<InsightsDashboard />)
    await waitFor(() =>
      expect(screen.getByText(/3 users flagged a missing indemnity clause/i)).toBeInTheDocument()
    )
  })

  it('shows empty state when no pending recommendations', async () => {
    mockInitialLoad([])
    render(<InsightsDashboard />)
    await waitFor(() =>
      expect(screen.getByText(/no pending recommendations/i)).toBeInTheDocument()
    )
  })
})

// ── Section D: Approve / Reject / Undo buttons ───────────────────────────────

describe('InsightsDashboard — approve button', () => {
  it('Approve button is visible for pending recommendation', async () => {
    mockInitialLoad([PENDING_REC])
    render(<InsightsDashboard />)
    await waitFor(() =>
      expect(screen.getByRole('button', { name: /approve/i })).toBeInTheDocument()
    )
  })

  it('clicking Approve calls POST /api/admin/insights/{rec_id}/approve', async () => {
    const fetchMock = mockInitialLoad([PENDING_REC])
    render(<InsightsDashboard />)
    await waitFor(() => screen.getByRole('button', { name: /approve/i }))

    fetchMock.mockImplementationOnce(() =>
      Promise.resolve({
        ok: true,
        json: async () => ({ status: 'approved', rec_id: 'rec-pending' }),
      } as Response)
    )

    fireEvent.click(screen.getByRole('button', { name: /approve/i }))

    await waitFor(() =>
      expect(fetchMock).toHaveBeenCalledWith(
        expect.stringContaining('/api/admin/insights/rec-pending/approve'),
        expect.objectContaining({ method: 'POST' })
      )
    )
  })

  it('shows success message after approve', async () => {
    const fetchMock = mockInitialLoad([PENDING_REC])
    render(<InsightsDashboard />)
    await waitFor(() => screen.getByRole('button', { name: /approve/i }))

    fetchMock.mockImplementationOnce(() =>
      Promise.resolve({
        ok: true,
        json: async () => ({ status: 'approved', action: 'approved', rec_id: 'rec-pending' }),
      } as Response)
    )

    fireEvent.click(screen.getByRole('button', { name: /approve/i }))

    await waitFor(() =>
      expect(screen.getByText(/clause added to regulatory_db/i)).toBeInTheDocument()
    )
  })
})

describe('InsightsDashboard — reject button', () => {
  it('Reject button is visible for pending recommendation', async () => {
    mockInitialLoad([PENDING_REC])
    render(<InsightsDashboard />)
    await waitFor(() =>
      expect(screen.getByRole('button', { name: /reject/i })).toBeInTheDocument()
    )
  })

  it('clicking Reject calls POST /api/admin/insights/{rec_id}/reject', async () => {
    const fetchMock = mockInitialLoad([PENDING_REC])
    render(<InsightsDashboard />)
    await waitFor(() => screen.getByRole('button', { name: /reject/i }))

    fetchMock.mockImplementationOnce(() =>
      Promise.resolve({
        ok: true,
        json: async () => ({ status: 'rejected', rec_id: 'rec-pending' }),
      } as Response)
    )

    fireEvent.click(screen.getByRole('button', { name: /reject/i }))

    await waitFor(() =>
      expect(fetchMock).toHaveBeenCalledWith(
        expect.stringContaining('/api/admin/insights/rec-pending/reject'),
        expect.objectContaining({ method: 'POST' })
      )
    )
  })

  it('shows rejection message after reject', async () => {
    const fetchMock = mockInitialLoad([PENDING_REC])
    render(<InsightsDashboard />)
    await waitFor(() => screen.getByRole('button', { name: /reject/i }))

    fetchMock.mockImplementationOnce(() =>
      Promise.resolve({
        ok: true,
        json: async () => ({ status: 'rejected', action: 'rejected', rec_id: 'rec-pending' }),
      } as Response)
    )

    fireEvent.click(screen.getByRole('button', { name: /reject/i }))

    await waitFor(() =>
      expect(screen.getByText(/rejected.*won't be suggested again/i)).toBeInTheDocument()
    )
  })
})

describe('InsightsDashboard — undo button', () => {
  it('Undo button is visible for approved recommendation', async () => {
    mockInitialLoad([APPROVED_REC])
    render(<InsightsDashboard />)
    await waitFor(() =>
      expect(screen.getByRole('button', { name: /undo/i })).toBeInTheDocument()
    )
  })

  it('Undo button is visible for rejected recommendation', async () => {
    mockInitialLoad([REJECTED_REC])
    render(<InsightsDashboard />)
    await waitFor(() =>
      expect(screen.getByRole('button', { name: /undo/i })).toBeInTheDocument()
    )
  })

  it('Undo button is NOT shown for pending recommendation', async () => {
    mockInitialLoad([PENDING_REC])
    render(<InsightsDashboard />)
    await waitFor(() => screen.getByRole('button', { name: /approve/i })) // wait for render
    expect(screen.queryByRole('button', { name: /undo/i })).not.toBeInTheDocument()
  })

  it('Undo button is NOT shown for undone recommendation', async () => {
    mockInitialLoad([UNDONE_REC])
    render(<InsightsDashboard />)
    // Undone recs render as a simple faded span, no buttons
    await waitFor(() =>
      expect(screen.getByText(/pending recommendations \(0\)/i)).toBeInTheDocument()
    )
    expect(screen.queryByRole('button', { name: /undo/i })).not.toBeInTheDocument()
  })

  it('clicking Undo calls POST /api/admin/insights/{rec_id}/undo', async () => {
    const fetchMock = mockInitialLoad([APPROVED_REC])
    render(<InsightsDashboard />)
    await waitFor(() => screen.getByRole('button', { name: /undo/i }))

    fetchMock.mockImplementationOnce(() =>
      Promise.resolve({
        ok: true,
        json: async () => ({ status: 'undone', rec_id: 'rec-approved' }),
      } as Response)
    )

    fireEvent.click(screen.getByRole('button', { name: /undo/i }))

    await waitFor(() =>
      expect(fetchMock).toHaveBeenCalledWith(
        expect.stringContaining('/api/admin/insights/rec-approved/undo'),
        expect.objectContaining({ method: 'POST' })
      )
    )
  })

  it('shows undo success message after undo', async () => {
    const fetchMock = mockInitialLoad([APPROVED_REC])
    render(<InsightsDashboard />)
    await waitFor(() => screen.getByRole('button', { name: /undo/i }))

    fetchMock.mockImplementationOnce(() =>
      Promise.resolve({
        ok: true,
        json: async () => ({ status: 'undone', action: 'undone', rec_id: 'rec-approved' }),
      } as Response)
    )

    fireEvent.click(screen.getByRole('button', { name: /undo/i }))

    await waitFor(() =>
      expect(screen.getByText(/clause removed from regulatory_db/i)).toBeInTheDocument()
    )
  })

  it('undo on rejected rec shows re-opened message when action is reopened', async () => {
    const fetchMock = mockInitialLoad([REJECTED_REC])
    render(<InsightsDashboard />)
    await waitFor(() => screen.getByRole('button', { name: /undo/i }))

    fetchMock.mockImplementationOnce(() =>
      Promise.resolve({
        ok: true,
        json: async () => ({ status: 'pending', action: 'reopened', rec_id: 'rec-rejected' }),
      } as Response)
    )

    fireEvent.click(screen.getByRole('button', { name: /undo/i }))

    await waitFor(() =>
      expect(screen.getByText(/re-opened.*moved back to pending/i)).toBeInTheDocument()
    )
  })
})

// ── Approved / Rejected / Undone sections ────────────────────────────────────

describe('InsightsDashboard — resolved recommendations sections', () => {
  it('renders Approved section heading when approved recs exist', async () => {
    mockInitialLoad([APPROVED_REC])
    render(<InsightsDashboard />)
    await waitFor(() =>
      expect(screen.getByText(/Approved \(1\)/i)).toBeInTheDocument()
    )
  })

  it('renders Rejected section heading when rejected recs exist', async () => {
    mockInitialLoad([REJECTED_REC])
    render(<InsightsDashboard />)
    await waitFor(() =>
      expect(screen.getByText(/Rejected \(1\)/i)).toBeInTheDocument()
    )
  })

  it('renders Undone section heading when undone recs exist', async () => {
    mockInitialLoad([UNDONE_REC])
    render(<InsightsDashboard />)
    await waitFor(() =>
      expect(screen.getByText(/Undone \(1\)/i)).toBeInTheDocument()
    )
  })

  it('does not render Approved section when none exist', async () => {
    mockInitialLoad([PENDING_REC])
    render(<InsightsDashboard />)
    await waitFor(() => screen.getByText(/Pending Recommendations \(1\)/i))
    expect(screen.queryByText(/Approved \(\d+\)/i)).not.toBeInTheDocument()
  })
})
