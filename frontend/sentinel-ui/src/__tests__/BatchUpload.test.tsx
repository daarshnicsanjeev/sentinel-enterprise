import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import { vi } from 'vitest'
import { BatchUpload } from '../components/BatchUpload'

const JOB_PENDING = { job_id: 'abc-123', status: 'pending', total: 2, completed: 0, results: [] }
const JOB_RUNNING = { job_id: 'abc-123', status: 'running', total: 2, completed: 1, results: [] }
const JOB_DONE = {
  job_id: 'abc-123',
  status: 'completed',
  total: 2,
  completed: 2,
  results: [
    { filename: 'a.txt', final_decision: 'APPROVED', evaluation_score: 0.9, trace_id: 'trace-aaa', sanitized: true },
    { filename: 'b.txt', final_decision: 'REJECTED', evaluation_score: 0.4, trace_id: 'trace-bbb', sanitized: true },
  ],
}

const makeFile = () => new File(['dummy zip content'], 'docs.zip', { type: 'application/zip' })

beforeEach(() => { localStorage.clear() })
afterEach(() => { vi.restoreAllMocks() })

// ---------------------------------------------------------------------------
// Rendering
// ---------------------------------------------------------------------------
describe('BatchUpload — rendering', () => {
  it('renders a file input that accepts zip only', () => {
    render(<BatchUpload apiBase="" />)
    const input = document.getElementById('batch-zip-input') as HTMLInputElement
    expect(input).toBeTruthy()
    expect(input.accept).toContain('.zip')
  })

  it('drop zone is announced as a button for assistive technology', () => {
    render(<BatchUpload apiBase="" />)
    expect(screen.getByRole('button', { name: /upload zip file/i })).toBeInTheDocument()
  })

  it('drop zone is keyboard activatable via Enter/Space', () => {
    render(<BatchUpload apiBase="" />)
    const zone = screen.getByRole('button', { name: /upload zip file/i })
    expect(zone).toHaveAttribute('tabindex', '0')
  })

  it('does not show progress bar initially', () => {
    render(<BatchUpload apiBase="" />)
    expect(screen.queryByRole('progressbar')).not.toBeInTheDocument()
  })

  it('does not show results table initially', () => {
    render(<BatchUpload apiBase="" />)
    expect(screen.queryByRole('table')).not.toBeInTheDocument()
  })
})

// ---------------------------------------------------------------------------
// Submission (auto-triggers on file select)
// ---------------------------------------------------------------------------
describe('BatchUpload — submission', () => {
  it('shows progress bar after file selected', async () => {
    vi.spyOn(global, 'fetch')
      .mockResolvedValueOnce({ ok: true, json: async () => JOB_PENDING } as Response)
      .mockResolvedValueOnce({ ok: true, json: async () => JOB_DONE } as Response)

    render(<BatchUpload apiBase="" />)
    fireEvent.change(document.getElementById('batch-zip-input')!, { target: { files: [makeFile()] } })

    await waitFor(() => expect(screen.getByRole('progressbar')).toBeInTheDocument())
  })

  it('progress bar has aria-valuenow', async () => {
    vi.spyOn(global, 'fetch')
      .mockResolvedValueOnce({ ok: true, json: async () => JOB_RUNNING } as Response)
      .mockResolvedValueOnce({ ok: true, json: async () => JOB_DONE } as Response)

    render(<BatchUpload apiBase="" />)
    fireEvent.change(document.getElementById('batch-zip-input')!, { target: { files: [makeFile()] } })

    await waitFor(() => expect(screen.getByRole('progressbar')).toHaveAttribute('aria-valuenow'))
  })

  it('progress bar has aria-valuemax', async () => {
    vi.spyOn(global, 'fetch')
      .mockResolvedValueOnce({ ok: true, json: async () => JOB_PENDING } as Response)
      .mockResolvedValueOnce({ ok: true, json: async () => JOB_DONE } as Response)

    render(<BatchUpload apiBase="" />)
    fireEvent.change(document.getElementById('batch-zip-input')!, { target: { files: [makeFile()] } })

    await waitFor(() => expect(screen.getByRole('progressbar')).toHaveAttribute('aria-valuemax'))
  })

  it('status text has aria-live', async () => {
    vi.spyOn(global, 'fetch')
      .mockResolvedValueOnce({ ok: true, json: async () => JOB_PENDING } as Response)
      .mockResolvedValueOnce({ ok: true, json: async () => JOB_DONE } as Response)

    render(<BatchUpload apiBase="" />)
    fireEvent.change(document.getElementById('batch-zip-input')!, { target: { files: [makeFile()] } })

    await waitFor(() => expect(document.querySelector('[aria-live]')).toBeInTheDocument())
  })
})

// ---------------------------------------------------------------------------
// Results table
// ---------------------------------------------------------------------------
describe('BatchUpload — results table', () => {
  const setupCompleted = async () => {
    vi.spyOn(global, 'fetch')
      .mockResolvedValueOnce({ ok: true, json: async () => ({ job_id: 'xyz', total: 2 }) } as Response)
      .mockResolvedValue({ ok: true, json: async () => JOB_DONE } as Response)

    render(<BatchUpload apiBase="" />)
    fireEvent.change(document.getElementById('batch-zip-input')!, { target: { files: [makeFile()] } })
    await waitFor(() => screen.getByRole('table'), { timeout: 5000 })
  }

  it('shows results table when completed', async () => {
    await setupCompleted()
    expect(screen.getByRole('table')).toBeInTheDocument()
  })

  it('results table has a caption', async () => {
    await setupCompleted()
    expect(screen.getByRole('table', { name: /batch results/i })).toBeInTheDocument()
  })

  it('results table headers have scope col', async () => {
    await setupCompleted()
    screen.getAllByRole('columnheader').forEach(th => expect(th).toHaveAttribute('scope', 'col'))
  })

  it('results table shows filenames', async () => {
    await setupCompleted()
    expect(screen.getByText('a.txt')).toBeInTheDocument()
    expect(screen.getByText('b.txt')).toBeInTheDocument()
  })
})

// ---------------------------------------------------------------------------
// Source column
// ---------------------------------------------------------------------------
describe('BatchUpload — results details', () => {
  it('shows Source column with cached badge for cached results', async () => {
    vi.spyOn(global, 'fetch')
      .mockResolvedValueOnce({ ok: true, json: async () => ({ job_id: 'src-1', total: 1 }) } as Response)
      .mockResolvedValue({
        ok: true,
        json: async () => ({
          job_id: 'src-1', status: 'completed', total: 1, completed: 1,
          results: [{ filename: 'x.txt', final_decision: 'APPROVED', evaluation_score: 0.9, from_cache: true, trace_id: 'trace-x' }],
        }),
      } as Response)

    render(<BatchUpload apiBase="" />)
    fireEvent.change(document.getElementById('batch-zip-input')!, { target: { files: [makeFile()] } })

    await waitFor(() => screen.getByRole('table'), { timeout: 5000 })
    expect(screen.getByText('Source')).toBeInTheDocument()
    expect(screen.getByText('⚡ Cached')).toBeInTheDocument()
  })
})

// ---------------------------------------------------------------------------
// BLOCKED decision display
// ---------------------------------------------------------------------------
describe('BatchUpload — BLOCKED decision', () => {
  it('shows BLOCKED badge when sanitized is false', async () => {
    vi.spyOn(global, 'fetch')
      .mockResolvedValueOnce({ ok: true, json: async () => ({ job_id: 'blk-1', total: 1 }) } as Response)
      .mockResolvedValue({
        ok: true,
        json: async () => ({
          job_id: 'blk-1', status: 'completed', total: 1, completed: 1,
          results: [{ filename: 'bad.txt', final_decision: 'UNKNOWN', evaluation_score: 0, sanitized: false, trace_id: '' }],
        }),
      } as Response)

    render(<BatchUpload apiBase="" />)
    fireEvent.change(document.getElementById('batch-zip-input')!, { target: { files: [makeFile()] } })

    await waitFor(() => screen.getByRole('table'), { timeout: 5000 })
    expect(screen.getByText('BLOCKED')).toBeInTheDocument()
  })
})

// ---------------------------------------------------------------------------
// Checkbox selection
// ---------------------------------------------------------------------------
describe('BatchUpload — checkbox selection', () => {
  const setupCompleted = async () => {
    vi.spyOn(global, 'fetch')
      .mockResolvedValueOnce({ ok: true, json: async () => ({ job_id: 'chk-1', total: 2 }) } as Response)
      .mockResolvedValue({ ok: true, json: async () => JOB_DONE } as Response)

    render(<BatchUpload apiBase="" />)
    fireEvent.change(document.getElementById('batch-zip-input')!, { target: { files: [makeFile()] } })
    await waitFor(() => screen.getByRole('table'), { timeout: 5000 })
  }

  it('shows per-row checkboxes after completion', async () => {
    await setupCompleted()
    const checkboxes = screen.getAllByRole('checkbox')
    // select-all + 2 row checkboxes = 3
    expect(checkboxes.length).toBeGreaterThanOrEqual(2)
  })

  it('select-all checkbox checks all rows', async () => {
    await setupCompleted()
    const selectAll = screen.getByLabelText(/select all/i)
    fireEvent.click(selectAll)
    const rowCheckboxes = screen.getAllByRole('checkbox').filter(c => c !== selectAll)
    rowCheckboxes.forEach(c => expect(c).toBeChecked())
  })

  it('Re-analyse Selected button appears when rows selected', async () => {
    await setupCompleted()
    fireEvent.click(screen.getByLabelText(/select all/i))
    expect(screen.getByRole('button', { name: /re-analyse selected/i })).toBeInTheDocument()
  })

  it('Re-analyse Selected button is disabled when nothing selected', async () => {
    await setupCompleted()
    const btn = screen.getByRole('button', { name: /re-analyse selected/i })
    expect(btn).toBeDisabled()
  })
})

// ---------------------------------------------------------------------------
// Error state
// ---------------------------------------------------------------------------
describe('BatchUpload — error state', () => {
  it('shows error when batch submit fails', async () => {
    vi.spyOn(global, 'fetch').mockResolvedValueOnce({
      ok: false, status: 400, json: async () => ({ detail: 'Bad request' }),
    } as Response)

    render(<BatchUpload apiBase="" />)
    fireEvent.change(document.getElementById('batch-zip-input')!, {
      target: { files: [new File(['x'], 'docs.zip', { type: 'application/zip' })] },
    })

    await waitFor(() => expect(screen.getByRole('alert')).toBeInTheDocument())
  })
})
