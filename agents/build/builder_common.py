import json
import logging
import os
import re
import shutil
import subprocess
import textwrap
from pathlib import Path

import requests

log = logging.getLogger("builder")


def _find_npm_cmd():
    """The npm to shell out to, or None if there is not one.

    `BuilderAgent._install_deps` has always called this and it has never
    existed, so every run through `pipeline.py` — which builds a bare
    `BuilderAgent` rather than the studio's `UIBuilder` subclass — died with
    NameError the moment it reached npm install. The studio path never hit it
    because `UIBuilder._install_deps` overrides the method entirely and uses
    its own resolved `NPM_BIN`.

    The env vars are the ones the packaged Electron app sets, and are named in
    the error message this function's caller prints on failure.
    """
    explicit = os.environ.get("AGENTFORGE_NPM") or os.environ.get("NPM")
    if explicit and Path(explicit).exists():
        return [explicit]
    found = shutil.which("npm")
    return [found] if found else None

_stream_callback = None


def set_stream_callback(fn):
    global _stream_callback
    _stream_callback = fn

def _emit(token):
    if _stream_callback:
        _stream_callback(token)


_PROMPT_FALLBACK = """\
You are an expert React and Tailwind developer. Return only complete valid JSX.
Use one export default function with all logic inside it and imports first.
Only use react, react-dom, framer-motion, and imports from react-icons families.
Use real icon names, self-close void elements, and give the root a dark background.
Hoist regex and division expressions outside JSX. Do not use extra dependencies.
"""


def _load_system_prompt() -> str:
    """Load the editable generation contract, retaining safe packaged defaults."""
    prompt_path = Path(__file__).with_name("builder_prompt.md")
    try:
        prompt = prompt_path.read_text(encoding="utf-8").strip()
    except OSError as exc:
        log.warning("Builder prompt unavailable at %s: %s", prompt_path, exc)
        return _PROMPT_FALLBACK.strip()
    return prompt or _PROMPT_FALLBACK.strip()


SYSTEM_PROMPT = _load_system_prompt()


def _stream_chat(url: str, model: str, prompt: str, label: str,
                 temperature: float, timeout: int) -> str:
    """Run one framed streaming model call and return its complete text."""
    full = ""
    try:
        response = requests.post(
            url,
            json={
                "model": model,
                "messages": [
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": prompt},
                ],
                "stream": True,
                "options": {"temperature": temperature, "num_predict": 4096},
            },
            stream=True,
            timeout=timeout,
        )
        response.raise_for_status()
        _emit(f"\x00START:{label}")
        for line in response.iter_lines():
            if not line:
                continue
            try:
                chunk = json.loads(line)
            except (TypeError, ValueError):
                continue
            if not isinstance(chunk, dict):
                continue
            message = chunk.get("message", {})
            token = message.get("content", "") if isinstance(message, dict) else ""
            if token:
                full += token
                _emit(token)
            if chunk.get("done"):
                break
    finally:
        _emit("\x00END")
    return full


def _app_shell(title: str, sections: list) -> str:
    """Generate App.jsx that imports and renders all sections. Pure Python string — no fragile escaping."""
    non_navbar = [s for s in sections if s != "Navbar"]
    lines = [
        "import { motion } from 'framer-motion'",
        "import Navbar from './components/Navbar'",
    ]
    for s in non_navbar:
        lines.append(f"import {s} from './components/{s}'")
    lines += [
        "",
        "const fadeUp = { hidden:{opacity:0,y:40}, visible:{opacity:1,y:0,transition:{duration:0.65}} }",
        "",
        "export default function App() {",
        "  return (",
        "    <div className='bg-dark min-h-screen overflow-x-hidden'>",
        "      <Navbar />",
    ]
    for s in non_navbar:
        lines += [
            f"      <motion.div id='{s.lower()}' className='py-20 px-6 max-w-7xl mx-auto'",
            "        initial='hidden' whileInView='visible' viewport={{ once:true, amount:0.08 }} variants={fadeUp}>",
            f"        <{s} />",
            "      </motion.div>",
        ]
    lines += [
        "      <footer className='border-t border-white/10 py-6 text-center text-gray-500 text-sm'>",
        f"        <p>© 2024 {title}</p>",
        "      </footer>",
        "    </div>",
        "  )",
        "}",
    ]
    return "\n".join(lines) + "\n"


def _single_app_shell() -> str:
    return textwrap.dedent("""\
        import AppComponent from './components/App'
        export default function App() {
          return <div className='min-h-screen overflow-x-hidden'><AppComponent /></div>
        }
        """)


SAFE_COMPONENT = textwrap.dedent("""\
    import { motion } from 'framer-motion'
    export default function {name}() {
      return (
        <section id='{id}' className='py-20 px-6'>
          <motion.div className='max-w-4xl mx-auto text-center'
            initial={{opacity:0,y:30}} whileInView={{opacity:1,y:0}}
            transition={{duration:0.6}} viewport={{once:true}}>
            <h2 className='text-5xl font-black mb-4' style={{
              background:'linear-gradient(135deg,#6366f1,#22d3ee)',
              WebkitBackgroundClip:'text', WebkitTextFillColor:'transparent'
            }}>{name}</h2>
            <p className='text-gray-400 text-lg'>Section content goes here.</p>
          </motion.div>
        </section>
      )
    }
    """)

def _safe_component(name: str) -> str:
    return SAFE_COMPONENT.replace("{name}", name).replace("{id}", name.lower())


__all__ = [name for name in globals() if not name.startswith("__")]
