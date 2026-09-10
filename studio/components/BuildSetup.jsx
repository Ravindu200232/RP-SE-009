'use client'

import { useState } from 'react'
import { ArrowRight } from 'lucide-react'
import { Button, Input, Modal } from './ui'
import { STACKS } from '@/lib/stacks'

export default function BuildSetup({ model, stack, think, options = [], onContinue, onCancel }) {
  const [selectedModel, setModel] = useState(model || '')
  const [selectedStack, setStack] = useState(stack || 'nextjs-mongo')
  const [thinking, setThinking] = useState(Boolean(think))
  const choices = [...new Map(options.map(item => [item.id, item])).values()]

  return (
    <Modal onClose={onCancel}>
      <section role="dialog" aria-modal="true" aria-labelledby="build-settings-title">
        <h2 id="build-settings-title" className="text-[17px] font-semibold text-ink">Configure your build</h2>
        <p className="mt-2 text-[12px] leading-relaxed text-muted">
          Choose your model and stack. Review the plan next, then customize the design before the app is built and tested.
        </p>
        <label htmlFor="build-model" className="mt-5 block text-[12px] font-semibold text-ink">Model</label>
        <Input id="build-model" list="build-model-options" value={selectedModel}
               placeholder="Choose or enter an Ollama model ID"
               onChange={event => setModel(event.target.value)} className="mt-2" />
        <datalist id="build-model-options">
          {choices.map(item => <option key={item.id} value={item.id}>{item.label || item.id}</option>)}
        </datalist>
        <p className="mt-1.5 text-[11px] text-muted2">Used for planning, design and building.</p>
        <label htmlFor="build-setup-stack" className="mt-4 block text-[12px] font-semibold text-ink">Stack</label>
        <select id="build-setup-stack" value={selectedStack}
                onChange={event => setStack(event.target.value)}
                className="mt-2 h-10 w-full rounded-xl border border-line bg-panel px-3 text-[12px] text-ink">
          {STACKS.map(item => <option key={item.id} value={item.id}>{item.name}</option>)}
        </select>
        <p className="mt-1.5 text-[11px] text-muted2">{STACKS.find(item => item.id === selectedStack)?.blurb}</p>
        <label className="mt-4 flex items-center gap-2 text-[12px] text-ink">
          <input type="checkbox" checked={thinking} onChange={event => setThinking(event.target.checked)} />
          Enable model thinking
        </label>
        <footer className="mt-5 flex justify-end gap-2 border-t border-line pt-4">
          <Button variant="outline" onClick={onCancel}>Back</Button>
          <Button variant="solid" disabled={!selectedModel.trim()}
                  onClick={() => onContinue({ model: selectedModel.trim(), stack: selectedStack,
                                              think: thinking })}>
            Create plan <ArrowRight className="size-3" />
          </Button>
        </footer>
      </section>
    </Modal>
  )
}
