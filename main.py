"""
main.py

CLI entry point for the AI Code Review Crew.

Default behaviour: always writes the report to disk as a .md file under ./reports/

Usage examples:
    # Review a file → saved to ./reports/ (default)
    python main.py review --file path/to/code.py

    # Review a git diff
    python main.py review --diff path/to/patch.diff

    # Review an inline snippet
    python main.py review --snippet "def foo(): pass" --lang python

    # Also push to Google Docs (requires OAuth credentials configured)
    python main.py review --file path/to/code.py --google-docs

    # Change the output directory for the .md report
    python main.py review --file path/to/code.py --output-dir /tmp/reviews

    # Ingest knowledge base documents
    python main.py ingest owasp_standards --dir knowledge_base/owasp
    python main.py ingest org_adrs --dir knowledge_base/standards
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Optional

import typer
from dotenv import load_dotenv
from rich.console import Console
from rich.panel import Panel

from crews.code_review_crew import build_code_review_crew
from exporters import GoogleDocsExporter, MarkdownExporter, ReviewReport
from tools.code_parser import code_parser

load_dotenv()

app = typer.Typer(
    help="🤖 AI Code Review Crew — multi-agent code review with RAG",
    add_completion=False,
)
console = Console()


@app.command()
def review(
    file: Optional[Path] = typer.Option(
        None, "--file", "-f", help="Path to a source code file to review"
    ),
    diff: Optional[Path] = typer.Option(
        None, "--diff", "-d", help="Path to a git diff/patch file to review"
    ),
    snippet: Optional[str] = typer.Option(
        None, "--snippet", "-s", help="Inline code snippet (wrap in quotes)"
    ),
    context: str = typer.Option(
        "General code review",
        "--context", "-c",
        help="PR title, ticket ID, or human-readable context for this review",
    ),
    pr_url: Optional[str] = typer.Option(
        None, "--pr-url", help="GitHub PR URL for the report header"
    ),
    output_dir: str = typer.Option(
        "reports",
        "--output-dir", "-o",
        help="Directory to write the .md report file (default: ./reports)",
    ),
    google_docs: bool = typer.Option(
        False,
        "--google-docs",
        help="Also push the report to Google Docs (requires OAuth credentials)",
        is_flag=True,
    ),
    language: str = typer.Option(
        "python", "--lang", help="Language hint for snippet input"
    ),
):
    """
    Run the AI Code Review Crew on a file, diff, or pasted snippet.
    Report is always written to disk. Pass --google-docs to also push to Drive.
    """
    # ── Resolve input ─────────────────────────────────────────────────────────
    if file:
        parsed = code_parser.from_file(file)
        title = f"Review: {file.name}"
    elif diff:
        parsed = code_parser.from_diff(diff.read_text())
        title = f"Diff Review: {diff.name}"
    elif snippet:
        parsed = code_parser.from_string(snippet, language=language)
        title = f"Snippet Review ({language})"
    else:
        console.print("[yellow]No input provided. Paste your code below (Ctrl+D to finish):[/yellow]")
        lines = []
        try:
            while True:
                lines.append(input())
        except EOFError:
            pass
        parsed = code_parser.from_string("\n".join(lines), language=language)
        title = f"Snippet Review ({language})"

    code_prompt = parsed.to_agent_prompt()

    export_label = "disk" + (" + Google Docs" if google_docs else "")
    console.print(Panel(
        f"[bold]Reviewing:[/bold] {title}\n"
        f"[bold]Context:[/bold] {context}\n"
        f"[bold]Output dir:[/bold] {output_dir}/\n"
        f"[bold]Export:[/bold] {export_label}",
        title="🤖 Code Review Crew",
        border_style="blue",
    ))

    # ── Run crew ──────────────────────────────────────────────────────────────
    crew = build_code_review_crew(
        code_snippet=code_prompt,
        context=context,
    )

    console.print("[bold cyan]Starting crew run...[/bold cyan]")
    result = crew.kickoff()
    raw_output = str(result)

    # ── Build report ──────────────────────────────────────────────────────────
    report = ReviewReport(
        title=title,
        code_context=context,
        raw_markdown=raw_output,
        reviewed_at=datetime.utcnow(),
        reviewed_by="AI Code Review Crew (v1)",
        pr_url=pr_url,
    )

    # ── Export: always write to disk ──────────────────────────────────────────
    export_results = []

    md_exporter = MarkdownExporter(output_dir=output_dir)
    md_path = md_exporter.export(report)
    export_results.append(f"📄 Report saved: {md_path}")

    # ── Export: optionally push to Google Docs ────────────────────────────────
    if google_docs:
        try:
            gdoc_exporter = GoogleDocsExporter()
            url = gdoc_exporter.export(report)
            export_results.append(f"📝 Google Doc:  {url}")
        except FileNotFoundError as e:
            console.print(f"[red]Google Docs auth not configured:[/red] {e}")
            console.print(
                "[yellow]Tip: set GOOGLE_CREDENTIALS_PATH in .env and re-run with --google-docs[/yellow]"
            )

    console.print(Panel(
        "\n".join(export_results),
        title="✅ Review Complete",
        border_style="green",
    ))


@app.command()
def ingest(
    collection: str = typer.Argument(..., help="Qdrant collection name"),
    directory: str = typer.Option(..., "--dir", help="Directory of documents to ingest"),
    recreate: bool = typer.Option(False, "--recreate", help="Drop and recreate collection"),
):
    """
    Ingest documents into a Qdrant collection for RAG.

    Run before first use:
        python main.py ingest owasp_standards --dir knowledge_base/owasp
        python main.py ingest org_adrs --dir knowledge_base/standards
    """
    from ingestion.ingest import ingest as _ingest
    _ingest(collection=collection, directory=directory, recreate=recreate)


if __name__ == "__main__":
    app()