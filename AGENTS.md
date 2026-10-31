# Agent workflow — p1-pipeline

These rules apply to all work in this repository. Read this file, [README](README.md), and the relevant [architecture](docs/architecture.md), [benchmark protocol](docs/benchmarking.md), and [decisions](docs/decisions.md) before changing code. Keep this file concise; add agreed rules here as the project evolves.

## Mandatory workflow

1. **Understand:** inspect the implementation, callers, tests, fixtures, dependencies and Git status. Preserve unrelated work. Distinguish implemented behavior from planned capabilities.
2. **Define:** state expected behavior and acceptance criteria; identify code, tests and documentation affected. Resolve routine implementation choices without unnecessary approval requests.
3. **Implement and test:** use existing patterns and the smallest complete change. All new and changed logic must be comprehensively unit tested: normal behavior, boundaries, invalid input, and relevant failure/recovery paths. Every bug fix needs a regression test. Assert observable behavior using deterministic fixtures.
4. **Verify:** run focused tests during development, then the required checks below. Inspect uncovered lines/branches in changed logic and close meaningful gaps. Coverage percentages do not replace behavioral assertions. Report unavailable or failed checks accurately.
5. **Document:** update explanations in the same change: what works, how data flows, why the approach was chosen, setup/examples, limitations and verification. Update `README.md` for setup/status changes, `docs/architecture.md` for implementation/contracts, and `docs/benchmarking.md` for measurement/label conventions. Record consequential choices and alternatives in `docs/decisions.md`; mark replaced decisions superseded. Never invent historical rationale or benchmark results.
6. **Review and report:** inspect the full diff, validate documentation links and commands, and report implementation, documentation, checks actually run and remaining limitations. Completion requires code, tests and docs to agree.

Documentation-only changes need link/example checks; they do not require fabricated unit tests. Existing coverage gaps are recorded in the architecture document and addressed when the affected behavior changes.

## Required checks

After setup (`uv sync --locked --extra dfine` for both models):

```sh
uv run --locked python -m coverage run --branch -m unittest discover -s tests -v
uv run --locked python -m coverage report -m
git diff --check
```

CI installs only the `dev` dependency group: coverage, PyAV and NumPy. The complete tests run without weights, private footage, GPU access or network calls. Model imports stay lazy. Generated-video decoder tests exercise the real PyAV boundary; adapter unit tests fake model-library boundaries.

Adapter, decoder or runtime-dependency changes also require the relevant real-checkpoint smoke test when its dependencies/weights are available. See the README for commands. Record unverified hardware explicitly. Unit tests establish code behavior; smoke tests establish runtime integration; labelled match footage establishes detection quality. A successful smoke test is never an accuracy result.

## Experiment and data rules

- Preserve RGB input, documented class mappings, normalized boxes, presentation timestamps, confidence semantics, schema validation and failed-run handling. Test changes to every affected contract.
- `player` currently means COCO person; it does not establish match participation or identity. `football` currently means COCO sports ball. For main-game datasets, agree and retain a match-area polygon before scoring; annotate only objects in that scope and pass the same scope through conversion/evaluation for both models. Never remove other-pitch labels while still scoring full-frame predictions. See [scope rules](docs/benchmarking.md#main-game-scope).
- Keep comparisons reproducible: same input hash, sampled frames, device, precision and evaluation settings; record checkpoint hashes, runtime versions, source revisions and preprocessing. Retain `uv.lock` and regenerate it when dependencies change.
- Never overwrite existing runs. Keep source footage, weights, vendor checkouts, results and credentials out of Git. Use trusted local checkpoints; download explicitly using documented sources.
- Keep unit tests offline and deterministic. Do not add paid services, model downloads or live accounts to default CI. Do not claim CUDA, mobile or production behavior was validated on a CPU smoke test.
- Keep the benchmark workspace focused. Tracking, identity, calibration, events, training and app integration require their own documented work and tests.
- For CVAT work, follow [the labelling workflow](docs/labelling.md): preserve manual corrections, use targeted official-API updates with read-back checks, keep the MCP read-only, and never mark AI drafts human-reviewed merely because no issues were flagged. Keep credentials out of Git and tool output.

## Adding rules

Apply user-approved rules in the appropriate section, update linked checks/docs together, and explain consequential workflow changes in the decision log. More-specific instruction files may add local requirements but must preserve these core documentation and testing obligations.
