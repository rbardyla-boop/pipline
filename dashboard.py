import json
import glob
import sys
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich import box

console = Console()


def display_run(filepath: str):
    with open(filepath) as f:
        data = json.load(f)

    metrics = data.get("sandbox_metrics", {})
    verdict = data.get("sandbox_verdict", "UNKNOWN")
    verdict_color = "green" if verdict == "HIT" else "red"

    console.print(Panel(
        f"[bold]Run ID:[/bold]  {data.get('run_id', 'N/A')}\n"
        f"[bold]Domain:[/bold]  {data.get('domain', 'N/A').upper()}\n"
        f"[bold]Verdict:[/bold] [{verdict_color}]{verdict}[/{verdict_color}]",
        title="Universal Extrapolative Engine — Run Report",
        border_style="cyan"
    ))

    # Refinement history
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


def show_latest():
    runs = sorted(glob.glob("logs/runs/full_run_*.json"), reverse=True)
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
    table.add_column("Domain")
    table.add_column("Verdict")
    table.add_column("Phoenix")
    table.add_column("Loops")
    table.add_column("Vv")
    table.add_column("Md")

    for path in runs:
        with open(path) as f:
            d = json.load(f)
        m = d.get("sandbox_metrics", {})
        verdict = d.get("sandbox_verdict", "?")
        color = "green" if verdict == "HIT" else "red"
        phoenix = d.get("best_concept_score")
        phoenix_str = f"{phoenix:.2f}" if phoenix is not None else "?"
        table.add_row(
            d.get("run_id", "?"),
            d.get("domain", "?").upper(),
            f"[{color}]{verdict}[/{color}]",
            phoenix_str,
            str(d.get("refinement_loop_count", "?")),
            str(m.get("viral_velocity", "?")),
            str(m.get("memetic_drift", "?"))
        )

    console.print(table)


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "all":
        show_all_summary()
    else:
        show_latest()
