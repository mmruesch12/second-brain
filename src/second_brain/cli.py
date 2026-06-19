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


@app.command("query")
def query_cmd(
    question: str = typer.Argument(..., help="Question to answer from your notes"),
    profile: str = typer.Option("brief", "--profile", "-p", help="Output profile: brief | standard | audit"),
    zone: Optional[str] = typer.Option(None, "--zone", "-z", help="Restrict to DataZone"),
    limit: int = typer.Option(5, "--limit", help="Max chunks to retrieve"),
    json_out: bool = typer.Option(False, "--json", help="Output full JSON SynthesisResponse"),
    debug: bool = typer.Option(False, "--debug", help="Show full trace / response"),
) -> None:
    """Answer a question using baseline retrieval + synthesis (default brief profile).

    Uses immortal baseline_rag + synthesizer (1 LLM call).
    """
    # Import inside to avoid top-level dep on litellm when not needed (e.g. ingest only, smoke)
    from src.second_brain.synthesizer import synthesize

    resp = synthesize(question, limit=limit, zone=zone, profile=profile)

    if json_out or debug:
        # pydantic v2
        try:
            print(resp.model_dump_json(indent=2))
        except Exception:
            print(resp)
    else:
        print(resp.answer_markdown)

    if debug:
        typer.echo(f"\n[debug] model_used={resp.model_used} profile={resp.profile} confidence={resp.confidence}")


@app.command("doctor")
def doctor_cmd(
    zone: Optional[str] = typer.Option(None, "--zone", help="Filter health to zone"),
) -> None:
    """Health check (smoke test for Phase 0a). Reports module status, acceptance, basic stats."""
    typer.echo("sb doctor — Personal Agentic Second Brain health check")
    issues = []

    # Check core modules
    try:
        from src.second_brain import eval_harness
        from src.second_brain.retriever import baseline_rag
        from src.second_brain.synthesizer import synthesize
        typer.echo("  Modules: OK (retriever, synthesizer, harness)")
    except Exception as e:
        issues.append(f"module load: {e}")

    # Check demo corpus
    try:
        import glob
        demo = glob.glob("demo/**/*.md", recursive=True)
        typer.echo(f"  Demo corpus: {len(demo)} md files")
    except Exception as e:
        issues.append(f"demo glob: {e}")

    # Verify acceptance (from harness)
    try:
        from src.second_brain.eval_harness import verify_phase0a_acceptance
        v = verify_phase0a_acceptance()
        typer.echo(f"  Phase 0a acceptance: {'MET' if v.get('acceptance_met') else 'NOT MET'} (files={v.get('demo_md_files')}, citations={v.get('sample_query_citations')})")
    except Exception as e:
        issues.append(f"verify: {e}")

    if zone:
        typer.echo(f"  Zone filter: {zone}")

    if issues:
        typer.echo("  Issues:")
        for i in issues:
            typer.echo(f"    - {i}")
    else:
        typer.echo("  Status: healthy (Phase 0a smoke OK)")

    raise typer.Exit(code=1 if issues else 0)


@app.callback()
def main() -> None:
    """sb - local-first personal knowledge base (MVP)"""
    pass


if __name__ == "__main__":
    app()
