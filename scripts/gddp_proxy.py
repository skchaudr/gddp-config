"""Lazy proxies so cli_* modules honor test patches on the gddp module."""

from __future__ import annotations


class _ConsoleProxy:
    def __getattr__(self, item: str):
        import gddp
        return getattr(gddp.console, item)


console = _ConsoleProxy()
