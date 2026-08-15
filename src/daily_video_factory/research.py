from __future__ import annotations

import html
import re
import xml.etree.ElementTree as ET
from collections import Counter
from datetime import date
from urllib.parse import quote_plus

import httpx

from .config import Settings
from .logging import get_logger
from .models import EvidenceSource, ResearchItem, ResearchReport


class TopicResearcher:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.timeout = settings.research.request_timeout_seconds
        self.log = get_logger(component="research")
        self.headers = {
            "User-Agent": "AtlasForgeAI/0.2 (+https://github.com/ReaperXD67/atlasforge-ai)"
        }

    def _youtube_suggestions(self) -> list[ResearchItem]:
        items: list[ResearchItem] = []
        for seed in self.settings.research.seed_topics:
            try:
                response = httpx.get(
                    "https://suggestqueries.google.com/complete/search",
                    params={"client": "firefox", "ds": "yt", "q": seed},
                    headers=self.headers,
                    timeout=self.timeout,
                )
                response.raise_for_status()
                suggestions = response.json()[1]
                for rank, title in enumerate(suggestions[:8]):
                    items.append(
                        ResearchItem(
                            title=str(title),
                            source="youtube_autocomplete",
                            score=7.5 - rank * 0.35,
                            rationale=f"YouTube search suggestion for '{seed}'",
                        )
                    )
            except Exception as exc:
                self.log.warning("research_source_failed", source="youtube", error=str(exc))
        return items

    def _google_trends(self) -> list[ResearchItem]:
        try:
            response = httpx.get(
                "https://trends.google.com/trending/rss",
                params={"geo": self.settings.channel.region},
                headers=self.headers,
                timeout=self.timeout,
            )
            response.raise_for_status()
            root = ET.fromstring(response.text)
            items: list[ResearchItem] = []
            for rank, node in enumerate(root.findall(".//item")[:30]):
                title = html.unescape(node.findtext("title", "")).strip()
                link = node.findtext("link")
                if title:
                    items.append(
                        ResearchItem(
                            title=title,
                            source="google_trends_rss",
                            url=link or None,
                            score=5.0 - min(rank, 20) * 0.08,
                            rationale="Current Google Trends RSS item",
                        )
                    )
            return items
        except Exception as exc:
            self.log.warning("research_source_failed", source="google_trends", error=str(exc))
            return []

    def _reddit(self) -> list[ResearchItem]:
        items: list[ResearchItem] = []
        for subreddit in self.settings.research.reddit_subreddits:
            try:
                response = httpx.get(
                    f"https://www.reddit.com/r/{quote_plus(subreddit)}/hot.json",
                    params={"limit": 15, "raw_json": 1},
                    headers=self.headers,
                    timeout=self.timeout,
                    follow_redirects=True,
                )
                response.raise_for_status()
                children = response.json()["data"]["children"]
                for child in children:
                    data = child.get("data", {})
                    if data.get("stickied"):
                        continue
                    title = str(data.get("title", "")).strip()
                    if title:
                        items.append(
                            ResearchItem(
                                title=title,
                                source=f"reddit:r/{subreddit}",
                                url=f"https://reddit.com{data.get('permalink', '')}",
                                score=min(7.0, 3.0 + float(data.get("score", 0)) ** 0.25),
                                rationale="Active discussion; used as audience-signal, not a factual source",
                            )
                        )
            except Exception as exc:
                self.log.warning(
                    "research_source_failed", source=f"reddit:{subreddit}", error=str(exc)
                )
        return items

    @staticmethod
    def _tokens(text: str) -> set[str]:
        return set(re.findall(r"[a-z0-9]+", text.lower()))

    def _rank(self, items: list[ResearchItem]) -> list[ResearchItem]:
        audience_tokens = self._tokens(" ".join(self.settings.channel.audience))
        seed_tokens = self._tokens(" ".join(self.settings.research.seed_topics))
        frequencies = Counter(token for item in items for token in self._tokens(item.title))
        seen: set[str] = set()
        ranked: list[ResearchItem] = []
        for item in items:
            normalized = re.sub(r"\W+", " ", item.title.lower()).strip()
            if normalized in seen or len(normalized) < 12:
                continue
            seen.add(normalized)
            tokens = self._tokens(item.title)
            relevance = len(tokens & (audience_tokens | seed_tokens)) * 1.4
            cross_signal = sum(min(frequencies[token], 4) for token in tokens) * 0.12
            question_bonus = 0.7 if any(word in tokens for word in {"how", "why", "what"}) else 0
            item.score = round(item.score + relevance + cross_signal + question_bonus, 3)
            ranked.append(item)
        return sorted(ranked, key=lambda item: item.score, reverse=True)

    def run(self, query_date: date, topic_override: str | None = None) -> ResearchReport:
        items = self._youtube_suggestions() + self._google_trends() + self._reddit()
        if not items:
            items = [
                ResearchItem(
                    title=topic,
                    source="configured_seed",
                    score=1,
                    rationale="Network research unavailable; used configured evergreen seed",
                )
                for topic in self.settings.research.seed_topics
            ]
        ranked = self._rank(items)[: self.settings.research.max_candidates]
        configured_topics = self.settings.research.editorial_topics
        if topic_override:
            selected_title = topic_override
        elif self.settings.research.rotate_editorial_topics and configured_topics:
            selected_title = configured_topics[query_date.toordinal() % len(configured_topics)]
        else:
            selected_title = ranked[0].title
        brand = self.settings.channel.brand_name.strip()
        brand_focused = bool(brand and brand.lower() in selected_title.lower())
        if brand_focused:
            angle = (
                f"Answer '{selected_title}' directly for a skeptical beginner in "
                f"{self.settings.channel.region}. Ground every "
                "registration, eligibility, product, or compensation statement in the official "
                "source pack; distinguish consumer and distributor membership; explain tradeoffs; "
                "and make no earnings or health claims."
            )
        elif self.settings.channel.brand_required and brand:
            angle = (
                f"Answer the search intent behind '{selected_title}' with an evidence-aware beginner "
                f"guide. Teach a reusable framework first, then evaluate {brand} neutrally as one "
                "optional example."
            )
        else:
            angle = (
                f"Answer the search intent behind '{selected_title}' with an evidence-aware beginner "
                "guide. Teach a reusable framework, concrete examples, and honest tradeoffs."
            )
        evidence = [
            EvidenceSource(
                title=source.title,
                url=source.url,
                checked_on=source.checked_on,
                summary=source.summary,
            )
            for source in self.settings.research.official_sources
        ]
        return ResearchReport(
            query_date=query_date,
            candidates=ranked,
            selected_title=selected_title,
            selected_angle=angle,
            brand_focused=brand_focused,
            evidence=evidence,
            source_notes=[
                "Trends and social posts are topic signals, not verified evidence.",
                "Official-source summaries are locally pinned and must be refreshed on the configured cadence.",
                "Any product, financial, supplement, or skincare claim outside the source pack must be verified before publication.",
            ],
        )
