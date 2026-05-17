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
  },
  {
    trace_id: 'def-456',
    filename: 'filing.pdf',
    doc_type: 'REGULATORY_FILING',
    decision: 'REJECTED',
    faithfulness: 0.45,
    risk: 'high',
    created_at: '2026-05-16T11:00:00Z',
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
})
