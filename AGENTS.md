# AGENTS.md

xharvest downloads environmental data from many providers and standardises it into netCDF that xarray and [catena](https://github.com/NERC-CEH/catena) read as-is.
It is built so that catena never has to download anything, yet it is useful without catena: no module imports `catena`, and catena finds the node modules through its `catena.modules` entry point.
`docs/adr/` records why; `docs/adding-a-connector.md` holds the rules a connector follows.
Alpha, with no external users: make breaking changes rather than compatibility shims.

- **Verify what a provider's data means against the data, not only its docs.** COSMOS-UK's timestamp convention was settled by summing 30-minute values into daily ones, and its `/locations` GeoJSON turned out to list `[lat, lon]`. Record what was checked, and how, on the provider page.
- **Standardise never converts units.** It keeps the provider's units and changes values only to decode fills and scale factors; conversion is the consuming node's job: it declares the unit it receives and calls `xarray_annotated.units.convert` in its body. Do not ship a node whose only purpose is a unit conversion.
- **Provenance must be captured at fetch time**, in the sidecar: standardise cannot recover where or when a file came from. Anything else standardise needs that the raw file omits (e.g. COSMOS-UK site names) goes in the sidecar's `metadata` too.
- **Fixtures are real provider output.** Regenerate them with `tests/fixtures/<provider>/make_fixtures.py` (it calls the live API); never hand-edit them. On regeneration the data files should be byte-identical; if they are not, the provider has revised its data, which is worth knowing. A provider's licence must allow committing them.
- **`xarray-annotated` and catena are developed by the same maintainer.** When contracts or catena fall short, raise it upstream rather than working around it here.
- **The CLI reference uses mkdocs-typer2's termynal output.** Its native output ignores `:command:` and reads only the first word of `:name:`, so it cannot render one provider's command group on its own.
- **Tool versions are pinned in three places that must stay in step:** `[dependency-groups] dev`, the `.pre-commit-config.yaml` revs, and the `uv_build` bound in `[build-system]`.
- **Never hand-edit `.copier-answers.yml`.** To change an answer, run `copier update --vcs-ref <current _commit> --data key=value`, then resolve every conflict to the project's side; the commit should touch only the answers file.
