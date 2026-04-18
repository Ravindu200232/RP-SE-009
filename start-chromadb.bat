@echo off
echo Starting ChromaDB vector database for bug memory...
echo.

REM Check if chromadb is installed
python -c "import chromadb" 2>nul
if errorlevel 1 (
    echo [SETUP] Installing chromadb...
    pip install chromadb
)

REM Create data directory
if not exist "chroma-data" mkdir chroma-data

echo [ChromaDB] Starting on port 8001...
echo [ChromaDB] Data stored in: chroma-data\
echo [ChromaDB] Bug fix memory will be saved here across sessions.
echo.
echo Press Ctrl+C to stop ChromaDB.
echo.

chroma run --path ./chroma-data --port 8001
