"""
ingestion/ingest.py

Ingests knowledge base documents into Qdrant collections.

Run this once before the first crew execution (or whenever docs are updated):
    python -m ingestion.ingest --collection owasp_standards --dir knowledge_base/owasp
    python -m ingestion.ingest --collection org_adrs --dir knowledge_base/standards

For Phase 2 (Bug Triage), add:
    python -m ingestion.ingest --collection codebase_index --dir src/
    python -m ingestion.ingest --collection bug_history --dir bug_reports/
"""

from __future__ import annotations

import os
from pathlib import Path

import typer
from dotenv import load_dotenv
from llama_index.core import Settings, SimpleDirectoryReader, StorageContext, VectorStoreIndex
from llama_index.core.node_parser import SentenceSplitter
from llama_index.vector_stores.qdrant import QdrantVectorStore
from qdrant_client import QdrantClient
from qdrant_client.http.models import Distance, VectorParams
from rich.console import Console

from tools.llm_factory import get_embedding_dim, get_embedding_model, get_llm, print_provider_info

load_dotenv()

console = Console()
app = typer.Typer(help="Ingest documents into a Qdrant collection for RAG.")


def _get_qdrant_client() -> QdrantClient:
    host = os.getenv("QDRANT_HOST", "localhost")
    port = int(os.getenv("QDRANT_PORT", 6333))
    api_key = os.getenv("QDRANT_API_KEY")
    if api_key:
        return QdrantClient(host=host, port=port, api_key=api_key)
    return QdrantClient(host=host, port=port)


@app.command()
def ingest(
    collection: str = typer.Option(..., help="Qdrant collection name (e.g. owasp_standards)"),
    directory: str = typer.Option(..., "--dir", help="Directory containing documents to ingest"),
    chunk_size: int = typer.Option(512, help="Chunk size for text splitting"),
    chunk_overlap: int = typer.Option(64, help="Chunk overlap"),
    recreate: bool = typer.Option(
        False, "--recreate", help="Drop and recreate the collection before ingesting"
    ),
):
    """
    Ingest all documents from a directory into a Qdrant collection.

    Supported formats: .txt, .md, .pdf, .html, .rst
    """
    doc_dir = Path(directory)
    if not doc_dir.exists():
        console.print(f"[red]Directory not found: {doc_dir}[/red]")
        raise typer.Exit(1)

    print_provider_info()
    console.print(f"[bold]Ingesting documents from:[/bold] {doc_dir}")
    console.print(f"[bold]Target collection:[/bold] {collection}")

    # Configure LlamaIndex from factory (Ollama or OpenAI based on LLM_PROVIDER)
    Settings.llm = get_llm()
    Settings.embed_model = get_embedding_model()

    # Set up Qdrant — use dimension matching the active embedding model
    client = _get_qdrant_client()
    embedding_dim = get_embedding_dim()

    if recreate:
        console.print(f"[yellow]Recreating collection '{collection}'...[/yellow]")
        if client.collection_exists(collection):
            client.delete_collection(collection)

    if not client.collection_exists(collection):
        client.create_collection(
            collection_name=collection,
            vectors_config=VectorParams(size=embedding_dim, distance=Distance.COSINE),
        )
        console.print(f"[green]Created collection '{collection}'[/green]")

    # Load documents
    console.print("[bold]Loading documents...[/bold]")
    reader = SimpleDirectoryReader(
        input_dir=str(doc_dir),
        recursive=True,
        required_exts=[".txt", ".md", ".pdf", ".html", ".rst"],
    )
    documents = reader.load_data()
    console.print(f"Loaded {len(documents)} document(s)")

    # Build index
    console.print("[bold]Chunking and embedding...[/bold]")
    splitter = SentenceSplitter(chunk_size=chunk_size, chunk_overlap=chunk_overlap)

    vector_store = QdrantVectorStore(client=client, collection_name=collection)
    storage_context = StorageContext.from_defaults(vector_store=vector_store)

    VectorStoreIndex.from_documents(
        documents,
        storage_context=storage_context,
        transformations=[splitter],
        show_progress=True,
    )

    console.print(f"[green bold]✓ Ingestion complete for collection '{collection}'[/green bold]")


if __name__ == "__main__":
    app()