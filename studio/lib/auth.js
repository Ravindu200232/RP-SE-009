'use client'

import { create } from 'zustand'
import { api, setAuthToken, getAuthToken } from './api'

export const useAuthStore = create((set, get) => ({
  user: null,
  token: '',
  loading: true,
  error: '',

  init: async () => {
    const token = getAuthToken()
    if (!token) {
      set({ user: null, token: '', loading: false })
      return
    }
    set({ token, loading: true })
    try {
      const res = await api.auth.me()
      if (res?.ok && res?.user) {
        set({ user: res.user, loading: false })
      } else {
        setAuthToken('')
        set({ user: null, token: '', loading: false })
      }
    } catch {
      setAuthToken('')
      set({ user: null, token: '', loading: false })
    }
  },

  login: async (login, password) => {
    set({ loading: true, error: '' })
    try {
      const res = await api.auth.login({ login, password })
      if (res?.ok && res?.token) {
        setAuthToken(res.token)
        set({ user: res.user, token: res.token, loading: false, error: '' })
        return { ok: true, user: res.user }
      }
      const err = res?.error || 'Login failed'
      set({ loading: false, error: err })
      return { ok: false, error: err }
    } catch (e) {
      const err = e?.message || 'Login failed'
      set({ loading: false, error: err })
      return { ok: false, error: err }
    }
  },

  signup: async (username, email, password, name) => {
    set({ loading: true, error: '' })
    try {
      const res = await api.auth.signup({ username, email, password, name })
      if (res?.ok && res?.token) {
        setAuthToken(res.token)
        set({ user: res.user, token: res.token, loading: false, error: '' })
        return { ok: true, user: res.user }
      }
      const err = res?.error || 'Registration failed'
      set({ loading: false, error: err })
      return { ok: false, error: err }
    } catch (e) {
      const err = e?.message || 'Registration failed'
      set({ loading: false, error: err })
      return { ok: false, error: err }
    }
  },

  logout: async () => {
    try {
      await api.auth.logout().catch(() => {})
    } finally {
      setAuthToken('')
      set({ user: null, token: '', error: '' })
    }
  },

  clearError: () => set({ error: '' }),
}))
