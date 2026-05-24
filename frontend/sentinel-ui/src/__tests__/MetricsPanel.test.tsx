/**
 * TDD spec for MetricsPanel component (Phase 9B).
 * RED first — tests fail until MetricsPanel is created.
 */
import { render, screen, waitFor } from '@testing-library/react'
import { vi } from 'vitest'
import { MetricsPanel } from '../components/MetricsPanel'
import App from '../App'

const MOCK_METRICS = {
  total: 42,
  by_decision: { APPROVED: 30, REJECTED: 10, ESCALATE: 2 },
  avg_faithfulness: 0.87,
  risk_distribution: { low: 20, medium: 15, high: 7 },
  daily_last_7_days: { '2026-05-15': 3, '2026-05-16': 7, '2026-05-17': 5 },
}

const mockFetch = (data: object, ok = true) => {
  vi.spyOn(global, 'fetch').mockResolvedValueOnce({
    ok,
    status: ok ? 200 : 500,
    json: async () => data,
  } as Response)
}

afterEach(() => {
  vi.restoreAllMocks()
})

describe('MetricsPanel — loading state', () => {
  it('renders loading indicator while fetching', () => {
    vi.spyOn(global, 'fetch').mockReturnValue(new Promise(() => {}))
    render(<MetricsPanel apiBase="" />)
    expect(screen.getByText(/loading metrics/i)).toBeInTheDocument()
  })

  it('loading element has aria-busy true', () => {
    vi.spyOn(global, 'fetch').mockReturnValue(new Promise(() => {}))
    render(<MetricsPanel apiBase="" />)
    const el = screen.getByText(/loading metrics/i)
    expect(el).toHaveAttribute('aria-busy', 'true')
  })
})

describe('MetricsPanel — data display', () => {
  it('shows total analyses count after load', async () => {
    mockFetch(MOCK_METRICS)
    render(<MetricsPanel apiBase="" />)
    await waitFor(() => expect(screen.getByText('42')).toBeInTheDocument())
  })

  it('shows average faithfulness as percentage', async () => {
    mockFetch(MOCK_METRICS)
    render(<MetricsPanel apiBase="" />)
    await waitFor(() => expect(screen.getByText('87%')).toBeInTheDocument())
  })

  it('renders section with accessible label', async () => {
    mockFetch(MOCK_METRICS)
    render(<MetricsPanel apiBase="" />)
    await waitFor(() =>
      expect(screen.getByRole('region', { name: /system metrics/i })).toBeInTheDocument()
    )
  })
})

describe('MetricsPanel — accessible bar chart', () => {
  it('decision bars have role meter', async () => {
    mockFetch(MOCK_METRICS)
    render(<MetricsPanel apiBase="" />)
    await waitFor(() => {
      const meters = screen.getAllByRole('meter')
      expect(meters.length).toBeGreaterThan(0)
    })
  })

  it('decision bars have aria-valuenow', async () => {
    mockFetch(MOCK_METRICS)
    render(<MetricsPanel apiBase="" />)
    await waitFor(() => {
      const meters = screen.getAllByRole('meter')
      meters.forEach(m => expect(m).toHaveAttribute('aria-valuenow'))
    })
  })

  it('decision bars have aria-label', async () => {
    mockFetch(MOCK_METRICS)
    render(<MetricsPanel apiBase="" />)
    await waitFor(() => {
      const meters = screen.getAllByRole('meter')
      meters.forEach(m => expect(m).toHaveAttribute('aria-label'))
    })
  })

  it('sr-only table is present with caption', async () => {
    mockFetch(MOCK_METRICS)
    render(<MetricsPanel apiBase="" />)
    await waitFor(() => {
      expect(screen.getByRole('table', { name: /decision breakdown/i })).toBeInTheDocument()
    })
  })
})

describe('MetricsPanel — error state', () => {
  it('shows error on fetch failure', async () => {
    vi.spyOn(global, 'fetch').mockRejectedValueOnce(new Error('fail'))
    render(<MetricsPanel apiBase="" />)
    await waitFor(() =>
      expect(screen.getByRole('alert')).toBeInTheDocument()
    )
  })

  it('shows error when server returns non-ok', async () => {
    mockFetch({}, false)
    render(<MetricsPanel apiBase="" />)
    await waitFor(() =>
      expect(screen.getByRole('alert')).toBeInTheDocument()
    )
  })
})

describe('MetricsPanel — tab button in App', () => {
  it('renders a Metrics tab button in navigation', () => {
    render(<App />)
    expect(screen.getByRole('button', { name: /metrics/i })).toBeInTheDocument()
  })
})
