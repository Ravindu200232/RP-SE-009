'use client'

import { Check, CreditCard, Sparkles, X, Zap } from 'lucide-react'
import { Modal } from './ui'

export default function SubscriptionModal({ onClose }) {
  return (
    <Modal onClose={onClose}>
      <div className="space-y-6 text-white">
        {/* Modal Header */}
        <div className="flex items-center justify-between border-b border-white/10 pb-4">
          <div className="flex items-center gap-2.5">
            <div className="grid size-9 place-items-center rounded-xl bg-blue-600/20 text-blue-400 border border-blue-500/30">
              <CreditCard className="size-4" />
            </div>
            <div>
              <h2 className="text-[16px] font-bold text-white">Subscription & Plan</h2>
              <p className="text-[12px] text-white/50">Manage your AgentForge developer tier</p>
            </div>
          </div>
          <button
            onClick={onClose}
            className="grid size-8 place-items-center rounded-lg text-white/40 hover:bg-white/10 hover:text-white transition-colors"
          >
            <X className="size-4" />
          </button>
        </div>

        {/* Active Plan Card */}
        <div className="rounded-2xl border border-blue-500/30 bg-blue-500/10 p-4 shadow-lg shadow-blue-500/10">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-3">
              <div className="grid size-10 place-items-center rounded-xl bg-blue-600 text-white shadow-md shadow-blue-500/30">
                <Zap className="size-5" />
              </div>
              <div>
                <div className="flex items-center gap-2">
                  <h3 className="font-bold text-[15px] text-white">Developer Edition</h3>
                  <span className="rounded-full bg-emerald-500/20 px-2.5 py-0.5 text-[10.5px] font-semibold text-emerald-400 border border-emerald-500/30">
                    Active Plan
                  </span>
                </div>
                <p className="text-[12px] text-white/60">Full local AI development suite with unlimited generation</p>
              </div>
            </div>
          </div>
        </div>

        {/* Plan Capabilities */}
        <div className="space-y-3">
          <h4 className="text-[11px] font-bold uppercase tracking-wider text-white/40">Included Features</h4>
          <div className="grid grid-cols-1 gap-2.5 sm:grid-cols-2 text-[12.5px]">
            {[
              'Unlimited local LLM code generation',
              'Qwen 2.5 Coder 14B & Llama 3.1 8B',
              'Full-Stack Next.js 16 + MongoDB engine',
              'Automated Vitest & Live E2E tests',
              'Live interactive HTML prototypes',
              'Direct AWS EC2 & Vercel deployments',
            ].map((feature, i) => (
              <div key={i} className="flex items-center gap-2 text-white/85">
                <Check className="size-4 text-emerald-400 shrink-0" />
                <span>{feature}</span>
              </div>
            ))}
          </div>
        </div>

        {/* Footer */}
        <div className="flex items-center justify-end border-t border-white/10 pt-4">
          <button
            onClick={onClose}
            className="rounded-xl bg-blue-600 px-4 py-2 text-[12.5px] font-semibold text-white shadow-lg shadow-blue-500/20 hover:bg-blue-500 transition-colors"
          >
            Got it
          </button>
        </div>
      </div>
    </Modal>
  )
}
