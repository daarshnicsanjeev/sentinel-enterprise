/**
 * TDD spec for ConfidenceGauge component.
 */
import { render, screen } from '@testing-library/react'
import { ConfidenceGauge } from '../components/ConfidenceGauge'

describe('ConfidenceGauge', () => {
  it('renders an SVG when confidence is 0', () => {
    const { container } = render(<ConfidenceGauge confidence={0} />)
    expect(container.querySelector('svg')).toBeInTheDocument()
    expect(screen.getByText('0%')).toBeInTheDocument()
  })

  it('renders an SVG when confidence is > 0', () => {
    const { container } = render(<ConfidenceGauge confidence={0.85} />)
    expect(container.querySelector('svg')).toBeInTheDocument()
  })

  it('displays the confidence percentage as text', () => {
    render(<ConfidenceGauge confidence={0.75} />)
    expect(screen.getByText('75%')).toBeInTheDocument()
  })

  it('displays 100% for confidence of 1.0', () => {
    render(<ConfidenceGauge confidence={1.0} />)
    expect(screen.getByText('100%')).toBeInTheDocument()
  })

  it('renders a label describing routing confidence', () => {
    render(<ConfidenceGauge confidence={0.9} />)
    expect(screen.getByText(/confidence/i)).toBeInTheDocument()
  })

  it('rounds fractional percentages to integer', () => {
    render(<ConfidenceGauge confidence={0.876} />)
    expect(screen.getByText('88%')).toBeInTheDocument()
  })

  it('renders nothing when confidence is above 1', () => {
    const { container } = render(<ConfidenceGauge confidence={1.5} />)
    expect(container.firstChild).toBeNull()
  })

  it('renders nothing when confidence is negative', () => {
    const { container } = render(<ConfidenceGauge confidence={-0.1} />)
    expect(container.firstChild).toBeNull()
  })

  it('renders nothing when confidence is null', () => {
    const { container } = render(<ConfidenceGauge confidence={null as unknown as number} />)
    expect(container.firstChild).toBeNull()
  })
})
