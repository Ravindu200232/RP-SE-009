#!/usr/bin/env python3
"""Load the server modules into the legacy shared runtime namespace."""
from __future__ import annotations

from pathlib import Path

# Order matters because these files share one runtime namespace.
_RUNTIME_PARTS = (
    # 1) Shared process state and development-server lifecycle.
    'server_modules/core/startup/bootstrap.py',
    'server_modules/core/runtime/stream_events.py',
    'server_modules/core/runtime/model_runtime.py',
    'server_modules/core/runtime/dependencies.py',
    'server_modules/core/runtime/process_cleanup.py',
    'server_modules/core/runtime/next_preview.py',

    # 2) Builder repair + QA helpers + SRS/deployment sidecars.
    'agents/pipeline/build/project_preview.py',
    'agents/pipeline/build/runtime_faults.py',
    'agents/pipeline/build/build_fix_loop.py',
    'qa_agent/server/unit_support.py',
    'qa_agent/server/feature_unit.py',
    'server_modules/srs/srs_runtime.py',
    'server_modules/deploy/deploy_runtime.py',
    'qa_agent/server/unit_stage.py',
    'qa_agent/server/e2e_stage.py',
    'qa_agent/server/e2e_final.py',
    'qa_agent/server/runtime_repair.py',

    # 3) Images, verification, bug repair, and the main build pipeline.
    'agents/features/runtime/images/image_service.py',
    'agents/features/runtime/images/image_planning.py',
    'agents/features/runtime/images/image_completion.py',
    'qa_agent/server/verification.py',
    'agents/pipeline/bugs/bug_request.py',
    'agents/pipeline/bugs/bug_workflow.py',
    'agents/pipeline/bugs/bug_verification.py',
    'agents/pipeline/build/runtime_and_tests.py',
    'agents/pipeline/build/final_quality.py',
    'agents/pipeline/build_pipeline.py',
    'agents/pipeline/feature_safety.py',

    # 4) Post-build editing tools: Feature, image, Selection, Pencil.
    'agents/features/runtime/feature_update.py',
    'agents/features/runtime/image_edit.py',
    'agents/features/runtime/selection/selection_scope.py',
    'agents/features/runtime/selection/selection_repair.py',
    'agents/features/runtime/selection/selection_workflow.py',
    'agents/features/runtime/pencil/pencil_writer.py',
    'agents/features/runtime/pencil/pencil_workflow.py',
    'agents/features/runtime/pencil/page_update.py',

    # 5) Project requests and public HTTP/WebSocket endpoints.
    'agents/server/projects/project_files.py',
    'agents/server/projects/project_socket.py',
    'server_modules/ui/http_base.py',
    'server_modules/ui/handler/response_helpers.py',
    'server_modules/ui/handler/request_router.py',
    'server_modules/ui/handler/api_get.py',
    'server_modules/ui/handler/api_post.py',
    'server_modules/ui/handler/proxy_routes.py',
    'server_modules/ui/http_handler.py',
    'server_modules/srs/srs_api.py',
    'server_modules/deploy/deploy_api.py',
    'server_modules/core/endpoints/jobs.py',
    'server_modules/deploy/jobs.py',
    'server_modules/core/endpoints/main.py',
)


def _load_runtime_parts() -> None:
    root = Path(__file__).resolve().parent
    namespace = globals()
    for relative_path in _RUNTIME_PARTS:
        path = root / relative_path
        source = path.read_text(encoding="utf-8")
        exec(compile(source, str(path), "exec"), namespace, namespace)


_load_runtime_parts()
