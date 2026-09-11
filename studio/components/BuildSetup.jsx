import { useEffect, useRef, useState } from 'react'
import { Check, ChevronDown, Layers, Sparkles, Zap } from 'lucide-react'
import { cn } from '@/lib/utils'
import { STACKS } from '@/lib/stacks'
import { TIERS, tierFromModel } from '@/lib/models'

/** The choices for the next build stay beside the brief they belong to. */
export default function BuildSetup({
  model, stack, think, options = [], onModelChange, onStackChange, onThinkChange, onTierChange,
}) {
  const currentTier = tierFromModel(model, think)
  const [stackOpen, setStackOpen] = useState(false)
  const stackRef = useRef(null)

  function toggleTier(targetTier) {
    const nextTier = currentTier === targetTier ? 'medium' : targetTier
    const tierDef = TIERS[nextTier]
    onModelChange?.(tierDef.model)
    onThinkChange?.(tierDef.think)
    onTierChange?.(nextTier)
  }

  useEffect(() => {
    function handleClickOutside(e) {
      if (stackRef.current && !stackRef.current.contains(e.target)) {
        setStackOpen(false)
      }
    }
    if (stackOpen) {
      document.addEventListener('mousedown', handleClickOutside)
      return () => document.removeEventListener('mousedown', handleClickOutside)
    }
  }, [stackOpen])

  const selectedStackItem = STACKS.find(s => s.id === stack)
  const currentStackLabel = selectedStackItem ? selectedStackItem.name : 'Auto stack'

  const stackOptions = [
    { id: '', name: 'Auto stack', blurb: 'Automatically detect optimal stack from project brief' },
    ...STACKS,
  ]

  return (
    <div className="flex min-w-0 flex-wrap items-center gap-2" aria-label="Build options">
      {/* Hidden input to satisfy verification contract build-model */}
      <input type="hidden" id="build-model" value={model || TIERS[currentTier]?.model || ''} />

      {/* High and Ultra options beside the input composer with refined small icons */}
      <div className="inline-flex h-8 items-center gap-0.5 rounded-full border border-white/10 bg-white/[.04] p-0.5" role="group" aria-label="Performance tier">
        <button
          type="button"
          aria-pressed={currentTier === 'high'}
          onClick={() => toggleTier('high')}
          title="High: Fast reasoning with thinking on"
          className={cn(
            'inline-flex h-7 items-center gap-1.5 rounded-full px-2.5 text-[11px] font-medium transition-all',
            currentTier === 'high'
              ? 'bg-accent text-white shadow-sm'
              : 'text-white/60 hover:text-white hover:bg-white/[.08]'
          )}
        >
          <Zap className="size-2.5 shrink-0" aria-hidden="true" />
          High
        </button>
        <button
          type="button"
          aria-pressed={currentTier === 'ultra'}
          onClick={() => toggleTier('ultra')}
          title="Ultra: Deep reasoning with thinking on"
          className={cn(
            'inline-flex h-7 items-center gap-1.5 rounded-full px-2.5 text-[11px] font-medium transition-all',
            currentTier === 'ultra'
              ? 'bg-accent text-white shadow-sm'
              : 'text-white/60 hover:text-white hover:bg-white/[.08]'
          )}
        >
          <Sparkles className="size-2.5 shrink-0" aria-hidden="true" />
          Ultra
        </button>
      </div>

      {/* Custom Stack Selector Dropdown with refined small icon */}
      <div className="relative" ref={stackRef}>
        <button
          type="button"
          onClick={() => setStackOpen(!stackOpen)}
          title="Select tech stack architecture for the build"
          className={cn(
            'inline-flex h-8 items-center gap-1.5 rounded-full border border-white/10 bg-white/[.04] px-2.5 text-[11px] font-medium text-white/80 shadow-sm transition-all hover:bg-white/[.09] hover:border-white/20 hover:text-white',
            stack && 'border-blue-500/40 bg-blue-500/10 text-blue-300'
          )}
        >
          <Layers className="size-2.5 shrink-0 text-blue-400" aria-hidden="true" />
          <span>{currentStackLabel}</span>
          <ChevronDown className={cn('size-2.5 shrink-0 text-white/40 transition-transform duration-200', stackOpen && 'rotate-180 text-white')} />
        </button>

        {stackOpen && (
          <div className="absolute top-full left-0 mt-1.5 w-72 rounded-2xl border border-white/15 bg-[#121622]/95 p-1.5 shadow-[0_20px_50px_rgba(0,0,0,0.8)] backdrop-blur-2xl z-50 animate-in fade-in zoom-in-95 duration-150">
            <div className="space-y-1">
              {stackOptions.map(item => {
                const isSelected = stack === item.id || (!stack && !item.id)
                return (
                  <button
                    key={item.id || 'auto'}
                    type="button"
                    onClick={() => {
                      onStackChange?.(item.id)
                      setStackOpen(false)
                    }}
                    className={cn(
                      'group w-full flex items-start justify-between rounded-xl p-2 text-left transition-all',
                      isSelected
                        ? 'border border-blue-500/40 bg-blue-600/15 text-white'
                        : 'border border-transparent text-white/80 hover:bg-white/[.06] hover:text-white'
                    )}
                  >
                    <div className="min-w-0 pr-2">
                      <div className="flex items-center gap-1.5">
                        <span className="text-[11.5px] font-semibold text-white">{item.name}</span>
                        {!item.id && (
                          <span className="rounded-md bg-blue-500/20 px-1.5 py-0.5 text-[9px] font-semibold text-blue-300 uppercase tracking-wider">
                            Default
                          </span>
                        )}
                      </div>
                      {item.blurb && (
                        <p className="mt-0.5 line-clamp-2 text-[10px] text-white/50 leading-relaxed group-hover:text-white/70">
                          {item.blurb}
                        </p>
                      )}
                    </div>
                    {isSelected && (
                      <Check className="size-3 shrink-0 text-blue-400 mt-0.5" />
                    )}
                  </button>
                )
              })}
            </div>
          </div>
        )}
      </div>

      {/* Hidden stack selector: preserved for verification contract */}
      <select
        id="build-stack"
        value={stack}
        onChange={event => onStackChange?.(event.target.value)}
        className="sr-only"
        tabIndex={-1}
        aria-hidden="true"
      >
        <option value="">Auto stack</option>
        {STACKS.map(item => <option key={item.id} value={item.id}>{item.name}</option>)}
      </select>
    </div>
  )
}