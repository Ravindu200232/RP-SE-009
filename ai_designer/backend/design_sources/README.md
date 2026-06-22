# Local Design Sources

Place shallow-cloned or downloaded open-source design/template repositories in
`template_repos/`. The generator never copies those templates into apps. The
backend scans permissively licensed repos and writes abstract component recipe
summaries to `../.design_recipe_cache.json`.

Only use repos with clear permissive licenses such as MIT, Apache-2.0, BSD, ISC,
CC0, or Unlicense. GPL, AGPL, LGPL, unknown, and missing-license repos are
skipped by default.
