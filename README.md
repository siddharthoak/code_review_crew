# AI Code Review Crew

A multi-agent code review system built with **CrewAI** + **LlamaIndex (RAG)** + **Qdrant**.
Produces structured review reports written to disk as Markdown, with optional Google Docs export.

---

## Architecture

```
code_review_crew/
├── agents/               # Self-contained agent modules
│   ├── security_auditor.py        → OWASP RAG-backed security review
│   ├── architecture_reviewer.py   → ADR RAG-backed arch review
│   ├── test_coverage_reviewer.py  → Test gap analysis
│   ├── documentation_reviewer.py  → Docstring/type hint review
│   └── summary_agent.py           → Synthesizes all findings
│
├── tools/                # Reusable tools (shared across crews)
│   ├── rag.py            → RAGTool (LlamaIndex + Qdrant)
│   ├── code_parser.py    → Parses files, diffs, snippets
│   └── llm_factory.py    → Swaps Ollama ↔ OpenAI via LLM_PROVIDER env var
│
├── crews/
│   └── code_review_crew.py        → Wires agents + tasks into CrewAI Crew
│
├── exporters/            # Plugin-style output (add Confluence, Notion, etc.)
│   ├── base.py           → BaseExporter + ReviewReport dataclass
│   ├── markdown.py       → Local .md file export (default)
│   └── google_docs.py    → Google Docs API export (opt-in)
│
├── config/
│   ├── agents.yaml       → Agent personas and goals
│   └── tasks.yaml        → Task descriptions and expected outputs
│
├── ingestion/
│   └── ingest.py         → CLI to index docs into Qdrant
│
├── knowledge_base/
│   ├── owasp/            → OWASP standards docs
│   └── standards/        → Org ADRs and coding standards
│
└── main.py               → CLI entry point
```

---

## Setup

### 1. Prerequisites

- Python 3.12
- Docker + Docker Compose
- [Ollama](https://ollama.com/download) (free, local — default LLM provider)
- OpenAI API key (optional — only needed when `LLM_PROVIDER=openai`)

### 2. Install dependencies with Poetry

```bash
# Install Poetry if not already installed
curl -sSL https://install.python-poetry.org | python3 -

# Install project dependencies
poetry config virtualenvs.in-project true
poetry install

# Activate the virtualenv
poetry shell
```

### 3. Configure environment

```bash
cp .env.example .env
# Default config uses Ollama — no API key needed for local dev
```

Key variables in `.env`:

```bash
LLM_PROVIDER=ollama              # switch to "openai" for production
OLLAMA_LLM_MODEL=llama3.2
OLLAMA_EMBED_MODEL=nomic-embed-text
```

### 4. Pull Ollama models

```bash
ollama pull llama3.2
ollama pull nomic-embed-text
```

### 5. Start the full stack

```bash
docker compose up -d
# Starts: Qdrant (6333) · MySQL (3307) · Redis (6380) · app
```

### 6. Download and ingest the knowledge base

```bash
chmod +x fetch_kb.sh && ./fetch_kb.sh

python main.py ingest owasp_standards --dir knowledge_base/owasp
python main.py ingest org_adrs --dir knowledge_base/standards
```

Add your own org ADRs to `knowledge_base/standards/` before ingesting.

### 7. Configure Google Docs export (optional)

1. Go to [Google Cloud Console](https://console.cloud.google.com)
2. Create a project → Enable **Google Docs API** and **Google Drive API**
3. Create OAuth2 credentials → Desktop App → Download JSON
4. Save to `credentials/google_oauth_credentials.json`
5. First run opens a browser for OAuth consent; token is cached after that.

---

## Usage

### Review a file (report saved to `./reports/`)
```bash
python main.py review --file src/my_service.py --context "PR #142"
```

### Review a git diff
```bash
git diff HEAD~1 > /tmp/changes.diff
python main.py review --diff /tmp/changes.diff
```

### Review an inline snippet
```bash
python main.py review \
  --snippet "def get_user(id): return db.query(f'SELECT * FROM users WHERE id={id}')"
```

### Also push to Google Docs
```bash
python main.py review --file src/auth.py --context "SEC-204" --google-docs
```

### Custom output directory
```bash
python main.py review --file src/auth.py --output-dir /tmp/reviews
```

### Via Docker
```bash
docker compose exec app python main.py review --file /app/src/service.py
```

---

## LLM Provider

Switch between Ollama (free, local) and OpenAI (cloud) with one env var:

```bash
# Local development — no cost
LLM_PROVIDER=ollama
OLLAMA_LLM_MODEL=llama3.2           # or deepseek-coder for better code review
OLLAMA_EMBED_MODEL=nomic-embed-text

# Staging / production
LLM_PROVIDER=openai
OPENAI_API_KEY=sk-...
```

> ⚠ If you change `OLLAMA_EMBED_MODEL` after ingestion, re-run ingest with `--recreate`
> since Qdrant vector dimensions must match the embedding model.

---

## How RAG Works in This System

Two Qdrant collections are used:

| Collection | Used by | Content |
|---|---|---|
| `owasp_standards` | SecurityAuditorAgent | OWASP Top 10, CVE patterns, Python-specific vulnerability patterns |
| `org_adrs` | ArchitectureReviewerAgent | Your org's ADRs, coding standards, design patterns |

Before reviewing, each agent calls `RAGTool` to retrieve the most relevant
guidelines for what it observes in the code.

### Adding a new knowledge base

```python
# tools/rag.py — add:
test_patterns_rag_tool = RAGTool(collection_name="test_patterns")

# agents/test_coverage_reviewer.py — attach it:
tools=[test_patterns_rag_tool]

# Ingest:
python main.py ingest test_patterns --dir knowledge_base/test_patterns
```

---

## Extending with New Agents (Example: Performance Reviewer)

1. **Create the agent:**
```python
# agents/performance_reviewer.py
from crewai import Agent

def build_performance_reviewer(config: dict) -> Agent:
    return Agent(
        role=config["role"],
        goal=config["goal"],
        backstory=config["backstory"],
        tools=[],
        verbose=True,
    )
```

2. **Add config to `config/agents.yaml`:**
```yaml
performance_reviewer:
  role: "Performance Engineering Specialist"
  goal: "Identify N+1 queries, O(n²) algorithms, memory leaks..."
  backstory: "..."
```

3. **Add task to `config/tasks.yaml`:**
```yaml
performance_review:
  description: "Review for performance issues in: {code_snippet}..."
  expected_output: "Performance findings with Big-O analysis..."
```

4. **Wire into the crew (`crews/code_review_crew.py`):**
```python
from agents import build_performance_reviewer

perf_agent = build_performance_reviewer(agents_cfg["performance_reviewer"])
perf_task = Task(description=..., agent=perf_agent)
```

That's it. No other files change.

---

## Phase 2: Bug Triage Crew

Reused without modification:
- `tools/rag.py`, `tools/code_parser.py`, `exporters/`, `ingestion/ingest.py`

New additions only:
- `crews/bug_triage_crew.py` (LangGraph-based for retry loops)
- `agents/bug_parser.py`, `agents/root_cause.py`, `agents/impact_analysis.py`
- `knowledge_base/bug_history/`, `knowledge_base/codebase/`

---

## Adding New Exporters

```python
# exporters/confluence.py
from .base import BaseExporter, ReviewReport

class ConfluenceExporter(BaseExporter):
    def export(self, report: ReviewReport) -> str:
        # Push to Confluence REST API
        return "https://your-org.atlassian.net/wiki/..."
```

Register in `exporters/__init__.py` and add `--confluence` flag to `main.py`.
