/**
 * TDD spec for DocumentUpload component.
 *
 * Contract: the upload zone must be accessible, respond to file selection,
 * and disable itself correctly when a stream is in progress.
 */
import { render, screen, fireEvent } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { DocumentUpload } from '../components/DocumentUpload'

describe('DocumentUpload', () => {
  describe('rendering', () => {
    it('renders the drop zone', () => {
      render(<DocumentUpload onFile={vi.fn()} disabled={false} />)
      expect(screen.getByRole('button')).toBeInTheDocument()
    })

    it('has an accessible aria-label', () => {
      render(<DocumentUpload onFile={vi.fn()} disabled={false} />)
      const zone = screen.getByRole('button')
      expect(zone).toHaveAttribute('aria-label')
      expect(zone.getAttribute('aria-label')).toMatch(/upload/i)
    })

    it('shows descriptive text about supported types', () => {
      render(<DocumentUpload onFile={vi.fn()} disabled={false} />)
      expect(screen.getByText(/.txt/i)).toBeInTheDocument()
    })

    it('renders a hidden file input', () => {
      const { container } = render(<DocumentUpload onFile={vi.fn()} disabled={false} />)
      const input = container.querySelector('input[type="file"]')
      expect(input).toBeInTheDocument()
      expect(input).toHaveStyle({ display: 'none' })
    })
  })

  describe('interaction', () => {
    it('calls onFile when a file is selected via input', async () => {
      const onFile = vi.fn()
      const { container } = render(<DocumentUpload onFile={onFile} disabled={false} />)
      const input = container.querySelector('input[type="file"]') as HTMLInputElement

      const file = new File(['contract text'], 'contract.txt', { type: 'text/plain' })
      await userEvent.upload(input, file)

      expect(onFile).toHaveBeenCalledOnce()
      expect(onFile).toHaveBeenCalledWith(file)
    })

    it('calls onFile when a file is dropped onto the zone', () => {
      const onFile = vi.fn()
      render(<DocumentUpload onFile={onFile} disabled={false} />)
      const zone = screen.getByRole('button')

      const file = new File(['agreement text'], 'agreement.txt', { type: 'text/plain' })
      fireEvent.drop(zone, {
        dataTransfer: { files: [file] },
      })

      expect(onFile).toHaveBeenCalledOnce()
      expect(onFile).toHaveBeenCalledWith(file)
    })

    it('is keyboard activatable via Enter key', () => {
      const onFile = vi.fn()
      const { container } = render(<DocumentUpload onFile={onFile} disabled={false} />)
      const zone = screen.getByRole('button')
      const input = container.querySelector('input[type="file"]') as HTMLInputElement
      const clickSpy = vi.spyOn(input, 'click')

      fireEvent.keyDown(zone, { key: 'Enter' })
      expect(clickSpy).toHaveBeenCalled()
    })
  })

  describe('disabled state', () => {
    it('has not-allowed cursor when disabled', () => {
      render(<DocumentUpload onFile={vi.fn()} disabled={true} />)
      const zone = screen.getByRole('button')
      expect(zone.style.cursor).toBe('not-allowed')
    })

    it('has reduced opacity when disabled', () => {
      render(<DocumentUpload onFile={vi.fn()} disabled={true} />)
      const zone = screen.getByRole('button')
      expect(zone.style.opacity).toBe('0.5')
    })

    it('does not open file picker when disabled', () => {
      const { container } = render(<DocumentUpload onFile={vi.fn()} disabled={true} />)
      const zone = screen.getByRole('button')
      const input = container.querySelector('input[type="file"]') as HTMLInputElement
      const clickSpy = vi.spyOn(input, 'click')

      fireEvent.click(zone)
      expect(clickSpy).not.toHaveBeenCalled()
    })

    it('file input has disabled attribute when disabled', () => {
      const { container } = render(<DocumentUpload onFile={vi.fn()} disabled={true} />)
      const input = container.querySelector('input[type="file"]')
      expect(input).toBeDisabled()
    })
  })

  describe('WCAG 2.1 AA accessibility', () => {
    it('activates file picker on Space key (2.1.1 Keyboard)', () => {
      const { container } = render(<DocumentUpload onFile={vi.fn()} disabled={false} />)
      const zone = screen.getByRole('button')
      const input = container.querySelector('input[type="file"]') as HTMLInputElement
      const clickSpy = vi.spyOn(input, 'click')

      fireEvent.keyDown(zone, { key: ' ' })
      expect(clickSpy).toHaveBeenCalled()
    })

    it('does not activate on Space key when disabled', () => {
      const { container } = render(<DocumentUpload onFile={vi.fn()} disabled={true} />)
      const zone = screen.getByRole('button')
      const input = container.querySelector('input[type="file"]') as HTMLInputElement
      const clickSpy = vi.spyOn(input, 'click')

      fireEvent.keyDown(zone, { key: ' ' })
      expect(clickSpy).not.toHaveBeenCalled()
    })

    it('has aria-disabled=true when disabled (4.1.2 Name Role Value)', () => {
      render(<DocumentUpload onFile={vi.fn()} disabled={true} />)
      const zone = screen.getByRole('button')
      expect(zone).toHaveAttribute('aria-disabled', 'true')
    })

    it('has aria-disabled=false when enabled', () => {
      render(<DocumentUpload onFile={vi.fn()} disabled={false} />)
      const zone = screen.getByRole('button')
      expect(zone).toHaveAttribute('aria-disabled', 'false')
    })

    it('has upload-zone class for :focus-visible CSS rule (2.4.7 Focus Visible)', () => {
      render(<DocumentUpload onFile={vi.fn()} disabled={false} />)
      const zone = screen.getByRole('button')
      expect(zone.classList.contains('upload-zone')).toBe(true)
    })
  })
})
