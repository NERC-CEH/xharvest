# Run the full check suite: lint, typecheck, test, docs.
_:
  @just lint typecheck test docs

# Format and lint the package using ruff.
lint:
  ruff format
  ruff check --fix

# Variant of `lint` that doesn't cause any changes to files (for CI).
lint-check:
  ruff format --check
  ruff check

# Run static type checker.
typecheck:
  pyright

# Run the test suite using pytest.
test:
  pytest

# Run only the tests that call real provider APIs (network needed).
test-live:
  pytest -m live

# Run tests with coverage report.
test-cov:
  pytest --cov=xharvest --cov-report=term-missing --cov-fail-under=90

# Run doctest examples embedded in source docstrings.
doctest:
  pytest --doctest-modules src/xharvest

# Draw each connector's standardisation graph for the docs (needs Graphviz).
graphs:
  python scripts/render_graphs.py

# Build the documentation using Zensical, failing on any warning, such as a graph
# node whose link to its entry does not resolve.
docs: graphs
  zensical build --strict

# Serve the documentation locally with live reload.
docs-serve: graphs
  zensical serve
