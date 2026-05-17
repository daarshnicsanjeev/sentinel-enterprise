/**
 * TDD spec for WorkflowStream component.
 *
 * Contract: the stream viewer must be accessible (aria-live), render log
 * entries with node colour cues, and indicate live streaming status.
 */
import { render, screen } from '@testing-library/react'
import { WorkflowStream } from '../components/WorkflowStream'

const makeLogs = (count: number) =>
  Array.from({ length: count }, (_, i) => ({
    node: 'guardrail',
    message: `[Guardrail] Log entry ${i + 1}`,
  }))

describe('WorkflowStream', () => {
  describe('accessibility', () => {
    it('has aria-live="polite"', () => {
      const { container } = render(<WorkflowStream logs={[]} streaming={false} />)
      const region = container.firstChild as HTMLElement
      expect(region).toHaveAttribute('aria-live', 'polite')
    })

    it('has aria-atomic="false" to allow incremental announcements', () => {
      const { container } = render(<WorkflowStream logs={[]} streaming={false} />)
      const region = container.firstChild as HTMLElement
      expect(region).toHaveAttribute('aria-atomic', 'false')
    })

    it('has an aria-label describing the region', () => {
      const { container } = render(<WorkflowStream logs={[]} streaming={false} />)
      const region = container.firstChild as HTMLElement
      expect(region).toHaveAttribute('aria-label')
    })
  })

  describe('empty state', () => {
    it('shows upload prompt when no logs and not streaming', () => {
      render(<WorkflowStream logs={[]} streaming={false} />)
      expect(screen.getByText(/upload a document/i)).toBeInTheDocument()
    })

    it('shows initialising message when no logs but streaming', () => {
      render(<WorkflowStream logs={[]} streaming={true} />)
      expect(screen.getByText(/initialising/i)).toBeInTheDocument()
    })
  })

  describe('log rendering', () => {
    it('renders each log entry', () => {
      const logs = [
        { node: 'guardrail', message: '[Guardrail] Input sanitized: OK' },
        { node: 'router', message: '[Router] Document classified as: LEGAL_CONTRACT' },
      ]
      render(<WorkflowStream logs={logs} streaming={false} />)
      expect(screen.getByText('[Guardrail] Input sanitized: OK')).toBeInTheDocument()
      expect(screen.getByText('[Router] Document classified as: LEGAL_CONTRACT')).toBeInTheDocument()
    })

    it('renders all log entries when many are provided', () => {
      const logs = makeLogs(10)
      render(<WorkflowStream logs={logs} streaming={false} />)
      logs.forEach(log => {
        expect(screen.getByText(log.message)).toBeInTheDocument()
      })
    })

    it('does not show upload prompt when logs are present', () => {
      render(<WorkflowStream logs={makeLogs(1)} streaming={false} />)
      expect(screen.queryByText(/upload a document/i)).not.toBeInTheDocument()
    })
  })

  describe('streaming indicator', () => {
    it('shows processing indicator while streaming', () => {
      render(<WorkflowStream logs={makeLogs(1)} streaming={true} />)
      expect(screen.getByText(/processing/i)).toBeInTheDocument()
    })

    it('does not show processing indicator when not streaming', () => {
      render(<WorkflowStream logs={makeLogs(1)} streaming={false} />)
      expect(screen.queryByText(/processing/i)).not.toBeInTheDocument()
    })
  })

  describe('WCAG 2.1 AA accessibility', () => {
    it('renders log entries as <li> elements inside a <ul> (1.3.1 Info and Relationships)', () => {
      const logs = [
        { node: 'guardrail', message: '[Guardrail] Input sanitized: OK' },
        { node: 'router', message: '[Router] Classified as: LEGAL_CONTRACT' },
      ]
      const { container } = render(<WorkflowStream logs={logs} streaming={false} />)
      const ul = container.querySelector('ul')
      expect(ul).toBeInTheDocument()
      const items = ul!.querySelectorAll('li')
      expect(items).toHaveLength(2)
    })

    it('shows node name as visible text label on each entry (1.4.1 Use of Color)', () => {
      const logs = [
        { node: 'guardrail', message: '[Guardrail] Input sanitized: OK' },
        { node: 'compliance', message: '[Compliance] Verdict: REJECTED' },
      ]
      render(<WorkflowStream logs={logs} streaming={false} />)
      expect(screen.getByText('GUARDRAIL')).toBeInTheDocument()
      expect(screen.getByText('COMPLIANCE')).toBeInTheDocument()
    })
  })
})
