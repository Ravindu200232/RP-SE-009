"""Verify the 100+ section catalog: (1) the registry has >=100 templates,
(2) EVERY template compiles as valid JSX in isolation, (3) randomly composed
landing pages (hero + catalog middles + footer) compile. Uses the same
validate_jsx.js (@babel/parser) the live build pipeline uses."""
import os, sys, subprocess, random, tempfile
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from app import section_catalog, section_bank, design_library

VALID = os.path.join(os.path.dirname(os.path.abspath(__file__)), "validate_jsx.js")


def valid_jsx(src: str) -> tuple[bool, str]:
    src = src.replace("ACCENT", "indigo")           # mimic the theme recolour
    fd, path = tempfile.mkstemp(suffix=".jsx"); os.close(fd)
    with open(path, "w", encoding="utf-8") as f:
        f.write(src)
    try:
        r = subprocess.run(f'node "{VALID}" "{path}"', shell=True, capture_output=True, text=True, timeout=40)
        return r.returncode == 0, (r.stderr or r.stdout or "")[:160]
    finally:
        os.remove(path)


print(f"Catalog size: {section_catalog.count()} templates  (target >= 100)")
assert section_catalog.count() >= 100, "catalog under 100"

# 1) every template valid in isolation
bad = []
for e in section_catalog.CATALOG:
    src = section_bank._HEADER + section_catalog.render(e, "S").rstrip() + \
        "\n\nexport default function Home() { return <S />; }\n"
    ok, err = valid_jsx(src)
    if not ok:
        bad.append((e["key"], err))
print(f"Per-template JSX: {section_catalog.count() - len(bad)}/{section_catalog.count()} valid")
for k, err in bad[:10]:
    print("  INVALID", k, "->", err)

# 2) composed landings across many heroes + prompts
prompts = ["a SaaS analytics platform for teams", "a cleaning service company",
           "an online clothing store", "a restaurant booking site", "a school LMS portal",
           "a photography studio gallery", "a fitness gym membership app", "a fintech dashboard"]
comp_bad, n_comp = [], 0
for seed in range(24):
    rng = random.Random(seed)
    hero = rng.choice(section_bank.HEROES)[1]
    desc, src, _used = section_bank.compose_landing(rng=rng, hero_file=hero, prompt_text=rng.choice(prompts))
    n_comp += 1
    ok, err = valid_jsx(src)
    if not ok:
        comp_bad.append((seed, desc[:40], err))
print(f"Composed pages : {n_comp - len(comp_bad)}/{n_comp} valid")
for s, d, err in comp_bad[:8]:
    print("  INVALID page seed", s, d, "->", err)

# show how varied selection is (recommended method = input-matched + random)
print("\nSample compositions (note how middles change with the prompt):")
for p in prompts[:4]:
    rng = random.Random(7)
    desc, _, _used = section_bank.compose_landing(rng=rng, prompt_text=p)
    print(f"  [{p[:34]:34}] -> {desc}")

print("\n" + "=" * 64)
total_ok = (len(bad) == 0 and len(comp_bad) == 0 and section_catalog.count() >= 100)
print(f"RESULT: catalog={section_catalog.count()} | per-template={section_catalog.count()-len(bad)}/{section_catalog.count()} | composed={n_comp-len(comp_bad)}/{n_comp}")
print("ALL GREEN [OK]" if total_ok else "FAILURES ABOVE [X]")
