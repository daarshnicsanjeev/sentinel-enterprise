/**
 * TDD spec for App.tsx — tenant selector (C3) and override button (C2).
 */
import { render, screen } from '@testing-library/react'
import App from '../App'

describe('App — tenant selector (C3)', () => {
  it('renders a tenant selector labelled "Regulatory Profile"', () => {
    render(<App />)
    expect(screen.getByLabelText(/regulatory profile/i)).toBeInTheDocument()
  })

  it('tenant selector has Default, EU, and US options', () => {
    render(<App />)
    const select = screen.getByLabelText(/regulatory profile/i) as HTMLSelectElement
    const options = Array.from(select.options).map((o) => o.value)
    expect(options).toContain('default')
    expect(options).toContain('EU')
    expect(options).toContain('US')
  })

  it('tenant selector defaults to "default"', () => {
    render(<App />)
    const select = screen.getByLabelText(/regulatory profile/i) as HTMLSelectElement
    expect(select.value).toBe('default')
  })
})

describe('App — history tab (C1)', () => {
  it('renders an Analysis History tab button', () => {
    render(<App />)
    expect(screen.getByRole('button', { name: /analysis history/i })).toBeInTheDocument()
  })
})
