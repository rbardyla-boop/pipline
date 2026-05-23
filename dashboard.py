import json
import glob
import sys
from pathlib import Path
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich import box

console = Console()


def _verdict_color(verdict: str) -> str:
    return {"HIT": "green", "COUNTER_SIGNAL": "yellow"}.get(verdict, "red")


def _is_uaf(data: dict) -> bool:
    return "dynamics_summary" in data


def _display_legacy_run(data: dict):
    metrics = data.get("sandbox_metrics", {})
    verdict = data.get("sandbox_verdict", "UNKNOWN")
    ritual = data.get("ritual_cost_score")
    anti_opt = data.get("anti_optimization_score")
    goodhart = data.get("goodhart_warnings", 0)
    vc = _verdict_color(verdict)

    header_lines = [
        f"[bold]Run ID:[/bold]  {data.get('run_id', 'N/A')}",
        f"[bold]Domain:[/bold]  {data.get('domain', 'N/A').upper()}",
        f"[bold]Verdict:[/bold] [{vc}]{verdict}[/{vc}]",
    ]
    if ritual is not None:
        header_lines.append(f"[bold]Ritual Cost:[/bold]  {ritual:.3f}  |  [bold]Anti-Opt:[/bold] {anti_opt:.3f}")
    if goodhart:
        header_lines.append(f"[bold yellow]Goodhart Warnings:[/bold yellow] {goodhart}")

    console.print(Panel(
        "\n".join(header_lines),
        title="Universal Extrapolative Engine v4 — Run Report",
        border_style="cyan"
    ))

    history = data.get("concept_scores_history", [])
    best_score = data.get("best_concept_score")
    loops = data.get("refinement_loop_count", 0)
    best_concept = data.get("best_concept") or data.get("top_candidate", "N/A")

    if history:
        sparkline = " → ".join(f"{s:.2f}" for s in history)
        delta = history[-1] - history[0] if len(history) > 1 else 0
        delta_str = f"+{delta:.2f}" if delta >= 0 else f"{delta:.2f}"
        console.print(Panel(
            f"[bold]Loops:[/bold] {loops}  |  [bold]Score history:[/bold] {sparkline}\n"
            f"[bold]Best Phoenix score:[/bold] {best_score:.3f}/5.0  |  [bold]Improvement:[/bold] {delta_str}",
            title="Refinement Loop Summary",
            border_style="magenta"
        ))

    console.print("\n[bold cyan]BEST CONCEPT (highest Phoenix score):[/bold cyan]")
    console.print(Panel(best_concept, border_style="yellow"))

    terminal_path = Path("logs/terminal_archive.json")
    if terminal_path.exists():
        with open(terminal_path) as f:
            retired = json.load(f)
        console.print(f"\n[bold magenta]Terminal Archive:[/bold magenta] {len(retired)} concept(s) permanently retired")
        for entry in retired[-3:]:
            console.print(f"  [dim]↳ {entry.get('concept_preview', '')[:80]}... (Phoenix {entry.get('phoenix_score', '?')})[/dim]")

    table = Table(title="Sandbox Metrics", box=box.ROUNDED)
    table.add_column("Metric", style="bold")
    table.add_column("Value")
    table.add_column("Target")
    table.add_column("Pass?")

    checks = [
        ("Viral Velocity (Vv)",       metrics.get("viral_velocity", 0),            "> 4.0",  4.0),
        ("Memetic Drift (Md)",         metrics.get("memetic_drift", 0),             "> 0.40", 0.40),
        ("Retention Stability (Rd)",   metrics.get("retention_decay_slop", 0),     "> 0.30", 0.30),
        ("Budget Retention",           metrics.get("budget_filtered_retention", 0), "> 0.50", 0.50),
    ]
    for name, val, target, threshold in checks:
        passed = "✅" if float(val) > threshold else "❌"
        table.add_row(name, str(val), target, passed)
    console.print(table)

    sim = data.get("simulator")
    if sim and sim.get("simulator_active"):
        sim_lines = [
            f"[bold]Cycles tracked:[/bold] {sim['cycles_tracked']}",
            f"[bold]Trajectory warnings:[/bold] {sim['trajectory_warnings']}  |  "
            f"[bold]Active refractory clusters:[/bold] {sim['active_refractory_clusters']}",
        ]
        console.print(Panel("\n".join(sim_lines), title="v5 Simulator Metrics", border_style="blue"))

    top_candidates = data.get("top_candidates", [])
    if top_candidates:
        console.print("\n[bold cyan]TOP EVOLVED CANDIDATES:[/bold cyan]")
        for i, c in enumerate(top_candidates[:5], 1):
            console.print(Panel(
                f"[dim]{c['candidate'][:200]}[/dim]\n"
                f"[bold]Novelty:[/bold] {c['novelty']} | "
                f"[bold]Coherence:[/bold] {c['coherence']} | "
                f"[bold]Combined:[/bold] {c['combined']}",
                title=f"#{i}",
                border_style="dim"
            ))


def _display_uaf_run(data: dict):
    sim_result = data.get("simulation_result", {})
    summary = data.get("dynamics_summary", {})
    series = data.get("dynamics_series", [])
    config = data.get("config", {})

    console.print(Panel(
        "\n".join([
            f"[bold]Run ID:[/bold]       {data.get('run_id', 'N/A')}",
            f"[bold]Architecture:[/bold] {data.get('architecture_id', 'N/A')}",
            f"[bold]Domain:[/bold]       {data.get('domain', 'N/A').upper()}",
            f"[bold]Best Score:[/bold]   {sim_result.get('best_score', '?')}/5.0",
            f"[bold]Halt Reason:[/bold]  {sim_result.get('halt_reason', '?')}",
        ]),
        title="Universal Extrapolative Engine — UAF Run Report",
        border_style="cyan"
    ))

    console.print(Panel(
        "\n".join([
            f"[bold]Cycles:[/bold]          {summary.get('total_cycles', '?')}  |  "
            f"[bold]Mean Score:[/bold]  {summary.get('mean_score', '?')}",
            f"[bold]Trajectory Warn:[/bold] {summary.get('trajectory_warnings', 0)}  |  "
            f"[bold]Goodhart:[/bold]    {summary.get('goodhart_total', 0)}",
            f"[bold]Final Converge:[/bold]  {summary.get('final_convergence', '?'):.2f}  |  "
            f"[bold]Min Converge:[/bold] {summary.get('min_convergence', '?'):.2f}",
        ]),
        title="Dynamics Summary",
        border_style="magenta"
    ))

    if series:
        tbl = Table(title="Dynamics Series", box=box.ROUNDED)
        tbl.add_column("Cycle", style="bold")
        tbl.add_column("Score")
        tbl.add_column("Δ")
        tbl.add_column("Stability")
        tbl.add_column("Goodhart P.")
        tbl.add_column("Converging?")
        for snap in series:
            delta = snap.get("plateau_delta")
            delta_str = f"{delta:+.3f}" if delta is not None else "—"
            tbl.add_row(
                str(snap.get("cycle", "?")),
                f"{snap.get('composite_score', '?'):.3f}",
                delta_str,
                f"{snap.get('stability', 0):.4f}",
                f"{snap.get('goodhart_pressure', 0):.4f}",
                "⚠" if snap.get("session_converging") else "✓",
            )
        console.print(tbl)

    best_candidate = sim_result.get("best_candidate", "N/A")
    console.print("\n[bold cyan]BEST CANDIDATE:[/bold cyan]")
    console.print(Panel(
        f"{best_candidate[:300]}{'...' if len(best_candidate) > 300 else ''}\n\n"
        f"[bold]Score:[/bold] {sim_result.get('best_score', '?')}  |  "
        f"[bold]Combined:[/bold] {sim_result.get('best_combined', '?'):.4f}",
        border_style="yellow"
    ))

    if config:
        console.print(Panel(
            f"[bold]Domain:[/bold] {config.get('domain', '?')}  |  "
            f"[bold]Seeds:[/bold] {len(config.get('seeds', []))}  |  "
            f"[bold]Generations:[/bold] {config.get('generations', '?')}  |  "
            f"[bold]Variants/Gen:[/bold] {config.get('variants_per_gen', '?')}  |  "
            f"[bold]Max Loops:[/bold] {config.get('max_loops', '?')}  |  "
            f"[bold]V5 Sim:[/bold] {config.get('v5_simulator', False)}",
            title="Run Config",
            border_style="dim"
        ))


def display_run(filepath: str):
    with open(filepath) as f:
        data = json.load(f)
    if _is_uaf(data):
        _display_uaf_run(data)
    else:
        _display_legacy_run(data)


def show_latest():
    runs = sorted(glob.glob("logs/runs/full_run_*.json"), key=lambda p: Path(p).stat().st_mtime, reverse=True)
    if not runs:
        console.print("[red]No runs found in logs/runs/[/red]")
        console.print("[dim]Run: python main.py seeds/gaming.yaml[/dim]")
        return
    console.print(f"[dim]Loading: {runs[0]}[/dim]\n")
    display_run(runs[0])


def show_all_summary():
    runs = sorted(glob.glob("logs/runs/full_run_*.json"), reverse=True)
    if not runs:
        console.print("[red]No runs found.[/red]")
        return

    table = Table(title=f"All Runs ({len(runs)} total)", box=box.ROUNDED)
    table.add_column("Run ID")
    table.add_column("Fmt")
    table.add_column("Domain")
    table.add_column("Best")
    table.add_column("Cycles")
    table.add_column("Verdict / Halt")
    table.add_column("Dynamics")

    for path in runs:
        with open(path) as f:
            d = json.load(f)
        if _is_uaf(d):
            sim_result = d.get("simulation_result", {})
            summary = d.get("dynamics_summary", {})
            best = sim_result.get("best_score")
            halt = sim_result.get("halt_reason", "?")
            cycles = str(summary.get("total_cycles", "?"))
            dynamics = (f"traj={summary.get('trajectory_warnings', 0)} "
                        f"goodhart={summary.get('goodhart_total', 0)}")
            table.add_row(
                d.get("run_id", "?"),
                "[blue]uaf[/blue]",
                d.get("domain", "?").upper(),
                f"{best:.2f}" if best is not None else "?",
                cycles,
                halt,
                dynamics,
            )
        else:
            verdict = d.get("sandbox_verdict", "?")
            color = _verdict_color(verdict)
            best = d.get("best_concept_score")
            loops = str(d.get("refinement_loop_count", "?"))
            ritual = d.get("ritual_cost_score")
            anti_opt = d.get("anti_optimization_score")
            dynamics = (f"ritual={ritual:.2f} anti={anti_opt:.2f}"
                        if ritual is not None else "—")
            table.add_row(
                d.get("run_id", "?"),
                "[dim]legacy[/dim]",
                d.get("domain", "?").upper(),
                f"{best:.2f}" if best is not None else "?",
                loops,
                f"[{color}]{verdict}[/{color}]",
                dynamics,
            )

    console.print(table)


def show_ledger():
    ledger_path = Path("logs/experiment_ledger.jsonl")
    if not ledger_path.exists():
        console.print("[red]No experiment ledger found at logs/experiment_ledger.jsonl[/red]")
        return

    traces = []
    with open(ledger_path) as f:
        for line in f:
            line = line.strip()
            if line:
                traces.append(json.loads(line))

    if not traces:
        console.print("[dim]Experiment ledger is empty.[/dim]")
        return

    table = Table(title=f"Experiment Ledger ({len(traces)} runs)", box=box.ROUNDED)
    table.add_column("Run ID")
    table.add_column("Architecture")
    table.add_column("Domain")
    table.add_column("Best")
    table.add_column("Mean")
    table.add_column("Cycles")
    table.add_column("Traj Warn")
    table.add_column("Goodhart")
    table.add_column("Halt")

    for trace in traces:
        summary = trace.get("dynamics_summary", {})
        sim_result = trace.get("simulation_result", {})
        best = sim_result.get("best_score")
        table.add_row(
            trace.get("run_id", "?"),
            trace.get("architecture_id", "?"),
            trace.get("domain", "?").upper(),
            f"{best:.2f}" if best is not None else "?",
            str(summary.get("mean_score", "?")),
            str(summary.get("total_cycles", "?")),
            str(summary.get("trajectory_warnings", 0)),
            str(summary.get("goodhart_total", 0)),
            sim_result.get("halt_reason", "?"),
        )

    console.print(table)


if __name__ == "__main__":
    if len(sys.argv) > 1:
        if sys.argv[1] == "all":
            show_all_summary()
        elif sys.argv[1] == "ledger":
            show_ledger()
        else:
            display_run(sys.argv[1])
    else:
        show_latest()
