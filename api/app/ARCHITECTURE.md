# Agent 1 API Structure

This backend is split so developers can edit one concern at a time.

## Entry points

- `api_entry.py`: active FastAPI app and route wiring
- `main.py`: compatibility wrapper for `uvicorn app.main:app`

## Core modules

- `config.py`: runtime flags, dataset/template paths, question defaults
- `state.py`: in-memory session store and template/dataset caches
- `schemas.py`: request models
- `common.py`: shared helpers, dataset/template loading, upload parsing

## AI and requirement flow

- `orchestrator.py`: Ollama / DeepSeek / LangChain / LangGraph orchestration helpers
- `question_maker.py`: interview planning, question normalization, coverage tracking

## SRS generation

- `srs_sections.py`: section builders and AI content-pack merging
- `srs_generator.py`: SRS generation, stack recommendation, validation
- `session_service.py`: session persistence, PDF export, artifact delivery helpers

## Typical edit guide

- Change interview questions: `question_maker.py`
- Change model orchestration or AI prompts: `orchestrator.py` and `srs_generator.py`
- Change IEEE section layout: `srs_sections.py`
- Change API route behavior: `api_entry.py`
- Change storage / export behavior: `session_service.py`
