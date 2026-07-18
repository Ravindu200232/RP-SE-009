#!/bin/bash
# ──────────────────────────────────────────────────────────
# Web Agent Pipeline — Setup & Run Script
# ──────────────────────────────────────────────────────────

set -e

echo "🤖 Web Agent Pipeline Setup"
echo "══════════════════════════════════════"

# Check Python
if ! command -v python3 &> /dev/null; then
    echo "❌ Python 3 is required but not found. Install Python 3.9+ first."
    exit 1
fi

echo "✅ Python: $(python3 --version)"

# Check Ollama
if ! command -v ollama &> /dev/null; then
    echo "❌ Ollama not found. Install from https://ollama.ai"
    exit 1
fi

echo "✅ Ollama: found"

# Check if Ollama is running
if ! curl -s http://localhost:11434/api/tags > /dev/null 2>&1; then
    echo "⚠️  Ollama is not running. Starting it..."
    ollama serve &
    sleep 3
fi

echo "✅ Ollama: running"

# Check available models
echo ""
echo "📦 Available Ollama models:"
ollama list 2>/dev/null || echo "  (none yet)"

echo ""
echo "💡 Required: ollama pull gemma4:12b"
echo "   Locode is pinned to the local Gemma 4 12B Q4_K_M tag."
echo ""

# Install Python dependencies
echo "📥 Installing Python dependencies..."
pip3 install -r requirements.txt --quiet

echo "✅ Dependencies installed"

# Create necessary directories
mkdir -p ideas production-ready logs

echo ""
echo "══════════════════════════════════════"
echo "✅ Setup complete!"
echo ""
echo "📝 Model routing is read-only: gemma4:12b for every LLM stage."
echo "   Legacy model request fields are accepted but ignored."
echo ""
echo "🚀 To start the pipeline:"
echo "   python3 pipeline.py"
echo ""
echo "💡 Then drop a .txt file into the 'ideas/' folder!"
echo "   Example ideas are already in ideas/ for you to try."
echo "══════════════════════════════════════"
