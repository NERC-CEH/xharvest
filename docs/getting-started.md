# Getting started

## Installation

Install from the repository:

```sh
pip install git+https://github.com/NERC-CEH/conduit-data
```

Or, if you use [uv](https://docs.astral.sh/uv/), add it to a project:

```sh
uv add git+https://github.com/NERC-CEH/conduit-data
```

## First steps

The package exposes a single function:

```python
from conduit_data import greet

print(greet())  # Hello, world!
print(greet("reader"))  # Hello, reader!
```

That's the whole interface. Replace this page with something useful once the
package does something useful.

## Maths

KaTeX is wired up, so inline maths like $e^{i\pi} = -1$ and display maths

$$
\int_{-\infty}^{\infty} e^{-x^{2}} \, \mathrm{d}x = \sqrt{\pi}
$$

both render. This section exists so the docs build exercises the KaTeX
configuration; delete it (and see `zensical.toml`) if this package's
documentation has no maths in it.
