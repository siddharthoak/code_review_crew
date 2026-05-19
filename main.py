"""
main.py — placeholder entry point

Full implementation added incrementally as agents/, tools/, crews/ are built out.
"""

from __future__ import annotations

import typer
from rich.console import Console

app = typer.Typer(
    help="🤖 AI Code Review Crew — multi-agent code review with RAG",
    add_completion=False,
)
console = Console()


@app.command()
def review(
    file: str = typer.Option(None, "--file", "-f", help="Path to source file"),
    snippet: str = typer.Option(None, "--snippet", "-s", help="Inline code snippet"),
    context: str = typer.Option("General code review", "--context", "-c"),
):
    """Run the AI Code Review Crew. (Not yet implemented)"""
    console.print("[yellow]⚠ Code Review Crew not yet implemented.[/yellow]")
    console.print("Agents, tools, and crews are being built out incrementally.")


@app.command()
def ingest(
    collection: str = typer.Argument(..., help="Qdrant collection name"),
    directory: str = typer.Option(..., "--dir", help="Directory of documents"),
    recreate: bool = typer.Option(False, "--recreate"),
):
    """Ingest documents into Qdrant for RAG. (Not yet implemented)"""
    console.print("[yellow]⚠ Ingestion not yet implemented.[/yellow]")


if __name__ == "__main__":
    app()