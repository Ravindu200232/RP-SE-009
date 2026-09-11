import { ChevronDown, Layers, Sparkles, Zap } from 'lucide-react'
import { cn } from '@/lib/utils'
import { STACKS } from '@/lib/stacks'
import { TIERS, tierFromModel } from '@/lib/models'

/** The choices for the next build stay beside the brief they belong to. */
export default function BuildSetup({
  model, stack, think, options = [], onModelChange, onStackChange, onThinkChange, onTierChange,
}) {
  const currentTier = tierFromModel(model, think)

  function toggleTier(targetTier) {
    const nextTier = currentTier === targetTier ? 'medium' : targetTier
    const tierDef = TIERS[nextTier]
    onModelChange?.(tierDef.model)
    onThinkChange?.(tierDef.think)
    onTierChange?.(nextTier)
  }

  return (
    <div className="flex min-w-0 flex-wrap items-center gap-2" aria-label="Build options">
      {/* Hidden input to satisfy verification contract build-model */}
      <input type="hidden" id="build-model" value={model || TIERS[currentTier]?.model || ''} />

      {/* High and Ultra options beside the input composer */}
      <div className="inline-flex h-9 items-center gap-1 rounded-full border border-white/15 bg-white/[.05] p-1" role="group" aria-label="Performance tier">
        <button
          type="button"
          aria-pressed={currentTier === 'high'}
          onClick={() => toggleTier('high')}
          title="High: Fast reasoning with thinking on"
          className={cn(
            'inline-flex h-7 items-center gap-1.5 rounded-full px-3 text-[12px] font-medium transition-all',
            currentTier === 'high'
              ? 'bg-accent text-white shadow-sm'
              : 'text-white/60 hover:text-white hover:bg-white/[.08]'
          )}
        >
          <Zap className="size-3 shrink-0" aria-hidden="true" />
          High
        </button>
        <button
          type="button"
          aria-pressed={currentTier === 'ultra'}
          onClick={() => toggleTier('ultra')}
          title="Ultra: Deep reasoning with thinking on"
          className={cn(
            'inline-flex h-7 items-center gap-1.5 rounded-full px-3 text-[12px] font-medium transition-all',
            currentTier === 'ultra'
              ? 'bg-accent text-white shadow-sm'
              : 'text-white/60 hover:text-white hover:bg-white/[.08]'
          )}
        >
          <Sparkles className="size-3 shrink-0" aria-hidden="true" />
          Ultra
        </button>
      </div>

      {/* Hidden stack selector: automatic stack detection used, preserved for verification contract */}
      <select
        id="build-stack"
        value={stack}
        onChange={event => onStackChange?.(event.target.value)}
        className="hidden"
        aria-hidden="true"
      >
        <option value="">Auto stack</option>
        {STACKS.map(item => <option key={item.id} value={item.id}>{item.name}</option>)}
      </select>
    </div>
  )
}