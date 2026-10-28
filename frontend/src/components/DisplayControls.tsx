import { useEffect, useState } from 'react'

export default function DisplayControls() {
  const [highContrast, setHighContrast] = useState(false)
  const [textSize, setTextSize] = useState<'small' | 'normal' | 'large'>('normal')

  useEffect(() => {
    const root = document.documentElement
    root.classList.toggle('hc', highContrast)
    root.dataset.textSize = textSize
    return () => {
      root.classList.remove('hc')
      delete root.dataset.textSize
    }
  }, [highContrast, textSize])

  return <div className="accessibility-tools" aria-label="Display settings">
    <span className="display-label">Text size</span>
    <button type="button" aria-label="Decrease text size" aria-pressed={textSize === 'small'} onClick={() => setTextSize('small')}>A−</button>
    <button type="button" aria-label="Default text size" aria-pressed={textSize === 'normal'} onClick={() => setTextSize('normal')}>A</button>
    <button type="button" aria-label="Increase text size" aria-pressed={textSize === 'large'} onClick={() => setTextSize('large')}>A+</button>
    <button type="button" className="contrast-toggle" aria-pressed={highContrast} onClick={() => setHighContrast((value) => !value)}>{highContrast ? 'Standard contrast' : 'High contrast'}</button>
  </div>
}
