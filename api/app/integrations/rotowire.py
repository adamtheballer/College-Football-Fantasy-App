from __future__ import annotations

from typing import Any

import httpx
from bs4 import BeautifulSoup


class RotowireClient:
    def __init__(self, url: str = "https://www.rotowire.com/cfootball/news.php?view=all") -> None:
        self.url = url

    def _parse_table(self, soup: BeautifulSoup) -> list[dict[str, Any]]:
        table = soup.find("table")
        if not table:
            return []
        headers = [th.get_text(strip=True) for th in table.find_all("th")]
        rows: list[dict[str, Any]] = []
        for tr in table.find_all("tr")[1:]:
            cells = [td.get_text(" ", strip=True) for td in tr.find_all("td")]
            if not cells:
                continue
            row: dict[str, Any] = {}
            for idx, value in enumerate(cells):
                key = headers[idx] if idx < len(headers) else f"col_{idx}"
                row[key] = value
            rows.append(row)
        return rows

    def _parse_news(self, soup: BeautifulSoup) -> list[dict[str, Any]]:
        updates = soup.select(".news-update") or soup.select(".news-update__item") or []
        rows: list[dict[str, Any]] = []
        injury_keywords = (
            "injury",
            "questionable",
            "doubtful",
            "probable",
            "out ",
            " out",
            "sidelined",
            "surgery",
            "miss ",
            "will miss",
            "dealing with",
            "doesn't practice",
            "didn't practice",
        )
        injury_tags = {
            "ankle",
            "knee",
            "shoulder",
            "hamstring",
            "concussion",
            "illness",
            "foot",
            "leg",
            "undisclosed",
            "back",
            "wrist",
            "elbow",
            "hand",
        }

        for update in updates:
            player_el = update.select_one(".news-update__player-link")
            headline_el = update.select_one(".news-update__headline")
            report_el = update.select_one(".news-update__report") or update.select_one(".news-update__body")
            meta_el = update.select_one(".news-update__meta") or update.select_one(".news-update__info")
            pos_el = update.select_one(".news-update__pos")

            player = player_el.get_text(" ", strip=True) if player_el else ""
            headline = headline_el.get_text(" ", strip=True) if headline_el else ""
            report = report_el.get_text(" ", strip=True) if report_el else ""
            meta_text = meta_el.get_text(" ", strip=True) if meta_el else ""
            position = pos_el.get_text(" ", strip=True) if pos_el else ""

            if not player or not meta_text:
                continue

            lower_text = f"{headline} {report} {meta_text}".lower()
            if not any(keyword in lower_text for keyword in injury_keywords):
                continue

            status = "QUESTIONABLE"
            if "doubtful" in lower_text:
                status = "DOUBTFUL"
            elif "questionable" in lower_text or "game-time decision" in lower_text or "gtd" in lower_text:
                status = "QUESTIONABLE"
            elif "probable" in lower_text:
                status = "PROBABLE"
            elif "out" in lower_text or "will miss" in lower_text or "sidelined" in lower_text:
                status = "OUT"

            tokens = meta_text.split()
            if tokens and position and tokens[0].upper() == position.upper():
                tokens = tokens[1:]
            injury = headline
            if tokens and tokens[-1].lower() in injury_tags:
                injury = tokens[-1].title()
                tokens = tokens[:-1]
            team = " ".join(tokens).strip()
            if not team:
                continue

            rows.append(
                {
                    "Player": player,
                    "Team": team,
                    "Status": status,
                    "Position": position or None,
                    "Injury": injury,
                    "Notes": report or headline,
                }
            )
        return rows

    def get_injuries(self) -> list[dict[str, Any]]:
        with httpx.Client(timeout=20.0) as client:
            response = client.get(self.url)
        response.raise_for_status()

        soup = BeautifulSoup(response.text, "html.parser")

        rows = self._parse_table(soup)
        if rows:
            return rows

        return self._parse_news(soup)
