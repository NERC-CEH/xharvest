## 3. FLUXNET and ICOS are separate connectors, and the FLUXNET readers live in `xharvest.fluxnet`

- **Status:** accepted
- **Date:** 2026-11-25

### Context

`xharvest.icos` fetches the FLUXNET release product from the ICOS Carbon Portal, but 273 of its 355 sites are from other networks; in the UK only UK-AMo is an ICOS station.
ICOS stations also publish measured LAI (as green area index), biomass and canopy height, in a separate ETC L2 archive that the other sites lack.
Those measurements are in BIF, the same format as the site metadata the FLUXNET reader already parses.

### Decision

- Today's `xharvest.icos` becomes `xharvest.fluxnet`, for the multi-network FLUXNET release, with further hubs to follow as #2 proposes.
- `xharvest.icos` serves ICOS stations' own products from the ETC L2 archive, starting with the ancillary measurements.
- The FLUXNET archive and BIF readers live in `xharvest.fluxnet`, and `xharvest.icos` imports them from there.

`icos` is not nested under `fluxnet`.
ICOS's ecosystem products are FLUXNET-format, but ICOS also runs atmosphere and ocean stations, which a nested `fluxnet.icos` could not hold.

A private `xharvest/_formats/` package for shared readers is deferred until a second format is shared.

### Consequences

- Each connector's name matches what it serves, and the root of the package gains no shared module.
- `docs/adding-a-connector.md` changes: a shared reader lives in the connector named for its format, rather than in a subpackage of its own.
- The rename breaks `xharvest.icos` and `xharvest icos` for current callers, which is acceptable while xharvest is alpha.
