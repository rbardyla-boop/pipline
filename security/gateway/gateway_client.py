"""
Gateway-aware Tavily client.

In containerized mode (GATEWAY_URL set): routes all Tavily calls through
the AgentGateway proxy, which injects the real TAVILY_API_KEY.

In local dev mode: falls back to direct TavilyClient with key from env.

Scans fetched content for injection payloads before returning to caller.
"""
from __future__ import annotations

import os
import logging
from typing import Any

from security.firewall.llamafirewall_wrapper import scan_output

log = logging.getLogger(__name__)


class GatewayTavilyClient:
    """
    Drop-in replacement for `tavily.TavilyClient`.

    Adds:
    - Gateway routing when GATEWAY_URL is set
    - Post-fetch injection scan on all returned content snippets
    """

    def __init__(self) -> None:
        self._gateway_url = os.getenv("GATEWAY_URL")
        self._api_key = os.getenv("TAVILY_API_KEY", "")

    def search(self, query: str, **kwargs: Any) -> dict:
        results = self._do_search(query, **kwargs)
        return self._scan_results(results)

    def _do_search(self, query: str, **kwargs: Any) -> dict:
        if self._gateway_url:
            return self._gateway_search(query, **kwargs)
        return self._direct_search(query, **kwargs)

    def _direct_search(self, query: str, **kwargs: Any) -> dict:
        try:
            from tavily import TavilyClient
            client = TavilyClient(api_key=self._api_key)
            return client.search(query, **kwargs)
        except ImportError:
            log.warning("[GATEWAY] tavily not installed — returning empty results")
            return {"results": []}
        except Exception as e:
            log.warning("[GATEWAY] Tavily search error: %s", e)
            return {"results": []}

    def _gateway_search(self, query: str, **kwargs: Any) -> dict:
        import requests
        max_results = kwargs.get("max_results", 3)
        url = f"{self._gateway_url.rstrip('/')}/tavily/search"
        try:
            resp = requests.post(
                url,
                json={"query": query, "max_results": max_results},
                timeout=20,
            )
            resp.raise_for_status()
            return resp.json()
        except Exception as e:
            log.warning("[GATEWAY] Gateway Tavily call failed: %s — falling back to direct", e)
            return self._direct_search(query, **kwargs)

    def _scan_results(self, results: dict) -> dict:
        """Scan each result snippet for injection payloads."""
        scanned = []
        for item in results.get("results", []):
            content = item.get("content", "")
            scan = scan_output(content)
            if scan.blocked:
                log.warning(
                    "[GATEWAY] Tavily result BLOCKED (query contamination): %s — content suppressed",
                    scan.reason,
                )
                item = {**item, "content": f"[BLOCKED: {scan.reason}]"}
            scanned.append(item)
        return {**results, "results": scanned}


def get_gateway_tavily_client() -> GatewayTavilyClient:
    return GatewayTavilyClient()
