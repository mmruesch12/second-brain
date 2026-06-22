"""Typer CLI for second-brain (sb).

Implements per PRD Appendix A: ingest/capture/query + Phase1/2 (quick, rituals, --verify, stream).
"""

from typing import Optional

import typer

from second_brain.ingest import ingest, get_status

app = typer.Typer(help="Personal Agentic Second Brain (sb) - Phase 0-3 MVP (reflect + actions.md)")


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
    since: Optional[str] = typer.Option(None, "--since", help="Date filter YYYY-MM-DD (notes on/after)"),
    json_out: bool = typer.Option(False, "--json", help="Output full JSON SynthesisResponse"),
    debug: bool = typer.Option(False, "--debug", help="Show full trace / response"),
    verify: bool = typer.Option(False, "--verify", help="Run verifier sync (default: async/background)"),
) -> None:
    """Answer using Phase 1 hardened retrieval (filters, wikilinks, heuristic router) + synthesis (1 LLM).

    Default brief profile (<=5 bullets + 1 next action). --since and --zone for metadata filters.
    --verify for sync citation check; fast streaming default when not --json/--debug.
    """
    # Import inside to avoid top-level dep on litellm when not needed (e.g. ingest only, smoke)
    from second_brain.synthesizer import synthesize

    if zone and str(zone).lower() in ("all", "*"):
        typer.echo("Warning: --zone all bypasses DataZone enforcement (cross-zone retrieval). Use specific zones for privacy.")
    do_stream = not (json_out or debug)
    resp = synthesize(question, limit=limit, zone=zone, profile=profile, since=since, stream=do_stream, verify=verify)

    if json_out or debug:
        # pydantic v2
        try:
            print(resp.model_dump_json(indent=2))
        except Exception:
            print(resp)
    else:
        # stream=True for human paths: output emitted live by synth; banner only if verdict present (from --verify)
        if resp.verifier_verdict:
            print(f"\n[verifier: {resp.verifier_verdict}]")

    if not verify:
        # async default per PRD: fire bg verify (non blocking; surfaces only on debug)
        import threading
        def _bg_verify():
            try:
                from second_brain.retriever import heuristic_router, retrieve
                from second_brain.verifier import verify_citations
                # use router for eff filters (since/tags etc) to match synth primary path
                rcfg = heuristic_router(question, zone=zone, since=since, limit=limit, profile=profile, ref_date=None)
                hs = retrieve(question, limit=rcfg.get("limit", limit), zone=rcfg.get("zone"), since=rcfg.get("since"), tags=rcfg.get("tags"), path_prefix=rcfg.get("path_prefix"))
                vv = verify_citations(question, resp.answer_markdown, hs)
                if debug:
                    print(f"\n[async-verifier: {vv}]")
            except Exception:
                if debug:
                    print("\n[async-verifier: UNVERIFIED]")
        threading.Thread(target=_bg_verify, daemon=True).start()

    if debug:
        typer.echo(f"\n[debug] model_used={resp.model_used} profile={resp.profile} confidence={resp.confidence} verifier={resp.verifier_verdict}")


@app.command("quick")
def quick_cmd(
    question: str = typer.Argument(..., help="Question (fast brief path, no verify, streaming)"),
    zone: Optional[str] = typer.Option(None, "--zone", "-z", help="Restrict to DataZone"),
    limit: int = typer.Option(5, "--limit", help="Max chunks to retrieve"),
    since: Optional[str] = typer.Option(None, "--since", help="Date filter YYYY-MM-DD"),
    json_out: bool = typer.Option(False, "--json", help="Output full JSON"),
    debug: bool = typer.Option(False, "--debug", help="Show full trace"),
) -> None:
    """Fast path per PRD (brief, streaming, no verifier). Alias for quick queries."""
    from second_brain.synthesizer import synthesize

    if zone and str(zone).lower() in ("all", "*"):
        typer.echo("Warning: --zone all bypasses DataZone enforcement (cross-zone retrieval). Use specific zones for privacy.")
    do_stream = not (json_out or debug)
    resp = synthesize(question, limit=limit, zone=zone, profile="brief", since=since, stream=do_stream, verify=False)

    if json_out or debug:
        try:
            print(resp.model_dump_json(indent=2))
        except Exception:
            print(resp)
    # else: human default uses live stream writes from synth (no reprint to avoid dupe)

    if debug:
        typer.echo(f"\n[debug] model_used={resp.model_used} profile={resp.profile}")


@app.command("morning")
def morning_cmd(
    profile: str = typer.Option("brief", "--profile", "-p", help="Output profile"),
    zone: Optional[str] = typer.Option(None, "--zone", "-z"),
    limit: int = typer.Option(5, "--limit"),
    json_out: bool = typer.Option(False, "--json"),
    debug: bool = typer.Option(False, "--debug"),
) -> None:
    """Morning ritual: synthesis focused on what matters today (last ~48h via --since)."""
    from datetime import datetime, timedelta
    from second_brain.synthesizer import synthesize

    if zone and str(zone).lower() in ("all", "*"):
        typer.echo("Warning: --zone all bypasses DataZone enforcement (cross-zone retrieval). Use specific zones for privacy.")
    ref = datetime(2026, 6, 20)  # matches router ref_date for demo corpus dates
    since = (ref - timedelta(days=2)).strftime("%Y-%m-%d")
    q = "What matters today? Key priorities, decisions, open questions, next actions from recent notes."
    do_stream = not (json_out or debug)
    resp = synthesize(q, limit=limit, zone=zone, profile=profile, since=since, stream=do_stream, verify=False)

    if json_out or debug:
        try:
            print(resp.model_dump_json(indent=2))
        except Exception:
            print(resp)
    # else not needed: human default uses live synth stream writes

    if debug:
        typer.echo(f"\n[debug] model_used={resp.model_used} since={since}")


@app.command("prep")
def prep_cmd(
    topic: str = typer.Argument(..., help="Topic for prep (e.g. 'Acme Q3 meeting' or decision)"),
    profile: str = typer.Option("brief", "--profile", "-p"),
    zone: Optional[str] = typer.Option(None, "--zone", "-z"),
    limit: int = typer.Option(5, "--limit"),
    since: Optional[str] = typer.Option(None, "--since"),
    json_out: bool = typer.Option(False, "--json"),
    debug: bool = typer.Option(False, "--debug"),
) -> None:
    """Prep ritual: cited brief synthesis for a topic (passes topic into query)."""
    from second_brain.synthesizer import synthesize

    if zone and str(zone).lower() in ("all", "*"):
        typer.echo("Warning: --zone all bypasses DataZone enforcement (cross-zone retrieval). Use specific zones for privacy.")
    q = f"Prep summary for {topic}: key points, prior decisions, risks, commitments, open questions and next actions from notes."
    do_stream = not (json_out or debug)
    resp = synthesize(q, limit=limit, zone=zone, profile=profile, since=since, stream=do_stream, verify=False)

    if json_out or debug:
        try:
            print(resp.model_dump_json(indent=2))
        except Exception:
            print(resp)
    # human default: live synth writes for stream

    if debug:
        typer.echo(f"\n[debug] model_used={resp.model_used} topic={topic}")


@app.command("weekly")
def weekly_cmd(
    profile: str = typer.Option("brief", "--profile", "-p"),
    zone: Optional[str] = typer.Option(None, "--zone", "-z"),
    limit: int = typer.Option(5, "--limit"),
    since: Optional[str] = typer.Option(None, "--since"),
    json_out: bool = typer.Option(False, "--json"),
    debug: bool = typer.Option(False, "--debug"),
) -> None:
    """North-star ritual: bounded weekly synthesis (themes, decisions, questions, actions). <=5min target."""
    from datetime import datetime, timedelta
    from second_brain.synthesizer import synthesize

    if zone and str(zone).lower() in ("all", "*"):
        typer.echo("Warning: --zone all bypasses DataZone enforcement (cross-zone retrieval). Use specific zones for privacy.")
    ref = datetime(2026, 6, 20)
    eff_since = since or (ref - timedelta(days=7)).strftime("%Y-%m-%d")
    q = "Weekly recap: key themes, decisions, open questions, next actions from recent notes. Use brief cited bullets."
    do_stream = not (json_out or debug)
    resp = synthesize(q, limit=limit, zone=zone, profile=profile, since=eff_since, stream=do_stream, verify=False)

    if json_out or debug:
        try:
            print(resp.model_dump_json(indent=2))
        except Exception:
            print(resp)
    # human default: live synth writes for stream

    if debug:
        typer.echo(f"\n[debug] model_used={resp.model_used} since={eff_since}")


@app.command("reflect")
def reflect_cmd(
    days: int = typer.Option(7, "--days", help="Window in days back from ref (uses modified_at)"),
    max_items: int = typer.Option(3, "--max-items", help="Cap items per category (tasks/questions/connections)"),
    zone: Optional[str] = typer.Option(None, "--zone", "-z", help="Restrict to DataZone"),
    json_out: bool = typer.Option(False, "--json", help="Output full JSON ReflectionResponse"),
    debug: bool = typer.Option(False, "--debug", help="Show full trace / response"),
) -> None:
    """Bounded reflection per PRD §7.3 Phase 3: recent notes (since via --days, cap 50 notes), structured extract {tasks,open_questions,connections} each cited. Export actions.md (deduped checkboxes for triage). 1 LLM target. Use retrieve path."""
    from datetime import datetime, timedelta
    from second_brain.reflect import reflect

    if zone and str(zone).lower() in ("all", "*"):
        typer.echo("Warning: --zone all bypasses DataZone enforcement (cross-zone retrieval). Use specific zones for privacy.")
    ref = datetime(2026, 6, 21)  # demo determinism consistent with reflect default
    # since computed inside reflect; pass ref_date for header consistency
    resp = reflect(days=days, max_items=max_items, zone=zone, ref_date=ref, debug=debug)

    if json_out or debug:
        try:
            print(resp.model_dump_json(indent=2))
        except Exception:
            print(resp)
    else:
        # default human: readable cited sections (checkboxes in actions.md export)
        since_str = (ref - timedelta(days=days)).strftime("%Y-%m-%d")
        print(f"Reflect ({days}d window, max {max_items} per cat; since ~{since_str})")
        for cat, label in [("tasks", "Tasks"), ("open_questions", "Open questions"), ("connections", "Connections")]:
            items = getattr(resp, cat, [])
            print(f"\n### {label}")
            if items:
                for it in items:
                    q = f' "{it.quote}"' if it.quote else ""
                    print(f"- {it.text} [{it.citation}]{q}")
            else:
                print("- (none)")
        if resp.note:
            print(f"\nNote: {resp.note}")
        print("\nExported triage to actions.md (edit checkboxes for snooze/done/trash).")

    if debug:
        typer.echo(f"\n[debug] model_used={resp.model_used} note={resp.note}")


@app.command("doctor")
def doctor_cmd(
    zone: Optional[str] = typer.Option(None, "--zone", help="Filter health to zone"),
) -> None:
    """Health check (smoke test for Phase 0a/0b + Phase 1 + Phase 2). Reports module status, acceptance, basic stats incl. PDF parse per PRD §13. Phase1/2 retrieve/router/verifier/rituals/stream exercised."""
    typer.echo("sb doctor — Personal Agentic Second Brain health check")
    issues = []

    # Check core modules (explicit reflect import to validate + match echoed list)
    try:
        from second_brain.synthesizer import synthesize
        from second_brain.reflect import reflect
        typer.echo("  Modules: OK (retriever, synthesizer, verifier, harness, reflect)")
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

    # Verify acceptance (Phase1 extended)
    try:
        from second_brain.eval_harness import verify_phase0a_acceptance
        v = verify_phase0a_acceptance()
        typer.echo(f"  Phase 0a/1 acceptance: {'MET' if v.get('acceptance_met') else 'NOT MET'} (files={v.get('demo_md_files')}, citations={v.get('sample_query_citations')})")
    except Exception as e:
        issues.append(f"verify: {e}")

    # Phase2: verifier + rituals + streaming smoke (PRD §12)
    try:
        from second_brain.eval_harness import verify_phase2_acceptance
        import tempfile
        import shutil
        od = tempfile.mkdtemp()
        try:
            v2 = verify_phase2_acceptance(out_dir=od)
        finally:
            shutil.rmtree(od, ignore_errors=True)
        typer.echo(f"  Phase2 acceptance: {'MET' if v2.get('acceptance_met') else 'NOT MET'} (rituals={len(v2.get('weekly_ritual_smoke', []))}, elapsed={v2.get('elapsed_s',0)}s)")
        if not v2.get("acceptance_met"):
            issues.append("phase2 acceptance not met (see harness smoke for details)")
    except Exception as e:
        issues.append(f"phase2 verify: {e}")

    # Phase1 smoke: filters via retrieve (router exercised in primary synth/harness/bg paths)
    try:
        from second_brain.retriever import retrieve
        rh = retrieve("Acme Q3 risks last week", limit=3, zone="PUBLIC_DEMO", since="2026-06-01", tags=["acme"])
        typer.echo(f"  Phase1 retrieve: hits={len(rh)} (demo realistic e.g. 2026-06-05-acme-q3.md)")
    except Exception as e:
        issues.append(f"phase1 retrieve: {e}")

    # Phase2 synth smoke (stream off for no print in doctor)
    try:
        from second_brain.synthesizer import synthesize
        rs = synthesize("weekly key themes from recent", limit=2, zone="PUBLIC_DEMO", profile="brief", stream=False, verify=True)
        typer.echo(f"  Phase2 synth+verify: verdict={rs.verifier_verdict or 'n/a'}")
    except Exception as e:
        issues.append(f"phase2 synth: {e}")

    # Phase3 smoke: reflect (real retrieve+router via harness populate pattern)
    try:
        from second_brain.eval_harness import verify_phase3_acceptance
        import tempfile
        import shutil
        od = tempfile.mkdtemp()
        try:
            v3 = verify_phase3_acceptance(out_dir=od)
        finally:
            shutil.rmtree(od, ignore_errors=True)
        tw = v3.get("actions_written", bool(v3.get("actions_path")))
        typer.echo(f"  Phase3 acceptance: {'MET' if v3.get('acceptance_met') else 'NOT MET'} (items={v3.get('items_total',0)}, actions_written={tw})")
        if not v3.get("acceptance_met"):
            issues.append("phase3 acceptance not met (see harness for details)")
    except Exception as e:
        issues.append(f"phase3 verify: {e}")

    if zone:
        typer.echo(f"  Zone filter: {zone}")

    if issues:
        typer.echo("  Issues:")
        for i in issues:
            typer.echo(f"    - {i}")
    else:
        typer.echo("  Status: healthy (Phase 0a/0b + Phase1/2 + Phase3 reflect/actions.md smoke OK)")

    raise typer.Exit(code=1 if issues else 0)


@app.callback()
def main() -> None:
    """sb - local-first personal knowledge base (MVP)"""
    pass


if __name__ == "__main__":
    app()
