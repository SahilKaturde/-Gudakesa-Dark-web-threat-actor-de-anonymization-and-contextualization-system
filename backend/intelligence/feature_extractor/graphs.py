"""
Matplotlib graph generation for GUDAKESA Feature Extractor.
Returns charts as base64-encoded PNG strings.
"""
import io
import base64
from typing import List, Dict

import matplotlib
matplotlib.use("Agg")


PALETTE = ["#6366f1", "#8b5cf6", "#d946ef", "#f43f5e", "#fb923c", "#facc15", "#4ade80", "#22d3ee", "#38bdf8", "#a78bfa"]
BG_DARK = "#0f172a"
BG_MID = "#1e293b"
GRID_COLOR = "#334155"
TEXT_COLOR = "#e2e8f0"


def _base_style():
    """Apply consistent dark theme to current matplotlib figure."""
    import matplotlib.pyplot as plt
    plt.rcParams.update({
        "figure.facecolor": BG_DARK,
        "axes.facecolor": BG_MID,
        "axes.edgecolor": GRID_COLOR,
        "axes.labelcolor": TEXT_COLOR,
        "axes.titlecolor": TEXT_COLOR,
        "xtick.color": TEXT_COLOR,
        "ytick.color": TEXT_COLOR,
        "grid.color": GRID_COLOR,
        "text.color": TEXT_COLOR,
        "font.family": "sans-serif",
        "font.size": 10,
    })


def _fig_to_base64(fig) -> str:
    """Convert a matplotlib figure to a base64 PNG string."""
    import matplotlib.pyplot as plt
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=130, bbox_inches="tight", facecolor=BG_DARK)
    buf.seek(0)
    encoded = base64.b64encode(buf.read()).decode("utf-8")
    plt.close(fig)
    buf.close()
    return encoded


# ---------------------------------------------------------------------------
# LLM-callable chart builders (labels, values, title)
# ---------------------------------------------------------------------------
def generate_custom_bar_chart(
    labels: List[str],
    values: List[float],
    title: str,
    x_label: str = "",
    y_label: str = "",
) -> str:
    """Vertical bar chart from LLM tool arguments."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    _base_style()
    if not labels or not values:
        return ""

    fig, ax = plt.subplots(figsize=(10, 6), facecolor=BG_DARK)
    colors = PALETTE * (len(labels) // len(PALETTE) + 1)

    bars = ax.bar(
        labels, values,
        color=colors[: len(labels)],
        edgecolor="none", linewidth=0, zorder=3,
    )

    ax.set_title(title, fontsize=14, pad=16, fontweight="bold", color=TEXT_COLOR)
    if x_label:
        ax.set_xlabel(x_label, labelpad=10, color=TEXT_COLOR)
    if y_label:
        ax.set_ylabel(y_label, labelpad=10, color=TEXT_COLOR)

    ax.yaxis.grid(True, linestyle="--", alpha=0.4, zorder=0)
    ax.set_axisbelow(True)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    plt.xticks(rotation=45, ha="right", fontsize=9)

    max_v = max(values) if values else 0.08
    for bar, val in zip(bars, values):
        ax.text(
            bar.get_x() + bar.get_width() / 2,
            bar.get_height() + (max_v * 0.02 if max_v else 0.08),
            str(val),
            ha="center", va="bottom",
            fontweight="bold", fontsize=9, color=TEXT_COLOR,
        )

    plt.tight_layout()
    return _fig_to_base64(fig)


def generate_custom_pie_chart(
    labels: List[str],
    values: List[float],
    title: str,
) -> str:
    """Pie chart from LLM tool arguments. Matplotlib normalizes values."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    _base_style()
    if not labels or not values or len(labels) != len(values):
        return ""

    fig, ax = plt.subplots(figsize=(8, 6), facecolor=BG_DARK)
    colors = PALETTE * (len(labels) // len(PALETTE) + 1)

    wedges, texts, autotexts = ax.pie(
        values,
        labels=labels,
        autopct="%1.1f%%",
        colors=colors[: len(labels)],
        startangle=140,
        pctdistance=0.82,
        wedgeprops={"linewidth": 2, "edgecolor": BG_DARK},
    )
    for t in list(texts) + list(autotexts):
        t.set_color(TEXT_COLOR)
        t.set_fontsize(9)

    ax.set_title(title, fontsize=14, pad=16, fontweight="bold", color=TEXT_COLOR)
    plt.tight_layout()
    return _fig_to_base64(fig)


def generate_custom_confidence_chart(
    labels: List[str],
    values: List[float],
    title: str,
    x_label: str = "Confidence Score",
) -> str:
    """Horizontal bar chart for 0-1 metrics. Values > 1 are treated as percentages."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    _base_style()
    if not labels or not values or len(labels) != len(values):
        return ""

    clean_values = []
    for v in values:
        try:
            f = float(v)
        except (TypeError, ValueError):
            f = 0.0
        if f > 1.0:
            f = f / 100.0
        clean_values.append(max(0.0, min(1.0, f)))

    colors = [PALETTE[i % len(PALETTE)] for i in range(len(labels))]
    fig, ax = plt.subplots(
        figsize=(8, max(3, len(labels) * 0.7 + 1)),
        facecolor=BG_DARK,
    )

    bars = ax.barh(
        labels, clean_values,
        color=colors, edgecolor="none", height=0.55, zorder=3,
    )
    ax.set_xlim(0, 1.12)
    ax.set_xlabel(x_label, labelpad=10)
    ax.set_title(title, fontsize=13, pad=14, fontweight="bold")
    ax.xaxis.grid(True, linestyle="--", alpha=0.35, zorder=0)
    ax.set_axisbelow(True)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)

    for bar, val in zip(bars, clean_values):
        ax.text(
            val + 0.02,
            bar.get_y() + bar.get_height() / 2,
            f"{val:.2f}",
            va="center", fontsize=9,
        )

    plt.tight_layout()
    return _fig_to_base64(fig)


# ---------------------------------------------------------------------------
# Feature-list chart builders (kept for callers with a raw features list)
# ---------------------------------------------------------------------------
def generate_feature_bar(features: List[Dict]) -> str:
    """Bar chart: count of each feature type."""
    import matplotlib.pyplot as plt
    from collections import Counter

    _base_style()
    type_counts = Counter(f.get("feature_type", "other") for f in features)

    fig, ax = plt.subplots(figsize=(9, 5))
    bars = ax.bar(
        list(type_counts.keys()),
        list(type_counts.values()),
        color=PALETTE[: len(type_counts)],
        edgecolor="none", linewidth=0, zorder=3,
    )
    ax.set_title("Extracted Threat Indicators by Category",
                 fontsize=14, pad=16, fontweight="bold")
    ax.set_ylabel("Count", labelpad=10)
    ax.yaxis.grid(True, linestyle="--", alpha=0.4, zorder=0)
    ax.set_axisbelow(True)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    for bar, val in zip(bars, type_counts.values()):
        ax.text(
            bar.get_x() + bar.get_width() / 2,
            bar.get_height() + 0.08,
            str(val),
            ha="center", va="bottom", fontweight="bold", fontsize=11,
        )
    plt.tight_layout()
    return _fig_to_base64(fig)


def generate_feature_pie(features: List[Dict]) -> str:
    """Pie chart: proportion of each feature type."""
    import matplotlib.pyplot as plt
    from collections import Counter

    _base_style()
    type_counts = Counter(f.get("feature_type", "other") for f in features)

    fig, ax = plt.subplots(figsize=(8, 6), facecolor=BG_DARK)
    wedges, texts, autotexts = ax.pie(
        type_counts.values(),
        labels=type_counts.keys(),
        autopct="%1.1f%%",
        colors=PALETTE[: len(type_counts)],
        startangle=140,
        pctdistance=0.82,
        wedgeprops={"linewidth": 2, "edgecolor": BG_DARK},
    )
    for t in list(texts) + list(autotexts):
        t.set_color(TEXT_COLOR)
        t.set_fontsize(9)
    ax.set_title("Threat Indicator Distribution",
                 fontsize=14, pad=16, fontweight="bold", color=TEXT_COLOR)
    plt.tight_layout()
    return _fig_to_base64(fig)


def generate_confidence_chart(features: List[Dict]) -> str:
    """Horizontal bar: average confidence per feature type."""
    import matplotlib.pyplot as plt

    _base_style()
    by_type: Dict[str, list] = {}
    for f in features:
        by_type.setdefault(f.get("feature_type", "other"), []).append(
            f.get("confidence_score") or 0.7
        )
    avg = {k: round(sum(v) / len(v), 3) for k, v in by_type.items()}

    labels = list(avg.keys())
    values = list(avg.values())
    colors = [PALETTE[i % len(PALETTE)] for i in range(len(labels))]

    fig, ax = plt.subplots(
        figsize=(8, max(3, len(labels) * 0.7 + 1)),
        facecolor=BG_DARK,
    )
    bars = ax.barh(labels, values, color=colors, edgecolor="none",
                   height=0.55, zorder=3)
    ax.set_xlim(0, 1.12)
    ax.set_xlabel("Average Confidence Score", labelpad=10)
    ax.set_title("Confidence Score by Feature Type",
                 fontsize=13, pad=14, fontweight="bold")
    ax.xaxis.grid(True, linestyle="--", alpha=0.35, zorder=0)
    ax.set_axisbelow(True)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    for bar, val in zip(bars, values):
        ax.text(val + 0.02, bar.get_y() + bar.get_height() / 2,
                f"{val:.2f}", va="center", fontsize=9)
    plt.tight_layout()
    return _fig_to_base64(fig)


def generate_feature_graph(features: List[Dict], graph_type: str = "bar") -> str:
    """Dispatcher for feature-list charts. graph_type: 'bar'|'pie'|'confidence'."""
    if not features:
        return ""
    try:
        if graph_type == "pie":
            return generate_feature_pie(features)
        if graph_type == "confidence":
            return generate_confidence_chart(features)
        return generate_feature_bar(features)
    except Exception as e:
        print(f"[Graphs] Error generating '{graph_type}' graph: "
              f"{type(e).__name__}: {e}")
        return ""