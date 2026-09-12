'use client'

import { useState } from 'react'
import { X, Mail, Lock, User, ArrowLeft, Loader2, AlertCircle } from 'lucide-react'
import { useAuthStore } from '@/lib/auth'
import { cn } from '@/lib/utils'

export default function AuthModal({ isOpen, onClose, onSuccess, initialScreen = 'methods' }) {
  const { login, signup, loading, error, clearError } = useAuthStore()

  // screen: 'methods' | 'email'
  const [screen, setScreen] = useState(initialScreen)
  // mode: 'signin' | 'signup'
  const [mode, setMode] = useState('signin')

  const [formLogin, setFormLogin] = useState('')
  const [formEmail, setFormEmail] = useState('')
  const [formPassword, setFormPassword] = useState('')
  const [formName, setFormName] = useState('')
  const [localError, setLocalError] = useState('')

  if (!isOpen) return null

  function handleClose() {
    clearError()
    setLocalError('')
    onClose?.()
  }

  async function handleSubmit(e) {
    e?.preventDefault()
    setLocalError('')
    clearError()

    if (mode === 'signin') {
      if (!formLogin.trim() || !formPassword) {
        setLocalError('Please enter your email or username and password')
        return
      }
      const res = await login(formLogin.trim(), formPassword)
      if (res.ok) {
        onSuccess?.(res.user)
        handleClose()
      }
    } else {
      if (!formLogin.trim()) {
        setLocalError('Please choose a username')
        return
      }
      if (!formEmail.trim() || !formEmail.includes('@')) {
        setLocalError('Please enter a valid email address')
        return
      }
      if (!formPassword || formPassword.length < 8) {
        setLocalError('Password must be at least 8 characters')
        return
      }
      const res = await signup(formLogin.trim(), formEmail.trim(), formPassword, formName.trim())
      if (res.ok) {
        onSuccess?.(res.user)
        handleClose()
      }
    }
  }

  function go(next) {
    clearError()
    setLocalError('')
    setMode(next)
    setScreen('email')
  }

  const activeError = localError || error

  return (
    <div className="fixed inset-0 z-[100] flex items-center justify-center bg-black/75 p-4 backdrop-blur-md animate-in fade-in duration-200">
      <div
        className="relative w-full max-w-[440px] rounded-3xl border border-white/15 bg-[#0f1422] p-7 shadow-2xl backdrop-blur-2xl transition-all"
        role="dialog"
        aria-modal="true"
      >
        {/* Close Button */}
        <button
          onClick={handleClose}
          className="absolute right-5 top-5 flex size-8 items-center justify-center rounded-xl text-white/50 hover:bg-white/10 hover:text-white transition-colors"
          aria-label="Close"
        >
          <X className="size-4" />
        </button>

        {/* Brand Logo */}
        <div className="flex flex-col items-center justify-center pt-2">
          <div className="flex items-center gap-2">
            <div className="flex size-7 shrink-0 items-center justify-center rounded-lg bg-blue-500/20 ring-1 ring-blue-500/30">
              <img src="/__agentforge/agentforge-mark.png" alt="AgentForge" className="size-5 object-contain" />
            </div>
            <span className="font-display text-[22px] font-bold italic tracking-tight text-white">
              agentforge<span className="text-blue-500 font-normal">.ai</span>
            </span>
          </div>
        </div>

        {/* Error Alert */}
        {activeError && (
          <div className="mt-4 flex items-center gap-2 rounded-xl border border-rose-500/30 bg-rose-500/10 px-3.5 py-2.5 text-[12.5px] text-rose-300">
            <AlertCircle className="size-4 shrink-0" />
            <span>{activeError}</span>
          </div>
        )}

        {/* Screen 1: Method Selection (Matching media_1789153674897.png) */}
        {screen === 'methods' && (
          <div className="mt-5 text-center">
            <p className="px-3 text-[13px] leading-relaxed text-white/70">
              Sign in to reach your own projects, specifications and deployments.
              Each account sees only its own.
            </p>

            <div className="mt-6 flex flex-col gap-2.5">
              {/* Email & Password */}
              <button
                type="button"
                onClick={() => go('signin')}
                className="flex h-11 w-full items-center justify-center gap-3 rounded-xl border border-white/10 bg-white/[.04] px-4 font-display text-[13px] font-medium text-white shadow-sm transition-all hover:border-white/20 hover:bg-white/[.08]"
              >
                <Mail className="size-4 text-white/70" />
                <span>Sign in with email and password</span>
              </button>

              <button
                type="button"
                onClick={() => go('signup')}
                className="flex h-11 w-full items-center justify-center gap-3 rounded-xl border border-white/10 bg-white/[.04] px-4 font-display text-[13px] font-medium text-white shadow-sm transition-all hover:border-white/20 hover:bg-white/[.08]"
              >
                <User className="size-4 text-white/70" />
                <span>Create an account</span>
              </button>
            </div>

            <p className="mt-6 text-[11px] text-white/45">
              By signing in, you accept the{' '}
              <a href="#" className="text-white/70 underline hover:text-white">Terms of Service</a>{' '}
              and acknowledge our{' '}
              <a href="#" className="text-white/70 underline hover:text-white">Privacy Policy</a>.
            </p>
          </div>
        )}

        {/* Screen 2: Credentials Form (Matching media_1789153671638.png) */}
        {screen === 'email' && (
          <div className="mt-4">
            <h2 className="text-center font-display text-[18px] font-bold text-white">
              {mode === 'signin' ? 'Sign in' : 'Create an account'}
            </h2>

            <form onSubmit={handleSubmit} className="mt-5 space-y-3.5">
              {mode === 'signup' && (
                <div>
                  <label className="mb-1 block text-[11.5px] font-medium text-white/70">
                    Full name
                  </label>
                  <div className="relative flex items-center">
                    <User className="pointer-events-none absolute left-3 size-4 text-white/40" />
                    <input
                      type="text"
                      value={formName}
                      onChange={e => setFormName(e.target.value)}
                      placeholder="Ravindu"
                      className="h-10 w-full rounded-xl border border-white/15 bg-white/[.04] pl-9 pr-3 text-[13px] text-white placeholder:text-white/30 focus:border-blue-500 focus:outline-none"
                    />
                  </div>
                </div>
              )}

              <div>
                <label className="mb-1 block text-[11.5px] font-medium text-white/70">
                  {mode === 'signup' ? 'Username *' : 'Email or username *'}
                </label>
                <div className="relative flex items-center">
                  <User className="pointer-events-none absolute left-3 size-4 text-white/40" />
                  <input
                    type="text"
                    required
                    autoFocus
                    value={formLogin}
                    onChange={e => setFormLogin(e.target.value)}
                    placeholder={mode === 'signup' ? 'ravindu2232' : 'Enter email or username'}
                    className="h-10 w-full rounded-xl border border-white/15 bg-white/[.04] pl-9 pr-3 text-[13px] text-white placeholder:text-white/30 focus:border-blue-500 focus:outline-none"
                  />
                </div>
              </div>

              {mode === 'signup' && (
                <div>
                  <label className="mb-1 block text-[11.5px] font-medium text-white/70">
                    Email address *
                  </label>
                  <div className="relative flex items-center">
                    <Mail className="pointer-events-none absolute left-3 size-4 text-white/40" />
                    <input
                      type="email"
                      required
                      value={formEmail}
                      onChange={e => setFormEmail(e.target.value)}
                      placeholder="user@example.com"
                      className="h-10 w-full rounded-xl border border-white/15 bg-white/[.04] pl-9 pr-3 text-[13px] text-white placeholder:text-white/30 focus:border-blue-500 focus:outline-none"
                    />
                  </div>
                </div>
              )}

              <div>
                <div className="mb-1 flex items-center justify-between">
                  <label className="text-[11.5px] font-medium text-white/70">
                    Password *
                  </label>
                  {mode === 'signin' && (
                    <button
                      type="button"
                      onClick={() => setLocalError('Please contact support to reset your password.')}
                      className="text-[11px] text-blue-400 hover:underline"
                    >
                      Forgot password?
                    </button>
                  )}
                </div>
                <div className="relative flex items-center">
                  <Lock className="pointer-events-none absolute left-3 size-4 text-white/40" />
                  <input
                    type="password"
                    required
                    value={formPassword}
                    onChange={e => setFormPassword(e.target.value)}
                    placeholder="••••••••"
                    className="h-10 w-full rounded-xl border border-white/15 bg-white/[.04] pl-9 pr-3 text-[13px] text-white placeholder:text-white/30 focus:border-blue-500 focus:outline-none"
                  />
                </div>
              </div>

              <div className="pt-2 flex flex-col gap-2">
                <button
                  type="submit"
                  disabled={loading}
                  className="flex h-11 w-full items-center justify-center gap-2 rounded-xl bg-blue-600 font-display text-[13px] font-semibold text-white shadow-lg shadow-blue-500/25 transition-all hover:bg-blue-500 active:scale-95 disabled:pointer-events-none disabled:opacity-50"
                >
                  {loading && <Loader2 className="size-4 animate-spin" />}
                  <span>{mode === 'signin' ? 'Sign in' : 'Create account'}</span>
                </button>

                <button
                  type="button"
                  onClick={() => { setScreen('methods'); clearError(); setLocalError('') }}
                  className="flex h-10 w-full items-center justify-center gap-2 rounded-xl border border-white/10 bg-white/[.04] text-[13px] font-medium text-white/75 hover:bg-white/[.08] hover:text-white transition-all"
                >
                  <ArrowLeft className="size-3.5" />
                  <span>Back</span>
                </button>
              </div>
            </form>

            <div className="mt-5 text-center text-[12.5px] text-white/60">
              {mode === 'signin' ? (
                <>
                  Don't have an account?{' '}
                  <button
                    onClick={() => { setMode('signup'); clearError(); setLocalError('') }}
                    className="font-semibold text-blue-400 hover:underline"
                  >
                    Sign up
                  </button>
                </>
              ) : (
                <>
                  Already have an account?{' '}
                  <button
                    onClick={() => { setMode('signin'); clearError(); setLocalError('') }}
                    className="font-semibold text-blue-400 hover:underline"
                  >
                    Sign in
                  </button>
                </>
              )}
            </div>

            <p className="mt-5 text-center text-[11px] text-white/45">
              By signing in, you accept the{' '}
              <a href="#" className="text-white/70 underline hover:text-white">Terms of Service</a>{' '}
              and acknowledge our{' '}
              <a href="#" className="text-white/70 underline hover:text-white">Privacy Policy</a>.
            </p>
          </div>
        )}
      </div>
    </div>
  )
}
