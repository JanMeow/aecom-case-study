// Colours for code that can't use Tailwind classes (MapLibre layers, SVG, inline styles).
// They are defined once in index.css (@theme) and read from there, so changing a colour is one edit.
import type { Tier } from './types'

const NAMES = ['navy', 'teal', 'tier-low', 'tier-medium', 'tier-high', 'tier-critical', 'wind-34', 'wind-50',
               'wind-64', 'surface', 'border', 'muted', 'label', 'ink'] as const
type Name = (typeof NAMES)[number]

let cache: Record<Name, string> | null = null

// Read every colour variable once (first use), then reuse
export function palette(): Record<Name, string> {
  if (!cache) {
    const style = getComputedStyle(document.documentElement)
    cache = Object.fromEntries(NAMES.map((n) => [n, style.getPropertyValue(`--color-${n}`).trim()])) as Record<Name, string>
  }
  return cache
}

export const tierColor = (tier: Tier) => palette()[`tier-${tier.toLowerCase()}` as Name]
