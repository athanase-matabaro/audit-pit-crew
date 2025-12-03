# Tools Troubleshooting & Conclusions

This document summarizes the troubleshooting performed and the conclusions for the four analysis tools used by Audit-Pit-Crew: Slither, Mythril, Aderyn, and Oyente. It captures observed failures, root causes, fixes/workarounds applied, current status, and recommended next steps.

---

## Overview

- Work focused on making the worker image and multi-tool scanning robust inside Docker.
- Primary goal: ensure Slither and Mythril are reliable baseline analyzers and make Aderyn and Oyente optional until upstream issues are resolved.
- Changes applied across healthchecks, configuration, Dockerfile, and a small Mythril patch script.

---

## Slither

### Symptoms / Logs
- Slither ran successfully in healthcheck and direct tests.
- When tests used a single file path instead of repository root, earlier runs raised errors due to scanner expecting a directory.

### Root Cause
- Slither's CLI and `crytic_compile` expect a repository root directory for full runs. Passing a file path where the code expects to create output directories caused `NotADirectoryError` (e.g. trying to create `/tmp/Test.sol/slither_report.json`).

### Fix / Workaround
- Ensure scanners are invoked with repository root paths; for file-level testing, call Slither directly on a file outside scanner orchestration.
- Adjusted tests to run `slither /tmp/Test.sol` when directly testing the binary.

### Changes Applied
- Verified Slither v0.11.0 in container and confirmed detection of reentrancy and other issues on test contracts.
- UnifiedScanner default config includes `slither` as core tool.

### Current Status
- Working and reliable (core analyzer).
- Verified via direct run and via UnifiedScanner orchestration (when provided a repository directory).

### Next Steps / Recommendations
- Keep Slither as a required/core tool in CI.
- When reporting results, ensure scanner receives repository root path to avoid path-based errors.

---

## Mythril

### Symptoms / Logs
- Mythril originally crashed during import due to network calls initiated from `solcx.get_installable_solc_versions()` at import-time.
- Docker build logs showed Mythril failing on import with a network error; runtime showed crash traces when solc fetching code executed.
- Pip dependency resolver warnings showed several version conflicts during image build (warnings, not fatal). 

### Root Cause
- Mythril (and some of its dependencies) call `solcx.get_installable_solc_versions()` at import time which performs network I/O; in restricted or flaky build/runtime environments this can cause import-time failures.
- The Mythril/solcx behavior makes the import fragile if network access is unavailable or blocked.
- Also, Python package dependency versions diverged; pip printed dependency conflict warnings during installation (Mythril still installed though).

### Fix / Workaround
- Introduced `scripts/patch_mythril.py` which patches Mythril's `util.py` to wrap `solcx.get_installable_solc_versions()` in a try/except block so import-time network errors are caught and handled gracefully.
- Applied the patch during Docker build to avoid runtime import crashes.
- Left dependency warnings intact (they were not fatal). If needed, pin conflicting dependencies in `pyproject.toml` for full compatibility.

### Changes Applied
- `scripts/patch_mythril.py` added and invoked during Docker build.
- `Dockerfile` updated to run the patch step during image build.
- Healthcheck script and tests now show Mythril v0.23.0 available and working.

### Current Status
- Mythril v0.23.0 is working in the container and can analyze contracts (verified on `/tmp/Test.sol`).
- Pip saw dependency conflicts during install (warnings). Functionality verified despite warnings.

### Next Steps / Recommendations
- Consider pinning Mythril-compatible dependency versions in `pyproject.toml` to avoid runtime incompatibilities across environments.
- Upstream fix: open an issue/PR against Mythril/solcx to avoid network calls at import time or add a guarded import.

---

## Aderyn

### Symptoms / Logs
- Worker healthcheck initially reported Aderyn v0.1.9 present; Aderyn produced runtime panics (crash/bug) when run.
- Attempts to install a newer Aderyn from GitHub using `cargo install --git ... --tag aderyn-v0.6.5` failed during Docker build and fell back to crates.io release v0.1.9 (older, buggy) in some cases.
- Docker healthcheck showed `aderyn: not found` when the install failed cleanly.

### Root Cause
- Two installation failure modes observed:
  1. `cargo install --git` with tag may fail in Docker build due to network or repository layout differences. When it fails, build logic sometimes leaves a broken or older version.
  2. There is an upstream bug in Aderyn v0.1.9 that causes a panic when parsing certain version strings, causing runtime crashes.

### Fix / Workaround
- Avoid running Aderyn by default. It is now optional in `enabled_tools` (defaults set to `["slither", "mythril"]`).
- Dockerfile was updated to attempt GitHub install and mark failure with a sentinel file `/tmp/aderyn_failed`. The healthcheck was made tolerant to the missing Aderyn binary.
- Recommended to explicitly opt-in to Aderyn in repository config once a verifiably stable version is available.

### Changes Applied
- `Dockerfile` includes install attempt for Aderyn from GitHub; failing that, image build marks it as unavailable.
- `audit-pit-crew.yml.example` updated to show default excludes Aderyn.
- Healthcheck (`scripts/analyzers_healthcheck.sh`) updated to treat Aderyn as optional and not fail the container when missing.

### Current Status
- Aderyn is not installed by default in the worker image (optional). Healthcheck reports: "Aderyn not installed (optional)".

### Next Steps / Recommendations
- If Aderyn is required, test explicit install flow locally: prefer installing a vetted crates.io release (e.g. `aderyn@0.3.4`) or using a release artifact verified to be stable. Example fallback: `cargo install aderyn@0.3.4`.
- Re-run Docker builds with added logging to capture `cargo install` failures; if the GitHub tag is required, ensure the correct tag/ref syntax and network access in build environment.
- Monitor Aderyn upstream for bug fixes; re-enable in `enabled_tools` only after stable version validated.

---

## Oyente

### Symptoms / Logs
- `pip show oyente` previously indicated the PyPI distribution is broken/missing files (e.g., README.md missing in distribution). GitHub install attempts also failed due to repository submodule issues.
- Oyente import or install fails during Docker build.

### Root Cause
- Upstream PyPI package is broken and the GitHub repository appears to have broken or complex install procedures; package distribution is not maintained in a way compatible with modern packaging expectations.

### Fix / Workaround
- Excluded Oyente from default `enabled_tools` (defaults set to `["slither", "mythril"]`). Marked Oyente as optional in healthchecks and docs.
- Healthcheck now prints a friendly message when Oyente isn't installed.

### Changes Applied
- `audit-pit-crew.yml.example` documented that Oyente is unmaintained and excluded by default.
- Healthcheck script updated so missing Oyente does not cause container startup to fail.

### Current Status
- Oyente not installed by default (optional). Upstream package requires manual intervention; no reliable install path available in the image.

### Next Steps / Recommendations
- If Oyente must be used, install from a manually built wheel or cleanly forked repository and host the package artifact in a reliable place.
- Consider removing Oyente as a dependency entirely if upstream maintenance does not continue.

---

## Common Changes / Project-Level Decisions

- `enabled_tools` default now: `["slither", "mythril"]` to provide a stable baseline.
- `scripts/analyzers_healthcheck.sh` improved to:
  - Not exit on first failure
  - Treat Aderyn and Oyente as optional
  - Require Slither and Mythril as core tools
- `scripts/patch_mythril.py` introduced to guard Mythril import-time behavior that depended on network access.
- `Dockerfile` adjusted to run the Mythril patch during build and to attempt but not require Aderyn install.

---

## Validation & Reproduction Steps

To reproduce the key verifications on a machine with Docker:

1. Rebuild images (worker):
```bash
docker compose down
docker compose build --no-cache worker
```

2. Start services and verify healthcheck:
```bash
docker compose up -d
docker compose logs worker --tail 100
# Look for: "✅ Core analyzers found (Slither, Mythril)"
```

3. Trigger a webhook for a PR to run a scan (example uses local server on port 8000):
```bash
curl -X POST http://localhost:8000/webhook/github -H "Content-Type: application/json" -d @pr_payload.json
```

4. Directly test Slither and Mythril on a sample file inside the worker container (for debugging):
```bash
# create a test file in container (done earlier in troubleshooting)
docker compose exec worker bash -c 'slither /tmp/Test.sol --json - | jq .'

docker compose exec worker bash -c 'myth analyze /tmp/Test.sol -o json | jq .'
```

Notes:
- The unified scanner expects repository directory paths (the orchestration clones a repo and provides a root dir). Passing lone file paths through the orchestration yields NotADirectory errors for output paths; direct tool invocation on file paths is valid for debugging only.

---

## Recommended Future Work

1. Dependency pinning: review `pyproject.toml` and pin versions compatible with Mythril 0.23.0 and Slither to avoid pip resolver warnings in some environments.
2. Aderyn strategy: adopt an explicit opt-in and document the verified install command (recommended crates.io version or known-good Git tag). Add more verbose build logging for `cargo install` failures.
3. Mythril upstream: open a PR/issue to make `solcx.get_installable_solc_versions()` optional or guarded so import-time network calls are not required.
4. Oyente: decide whether to maintain a fork, remove it, or host a prebuilt wheel if its analyses are still required.
5. Add CI checks which run a minimal scan on push to ensure that default toolset (Slither + Mythril) remains functional across matrix environments.

---

## Appendix: Key Files Changed During Troubleshooting

- `scripts/patch_mythril.py` — patch to wrap solcx network calls
- `scripts/analyzers_healthcheck.sh` — made robust and tolerant to optional tools
- `Dockerfile` — added patch step, attempted Aderyn install and sentinel handling
- `src/core/config.py` — `enabled_tools` default updated to `['slither', 'mythril']`
- `audit-pit-crew.yml.example` — updated notes and defaults for tools
- `src/core/analysis/unified_scanner.py` — ensures config types handled and logs tool status summary

---

If you want, I can:
- Convert this markdown into a PR and open it (create branch and commit), or
- Add a short test CI job that runs a smoke scan with Slither + Mythril in CI, or
- Try to reattempt Aderyn install using an explicit crates.io version and capture build logs for diagnosis.

Pick next step and I'll proceed.