/**
 * TDD spec for SourceViewer — the "View Source" trust feature.
 * The user must be able to open the original document text and see the
 * agent's cited evidence highlighted inside it.
 */
import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import { vi } from 'vitest'
import { SourceViewer, buildSegments } from '../components/SourceViewer'

const TRACE = 'ab5e713b-e298-4efa-84f8-44cdca93bc0b'
const RAW = 'PREAMBLE. In the event of force majeure neither party is liable. END.'

function mockFetchOk() {
  return vi.fn().mockResolvedValue({
    ok: true,
    status: 200,
    json: async () => ({ trace_id: TRACE, filename: 'contract.pdf', raw_text: RAW }),
  })
}

describe('SourceViewer', () => {
  afterEach(() => vi.restoreAllMocks())

  it('renders a View Source button', () => {
    render(<SourceViewer traceId={TRACE} apiBase="" />)
    expect(screen.getByRole('button', { name: /view source/i })).toBeInTheDocument()
  })

  it('opens an accessible dialog and fetches the source on click', async () => {
    const fetchMock = mockFetchOk()
    vi.stubGlobal('fetch', fetchMock)
    render(<SourceViewer traceId={TRACE} apiBase="" />)
    fireEvent.click(screen.getByRole('button', { name: /view source/i }))
    expect(screen.getByRole('dialog')).toBeInTheDocument()
    await waitFor(() =>
      expect(fetchMock).toHaveBeenCalledWith(`/api/history/${TRACE}/source`),
    )
  })

  it('shows the document text inside the dialog', async () => {
    vi.stubGlobal('fetch', mockFetchOk())
    render(<SourceViewer traceId={TRACE} apiBase="" />)
    fireEvent.click(screen.getByRole('button', { name: /view source/i }))
    await waitFor(() => expect(screen.getByText(/PREAMBLE/)).toBeInTheDocument())
  })

  it('shows the filename in the dialog title', async () => {
    vi.stubGlobal('fetch', mockFetchOk())
    render(<SourceViewer traceId={TRACE} apiBase="" />)
    fireEvent.click(screen.getByRole('button', { name: /view source/i }))
    await waitFor(() => expect(screen.getByText(/contract\.pdf/)).toBeInTheDocument())
  })

  it('highlights cited evidence within the source text', async () => {
    vi.stubGlobal('fetch', mockFetchOk())
    render(
      <SourceViewer
        traceId={TRACE}
        apiBase=""
        highlights={['force majeure neither party is liable']}
      />,
    )
    fireEvent.click(screen.getByRole('button', { name: /view source/i }))
    await waitFor(() => {
      const marked = document.querySelector('mark')
      expect(marked).not.toBeNull()
      expect(marked!.textContent).toMatch(/force majeure/)
    })
  })

  it('closes on Escape key', async () => {
    vi.stubGlobal('fetch', mockFetchOk())
    render(<SourceViewer traceId={TRACE} apiBase="" />)
    fireEvent.click(screen.getByRole('button', { name: /view source/i }))
    fireEvent.keyDown(document, { key: 'Escape' })
    await waitFor(() => expect(screen.queryByRole('dialog')).not.toBeInTheDocument())
  })

  it('shows a truncation notice when the stored text was cut', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue({
        ok: true,
        status: 200,
        json: async () => ({
          trace_id: TRACE,
          filename: 'huge.pdf',
          raw_text: RAW,
          truncated: true,
        }),
      }),
    )
    render(<SourceViewer traceId={TRACE} apiBase="" />)
    fireEvent.click(screen.getByRole('button', { name: /view source/i }))
    await waitFor(() => expect(screen.getByText(/truncated/i)).toBeInTheDocument())
  })

  it('shows no truncation notice for a complete document', async () => {
    vi.stubGlobal('fetch', mockFetchOk())
    render(<SourceViewer traceId={TRACE} apiBase="" />)
    fireEvent.click(screen.getByRole('button', { name: /view source/i }))
    await waitFor(() => expect(screen.getByText(/PREAMBLE/)).toBeInTheDocument())
    expect(screen.queryByText(/truncated/i)).not.toBeInTheDocument()
  })

  it('shows a friendly error when the source is unavailable', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue({ ok: false, status: 404, json: async () => ({}) }),
    )
    render(<SourceViewer traceId={TRACE} apiBase="" />)
    fireEvent.click(screen.getByRole('button', { name: /view source/i }))
    await waitFor(() =>
      expect(screen.getByRole('alert')).toHaveTextContent(/not available/i),
    )
  })
})

describe('buildSegments', () => {
  it('returns a single unmarked segment when there are no highlights', () => {
    expect(buildSegments('hello world', [])).toEqual([{ text: 'hello world', marked: false }])
  })

  it('marks an exact match', () => {
    const segs = buildSegments('aaa TARGET bbb', ['TARGET'])
    expect(segs.find((s) => s.marked)?.text).toBe('TARGET')
  })

  it('matches across whitespace differences', () => {
    const segs = buildSegments('one two\n  three four', ['two three'])
    expect(segs.some((s) => s.marked)).toBe(true)
  })

  it('merges overlapping highlight ranges', () => {
    const segs = buildSegments('alpha beta gamma', ['alpha beta', 'beta gamma'])
    expect(segs.filter((s) => s.marked)).toHaveLength(1)
    expect(segs.find((s) => s.marked)?.text).toBe('alpha beta gamma')
  })

  it('leaves text unmarked when the quote is not found', () => {
    const segs = buildSegments('document body', ['fabricated quote'])
    expect(segs.every((s) => !s.marked)).toBe(true)
  })
})
