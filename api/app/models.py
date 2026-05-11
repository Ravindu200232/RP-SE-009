from __future__ import annotations

from typing import Any, Literal, Optional

from pydantic import BaseModel, Field


class GenerateRequest(BaseModel):
    source_path: str = Field(..., description="Absolute path to a Node service or a folder containing services")
    framework: Literal["jest"] = "jest"
    overwrite: bool = False


class RunRequest(BaseModel):
    source_path: str
    install: bool = True


class DiscoveredFile(BaseModel):
    path: str
    relative: str
    service: str
    bytes: int


class FunctionInfo(BaseModel):
    name: str
    kind: Literal["function", "arrow", "method", "export-default"]
    params: list[str] = []
    snippet: str = ""


class GeneratedTest(BaseModel):
    source_file: str
    test_file: str
    function_count: int
    test_count: int
    used_llm: bool
    preview: str


class ServiceInfo(BaseModel):
    name: str
    path: str
    module_kind: Literal["cjs", "esm"]
    file_count: int
    function_count: int
    has_dependencies: bool
    framework_hint: Optional[str] = None  # "express" | "nest" | "fastify" | None


class ScanResult(BaseModel):
    root: str
    services: list[ServiceInfo] = []
    files: list[DiscoveredFile] = []
    total_services: int = 0
    total_files: int = 0
    total_functions: int = 0
    duration_ms: float = 0.0


class TestResult(BaseModel):
    name: str
    status: Literal["passed", "failed", "skipped", "pending"]
    duration_ms: float = 0.0
    failure_message: Optional[str] = None


class FileResult(BaseModel):
    file: str
    passed: int
    failed: int
    total: int
    tests: list[TestResult] = []


class JestSummary(BaseModel):
    services_tested: list[str] = []
    files: list[FileResult] = []
    total_tests: int = 0
    total_passed: int = 0
    total_failed: int = 0
    total_skipped: int = 0
    duration_ms: float = 0.0


class RunStatus(BaseModel):
    run_id: str
    phase: str
    status: Literal["pending", "running", "completed", "failed"]
    logs: list[str] = []
    discovered: list[DiscoveredFile] = []
    generated: list[GeneratedTest] = []
    summary: Optional[JestSummary] = None
    error: Optional[str] = None
    started_at: float = 0.0
    finished_at: Optional[float] = None
    used_llm: bool = False


class HealthResponse(BaseModel):
    ok: bool
    service: str
    langchain: bool
    langgraph: bool
    llm_provider: Optional[str] = None
    node_available: bool = False
