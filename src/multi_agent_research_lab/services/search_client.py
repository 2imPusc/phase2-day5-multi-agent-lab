"""Search client abstraction for ResearcherAgent."""

from __future__ import annotations

import logging

import requests
from tenacity import retry, stop_after_attempt, wait_exponential

from multi_agent_research_lab.core.config import get_settings
from multi_agent_research_lab.core.schemas import SourceDocument

logger = logging.getLogger(__name__)


class SearchClient:
    """Provider-agnostic search client using Brave Search API with mock fallback."""

    def __init__(self) -> None:
        settings = get_settings()
        self._api_key = settings.brave_api_key

    def search(self, query: str, max_results: int = 5) -> list[SourceDocument]:
        """Search for documents relevant to a query."""

        if not self._api_key:
            logger.warning("No BRAVE_API_KEY set — returning mock results")
            return self._mock_search(query, max_results)
        return self._brave_search(query, max_results)

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(min=1, max=10))
    def _brave_search(self, query: str, max_results: int) -> list[SourceDocument]:
        headers = {
            "X-Subscription-Token": self._api_key or "",
            "Accept": "application/json",
        }
        resp = requests.get(
            "https://api.search.brave.com/res/v1/web/search",
            params={"q": query, "count": str(max_results)},
            headers=headers,
            timeout=10,
        )
        resp.raise_for_status()
        results = resp.json().get("web", {}).get("results", [])
        docs = [
            SourceDocument(
                title=r.get("title", ""),
                url=r.get("url"),
                snippet=r.get("description", ""),
            )
            for r in results[:max_results]
        ]
        logger.info("Brave search returned %d results for: %s", len(docs), query)
        return docs

    @staticmethod
    def _mock_search(query: str, max_results: int) -> list[SourceDocument]:
        return [
            SourceDocument(
                title=f"Source {i + 1} for: {query}",
                url=f"https://example.com/source-{i + 1}",
                snippet=f"Relevant information about {query} from source {i + 1}. "
                f"This mock result provides context for research and analysis.",
            )
            for i in range(min(max_results, 3))
        ]
