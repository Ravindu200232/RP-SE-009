from __future__ import annotations

from .integrations import IntegrationService
from .models import PackageRequest
from .service import Agent4Service


def create_app():
    try:
        from fastapi import FastAPI, HTTPException
        from fastapi.middleware.cors import CORSMiddleware
        from fastapi.responses import FileResponse
    except ModuleNotFoundError as exc:
        raise RuntimeError("FastAPI is not installed. Install requirements.txt before running the API.") from exc

    app = FastAPI(title="Agent 4", version="1.1.0")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    service = Agent4Service()
    integrations = IntegrationService()

    @app.get("/health")
    def health():
        return {"status": "ok", "service": "agent4"}

    @app.get("/integrations/status")
    def integration_status():
        """Return credential-presence and CLI-auth diagnostics without secrets."""
        try:
            return integrations.statuses()
        except Exception as exc:  # pragma: no cover - defensive endpoint guard
            raise HTTPException(status_code=500, detail=str(exc)) from exc

    @app.post("/package")
    def package(payload: dict):
        try:
            request = PackageRequest.from_dict(payload)
            result = service.process(request)
            return result.to_dict()
        except KeyError as exc:
            raise HTTPException(status_code=400, detail=f"Missing required field: {exc.args[0]}") from exc
        except Exception as exc:  # pragma: no cover - defensive endpoint guard
            raise HTTPException(status_code=500, detail=str(exc)) from exc

    @app.get("/inputs")
    def inputs():
        try:
            return service.list_input_candidates()
        except Exception as exc:  # pragma: no cover - defensive endpoint guard
            raise HTTPException(status_code=500, detail=str(exc)) from exc

    @app.get("/jobs/{job_id}")
    def job(job_id: str):
        result = service.get_job(job_id)
        if not result:
            raise HTTPException(status_code=404, detail="Job not found.")
        return result

    @app.get("/download/{job_id}")
    def download(job_id: str):
        file_path = service.download_path(job_id)
        if not file_path:
            raise HTTPException(status_code=404, detail="Download not found.")
        return FileResponse(path=file_path, filename=file_path.name, media_type="application/zip")

    return app
