/**
 * TDD spec for the visitor demo-feedback form and the demo-mode notice.
 */
import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import { vi } from 'vitest'
import { DemoFeedback } from '../components/DemoFeedback'
import { DemoNotice } from '../components/DemoNotice'

describe('DemoNotice', () => {
  it('explains that login is intentionally disabled for the demo', () => {
    render(<DemoNotice />)
    const note = screen.getByRole('note')
    expect(note).toHaveTextContent(/login disabled/i)
    expect(note).toHaveTextContent(/demo/i)
  })

  it('mentions that production enforces authentication', () => {
    render(<DemoNotice />)
    expect(screen.getByRole('note')).toHaveTextContent(/production.*authentication/i)
  })
})

describe('DemoFeedback', () => {
  afterEach(() => vi.restoreAllMocks())

  const fill = (message: string) => {
    fireEvent.change(screen.getByLabelText(/your feedback/i), {
      target: { value: message },
    })
  }

  it('renders name, email, message fields and a submit button', () => {
    render(<DemoFeedback apiBase="" />)
    expect(screen.getByLabelText(/name/i)).toBeInTheDocument()
    expect(screen.getByLabelText(/email/i)).toBeInTheDocument()
    expect(screen.getByLabelText(/your feedback/i)).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /send feedback/i })).toBeInTheDocument()
  })

  it('renders five star rating buttons', () => {
    render(<DemoFeedback apiBase="" />)
    expect(screen.getAllByRole('radio')).toHaveLength(5)
  })

  it('rejects a message shorter than 10 characters without calling the API', () => {
    const fetchMock = vi.fn()
    vi.stubGlobal('fetch', fetchMock)
    render(<DemoFeedback apiBase="" />)
    fill('too short')
    fireEvent.click(screen.getByRole('button', { name: /send feedback/i }))
    expect(screen.getByRole('alert')).toHaveTextContent(/at least 10 characters/i)
    expect(fetchMock).not.toHaveBeenCalled()
  })

  it('posts feedback to /api/demo-feedback and shows a thank-you message', async () => {
    const fetchMock = vi.fn().mockResolvedValue({ ok: true, status: 200 })
    vi.stubGlobal('fetch', fetchMock)
    render(<DemoFeedback apiBase="" />)
    fill('The citation verification feature is excellent.')
    fireEvent.click(screen.getByRole('button', { name: /send feedback/i }))
    await waitFor(() => expect(screen.getByRole('status')).toHaveTextContent(/thank you/i))
    expect(fetchMock).toHaveBeenCalledWith(
      '/api/demo-feedback',
      expect.objectContaining({ method: 'POST' }),
    )
    const body = JSON.parse(fetchMock.mock.calls[0][1].body)
    expect(body.message).toBe('The citation verification feature is excellent.')
  })

  it('includes the selected rating in the payload', async () => {
    const fetchMock = vi.fn().mockResolvedValue({ ok: true, status: 200 })
    vi.stubGlobal('fetch', fetchMock)
    render(<DemoFeedback apiBase="" />)
    fill('Great demo, would love to see SSO integration next.')
    fireEvent.click(screen.getByRole('radio', { name: /4 stars/i }))
    fireEvent.click(screen.getByRole('button', { name: /send feedback/i }))
    await waitFor(() => expect(fetchMock).toHaveBeenCalled())
    const body = JSON.parse(fetchMock.mock.calls[0][1].body)
    expect(body.rating).toBe(4)
  })

  it('shows a friendly error when the API call fails', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue({ ok: false, status: 429 }))
    render(<DemoFeedback apiBase="" />)
    fill('This message is long enough to pass validation.')
    fireEvent.click(screen.getByRole('button', { name: /send feedback/i }))
    await waitFor(() =>
      expect(screen.getByRole('alert')).toHaveTextContent(/try again/i),
    )
  })
})
