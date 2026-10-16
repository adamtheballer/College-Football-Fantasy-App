"""Read public Power Four football availability reports.

The conference pages are the source of record.  This module deliberately
reads rendered report documents only; it does not call undocumented data
endpoints belonging to the embedded report vendor.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
import os
import re
from collections.abc import Callable
from typing import Any
from urllib.parse import urljoin, urlparse, parse_qs

import httpx
from bs4 import BeautifulSoup


@dataclass(frozen=True)
class ConferenceReportSource:
    conference: str
    url: str


OFFICIAL_CONFERENCE_REPORTS = (
    ConferenceReportSource("SEC", "https://www.secsports.com/fbreports"),
    ConferenceReportSource(
        "BIG12",
        "https://big12sports.com/sports/2025/8/14/FBreporting.aspx",
    ),
    ConferenceReportSource(
        "ACC",
        "https://theacc.com/sports/2025/8/28/availability-reporting-football.aspx",
    ),
    # The conference has moved the season-specific route before.  Keep this
    # as the official directory, rather than hardcoding a prior-season report.
    ConferenceReportSource("BIG10", "https://bigten.org/fb/availability-reports/"),
)


class ConferenceReportUnavailable(RuntimeError):
    """Raised when a public report cannot be read as a document."""


def parse_archive_document(html: str, *, conference: str, source_url: str) -> list[dict[str, str | None]]:
    """Read dated archive rows for deliberate audits/backfills, never live fallback.

    The public archives expose final and intermediate statuses in separate
    columns. Pick the last populated update, retaining the game date so a caller
    cannot accidentally assign old absences to this week's pending games.
    """
    rows: list[dict[str, str | None]] = []
    for table in BeautifulSoup(html, "html.parser").find_all("table"):
        header = table.find("tr")
        if header is None:
            continue
        headers = [cell.get_text(" ", strip=True) for cell in header.find_all(["th", "td"])]
        if not _has_heading(headers, "player") or not _has_heading(headers, "game day status"):
            continue
        for tr in table.find_all("tr")[1:]:
            values = [cell.get_text(" ", strip=True) for cell in tr.find_all(["td", "th"])]
            if len(values) != len(headers):
                continue
            date = _field(headers, values, "date")
            parsed_date = None
            for pattern in ("%m/%d/%y", "%a, %b %d, %Y"):
                try:
                    parsed_date = datetime.strptime(date or "", pattern).date().isoformat()
                    break
                except ValueError:
                    pass
            name = _field(headers, values, "player")
            team = _field(headers, values, "team")
            status = _field(headers, values, "game day status", "update 2 status", "update 1 status", "initial status")
            if not parsed_date or not name or not team or not status or status.upper() == "EXEMPT":
                continue
            rows.append({"player_name": name, "team_name": team, "status": status,
                         "conference": conference, "source_url": source_url,
                         "game_date": parsed_date, "position": None, "injury": None,
                         "return_timeline": None, "practice_level": None, "notes": None})
    if not rows:
        raise ConferenceReportUnavailable(f"{conference} archive did not contain readable dated report rows")
    return rows


def report_source_for(conference: str) -> ConferenceReportSource:
    normalized = conference.upper().replace(" ", "")
    for source in OFFICIAL_CONFERENCE_REPORTS:
        if source.conference == normalized:
            return source
    raise ValueError(f"unsupported conference report: {conference}")


def _header_key(value: str) -> str:
    return "".join(character for character in value.lower() if character.isalnum())


def _field(headers: list[str], values: list[str], *candidates: str) -> str | None:
    columns = {_header_key(header): value for header, value in zip(headers, values)}
    for candidate in candidates:
        value = columns.get(_header_key(candidate))
        if value:
            return value
    return None


def _has_heading(headers: list[str], *candidates: str) -> bool:
    """Return whether a report table has one of the expected columns.

    The four conferences do not use one shared vendor.  In particular, some
    label the athlete column "Student-Athlete" and the school column
    "Institution".  These are explicit column aliases, not fuzzy inference
    from row text.
    """

    header_keys = {_header_key(header) for header in headers}
    return any(_header_key(candidate) in header_keys for candidate in candidates)


def _embedded_report_url(soup: BeautifulSoup, document_url: str) -> str | None:
    """Choose the availability app, never a tracking iframe.

    The ACC page includes advertising iframes before its `embedded-app`.
    Fetching the first iframe made the importer inspect an ad response rather
    than the official report shell.  Prefer the explicitly named report frame,
    then accept only an iframe whose source itself identifies a report.
    """

    frames = soup.find_all("iframe", src=True)
    candidates = [
        frame
        for frame in frames
        if frame.get("id") == "embedded-app"
        or any(token in str(frame["src"]).lower() for token in ("availability", "injury", "report", "confinj"))
    ]
    if not candidates:
        return None
    target = urljoin(document_url, str(candidates[0]["src"]))
    if urlparse(target).hostname and urlparse(target).hostname.endswith(".safelinks.protection.outlook.com"):
        linked = parse_qs(urlparse(target).query).get("url", [None])[0]
        if linked and urlparse(linked).hostname == "app.hdintelligence.com":
            target = linked
    return target


def _rendered_report_frame(page: Any) -> Any:
    """Return one public report iframe, preferring the dedicated app frame.

    Conference pages also embed analytics and advertising frames.  Passing a
    locator that matches more than one iframe to ``content_frame`` triggers
    Playwright's strict-mode exception, so the browser fallback must always
    resolve a single, explicitly selected frame.
    """

    embedded_app = page.locator("iframe#embedded-app")
    if embedded_app.count() > 0:
        return embedded_app.first
    return page.locator(
        "iframe[src*='availability'], iframe[src*='injury'], "
        "iframe[src*='report'], iframe[src*='confinj']"
    ).first


def _parse_grouped_report_cards(soup: BeautifulSoup, *, conference: str, source_url: str) -> list[dict[str, str | None]]:
    """Read the public HDI card layout by team/status headings, not CSS colors.

    Each card needs a dated Games heading, exactly one team heading, an explicit
    status group and jersey-labelled athletes. Unrelated articles are not data.
    """
    athlete = re.compile(r"^([A-Z]{1,5})\s+#\d+\s+(.+)$")
    statuses = {"OUT", "DOUBTFUL", "QUESTIONABLE", "PROBABLE", "AVAILABLE", "FULL", "TBD", "OUT FOR SEASON", "SUSPENDED", "INACTIVE", "NOT AVAILABLE"}
    rows = []
    ignored_logos = {"", "team logo", "conference logo", "conference", "sec logo", "acc football", "b1g football", "network", "football"}

    def players_in(element):
        # Vendors split position, jersey and name into separate elements. Only
        # the smallest complete row is an athlete; never combine adjacent rows.
        result = []
        for child in element.find_all(["div", "li", "p"]):
            match = athlete.fullmatch(child.get_text(" ", strip=True))
            if match and not any(athlete.fullmatch(nested.get_text(" ", strip=True)) for nested in child.find_all(["div", "li", "p"])):
                result.append(match)
        return result

    def report_date(element):
        heading = element.find_previous("h1")
        text = heading.get_text(" ", strip=True) if heading else ""
        match = re.fullmatch(r"Games (?:on|of) (.+)", text)
        if not match:
            return None
        try:
            return datetime.strptime(match.group(1), "%B %d, %Y").date().isoformat()
        except ValueError:
            # Big Ten groups Friday and Saturday under one range heading.
            year = re.search(r", (\d{4})$", text)
            parent = element.parent
            while parent and parent.name not in {"body", "html"}:
                footer = re.search(r"(?:Friday|Saturday|Thursday|Sunday), ([A-Z][a-z]+ \d{1,2}) \|", parent.get_text(" ", strip=True))
                if footer and year:
                    try:
                        return datetime.strptime(f"{footer.group(1)}, {year.group(1)}", "%B %d, %Y").date().isoformat()
                    except ValueError:
                        return None
                parent = parent.parent
            return None

    def team_marker(element):
        if element.name == "h3":
            return element.get_text(" ", strip=True).upper() not in statuses
        return element.name == "img" and element.get("alt", "").strip().lower() not in ignored_logos

    def append_groups(card, team_name, game_date):
        for label in card.find_all(string=lambda text: text.strip().upper() in statuses):
            status = label.strip().upper()
            group = label.parent
            while group is not card and group is not None:
                texts = list(group.stripped_strings)
                if sum(text.upper() in statuses for text in texts) != 1:
                    break
                players = players_in(group)
                if players:
                    for player in players:
                        rows.append({"player_name": player.group(2), "team_name": team_name,
                            "position": player.group(1), "status": status, "injury": None, "return_timeline": None,
                            "practice_level": None, "notes": None, "conference": conference,
                            "source_url": source_url, "game_date": game_date})
                    break
                group = group.parent

    markers = [element for element in soup.find_all(["h3", "img"]) if team_marker(element)]
    for heading in markers:
        game_date = report_date(heading)
        if not game_date:
            continue
        team_name = heading.get("alt", "").strip() if heading.name == "img" else heading.get_text(" ", strip=True)
        card = heading.parent
        while card and sum(team_marker(child) for child in card.find_all(["h3", "img"])) == 1:
            if players_in(card):
                break
            card = card.parent
        if card and sum(team_marker(child) for child in card.find_all(["h3", "img"])) == 1:
            append_groups(card, team_name, game_date)
    if not rows and conference == "BIG12":
        # Big 12 exposes generic team-logo labels, so there is no textual team
        # identity to parse. The importer must resolve a UNIQUE exact name +
        # position in this conference with a real game on this explicit date.
        for heading in soup.find_all("h1"):
            card = heading.parent
            game_date = report_date(heading.find_next())
            if game_date:
                append_groups(card, None, game_date)
    return rows


def parse_report_document(
    html: str,
    *,
    conference: str,
    source_url: str,
) -> list[dict[str, str | None]]:
    """Parse a public, rendered availability table into neutral source rows.

    Conference vendors change CSS frequently, so parsing is based on explicit
    table headings.  A document without a recognised table is *not* treated as
    an empty report: that would incorrectly clear or overwrite player status.
    """

    soup = BeautifulSoup(html, "html.parser")
    rows: list[dict[str, str | None]] = []
    for table in soup.find_all("table"):
        header_row = table.find("tr")
        if header_row is None:
            continue
        headers = [cell.get_text(" ", strip=True) for cell in header_row.find_all(["th", "td"])]
        if not _has_heading(headers, "player", "player name", "student athlete", "student-athlete", "name"):
            continue
        if not _has_heading(headers, "status", "availability", "availability status", "game status"):
            continue
        for tr in table.find_all("tr")[1:]:
            values = [cell.get_text(" ", strip=True) for cell in tr.find_all(["td", "th"])]
            if len(values) != len(headers):
                continue
            player_name = _field(headers, values, "player", "player name", "student athlete", "student-athlete", "name")
            status = _field(headers, values, "status", "availability", "availability status", "game status")
            team_name = _field(headers, values, "team", "school", "institution")
            if not player_name or not status or not team_name:
                continue
            rows.append(
                {
                    "player_name": player_name,
                    "team_name": team_name,
                    "position": _field(headers, values, "position", "pos"),
                    "status": status,
                    "injury": _field(headers, values, "injury", "injury type"),
                    "return_timeline": _field(headers, values, "return", "timeline", "expected return"),
                    "practice_level": _field(headers, values, "practice", "participation"),
                    "notes": _field(headers, values, "notes", "comment", "details"),
                    "conference": conference,
                    "source_url": source_url,
                }
            )
    if not rows:
        rows = _parse_grouped_report_cards(soup, conference=conference, source_url=source_url)
    report_text = soup.get_text(" ", strip=True).lower()
    no_report_markers = ("no games until", "no games scheduled", "no reports available")
    if not rows and not any(marker in report_text for marker in no_report_markers):
        raise ConferenceReportUnavailable(
            f"{conference} report did not contain a readable public availability table"
        )
    return rows


class ConferenceAvailabilityReportClient:
    """Fetch official pages and, when present, their public embedded report."""

    def __init__(
        self,
        timeout_seconds: float = 20.0,
        rendered_document: Callable[[ConferenceReportSource], str] | None = None,
    ) -> None:
        self.timeout_seconds = timeout_seconds
        self.rendered_document = rendered_document

    def _render_public_document(self, source: ConferenceReportSource) -> str:
        """Render only the public conference page when static HTML is a JS shell.

        The reports are published inside public embedded apps.  We intentionally
        do not call a private or undocumented vendor API; Chromium loads the
        same official page a manager sees and returns the rendered report DOM.
        """

        if self.rendered_document is not None:
            return self.rendered_document(source)
        try:
            from playwright.sync_api import TimeoutError as PlaywrightTimeoutError
            from playwright.sync_api import sync_playwright
        except ImportError as exc:  # pragma: no cover - image configuration guard
            raise ConferenceReportUnavailable("browser renderer dependency is unavailable") from exc

        executable_path = os.getenv("PLAYWRIGHT_CHROMIUM_EXECUTABLE") or None
        try:
            with sync_playwright() as playwright:
                browser = playwright.chromium.launch(
                    headless=True,
                    executable_path=executable_path,
                    args=["--no-sandbox", "--disable-dev-shm-usage"],
                )
                try:
                    page = browser.new_page()
                    page.goto(source.url, wait_until="domcontentloaded", timeout=int(self.timeout_seconds * 1000))
                    embedded_url = _embedded_report_url(BeautifulSoup(page.content(), "html.parser"), source.url)
                    if embedded_url and urlparse(embedded_url).hostname == "app.hdintelligence.com":
                        # Read the exact public document linked by the official
                        # page, avoiding wrapper redirects and archive frames.
                        page.goto(embedded_url, wait_until="domcontentloaded", timeout=int(self.timeout_seconds * 1000))
                    iframe = _rendered_report_frame(page)
                    has_frame = iframe.count() > 0
                    # Playwright 1.56+ exposes ``content_frame`` as a
                    # FrameLocator property (not a callable Frame).  Calling
                    # it caused every JS-hosted conference report to fail
                    # before parsing, silently reducing the daily audit to
                    # zero usable sources.
                    frame = iframe.content_frame if has_frame else page
                    try:
                        frame.locator("table").or_(frame.get_by_text(re.compile(r"^(?:[A-Z]{1,5}\s+#\d+\s+|#\d+$)"))).or_(
                            frame.get_by_text(re.compile(r"no games until|no games scheduled|no reports available", re.I))
                        ).first.wait_for(
                            state="attached", timeout=int(self.timeout_seconds * 1000)
                        )
                    except PlaywrightTimeoutError:
                        # In the offseason the public app renders its explicit
                        # no-games state instead of a table.  Return that DOM so
                        # `parse_report_document` can distinguish it from a
                        # broken page without inventing availability statuses.
                        pass
                    # FrameLocator has no ``content`` method.  Reading the
                    # public frame's rendered HTML preserves explicit team,
                    # status and date semantics across table/card layouts.
                    return frame.locator("html").inner_html()
                finally:
                    browser.close()
        except ConferenceReportUnavailable:
            raise
        except Exception as exc:  # pragma: no cover - browser/platform failures
            raise ConferenceReportUnavailable(f"browser renderer failed: {exc}") from exc

    def get_rows(self, source: ConferenceReportSource) -> list[dict[str, str | None]]:
        headers = {
            "User-Agent": "CollegeFootballFantasy/1.0 availability-sync",
            "Accept": "text/html,application/xhtml+xml",
        }
        with httpx.Client(timeout=self.timeout_seconds, follow_redirects=True, headers=headers) as client:
            response = client.get(source.url)
            response.raise_for_status()
            document_url = str(response.url)
            official_source_url = document_url
            html = response.text
            soup = BeautifulSoup(html, "html.parser")
            embedded_url = _embedded_report_url(soup, document_url)
            if embedded_url is not None:
                embedded = client.get(embedded_url, headers={"Referer": document_url})
                embedded.raise_for_status()
                html = embedded.text
                document_url = str(embedded.url)
        try:
            return parse_report_document(
                html,
                conference=source.conference,
                # Keep the user-visible provenance on the conference site even
                # when that page embeds a public report document from its vendor.
                source_url=official_source_url,
            )
        except ConferenceReportUnavailable as static_error:
            rendered_html = self._render_public_document(source)
            try:
                return parse_report_document(
                    rendered_html,
                    conference=source.conference,
                    source_url=official_source_url,
                )
            except ConferenceReportUnavailable as rendered_error:
                raise ConferenceReportUnavailable(
                    f"static document unreadable ({static_error}); rendered document unreadable ({rendered_error})"
                ) from rendered_error
