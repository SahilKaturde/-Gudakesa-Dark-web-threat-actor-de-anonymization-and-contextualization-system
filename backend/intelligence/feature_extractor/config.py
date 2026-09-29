"""
extractor/config.py
Central configuration settings for Darkweb Feature Extractor.
"""
import os

# -----------------------------------------------------------------------
# Ollama / LLM Settings (qwen3:1.7b)
# -----------------------------------------------------------------------
OLLAMA_HOST = os.getenv("OLLAMA_HOST", "http://localhost:11434")
OLLAMA_GENERATE_URL = f"{OLLAMA_HOST}/api/generate"
OLLAMA_TAGS_URL = f"{OLLAMA_HOST}/api/tags"
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "qwen3:1.7b")

LLM_TEMPERATURE = 0.1
LLM_TOP_P = 0.9
LLM_MAX_TOKENS = 512
LLM_NUM_CTX = 4096
LLM_REQUEST_TIMEOUT = 45

# -----------------------------------------------------------------------
# Text Chunking for Small Context Models (1.7B)
# -----------------------------------------------------------------------
CHUNK_SIZE = 1500
CHUNK_OVERLAP = 400

# -----------------------------------------------------------------------
# Extraction & Fallback Thresholds
# -----------------------------------------------------------------------
MIN_FEATURES_REGEX = 3
REVIEW_MIN_COMMENT_LEN = 3

# -----------------------------------------------------------------------
# Output File Defaults
# -----------------------------------------------------------------------
DEFAULT_OUTPUT_DIR = "extracted"
FEATURES_JSON_FILENAME = "features.json"
INTEL_REPORT_MD_FILENAME = "intel_report.md"
