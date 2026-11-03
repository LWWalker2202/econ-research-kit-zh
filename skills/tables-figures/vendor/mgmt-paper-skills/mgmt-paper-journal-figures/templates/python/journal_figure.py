"""Minimal journal-style figure template.

Run:
    python3 journal_figure.py

Output:
    journal_figure.pdf
"""

from __future__ import annotations

JOURNAL = "Nature"
STYLE = {
    "Nature": {"figsize": (3.5, 2.5), "font": "Arial", "color": "#1F77B4"},
    "Management Science": {"figsize": (3.4, 2.4), "font": "Times New Roman", "color": "0.1"},
    "Academy of Management Journal": {"figsize": (3.5, 2.45), "font": "Times New Roman", "color": "#4C78A8"},
    "Administrative Science Quarterly": {"figsize": (3.6, 2.5), "font": "Times New Roman", "color": "0.15"},
    "Organization Science": {"figsize": (3.5, 2.45), "font": "Times New Roman", "color": "#2F4B7C"},
    "Strategic Management Journal": {"figsize": (3.4, 2.4), "font": "Times New Roman", "color": "0.1"},
    "Journal of Finance": {"figsize": (3.3, 2.35), "font": "Times New Roman", "color": "0.1"},
    "管理世界": {"figsize": (3.4, 2.45), "font": "Songti SC", "color": "0.1"},
}


def fallback_svg(path: str) -> None:
    with open(path, "w", encoding="utf-8") as handle:
        handle.write("""<svg xmlns="http://www.w3.org/2000/svg" width="420" height="280" viewBox="0 0 420 280">
<rect width="420" height="280" fill="white"/>
<text x="28" y="28" font-family="Arial" font-size="14">Journal figure preview</text>
<line x1="60" y1="220" x2="380" y2="220" stroke="black"/>
<line x1="60" y1="40" x2="60" y2="220" stroke="black"/>
<polyline points="60,180 100,170 140,165 180,145 220,100 260,82 300,76 340,70 380,66" fill="none" stroke="#1F77B4" stroke-width="3"/>
<line x1="180" y1="40" x2="180" y2="220" stroke="#999" stroke-dasharray="4 4"/>
<text x="180" y="245" font-family="Arial" font-size="11">Event time</text>
<text x="18" y="140" font-family="Arial" font-size="11" transform="rotate(-90 18,140)">Estimate</text>
</svg>
""")


def main() -> None:
    profile = STYLE.get(JOURNAL, STYLE["Management Science"])
    try:
        import matplotlib.pyplot as plt
    except ModuleNotFoundError:
        fallback_svg("journal_figure.svg")
        return

    plt.rcParams.update({
        "font.family": profile["font"],
        "axes.linewidth": 0.8,
        "pdf.fonttype": 42,
        "ps.fonttype": 42,
    })
    x = list(range(-4, 5))
    y = [-0.02, -0.01, 0.00, 0.01, 0.05, 0.08, 0.09, 0.10, 0.11]
    ci = [0.03, 0.025, 0.024, 0.022, 0.021, 0.023, 0.026, 0.028, 0.03]
    fig, ax = plt.subplots(figsize=profile["figsize"])
    ax.axhline(0, color="0.25", linewidth=0.8)
    ax.axvline(-1, color="0.65", linewidth=0.8, linestyle="--")
    ax.errorbar(x, y, yerr=ci, marker="o", color=profile["color"], linewidth=1.2, capsize=2)
    ax.set_xlabel("Event time", fontsize=8)
    ax.set_ylabel("Estimate", fontsize=8)
    ax.tick_params(labelsize=7)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    fig.tight_layout()
    fig.savefig("journal_figure.pdf", dpi=300, bbox_inches="tight")


if __name__ == "__main__":
    main()
