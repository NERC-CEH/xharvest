import marimo

__generated_with = "0.25.2"
app = marimo.App(width="medium")


@app.cell(hide_code=True)
def _(mo):
    mo.md("""
    # COSMOS-UK, from raw download to a conduit input

    This notebook standardises two short COSMOS-UK records that are committed
    with the tests, so it runs without network access.
    The same files come from the API with:

    ```python
    from datetime import date
    from conduit_data import cosmos

    raw = cosmos.fetch("MOORH", date(2025, 1, 1), date(2025, 1, 14), "data/raw")
    ```

    Every file `fetch` writes has a `.meta.json` sidecar recording the request
    and when it was made.
    """)
    return


@app.cell
def _():
    from pathlib import Path

    from conduit_data import cosmos

    fixtures = Path(__file__).parents[1] / "tests" / "fixtures" / "cosmos"
    raw = sorted(fixtures.glob("*_1D_*.json"))
    [p.name for p in raw]
    return cosmos, raw


@app.cell(hide_code=True)
def _(mo):
    mo.md("""
    `standardise` skips the sidecars and combines the sites into one
    `(time, site)` Dataset.
    The two records cover different days, so each is NaN-padded where the
    other has data.
    """)
    return


@app.cell
def _(cosmos, raw):
    ds = cosmos.standardise(raw)
    ds
    return (ds,)


@app.cell(hide_code=True)
def _(mo):
    mo.md("""
    Values and units are the API's own; only nulls change, to NaN.
    The provenance is in the global attributes:
    """)
    return


@app.cell
def _(ds):
    print(ds.attrs["license"])
    print(ds.attrs["history"])
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md("""
    On snow days COSMOS-UK reports a VWC *estimated* from the counts before the
    snow, which shows up at Moor House as a flat run of 65.5%.
    The node `cosmos_vwc_snow_masked` removes those days.
    Solid lines are the masked values, dotted lines the values as reported.
    """)
    return


@app.cell
def _(ds):
    import matplotlib.pyplot as plt

    from conduit_data.cosmos.nodes import cosmos_vwc_snow_masked

    colours = {"ALIC1": "#2a78d6", "MOORH": "#eb6834"}
    names = {"ALIC1": "Alice Holt", "MOORH": "Moor House"}
    masked = cosmos_vwc_snow_masked(ds.cosmos_vwc, ds.snow)

    fig, ax = plt.subplots(figsize=(8, 3.8))
    snow_days = ds.time.where(ds.snow.sel(site="MOORH") == 1, drop=True).values
    ax.axvspan(snow_days[0], snow_days[-1], color="#e1e0d9", lw=0)
    ax.text(snow_days[0], 30, " Moor House snow days", color="#52514e", va="bottom")
    for site, colour in colours.items():
        ax.plot(ds.time, ds.cosmos_vwc.sel(site=site), color=colour, lw=1, ls=":")
        ax.plot(
            ds.time,
            masked.sel(site=site),
            color=colour,
            lw=2,
            marker="o",
            ms=4,
            label=names[site],
        )
    ax.set_ylim(28, 100)
    ax.set_ylabel("COSMOS VWC (%)", color="#52514e")
    ax.legend(frameon=False, loc="upper right", labelcolor="#0b0b0b")
    for side in ("top", "right"):
        ax.spines[side].set_visible(False)
    ax.tick_params(colors="#52514e")
    fig.autofmt_xdate()
    fig
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md("""
    ## Into conduit

    Write the standardised file, then read it from a conduit config.
    `[cosmos]` needs no `_import_path`: installing `conduit-data` registers it.

    ```python
    cosmos.to_netcdf(raw, "data/cosmos.nc")
    ```

    ```toml
    [inputs.cosmos]
    path = "data/cosmos.nc"
    suffix = "\"
    vars = ["cosmos_vwc", "snow"]

    [cosmos]
    ```

    A node that wants VWC as a fraction declares `Unit("m3 m-3")` on its
    input, and conduit converts from percent.
    """)
    return


@app.cell
def _():
    import marimo as mo

    return (mo,)


if __name__ == "__main__":
    app.run()
