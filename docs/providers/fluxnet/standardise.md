# How FLUXNET standardisation works

`fetch` changes nothing: it picks each site's current archive, checks it against the portal's SHA-256, and saves it as served.
`standardise` runs the graph below, from the archive paths to the dataset.
Each node does one thing, and its colour says what kind of thing; [ADR 2](https://github.com/NERC-CEH/xharvest/blob/main/docs/adr/0002-standardise-as-hamilton-graph.md#decision) defines each kind.
Hover over a node for a summary, or click its name for its entry under [Standardisation nodes](#standardisation-nodes), which says what it does and why.

--8<-- "docs/providers/_graphs/fluxnet.html"

Nothing converts units, filters on quality flags, or fills gaps.
Gap-filled values come from ONEFlux, upstream; the `_QC` fractions say how much of each day was filled.

!!! note "Judgement calls"

    The nodes tagged `interprets` make choices that are xharvest's, not the provider's, and could reasonably go the other way:
    [`variables`](#xharvest.fluxnet._archive.variables), [`descriptions`](#xharvest.fluxnet._pipeline.descriptions), [`flag_attributes`](#xharvest.fluxnet._pipeline.flag_attributes) and [`cell_methods`](#xharvest.fluxnet._pipeline.cell_methods).
    Each one's entry says what it decides and why.

## Standardisation nodes

The nodes of the graph above, in the order their modules define them.
The FLUXNET reader reads any FLUXNET archive, whichever hub serves it; the rest are specific to this connector.

::: xharvest.fluxnet._archive
    options:
      heading_level: 3
      show_root_heading: true
      members_order: source
      filters: ["!^_", "!^FILL_VALUE$"]

::: xharvest.fluxnet._pipeline
    options:
      heading_level: 3
      show_root_heading: true
      members_order: source
      filters: ["!^_", "!^QC_DESCRIPTION$", "!^TITLE$", "!^Kept$", "!^KEPT$"]
