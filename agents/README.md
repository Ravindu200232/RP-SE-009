# Agent pipeline

This folder turns one product request into a planned, built, checked app.
Read the packages in this order:

1. `server` accepts the request and owns the end-to-end run.
2. `planner` turns the request or SRS into requirements and a file map.
3. `build` writes the planned files, cleans them, and installs dependencies.
4. `data` starts MongoDB and prepares isolated project data.
5. `analysis` compares the app with its plan and reports real gaps.
6. `features` makes later, tightly scoped changes to an existing app.
7. `core` supplies cancellation, commands, model calls, and file tools.

## New app flow

```text
request or SRS
  -> server.agent_pipeline.run_agent_pipeline
  -> planner.PlannerAgent
  -> planner.ArchitectAgent
  -> build.BuilderAgent
  -> dependency install and production build
  -> analysis.AnalyzerAgent
  -> unit, runtime, API, role, E2E, security, and performance checks
  -> live preview and final quality receipt
```

`run_agent_pipeline` is the public entry point. Its numbered comments follow
the same order as this map. Repair steps always use observed errors or plan
evidence; they do not guess new product requirements.

## Existing app change flow

```text
user change
  -> server.scope_map selects the smallest safe source set
  -> features plans and applies the change
  -> analysis checks the affected routes and contracts
  -> server restarts or repairs only when the evidence requires it
```

Pencil edits begin with `features.capture` and `features.picker`. Chat bug
reports begin in `server.chat_bugfix`. Both flows join the same scoped apply
and verification path.

## Where to start reading

| Goal | Start here |
| --- | --- |
| Understand a full build | `server/agent_pipeline.py` |
| Understand requirements | `planner/planning.py` |
| Understand file generation | `planner/architecture.py` |
| Understand code writing | `build/builder_generation.py` |
| Understand verification | `analysis/analyzer.py` |
| Understand repair | `server/build_repair.py` |
| Understand feature edits | `server/feature_actions.py` |
| Understand database setup | `data/mongo_lifecycle.py` |

Keep comments short and explain why a stage exists. Function names explain
what happens. Prompt details belong in the package prompt Markdown files, not
in long Python comments.
