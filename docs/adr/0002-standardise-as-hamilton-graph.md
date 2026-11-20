## 2. Standardise runs as a Hamilton graph of single-purpose nodes

- **Status:** accepted
- **Date:** 2026-11-19

### Context

xharvest is meant to be a transparent tool: a user should be able to see what was done to a provider's data between download and the netCDF file they load.
Standardisation is where that is hardest.
For COSMOS-UK it is mostly reshaping, but the ICOS connector's `standardise` makes about fifteen changes, and some are interpretations the provider does not state:

- every `_QC` is given unit `1` because its values are fractions, although the archive labels some of them with their parent variable's unit;
- `LE_CORR` and `H_CORR` get no `cell_methods`, because the data contradict their definitions;
- where a variable has several metadata entries, the first is kept.

These live in private functions, so finding where something happens means reading the code.
The provider page lists the changes in prose, which describes the code from outside and will drift from it.

catena pipelines, and the viresco docs built on them, already solve this for models.
Each step is a Hamilton node with a docstring and annotations, the documentation is generated from the nodes, and a rendered graph shows how they connect.

### Decision

Each connector's `standardise` runs a Hamilton graph, built from modules of nodes in which each node does one auditable thing.

- **Nodes live in a private module of their own**, `xharvest/<provider>/_pipeline.py`, because Hamilton makes a node of every public function in a module it is given.
  `_standardise.py` keeps `standardise(paths)` and `to_netcdf(paths, out)`, with unchanged signatures; `standardise` builds the driver, runs the graph and returns its result.
  A file format shared between providers keeps its nodes in a shared module, as `xharvest._fluxnet` holds the FLUXNET archive reader, and the graph is built from both modules.
- **One node is one action, applied to every site and variable at once.**
  The graph is static, from one input (`paths`) to one output (`dataset`), with no dynamic fan-out (`Parallelizable`/`Collect`), so it reads the same whatever is being standardised.
  There is never a node per variable or per site.
  A private helper (`_name`, which Hamilton ignores) is allowed only for mechanics inside one node's action, such as decoding text; any decision about the data is a node.
- **Every node has a docstring and an `action` tag**, from a fixed vocabulary:

  - `reads`: parses provider files without changing what they say;
  - `selects`: keeps some of what was read and drops the rest;
  - `checks`: raises if the data break an expectation, and otherwise passes them through unchanged;
  - `decodes`: changes values as the provider specifies, such as fill values to NaN;
  - `reshapes`: rearranges values without changing them;
  - `annotates`: adds or rewrites attributes and coordinates, such as unit strings, without changing values;
  - `interprets`: a judgement the provider does not state.

  A test enforces both.
  Because Hamilton runs only the nodes an output needs, a `checks` node returns what it checked, and the nodes after it take that.
- **The docs are generated from the graph.**
  Each provider page renders the graph, coloured by `action`, and the node reference from the docstrings, in place of hand-written lists of what `standardise` changes.
  The graph is rendered at docs build time and not committed.
  What was checked against the data, and where the provider contradicts itself, stays as prose: it is evidence, which the code cannot generate.
- **Pipeline modules are not catena modules.**
  They are never registered in the `catena.modules` entry-point group, and a test enforces it, so standardisation nodes never appear in a user's pipeline.
- **`fetch` is unchanged**: it is network-bound and imperative, for the reasons ADR 1 keeps downloading out of catena.
- **Hamilton becomes a dependency of xharvest.**
  `apache-hamilton` needs numpy, pandas, typing-extensions and typing-inspect, and all but the last already come with xarray.
  The node modules for catena therefore no longer need to explain a missing Hamilton.

The ICOS connector is converted first.
COSMOS-UK follows once the ICOS page shows whether the generated documentation reads better than what it replaces.

### Consequences

- What `standardise` does to a provider's data is documented by the code that does it, and judgements are visible in the graph as `interprets` nodes.
- Each node can be tested on its own.
- A node's inputs are wired by parameter name, which is implicit: reading the source, it is less obvious where a value comes from than with explicit calls, and debugging follows names through the module rather than a call stack.
- Adding a connector needs some familiarity with Hamilton, which raises the bar for contributors who do not use catena.
- Hamilton logs a traceback and a request to join its Slack when a node raises.
  `standardise` silences Hamilton's loggers while it runs and re-raises the original exception, so errors reach the CLI and callers as they do now.
- Building the docs needs Graphviz: dotdoc, which draws the graphs, in the `docs` group, and the `dot` binary in CI.
- A graph shows data flow, not decisions.
  The docstrings and tags must say why each node does what it does, or the graph adds nothing.
