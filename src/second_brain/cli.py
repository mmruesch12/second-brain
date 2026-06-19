"""Typer CLI for second-brain (sb).

Implements `sb ingest` (Phase 0a) per PRD Appendix A and progress.
"""

from typing import Optional

import typer

from src.second_brain.ingest import ingest, get_status

app = typer.Typer(help="Personal Agentic Second Brain (sb) - Phase 0a MVP")


@app.command("ingest")
def ingest_cmd(
    path: Optional[str] = typer.Argument(
        None,
        help="Path to markdown file or directory. Omit with --status to show manifest only.",
    ),
    zone: Optional[str] = typer.Option(
        None, "--zone", "-z", help="Override DataZone (PERSONAL | WORK_ADJACENT | PUBLIC_DEMO)"
    ),
    status: bool = typer.Option(
        False, "--status", help="Show ingest manifest/status instead of ingesting"
    ),
) -> None:
    """Ingest markdown files or show status.

    Respects .secondbrainignore and DataZone rules.
    """
    if status:
        rows = get_status()
        if not rows:
            typer.echo("No documents ingested yet.")
            raise typer.Exit()
        typer.echo("Ingest status (most recent first):")
        for r in rows:
            typer.echo(
                f"  {r['doc_id']} | {r['source_path']} | zone={r['data_zone']} | "
                f"chunks={r['num_chunks']} | {r['ingested_at']}"
            )
        return

    if not path:
        typer.echo("Error: path required unless using --status")
        raise typer.Exit(code=1)

    summary = ingest(path, zone_override=zone)
    typer.echo(
        f"Ingest complete: added={summary['added']} skipped={summary['skipped']} "
        f"(from {summary['total_files']} files)"
    )



@app.callback()
def main() -> None:
    """sb - local-first personal knowledge base (MVP)"""
    pass


if __name__ == "__main__":
    app()
