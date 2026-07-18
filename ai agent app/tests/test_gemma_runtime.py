import hashlib
import json
from pathlib import Path

import pytest

from agents import llm
from agents.architect import ARCHITECT_JSON_SCHEMA, validate_spec
from agents.gen_agents import (GenAgent, SYSTEM, SectionAgent, UpdateAgent, apply_search_replace,
                               fix_compiler_suggested_identifier, fix_decorative_overlay_pointer_events,
                               fix_invalid_lucide_imports,
                               fix_date_literal_for_serialized_dto,
                               fix_duplicate_jsx_classname,
                               fix_forbidden_external_decorative_image,
                               fix_interactive_badge_as_button,
                               fix_missing_gradient_artwork_colors,
                               fix_missing_dto_metadata,
                               fix_missing_canonical_prop_field,
                               fix_missing_entity_type_import,
                               fix_missing_ui_imports,
                               fix_missing_controlled_filter_props, fix_nonsemantic_color_classes,
                               fix_public_reference_empty_fallback, fix_single_route_topnav,
                               fix_redundant_unsafe_html_prop,
                               fix_navigator_share_feature_test,
                               fix_transition_misused_as_boolean_state,
                               fix_unsupported_button_link_variant,
                               fix_unwired_filter_state, fix_unwired_selection_state,
                               fix_uncalled_boolean_prop, repair_output_budget, scrub_jsx)
from agents.memory import Memory
from agents.product_context import build_product_context, prompt_block, write_product_context
from tests.test_architect_context import spec


class _Response:
    def __init__(self, value):
        self.value = value

    def json(self):
        return self.value

    def iter_lines(self):
        return iter(self.value)


def _runtime_request(method, path, **kwargs):
    if path == "/api/tags":
        return _Response({"models": [{"name": "gemma4:12b"}]})
    if path == "/api/show":
        return _Response({"details": {"family": "gemma4", "quantization_level": "Q4_K_M"}})
    if path == "/api/chat":
        assert kwargs["json"]["options"]["num_ctx"] == 98_304
        assert kwargs["json"]["keep_alive"] == "30m"
        return _Response({"done": True, "done_reason": "stop", "message": {"content": "OK"}})
    if path == "/api/ps":
        return _Response({"models": [{"name": "gemma4:12b", "context_length": 98_304,
                                      "size": 8_000, "size_vram": 8_000}]})
    raise AssertionError(path)


def _runtime_env(monkeypatch):
    monkeypatch.setenv("OLLAMA_FLASH_ATTENTION", "1")
    monkeypatch.setenv("OLLAMA_KV_CACHE_TYPE", "q8_0")
    monkeypatch.setenv("OLLAMA_NUM_PARALLEL", "2")


def test_runtime_profile_requires_exact_gpu_resident_configuration(monkeypatch):
    _runtime_env(monkeypatch)
    monkeypatch.setattr(llm, "_request", _runtime_request)
    profile = llm.runtime_profile(prewarm=True)
    assert profile == {
        "model": "gemma4:12b", "family": "gemma4", "quantization": "Q4_K_M",
        "context": 98_304, "size": 8_000, "sizeVram": 8_000,
        "processor": "100% GPU", "flashAttention": True,
        "kvCache": "q8_0", "parallel": 2,
        "prewarmLoadSeconds": 0.0, "warmStart": True,
    }


def test_runtime_profile_rejects_cpu_spill_before_generation(monkeypatch):
    _runtime_env(monkeypatch)

    def request(method, path, **kwargs):
        response = _runtime_request(method, path, **kwargs)
        if path == "/api/ps":
            return _Response({"models": [{"name": "gemma4:12b", "context_length": 98_304,
                                          "size": 8_000, "size_vram": 7_999}]})
        return response

    monkeypatch.setattr(llm, "_request", request)
    with pytest.raises(llm.RuntimeProfileError, match="CPU-offloaded"):
        llm.runtime_profile(prewarm=True)


def test_payload_ignores_model_context_and_gpu_overrides():
    payload = llm._payload(
        "nemotron-3-super:cloud", [{"role": "user", "content": "x"}], 77, False,
        {"num_ctx": 4_096, "num_gpu": 0, "temperature": 0.7},
    )
    assert payload["model"] == "gemma4:12b"
    assert payload["options"]["num_ctx"] == 98_304
    assert payload["options"]["num_predict"] == 77
    assert "num_gpu" not in payload["options"]


def test_architect_payload_is_cloud_only_with_262k_context():
    payload = llm._payload(
        "gemma4:12b", [{"role": "user", "content": "plan"}], 1_000, False,
        {"num_ctx": 4_096, "num_gpu": 0}, route="architect",
    )
    assert payload["model"] == "nemotron-3-super:cloud"
    assert payload["options"]["num_ctx"] == 262_144
    assert "num_gpu" not in payload["options"]


def test_length_stopped_response_is_rejected(monkeypatch):
    monkeypatch.setattr(llm, "_request", lambda *a, **k: _Response({
        "done": True, "done_reason": "length", "eval_count": 50,
        "message": {"content": "partial"},
    }))
    with pytest.raises(llm.LLMTruncatedError):
        llm.chat([{"role": "user", "content": "generate"}], num_predict=50)


def test_stream_length_stop_never_returns_a_partial_candidate(monkeypatch):
    chunks = [
        json.dumps({"message": {"content": "partial"}, "done": False}).encode(),
        json.dumps({"message": {"content": ""}, "done": True,
                    "done_reason": "length", "eval_count": 10}).encode(),
    ]
    monkeypatch.setattr(llm, "_request", lambda *a, **k: _Response(chunks))
    with pytest.raises(llm.LLMTruncatedError):
        list(llm.stream_chat([{"role": "user", "content": "generate"}], num_predict=10))


def test_native_system_role_is_used_without_manual_control_tokens():
    messages = llm._messages([{"role": "user", "content": "task"}], "system rule")
    assert messages == [{"role": "system", "content": "system rule"},
                        {"role": "user", "content": "task"}]
    assert "<|turn>" not in json.dumps(messages)


def test_generation_system_starts_code_without_reasoning_channels():
    assert "Thinking is disabled" in SYSTEM
    assert "start immediately with the first code token" in SYSTEM
    assert "Reason efficiently" not in SYSTEM
    assert "<|" not in SYSTEM


def test_memory_manifest_hashes_every_authoritative_view(tmp_path):
    planned = spec()
    context = build_product_context(planned)
    write_product_context(tmp_path, context)
    memory = Memory(tmp_path, planned)
    memory.set_product_context(context)
    memory.set_contract("# CONTRACT\n\nExact fields.\n")
    memory.write_all(tasks=["components/pages/Journal.tsx"])
    memory.write_locations({"components/pages/Journal.tsx": ("section", {})})
    assert memory.validate_memory() == []

    manifest = json.loads((tmp_path / ".locode" / "memory-manifest.json").read_text())
    for required in ("PROJECT.md", "MODELS.md", "ROUTES.md", "API.md", "CONTRACT.md",
                     "TASKS.md", "LOCATIONS.md", "COMPONENTS.md", "PROGRESS.md",
                     "product-context.json"):
        assert required in manifest["documents"]
        raw = (tmp_path / ".locode" / required).read_bytes()
        assert manifest["documents"][required]["sha256"] == hashlib.sha256(raw).hexdigest()
        assert manifest["documents"][required]["bytes"] == len(raw)
    (tmp_path / ".locode" / "ROUTES.md").write_text("tampered", encoding="utf-8")
    assert any("ROUTES.md" in issue for issue in memory.validate_memory())


def test_update_memory_hydrates_append_only_progress_and_components(tmp_path):
    planned = spec()
    context = build_product_context(planned)
    write_product_context(tmp_path, context)
    first = Memory(tmp_path, planned)
    first.set_product_context(context)
    first.set_contract("# CONTRACT\n\nExact fields.\n")
    first.write_all(tasks=["components/pages/Journal.tsx"])
    first.write_locations({"components/pages/Journal.tsx": ("section", {})})
    first.note_component("components/pages/Journal.tsx")
    first.note_progress("generated Journal")

    update = Memory(tmp_path, planned)
    update.set_product_context(context)
    update.set_contract("# CONTRACT\n\nExact fields.\n")
    update.note_component("components/features/journal/SpeciesFilter.tsx")
    update.note_progress("updated SpeciesFilter")

    components = (tmp_path / ".locode" / "COMPONENTS.md").read_text(encoding="utf-8")
    progress = (tmp_path / ".locode" / "PROGRESS.md").read_text(encoding="utf-8")
    assert "components/pages/Journal.tsx" in components
    assert "components/features/journal/SpeciesFilter.tsx" in components
    assert "generated Journal" in progress
    assert "updated SpeciesFilter" in progress
    assert update.validate_memory() == []


def test_product_context_contains_generation_plan_and_exact_ui_exports():
    context = build_product_context(spec())
    assert context["generationPlan"]["components"]
    assert context["uiExportMap"]["@/components/ui/button"]["values"] == [
        "Button", "buttonVariants"]
    assert "Typography" not in json.dumps(context["uiExportMap"])
    assert {"Select", "SelectContent", "SelectItem", "SelectTrigger", "SelectValue"}.issubset(
        context["uiExportMap"]["@/components/ui/select"]["values"])
    assert "onValueChange" in context["uiExportMap"]["@/components/ui/select"]["signatures"]["Select"]
    assert "orientation" in context["uiExportMap"]["@/components/ui/separator"]["signatures"]["Separator"]


def test_active_preflight_uses_one_bounded_micro_repair(monkeypatch, tmp_path):
    planned = spec()
    context = build_product_context(planned)
    write_product_context(tmp_path, context)
    memory = Memory(tmp_path, planned)
    memory.set_product_context(context)

    class Analyzer:
        ok = True

        def check(self, _rel, source):
            return [] if "const value = 'ready'" in source else [
                {"line": 1, "code": 2304, "message": "Cannot find name 'missing'."}]

        def release(self, _rel):
            pass

    agent = GenAgent(tmp_path, memory, get_analyzer=lambda: Analyzer())
    monkeypatch.setattr(agent, "_gen", lambda *_args, **_kwargs: "const value = missing\n")
    monkeypatch.setattr(llm, "chat", lambda *_args, **_kwargs: (
        "<<<<<<< SEARCH\nconst value = missing\n=======\n"
        "const value = 'ready'\n>>>>>>> REPLACE"))
    assert agent._gen_checked("lib/value.ts", "Generate value", 1000) == "const value = 'ready'\n"


def test_exact_micro_repair_requires_a_unique_search():
    original = "const value = missing\n"
    fixed, count = apply_search_replace(
        original,
        "<<<<<<< SEARCH\nconst value = missing\n=======\nconst value = 'ready'\n>>>>>>> REPLACE",
    )
    assert count == 1
    assert fixed == "const value = 'ready'\n"
    unchanged, count = apply_search_replace("x\nx\n", "<<<<<<< SEARCH\nx\n=======\ny\n>>>>>>> REPLACE")
    assert count == 0
    assert unchanged == "x\nx\n"


def test_proven_missing_shadcn_export_is_added_to_existing_import():
    source = "import { Alert, AlertDescription } from '@/components/ui/alert'\nconst x = <AlertTitle />\n"
    fixed, count = fix_missing_ui_imports(source, [
        {"code": 2304, "message": "Cannot find name 'AlertTitle'."}])
    assert count == 1
    assert "import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert'" in fixed


def test_missing_canonical_dto_in_type_position_gets_exact_type_import():
    source = "'use client'\ninterface Props { teas: TeaType[] }\n"
    fixed, count = fix_missing_entity_type_import(
        source,
        [{"code": 2304, "message": "Cannot find name 'TeaType'."}],
        {"collections": [{"name": "TeaType"}]},
    )
    assert count == 1
    assert "import type { TeaType } from '@/types'" in fixed


def test_typescript_lucide_export_suggestion_repairs_only_lucide_import():
    source = (
        "import { Clipboard_Copy as CopyIcon, Leaf } from 'lucide-react'\n"
        "const label = 'Clipboard_Copy'\n"
    )
    fixed, count = fix_invalid_lucide_imports(source, [{
        "code": 2724,
        "message": "'lucide-react' has no exported member named 'Clipboard_Copy'. "
                   "Did you mean 'ClipboardCopy'?",
    }])
    assert count == 1
    assert "{ ClipboardCopy as CopyIcon, Leaf } from 'lucide-react'" in fixed
    assert "const label = 'Clipboard_Copy'" in fixed


def test_typescript_local_identifier_suggestion_repairs_only_diagnosed_line():
    source = "const activeLevels = []\nconst next = activeLetters.filter(Boolean)\nconst copy = 'activeLetters'\n"
    fixed, count = fix_compiler_suggested_identifier(source, [{
        "line": 2,
        "message": "Cannot find name 'activeLetters'. Did you mean 'activeLevels'?",
    }])
    assert count == 1
    assert "const next = activeLevels.filter(Boolean)" in fixed
    assert "const copy = 'activeLetters'" in fixed


def test_public_reference_content_survives_a_successful_empty_api_array():
    source = "const INITIAL_TEAS: Tea[] = []\nif (result.success && result.data) setTeas(result.data)\n"
    fixed, count = fix_public_reference_empty_fallback(source)
    assert count == 1
    assert "Array.isArray(result.data) && result.data.length > 0" in fixed


def test_comment_only_filter_callback_is_wired_to_sibling_filter_prop():
    source = """'use client'
import React, { useState } from 'react'
import FilterControls from '@/components/FilterControls'
export default function Page() {
  return <><FilterControls onFilterChange={(value) => { // handled by the grid
  }} /><Grid filter={null} /></>
}
"""
    fixed, count = fix_unwired_filter_state(source)
    assert count == 3
    assert "onFilterChange={setFilter}" in fixed
    assert "filter={filter}" in fixed
    assert "React.ComponentProps<typeof FilterControls>['onFilterChange']" in fixed


def test_missing_controlled_filter_props_create_typed_state_and_real_filter_logic():
    source = """'use client'
import React, { useMemo, useState } from 'react'
import CaffeineFilter from '@/components/CaffeineFilter'
export default function Page() {
  const [teaData, setTeaData] = useState<TeaType[]>([])
  const filteredTeas = useMemo(() => { return teaData }, [teaData])
  return <><CaffeineFilter />{filteredTeas.length}</>
}
"""
    diagnostics = [{
        "message": "Type '{}' is missing the following properties from type "
                   "'{ onFilterChange: (level: string | null) => void; "
                   "currentFilter: string | null; }': onFilterChange, currentFilter",
    }]
    contract = {"collections": [{"fields": [{"name": "caffeineLevel"}]}]}
    fixed, count = fix_missing_controlled_filter_props(source, diagnostics, contract)
    assert count == 3
    assert "currentFilter={currentFilter} onFilterChange={setCurrentFilter}" in fixed
    assert "React.ComponentProps<typeof CaffeineFilter>['currentFilter']" in fixed
    assert "teaData.filter((item) => String(item.caffeineLevel).toLowerCase()" in fixed
    assert "[teaData, currentFilter]" in fixed


def test_empty_card_selection_handler_wires_selected_detail_state():
    source = """'use client'
import React, { useState } from 'react'
import type { TeaType } from '@/types'
export default function Page() {
  return <>{teas.map((tea) => <TeaCard tea={tea} isSelected={false} onSelect={(t) => {}} />)}
    <RecipeDetail selectedTea={filteredTeas[0] || null} /></>
}
"""
    fixed, count = fix_unwired_selection_state(
        source, {"collections": [{"name": "TeaType"}]})
    assert count == 4
    assert "const [selectedTea, setSelectedTea] = useState<TeaType | null>(null)" in fixed
    assert "onSelect={() => setSelectedTea(tea)}" in fixed
    assert "isSelected={selectedTea?._id === tea._id}" in fixed
    assert "selectedTea={selectedTea}" in fixed


def test_one_route_topnav_repeated_home_links_become_section_anchors():
    contract = {"routes": ["/"], "design": {"navStyle": "topnav"}}
    source = """<><nav><a href="/">Home</a><a href="/">Collections</a><a href="/">Brewing Guide</a></nav>
<main><section>Hero</section><section>Filters</section><section>Cards</section><section>Recipe</section></main></>"""
    fixed, count = fix_single_route_topnav(source, contract)
    assert count == 4
    assert 'href="#collections"' in fixed and 'id="collections"' in fixed
    assert 'href="#brewing-guide"' in fixed and 'id="brewing-guide"' in fixed
    assert fixed.count('href="/"') == 1


def test_one_route_topnav_empty_hash_links_also_become_real_anchors():
    contract = {"routes": ["/"], "design": {"navStyle": "topnav"}}
    source = """<><nav><a href="/">Home</a><a href="#">About</a><a href="#">Guide</a></nav>
<main><section>Hero</section><section>About</section><section>Guide</section></main></>"""
    fixed, count = fix_single_route_topnav(source, contract)
    assert count == 4
    assert 'href="#about"' in fixed and 'id="about"' in fixed
    assert 'href="#guide"' in fixed and 'id="guide"' in fixed


def test_full_card_decorative_overlay_cannot_intercept_controls():
    source = '<div className={cn("absolute inset-0 bg-gradient", visible && "opacity-100")} />\n'
    fixed, count = fix_decorative_overlay_pointer_events(source)
    assert count == 1
    assert "pointer-events-none absolute inset-0" in fixed


def test_generated_visible_mojibake_is_normalized():
    fixed, count = scrub_jsx("components/pages/Home.tsx", "return <p>Â© 95Â°C</p>\n")
    assert count == 2
    assert "© 95°C" in fixed


def test_explicit_final_reimplementation_replaces_an_appended_broken_first_version():
    source = """'use client'
export default function Filter({ onChange }: { onChange: (x: string) => void }) {
  return <div>{'broken'}</div>
}
// Re-implementing correctly for the final export
function FilterFinal({ onChange }: { onChange: (x: string) => void }) {
  return <button onClick={() => onChange('ok')}>OK</button>
}
export default FilterFinal;
"""
    fixed, count = scrub_jsx("components/features/Filter.tsx", source)
    assert count == 1
    assert "export default function Filter" not in fixed
    assert "function FilterFinal" in fixed and "export default FilterFinal" in fixed


def test_multiline_class_template_closed_with_quote_gets_backtick_and_brace():
    source = """export default function Card() {
  return <button className={`base ${active ? 'on' : 'off'} focus:ring-2"
  >Choose</button>
}
"""
    fixed, count = scrub_jsx("components/features/Card.tsx", source)
    assert count == 1
    assert "focus:ring-2`}" in fixed


def test_quoted_class_closed_as_template_and_final_function_brace_are_repaired():
    source = """export default function StoryCard() {
  return (
    <article className="flex h-full`}>
      <div className="items-center gap-2`}>Story</div>
    </article>
  );
"""
    fixed, count = scrub_jsx("components/features/StoryCard.tsx", source)
    assert count == 3
    assert 'className="flex h-full">' in fixed
    assert 'className="items-center gap-2">' in fixed
    assert fixed.rstrip().endswith("}")


def test_extra_fragment_close_and_callback_result_shadow_are_repaired():
    source = """function Card({ isBookmarked }: { isBookmarked: (slug: string) => boolean }) {
  const isBookmarked = isBookmarked(story.slug)
  return <>{isBookmarked ? <span>Saved</span> : <></>>}</>
}
"""
    fixed, count = scrub_jsx("components/features/story-card.tsx", source)
    assert count == 2
    assert "const isBookmarkedResult = isBookmarked(story.slug)" in fixed
    assert "{isBookmarkedResult ?" in fixed
    assert "</>>" not in fixed


def test_unterminated_data_image_class_is_removed_but_gradient_child_remains():
    source = """export default function Art() {
  return (
    <div>
      <div className="absolute inset-0 opacity-20 bg-[url('data:image/svg+xml;bad-data%22>
        <div className="absolute inset-0 bg-gradient-to-tr from-primary to-accent" />
      </div>
  );
}
"""
    fixed, count = scrub_jsx("components/features/gradient-artwork.tsx", source)
    assert count == 2
    assert "data:image" not in fixed
    assert 'className="pointer-events-none absolute inset-0 opacity-20">' in fixed
    assert "bg-gradient-to-tr from-primary to-accent" in fixed
    assert fixed.count("</div>") == 2
    fixed_again, second_count = scrub_jsx("components/features/gradient-artwork.tsx", fixed)
    assert second_count == 0
    assert fixed_again == fixed


def test_split_self_closing_overlay_and_surplus_close_are_repaired():
    source = """export default function Art() {
  return (
    <div className="relative">
      <div className="pointer-events-none absolute inset-0">
      />
      <div className="absolute inset-0 bg-gradient-to-r" />
    </div>
  </div>
  );
}
"""
    fixed, count = scrub_jsx("components/features/gradient-artwork.tsx", source)
    assert count == 2
    assert '<div className="pointer-events-none absolute inset-0" />' in fixed
    assert fixed.count("</div>") == 1
    fixed_again, second_count = scrub_jsx("components/features/gradient-artwork.tsx", fixed)
    assert second_count == 0 and fixed_again == fixed


def test_unclosed_fragment_in_ternary_branch_is_completed():
    source = """export default function Action({ copied }: { copied: boolean }) {
  return <button>{copied ? (
    <>
      <span>Done</span>
    ) : (
    <>
      <span>Copy</span>
    </>
  )}</button>
}
"""
    fixed, count = scrub_jsx("components/features/action.tsx", source)
    assert count == 1
    assert fixed.count("</>") == 2
    assert "<span>Done</span>\n    </>" in fixed


def test_complete_root_jsx_with_extra_chevron_gets_return_and_function_tail():
    source = """export default function HomePage() {
  return (
    <div><main>Atlas</main></div>>
"""
    fixed, count = scrub_jsx("components/pages/HomePage.tsx", source)
    assert count == 2
    assert "</div>>" not in fixed
    assert fixed.rstrip().endswith(");\n}")
    again, second_count = scrub_jsx("components/pages/HomePage.tsx", fixed)
    assert second_count == 0 and again == fixed


def test_text_only_links_are_closed_before_their_next_sibling():
    source = """export default function Nav() {
  return <nav>
    <Link href="/about">About
    <Link href="/notes">
      Field Notes

    <Link href="/ok">Already closed</Link>
  </nav>
}
"""
    fixed, count = scrub_jsx("components/pages/Nav.tsx", source)
    assert count == 2
    assert '<Link href="/about">About</Link>' in fixed
    assert "Field Notes</Link>" in fixed
    assert fixed.count("</Link>") == 3
    again, second_count = scrub_jsx("components/pages/Nav.tsx", fixed)
    assert second_count == 0 and again == fixed


def test_compiler_and_product_contract_add_a_missing_nested_prop_field():
    source = """interface Props {
  story: {
    id: string;
    title: string;
  };
}
const preview = story.content.substring(0, 80)
"""
    fixed, count = fix_missing_canonical_prop_field(source, [{
        "line": 7,
        "code": 2339,
        "message": "Property 'content' does not exist on type '{ id: string; title: string; }'.",
    }], {"collections": [{"name": "Story", "fields": [
        {"name": "content", "type": "String"},
    ]}]})
    assert count == 1
    assert "content: string;" in fixed


def test_ts2774_boolean_callback_is_called_with_contract_proven_entity_key():
    source = """type Props = {
  story: Story;
  isBookmarked: (slug: string) => boolean;
};
const label = isBookmarked ? 'Remove' : 'Add';
const tone = isBookmarked ? 'active' : 'muted';
const icon = isBookmarked && 'filled';
"""
    diagnostics = [{
        "line": line,
        "code": 2774,
        "message": "This condition will always return true since this function is always defined. "
                   "Did you mean to call it instead?",
    } for line in (5, 6, 7)]
    fixed, count = fix_uncalled_boolean_prop(source, diagnostics, {
        "collections": [{"name": "Story", "fields": [{"name": "slug", "type": "String"}]}],
    })
    assert count == 3
    assert fixed.count("isBookmarked(story.slug)") == 3


def test_boolean_callback_fixer_ignores_non_typescript_quality_codes():
    source = "const tone = isBookmarked ? 'active' : 'muted'\n"
    fixed, count = fix_uncalled_boolean_prop(source, [{
        "code": "nonsemantic-hex-color",
        "message": "generated UI must use semantic tokens",
    }], {"collections": []})
    assert count == 0
    assert fixed == source


def test_invalid_duplicate_html_prop_becomes_safe_text_content():
    source = """<div
  className="whitespace-pre-wrap"
  dangerously_html_from={content} // invented unsafe prop
  dangerouslySetInnerHTML={{ __html: content }}
/>"""
    fixed, count = fix_redundant_unsafe_html_prop(source, [{
        "code": 2322,
        "line": 3,
        "message": "Property 'dangerously_html_from' does not exist on type "
                   "'DetailedHTMLProps<HTMLAttributes<HTMLDivElement>, HTMLDivElement>'.",
    }])
    assert count == 1
    assert "dangerously" not in fixed
    assert "{content}</div>" in fixed


def test_duplicate_static_and_conditional_classname_attributes_are_merged():
    source = """<Textarea
  id="note"
  className="min-h-[120px]"
  value={formData.note}
  onChange={(e) => setNote(e.target.value)}
  className={errors.note ? 'border-destructive' : ''}
/>"""
    fixed, count = fix_duplicate_jsx_classname(source, [{
        "code": 17001,
        "line": 6,
        "message": "JSX elements cannot have multiple attributes with the same name.",
    }])
    assert count == 1
    assert fixed.count("className=") == 1
    assert "min-h-[120px]" in fixed and "errors.note ? 'border-destructive' : ''" in fixed
    assert "onChange=" in fixed and "value=" in fixed


def test_interactive_badge_with_button_props_uses_button_primitive():
    source = """import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
const control = <Badge type="button" onClick={choose} aria-pressed={active}>Mood</Badge>
"""
    fixed, count = fix_interactive_badge_as_button(source, [{
        "code": 2322,
        "line": 3,
        "message": "Property 'type' does not exist on type 'IntrinsicAttributes & BadgeProps'.",
    }])
    assert count == 1
    assert '<Button type="button"' in fixed and "</Button>" in fixed
    assert "onClick={choose}" in fixed and "aria-pressed={active}" in fixed


def test_date_literals_are_serialized_only_on_exact_dto_string_diagnostics():
    source = """const story: Story = {
  createdAt: new Date('2025-04-01'),
  updatedAt: new Date('2025-04-02'),
}
const age = new Date('2020-01-01')
"""
    diagnostics = [{
        "code": 2322,
        "line": line,
        "message": "Type 'Date' is not assignable to type 'string'.",
    } for line in (2, 3)]
    fixed, count = fix_date_literal_for_serialized_dto(source, diagnostics)
    assert count == 2
    assert "createdAt: new Date('2025-04-01').toISOString()" in fixed
    assert "updatedAt: new Date('2025-04-02').toISOString()" in fixed
    assert "const age = new Date('2020-01-01')" in fixed


def test_usetransition_called_with_booleans_becomes_loading_state():
    source = """import React, { useState, useTransition } from 'react';
export default function Form() {
  const [isPending, setPending] = useTransition();
  async function submit() {
    setPending(true);
    await send();
    setPending(false);
  }
  return <button disabled={isPending}>Send</button>
}
"""
    diagnostics = [{
        "code": 2345,
        "line": line,
        "message": "Argument of type 'boolean' is not assignable to parameter of type "
                   "'TransitionFunction'.",
    } for line in (5, 7)]
    fixed, count = fix_transition_misused_as_boolean_state(source, diagnostics)
    assert count == 1
    assert "const [isPending, setPending] = useState(false)" in fixed
    assert "useTransition" not in fixed
    assert "import React, { useState } from 'react'" in fixed
    assert "setPending(true)" in fixed and "setPending(false)" in fixed


def test_curated_typed_dto_array_gets_only_compiler_missing_metadata():
    source = """const stories: Story[] = useMemo(() => [
  {
    title: 'Amber Hour',
    slug: 'amber-hour',
    publishedAt: new Date().toISOString(),
  },
], [])
const unrelated = { title: 'Do not edit', slug: 'outside-array' }
"""
    fixed, count = fix_missing_dto_metadata(source, [{
        "code": 2322,
        "line": 1,
        "message": "Type '{ title: string; slug: string; publishedAt: string; }[]' is not "
                   "assignable to type 'Story[]'. Type '{ ... }' is missing the following "
                   "properties from type 'Story': _id, createdAt, updatedAt",
    }], {"collections": [{"name": "Story", "fields": [
        {"name": "title"}, {"name": "slug"}, {"name": "publishedAt"},
    ]}]})
    assert count == 3
    assert "_id: 'amber-hour'" in fixed
    assert "createdAt: '2025-01-01T00:00:00.000Z'" in fixed
    assert "updatedAt: '2025-01-01T00:00:00.000Z'" in fixed
    assert "const unrelated = { title: 'Do not edit', slug: 'outside-array' }" in fixed


def test_navigator_share_condition_uses_callable_feature_test():
    source = """if (typeof navigator !== 'undefined' && window.navigator.share) {
  await navigator.share(payload)
}
"""
    fixed, count = fix_navigator_share_feature_test(source, [{
        "code": 2774,
        "line": 1,
        "message": "This condition will always return true since this function is always defined. "
                   "Did you mean to call it instead?",
    }])
    assert count == 1
    assert "typeof window.navigator.share === 'function'" in fixed
    assert "await navigator.share(payload)" in fixed


def test_unsupported_link_button_variant_uses_registry_supported_ghost():
    source = '<Button variant="link" onClick={clear}>Clear filters</Button>\n'
    fixed, count = fix_unsupported_button_link_variant(source, [{
        "code": 2322,
        "line": 1,
        "message": "Type '\"link\"' is not assignable to type "
                   "'\"default\" | \"secondary\" | \"ghost\" | undefined'.",
    }])
    assert count == 1
    assert 'variant="ghost"' in fixed


def test_missing_gradient_artwork_palette_is_supplied_as_semantic_variables():
    source = """<section>
  <GradientArtwork className="min-h-72" />
</section>
"""
    fixed, count = fix_missing_gradient_artwork_colors(source, [{
        "code": 2741,
        "line": 2,
        "message": "Property 'colors' is missing in type '{ className: string; }' but required "
                   "in type '{ colors: string[]; className?: string | undefined; }'.",
    }])
    assert count == 1
    assert "colors={['var(--primary)', 'var(--secondary)', 'var(--accent)']}" in fixed
    assert 'className="min-h-72"' in fixed


def test_forbidden_external_empty_texture_overlay_is_removed_without_siblings():
    source = """<div className="relative">
  <div className="absolute inset-0 bg-gradient-to-r from-primary to-accent" />
  <div className="absolute inset-0 bg-[url('https://example.com/noise.png')] pointer-events-none" />
</div>
"""
    fixed, count = fix_forbidden_external_decorative_image(source, [{
        "code": "forbidden-external-image",
        "message": "raw product request forbids external image dependencies",
    }])
    assert count == 1
    assert "https://" not in fixed
    assert "bg-gradient-to-r from-primary to-accent" in fixed


def test_palette_matching_rgba_literal_maps_to_semantic_color_mix():
    design = spec()["design"]
    design["palette"]["secondary"] = "#D4AF37"
    source = "background: linear-gradient(transparent, rgba(212, 175, 55, 0.1))"
    fixed, count = fix_nonsemantic_color_classes(source, design)
    assert count == 1
    assert "color-mix(in srgb, var(--secondary) 10%, transparent)" in fixed
    assert "rgba(" not in fixed


def test_repair_budget_scales_with_file_and_diagnostics_but_stays_bounded():
    assert repair_output_budget("const x = missing\n", [{"code": 2304}]) == 1800
    budget = repair_output_budget("x" * 3200, [{"code": 1005}] * 20)
    assert 1800 < budget <= 4096


def test_literal_tailwind_colours_map_to_architect_semantic_tokens():
    design = spec()["design"]
    source = 'className="bg-[#fffdf5] text-[#14532d] border-red-200 bg-white text-green-700"'
    fixed, count = fix_nonsemantic_color_classes(source, design)
    assert count == 5
    assert "bg-background" in fixed and "text-primary" in fixed
    assert "border-destructive/30" in fixed
    assert "bg-card" in fixed and "text-success" in fixed
    assert "#" not in fixed and "red-" not in fixed and "green-" not in fixed


def test_inline_gradient_palette_hexes_map_to_css_variables():
    design = spec()["design"]
    primary = design["palette"]["primary"]
    secondary = design["palette"]["secondary"]
    accent = design["palette"]["accent"]
    source = f"background: `linear-gradient(135deg, {primary}, {secondary}, {accent})`"
    fixed, count = fix_nonsemantic_color_classes(source, design)
    assert count == 3
    assert "var(--primary)" in fixed
    assert "var(--secondary)" in fixed
    assert "var(--accent)" in fixed
    assert "#" not in fixed


def test_update_prompt_contains_full_context_file_and_dependencies(monkeypatch, tmp_path):
    planned = spec()
    context = build_product_context(planned)
    write_product_context(tmp_path, context)
    memory = Memory(tmp_path, planned)
    memory.set_product_context(context)
    captured = []

    def stream(messages, **kwargs):
        captured.append((messages, kwargs))
        yield "'use client'\nexport default function Journal(){return <main>Updated</main>}\n"

    monkeypatch.setattr(llm, "stream_chat", stream)
    UpdateAgent(tmp_path, memory).generate_update(
        "components/pages/Journal.tsx", "Add a species filter",
        "'use client'\nexport default function Journal(){return <main>Old</main>}\n",
        "-- types/index.ts --\nexport type Observation = { title: string }",
    )
    prompt = captured[0][0][0]["content"]
    for expected in (context["contextHash"], planned["_raw_idea"], "Add a species filter",
                     "FULL CURRENT FILE", "<main>Old</main>", "DEPENDENT FILES",
                     "Observation = { title: string }", "uiExportMap"):
        assert expected in prompt
    assert captured[0][1]["think"] is False
    assert captured[0][1]["extra_opts"]["temperature"] == 0


def test_generation_waves_reject_more_than_two_concurrent_components():
    planned = spec()
    paths = [item["path"] for item in planned["generation_plan"]["components"]]
    planned["generation_plan"]["dependencyWaves"] = [paths]
    if len(paths) < 3:
        clone = dict(planned["generation_plan"]["components"][0])
        clone.update({"name": "ExtraPanel", "path": "components/features/extra/ExtraPanel.tsx"})
        planned["generation_plan"]["components"].append(clone)
        paths.append(clone["path"])
        planned["generation_plan"]["dependencyWaves"] = [paths]
    assert "generation dependency waves may contain at most two components" in validate_spec(planned)


def test_public_fixed_count_guide_prompt_requires_first_load_content(monkeypatch, tmp_path):
    planned = spec()
    planned["_raw_idea"] = "Create a public guide comparing five observation types with top navigation."
    page = planned["pages"][0]
    page["kind"] = "educational-guide"
    page["resource"] = None
    page["resources"] = ["Observation"]
    context = build_product_context(planned)
    write_product_context(tmp_path, context)
    memory = Memory(tmp_path, planned)
    memory.set_product_context(context)
    captured = {}
    agent = SectionAgent(tmp_path, memory)

    def checked(rel, user, **kwargs):
        captured.update({"rel": rel, "user": user, "kwargs": kwargs})
        return "'use client'\nexport default function Journal(){return <main /> }\n"

    monkeypatch.setattr(agent, "_gen_checked", checked)
    agent.generate(page, "Journal", imports=[])
    assert "exactly 5 domain-accurate `Observation` reference records" in captured["user"]
    assert "an empty GET response must not turn the requested guide into a blank product" in captured["user"]
    assert "REQUIRED TOP NAVIGATION" in captured["user"]


def test_composed_page_prompt_uses_real_component_props_without_bare_render_examples(
        monkeypatch, tmp_path):
    planned = spec()
    context = build_product_context(planned)
    write_product_context(tmp_path, context)
    memory = Memory(tmp_path, planned)
    memory.set_product_context(context)
    captured = {}

    class FakeAnalyzer:
        ok = True

        @staticmethod
        def interface(rel):
            assert rel == "components/features/story-search-filter.tsx"
            return {
                "name": "StorySearchFilter",
                "props": "{ onSearch: (query: string) => void; onRegionFilter: "
                         "(region: string) => void }",
                "found": True,
            }

    agent = SectionAgent(tmp_path, memory, get_analyzer=lambda: FakeAnalyzer())

    def checked(rel, user, **kwargs):
        captured.update({"rel": rel, "user": user, "kwargs": kwargs})
        return "'use client'\nexport default function Journal(){return <main /> }\n"

    monkeypatch.setattr(agent, "_gen_checked", checked)
    agent.generate(planned["pages"][0], "Journal", imports=[
        ("story-search-filter", "@/components/features/story-search-filter"),
    ])
    assert "Their REAL signatures, read from the files" in captured["user"]
    assert "onSearch: (query: string) => void" in captured["user"]
    assert "create and wire the page-owned state/callbacks first" in captured["user"]
    assert "<StorySearchFilter />" not in captured["user"]
    assert "new Date(...).toISOString()" in captured["user"]


def test_architect_schema_nests_model_required_at_object_level():
    model_schema = ARCHITECT_JSON_SCHEMA["properties"]["data_model"]["items"]
    assert model_schema["required"] == ["name", "fields"]
    assert "required" not in model_schema["properties"]


def test_generation_dependency_must_precede_its_consumer():
    planned = spec()
    components = planned["generation_plan"]["components"]
    assert len(components) >= 2
    producer, consumer = components[0], components[1]
    consumer["dependencies"] = [producer["path"]]
    planned["generation_plan"]["dependencyWaves"] = [[consumer["path"]], [producer["path"]]] + [
        wave for wave in planned["generation_plan"]["dependencyWaves"]
        if producer["path"] not in wave and consumer["path"] not in wave]
    issues = validate_spec(planned)
    assert any("must be scheduled before consumer" in issue for issue in issues)


def test_target_selection_is_schema_bound_and_receives_canonical_context(monkeypatch):
    import server

    context = build_product_context(spec())
    captured = {}

    def chat(messages, **kwargs):
        captured["prompt"] = messages[0]["content"]
        captured["kwargs"] = kwargs
        return json.dumps({"targets": ["Journal"]})

    monkeypatch.setattr(server.llm, "chat", chat)
    assert server._decide_targets("Change the journal header", ["Journal"],
                                  prompt_block(context, output_tokens=120), llm.LOCAL_MODEL) == ["Journal"]
    assert context["contextHash"] in captured["prompt"]
    assert "Change the journal header" in captured["prompt"]
    assert captured["kwargs"]["model"] == "nemotron-3-super:cloud"
    assert captured["kwargs"]["route"] == "architect"
    assert "format_schema" not in captured["kwargs"]
    assert '"required":["targets"]' in captured["prompt"]


def test_runtime_failure_happens_before_orchestrator_creates_project(monkeypatch, tmp_path):
    from agents import orchestrator

    target = tmp_path / "must-not-exist"
    monkeypatch.setattr(llm, "runtime_profile", lambda **kwargs: (_ for _ in ()).throw(
        llm.RuntimeProfileError("CPU spill")))
    with pytest.raises(llm.RuntimeProfileError, match="CPU spill"):
        orchestrator.generate_app({}, target, install=False, fix=False)
    assert not target.exists()


def test_staging_publish_keeps_old_project_until_green_swap(monkeypatch, tmp_path):
    import server

    monkeypatch.setattr(server, "PROD_DIR", tmp_path)
    target = tmp_path / "demo"
    target.mkdir()
    (target / "version.txt").write_text("old", encoding="utf-8")
    stage = server._prepare_staging("demo")
    (stage / "version.txt").write_text("green", encoding="utf-8")
    assert (target / "version.txt").read_text() == "old"
    published = server._publish_staging("demo", stage)
    assert published == target
    assert (target / "version.txt").read_text() == "green"
    assert not (tmp_path / ".demo.locode-backup").exists()


def test_windows_locked_directory_uses_child_move_publish_fallback(monkeypatch, tmp_path):
    from agents.publish import publish_stage

    stage = tmp_path / ".demo.staging"
    target = tmp_path / "demo"
    backup = tmp_path / ".demo.backup"
    component_dir = stage / "components"
    component_dir.mkdir(parents=True)
    (component_dir / "Page.tsx").write_text("export default function Page(){}", encoding="utf-8")
    (stage / "package.json").write_text("{}", encoding="utf-8")
    real_rename = Path.rename

    def locked_directory_rename(self, destination):
        if self in {stage, component_dir}:
            raise PermissionError("simulated Windows watcher handle")
        return real_rename(self, destination)

    monkeypatch.setattr(Path, "rename", locked_directory_rename)
    published, residual = publish_stage(stage, target, backup)
    assert published == target
    assert (target / "components" / "Page.tsx").is_file()
    assert (target / "package.json").is_file()
    assert not backup.exists()
    assert residual is False


def test_active_update_pipeline_does_not_use_legacy_template_builder():
    import inspect
    import server

    source = inspect.getsource(server.run_update_pipeline)
    assert "UpdateAgent" in source
    assert "UIBuilder" not in source
    assert "_safe_component" not in source
    assert "suppress_type_errors" not in source


def test_generation_resume_is_hash_bound_and_revalidates_existing_features():
    import inspect
    from agents import orchestrator

    source = inspect.getsource(orchestrator.generate_app)
    assert 'resume_context_hash == product_context.get("contextHash")' in source
    assert "get_analyzer().check(rel, code)" in source
    assert "ca._contract_diagnostics(rel, code)" in source
    assert "reused clean from matching context hash" in source


def test_smoke_resume_restores_only_feature_components_not_failed_pages():
    import inspect
    from scripts import gen_smoketest

    source = inspect.getsource(gen_smoketest.run)
    assert 'glob("components/features/**/*.tsx")' in source
    assert "components/pages/**/*.tsx" not in source
    assert "resume_context_hash=resume_context_hash" in source
