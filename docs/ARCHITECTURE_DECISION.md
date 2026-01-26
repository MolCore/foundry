# Architecture Decision: Modal Integration Strategy

## Current State Analysis

### 1. Existing Workflow System (`/Users/ariel/dev/molCore/workflow`)

**Purpose**: Comprehensive workflow management for protein design on SLURM/HPC infrastructure

**Key Features**:
- ✅ UUID-based process tracking and history
- ✅ Input/output validation with schemas
- ✅ Apptainer container management
- ✅ SLURM job scheduling integration
- ✅ Model wrappers (RFdiffusion, ProteinMPNN planned)
- ✅ GPU resource management (L40S, H200)
- ✅ Parent-child process relationship tracking

**Architecture**:
```
workflow/
├── history/tracker.py           # UUID tracking, process relationships
├── schemas/model_schemas.py     # Parameter validation, I/O specs
├── wrappers/
│   ├── input/rfdiffusion_wrapper.py   # Input preparation
│   └── output/rfdiffusion_wrapper.py  # Output collection
├── containers/apptainer/        # Container definitions
└── scripts/sbatch_examples/     # SLURM job templates
```

**Target Infrastructure**: Linux HPC cluster with SLURM (your current GPU server setup)

### 2. Foundry Modal Apps (What We Just Built)

**Purpose**: Serverless cloud execution of foundry models on Modal

**Key Features**:
- ✅ Modular Modal apps (RFD3, MPNN, RF3 separate)
- ✅ Cost-optimized GPU selection (L4 for most, CPU for MPNN)
- ✅ Pipeline orchestrator
- ✅ Container image management
- ✅ Parallel execution primitives

**Architecture**:
```
foundry/modal_apps/
├── foundry_rfd3.py           # RFD3 on L4
├── foundry_mpnn.py           # MPNN on CPU
├── foundry_rf3.py            # RF3 on L4
└── pipeline_orchestrator.py  # Coordinates all three
```

**Target Infrastructure**: Modal cloud (serverless GPU)

## Decision Point: Integration Strategy

You have **three options** for how to proceed:

---

## Option A: Foundry-Only Modal (Small Scope) ⚡

**What**: Keep Modal focused ONLY on running foundry models

**Scope**: Just what we've built - standalone Modal apps for RFD3/MPNN/RF3

**Pros**:
- ✅ Quick to test and deploy
- ✅ Simple, focused scope
- ✅ Easy to understand and maintain
- ✅ Immediate value - run foundry in cloud
- ✅ No disruption to existing workflow system

**Cons**:
- ❌ No process tracking/history
- ❌ No integration with existing workflow infrastructure
- ❌ Duplicate effort if you want tracking later
- ❌ Two separate systems to maintain

**Use Case**:
- Quick prototyping of foundry models
- One-off design campaigns
- Learning Modal infrastructure
- Testing foundry on cloud GPUs

**Next Steps**:
1. Test Modal setup: `modal run modal_apps/test_modal_setup.py`
2. Implement foundry inference code in each app (CLI subprocess)
3. Test pipeline: `modal run modal_apps/pipeline_orchestrator.py::test`
4. Run production: `modal run modal_apps/pipeline_orchestrator.py::run --target-pdb target.pdb`

---

## Option B: Modal with Workflow Integration (Medium Scope) 🔗

**What**: Make Modal a **cloud backend** for your existing workflow system

**Scope**: Extend workflow system to dispatch jobs to Modal instead of SLURM

**Architecture**:
```
workflow/
├── backends/
│   ├── slurm.py           # Existing SLURM backend
│   └── modal.py           # NEW: Modal backend
├── history/tracker.py     # Same tracking for both backends
├── schemas/               # Same schemas for both
└── wrappers/              # Same wrappers, different execution
```

**How it works**:
```python
# In workflow system
from workflow.backends.modal import ModalBackend
from workflow.wrappers.input import RFdiffusionInputWrapper

# Create input (same as SLURM)
wrapper = RFdiffusionInputWrapper(...)
process_id = wrapper.prepare_input(input_spec)

# Choose backend
backend = ModalBackend()  # or SlurmBackend()
job_id = backend.submit(process_id, command)

# Track process (same for both)
tracker.update_process(process_id, status="running")
```

**Pros**:
- ✅ Unified tracking across SLURM and Modal
- ✅ Reuse existing schemas and validation
- ✅ Choose backend per job (SLURM for long training, Modal for inference)
- ✅ Process history works across platforms
- ✅ Familiar workflow API

**Cons**:
- ❌ More work to implement
- ❌ Need to adapt workflow system for cloud
- ❌ Complexity of maintaining two backends

**Use Case**:
- Production workflows that might run on either SLURM or Modal
- Teams using both HPC and cloud
- Wanting unified tracking/history
- Flexible infrastructure (burst to cloud when SLURM busy)

**Next Steps**:
1. Create `workflow/backends/modal.py` adapter
2. Test backend switching
3. Implement process tracking for Modal jobs
4. Extend schemas to include Modal-specific parameters

---

## Option C: Full Workflow System on Modal (Large Scope) 🌍

**What**: Port entire workflow system to run natively on Modal

**Scope**: Reimplement workflow orchestration, tracking, and schemas on Modal infrastructure

**Architecture**:
```
modal_workflow/
├── modal_tracker.py       # Process tracking using Modal Dicts/Volumes
├── modal_orchestrator.py  # Workflow orchestration on Modal
├── schemas/               # Reuse existing schemas
└── apps/
    ├── rfd3.py
    ├── mpnn.py
    ├── rf3.py
    └── workflow_dag.py    # DAG execution engine on Modal
```

**How it works**:
```python
# All-Modal workflow
from modal_workflow import ModalWorkflow

workflow = ModalWorkflow("design-campaign")

# Define DAG
backbone_job = workflow.add_task("rfd3", inputs=...)
sequence_job = workflow.add_task("mpnn", depends_on=backbone_job)
predict_job = workflow.add_task("rf3", depends_on=sequence_job)

# Execute (all on Modal)
results = workflow.run()
```

**Pros**:
- ✅ Cloud-native, no SLURM dependency
- ✅ Modal handles all orchestration
- ✅ Serverless scaling
- ✅ Could use Modal Dicts for process tracking
- ✅ Single platform (simplicity)

**Cons**:
- ❌ Most work to implement
- ❌ Lose SLURM backend entirely (unless you keep both)
- ❌ Need to reimplement workflow logic on Modal
- ❌ Overkill if you want to keep using SLURM

**Use Case**:
- Moving entirely to cloud
- Don't want to manage HPC infrastructure
- Want Modal-native workflow features
- Building a SaaS product

**Next Steps**:
1. Design Modal-native workflow DAG system
2. Implement process tracking with Modal Dicts
3. Port schemas and validation
4. Build DAG executor on Modal
5. Migrate incrementally

---

## Recommendation Matrix

| Scenario | Recommended Option | Why |
|----------|-------------------|-----|
| **Want to test foundry on Modal quickly** | A | Fastest path to value |
| **Already happy with SLURM workflow** | A | Don't fix what isn't broken |
| **Want flexibility (SLURM + Modal)** | B | Best of both worlds |
| **Large teams, need unified tracking** | B | Consistent history across platforms |
| **Moving fully to cloud** | C | Full cloud migration |
| **Building production SaaS** | C | Cloud-native architecture |
| **Uncertain about cloud** | A → B | Start small, grow later |

---

## Cost Comparison

### Option A (Foundry-Only Modal)
- **Dev time**: 1-2 weeks (implement inference code, test)
- **Maintenance**: Low (just foundry apps)
- **Flexibility**: Low (no tracking)

### Option B (Modal + Workflow Integration)
- **Dev time**: 3-4 weeks (backend adapter, integration testing)
- **Maintenance**: Medium (two backends to maintain)
- **Flexibility**: High (choose backend per job)

### Option C (Full Modal Workflow)
- **Dev time**: 6-8 weeks (reimplement workflow on Modal)
- **Maintenance**: Medium (new workflow system)
- **Flexibility**: Medium (Modal-only)

---

## My Recommendation

**Start with Option A, with a plan to move to Option B if needed.**

**Why**:
1. **Immediate value**: Test foundry on Modal quickly
2. **Learn Modal**: Understand Modal infrastructure before committing
3. **Validate use case**: See if Modal makes sense for your workloads
4. **Low risk**: Doesn't disrupt existing SLURM workflow
5. **Easy upgrade path**: Can add workflow integration later if valuable

**When to upgrade to Option B**:
- You find yourself using Modal frequently
- Want unified tracking across SLURM and Modal
- Need to burst to cloud when SLURM is busy
- Teams want consistent API across platforms

**When to consider Option C**:
- Moving fully off HPC infrastructure
- Modal becomes your primary platform
- Want to build product on top of workflows

---

## Next Immediate Steps (Option A)

1. **Test Modal infrastructure** (30 min)
   ```bash
   modal run modal_apps/test_modal_setup.py
   ```

2. **Implement RFD3 inference** (2-3 hours)
   - Use CLI subprocess calls to `rfd3 design`
   - Test with small design (5 backbones)

3. **Implement MPNN inference** (2-3 hours)
   - Use CLI subprocess (once CLI is documented)
   - Test with single backbone

4. **Implement RF3 inference** (2-3 hours)
   - Use CLI subprocess to `rf3 fold`
   - Test with single sequence

5. **Test pipeline** (1 hour)
   ```bash
   modal run modal_apps/pipeline_orchestrator.py::test
   ```

6. **Production run** (validate)
   ```bash
   modal run modal_apps/pipeline_orchestrator.py::run \
       --target-pdb target.pdb \
       --num-backbones 10
   ```

**Total time to working system: ~1-2 weeks**

---

## Questions to Consider

1. **How often will you use Modal vs SLURM?**
   - Mostly SLURM → Option A
   - 50/50 → Option B
   - Mostly Modal → Option C

2. **Do you need unified process tracking?**
   - No → Option A
   - Yes → Option B or C

3. **Is this for research or product?**
   - Research → Option A or B
   - Product → Option C

4. **What's your team size?**
   - Solo/small → Option A
   - Medium team → Option B
   - Large team/company → Option C

5. **What's your infrastructure preference?**
   - Keep HPC → Option A or B
   - Move to cloud → Option C
   - Hybrid → Option B

---

## Summary

**tl;dr**: Start simple (Option A), prove value, then decide if you need workflow integration (Option B) or full migration (Option C).

The Modal foundry apps are ready to test. Let's validate the infrastructure works, then implement the inference code. We can always add workflow integration later if it proves valuable.
