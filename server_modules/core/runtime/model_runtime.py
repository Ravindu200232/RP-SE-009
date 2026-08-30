# Model Runtime: one focused part of the development-server lifecycle.
# Purpose: Make sure the selected AI model is ready before generation starts.
def ensure_model(model: str) -> bool:
    """Check Ollama tags; pull model if missing. Returns True if ready."""

    if is_cloud_model(model):

        # No weights to fetch, but the daemon only proxies a cloud model it
        # has been asked for, so an unregistered one is registered first. With
        # an API key has_model() is already true and nothing is pulled.
        if not ollama.has_model(model):
            elog("INFO", f"   ☁️  Registering cloud model {model} "
                         f"(no download — cloud models carry no weights)…")
            if ollama.pull(model):
                elog("INFO", f"   ✅ {model} registered")
            else:
                elog("WARN", f"   ⚠️  Could not register {model} with "
                             f"Ollama — trying the call anyway")

        via = "API key" if ollama.api_key else \
              "signed-in Ollama" if ollama.signed_in() else None
        if via:
            elog("INFO", f"   ☁️  Cloud model ready: {model} via {via} "
                         f"(ctx {max_context(model):,})")
        else:

            elog("WARN", f"   ☁️  {model}: no API key and Ollama isn't signed "
                         f"in — trying anyway")
        return True

    if ollama.has_model(model):
        elog("INFO", f"   ✅ Model ready: {model}")
        return True

    elog("INFO", f"   📥 Pulling {model} from Ollama (first time only)…")
    ok = ollama.pull(model, on_progress=lambda p: elog("INFO", f"   📥 {model}: {p}%"))
    if ok:
        elog("INFO", f"   ✅ {model} pulled!")
    else:
        elog("ERROR", f"   ❌ Pull failed: {model}")
    return ok

# Purpose: Unload model from VRAM immediately after use.
def stop_model(model: str):
    """Unload model from VRAM immediately after use."""
    if is_cloud_model(model):
        return
    ollama.unload(model)
    elog("INFO", f"   🗑️  Unloaded {model}")

