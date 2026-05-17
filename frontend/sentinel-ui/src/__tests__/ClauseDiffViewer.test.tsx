/**
 * TDD spec for ClauseDiffViewer component.
 */
import { render, screen } from '@testing-library/react'
import { ClauseDiffViewer } from '../components/ClauseDiffViewer'

const attempt1 = [
  { clause: 'force majeure', status: 'MISSING', evidence: '' },
  { clause: 'limitation of liability', status: 'PRESENT', evidence: 'liability text' },
]

const attempt2 = [
  { clause: 'force majeure', status: 'PRESENT', evidence: 'force majeure found' },
  { clause: 'limitation of liability', status: 'PRESENT', evidence: 'liability text' },
]

describe('ClauseDiffViewer', () => {
  it('renders nothing when history has fewer than 2 entries', () => {
    const { container } = render(<ClauseDiffViewer history={[attempt1]} />)
    expect(container.firstChild).toBeNull()
  })

  it('renders a diff table when history has 2 entries', () => {
    render(<ClauseDiffViewer history={[attempt1, attempt2]} />)
    expect(screen.getByRole('table')).toBeInTheDocument()
  })

  it('shows clause names in the table', () => {
    render(<ClauseDiffViewer history={[attempt1, attempt2]} />)
    expect(screen.getByText(/force majeure/i)).toBeInTheDocument()
  })

  it('shows MISSING status for attempt 1', () => {
    render(<ClauseDiffViewer history={[attempt1, attempt2]} />)
    const missingCells = screen.getAllByText('MISSING')
    expect(missingCells.length).toBeGreaterThan(0)
  })

  it('shows PRESENT status for attempt 2', () => {
    render(<ClauseDiffViewer history={[attempt1, attempt2]} />)
    const presentCells = screen.getAllByText('PRESENT')
    expect(presentCells.length).toBeGreaterThan(0)
  })

  it('renders a heading for the diff section', () => {
    render(<ClauseDiffViewer history={[attempt1, attempt2]} />)
    expect(screen.getByText(/retry diff/i)).toBeInTheDocument()
  })
})
