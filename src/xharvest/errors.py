"""Errors raised by connectors."""


class ProviderError(RuntimeError):
    """A provider was unreachable, or its response unusable.

    Raised when a provider cannot be reached, rejects a request, or returns
    something a connector cannot read. The message carries the provider's own
    explanation where it gives one.
    """
