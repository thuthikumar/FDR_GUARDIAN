import { SHOW_GOV_BRANDING } from './branding'

type ImageProbe = {
  src: string
  onload: (() => void) | null
  onerror: (() => void) | null
}

export function configureFavicon(
  showGovBranding = SHOW_GOV_BRANDING,
  documentRef: Document = document,
  createImage: () => ImageProbe = () => new Image() as ImageProbe,
) {
  if (!showGovBranding) return

  const image = createImage()
  image.onload = () => {
    let iconLink = documentRef.querySelector<HTMLLinkElement>('link[rel~="icon"]')
    if (!iconLink) {
      iconLink = documentRef.createElement('link')
      iconLink.rel = 'icon'
      documentRef.head.append(iconLink)
    }
    iconLink.href = '/branding/gov-logo.png'
    iconLink.type = 'image/png'
  }
  image.onerror = () => undefined
  image.src = '/branding/gov-logo.png'
}
