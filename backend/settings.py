"""Runtime settings from the environment / .env (gitignored). Defaults match .env.example."""
import os
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
load_dotenv(ROOT / ".env")

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://kg:kg@localhost:5433/kg")
OLLAMA_URL = os.getenv("OLLAMA_URL", "http://localhost:11435")
LLM_MODEL = os.getenv("LLM_MODEL", "qwen3.5:4b")
EMBED_MODEL = os.getenv("EMBED_MODEL", "embeddinggemma")
RAW_HPE_DIR = ROOT / "data" / "raw" / "hpe"
