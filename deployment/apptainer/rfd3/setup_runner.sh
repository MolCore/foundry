#!/bin/bash
#
# Setup GitHub Actions self-hosted runner on borg
# Run this script on borg server as the user that will run builds
#
# Usage: ./setup_runner.sh
#

set -e

echo "========================================="
echo "GitHub Actions Runner Setup for Borg"
echo "========================================="
echo ""

# Configuration
RUNNER_DIR="/runtime/github-runner"
RUNNER_NAME="borg-runner"
RUNNER_LABELS="self-hosted,linux,borg,apptainer,x64"
WORK_DIR="/runtime/github-runner/_work"

# Check if running on borg
if [[ ! -d "/runtime" ]]; then
    echo "❌ ERROR: This script must be run on the borg server"
    echo "Expected /runtime directory not found"
    exit 1
fi

# Check user permissions
if [[ ! -w "/runtime" ]]; then
    echo "❌ ERROR: User $(whoami) does not have write permissions to /runtime"
    echo "Please ensure you have the correct permissions"
    exit 1
fi

echo "✓ Running on borg as user: $(whoami)"
echo "✓ /runtime directory accessible"
echo ""

# Check for required tools
echo "Checking required tools..."
command -v apptainer >/dev/null 2>&1 || { echo "❌ ERROR: apptainer not found"; exit 1; }
command -v git >/dev/null 2>&1 || { echo "❌ ERROR: git not found"; exit 1; }
command -v curl >/dev/null 2>&1 || { echo "❌ ERROR: curl not found"; exit 1; }

echo "✓ apptainer: $(apptainer --version)"
echo "✓ git: $(git --version | head -1)"
echo "✓ curl: $(curl --version | head -1)"
echo ""

# Create runner directory
echo "Creating runner directory..."
mkdir -p "$RUNNER_DIR"
cd "$RUNNER_DIR"

# Download latest runner
echo "Downloading GitHub Actions runner..."
RUNNER_VERSION="2.311.0"  # Update to latest stable version
RUNNER_URL="https://github.com/actions/runner/releases/download/v${RUNNER_VERSION}/actions-runner-linux-x64-${RUNNER_VERSION}.tar.gz"

if [[ ! -f "actions-runner-linux-x64-${RUNNER_VERSION}.tar.gz" ]]; then
    curl -o "actions-runner-linux-x64-${RUNNER_VERSION}.tar.gz" -L "$RUNNER_URL"
    tar xzf "actions-runner-linux-x64-${RUNNER_VERSION}.tar.gz"
else
    echo "Runner package already downloaded"
fi

echo ""
echo "========================================="
echo "Runner Configuration"
echo "========================================="
echo ""
echo "Next steps:"
echo ""
echo "1. Get a registration token from GitHub:"
echo "   - Go to: https://github.com/MolCore/foundry/settings/actions/runners/new"
echo "   - Select 'Linux' as the operating system"
echo "   - Copy the registration token"
echo ""
echo "2. Configure the runner with the token:"
echo "   cd $RUNNER_DIR"
echo "   ./config.sh \\"
echo "     --url https://github.com/MolCore/foundry \\"
echo "     --token YOUR_REGISTRATION_TOKEN \\"
echo "     --name $RUNNER_NAME \\"
echo "     --labels $RUNNER_LABELS \\"
echo "     --work $WORK_DIR \\"
echo "     --unattended"
echo ""
echo "3. Install as a service:"
echo "   cd $RUNNER_DIR"
echo "   sudo ./svc.sh install $(whoami)"
echo "   sudo ./svc.sh start"
echo ""
echo "4. Verify runner is active:"
echo "   sudo ./svc.sh status"
echo ""
echo "5. Check GitHub:"
echo "   https://github.com/MolCore/foundry/settings/actions/runners"
echo "   Runner should show as 'Idle' (ready to accept jobs)"
echo ""
echo "========================================="
echo ""
echo "✅ Runner directory prepared at: $RUNNER_DIR"
echo ""
echo "⚠️  IMPORTANT: You must complete steps 1-5 manually"
echo "   (Registration token cannot be automated for security)"
echo ""
