import { afterEach, describe, expect, it, vi } from 'vitest'
import { configureFavicon } from './favicon'

function makeImageProbe() {
  return { src: '', onload: null, onerror: null } as { src: string; onload: (() => void) | null; onerror: (() => void) | null }
}

afterEach(() => {
  document.head.querySelectorAll('link[rel~="icon"]').forEach((link) => link.remove())
})

describe('government favicon selection', () => {
  it('uses the optional government logo after the image loads', () => {
    const defaultLink = document.createElement('link')
    defaultLink.rel = 'icon'
    defaultLink.href = '/favicon.svg'
    defaultLink.type = 'image/svg+xml'
    document.head.append(defaultLink)

    const image = makeImageProbe()
    const createImage = vi.fn(() => image)
    configureFavicon(true, document, createImage)

    expect(image.src).toBe('/branding/gov-logo.png')
    expect(defaultLink.href).toBe(`${window.location.origin}/favicon.svg`)
    image.onload?.()
    expect(defaultLink.href).toBe(`${window.location.origin}/branding/gov-logo.png`)
    expect(defaultLink.type).toBe('image/png')
  })

  it('leaves the default favicon unchanged when the government logo cannot load', () => {
    const defaultLink = document.createElement('link')
    defaultLink.rel = 'icon'
    defaultLink.href = '/favicon.svg'
    defaultLink.type = 'image/svg+xml'
    document.head.append(defaultLink)

    const image = makeImageProbe()
    configureFavicon(true, document, () => image)
    image.onerror?.()

    expect(defaultLink.href).toBe(`${window.location.origin}/favicon.svg`)
    expect(defaultLink.type).toBe('image/svg+xml')
  })

  it('does not probe for or replace a favicon when government branding is disabled', () => {
    const defaultLink = document.createElement('link')
    defaultLink.rel = 'icon'
    defaultLink.href = '/favicon.svg'
    document.head.append(defaultLink)
    const createImage = vi.fn(makeImageProbe)

    configureFavicon(false, document, createImage)

    expect(createImage).not.toHaveBeenCalled()
    expect(defaultLink.href).toBe(`${window.location.origin}/favicon.svg`)
  })
})
