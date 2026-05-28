import matplotlib
matplotlib.use("Agg")   # non-interactive; must be set before pyplot import
import matplotlib.pyplot as plt
import matplotlib.gridspec as gridspec
import cv2
import numpy as np
import os


class ForensicReporter:
    """
    2×3 forensic report grid:

      [0,0] Source image     [0,1] ELA heatmap      [0,2] κ trajectory
      [1,0] FRW trust bars   [1,1] Semantic status   [1,2] Final verdict
    """

    CLEAN_THRESH    = 8.0
    DEGRADED_THRESH = 20.0
    PALETTE = {
        "ORGANIC":                    "#27ae60",
        "SYNTHETIC (OVER-COHERENT)":  "#f39c12",
        "COMPOSITE (MANIFOLD COLLISION)": "#e74c3c",
        "LAUNDERED / COMPRESSED":     "#8e44ad",
        "MALFORMED / ADVERSARIAL":    "#c0392b",
        "ORGANIC / COMPLEX_TEXTURE":  "#2ecc71",
        "LAUNDERED / FALSE_CONFLICT": "#16a085",
    }

    def render(self, ladder_data: list, trajectory: dict,
               semantic_result=None, ela_map=None,
               feature_trust: dict = None, image_path: str = None,
               output_path: str = "report.png") -> str:

        fig = plt.figure(figsize=(20, 13), facecolor="#1a1a2e")
        gs  = gridspec.GridSpec(2, 3, figure=fig,
                                hspace=0.45, wspace=0.35)

        self._panel_source(fig.add_subplot(gs[0, 0]), image_path)
        self._panel_ela(fig.add_subplot(gs[0, 1]), ela_map)
        self._panel_kappa(fig.add_subplot(gs[0, 2]), ladder_data, trajectory)
        self._panel_frw(fig.add_subplot(gs[1, 0]), feature_trust)
        self._panel_semantic(fig.add_subplot(gs[1, 1]), semantic_result)
        self._panel_verdict(fig.add_subplot(gs[1, 2]),
                            trajectory["structural_class"], trajectory)

        fname = os.path.basename(image_path) if image_path else "unknown"
        fig.suptitle(f"Artifact Lens — Forensic Signature Report\n{fname}",
                     fontsize=15, fontweight="bold", color="white", y=0.98)

        os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
        fig.savefig(output_path, dpi=150, bbox_inches="tight",
                    facecolor=fig.get_facecolor())
        plt.close(fig)
        return output_path

    def generate_report(self, image_path: str, results: dict,
                        output_dir: str = "outputs") -> str:
        """
        Spec-named entry point.  Derives the output path as
        outputs/FORENSIC_<basename>.png and delegates to render().
        """
        os.makedirs(output_dir, exist_ok=True)
        img_name    = os.path.basename(image_path)
        output_path = os.path.join(output_dir, f"FORENSIC_{img_name}.png")

        ela_map = results.get("ela_map")
        if ela_map is None:
            ladder = results.get("ladder_data", [])
            ela_map = ladder[-1].get("ela_map") if ladder else None

        return self.render(
            ladder_data    = results.get("ladder_data", []),
            trajectory     = results.get("trajectory", {}),
            semantic_result= results.get("semantic_validation")
                             if isinstance(results.get("semantic_validation"), dict)
                             else None,
            ela_map        = ela_map,
            feature_trust  = results.get("feature_trust"),
            image_path     = image_path,
            output_path    = output_path,
        )

    # ------------------------------------------------------------------
    # Panel helpers
    # ------------------------------------------------------------------

    def _panel_source(self, ax, image_path):
        ax.set_facecolor("#0d0d1a")
        if image_path and os.path.exists(image_path):
            img_bgr = cv2.imread(image_path)
            img_rgb = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2RGB)
            ax.imshow(img_rgb)
            ax.set_title("Source Image", color="white", fontsize=11, pad=6)
        else:
            ax.text(0.5, 0.5, "No source", ha="center", va="center",
                    color="grey", transform=ax.transAxes)
        ax.axis("off")

    def _panel_ela(self, ax, ela_map):
        ax.set_facecolor("#0d0d1a")
        ax.set_title("ELA Residual Map (Q=10)", color="white", fontsize=11, pad=6)
        if ela_map is not None:
            ela_gray = np.mean(ela_map, axis=2) if ela_map.ndim == 3 else ela_map
            ela_norm = (ela_gray - ela_gray.min()) / (ela_gray.max() - ela_gray.min() + 1e-8)
            im = ax.imshow(ela_norm, cmap="inferno", vmin=0, vmax=1)
            plt.colorbar(im, ax=ax, fraction=0.046, pad=0.04).ax.tick_params(colors="white")
        else:
            ax.text(0.5, 0.5, "ELA unavailable", ha="center", va="center",
                    color="grey", transform=ax.transAxes)
        ax.axis("off")

    def _panel_kappa(self, ax, ladder_data, trajectory):
        ax.set_facecolor("#0d0d1a")
        qualities = [r["quality"] for r in ladder_data]
        kappas    = [r["kappa"]   for r in ladder_data]

        ax.plot(qualities, kappas, "o-", color="#00d2ff", linewidth=2,
                label="κ (spatial CoV)")
        ax.axhline(self.CLEAN_THRESH,    color="#27ae60", linestyle="--",
                   alpha=0.6, label=f"Stable < {self.CLEAN_THRESH}")
        ax.axhline(self.DEGRADED_THRESH, color="#e74c3c", linestyle="--",
                   alpha=0.6, label=f"Degraded > {self.DEGRADED_THRESH}")

        for i in range(1, len(kappas)):
            if abs(kappas[i] - kappas[i - 1]) > 3:
                ax.scatter(qualities[i], kappas[i], s=100,
                           facecolors="none", edgecolors="#ff6b6b", linewidth=2)

        ax.set_title(
            f"κ Trajectory — {trajectory['kappa_profile'].upper()}",
            color="white", fontsize=11, pad=6)
        ax.set_xlabel("JPEG Quality →", color="white", fontsize=9)
        ax.set_ylabel("κ", color="white", fontsize=9)
        ax.invert_xaxis()
        ax.tick_params(colors="white")
        ax.legend(fontsize=8, labelcolor="white",
                  facecolor="#1a1a2e", edgecolor="grey")
        for sp in ax.spines.values():
            sp.set_color("#444466")

    def _panel_frw(self, ax, feature_trust):
        ax.set_facecolor("#0d0d1a")
        ax.set_title("FRW Feature Trust Weights", color="white", fontsize=11, pad=6)

        if feature_trust:
            labels  = [k.upper() for k in feature_trust]
            values  = list(feature_trust.values())
            colors  = ["#00d2ff", "#a29bfe", "#fd79a8"]
            bars    = ax.bar(labels, values, color=colors, width=0.5)
            for bar, v in zip(bars, values):
                ax.text(bar.get_x() + bar.get_width() / 2,
                        bar.get_height() + 0.01,
                        f"{v:.2f}", ha="center", color="white", fontsize=10)
            ax.set_ylim(0, max(values) * 1.25)
        else:
            ax.text(0.5, 0.5, "FRW unavailable", ha="center", va="center",
                    color="grey", transform=ax.transAxes)

        ax.tick_params(colors="white")
        ax.set_ylabel("Trust Weight", color="white", fontsize=9)
        for sp in ax.spines.values():
            sp.set_color("#444466")

    def _panel_semantic(self, ax, semantic_result):
        ax.set_facecolor("#0d0d1a")
        ax.set_title("Semantic Validation Gate", color="white", fontsize=11, pad=6)
        ax.axis("off")

        if isinstance(semantic_result, dict):
            conflict = semantic_result.get("semantic_conflict", False)
            dist     = semantic_result.get("max_latent_distance", 0.0)
            thresh   = semantic_result.get("threshold_used", 0.45)
            verdict  = semantic_result.get("verdict", "—")

            status_color = "#e74c3c" if conflict else "#27ae60"
            status_text  = "CONFLICT CONFIRMED" if conflict else "NO CONFLICT"

            ax.text(0.5, 0.75, status_text, ha="center", va="center",
                    transform=ax.transAxes, fontsize=14, fontweight="bold",
                    color=status_color)
            ax.text(0.5, 0.52,
                    f"Max cosine distance: {dist:.4f}\nThreshold: {thresh}",
                    ha="center", va="center", transform=ax.transAxes,
                    fontsize=10, color="white")
            ax.text(0.5, 0.3, verdict, ha="center", va="center",
                    transform=ax.transAxes, fontsize=10,
                    color="#dfe6e9", style="italic")
        else:
            ax.text(0.5, 0.5, "Semantic gate\nnot triggered",
                    ha="center", va="center", transform=ax.transAxes,
                    fontsize=12, color="#636e72")

    def _panel_verdict(self, ax, structural_class, trajectory):
        ax.set_facecolor("#0d0d1a")
        ax.set_title("Final Forensic Verdict", color="white", fontsize=11, pad=6)
        ax.axis("off")

        key = next((k for k in self.PALETTE if structural_class.startswith(k)), None)
        verdict_color = self.PALETTE.get(key, "#dfe6e9")

        metrics = trajectory.get("metrics", {})

        ax.text(0.5, 0.72, structural_class, ha="center", va="center",
                transform=ax.transAxes, fontsize=12, fontweight="bold",
                color=verdict_color, wrap=True,
                bbox=dict(boxstyle="round,pad=0.4", facecolor="#0d0d2e",
                          edgecolor=verdict_color, linewidth=2))

        summary = (
            f"κ profile:    {trajectory.get('kappa_profile', '—').upper()}\n"
            f"Disagreement: {trajectory.get('disagreement_profile', '—').upper()}\n"
            f"Avg κ slope:  {metrics.get('kappa_slope', '—')}\n"
            f"Avg conflict: {metrics.get('avg_disagreement', '—')}\n"
            f"Δw (FRW):     {metrics.get('delta_w', '—')}"
        )
        ax.text(0.5, 0.33, summary, ha="center", va="center",
                transform=ax.transAxes, fontsize=9,
                color="#b2bec3", family="monospace",
                bbox=dict(boxstyle="round,pad=0.3", facecolor="#12122a",
                          edgecolor="#444466"))
