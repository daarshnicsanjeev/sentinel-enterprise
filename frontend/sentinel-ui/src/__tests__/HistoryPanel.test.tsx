/**
 * TDD spec for HistoryPanel component (C1 persistence).
 *
 * Contract: renders a table of past analysis records fetched from /api/history,
 * handles loading and empty states gracefully.
 */
import { render, screen, waitFor } from '@testing-library/react'
import { HistoryPanel } from '../components/HistoryPanel'

const MOCK_RECORDS = [
  {
    trace_id: 'abc-123',
    filename: 'contract.txt',
    doc_type: 'LEGAL_CONTRACT',
    decision: 'APPROVED',
    faithfulness: 0.92,
    risk: 'low',
    created_at: '2026-05-16T10:00:00Z',
    feedback_rating: 'positive',
  },
  {
    trace_id: 'def-456',
    filename: 'filing.pdf',
    doc_type: 'REGULATORY_FILING',
    decision: 'REJECTED',
    faithfulness: 0.45,
    risk: 'high',
    created_at: '2026-05-16T11:00:00Z',
    feedback_rating: 'negative',
  },
  {
    trace_id: 'ghi-789',
    filename: 'other.txt',
    doc_type: 'NDA',
    decision: 'ESCALATE',
    faithfulness: 0.7,
    risk: 'medium',
    created_at: '2026-05-16T12:00:00Z',
    feedback_rating: null,
  },
]

describe('HistoryPanel', () => {
  beforeEach(() => {
    vi.stubGlobal('fetch', vi.fn())
  })

  afterEach(() => {
    vi.unstubAllGlobals()
  })

  it('renders a heading', () => {
    vi.mocked(fetch).mockResolvedValue({
      ok: true,
      json: async () => [],
    } as unknown as Response)
    render(<HistoryPanel />)
    expect(screen.getByRole('heading', { name: /history/i })).toBeInTheDocument()
  })

  it('shows column headers', async () => {
    vi.mocked(fetch).mockResolvedValue({
      ok: true,
      json: async () => [],
    } as unknown as Response)
    render(<HistoryPanel />)
    await waitFor(() => {
      expect(screen.getByText(/filename/i)).toBeInTheDocument()
      expect(screen.getByText(/decision/i)).toBeInTheDocument()
      expect(screen.getByText(/doc type/i)).toBeInTheDocument()
    })
  })

  it('renders one row per record', async () => {
    vi.mocked(fetch).mockResolvedValue({
      ok: true,
      json: async () => MOCK_RECORDS,
    } as unknown as Response)
    render(<HistoryPanel />)
    await waitFor(() => {
      expect(screen.getByText('contract.txt')).toBeInTheDocument()
      expect(screen.getByText('filing.pdf')).toBeInTheDocument()
    })
  })

  it('shows empty state when no records', async () => {
    vi.mocked(fetch).mockResolvedValue({
      ok: true,
      json: async () => [],
    } as unknown as Response)
    render(<HistoryPanel />)
    await waitFor(() => {
      expect(screen.getByText(/no analyses/i)).toBeInTheDocument()
    })
  })

  it('calls the /api/history endpoint', async () => {
    const mockFetch = vi.mocked(fetch)
    mockFetch.mockResolvedValue({
      ok: true,
      json: async () => [],
    } as unknown as Response)
    render(<HistoryPanel />)
    await waitFor(() => {
      expect(mockFetch).toHaveBeenCalledWith(
        expect.stringContaining('/api/history'),
        expect.anything()
      )
    })
  })

  it('displays the decision for each record', async () => {
    vi.mocked(fetch).mockResolvedValue({
      ok: true,
      json: async () => MOCK_RECORDS,
    } as unknown as Response)
    render(<HistoryPanel />)
    await waitFor(() => {
      expect(screen.getByText('APPROVED')).toBeInTheDocument()
      expect(screen.getByText('REJECTED')).toBeInTheDocument()
    })
  })

  it('shows an error message when fetch throws a network error', async () => {
    vi.mocked(fetch).mockRejectedValue(new Error('Network failure'))
    render(<HistoryPanel />)
    await waitFor(() => {
      expect(screen.getByRole('alert')).toBeInTheDocument()
    })
  })

  it('shows an error message when server returns HTTP 500', async () => {
    vi.mocked(fetch).mockResolvedValue({
      ok: false,
      status: 500,
      json: async () => ({}),
    } as unknown as Response)
    render(<HistoryPanel />)
    await waitFor(() => {
      expect(screen.getByRole('alert')).toBeInTheDocument()
    })
  })

  it('shows empty state when server returns non-array JSON', async () => {
    vi.mocked(fetch).mockResolvedValue({
      ok: true,
      json: async () => ({ unexpected: 'object' }),
    } as unknown as Response)
    render(<HistoryPanel />)
    await waitFor(() => {
      expect(screen.getByText(/no analyses/i)).toBeInTheDocument()
    })
  })

  it('renders a Report column header', async () => {
    vi.mocked(fetch).mockResolvedValue({
      ok: true,
      json: async () => [],
    } as unknown as Response)
    render(<HistoryPanel />)
    await waitFor(() => {
      expect(screen.getByText(/report/i)).toBeInTheDocument()
    })
  })

  it('renders a PDF download button for each record', async () => {
    vi.mocked(fetch).mockResolvedValue({
      ok: true,
      json: async () => MOCK_RECORDS,
    } as unknown as Response)
    render(<HistoryPanel />)
    await waitFor(() => {
      const buttons = screen.getAllByRole('button', { name: /pdf/i })
      expect(buttons).toHaveLength(MOCK_RECORDS.length)
    })
  })

  it('renders a Feedback column header', async () => {
    vi.mocked(fetch).mockResolvedValue({
      ok: true,
      json: async () => [],
    } as unknown as Response)
    render(<HistoryPanel />)
    await waitFor(() => {
      expect(screen.getByText(/feedback/i)).toBeInTheDocument()
    })
  })

  it('shows thumbs-up emoji for positive feedback_rating', async () => {
    vi.mocked(fetch).mockResolvedValue({
      ok: true,
      json: async () => MOCK_RECORDS,
    } as unknown as Response)
    render(<HistoryPanel />)
    await waitFor(() => {
      expect(screen.getByText('👍')).toBeInTheDocument()
    })
  })

  it('shows thumbs-down emoji for negative feedback_rating', async () => {
    vi.mocked(fetch).mockResolvedValue({
      ok: true,
      json: async () => MOCK_RECORDS,
    } as unknown as Response)
    render(<HistoryPanel />)
    await waitFor(() => {
      expect(screen.getByText('👎')).toBeInTheDocument()
    })
  })

  it('shows dash for null feedback_rating', async () => {
    vi.mocked(fetch).mockResolvedValue({
      ok: true,
      json: async () => MOCK_RECORDS,
    } as unknown as Response)
    render(<HistoryPanel />)
    await waitFor(() => {
      // The record with feedback_rating: null should render a dash
      const cells = screen.getAllByRole('cell')
      const dashCells = cells.filter(c => c.textContent === '—')
      expect(dashCells.length).toBeGreaterThan(0)
    })
  })

  it('PDF button has a descriptive title attribute', async () => {
    vi.mocked(fetch).mockResolvedValue({
      ok: true,
      json: async () => [MOCK_RECORDS[0]],
    } as unknown as Response)
    render(<HistoryPanel />)
    await waitFor(() => {
      const btn = screen.getByRole('button', { name: /pdf/i })
      expect(btn).toHaveAttribute('title')
    })
  })
})
