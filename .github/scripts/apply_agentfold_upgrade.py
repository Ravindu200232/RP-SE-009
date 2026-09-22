from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def replace_once(text: str, old: str, new: str, label: str) -> str:
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"{label}: expected one exact match, found {count}")
    return text.replace(old, new, 1)


def replace_regex(text: str, pattern: str, new: str, label: str, flags: int = re.S) -> str:
    out, count = re.subn(pattern, new, text, count=1, flags=flags)
    if count != 1:
        raise RuntimeError(f"{label}: expected one regex match, found {count}")
    return out


def patch_design_customize() -> None:
    path = ROOT / "studio" / "components" / "DesignCustomize.jsx"
    text = path.read_text(encoding="utf-8")

    text = replace_once(
        text,
        "import { Button, Input, Modal, TextArea } from './ui'\n",
        "import { Button, Input, Modal, TextArea } from './ui'\n"
        "import AdvancedDesignCustomize, { advancedCustomizationDirection } from './AdvancedDesignCustomize'\n",
        "advanced customizer import",
    )

    text = replace_regex(
        text,
        r"\nconst FIDELITY_OPTIONS = \[.*?\n\]\n",
        "\n",
        "remove wireframe fidelity selector constants",
    )

    text = replace_once(
        text,
        "  appearance: '', border: '', shadow: '', icons: '', width: '', nav: '', motion: '',\n"
        "  wireframeFidelity: 'AI Polished',\n",
        "  appearance: '', border: '', shadow: '', icons: '', width: '', nav: '', motion: '',\n"
        "  advanced: {},\n",
        "blank state",
    )

    compose = r'''function composeDirection(state, theme) {
  const parts = [
    'Approved wireframe HTML is the mandatory layout source. Preserve its page structure, section order, controls, actions, and spatial hierarchy. Apply visual styling without redesigning the approved information architecture.',
  ]

  // Theme mode and custom mode are intentionally mutually exclusive. A theme
  // is a complete design system; custom controls are a different design system.
  if (theme && !state.custom) {
    parts.unshift(`Design theme: ${theme.name} (design-theme:${theme.slug}). ${theme.description}`)
    return parts.join('\n')
  }

  if (!state.custom) {
    parts.unshift('No preset theme selected. Derive the visual language from the approved product requirements and wireframes.')
    return parts.join('\n')
  }

  const tokens = tokenLines(state, null)
  if (tokens.length) parts.push(`Colors: ${tokens.join(', ')}.`)
  const fonts = [state.headingFont && `headings ${state.headingFont}`,
                 state.bodyFont && `body ${state.bodyFont}`].filter(Boolean)
  if (fonts.length) parts.push(`Typography: ${fonts.join(', ')}.`)
  parts.push(`Button radius: ${state.radius}. Spacing: ${state.density}.`)

  const chosen = [
    state.appearance && `Appearance: ${state.appearance}.`,
    state.border && `Borders: ${state.border.toLowerCase()}.`,
    state.shadow && `Shadows: ${state.shadow.toLowerCase()}.`,
    state.icons && `Icons: ${state.icons.toLowerCase()}.`,
    state.width && `Content width: ${state.width.toLowerCase()}.`,
    state.nav && `Navigation: ${state.nav.toLowerCase()}.`,
    state.motion && `Motion: ${state.motion.toLowerCase()}.`,
  ].filter(Boolean)
  if (chosen.length) parts.push(chosen.join(' '))

  const advanced = advancedCustomizationDirection(state.advanced || {})
  if (advanced) parts.push(advanced)
  if (state.direction.trim()) parts.push(state.direction.trim())
  return parts.join('\n')
}
'''
    text = replace_regex(
        text,
        r"function composeDirection\(state, theme\) \{.*?\n\}\n\n/\*\* A portable",
        compose + "\n/** A portable",
        "compose direction",
    )

    design_spec = r'''function designSpecFor(state, theme) {
  const mode = theme && !state.custom ? 'theme' : state.custom ? 'custom' : 'product'
  const isCustom = mode === 'custom'
  return {
    mode,
    theme: { slug: mode === 'theme' ? state.slug || '' : '', name: mode === 'theme' ? theme?.name || '' : '' },
    colors: isCustom ? { ...state.colors, button: state.button || '' } : {},
    typography: isCustom
      ? { heading_font: state.headingFont || '', body_font: state.bodyFont || '' }
      : { heading_font: '', body_font: '' },
    layout: isCustom ? {
      density: state.density || '', radius: state.radius || '', appearance: state.appearance || '',
      border: state.border || '', shadow: state.shadow || '', icons: state.icons || '',
      width: state.width || '', navigation: state.nav || '',
    } : {},
    motion: isCustom ? state.motion || '' : '',
    advanced: isCustom ? state.advanced || {} : {},
    direction: isCustom ? state.direction.trim() : '',
    wireframe_source: 'approved-html-required',
  }
}

function stateFromDesignSpec(spec) {
  if (!spec || typeof spec !== 'object') return null
  const theme = spec.theme || {}, colors = spec.colors || {}, type = spec.typography || {}, layout = spec.layout || {}
  const mode = spec.mode || (theme.slug ? 'theme' : 'product')
  return {
    slug: mode === 'theme' ? theme.slug || '' : '',
    custom: mode === 'custom' || spec.custom === true,
    colors: mode === 'custom' ? colors : {}, button: mode === 'custom' ? colors.button || '' : '',
    headingFont: mode === 'custom' ? type.heading_font || '' : '',
    bodyFont: mode === 'custom' ? type.body_font || '' : '',
    density: layout.density || BLANK.density, radius: layout.radius || BLANK.radius,
    appearance: layout.appearance || '', border: layout.border || '', shadow: layout.shadow || '',
    icons: layout.icons || '', width: layout.width || '', nav: layout.navigation || '',
    motion: spec.motion || '', advanced: spec.advanced || {},
    direction: mode === 'custom' ? spec.direction || '' : '',
  }
}
'''
    text = replace_regex(
        text,
        r"function designSpecFor\(state, theme\) \{.*?\n\}\n\nfunction stateFromDesignSpec\(spec\) \{.*?\n\}\n",
        design_spec,
        "design spec serialization",
    )

    # This effect was accidentally nested inside SiteImages and referenced the
    # parent component's setState. Remove it here and restore it in the correct
    # component below.
    text = replace_regex(
        text,
        r"\n  // A confirmed design no longer belongs only to the browser that picked it\..*?\n  \}, \[projectId\]\)\n",
        "\n",
        "remove misplaced design-spec restore effect",
    )

    restore_effect = r'''

  // Server-approved design state wins over a browser-local draft so the same
  // SRS produces the same prototype on another machine.
  useEffect(() => {
    if (!projectId) return
    let active = true
    api.designSpec(projectId)
      .then(answer => {
        const restored = stateFromDesignSpec(answer?.current?.spec)
        if (!active || !restored) return
        setState(previous => ({ ...previous, ...restored, colors: restored.colors || {}, advanced: restored.advanced || {} }))
        if (restored.headingFont) loadGoogleFont(restored.headingFont)
        if (restored.bodyFont) loadGoogleFont(restored.bodyFont)
      })
      .catch(() => {})
    return () => { active = false }
  }, [projectId])
'''
    text = replace_once(
        text,
        "  }, [projectId])\n\n  function save(patch) {",
        "  }, [projectId])" + restore_effect + "\n  function save(patch) {",
        "restore design spec effect in parent",
    )

    choose = r'''  function choose(picked) {
    // Choosing a complete theme exits custom mode and removes every custom
    // override so the two systems can never silently stack.
    save({
      slug: picked.slug,
      custom: false,
      colors: {}, button: '', headingFont: '', bodyFont: '',
      density: BLANK.density, radius: BLANK.radius,
      appearance: '', border: '', shadow: '', icons: '', width: '', nav: '', motion: '',
      advanced: {}, direction: '',
    })
    setPreview(null)
  }
'''
    text = replace_regex(
        text,
        r"  function choose\(picked\) \{.*?\n  \}\n\n  /\*\*",
        choose + "\n  /**",
        "theme choose mode",
    )

    text = replace_once(
        text,
        "            value={query}\n            onChange={e => setQuery(e.target.value)}\n",
        "            value={query}\n            disabled={state.custom}\n            onChange={e => setQuery(e.target.value)}\n",
        "disable theme search in custom mode",
    )

    text = replace_once(
        text,
        "        <div className=\"mt-4 grid max-h-[42vh] grid-cols-2 gap-3 overflow-y-auto pr-1 sm:grid-cols-3 lg:grid-cols-4\">",
        "        <div className={`mt-4 grid max-h-[42vh] grid-cols-2 gap-3 overflow-y-auto pr-1 sm:grid-cols-3 lg:grid-cols-4 ${state.custom ? 'pointer-events-none opacity-40 grayscale-[25%]' : ''}`}",
        "lock theme grid in custom mode",
    )

    customization_section = r'''        {/* Customization Section */}
        <div className="mt-6 rounded-xl border border-line bg-panel2 p-5">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <div>
              <p className="text-sm font-medium">
                {state.custom
                  ? 'Custom design mode — theme picker is locked'
                  : theme
                    ? <>Theme mode: <span className="text-accent">{theme.name}</span></>
                    : 'No theme selected — product requirements + approved wireframes drive the design'}
              </p>
              <p className="mt-1 text-[11px] text-muted2">
                Theme and custom design are mutually exclusive. Approved wireframe HTML is always the layout source.
              </p>
            </div>
            <button
              type="button"
              disabled={Boolean(theme)}
              onClick={() => {
                if (theme) return
                save({ custom: !state.custom, slug: '' })
              }}
              className="text-xs text-accent underline cursor-pointer disabled:cursor-not-allowed disabled:text-muted2 disabled:no-underline"
            >
              {theme ? 'Clear theme to customize' : state.custom ? 'Exit customization' : 'Customize design'}
            </button>
          </div>

          {state.custom && (
            <div className="mt-5 space-y-6">
              {/* 1-Click Curated Color Mood Presets */}
              <div className="rounded-xl border border-line/70 bg-panel/60 p-4 space-y-3">
                <div className="flex items-center justify-between">
                  <p className="text-xs font-semibold uppercase tracking-wide text-muted flex items-center gap-1.5">
                    <Sparkles className="size-3.5 text-accent" />
                    1-Click Color Mood Presets
                  </p>
                  <span className="text-[10.5px] text-muted2">Harmonious color palettes</span>
                </div>
                <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 gap-2">
                  {COLOR_PRESETS.map(preset => (
                    <button
                      key={preset.name}
                      type="button"
                      onClick={() => save({ colors: { ...preset.colors }, button: preset.colors.button })}
                      className="group flex flex-col gap-1.5 rounded-xl border border-line bg-panel p-2.5 text-left transition hover:border-accent hover:bg-panel2 cursor-pointer shadow-xs"
                    >
                      <div className="flex items-center justify-between">
                        <span className="text-xs font-semibold text-ink group-hover:text-accent truncate">
                          {preset.name}
                        </span>
                        <span className="rounded bg-panel2 px-1.5 py-0.5 font-mono text-[9px] text-muted2">
                          {preset.tag}
                        </span>
                      </div>
                      <div className="flex h-3 w-full overflow-hidden rounded-md border border-line/60">
                        <span className="flex-1" style={{ background: preset.colors.primary }} />
                        <span className="flex-1" style={{ background: preset.colors.secondary }} />
                        <span className="flex-1" style={{ background: preset.colors.surface }} />
                        <span className="flex-1" style={{ background: preset.colors.button }} />
                        <span className="flex-1" style={{ background: preset.colors.success }} />
                      </div>
                    </button>
                  ))}
                </div>
              </div>

              <div className="grid gap-6 lg:grid-cols-12">
                <div className="space-y-6 lg:col-span-7">
                  <div className="rounded-xl border border-line bg-panel p-4 space-y-4">
                    <p className="text-xs font-semibold uppercase tracking-wide text-muted">Colors & Appearance</p>
                    <div className="grid grid-cols-2 gap-3">
                      {SWATCHES.map(key => (
                        <Swatch key={key} label={key} value={state.colors[key]}
                          fallback={DEFAULT_PALETTE[key]}
                          onChange={value => save({ colors: { ...state.colors, [key]: value } })} />
                      ))}
                      <Swatch label="button" value={state.button} fallback={DEFAULT_PALETTE.primary}
                        onChange={value => save({ button: value })} />
                      {STATUS_SWATCHES.map(key => (
                        <Swatch key={key} label={key} value={state.colors[key]}
                          fallback={DEFAULT_PALETTE[key]}
                          onChange={value => save({ colors: { ...state.colors, [key]: value } })} />
                      ))}
                    </div>
                    <div className="pt-2 border-t border-line/60 space-y-3">
                      <Choice label="Appearance" options={APPEARANCES} value={state.appearance} onPick={value => save({ appearance: value })} />
                      <Choice label="Borders" options={BORDERS} value={state.border} onPick={value => save({ border: value })} />
                      <Choice label="Shadows" options={SHADOWS} value={state.shadow} onPick={value => save({ shadow: value })} />
                      <Choice label="Icons" options={ICONS} value={state.icons} onPick={value => save({ icons: value })} />
                    </div>
                  </div>

                  <div className="rounded-xl border border-line bg-panel p-4 space-y-4">
                    <p className="text-xs font-semibold uppercase tracking-wide text-muted">Typography & Core Layout</p>
                    <label className="text-xs font-semibold uppercase tracking-wide text-muted block">
                      Quick Font Pairing
                      <select
                        value={PAIRINGS.some(([, h, b]) => h === state.headingFont && b === state.bodyFont)
                          ? `${state.headingFont}|${state.bodyFont}` : 'custom'}
                        onChange={e => {
                          if (e.target.value === 'custom') return
                          const [heading, body] = e.target.value.split('|')
                          if (heading) loadGoogleFont(heading)
                          if (body) loadGoogleFont(body)
                          save({ headingFont: heading, bodyFont: body })
                        }}
                        className="mt-1.5 block w-full rounded-lg border border-line bg-panel2 p-2 text-sm font-normal text-ink outline-none"
                      >
                        {PAIRINGS.map(([label, heading, body]) => (
                          <option key={label} value={`${heading}|${body}`}>{label}</option>
                        ))}
                        <option value="custom">Custom (Search Google Fonts below)</option>
                      </select>
                    </label>
                    <div className="grid sm:grid-cols-2 gap-3">
                      <FontPicker label="Heading font" value={state.headingFont} placeholder="e.g. Playfair Display"
                        catalog={fontCatalog} onChange={val => save({ headingFont: val })} />
                      <FontPicker label="Body font" value={state.bodyFont} placeholder="e.g. Inter"
                        catalog={fontCatalog} onChange={val => save({ bodyFont: val })} />
                    </div>
                    <div className="pt-2 border-t border-line/60 space-y-3">
                      <div>
                        <p className="mb-2 text-xs font-semibold uppercase tracking-wide text-muted">Button corners</p>
                        <div className="flex flex-wrap gap-2">
                          {RADII.map(([label, value]) => (
                            <button key={value} type="button" onClick={() => save({ radius: value })}
                              style={{ borderRadius: value }}
                              className={`border px-3 py-1.5 text-xs transition cursor-pointer ${state.radius === value
                                ? 'border-accent bg-accent/15 text-ink font-medium'
                                : 'border-line text-muted hover:text-ink hover:bg-panel2'}`}>
                              {label}
                            </button>
                          ))}
                        </div>
                      </div>
                      <label className="text-xs font-semibold uppercase tracking-wide text-muted block">
                        Spacing & Density
                        <select value={state.density} onChange={e => save({ density: e.target.value })}
                          className="mt-1.5 block w-full rounded-lg border border-line bg-panel2 p-2 text-sm font-normal text-ink outline-none">
                          {DENSITIES.map(value => <option key={value}>{value}</option>)}
                        </select>
                      </label>
                      <div>
                        <p className="mb-2 text-xs font-semibold uppercase tracking-wide text-muted">
                          Corner radius <span className="font-normal normal-case text-muted2">({state.radius})</span>
                        </p>
                        <input type="range" min="0" max="32" step="1" aria-label="Corner radius"
                          value={parseInt(state.radius, 10) || 0}
                          onChange={e => save({ radius: `${e.target.value}px` })}
                          className="w-full accent-[#1877F2] cursor-pointer" />
                      </div>
                      <Choice label="Content width" options={WIDTHS} value={state.width} onPick={value => save({ width: value })} />
                      <Choice label="Navigation" options={NAVS} value={state.nav} onPick={value => save({ nav: value })} />
                      <Choice label="Motion" options={MOTIONS} value={state.motion} onPick={value => save({ motion: value })} />
                    </div>
                  </div>
                </div>

                <div className="lg:col-span-5">
                  <div className="sticky top-6">
                    <LiveComponentPreview state={state} theme={null} />
                  </div>
                </div>
              </div>

              <AdvancedDesignCustomize value={state.advanced || {}} onChange={advanced => save({ advanced })} />

              <label className="block text-sm font-medium">
                Anything else about the custom look and feel
                <TextArea value={state.direction} onChange={e => save({ direction: e.target.value })} rows={3}
                  placeholder="Reference sites, imagery, tone, or UI rules not covered above…"
                  className="mt-2 w-full rounded-lg border border-line bg-panel p-3 text-ink" />
              </label>
            </div>
          )}
        </div>

'''
    text = replace_regex(
        text,
        r"        \{/\* Customization Section \*/\}.*?(?=        \{/\* Site Images \*/\})",
        customization_section,
        "replace customization section",
    )

    text = replace_regex(
        text,
        r"\n        \{/\* Additional Look & Feel Directive \*/\}.*?\n        </label>\n",
        "\n",
        "remove duplicate global look-and-feel textarea",
    )

    path.write_text(text, encoding="utf-8")


def patch_wireframe_context() -> None:
    path = ROOT / "server_modules" / "builder" / "site_images.py"
    text = path.read_text(encoding="utf-8")

    old = '''        "MANDATORY UI/UX CONSISTENCY RULE: You MUST follow these wireframe blueprints strictly.",
        "The wireframe defines the spatial hierarchy, page sections, ordering, form controls, table columns,",
        "and interactive elements that the customer reviewed and approved. Keep the same sections in the same order,",
        "the same fields in forms, and the same actions/buttons. Do not rearrange or omit wireframe elements.",
        "Take the layout and structure from the wireframes; take styling, colors, and polish from the design system.\\n",
        "=== WIREFRAME STRUCTURAL BLUEPRINTS (read into context) ==="
'''
    new = '''        "MANDATORY UI/UX CONSISTENCY RULE: You MUST follow these wireframe HTML files strictly.",
        "Before writing or editing ANY prototype/build UI page, read the matching HTML file from",
        "`.agentforge/wireframes/html/`. The HTML is the approved low-fidelity source of truth.",
        "Preserve page sections, ordering, form controls, table columns, actions/buttons and spatial hierarchy.",
        "Do not invent a different layout. Styling, colors and component polish may change; structure may not.\\n",
        "=== APPROVED WIREFRAME HTML CONTEXT ==="
'''
    text = replace_once(text, old, new, "wireframe mandatory instructions")

    old_loop = '''        try:
            content = item["path"].read_text(encoding="utf-8", errors="replace")
            struct = outline(content)
            if struct:
                if len(struct) > 1500:
                    struct = struct[:1500].rsplit("\\n", 1)[0] + "\\n  …"
                brief_lines.append(f"\\n--- Wireframe: {item['name']} ({item['route']} -> {item['file']}) ---\\n{struct}")
        except Exception:
            continue

    brief_lines.append("\\n=== END WIREFRAME BLUEPRINTS ===\\n")
'''
    new_loop = '''        try:
            content = item["path"].read_text(encoding="utf-8", errors="replace")
            struct = outline(content)
            if struct:
                if len(struct) > 1800:
                    struct = struct[:1800].rsplit("\\n", 1)[0] + "\\n  …"
                brief_lines.append(
                    f"\\n--- Wireframe: {item['name']} ({item['route']} -> {item['file']}) ---"
                    f"\\nSTRUCTURE:\\n{struct}")
            # The model receives the actual approved markup, not only a derived
            # summary. A bounded copy keeps the initial context fast; when a
            # wireframe is longer the mandatory instruction above makes the
            # agent open the file itself before touching that page.
            raw = content if len(content) <= 6000 else content[:6000] + "\\n<!-- truncated here: read the file before editing this page -->"
            brief_lines.append(f"\\nAPPROVED HTML SOURCE:\\n{raw}")
        except Exception:
            continue

    brief_lines.append("\\n=== END APPROVED WIREFRAME HTML CONTEXT ===\\n")
'''
    text = replace_once(text, old_loop, new_loop, "wireframe raw html context")
    path.write_text(text, encoding="utf-8")


def patch_build_page_sync() -> None:
    path = ROOT / "server_modules" / "srs" / "parent_sync.py"
    text = path.read_text(encoding="utf-8")
    text = replace_once(
        text,
        '        if any(name.lower().endswith(ext) for ext in (".jsx", ".tsx"))\n',
        '        if any(name.lower().endswith(ext) for ext in (".jsx", ".tsx", ".js", ".ts"))\n',
        "build page source extensions",
    )
    text = replace_once(
        text,
        '    """The pages a developer (build) change rewrote, derived from JSX/TSX files.\n',
        '    """The pages a developer (build) change rewrote, derived from JS/JSX/TS/TSX files.\n',
        "build page sync docstring",
    )
    path.write_text(text, encoding="utf-8")


def verify() -> None:
    design = (ROOT / "studio" / "components" / "DesignCustomize.jsx").read_text(encoding="utf-8")
    required = [
        "AdvancedDesignCustomize",
        "advancedCustomizationDirection",
        "Theme and custom design are mutually exclusive",
        "wireframe_source: 'approved-html-required'",
        "Custom design mode — theme picker is locked",
    ]
    for marker in required:
        if marker not in design:
            raise RuntimeError(f"missing design marker: {marker}")
    forbidden = ["FIDELITY_OPTIONS", "AI Polished (Recommended)", "Strict Wireframe (1:1)", "wireframeFidelity"]
    for marker in forbidden:
        if marker in design:
            raise RuntimeError(f"legacy wireframe mode still present: {marker}")

    helper = (ROOT / "studio" / "components" / "AdvancedDesignCustomize.jsx").read_text(encoding="utf-8")
    for title in [
        "Layout & Page Structure", "Responsive Design", "Header / Navbar", "Sidebar", "Cards", "Buttons",
        "Forms", "Tables & Data Lists", "Tabs / Segmented Controls", "Modal / Drawer / Popup",
        "Hero & Landing Sections", "Dashboard Style", "Charts & Data Visualization",
        "Status & Feedback Components", "Brand Identity", "Shape Language", "Icon System",
        "Images & Media", "Background System", "Typography Advanced", "Navigation Behaviour",
        "Motion & Interaction", "Accessibility", "Design Density", "Page-specific Customization",
        "Advanced Design System", "Live Preview Controls", "AI Assisted Design",
    ]:
        if title not in helper:
            raise RuntimeError(f"missing advanced section: {title}")


if __name__ == "__main__":
    patch_design_customize()
    patch_wireframe_context()
    patch_build_page_sync()
    verify()
    print("AgentFold wireframe/design upgrade applied successfully")
