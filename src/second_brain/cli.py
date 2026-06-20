"""Typer CLI for second-brain (sb).

Implements `sb ingest` (Phase 0a) per PRD Appendix A and progress.
"""

from typing import Optional

import typer

from second_brain.ingest import ingest, get_status

app = typer.Typer(help="Personal Agentic Second Brain (sb) - Phase 0a/0b MVP")


@app.command("ingest")
def ingest_cmd(
    path: Optional[str] = typer.Argument(
        None,
        help="Path to .md/.pdf file or dir. Omit with --status to show manifest only. (Phase 0b PDFs)",
    ),
    zone: Optional[str] = typer.Option(
        None, "--zone", "-z", help="Override DataZone (PERSONAL | WORK_ADJACENT | PUBLIC_DEMO)"
    ),
    status: bool = typer.Option(
        False, "--status", help="Show ingest manifest/status instead of ingesting"
    ),
) -> None:
    """Ingest markdown or text-native PDF files or show status.

    Respects .secondbrainignore and DataZone rules. (Phase 0b: .pdf T0/T1 supported)
    """
    if status:
        rows = get_status()
        if not rows:
            typer.echo("No documents ingested yet.")
            raise typer.Exit()
        typer.echo("Ingest status (most recent first):")
        for r in rows:
            dtype = r.get("doc_type", "markdown")
            q = r.get("parse_quality", "ok")
            typer.echo(
                f"  {r['doc_id']} | {r['source_path']} | zone={r['data_zone']} | "
                f"chunks={r['num_chunks']} | type={dtype} q={q} | {r['ingested_at']}"
            )
        return

    if not path:
        typer.echo("Error: path required unless using --status")
        raise typer.Exit(code=1)

    summary = ingest(path, zone_override=zone)
    failed = summary.get("failed", 0)
    extra = f" failed={failed}" if failed else ""
    typer.echo(
        f"Ingest complete: added={summary['added']} skipped={summary['skipped']}{extra} "
        f"(from {summary['total_files']} files)"
    )


@app.command("capture")
def capture_cmd(
    text: str = typer.Argument(..., help="Text to capture quickly into inbox/ as timestamped .md (auto-ingests)"),
) -> None:
    """Quick capture per PRD §7.1: lands in inbox/ as .md + auto-ingest for immediate queryability.

    <60s target. Uses resolve_zone (inbox/ -> PERSONAL by default).
    """
    from pathlib import Path
    from datetime import datetime

    inbox = Path("inbox")
    inbox.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime("%Y-%m-%d-%H%M%S-%f")  # microsec to avoid collision on rapid captures
    fpath = inbox / f"{ts}.md"
    content = f"""---
title: Capture {ts}
date: {datetime.now().date().isoformat()}
---

{text}
"""
    fpath.write_text(content, encoding="utf-8")
    # auto-ingest so immediately queryable via baseline_rag
    summary = ingest(str(fpath))
    typer.echo(f"Captured {fpath.name} (added={summary.get('added', 0)})")


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
    from second_brain.synthesizer import synthesize

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
    """Health check (smoke test for Phase 0a/0b). Reports module status, acceptance, basic stats incl. PDF parse per PRD §13."""
    typer.echo("sb doctor — Personal Agentic Second Brain health check")
    issues = []

    # Check core modules
    try:
        from second_brain import eval_harness
        from second_brain.retriever import baseline_rag
        from second_brain.synthesizer import synthesize
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

    # PDF parse stats (Phase 0b, PRD §13)
    try:
        import glob as _glob
        pdf_files = _glob.glob("demo/**/*.pdf", recursive=True)
        pdf_count = len(pdf_files)
        ok_p = partial_p = failed_p = 0
        try:
            from second_brain.ingest import get_status
            rows = get_status() or []
            for r in rows:
                sp = str(r.get("source_path", "")).lower()
                if (r.get("doc_type") == "pdf" or sp.endswith(".pdf")) and "demo/" in sp:
                    q = r.get("parse_quality", "ok")
                    if q == "failed":
                        failed_p += 1
                    elif q == "partial":
                        partial_p += 1
                    else:
                        ok_p += 1
        except Exception:
            pass  # manifest may be empty
        typer.echo(f"  Demo PDFs: {pdf_count} (ok={ok_p}, partial={partial_p}, failed={failed_p}; from manifest demo/ paths)")
    except Exception as e:
        issues.append(f"pdf stats: {e}")

    # Verify acceptance (from harness)
    try:
        from second_brain.eval_harness import verify_phase0a_acceptance
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
        typer.echo("  Status: healthy (Phase 0a/0b smoke OK)")

    raise typer.Exit(code=1 if issues else 0)


@app.callback()
def main() -> None:
    """sb - local-first personal knowledge base (MVP)"""
    pass


if __name__ == "__main__":
    app()
