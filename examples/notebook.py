import marimo

__generated_with = "0.23.16"
app = marimo.App(width="medium")


@app.cell(hide_code=True)
def _(mo):
    mo.md("""
    # Example

    This is a [marimo](https://marimo.io/) notebook. It is a valid Python
    module, so `ruff` and `pyright` see it like any other source file, and it
    is exported to Markdown *with* its rendered outputs by
    [`marimo-md-export`](https://github.com/jmarshrossney/marimo-md-export)
    as part of `just docs`.

    Edit it interactively with:

    ```sh
    marimo edit examples/notebook.py
    ```
    """)
    return


@app.cell
def _():
    from conduit_data import greet

    greet("marimo")
    return (greet,)


@app.cell(hide_code=True)
def _(mo):
    mo.md("""
    Cell outputs are captured in the exported Markdown, so the
    documentation cannot drift from what the code actually does.
    """)
    return


@app.cell
def _(greet):
    [greet(name) for name in ("one", "two", "three")]
    return


@app.cell
def _():
    import marimo as mo

    return (mo,)


if __name__ == "__main__":
    app.run()
