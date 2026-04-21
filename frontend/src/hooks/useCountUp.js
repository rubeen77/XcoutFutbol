import { useState, useEffect } from 'react'

/**
 * Animates a number from 0 to `target` over `duration` ms (ease-out cubic).
 * Resets and replays whenever `target` changes.
 */
export function useCountUp(target, duration = 700) {
  const num      = parseFloat(target) ?? 0
  const decimals = String(target).includes('.') ? (String(target).split('.')[1]?.length ?? 1) : 0
  const [value, setValue] = useState(0)

  useEffect(() => {
    if (!num) { setValue(0); return }
    let startTime = null
    let raf

    const step = (timestamp) => {
      if (!startTime) startTime = timestamp
      const progress = Math.min((timestamp - startTime) / duration, 1)
      // ease-out cubic
      const eased   = 1 - Math.pow(1 - progress, 3)
      const current = num * eased
      setValue(decimals ? parseFloat(current.toFixed(decimals)) : Math.round(current))
      if (progress < 1) raf = requestAnimationFrame(step)
    }

    setValue(0)
    raf = requestAnimationFrame(step)
    return () => cancelAnimationFrame(raf)
  }, [target, duration])   // eslint-disable-line react-hooks/exhaustive-deps

  return value
}
