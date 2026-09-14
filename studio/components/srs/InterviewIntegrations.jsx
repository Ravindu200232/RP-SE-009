'use client'

import { useState } from 'react'
import { api } from '@/lib/api'
import { Button } from '../ui'

export default function InterviewIntegrations({ projectId, questions, onDone }) {
  const [answers, setAnswers] = useState({})
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  function patch(id, update) { setAnswers(prior => ({ ...prior, [id]: { ...prior[id], ...update } })) }
  async function save() {
    setBusy(true); setError('')
    try {
      await api.saveIntegrations(projectId, questions.map(q => ({ id: q.id, ...answers[q.id] })))
      setAnswers({})
      onDone()
    } catch (e) { setError(e.message) } finally { setBusy(false) }
  }
  return (
    <div className="min-h-0 flex-1 overflow-auto p-6">
      <div className="mx-auto max-w-2xl space-y-6">
        <h1 className="text-xl font-semibold">Interview · Integrations</h1>
        <p className="text-sm text-muted">Choose how this app handles email, payments and image uploads. Credentials go into this project's environment file; agent conversations receive only the configured names.</p>
        {questions.map(question => {
          const answer = answers[question.id] || {}
          const choice = question.choices.find(c => c.id === answer.choice)
          return <fieldset key={question.id} className="space-y-3 rounded-xl border border-line p-4">
            <legend className="px-2 font-semibold">{question.question || question.purpose}</legend>
            <select aria-label={question.purpose} value={answer.choice || ''} onChange={e => patch(question.id, { choice: e.target.value, values: {} })}
              className="w-full rounded-lg border border-line bg-panel2 p-2 text-sm">
              <option value="" disabled>Choose an option</option>
              {question.choices.map(option => <option key={option.id} value={option.id}>{option.label}</option>)}
            </select>
            {choice?.hint && <p className="text-xs text-muted">{choice.hint}</p>}
            {[...(question.fields || []), ...(choice?.fields || [])].map(field => <label key={field.key} className="block text-sm">
              {field.label}
              <input type={field.secret ? 'password' : 'text'} autoComplete="off" value={answer.values?.[field.key] || ''}
                onChange={e => patch(question.id, { values: { ...answer.values, [field.key]: e.target.value } })}
                placeholder={field.example} className="mt-1 block w-full rounded-lg border border-line bg-panel2 p-2" />
              {field.hint && <span className="mt-1 block text-xs text-muted">{field.hint}</span>}
            </label>)}
          </fieldset>
        })}
        {error && <p role="alert" className="text-sm text-red-400">{error}</p>}
        <Button disabled={busy || questions.some(q => !answers[q.id]?.choice)} onClick={save}>{busy ? 'Saving…' : 'Continue interview'}</Button>
      </div>
    </div>
  )
}
