import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { ThemeProvider } from '@/contexts/theme-provider'
import DownloadPage from '@/pages/public/download'

vi.mock('sonner', () => ({
  toast: { success: vi.fn(), error: vi.fn() },
}))

function renderDownload() {
  return render(
    <MemoryRouter>
      <ThemeProvider>
        <DownloadPage />
      </ThemeProvider>
    </MemoryRouter>,
  )
}

describe('DownloadPage', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('renders the page title', () => {
    renderDownload()
    expect(
      screen.getByText('Download Operion Desktop'),
    ).toBeInTheDocument()
  })

  it('renders the version info', () => {
    renderDownload()
    expect(screen.getByText('Operion ERP 1.0.0')).toBeInTheDocument()
    expect(screen.getByText(/Released September 1, 2026/)).toBeInTheDocument()
  })

  it('renders download button', () => {
    renderDownload()
    const downloadBtn = screen.getByRole('link', {
      name: /download for windows/i,
    })
    expect(downloadBtn).toBeInTheDocument()
    expect(downloadBtn.getAttribute('href')).toBe('#download-windows')
  })

  it('renders system requirements table', () => {
    renderDownload()
    expect(screen.getByText('System Requirements')).toBeInTheDocument()
    expect(screen.getByText('Operating System')).toBeInTheDocument()
    expect(screen.getByText('RAM')).toBeInTheDocument()
    expect(screen.getByText('Storage')).toBeInTheDocument()
    expect(screen.getByText('Processor')).toBeInTheDocument()
  })

  it('renders release notes', () => {
    renderDownload()
    expect(screen.getByText('Release Notes')).toBeInTheDocument()
    expect(screen.getByText(/Initial release of Operion/)).toBeInTheDocument()
  })

  it('renders file checksums section', () => {
    renderDownload()
    expect(screen.getByText('File Checksums')).toBeInTheDocument()
    expect(screen.getByText('SHA-256')).toBeInTheDocument()
  })

  it('renders version history section', () => {
    renderDownload()
    expect(screen.getByText('Version History')).toBeInTheDocument()
    expect(
      screen.getByText('No previous versions available'),
    ).toBeInTheDocument()
  })

  it('renders toolkit section', () => {
    renderDownload()
    // Appears as both page header title and card title
    const toolkitTexts = screen.getAllByText('Operion Toolkit')
    expect(toolkitTexts.length).toBeGreaterThanOrEqual(2)
  })
})
