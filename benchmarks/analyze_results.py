"""
Results analyzer: reads latencies.csv and scenarios.csv and produces:
    - Summary statistics (mean, median, p95, std) for T_reg and T_ver
    - A histogram of T_reg and T_ver
    - A boxplot comparing the two latency distributions
    - A summary text file ready to paste into the TFM validation chapter

Outputs go to docs/results/figures/ and docs/results/summary.txt.
"""
from __future__ import annotations

import argparse
import csv
import logging
import sys
from pathlib import Path
from statistics import mean, median, pstdev, quantiles

import matplotlib.pyplot as plt

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Loading & stats
# ---------------------------------------------------------------------------

def load_latencies(path: Path) -> tuple[list[float], list[float], list[str]]:
    """Load (T_reg, T_ver, status) lists from a latencies CSV."""
    t_reg, t_ver, statuses = [], [], []
    with path.open("r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            statuses.append(row.get("status", ""))
            if row.get("T_reg_ms"):
                try:
                    t_reg.append(float(row["T_reg_ms"]))
                except ValueError:
                    pass
            if row.get("T_ver_ms"):
                try:
                    t_ver.append(float(row["T_ver_ms"]))
                except ValueError:
                    pass
    return t_reg, t_ver, statuses


def stats(values: list[float]) -> dict:
    if not values:
        return {"n": 0}
    n = len(values)
    s = sorted(values)
    p95 = quantiles(s, n=20)[18] if n >= 20 else max(s)
    return {
        "n":      n,
        "mean":   mean(values),
        "median": median(values),
        "p95":    p95,
        "std":    pstdev(values) if n > 1 else 0.0,
        "min":    min(values),
        "max":    max(values),
    }


def format_stats(label: str, s: dict) -> str:
    if s.get("n", 0) == 0:
        return f"{label}: no data"
    return (
        f"{label} (n={s['n']}):\n"
        f"  mean    = {s['mean']:.2f} ms\n"
        f"  median  = {s['median']:.2f} ms\n"
        f"  p95     = {s['p95']:.2f} ms\n"
        f"  std     = {s['std']:.2f} ms\n"
        f"  min/max = {s['min']:.2f} / {s['max']:.2f} ms"
    )


# ---------------------------------------------------------------------------
# Plots
# ---------------------------------------------------------------------------

def plot_histogram(t_reg, t_ver, out: Path) -> None:
    fig, axes = plt.subplots(1, 2, figsize=(11, 4.5), dpi=160)
    if t_reg:
        axes[0].hist(t_reg, bins=20, color="#1D9E75", edgecolor="white")
    axes[0].set_title("Distribución de T_reg (latencia de registro)")
    axes[0].set_xlabel("ms")
    axes[0].set_ylabel("Frecuencia")
    axes[0].grid(axis="y", alpha=0.3)

    if t_ver:
        axes[1].hist(t_ver, bins=20, color="#2E75B6", edgecolor="white")
    axes[1].set_title("Distribución de T_ver (latencia de verificación)")
    axes[1].set_xlabel("ms")
    axes[1].set_ylabel("Frecuencia")
    axes[1].grid(axis="y", alpha=0.3)

    fig.tight_layout()
    out.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    logger.info("Histogram saved to %s", out)


def plot_boxplot(t_reg, t_ver, out: Path) -> None:
    fig, ax = plt.subplots(figsize=(7, 5), dpi=160)
    data = []
    labels = []
    if t_reg:
        data.append(t_reg); labels.append("T_reg")
    if t_ver:
        data.append(t_ver); labels.append("T_ver")
    if not data:
        return
    bp = ax.boxplot(data, tick_labels=labels, patch_artist=True,
                    boxprops={"facecolor": "#E1F5EE", "edgecolor": "#1D9E75"},
                    medianprops={"color": "#085041", "linewidth": 2})
    ax.set_ylabel("Latencia (ms)")
    ax.set_title("Comparación de latencias")
    ax.grid(axis="y", alpha=0.3)
    fig.tight_layout()
    out.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    logger.info("Boxplot saved to %s", out)


# ---------------------------------------------------------------------------
# Scenarios summary
# ---------------------------------------------------------------------------

def summarize_scenarios(path: Path) -> str:
    if not path.exists():
        return "Scenarios CSV not found.\n"
    rows = list(csv.DictReader(path.open("r", encoding="utf-8")))
    if not rows:
        return "Scenarios CSV is empty.\n"
    passed = sum(1 for r in rows if r.get("passed") == "YES")
    total = len(rows)
    lines = [f"Scenarios: {passed}/{total} PASSED", ""]
    for r in rows:
        marker = "PASS" if r.get("passed") == "YES" else "FAIL"
        lines.append(
            f"  [{marker}] {r['scenario_id']}: {r['description']}"
            f" | expected={r['expected']} actual={r['actual']}"
        )
    return "\n".join(lines) + "\n"


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main(argv=None) -> int:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )
    parser = argparse.ArgumentParser(
        description="Compute statistics and figures from benchmark CSVs.",
    )
    parser.add_argument("--latencies", type=Path,
                        default=Path("docs/results/latencies.csv"))
    parser.add_argument("--scenarios", type=Path,
                        default=Path("docs/results/scenarios.csv"))
    parser.add_argument("--figures-dir", type=Path,
                        default=Path("docs/results/figures"))
    parser.add_argument("--summary", type=Path,
                        default=Path("docs/results/summary.txt"))
    args = parser.parse_args(argv)

    if not args.latencies.exists():
        logger.error("Latencies file not found: %s", args.latencies)
        return 2

    t_reg, t_ver, statuses = load_latencies(args.latencies)
    s_reg = stats(t_reg)
    s_ver = stats(t_ver)

    integro_count = sum(1 for st in statuses if st == "INTEGRO")
    detection_rate = (integro_count / len(statuses) * 100.0) if statuses else 0.0

    summary_lines = [
        "BENCHMARK SUMMARY",
        "=" * 64,
        format_stats("T_reg (latencia de registro)", s_reg),
        "",
        format_stats("T_ver (latencia de verificación)", s_ver),
        "",
        f"Tasa de éxito de registro+verificación: {detection_rate:.1f}% "
        f"({integro_count}/{len(statuses)} ejecuciones)",
        "",
        summarize_scenarios(args.scenarios),
    ]
    summary = "\n".join(summary_lines)
    args.summary.parent.mkdir(parents=True, exist_ok=True)
    args.summary.write_text(summary, encoding="utf-8")
    print(summary)
    logger.info("Summary saved to %s", args.summary)

    # Figures
    plot_histogram(t_reg, t_ver, args.figures_dir / "latency_histogram.png")
    plot_boxplot(t_reg, t_ver, args.figures_dir / "latency_boxplot.png")
    return 0


if __name__ == "__main__":
    sys.exit(main())
