# Platform — aegis v3 vendored dependency

This directory holds the pinned aegis v3 dependency reference. The actual
code lives in `rcabench-platform`, installed via uv.

## How to pin a specific aegis commit

In root `pyproject.toml`, replace the placeholder with:

```toml
dependencies = [
    "rcabench-platform @ git+https://github.com/OperationsPAI/aegis.git@<commit-hash>#subdirectory=rcabench-platform",
    ...
]
```

Then `uv sync` will install that specific commit.

## Or: vendored copy (for offline use)

```bash
git clone https://github.com/OperationsPAI/aegis.git ../aegis
cd ../aegis && git checkout <pin-hash>
# In sota-rca-study/pyproject.toml:
#   "rcabench-platform @ file://../aegis/rcabench-platform"
uv sync
```
