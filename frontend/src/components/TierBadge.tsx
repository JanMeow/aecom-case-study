import { tierColor } from '../colors'
import type { Tier } from '../types'

// Small coloured label for a risk tier
export default function TierBadge({ tier, score }: { tier: Tier; score?: number }) {
  return (
    <span className="inline-flex items-center gap-1 rounded px-1.5 py-0.5 text-xs font-semibold text-white"
          style={{ background: tierColor(tier) }}>
      {tier}{score !== undefined && <span className="font-normal opacity-90">{score.toFixed(2)}</span>}
    </span>
  )
}
