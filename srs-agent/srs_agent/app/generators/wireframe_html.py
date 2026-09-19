"""The wireframe page, as a self-contained HTML document.

The shell is ours and the content is the model's. That split is deliberate: the
design system and the browser chrome are the same on every page of every
product, so asking a model to reproduce them each time spends most of its
output budget on boilerplate it will get subtly wrong - a different border
width here, a heavier rule there - and eleven pages of a specification come
back looking like eleven different tools drew them.

The page is the wireframe and nothing else. There is no blueprint grid, no
annotation layer and no toggle bar over it: a reviewer opening a screen should
see the screen, not a tool's chrome sitting on top of it.

Written once here, the model is left with the only part that differs: what is
actually on the page.

No SVG anywhere. The crossed image placeholder is two CSS gradients, which holds
a 2px stroke at any box size - the thing `vector-effect="non-scaling-stroke"`
was needed for in SVG - and means the document has no vector markup to get
wrong.
"""
from __future__ import annotations

# Named so the model can ask for them by name instead of restating the styling.
DESIGN_SYSTEM = """
  :root{ --ink:#000; --paper:#fff; --fill:#F3F4F6; --fill2:#E5E7EB; --faint:#D1D5DB; }
  *{ box-sizing:border-box; }
  body{ background:var(--fill); color:var(--ink);
        font-family:'Comic Neue','Balsamiq Sans','Comic Sans MS',ui-monospace,Menlo,Consolas,monospace; }

  .wf-box{ border:2px solid var(--ink); background:var(--paper); border-radius:2px; }
  .wf-box-thin{ border:1px solid var(--ink); background:var(--paper); border-radius:2px; }
  .wf-fill{ background:var(--fill); }
  .wf-fill-2{ background:var(--fill2); }

  /* The crossed image placeholder, in CSS. Corner to corner, 2px at any size. */
  .wf-img{ position:relative; border:2px solid var(--ink); background-color:var(--fill);
    background-image:
      linear-gradient(to top right, transparent calc(50% - 1px), var(--ink) calc(50% - 1px),
                      var(--ink) calc(50% + 1px), transparent calc(50% + 1px)),
      linear-gradient(to bottom right, transparent calc(50% - 1px), var(--ink) calc(50% - 1px),
                      var(--ink) calc(50% + 1px), transparent calc(50% + 1px));
    display:flex; align-items:center; justify-content:center; }
  .wf-img > .wf-label{ background:var(--paper); border:1px solid var(--ink);
    padding:2px 8px; font-size:11px; font-family:ui-monospace,Menlo,monospace; }

  .wf-btn{ display:inline-flex; align-items:center; justify-content:center;
    border:1.5px solid var(--ink); background:var(--paper); color:var(--ink);
    border-radius:6px; padding:10px 20px; font-family:inherit; font-size:14px;
    font-weight:600; cursor:pointer; white-space:nowrap; }
  .wf-btn:active{ background:var(--fill); }
  .wf-btn-fill{ background:var(--ink); color:var(--paper); }
  .wf-btn-sm{ padding:6px 12px; font-size:12px; }

  .wf-input{ border:1.5px solid var(--ink); background:var(--paper); border-radius:2px;
    padding:10px 12px; font-family:inherit; font-size:14px; color:var(--ink); width:100%; }
  .wf-input::placeholder{ color:#71717A; font-style:italic; }
  .wf-input:focus{ outline:2px solid var(--ink); outline-offset:1px; }

  .wf-label-sm{ display:block; font-size:11px; font-weight:700; text-transform:uppercase;
    letter-spacing:.06em; margin-bottom:4px; font-family:ui-monospace,Menlo,monospace; }

  /* Skeleton copy. A wireframe says "text goes here" better than lorem does. */
  .sk{ display:block; height:10px; margin-bottom:8px; background:var(--fill);
    border:1px solid var(--faint); border-radius:2px; }
  .sk-thin{ height:7px; }

  /* A small dashed badge: a status, a count, a pill on a card. It is content,
     not commentary - there is no annotation layer over these pages. */
  .wf-tag{ font-family:ui-monospace,Menlo,monospace; font-size:10px; font-weight:700;
    letter-spacing:1px; border:1px dashed var(--ink); background:var(--paper);
    padding:2px 8px; border-radius:2px; text-transform:uppercase; white-space:nowrap; }

  .browser{ border:2px solid var(--ink); border-radius:8px; background:var(--paper); overflow:hidden; }
  .chrome-bar{ background:var(--fill2); border-bottom:2px solid var(--ink); }

  ::-webkit-scrollbar{ width:10px; height:10px; }
  ::-webkit-scrollbar-track{ background:var(--fill); }
  ::-webkit-scrollbar-thumb{ background:#9CA3AF; border:1px solid var(--ink); }
"""

SHELL = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8" />
<meta name="viewport" content="width=device-width, initial-scale=1.0" />
<title>[ __TITLE__ — Wireframe ]</title>
<script src="https://cdn.tailwindcss.com"></script>
<style>__CSS__</style>
</head>
<body class="antialiased min-h-screen">

<div class="max-w-6xl mx-auto py-8 px-4">
  <div class="browser relative">
    <div class="chrome-bar px-4 py-2 flex items-center gap-3">
      <div class="flex items-center gap-2">
        <span class="w-3 h-3 rounded-full border-2 border-black inline-block"></span>
        <span class="w-3 h-3 rounded-full border-2 border-black inline-block"></span>
        <span class="w-3 h-3 rounded-full border-2 border-black inline-block"></span>
      </div>
      <div class="flex items-center gap-1 ml-2">
        <button class="wf-btn wf-btn-sm" style="border-radius:999px" type="button">&#8592;</button>
        <button class="wf-btn wf-btn-sm opacity-40" style="border-radius:999px" type="button">&#8594;</button>
      </div>
      <div class="flex-1 flex items-center wf-box px-4 py-1.5 font-mono text-xs" style="border-radius:999px">
        <span class="text-zinc-500 mr-2">&#128274;</span><span>__URL__</span>
      </div>
      <button class="wf-btn wf-btn-sm" style="border-radius:999px" type="button">&#8635;</button>
    </div>

    <div class="bg-white">
__BODY__
    </div>
  </div>

  <div class="mt-6 wf-box-thin p-4 flex flex-wrap items-center gap-x-6 gap-y-2 text-xs font-mono">
    <span class="font-bold uppercase tracking-wider">Legend:</span>
    <span class="flex items-center gap-2"><span class="wf-img" style="width:18px;height:18px"></span> Image placeholder</span>
    <span class="wf-box-thin px-2 py-0.5">Wireframe button</span>
    <span class="flex items-center gap-2"><span class="sk" style="width:48px;margin:0"></span> Body copy</span>
  </div>
</div>

</body>
</html>
"""


def page_html(title: str, url: str, body: str) -> str:
    """One finished wireframe document: our shell around the model's sections."""
    return (SHELL
            .replace("__CSS__", DESIGN_SYSTEM)
            .replace("__TITLE__", str(title or "Page"))
            .replace("__URL__", str(url or "https://example.app/"))
            .replace("__BODY__", str(body or "")))
