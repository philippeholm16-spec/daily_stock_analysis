"""Fair source sampling: keep Placera, DI/finance, analysis and issuer feeds visible.

This is a research discovery budget, not a guarantee that every publisher was
covered or that an article identifies a unique tradable share. Only provider-
verified identities may enter the live research candidate ranking.
"""
from src.automatic_news_candidates import select_headline_searches


def select_diverse_searches(direct_news, indexed_news, *, now, max_queries=10):
    if not 1 <= max_queries <= 12:
        raise ValueError("max_queries_must_be_1_to_12")
    indexed_news = list(indexed_news)
    groups = (
        ("publisher", list(direct_news), 4),
        ("financial_press", [x for x in indexed_news
                             if x.source == "Google News:financial_press"], 2),
        ("analysis", [x for x in indexed_news
                      if x.source == "Google News:analysis"], 2),
        ("company_releases", [x for x in indexed_news
                              if x.source == "Google News:company_releases"], 2),
    )
    pools, reasons = [], []
    for group_name, items, quota in groups:
        # Each bounded source gets its own opportunity. This does not turn
        # Google News indexing into publisher-verified reporting.
        candidates, rejected = select_headline_searches(
            items, now=now, max_queries=min(len(items), 30))
        pools.append((group_name, candidates, quota))
        reasons.extend(rejected[:30])
    selected, seen, source_counts = [], set(), {name: 0 for name, _, _ in groups}

    def select_from(name, candidates, quota):
        for row in candidates:
            if len(selected) >= max_queries or source_counts[name] >= quota:
                break
            query = row["query"].casefold().strip()
            if query in seen:
                continue
            seen.add(query)
            selected.append(row)
            source_counts[name] += 1

    for group_name, candidates, quota in pools:
        select_from(group_name, candidates, quota)
    if len(selected) < max_queries:
        for group_name, candidates, _quota in pools:
            select_from(group_name, candidates, max_queries)
    return selected, reasons, source_counts
