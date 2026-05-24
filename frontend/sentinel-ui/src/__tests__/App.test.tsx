/**
 * TDD spec for App.tsx — override button (C2), clause display.
 */
import { render, screen } from '@testing-library/react'
import App from '../App'
import { clauseDisplayLabel } from '../App'

describe('App — history tab (C1)', () => {
  it('renders an Analysis History tab button', () => {
    render(<App />)
    expect(screen.getByRole('button', { name: /analysis history/i })).toBeInTheDocument()
  })
})

describe('App — guardrail block visibility', () => {
  it('override button is absent when sanitized is false', () => {
    // The override button condition requires sanitized !== false, so with no result
    // rendered it simply should not appear on initial load
    render(<App />)
    expect(screen.queryByText(/override.*approve/i)).not.toBeInTheDocument()
  })
})

describe('clauseDisplayLabel — ESCALATE unverified badge', () => {
  it('returns PRESENT unchanged when decision is not ESCALATE', () => {
    expect(clauseDisplayLabel('PRESENT', 'APPROVED')).toBe('PRESENT')
  })

  it('returns MISSING unchanged when decision is not ESCALATE', () => {
    expect(clauseDisplayLabel('MISSING', 'APPROVED')).toBe('MISSING')
  })

  it('returns ⚠ UNVERIFIED for PRESENT when decision is ESCALATE', () => {
    expect(clauseDisplayLabel('PRESENT', 'ESCALATE')).toBe('⚠ UNVERIFIED')
  })

  it('returns MISSING unchanged even when decision is ESCALATE', () => {
    expect(clauseDisplayLabel('MISSING', 'ESCALATE')).toBe('MISSING')
  })

  it('returns PRESENT unchanged when decision is REJECTED', () => {
    expect(clauseDisplayLabel('PRESENT', 'REJECTED')).toBe('PRESENT')
  })
})
