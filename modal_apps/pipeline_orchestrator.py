"""
Foundry Design Pipeline Orchestrator

Coordinates RFD3 → MPNN → RF3 pipeline across separate Modal apps.

This orchestrator:
1. Calls foundry_rfd3.py to generate backbones (A100)
2. Calls foundry_mpnn.py in parallel to design sequences (A10G)
3. Calls foundry_rf3.py in parallel to predict structures (A100)
4. Filters and ranks results by confidence metrics

Each stage uses an optimized container with only the necessary dependencies.
"""

import modal
from pathlib import Path
from typing import Optional

app = modal.App("foundry-pipeline")

# Import the other Modal apps as dependencies
# Modal will handle cross-app function calls
rfd3_app = modal.App.lookup("foundry-rfd3", create_if_missing=False)
mpnn_app = modal.App.lookup("foundry-mpnn", create_if_missing=False)
rf3_app = modal.App.lookup("foundry-rf3", create_if_missing=False)

# Shared volumes
results_volume = modal.Volume.from_name("foundry-results", create_if_missing=True)

# ============================================================================
# Pipeline Functions
# ============================================================================

@app.function(
    volumes={"/results": results_volume},
    timeout=7200,  # 2 hours max for full pipeline
)
def run_pipeline(
    target_pdb: str,
    num_backbones: int = 100,
    sequences_per_backbone: int = 10,
    pipeline_config: dict = None,
    output_dir: str = "/results/pipeline",
):
    """
    Run the complete RFD3 → MPNN → RF3 design pipeline.

    Args:
        target_pdb: Target structure PDB string
        num_backbones: Number of backbones to generate with RFD3
        sequences_per_backbone: Number of sequences per backbone with MPNN
        pipeline_config: Configuration for each stage
            Example: {
                "rfd3": {"num_steps": 50, "temperature": 1.0},
                "mpnn": {"temperature": 0.1},
                "rf3": {"num_recycles": 3},
            }
        output_dir: Base output directory

    Returns:
        dict: {
            "backbones": [...],
            "sequences": [...],
            "predictions": [...],  # Sorted by confidence
            "summary": {
                "total_backbones": 100,
                "total_sequences": 1000,
                "total_predictions": 1000,
                "top_plddt": 95.2,
                "avg_plddt": 82.1,
            }
        }
    """
    from pathlib import Path
    import modal

    # Import functions from other apps
    from modal_apps.foundry_rfd3 import generate_backbones
    from modal_apps.foundry_mpnn import design_sequences
    from modal_apps.foundry_rf3 import predict_structure

    config = pipeline_config or {}
    output_path = Path(output_dir)

    print("=" * 80)
    print("🚀 FOUNDRY DESIGN PIPELINE")
    print("=" * 80)
    print(f"Target: {len(target_pdb)} characters")
    print(f"Pipeline: {num_backbones} backbones × {sequences_per_backbone} sequences = {num_backbones * sequences_per_backbone} total designs")
    print()

    # ========================================================================
    # Stage 1: Generate Backbones (RFD3)
    # ========================================================================
    print("📐 STAGE 1: Generating backbones with RFD3 (A100)")
    print("-" * 80)

    backbones = generate_backbones.remote(
        target_pdb=target_pdb,
        num_designs=num_backbones,
        design_config=config.get("rfd3"),
        output_dir=str(output_path / "backbones"),
    )

    print(f"✅ Generated {len(backbones)} backbones")
    print()

    # ========================================================================
    # Stage 2: Design Sequences (MPNN) - Parallel
    # ========================================================================
    print("🧬 STAGE 2: Designing sequences with MPNN (A10G)")
    print("-" * 80)
    print(f"Running {len(backbones)} parallel MPNN jobs...")

    # Map over backbones in parallel
    sequence_jobs = [
        design_sequences.remote(
            backbone_pdb=bb["pdb_string"],
            num_sequences=sequences_per_backbone,
            design_config=config.get("mpnn"),
            output_dir=str(output_path / "sequences" / bb["backbone_id"]),
        )
        for bb in backbones
    ]

    # Flatten results
    all_sequences = []
    for sequences in sequence_jobs:
        all_sequences.extend(sequences)

    print(f"✅ Designed {len(all_sequences)} total sequences")
    print()

    # ========================================================================
    # Stage 3: Predict Structures (RF3) - Parallel
    # ========================================================================
    print("🔮 STAGE 3: Predicting structures with RF3 (A100)")
    print("-" * 80)
    print(f"Running {len(all_sequences)} parallel RF3 jobs...")

    # Map over sequences in parallel
    prediction_jobs = [
        predict_structure.remote(
            sequence=seq["sequence"],
            backbone_pdb=seq["backbone_pdb"],
            prediction_config=config.get("rf3"),
            output_dir=str(output_path / "predictions"),
        )
        for seq in all_sequences
    ]

    predictions = list(prediction_jobs)

    print(f"✅ Predicted {len(predictions)} structures")
    print()

    # ========================================================================
    # Post-processing: Filter and Rank
    # ========================================================================
    print("📊 POST-PROCESSING: Filtering and ranking")
    print("-" * 80)

    # Sort by pLDDT (confidence)
    predictions_sorted = sorted(
        predictions,
        key=lambda x: x["confidence_metrics"]["plddt"],
        reverse=True
    )

    # Calculate summary statistics
    plddts = [p["confidence_metrics"]["plddt"] for p in predictions]
    avg_plddt = sum(plddts) / len(plddts)
    top_plddt = max(plddts)

    summary = {
        "total_backbones": len(backbones),
        "total_sequences": len(all_sequences),
        "total_predictions": len(predictions),
        "top_plddt": top_plddt,
        "avg_plddt": avg_plddt,
    }

    # Save summary
    import json
    summary_path = output_path / "pipeline_summary.json"
    summary_path.parent.mkdir(parents=True, exist_ok=True)
    with open(summary_path, "w") as f:
        json.dump(summary, f, indent=2)

    results_volume.commit()

    print(f"✅ Pipeline complete!")
    print(f"   Total designs: {len(predictions)}")
    print(f"   Average pLDDT: {avg_plddt:.1f}")
    print(f"   Top pLDDT: {top_plddt:.1f}")
    print(f"   Output: {output_dir}")
    print("=" * 80)

    return {
        "backbones": backbones,
        "sequences": all_sequences,
        "predictions": predictions_sorted,
        "summary": summary,
    }


@app.function(timeout=300)
def run_quick_test():
    """
    Quick pipeline test with minimal resources (5 backbones, 2 sequences each).

    Usage:
        modal run modal_apps/pipeline_orchestrator.py::run_quick_test
    """
    print("🧪 Running quick pipeline test (5 backbones × 2 sequences = 10 designs)")

    # Simple target structure
    target_pdb = """ATOM      1  N   ALA A   1       0.000   0.000   0.000  1.00  0.00           N
ATOM      2  CA  ALA A   1       1.458   0.000   0.000  1.00  0.00           C
END
"""

    results = run_pipeline.remote(
        target_pdb=target_pdb,
        num_backbones=5,
        sequences_per_backbone=2,
        output_dir="/results/pipeline_test",
    )

    print("\n" + "=" * 80)
    print("🎉 TEST COMPLETE!")
    print("=" * 80)
    print(f"Generated {results['summary']['total_backbones']} backbones")
    print(f"Designed {results['summary']['total_sequences']} sequences")
    print(f"Predicted {results['summary']['total_predictions']} structures")
    print(f"Top pLDDT: {results['summary']['top_plddt']:.1f}")
    print(f"Avg pLDDT: {results['summary']['avg_plddt']:.1f}")
    print("\nTop 3 designs:")
    for i, pred in enumerate(results['predictions'][:3], 1):
        plddt = pred['confidence_metrics']['plddt']
        print(f"  {i}. {pred['sequence_id']}: pLDDT={plddt:.1f}")

    return results


# ============================================================================
# CLI Entrypoints
# ============================================================================

@app.local_entrypoint()
def test():
    """
    Run a quick test of the full pipeline.

    Usage:
        modal run modal_apps/pipeline_orchestrator.py::test
    """
    return run_quick_test.remote()


@app.local_entrypoint()
def run(
    target_pdb_path: str,
    num_backbones: int = 100,
    sequences_per_backbone: int = 10,
    output_dir: str = "/results/production",
):
    """
    Run the full production pipeline.

    Usage:
        modal run modal_apps/pipeline_orchestrator.py::run \\
            --target-pdb-path target.pdb \\
            --num-backbones 100 \\
            --sequences-per-backbone 10
    """
    from pathlib import Path

    # Read target PDB
    target_pdb = Path(target_pdb_path).read_text()

    print("🚀 Starting production pipeline")
    print(f"   Target: {target_pdb_path}")
    print(f"   Backbones: {num_backbones}")
    print(f"   Sequences per backbone: {sequences_per_backbone}")
    print(f"   Total designs: {num_backbones * sequences_per_backbone}")
    print()

    results = run_pipeline.remote(
        target_pdb=target_pdb,
        num_backbones=num_backbones,
        sequences_per_backbone=sequences_per_backbone,
        output_dir=output_dir,
    )

    # Save top designs locally
    output_local = Path("pipeline_results")
    output_local.mkdir(exist_ok=True)

    import json
    summary_file = output_local / "summary.json"
    with open(summary_file, "w") as f:
        json.dump(results["summary"], f, indent=2)

    top_designs_file = output_local / "top_10_designs.json"
    with open(top_designs_file, "w") as f:
        json.dump(results["predictions"][:10], f, indent=2)

    print("\n" + "=" * 80)
    print("🎉 PIPELINE COMPLETE!")
    print("=" * 80)
    print(f"Total designs: {results['summary']['total_predictions']}")
    print(f"Average pLDDT: {results['summary']['avg_plddt']:.1f}")
    print(f"Top pLDDT: {results['summary']['top_plddt']:.1f}")
    print(f"\nRemote output: {output_dir}")
    print(f"Local summary: {output_local}/")
    print("\nTop 10 designs by pLDDT:")
    for i, pred in enumerate(results["predictions"][:10], 1):
        plddt = pred["confidence_metrics"]["plddt"]
        seq_preview = pred["sequence"][:30] + ("..." if len(pred["sequence"]) > 30 else "")
        print(f"  {i:2d}. {pred['sequence_id']}: {plddt:5.1f} - {seq_preview}")

    return results


@app.local_entrypoint()
def deploy():
    """
    Deploy all pipeline components.

    Usage:
        modal deploy modal_apps/pipeline_orchestrator.py::deploy
    """
    print("📦 Deploying foundry pipeline components...")
    print()
    print("This will deploy:")
    print("  - foundry-rfd3 (backbone generation)")
    print("  - foundry-mpnn (sequence design)")
    print("  - foundry-rf3 (structure prediction)")
    print("  - foundry-pipeline (orchestrator)")
    print()
    print("After deployment, you can run via:")
    print("  modal run foundry-pipeline::run --target-pdb-path target.pdb")
    print()
    print("Note: Individual apps must be deployed separately:")
    print("  modal deploy modal_apps/foundry_rfd3.py")
    print("  modal deploy modal_apps/foundry_mpnn.py")
    print("  modal deploy modal_apps/foundry_rf3.py")
    print("  modal deploy modal_apps/pipeline_orchestrator.py")
