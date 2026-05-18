# AI Code Review Crew

A multi-agent code review system built with **CrewAI** + **LlamaIndex (RAG)** + **Qdrant**.
Produces structured review reports exportable directly to **Google Docs** or Markdown.

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
│   └── code_parser.py    → Parses files, diffs, snippets
│
├── crews/
│   └── code_review_crew.py        → Wires agents + tasks into CrewAI Crew
│
├── exporters/            # Plugin-style output (add Confluence, Notion, etc.)
│   ├── base.py           → BaseExporter + ReviewReport dataclass
│   ├── markdown.py       → Local .md file export
│   └── google_docs.py    → Google Docs API export
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

- Python 3.11+
- Docker (for local Qdrant)
- OpenAI API key
- Google Cloud project with Docs + Drive APIs enabled (for Google Docs export)

### 2. Install dependencies

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### 3. Configure environment

```bash
cp .env.example .env
# Edit .env and fill in OPENAI_API_KEY and Qdrant settings
```

### 4. Start Qdrant locally

```bash
docker run -p 6333:6333 -p 6334:6334 \
  -v $(pwd)/qdrant_storage:/qdrant/storage \
  qdrant/qdrant
```

### 5. Ingest knowledge base

```bash
python main.py ingest owasp_standards --dir knowledge_base/owasp
python main.py ingest org_adrs --dir knowledge_base/standards
```

Add your own org's ADRs and coding standards to `knowledge_base/standards/`
before ingesting. The more context you add, the more relevant the architecture
reviews will be.

### 6. Configure Google Docs export (optional)

1. Go to [Google Cloud Console](https://console.cloud.google.com)
2. Create a project → Enable **Google Docs API** and **Google Drive API**
3. Create OAuth2 credentials → Desktop App → Download JSON
4. Save to `credentials/google_oauth_credentials.json`
5. First run will open a browser for OAuth consent; token is cached after that.

---

## Usage

### Review a Python file → export to Google Docs
```bash
python main.py review --file src/my_service.py --context "PR #142: Add payment service" --export google_docs
```

### Review a git diff → export to Markdown
```bash
git diff HEAD~1 > /tmp/my_changes.diff
python main.py review --diff /tmp/my_changes.diff --export markdown
```

### Review an inline snippet → export both
```bash
python main.py review \
  --snippet "def get_user(id): return db.query(f'SELECT * FROM users WHERE id={id}')" \
  --export both
```

### Review with full options
```bash
python main.py review \
  --file src/auth.py \
  --context "Ticket: SEC-204 — Refactor auth token handling" \
  --pr-url "https://github.com/org/repo/pull/88" \
  --export google_docs
```

---

## How RAG Works in This System

Two Qdrant collections are used:

| Collection | Used by | Content |
|---|---|---|
| `owasp_standards` | SecurityAuditorAgent | OWASP Top 10, CVE patterns, Python-specific vulnerability patterns |
| `org_adrs` | ArchitectureReviewerAgent | Your org's ADRs, coding standards, design patterns |

Before reviewing, each agent calls `RAGTool` to retrieve the most relevant
guidelines for what it observes in the code. This grounds reviews in your
actual org standards rather than generic advice.

### Adding a new knowledge base

```python
# In tools/rag.py — already there, just uncomment:
test_patterns_rag_tool = RAGTool(collection_name="test_patterns")

# In agents/test_coverage_reviewer.py:
tools=[test_patterns_rag_tool]

# Ingest your test pattern docs:
# python main.py ingest test_patterns --dir knowledge_base/test_patterns
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
        tools=[],   # attach perf_patterns_rag_tool if desired
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
# Add to tasks list and summary_task context
```

That's it. No other files change.

---

## Phase 2: Bug Triage Crew

The following will be reused without modification:
- `tools/rag.py` (add `codebase_rag_tool`, `bug_history_rag_tool`)
- `tools/code_parser.py`
- `exporters/` (all exporters)
- `ingestion/ingest.py`

New additions only:
- `crews/bug_triage_crew.py` (LangGraph-based for retry loops)
- `agents/bug_parser.py`
- `agents/root_cause.py`
- `agents/impact_analysis.py`
- `knowledge_base/bug_history/`
- `knowledge_base/codebase/`  (or index from src/ directly)

---

## Adding New Exporters

```python
# exporters/confluence.py
from .base import BaseExporter, ReviewReport

class ConfluenceExporter(BaseExporter):
    def export(self, report: ReviewReport) -> str:
        # Push to Confluence REST API
        ...
        return "https://your-org.atlassian.net/wiki/..."
```

Register in `exporters/__init__.py` and add to the CLI in `main.py`.
