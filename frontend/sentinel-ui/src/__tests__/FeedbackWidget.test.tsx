/**
 * TDD spec for FeedbackWidget component (Phase 9A).
 * RED first — tests fail until FeedbackWidget is created.
 */
import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import { vi } from 'vitest'
import { FeedbackWidget } from '../components/FeedbackWidget'

const mockFetch = (ok: boolean, status = 201) => {
  vi.spyOn(global, 'fetch').mockResolvedValueOnce({
    ok,
    status,
    json: async () => ({ status: 'recorded' }),
  } as Response)
}

afterEach(() => {
  vi.restoreAllMocks()
})

describe('FeedbackWidget — rendering', () => {
  it('renders thumbs-up button', () => {
    render(<FeedbackWidget traceId="test-trace" apiBase="" />)
    expect(screen.getByRole('button', { name: /mark analysis as helpful/i })).toBeInTheDocument()
  })

  it('renders thumbs-down button', () => {
    render(<FeedbackWidget traceId="test-trace" apiBase="" />)
    expect(screen.getByRole('button', { name: /mark analysis as unhelpful/i })).toBeInTheDocument()
  })

  it('renders a group with accessible label', () => {
    render(<FeedbackWidget traceId="test-trace" apiBase="" />)
    expect(screen.getByRole('group', { name: /rate this analysis/i })).toBeInTheDocument()
  })

  it('renders helpful prompt text', () => {
    render(<FeedbackWidget traceId="test-trace" apiBase="" />)
    expect(screen.getByText(/was this analysis helpful/i)).toBeInTheDocument()
  })
})

describe('FeedbackWidget — positive submission', () => {
  it('submits positive rating on thumbs-up click', async () => {
    mockFetch(true)
    render(<FeedbackWidget traceId="test-trace-pos" apiBase="" />)
    fireEvent.click(screen.getByRole('button', { name: /mark analysis as helpful/i }))
    expect(global.fetch).toHaveBeenCalledWith(
      '/api/feedback/test-trace-pos',
      expect.objectContaining({
        method: 'POST',
        body: expect.stringContaining('"positive"'),
      })
    )
  })

  it('shows confirmation message after positive submission', async () => {
    mockFetch(true)
    render(<FeedbackWidget traceId="test-trace" apiBase="" />)
    fireEvent.click(screen.getByRole('button', { name: /mark analysis as helpful/i }))
    await waitFor(() =>
      expect(screen.getByText(/thanks for the positive feedback/i)).toBeInTheDocument()
    )
  })

  it('confirmation has aria-live polite', async () => {
    mockFetch(true)
    render(<FeedbackWidget traceId="test-trace" apiBase="" />)
    fireEvent.click(screen.getByRole('button', { name: /mark analysis as helpful/i }))
    await waitFor(() => {
      const el = screen.getByText(/thanks for the positive feedback/i)
      expect(el).toHaveAttribute('aria-live', 'polite')
    })
  })
})

describe('FeedbackWidget — negative submission', () => {
  it('submits negative rating after comment step', async () => {
    mockFetch(true)
    render(<FeedbackWidget traceId="test-trace-neg" apiBase="" />)
    // Step 1: click 👎 → comment box appears
    fireEvent.click(screen.getByRole('button', { name: /mark analysis as unhelpful/i }))
    await waitFor(() => screen.getByRole('button', { name: /submit feedback/i }))
    // Step 2: submit → fetch called with negative rating
    fireEvent.click(screen.getByRole('button', { name: /submit feedback/i }))
    expect(global.fetch).toHaveBeenCalledWith(
      '/api/feedback/test-trace-neg',
      expect.objectContaining({
        method: 'POST',
        body: expect.stringContaining('"negative"'),
      })
    )
  })

  it('shows review confirmation after negative submission', async () => {
    mockFetch(true)
    render(<FeedbackWidget traceId="test-trace" apiBase="" />)
    fireEvent.click(screen.getByRole('button', { name: /mark analysis as unhelpful/i }))
    await waitFor(() => screen.getByRole('button', { name: /submit feedback/i }))
    fireEvent.click(screen.getByRole('button', { name: /submit feedback/i }))
    await waitFor(() =>
      expect(screen.getByText(/we'll review this result/i)).toBeInTheDocument()
    )
  })
})

describe('FeedbackWidget — error handling', () => {
  it('shows error when fetch fails (network error)', async () => {
    vi.spyOn(global, 'fetch').mockRejectedValueOnce(new Error('Network error'))
    render(<FeedbackWidget traceId="test-trace" apiBase="" />)
    fireEvent.click(screen.getByRole('button', { name: /mark analysis as helpful/i }))
    await waitFor(() =>
      expect(screen.getByRole('alert')).toBeInTheDocument()
    )
  })

  it('shows error when server returns non-ok', async () => {
    mockFetch(false, 500)
    render(<FeedbackWidget traceId="test-trace" apiBase="" />)
    fireEvent.click(screen.getByRole('button', { name: /mark analysis as helpful/i }))
    await waitFor(() =>
      expect(screen.getByRole('alert')).toBeInTheDocument()
    )
  })

  it('error element contains descriptive message', async () => {
    vi.spyOn(global, 'fetch').mockRejectedValueOnce(new Error('fail'))
    render(<FeedbackWidget traceId="test-trace" apiBase="" />)
    fireEvent.click(screen.getByRole('button', { name: /mark analysis as helpful/i }))
    await waitFor(() =>
      expect(screen.getByRole('alert')).toHaveTextContent(/could not submit feedback/i)
    )
  })
})

describe('FeedbackWidget — comment box after thumbs-down', () => {
  it('comment textarea appears after thumbs-down click', async () => {
    render(<FeedbackWidget traceId="test-trace" apiBase="" />)
    fireEvent.click(screen.getByRole('button', { name: /mark analysis as unhelpful/i }))
    await waitFor(() =>
      expect(screen.getByRole('textbox', { name: /what was wrong/i })).toBeInTheDocument()
    )
  })

  it('comment textarea does NOT appear after thumbs-up click', async () => {
    mockFetch(true)
    render(<FeedbackWidget traceId="test-trace" apiBase="" />)
    fireEvent.click(screen.getByRole('button', { name: /mark analysis as helpful/i }))
    await waitFor(() =>
      expect(screen.queryByRole('textbox')).not.toBeInTheDocument()
    )
  })

  it('submit button appears alongside comment box', async () => {
    render(<FeedbackWidget traceId="test-trace" apiBase="" />)
    fireEvent.click(screen.getByRole('button', { name: /mark analysis as unhelpful/i }))
    await waitFor(() =>
      expect(screen.getByRole('button', { name: /submit feedback/i })).toBeInTheDocument()
    )
  })

  it('submits negative rating with comment text', async () => {
    mockFetch(true)
    render(<FeedbackWidget traceId="trace-comment" apiBase="" />)
    fireEvent.click(screen.getByRole('button', { name: /mark analysis as unhelpful/i }))
    await waitFor(() => screen.getByRole('textbox'))
    fireEvent.change(screen.getByRole('textbox'), { target: { value: 'Wrong clause detected' } })
    fireEvent.click(screen.getByRole('button', { name: /submit feedback/i }))
    expect(global.fetch).toHaveBeenCalledWith(
      '/api/feedback/trace-comment',
      expect.objectContaining({
        body: expect.stringContaining('Wrong clause detected'),
      })
    )
  })

  it('can skip comment and still submit by leaving it blank', async () => {
    mockFetch(true)
    render(<FeedbackWidget traceId="trace-skip" apiBase="" />)
    fireEvent.click(screen.getByRole('button', { name: /mark analysis as unhelpful/i }))
    await waitFor(() => screen.getByRole('button', { name: /submit feedback/i }))
    fireEvent.click(screen.getByRole('button', { name: /submit feedback/i }))
    expect(global.fetch).toHaveBeenCalled()
  })

  it('shows confirmation after negative comment submitted', async () => {
    mockFetch(true)
    render(<FeedbackWidget traceId="test-trace" apiBase="" />)
    fireEvent.click(screen.getByRole('button', { name: /mark analysis as unhelpful/i }))
    await waitFor(() => screen.getByRole('button', { name: /submit feedback/i }))
    fireEvent.click(screen.getByRole('button', { name: /submit feedback/i }))
    await waitFor(() =>
      expect(screen.getByText(/we'll review this result/i)).toBeInTheDocument()
    )
  })
})

describe('FeedbackWidget — uses apiBase prop', () => {
  it('prepends apiBase to fetch URL', async () => {
    mockFetch(true)
    render(<FeedbackWidget traceId="abc-123" apiBase="https://api.example.com" />)
    fireEvent.click(screen.getByRole('button', { name: /mark analysis as helpful/i }))
    expect(global.fetch).toHaveBeenCalledWith(
      'https://api.example.com/api/feedback/abc-123',
      expect.anything()
    )
  })
})
