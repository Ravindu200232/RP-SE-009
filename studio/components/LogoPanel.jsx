'use client'

import { useEffect, useRef, useState } from 'react'
import { Loader2, Upload } from 'lucide-react'
import { api } from '@/lib/api'
import { Button, Modal } from './ui'

const ACCEPT_LOGO = '.png,.jpg,.jpeg,.webp,.gif,.bmp,image/*'

export default function LogoPanel({ idea, model, onAccept, onSkip }) {
  const [prompt, setPrompt] = useState('')
  const [state, setState] = useState('writing')
  const [img, setImg] = useState(null)
  const [file, setFile] = useState('')
  const [error, setError] = useState('')
  const [own, setOwn] = useState('')
  const picker = useRef(null)

  const [waited, setWaited] = useState(0)

  useEffect(() => {
    let alive = true
    api.logoPrompt(idea, model)
      .then(r => {
        if (!alive) return
        setPrompt(r.prompt || idea.slice(0, 90))
        setState('ready')
      })
      .catch(e => { if (alive) { setError(e.message); setState('ready') } })
    return () => { alive = false }
  }, [idea, model])

  async function draw() {
    setState('drawing')
    setError('')
    setWaited(0)
    try {
      const r = await api.image(
        { prompt, name: 'logo', aspect: 'square', force: true },
        { onWait: setWaited })
      setImg(r.data_uri || '')
      setFile(r.file || '')
      setOwn('')
    } catch (e) {
      setError(e.message)
    }
    setState('ready')
  }

  async function upload(chosen) {
    if (!chosen) return
    setState('uploading')
    setError('')
    try {
      // Answers in the same shape `draw` does, so everything below this point
      // — the preview, Accept, and the build that copies the file to
      // public/logo.png — cannot tell the two apart.
      const r = await api.imageUpload(chosen, { name: 'logo' })
      setImg(r.data_uri || '')
      setFile(r.file || '')
      setOwn(chosen.name || 'your file')
    } catch (e) {
      setError(e.message)
    }
    setState('ready')
  }

  return (
    <Modal onClose={onSkip}>
      <header className="mb-3">
        <h3 className="font-display text-[15px] font-bold text-ink">A logo first</h3>
        <p className="mt-0.5 text-[11.5px] text-muted">
          Edit the prompt until the mark is right — or upload the one you
          already have — then build the app around it.
        </p>
      </header>

      <textarea value={prompt} rows={3} disabled={state === 'writing'}
                placeholder={state === 'writing' ? 'Writing a prompt…' : ''}
                onChange={e => setPrompt(e.target.value)}
                className="w-full resize-y rounded-ctl border border-line bg-bg p-2.5
                           text-[11.5px] leading-relaxed text-ink outline-none
                           focus:border-accent/60 disabled:opacity-60" />

      <div className="mt-3 grid h-[240px] place-items-center overflow-hidden
                      rounded-panel border border-dashed border-line bg-bg">
        {state === 'drawing'
          ? <span className="flex flex-col items-center gap-1.5 text-[12px] text-muted">
              <span className="flex items-center gap-2">
                <Loader2 className="size-4 animate-spin" /> Drawing…
              </span>
              <span className="font-mono text-[10.5px] text-muted2">
                {waited ? `${Math.round(waited)}s` : ''}
                {waited > 75 ? ' · a cold model load takes the first minute' : ''}
              </span>
            </span>
          : state === 'uploading'
            ? <span className="flex items-center gap-2 text-[12px] text-muted">
                <Loader2 className="size-4 animate-spin" /> Reading your file…
              </span>
            : img
              ? <img src={img} alt={own ? `the logo you uploaded, ${own}` : 'the generated logo'}
                     className="max-h-full max-w-full" />
              // `file` without `img` must not read as "nothing here": the panel
              // would then deny the upload in the box and confirm it in the
              // line underneath, with Accept live.
              : file
                ? <span className="px-6 text-center text-[12px] text-muted">
                    Saved, but it could not be shown here. Accept only if you
                    are sure of the file.
                  </span>
                : <span className="text-[12px] text-muted2">
                    Nothing drawn yet — generate one, or upload your own.
                  </span>}
      </div>

      {own && !error && (
        <p className="mt-2 text-[11.5px] text-muted">
          Using <b className="font-medium text-ink">{own}</b> — saved as a PNG.
        </p>
      )}
      {error && <p className="mt-2 text-[11.5px] text-bad">{error}</p>}

      <input ref={picker} type="file" hidden accept={ACCEPT_LOGO}
             onChange={e => {
               const chosen = e.target.files?.[0]
               e.target.value = ''   // so re-picking the same file fires again
               upload(chosen)
             }} />

      <footer className="mt-4 flex items-center gap-2">
        <Button variant="outline" size="lg" onClick={draw}
                disabled={state !== 'ready' || !prompt.trim()}>
          {img ? 'Try another' : 'Generate'}
        </Button>
        {/* Not gated on `state === 'ready'` like Generate is: uploading needs
            no prompt, so it should not wait behind the model writing one. */}
        <Button variant="outline" size="lg"
                disabled={state === 'drawing' || state === 'uploading'}
                onClick={() => picker.current?.click()}
                title="Use a logo you already have, instead of drawing one">
          <Upload className="size-3.5" /> Upload
        </Button>
        <Button variant="solid" size="lg" disabled={!file}
                onClick={() => onAccept(file)}>
          Accept and build
        </Button>
        <span className="flex-1" />
        <Button size="lg" onClick={onSkip}>Skip</Button>
      </footer>
    </Modal>
  )
}
