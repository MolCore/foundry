"""
RFDiffusion3 Modal App

Specialized container for RFD3 backbone generation.
Hardware: L4 (24GB) or A100 (40GB/80GB) for diffusion models.

Storage Strategy:
- Image: Python, PyTorch, RFD3 package, checkpoint (~500MB), CCD database (~2GB)
- Volume (results): Generated structures and metadata (persistent)
- Volume (pdb-cache): Optional PDB structure cache (lazy loading, LRU)
- On-demand: Fetch PDB structures from RCSB as needed

See: /docs/MODAL_STORAGE_ARCHITECTURE.md
"""

import modal
import os
from pathlib import Path

# ============================================================================
# Container Image: RFD3 with minimal dependencies
# ============================================================================

app = modal.App("foundry-rfd3")

# Optimized image: ONLY essential RFD3 dependencies
rfd3_image = (
    modal.Image.debian_slim(python_version="3.12")
    .apt_install(
        "wget",
        "git",
        "build-essential",  # For compiling some Python packages
    )
    .pip_install(
        "torch>=2.5.0",  # PyTorch with CUDA support
        "rc-foundry[rfd3]",  # RFD3 with minimal dependencies
    )
    .run_commands(
        # Download RFD3 checkpoint during image build (one-time ~500MB)
        "foundry install rfd3 --checkpoint-dir /root/.foundry/checkpoints",
        # Note: CCD database will be downloaded by foundry install automatically
    )
)

# Persistent volume for generated structures and metadata
results_volume = modal.Volume.from_name(
    "foundry-results",
    create_if_missing=True
)

# Optional: PDB cache volume for frequently used structures
# Lazy loading: fetch from RCSB on first use, cache for future
pdb_cache_volume = modal.Volume.from_name(
    "foundry-pdb-cache",
    create_if_missing=True
)

# ============================================================================
# RFD3 Functions
# ============================================================================

@app.function(
    image=rfd3_image,
    gpu="L4",  # 24GB VRAM, ~$0.60/hr (upgrade to A100 if needed)
    timeout=3600,  # 60 minutes max (for larger batches)
    volumes={
        "/pdb_cache": pdb_cache_volume,
        "/results": results_volume,
    },
)
def generate_backbones(
    design_spec: dict,
    num_designs: int = 100,
    diffusion_batch_size: int = 16,
    output_dir: str = "/results/backbones",
    dump_trajectories: bool = False,
):
    """
    Generate protein backbones using RFDiffusion3.

    Args:
        design_spec: RFD3 design specification dict
            Example (de novo monomer):
            {
                "my_design": {
                    "length": "80-100"
                }
            }

            Example (motif scaffolding):
            {
                "scaffold_7v11": {
                    "input": "7v11.pdb",  # PDB ID or file path
                    "ligand": "OQO",
                    "contig": "A431"
                }
            }

            Example (partial diffusion):
            {
                "partial_design": {
                    "input": "7v11.pdb",
                    "ligand": "OQO",
                    "partial_t": 10.0,
                    "contig": "A431"
                }
            }

        num_designs: Total number of designs to generate (split into batches)
        diffusion_batch_size: Batch size for diffusion sampling (affects GPU memory)
        output_dir: Where to save backbones (on volume)
        dump_trajectories: Whether to save intermediate trajectory steps

    Returns:
        List of dicts: [
            {
                "example_id": "my_design_0_model_0",
                "cif_path": "/results/backbones/my_design_0_model_0.cif.gz",
                "metadata": {...},  # RFD3 output metadata
            },
            ...
        ]
    """
    import json
    import tempfile
    import torch
    from rfd3.engine import RFD3InferenceEngine, RFD3InferenceConfig

    print("=" * 60)
    print("RFD3 Backbone Generation on Modal")
    print("=" * 60)
    print(f"Design spec: {list(design_spec.keys())}")
    print(f"Target designs: {num_designs}")
    print(f"Batch size: {diffusion_batch_size}")
    print("")

    # GPU info
    print(f"GPU available: {torch.cuda.is_available()}")
    if torch.cuda.is_available():
        print(f"GPU: {torch.cuda.get_device_name(0)}")
        print(f"GPU memory: {torch.cuda.get_device_properties(0).total_memory / 1e9:.1f} GB")
    print("")

    # Setup PDB cache environment
    os.environ["PDB_MIRROR_PATH"] = "/pdb_cache"
    # CCD should be in image already from foundry install

    # Create output directory
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    # Write design spec to temporary JSON file
    with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
        json.dump(design_spec, f, indent=2)
        input_json_path = f.name

    print(f"Input spec: {input_json_path}")
    print(f"Output dir: {output_path}")
    print("")

    # ========================================================================
    # Run RFD3 Inference
    # ========================================================================

    # Calculate number of batches needed
    n_batches = (num_designs + diffusion_batch_size - 1) // diffusion_batch_size

    print(f"Running RFD3 inference:")
    print(f"  Batches: {n_batches}")
    print(f"  Batch size: {diffusion_batch_size}")
    print(f"  Total designs: ~{n_batches * diffusion_batch_size}")
    print("")

    # Configure RFD3 inference engine
    config = RFD3InferenceConfig(
        ckpt_path="rfd3",  # Use foundry-installed checkpoint
        diffusion_batch_size=diffusion_batch_size,
        skip_existing=False,  # Generate fresh designs each time
        dump_trajectories=dump_trajectories,
        dump_prediction_metadata_json=True,
        prevalidate_inputs=True,
        verbose=True,
    )

    # Initialize engine
    print("Initializing RFD3 engine...")
    engine = RFD3InferenceEngine(**config)
    print("✓ Engine initialized")
    print("")

    # Run inference
    print("Generating backbones...")
    try:
        engine.run(
            inputs=input_json_path,
            out_dir=str(output_path),
            n_batches=n_batches,
        )
        print("✓ Inference complete")
    except Exception as e:
        print(f"❌ ERROR during inference: {e}")
        raise
    finally:
        # Cleanup temp input file
        Path(input_json_path).unlink(missing_ok=True)

    print("")

    # ========================================================================
    # Collect Results
    # ========================================================================

    print("Collecting outputs...")
    backbones = []

    # Find all generated CIF files
    cif_files = sorted(output_path.glob("*.cif.gz"))

    for cif_path in cif_files:
        example_id = cif_path.stem.replace(".cif", "")
        json_path = cif_path.with_suffix("").with_suffix(".json")

        # Load metadata if available
        metadata = {}
        if json_path.exists():
            with open(json_path) as f:
                metadata = json.load(f)

        backbones.append({
            "example_id": example_id,
            "cif_path": str(cif_path),
            "metadata": metadata,
        })

    print(f"✓ Collected {len(backbones)} structures")
    print("")

    # Commit changes to volume (persist results)
    print("Committing results to volume...")
    results_volume.commit()
    print("✓ Volume committed")
    print("")

    print("=" * 60)
    print(f"✅ RFD3 Complete: Generated {len(backbones)} backbones")
    print("=" * 60)

    return backbones


@app.function(
    image=rfd3_image,
    gpu="L4",
    timeout=600,  # 10 minutes for quick single design
)
def generate_single_design(
    design_spec: dict,
    dump_trajectories: bool = False,
):
    """
    Generate a single design (for testing or quick prototyping).

    Args:
        design_spec: RFD3 design specification (see generate_backbones docstring)
        dump_trajectories: Whether to save trajectory

    Returns:
        dict: Single backbone result
    """
    results = generate_backbones.local(
        design_spec=design_spec,
        num_designs=1,
        diffusion_batch_size=1,
        dump_trajectories=dump_trajectories,
    )
    return results[0] if results else None


# ============================================================================
# CLI Entrypoints
# ============================================================================

@app.local_entrypoint()
def test(num_designs: int = 2):
    """
    Test RFD3 generation with a simple de novo monomer design.

    Usage:
        modal run modal_apps/foundry_rfd3.py::test --num-designs 2
    """
    print("🧪 Testing RFD3 Modal app...")
    print("")

    # Simple test: de novo monomer
    design_spec = {
        "test_monomer": {
            "length": "80-100"
        }
    }

    backbones = generate_backbones.remote(
        design_spec=design_spec,
        num_designs=num_designs,
        diffusion_batch_size=2,
    )

    print("")
    print("✅ Test complete!")
    print(f"   Generated {len(backbones)} backbones")
    print("")
    print("Outputs:")
    for bb in backbones:
        print(f"   - {bb['example_id']}")
        print(f"     CIF: {bb['cif_path']}")
        if bb.get('metadata'):
            print(f"     Metadata: {len(bb['metadata'])} fields")

    return backbones


@app.local_entrypoint()
def generate(
    design_json_path: str,
    num_designs: int = 100,
    diffusion_batch_size: int = 16,
    output_dir: str = "/results/backbones",
    dump_trajectories: bool = False,
):
    """
    Generate backbones from a design specification JSON file.

    Usage:
        # Create design_spec.json:
        # {
        #   "my_design": {
        #     "length": "80-100"
        #   }
        # }

        modal run modal_apps/foundry_rfd3.py::generate \\
            --design-json-path design_spec.json \\
            --num-designs 100 \\
            --diffusion-batch-size 16
    """
    import json

    # Read design spec
    with open(design_json_path) as f:
        design_spec = json.load(f)

    print(f"🚀 Generating {num_designs} backbones")
    print(f"   Design spec: {design_json_path}")
    print(f"   Batch size: {diffusion_batch_size}")
    print("")

    backbones = generate_backbones.remote(
        design_spec=design_spec,
        num_designs=num_designs,
        diffusion_batch_size=diffusion_batch_size,
        output_dir=output_dir,
        dump_trajectories=dump_trajectories,
    )

    print("")
    print("✅ Generation complete!")
    print(f"   Output: {output_dir}")
    print(f"   Total backbones: {len(backbones)}")
    print("")
    print("Structures:")
    for bb in backbones[:10]:  # Show first 10
        print(f"   - {bb['example_id']}")

    if len(backbones) > 10:
        print(f"   ... and {len(backbones) - 10} more")

    return backbones
