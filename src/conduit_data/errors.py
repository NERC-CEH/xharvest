"""Errors raised by connectors."""


class ProviderError(RuntimeError):
    """A provider rejected a request, or returned something a connector cannot read.

    The message carries the provider's own explanation where it gives one.
    """
