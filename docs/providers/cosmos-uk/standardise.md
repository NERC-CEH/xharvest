# How COSMOS-UK standardisation works

`fetch` changes nothing: it saves each site's response as the API serves it.
`standardise` runs the graph below, from the file paths to the dataset.
Each node does one thing, and its colour says what kind of thing; [ADR 2](https://github.com/NERC-CEH/xharvest/blob/main/docs/adr/0002-standardise-as-hamilton-graph.md#decision) defines each kind.
Hover over a node for a summary, or click its name for its entry under [Standardisation nodes](#standardisation-nodes), which says what it does and why.

--8<-- "docs/providers/_graphs/cosmos.html"

Nothing converts units, fills gaps, or removes values.

!!! note "Judgement calls"

    The node tagged `interprets` makes a choice that is xharvest's, not the provider's:
    [`period`](#xharvest.cosmos._pipeline.period) decides which period each timestamp covers, which the API does not say.
    Its entry says what it decides, and [Timestamps](data.md#timestamps) says how that was checked.

## Standardisation nodes

The nodes of the graph above, in the order the module defines them.

::: xharvest.cosmos._pipeline
    options:
      heading_level: 3
      show_root_heading: true
      members_order: source
      filters: ["!^_", "!^INSTITUTION$", "!^TITLE$"]
