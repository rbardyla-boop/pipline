import matplotlib.pyplot as plt
import numpy as np

class ArtifactDashboard:
    """
    Diagnostic dashboard for Artifact Lens v1.2.
    Visualizes the structural integrity of media across the compression ladder.
    """
    def __init__(self):
        # Regime thresholds based on TOLS v3 spec
        self.clean_thresh = 8
        self.degraded_thresh = 20

    def render(self, ladder_data, trajectory, filename="artifact_signature.png"):
        qualities = [r["quality"] for r in ladder_data]
        kappas = [r["kappa"] for r in ladder_data]
        disagreement = [r["disagreement"] for r in ladder_data]
        
        # Features
        ela = [r["ela"] for r in ladder_data]
        fft = [r["fft"] for r in ladder_data]
        noise = [r["noise"] for r in ladder_data]

        fig, (ax1, ax2, ax3) = plt.subplots(3, 1, figsize=(11, 14), sharex=True)

        # --- 1. KAPPA (κ) CURVE & REGIME MARKERS ---
        ax1.plot(qualities, kappas, 'o-', color='#2c3e50', linewidth=2, label="$\kappa$ (Stability)")
        ax1.axhline(self.clean_thresh, color='green', linestyle='--', alpha=0.5, label="Clean Limit")
        ax1.axhline(self.degraded_thresh, color='red', linestyle='--', alpha=0.5, label="Degraded Limit")
        
        # Highlight Instability Points (Ghost Points)
        for i in range(1, len(kappas)):
            if abs(kappas[i] - kappas[i-1]) > 5:
                ax1.scatter(qualities[i], kappas[i], s=150, facecolors='none', edgecolors='red', linewidth=2)

        ax1.set_title(f"Spectral Stability Profile ($\kappa$)", loc='left', fontsize=12, fontweight='bold')
        ax1.set_ylabel("Condition Number ($\kappa$)")
        ax1.legend(loc='upper right')
        ax1.grid(True, alpha=0.2)

        # --- 2. DISAGREEMENT (CONFLICT) CURVE ---
        ax2.fill_between(qualities, 0, disagreement, color='#8e44ad', alpha=0.2)
        ax2.plot(qualities, disagreement, 'D-', color='#8e44ad', markersize=4, label="Signal Variance")
        ax2.set_title("Manifold Conflict (Disagreement)", loc='left', fontsize=12, fontweight='bold')
        ax2.set_ylabel("Variance")
        ax2.grid(True, alpha=0.2)

        # --- 3. FEATURE SUBSYSTEM BREAKDOWN ---
        ax3.plot(qualities, ela, label="ELA (Pixel Delta)", alpha=0.8)
        ax3.plot(qualities, fft, label="FFT (Frequency)", alpha=0.8)
        ax3.plot(qualities, noise, label="Noise Residual", alpha=0.8)
        ax3.set_title("Subsystem Response", loc='left', fontsize=12, fontweight='bold')
        ax3.set_ylabel("Normalized Score")
        ax3.set_xlabel("JPEG Quality (Launder Stress)")
        ax3.legend(loc='upper right')
        ax3.grid(True, alpha=0.2)

        # --- FINAL VERDICT OVERLAY ---
        verdict_text = (
            f"STRUCTURAL CLASS: {trajectory['structural_class']}\n"
            f"KAPPA TRAJECTORY: {trajectory['kappa_profile'].upper()}\n"
            f"SIGNAL STATE: {trajectory['disagreement_profile'].upper()}"
        )
        plt.suptitle(f"Artifact Lens Forensic Signature: {filename}\n", fontsize=16, fontweight='bold')
        fig.text(0.5, 0.02, verdict_text, ha='center', fontsize=12, 
                 bbox=dict(facecolor='white', alpha=0.8, edgecolor='#2c3e50', boxstyle='round,pad=1'))

        plt.tight_layout(rect=[0, 0.05, 1, 0.95])
        plt.gca().invert_xaxis()
        plt.show()