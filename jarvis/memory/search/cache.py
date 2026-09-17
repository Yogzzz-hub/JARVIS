from collections import OrderedDict
from jarvis.memory.search.models import SearchQuery, SearchResult

class SearchHotCache:
    """Bounded LRU cache for search results with generational invalidation."""
    def __init__(self, capacity: int = 2048, max_entries: int | None = None):
        self.capacity = max_entries if max_entries is not None else capacity
        self._cache: OrderedDict[tuple, list[SearchResult]] = OrderedDict()
        self.generation = 1
        self.hits = 0
        self.misses = 0
        self.evictions = 0

    def bump_generation(self):
        self.invalidate()

    def _make_key(self, query: SearchQuery) -> tuple:
        return (
            query.text.strip().casefold(),
            query.type_hint,
            query.temporal_hint,
            query.latest,
            self.generation,
        )

    def get(self, query: SearchQuery) -> list[SearchResult] | None:
        key = self._make_key(query)
        if key in self._cache:
            self.hits += 1
            self._cache.move_to_end(key)
            return self._cache[key]
        self.misses += 1
        return None

    def put(self, query: SearchQuery, results: list[SearchResult]):
        key = self._make_key(query)
        if key in self._cache:
            self._cache.move_to_end(key)
            self._cache[key] = results
            return
        if len(self._cache) >= self.capacity:
            self._cache.popitem(last=False)
            self.evictions += 1
        self._cache[key] = results

    def invalidate(self):
        """Advances index generation and purges cached results."""
        self.generation += 1
        self._cache.clear()
