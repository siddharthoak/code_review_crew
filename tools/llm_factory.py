"""
tools/llm_factory.py

Single source of truth for LLM and embedding model instantiation.
Swap providers by setting LLM_PROVIDER in .env — no code changes needed.

Supported providers:
    ollama   → local Ollama (zero API cost, runs on your machine)
    openai   → OpenAI API (for staging / production)

Usage:
    from tools.llm_factory import get_llm, get_embedding_model, get_crewai_llm

Environment variables:
    LLM_PROVIDER            = ollama | openai          (default: ollama)
    OLLAMA_BASE_URL         = http://localhost:11434   (default)
    OLLAMA_LLM_MODEL        = llama3.2                 (default)
    OLLAMA_EMBED_MODEL      = nomic-embed-text         (default)
    OPENAI_API_KEY          = sk-...                   (required for openai)
    OPENAI_LLM_MODEL        = gpt-4o-mini              (default)
    OPENAI_EMBED_MODEL      = text-embedding-3-small   (default)
"""

from __future__ import annotations

import os

from dotenv import load_dotenv

load_dotenv()

# ── Read config ───────────────────────────────────────────────────────────────

PROVIDER        = os.getenv("LLM_PROVIDER", "ollama").lower()
OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
OLLAMA_LLM      = os.getenv("OLLAMA_LLM_MODEL", "llama3.2")
OLLAMA_EMBED    = os.getenv("OLLAMA_EMBED_MODEL", "nomic-embed-text")
OPENAI_LLM      = os.getenv("OPENAI_LLM_MODEL", "gpt-4o-mini")
OPENAI_EMBED    = os.getenv("OPENAI_EMBED_MODEL", "text-embedding-3-small")


# ── LlamaIndex LLM ────────────────────────────────────────────────────────────

def get_llm():
    """
    Return a LlamaIndex-compatible LLM instance for the configured provider.
    Used in RAG tool and ingestion pipeline.
    """
    if PROVIDER == "ollama":
        from llama_index.llms.ollama import Ollama
        return Ollama(
            model=OLLAMA_LLM,
            base_url=OLLAMA_BASE_URL,
            request_timeout=120.0,
        )
    # openai (default fallback)
    from llama_index.llms.openai import OpenAI
    return OpenAI(model=OPENAI_LLM, temperature=0)


# ── LlamaIndex Embedding model ────────────────────────────────────────────────

def get_embedding_model():
    """
    Return a LlamaIndex-compatible embedding model for the configured provider.

    ⚠ Embedding dimension must match what was used during ingestion.
       If you switch providers, re-run ingestion with --recreate to rebuild
       the Qdrant collection with the correct vector dimensions.

    Dimensions:
        nomic-embed-text       →  768
        mxbai-embed-large      → 1024
        text-embedding-3-small → 1536
        text-embedding-3-large → 3072
    """
    if PROVIDER == "ollama":
        from llama_index.embeddings.ollama import OllamaEmbedding
        return OllamaEmbedding(
            model_name=OLLAMA_EMBED,
            base_url=OLLAMA_BASE_URL,
        )
    from llama_index.embeddings.openai import OpenAIEmbedding
    return OpenAIEmbedding(model=OPENAI_EMBED)


def get_embedding_dim() -> int:
    """
    Return the vector dimension for the current embedding model.
    Used when creating Qdrant collections.
    """
    dim_map = {
        "nomic-embed-text":       768,
        "mxbai-embed-large":      1024,
        "all-minilm":             384,
        "text-embedding-3-small": 1536,
        "text-embedding-3-large": 3072,
        "text-embedding-ada-002": 1536,
    }
    model = OLLAMA_EMBED if PROVIDER == "ollama" else OPENAI_EMBED
    return dim_map.get(model, 768)   # safe default for unknown Ollama models


# ── CrewAI LLM ────────────────────────────────────────────────────────────────

def get_crewai_llm():
    """
    Return an LLM string or object compatible with CrewAI's `llm=` parameter.

    CrewAI uses LiteLLM under the hood, so Ollama models are addressed as
    'ollama/<model_name>' and pointed at the local base URL via env var.
    """
    if PROVIDER == "ollama":
        # LiteLLM reads OLLAMA_API_BASE from environment
        os.environ.setdefault("OLLAMA_API_BASE", OLLAMA_BASE_URL)
        return f"ollama/{OLLAMA_LLM}"

    # OpenAI — CrewAI picks up OPENAI_API_KEY automatically
    return OPENAI_LLM


# ── Convenience summary ───────────────────────────────────────────────────────

def print_provider_info() -> None:
    """Print current LLM config — call from main.py on startup."""
    if PROVIDER == "ollama":
        print(
            f"[LLM] Ollama  →  {OLLAMA_BASE_URL}  "
            f"(LLM: {OLLAMA_LLM}  |  Embed: {OLLAMA_EMBED}  |  Dim: {get_embedding_dim()})"
        )
    else:
        print(
            f"[LLM] OpenAI  →  "
            f"(LLM: {OPENAI_LLM}  |  Embed: {OPENAI_EMBED}  |  Dim: {get_embedding_dim()})"
        )