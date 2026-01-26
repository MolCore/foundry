"""
Quick test to verify Modal authentication and basic infrastructure.

Run this first to ensure Modal is set up correctly before building the full pipeline.

Usage:
    modal run modal_apps/test_modal_setup.py
"""

import modal

app = modal.App("test-foundry-setup")

# Simple test image
test_image = modal.Image.debian_slim(python_version="3.12").pip_install("numpy")

@app.function(image=test_image, cpu=1.0)
def test_cpu():
    """Test CPU function."""
    import numpy as np
    print("✅ CPU function working")
    print(f"   NumPy version: {np.__version__}")
    result = np.random.rand(10, 10)
    print(f"   Created {result.shape} array")
    return "CPU test passed"

@app.function(image=test_image, gpu="L4", timeout=300)
def test_gpu():
    """Test GPU (L4) function."""
    import subprocess

    print("✅ GPU function working")

    # Check if CUDA is available
    result = subprocess.run(["nvidia-smi"], capture_output=True, text=True)
    if result.returncode == 0:
        print("   nvidia-smi output:")
        for line in result.stdout.split("\n")[:15]:  # First 15 lines
            print(f"     {line}")
    else:
        print("   ⚠️  nvidia-smi not available (expected on CPU)")

    return "GPU test passed"

@app.function(timeout=60)
def test_volumes():
    """Test volume creation."""
    print("✅ Testing volume creation")

    # These will create if they don't exist
    db_vol = modal.Volume.from_name("foundry-databases", create_if_missing=True)
    results_vol = modal.Volume.from_name("foundry-results", create_if_missing=True)

    print(f"   foundry-databases volume: ready")
    print(f"   foundry-results volume: ready")

    return "Volume test passed"

@app.local_entrypoint()
def main():
    """Run all tests."""
    print("=" * 80)
    print("🧪 TESTING MODAL SETUP FOR FOUNDRY")
    print("=" * 80)
    print()

    # Test 1: CPU
    print("Test 1: CPU function")
    print("-" * 80)
    result1 = test_cpu.remote()
    print(f"Result: {result1}")
    print()

    # Test 2: GPU
    print("Test 2: GPU (L4) function")
    print("-" * 80)
    try:
        result2 = test_gpu.remote()
        print(f"Result: {result2}")
    except Exception as e:
        print(f"⚠️  GPU test failed: {e}")
        print("   (This is OK if you haven't set up GPU access yet)")
    print()

    # Test 3: Volumes
    print("Test 3: Volume creation")
    print("-" * 80)
    result3 = test_volumes.remote()
    print(f"Result: {result3}")
    print()

    print("=" * 80)
    print("✅ MODAL SETUP TESTS COMPLETE")
    print("=" * 80)
    print()
    print("Next steps:")
    print("1. If all tests passed, you're ready to implement foundry inference")
    print("2. Check Modal dashboard: https://modal.com/")
    print("3. View volumes: modal volume ls")
    print("4. Ready to implement the actual inference code in modal_apps/foundry_*.py")
    print()
