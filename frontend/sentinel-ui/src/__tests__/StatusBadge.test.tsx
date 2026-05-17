/**
 * TDD spec for StatusBadge component.
 *
 * Contract: renders the correct label, aria-label, and background color
 * for every decision state the system can emit.
 */
import { render, screen } from '@testing-library/react'
import { StatusBadge } from '../components/StatusBadge'

describe('StatusBadge', () => {
  describe('label rendering', () => {
    it('renders APPROVED text', () => {
      render(<StatusBadge decision="APPROVED" />)
      expect(screen.getByText('APPROVED')).toBeInTheDocument()
    })

    it('renders REJECTED text', () => {
      render(<StatusBadge decision="REJECTED" />)
      expect(screen.getByText('REJECTED')).toBeInTheDocument()
    })

    it('renders RE-ROUTE text', () => {
      render(<StatusBadge decision="RE-ROUTE" />)
      expect(screen.getByText('RE-ROUTE')).toBeInTheDocument()
    })

    it('renders PENDING text', () => {
      render(<StatusBadge decision="PENDING" />)
      expect(screen.getByText('PENDING')).toBeInTheDocument()
    })

    it('renders BLOCKED text', () => {
      render(<StatusBadge decision="BLOCKED" />)
      expect(screen.getByText('BLOCKED')).toBeInTheDocument()
    })

    it('renders unknown decision as-is', () => {
      render(<StatusBadge decision="CUSTOM_STATE" />)
      expect(screen.getByText('CUSTOM_STATE')).toBeInTheDocument()
    })
  })

  describe('accessibility', () => {
    it('has aria-label containing the decision', () => {
      render(<StatusBadge decision="APPROVED" />)
      expect(screen.getByLabelText(/APPROVED/i)).toBeInTheDocument()
    })

    it('has aria-label for REJECTED', () => {
      render(<StatusBadge decision="REJECTED" />)
      expect(screen.getByLabelText(/REJECTED/i)).toBeInTheDocument()
    })
  })

  describe('background color — WCAG 2.1 AA compliant (≥4.5:1 white contrast)', () => {
    it('APPROVED badge has green-700 background (#15803d, ~4.6:1)', () => {
      render(<StatusBadge decision="APPROVED" />)
      const badge = screen.getByText('APPROVED')
      expect(badge.style.background).toBe('rgb(21, 128, 61)')
    })

    it('REJECTED badge has red-700 background (#b91c1c, ~7.0:1)', () => {
      render(<StatusBadge decision="REJECTED" />)
      const badge = screen.getByText('REJECTED')
      expect(badge.style.background).toBe('rgb(185, 28, 28)')
    })

    it('RE-ROUTE badge has amber-700 background (#b45309, ~4.5:1)', () => {
      render(<StatusBadge decision="RE-ROUTE" />)
      const badge = screen.getByText('RE-ROUTE')
      expect(badge.style.background).toBe('rgb(180, 83, 9)')
    })

    it('PENDING badge has blue-700 background (#1d4ed8, ~5.8:1)', () => {
      render(<StatusBadge decision="PENDING" />)
      const badge = screen.getByText('PENDING')
      expect(badge.style.background).toBe('rgb(29, 78, 216)')
    })

    it('BLOCKED badge has violet-700 background (#6d28d9, ~5.1:1)', () => {
      render(<StatusBadge decision="BLOCKED" />)
      const badge = screen.getByText('BLOCKED')
      expect(badge.style.background).toBe('rgb(109, 40, 217)')
    })

    it('unknown decision gets a fallback grey background', () => {
      render(<StatusBadge decision="SOMETHING_ELSE" />)
      const badge = screen.getByText('SOMETHING_ELSE')
      expect(badge.style.background).toBe('rgb(107, 114, 128)')
    })
  })

  describe('structure', () => {
    it('renders as a span element', () => {
      const { container } = render(<StatusBadge decision="APPROVED" />)
      expect(container.firstChild?.nodeName).toBe('SPAN')
    })
  })
})
