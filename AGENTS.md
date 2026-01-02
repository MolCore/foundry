## Agent operating rules (read first)

### Repo scope
- This repository is **MolCore/foundry**. Environment/dev instructions live here:
  - `tools/envs/molecore_foundry/AGENT_SETUP.md`

### Hard rule
- **Never suggest creating or changing pull requests to the RosettaCommons repository that the user forked from.**

### Environment expectations
- Global default env is a **uv virtualenv** at `~/.venvs/molecore_foundry`.
- Repo-local env (when working in this repo) is `./.venv` and is activated via `direnv` using `.envrc`.

### PyRosetta note (important)
- PyRosetta availability depends on what **prebuilt binaries** RosettaCommons publishes for your OS/Python.
  On this Linux server we verified PyRosetta can be installed into the default **Python 3.12** env via
  `pyrosetta-installer`, but you may still need credentials and other machines/OSes may differ.


