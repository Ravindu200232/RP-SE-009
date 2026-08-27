import { useEffect, useState } from 'react'

export default function Navbar() {
  const [scrolled, setScrolled] = useState(false)
  const [open, setOpen] = useState(false)
  useEffect(() => {
    const update = () => setScrolled(window.scrollY > 50)
    window.addEventListener('scroll', update)
    return () => window.removeEventListener('scroll', update)
  }, [])
  const smoothScroll = (event) => {
    event.preventDefault()
    const id = event.target.getAttribute('href')?.slice(1)
    document.getElementById(id)?.scrollIntoView({ behavior: 'smooth' })
    setOpen(false)
  }
  const background = scrolled
    ? 'backdrop-blur-xl bg-black/60 border-b border-white/10'
    : 'bg-transparent'
  return (
    <nav className={`fixed top-0 w-full z-50 transition-all duration-300 ${background}`}>
      <div className="max-w-7xl mx-auto px-6 py-4 flex justify-between items-center">
        <a href="#" className="text-xl font-black gradient-text">__TITLE__</a>
        <div className="hidden md:flex gap-8">
          __DESKTOP_LINKS__
        </div>
        <button
          className="md:hidden text-white text-xl"
          onClick={() => setOpen(!open)}
        >
          ☰
        </button>
      </div>
      {open && (
        <div className="md:hidden bg-black/90 px-6 py-4 flex flex-col gap-3">
          __MOBILE_LINKS__
        </div>
      )}
    </nav>
  )
}
