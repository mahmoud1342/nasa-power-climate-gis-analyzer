# Contributing to NPCGA

Thank you for considering a contribution to NASA POWER Climate & GIS Analyzer (NPCGA).
Contributions should improve correctness, reproducibility, usability, or documentation without
silently changing the meaning of existing data or methods.

## Before you start

1. Check existing issues and pull requests for related work.
2. For a substantial change, open an issue first to agree on scope.
3. Keep changes focused. Avoid unrelated formatting or refactoring.
4. Do not claim a feature is implemented until it is present and tested.
5. Do not add sample or synthetic values in a way that could be mistaken for observed or
   downloaded NASA POWER data.

## Development environment

The package metadata declares Python 3.11+. The maintainer develops and tests on Python 3.12; a CI
workflow for 3.11 and 3.12 (Windows and Ubuntu) is defined, but its results are not yet confirmed
(see the README). Python 3.12 is recommended for a new development environment.

### Windows (PowerShell)

```powershell
py -3.12 -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -e ".[dev]"
```

### Linux / macOS

```bash
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -e ".[dev]"
```

## Development rules

### Data integrity

- Never overwrite, drop, fill, interpolate, clip, or otherwise alter source observations silently.
- Preserve the project's NoData convention: NASA POWER `-999` is represented as `NaN` and counted
  by the relevant ingestion path.
- If a transformation is scientifically necessary, make it explicit, documented, and testable.
- Distinguish missing values, invalid values, and values outside a plausibility range.
- Report file-level failures with a reason; do not silently skip failed inputs.
- Never fabricate API responses, measurements, citations, benchmark results, or test outcomes.

### Scientific methods

- Cite authoritative definitions or peer-reviewed references when changing climate indices,
  thresholds, statistical tests, or assumptions.
- Document the reference period, units, thresholds, completeness rules, missing-data treatment,
  and any approximations.
- Do not describe an implementation as fully ETCCDI-compliant unless the relevant requirements
  have been checked and implemented.
- For trend methods, state assumptions such as independence and treatment of ties, missing data,
  and autocorrelation.
- Add hand-calculated test cases for scientific formulas where practical.

### Architecture and performance

- Keep analysis logic in `npcga`, not duplicated in CLI or presentation code.
- Keep I/O, validation, QC, analysis, and presentation responsibilities separated.
- Use lazy imports for heavy optional libraries (GIS, plotting, web, and other large dependencies)
  so core imports and unrelated workflows remain lightweight.
- Avoid making optional GIS or web packages mandatory for core functionality.
- Preserve clear error messages and avoid swallowing exceptions without recording context.
- Keep public function signatures and output schemas stable unless a change is intentional and
  documented.

### Code style

- Follow the existing module structure and naming conventions.
- Keep functions focused and type-annotate public interfaces where appropriate.
- Use Ruff with the repository's configured line length:

```bash
ruff check src tests
```

## Tests

Add or update tests for every behavior change.

Run the offline suite:

```bash
python -m pytest
```

Run the live API tests only when intentionally checking integration with NASA POWER:

```bash
python -m pytest -m network
```

The default pytest configuration excludes network tests. Tests must not require a live API unless
they are explicitly marked `network`.

For bug fixes, include a regression test that fails before the fix and passes after it. For
scientific calculations, include boundary cases such as leap years, missing days, threshold
equality, ties, constant series, and short records when relevant.

Before submitting, check:

- [ ] Tests pass locally.
- [ ] Ruff passes.
- [ ] No new test depends on live network access unless marked `network`.
- [ ] No source data is silently modified.
- [ ] Heavy optional dependencies are imported lazily.
- [ ] Documentation and method notes are updated where needed.

## Pull request guidance

A pull request should:

1. Explain the problem and why the change is needed.
2. Describe the implementation and any behavior or output-schema changes.
3. List tests run and their actual results (include Python version).
4. Identify scientific references and assumptions for methodological changes.
5. Mention limitations, migration steps, or backward-compatibility concerns.

Keep PRs reviewable and avoid combining unrelated features.

## Documentation changes

Update the README when user-visible capabilities, installation, or commands change.
Update `docs/METHODS.md` when formulas, thresholds, missing-data rules, or scientific assumptions
change. Add a changelog entry for user-visible changes.

## License

By contributing, you agree that your contributions are submitted under the project's MIT License.
