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
      if (!formPassword || formPassword.length < 6) {
        setLocalError('Password must be at least 6 characters')
        return
      }
      const res = await signup(formLogin.trim(), formEmail.trim(), formPassword, formName.trim())
      if (res.ok) {
        onSuccess?.(res.user)
        handleClose()
      }
    }
  }

  async function handleSocial(provider) {
    // Quick demo social login
    setLocalError('')
    clearError()
    const demoUser = `${provider.toLowerCase()}_user`
    const demoEmail = `${demoUser}@agentforge.ai`
    const res = await login(demoUser, 'password123')
    if (res.ok) {
      onSuccess?.(res.user)
      handleClose()
    } else {
      const regRes = await signup(demoUser, demoEmail, 'password123', `${provider} User`)
      if (regRes.ok) {
        onSuccess?.(regRes.user)
        handleClose()
      }
    }
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
              To use AgentForge you must log into an existing account or create one using one of the options below
            </p>

            <div className="mt-6 flex flex-col gap-2.5">
              {/* Google */}
              <button
                type="button"
                onClick={() => handleSocial('Google')}
                className="flex h-11 w-full items-center justify-center gap-3 rounded-xl border border-white/10 bg-white/[.04] px-4 font-display text-[13px] font-medium text-white shadow-sm transition-all hover:border-white/20 hover:bg-white/[.08]"
              >
                <svg className="size-4" viewBox="0 0 24 24">
                  <path fill="#EA4335" d="M12 5c1.6 0 3 .6 4.1 1.7l3.1-3.1C17.3 1.8 14.8 1 12 1 7.5 1 3.7 3.6 1.9 7.3l3.7 2.9C6.5 7.3 9 5 12 5z" />
                  <path fill="#4285F4" d="M23.5 12.3c0-.8-.1-1.6-.2-2.3H12v4.5h6.5c-.3 1.5-1.1 2.8-2.4 3.7l3.7 2.9c2.2-2 3.7-5 3.7-8.8z" />
                  <path fill="#FBBC05" d="M5.6 14.8c-.2-.7-.4-1.5-.4-2.8s.2-2.1.4-2.8L1.9 6.3C.7 8.7 0 10.3 0 12s.7 3.3 1.9 5.7l3.7-2.9z" />
                  <path fill="#34A853" d="M12 23c3.2 0 6-1.1 8-3l-3.7-2.9c-1.1.7-2.5 1.2-4.3 1.2-3 0-5.5-2.3-6.4-5.2L1.9 16c1.8 3.7 5.6 7 10.1 7z" />
                </svg>
                <span>Sign in with Google</span>
              </button>

              {/* GitHub */}
              <button
                type="button"
                onClick={() => handleSocial('GitHub')}
                className="flex h-11 w-full items-center justify-center gap-3 rounded-xl border border-white/10 bg-white/[.04] px-4 font-display text-[13px] font-medium text-white shadow-sm transition-all hover:border-white/20 hover:bg-white/[.08]"
              >
                <svg className="size-4 fill-current" viewBox="0 0 24 24">
                  <path d="M12 0C5.37 0 0 5.37 0 12c0 5.31 3.435 9.795 8.205 11.385.6.105.825-.255.825-.57 0-.285-.015-1.23-.015-2.235-3.015.555-3.795-.735-4.035-1.41-.135-.345-.72-1.41-1.23-1.695-.42-.225-1.02-.78-.015-.795.945-.015 1.62.87 1.845 1.23 1.08 1.815 2.805 1.305 3.495.99.105-.78.42-1.305.765-1.605-2.67-.3-5.46-1.335-5.46-5.925 0-1.305.465-2.385 1.23-3.225-.12-.3-.54-1.53.12-3.18 0 0 1.005-.315 3.3 1.23.96-.27 1.98-.405 3-.405s2.04.135 3 .405c2.295-1.56 3.3-1.23 3.3-1.23.66 1.65.24 2.88.12 3.18.765.84 1.23 1.905 1.23 3.225 0 4.605-2.805 5.625-5.475 5.925.435.375.81 1.095.81 2.22 0 1.605-.015 2.895-.015 3.3 0 .315.225.69.825.57A12.02 12.02 0 0024 12c0-6.63-5.37-12-12-12z" />
                </svg>
                <span>Sign in with GitHub</span>
              </button>

              {/* Email & Password */}
              <button
                type="button"
                onClick={() => { clearError(); setLocalError(''); setScreen('email') }}
                className="flex h-11 w-full items-center justify-center gap-3 rounded-xl border border-white/10 bg-white/[.04] px-4 font-display text-[13px] font-medium text-white shadow-sm transition-all hover:border-white/20 hover:bg-white/[.08]"
              >
                <Mail className="size-4 text-white/70" />
                <span>Sign in with email and password</span>
              </button>

              {/* SSO */}
              <button
                type="button"
                onClick={() => { clearError(); setLocalError(''); setScreen('email') }}
                className="flex h-11 w-full items-center justify-center gap-3 rounded-xl border border-white/10 bg-white/[.04] px-4 font-display text-[13px] font-medium text-white shadow-sm transition-all hover:border-white/20 hover:bg-white/[.08]"
              >
                <span>Sign in with SSO</span>
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
