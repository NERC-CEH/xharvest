# How ICOS standardisation works

`fetch` changes nothing: it picks each station's current archive, checks it against the portal's SHA-256, and saves it as served.
`standardise` runs the graph below, from the archive paths to one Dataset per group, and returns the group asked for.
Each node does one thing, and its colour says what kind of thing; [ADR 2](https://github.com/NERC-CEH/xharvest/blob/main/docs/adr/0002-standardise-as-hamilton-graph.md#decision) defines each kind.
Hover over a node for a summary, or click its name for its entry under [Standardisation nodes](#standardisation-nodes), which says what it does and why.

--8<-- "docs/providers/_graphs/icos.html"

Nothing converts units, averages or classifies records, or interpolates between dates.
The BIF files are parsed with the same reader as FLUXNET's site metadata, `xharvest.fluxnet._bif`.

!!! note "Judgement calls"

    The nodes tagged `interprets` make choices that are xharvest's, not the provider's, and could reasonably go the other way:
    [`values`](#xharvest.icos._pipeline.values) and [`periods`](#xharvest.icos._pipeline.periods).
    Each one's entry says what it decides and why.

## Standardisation nodes

The nodes of the graph above, in the order their module defines them.

::: xharvest.icos._pipeline
    options:
      heading_level: 3
      show_root_heading: true
      members_order: source
      filters: ["!^_", "!^TITLE$", "!^DRY_MATTER$", "!^ArchiveText$", "!^Site$", "!^Entry$"]
