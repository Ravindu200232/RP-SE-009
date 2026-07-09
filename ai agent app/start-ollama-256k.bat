@echo off
title Ollama - deepseek-r1:8b (thinking ON, q8_0 KV, 100%% GPU)
color 0B
REM ===================================================================
REM  Flash Attention + a quantized KV cache keep the model 100%% on the GPU.
REM  Model: deepseek-r1:8b (thinking ON). Its MAX context is 128K (131072) —
REM  there is NO 256K (that was gemma4:12b).
REM  Current builder default (.env.local): 32K everywhere
REM    OLLAMA_NUM_CTX=32768    (planner)
REM    OLLAMA_CODE_CTX=32768   (code steps)
REM  WHY 32K, not 128K: at NUM_PARALLEL=2 the q8_0 KV cache is ~2GB/slot at 32K
REM  (fits 12GB, 100%% GPU) but ~8GB/slot at 128K (needs ~20GB -> heavy CPU spill
REM  -> GPU sits ~32%% and generation crawls). Do NOT raise the context here.
REM
REM  Keep this window OPEN while you use AI Web Builder.
REM ===================================================================

REM q8_0 ~halves the KV-cache memory at near-full quality (keeps it on the GPU).
REM Only drop to q4_0 (quarters it) if you must push context higher on this card.
set OLLAMA_FLASH_ATTENTION=1
set OLLAMA_KV_CACHE_TYPE=q8_0
REM Parallel slots: the GPU batches concurrent requests (model weights read
REM once for all of them). RTX 3060 12GB is stable at 2 slots with 32K code
REM context; 3 slots can fail allocating pinned host KV buffers. The builder's
REM BUILD_CONCURRENCY (.env.local) must match this number.
set OLLAMA_NUM_PARALLEL=2
set OLLAMA_MAX_LOADED_MODELS=1

echo Stopping any running Ollama instance...
taskkill /F /IM ollama.exe >nul 2>&1
timeout /t 2 /nobreak >nul

echo.
echo Starting Ollama  (FlashAttention=ON, KV cache=%OLLAMA_KV_CACHE_TYPE%, parallel=%OLLAMA_NUM_PARALLEL%)
echo Leave this window open, then start the builder with: pnpm dev
echo.
ollama serve
