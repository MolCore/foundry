"""Modal (L40S, 48 GB) RFD3 CONTINUOUS hollow-fibre generation.

Design spec (per the input→geometry analysis):
    inputs  = { subunit_length (component), subunits_per_turn (n), R_target }
    derived = twist = 360/n
              rise  = subunit_height(length) / n      # so pitch = height -> turns STACK
    => both lateral (n↔n±1) AND turn-to-turn (n↔n±n_perturn) contacts form,
       which a *continuous* fibre needs (local 3090 only made lateral-only spirals).

Patches: prism_helical_via_cn_patch (C{n} disguise) + prism_helical_emergent_patch
(emergent screw + soft R_target). 48 GB lets us drop low_memory_mode and run
>=2 turns at clean folding size (the 3090 broke backbones >~700 res).
"""

from __future__ import annotations

from pathlib import Path
import modal

app = modal.App("foundry-rfd3-tube")

# The rfd3_sym package, resolved relative to this file (runners/ -> ../rfd3_sym),
# so the runner works from any checkout location.
LOCAL_PKG_DIR = (Path(__file__).resolve().parent.parent / "rfd3_sym")

# Same image definition as the working helical app -> Modal reuses cached layers.
rfd3_image = (
    modal.Image.debian_slim(python_version="3.12")
    .apt_install("wget", "git", "build-essential")
    .pip_install("torch>=2.5.0", "rc-foundry[rfd3]")
    .run_commands("foundry install rfd3 --checkpoint-dir /root/.foundry/checkpoints")
    .add_local_dir(str(LOCAL_PKG_DIR), remote_path="/root/rfd3_sym")
)

results_volume = modal.Volume.from_name("sym-rfd3-tube-results", create_if_missing=True)


def estimate_subunit_height(length: int) -> float:
    """Rough axial extent (Å) of an RFD3 subunit of `length` residues.
    Calibrated to measured heights: 60 aa -> ~23 Å, 80 aa -> ~28 Å."""
    return 0.25 * length + 8.0


def make_tag(subunits_per_turn: float, r_target: float, subunit_length: int,
             n_subunits: int, contact: bool = False) -> str:
    """Self-documenting tag = the generation parameters (no opaque names).
    emergent/R_target: 'spt5_R20_L70_n10'.  contact-forced (R derived): add '_ctc'
    e.g. 'spt3p5_L70_n9_ctc'. Inputs fully define the run."""
    spt = (str(int(subunits_per_turn)) if float(subunits_per_turn).is_integer()
           else str(subunits_per_turn).replace(".", "p"))
    if contact:
        return f"spt{spt}_L{int(subunit_length)}_n{int(n_subunits)}_ctc"
    return f"spt{spt}_R{int(round(r_target))}_L{int(subunit_length)}_n{int(n_subunits)}"


@app.function(
    image=rfd3_image,
    gpu="L40S",                       # 48 GB
    timeout=3600,
    volumes={"/results": results_volume},
    max_containers=6,
    retries=1,
)
def run_tube(
    subunits_per_turn: float,
    r_target: float,
    n_subunits: int,
    subunit_length: int,
    tag: str = "",
    seed: int = 0,
    subunit_height: float | None = None,
    radius_bias: float = 0.3,
    low_memory: bool = True,
    contact_mode: bool = False,
    lateral_overlap: float = 0.9,
    axial_overlap: float = 0.9,
    rise_override: float | None = None,
) -> dict:
    import os
    os.environ.setdefault("PYTORCH_CUDA_ALLOC_CONF", "expandable_segments:True")
    import datetime, json, sys, tempfile
    import numpy as np

    sys.path.insert(0, "/root")

    if not tag:  # name the run by its generation parameters
        tag = make_tag(subunits_per_turn, r_target, subunit_length, n_subunits, contact=contact_mode)

    h = subunit_height if subunit_height is not None else estimate_subunit_height(subunit_length)
    rise = rise_override if rise_override is not None else h / subunits_per_turn  # close-pack override or derived
    twist = 2 * np.pi / subunits_per_turn

    def rodrigues(a, th):
        c, s = np.cos(th), np.sin(th)
        K = np.array([[0, -a[2], a[1]], [a[2], 0, -a[0]], [-a[1], a[0], 0.0]])
        return np.eye(3) + s * K + (1 - c) * (K @ K)

    axis = np.array([0.0, 0.0, 1.0])
    frames = [(rodrigues(axis, twist * i), (i * rise) * axis) for i in range(n_subunits)]

    from rfd3_sym.frames import install_helical_via_cn_patch
    install_helical_via_cn_patch(n=n_subunits, helical_frames=frames)
    from rfd3_sym.projection import install_emergent_screw_patch
    install_emergent_screw_patch(frames, r_target=r_target, radius_bias=radius_bias,
                                 contact_mode=contact_mode, subunits_per_turn=subunits_per_turn,
                                 lateral_overlap=lateral_overlap, axial_overlap=axial_overlap)

    out_dir = Path(f"/results/{tag}/seed_{seed:04d}")
    out_dir.mkdir(parents=True, exist_ok=True)
    design_name = f"tube_{tag}_s{seed:04d}"
    spec = {design_name: {"length": subunit_length, "is_non_loopy": True,
                          "symmetry": {"id": f"C{n_subunits}", "is_symmetric_motif": True}}}
    with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as f:
        json.dump(spec, f); input_json = f.name

    started = datetime.datetime.now(datetime.UTC).isoformat()
    import rfd3.cli as _cli
    orig = list(sys.argv)
    sys.argv = ["rfd3", "design", f"out_dir={out_dir}", f"inputs={input_json}",
                "ckpt_path=rfd3", "inference_sampler.kind=symmetry",
                "diffusion_batch_size=1", "n_batches=1",
                f"low_memory_mode={low_memory}",   # True = neighbor-only attn (fits large sym assemblies)
                "dump_trajectories=False", "skip_existing=False", "prevalidate_inputs=True"]
    try:
        try:
            _cli.app()
        except SystemExit as e:
            if e.code not in (None, 0):
                raise
    finally:
        sys.argv = orig
        Path(input_json).unlink(missing_ok=True)

    try:
        import torch
        peak_vram = round(torch.cuda.max_memory_allocated() / 1e9, 2)
        reserved_vram = round(torch.cuda.max_memory_reserved() / 1e9, 2)
    except Exception:
        peak_vram = reserved_vram = None

    cifs = sorted(out_dir.glob("*.cif.gz"))
    prov = {"peak_vram_gb": peak_vram, "reserved_vram_gb": reserved_vram,
            "total_residues": n_subunits * subunit_length,
            "spec": {"subunits_per_turn": subunits_per_turn, "twist_deg": float(np.degrees(twist)),
                     "rise_A": rise, "pitch_A": rise * subunits_per_turn, "subunit_height_A": h,
                     "r_target": r_target, "n_subunits": n_subunits, "subunit_length": subunit_length},
            "derived": "rise = subunit_height / subunits_per_turn (turn-stacking)",
            "started": started, "finished": datetime.datetime.now(datetime.UTC).isoformat()}
    (out_dir / f"{tag}_provenance.json").write_text(json.dumps(prov, indent=2))
    results_volume.commit()
    return {"tag": tag, "n_cifs": len(cifs), "total_residues": n_subunits * subunit_length,
            "peak_vram_gb": peak_vram, "reserved_vram_gb": reserved_vram,
            "rise": rise, "pitch": rise * subunits_per_turn, "out_dir": str(out_dir)}


@app.local_entrypoint()
def run(subunits_per_turn: float, n_subunits: int, r_target: float = 20.0,
        subunit_length: int = 70, seed: int = 0, contact_mode: bool = False,
        lateral_overlap: float = 0.9, axial_overlap: float = 0.9,
        rise_override: float = -1.0):
    """Define a test purely by its generation parameters; tag is derived.
    Emergent/R_target: spt5_R20_L70_n10.  Contact-forced (R derived): spt5_L70_n12_ctc.

        modal run tube_modal_emergent.py::run --subunits-per-turn 6.2 --n-subunits 15 \
            --subunit-length 70 --contact-mode
    """
    r = run_tube.remote(subunits_per_turn=subunits_per_turn, r_target=r_target,
                        n_subunits=n_subunits, subunit_length=subunit_length, seed=seed,
                        contact_mode=contact_mode, lateral_overlap=lateral_overlap,
                        axial_overlap=axial_overlap,
                        rise_override=(None if rise_override < 0 else rise_override))
    print("result:", r)
