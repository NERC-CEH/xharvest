# Run the full check suite: lint, typecheck, test, run examples, docs.
_:
  @just lint typecheck test check-examples docs

# Format and lint the package using ruff, and lint the examples using marimo.
lint:
  ruff format
  marimo check --fix examples/
  ruff check --fix
  marimo check --strict examples/

# Variant of `lint` that doesn't cause any changes to files (for CI).
lint-check:
  ruff format --check
  ruff check
  marimo check --strict examples/

# Assert the example notebooks are in marimo's canonical form.
check-canonical:
  marimo check --fix examples/
  git diff --exit-code examples/

# Confirm the example notebooks actually run.
check-examples:
  python examples/notebook.py

# Run static type checker.
typecheck:
  pyright

# Run the test suite using pytest.
test:
  pytest

# Run tests with coverage report.
test-cov:
  pytest --cov=conduit_data --cov-report=term-missing --cov-fail-under=90

# Run doctest examples embedded in source docstrings.
doctest:
  pytest --doctest-modules src/conduit_data

# Export the example notebooks, then build the documentation using Zensical.
docs: docs-examples
  zensical build

# Export the example notebooks to markdown with their rendered outputs.
docs-examples:
  marimo-md-export examples/notebook.py docs/example.md
  ruff format examples/  # override marimo's reformatting

# Serve the documentation locally with live reload.
docs-serve: docs-examples
  zensical serve
