import argparse
import csv
import io
import json
import re
import time
import urllib.request
from datetime import datetime, timezone
from html.parser import HTMLParser


CONF_LABELS = {
    "Southeastern (SEC)": "SEC",
    "Big Ten (B1G)": "Big Ten",
    "Atlantic Coast (ACC)": "ACC",
    "Big 12": "Big 12",
}

ROLE_RE = re.compile(
    r"(starter|co-starter|backup|2nd|second|3rd|third|split|rotation|reserve|lead)",
    re.IGNORECASE,
)
CLASS_RE = re.compile(r"^(RS\s)?(FR|SO|JR|SR)$")
NAME_RE = re.compile(r"^[A-Za-z][A-Za-z\-.' ]* [A-Za-z][A-Za-z\-.' ]*$")

ORDERED_POSITIONS = ["QB", "RB", "WR", "TE", "K"]


def normalize_position(position: str) -> str | None:
    upper = re.sub(r"\s+", " ", position.strip().upper())
    if upper.startswith("QB"):
        return "QB"
    if upper.startswith(("RB", "HB", "TB", "FB")):
        return "RB"
    if upper.startswith(("WR", "SLOT")) or "WIDE" in upper:
        return "WR"
    if upper.startswith("TE"):
        return "TE"
    if upper in {"K", "PK", "K/P", "KICKER"} or upper.startswith("KICKER"):
        return "K"
    return None


class DepthChartIndexParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.div_stack: list[dict[str, object]] = []
        self.in_h3 = False
        self.h3_text = ""
        self.conf_links: dict[str, list[str]] = {conf: [] for conf in CONF_LABELS.values()}

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attrs_dict = dict(attrs)
        if tag == "div":
            is_column = "class" in attrs_dict and "elementor-column" in attrs_dict["class"]
            self.div_stack.append({"is_column": is_column, "conf": None})
        elif tag == "h3":
            self.in_h3 = True
            self.h3_text = ""
        elif tag == "a":
            conf = self.current_conf()
            if conf:
                href = attrs_dict.get("href")
                if href and "cfbdepth.com" in href:
                    self._add_link(conf, href)

    def handle_endtag(self, tag: str) -> None:
        if tag == "div" and self.div_stack:
            self.div_stack.pop()
        elif tag == "h3" and self.in_h3:
            text = self.h3_text.strip()
            conf = CONF_LABELS.get(text)
            if conf:
                for entry in reversed(self.div_stack):
                    if entry["is_column"]:
                        entry["conf"] = conf
                        break
            self.in_h3 = False
            self.h3_text = ""

    def handle_data(self, data: str) -> None:
        if self.in_h3:
            self.h3_text += data

    def current_conf(self) -> str | None:
        for entry in reversed(self.div_stack):
            if entry["is_column"] and entry["conf"]:
                return str(entry["conf"])
        return None

    def _add_link(self, conf: str, href: str) -> None:
        href = href.split("?")[0].rstrip("/")
        for bad in ("/depth-charts", "/category/", "/wp-content/"):
            if bad in href:
                return
        if href not in self.conf_links[conf]:
            self.conf_links[conf].append(href)


def fetch_text(url: str, *, timeout: float, retries: int, retry_delay: float) -> str:
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    for attempt in range(retries):
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                return resp.read().decode("utf-8", errors="ignore")
        except Exception:
            if attempt == retries - 1:
                raise
            time.sleep(retry_delay)


def fetch_csv(url: str, *, timeout: float, retries: int, retry_delay: float) -> list[list[str]]:
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    for attempt in range(retries):
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                data = resp.read().decode("utf-8", errors="ignore")
            return list(csv.reader(io.StringIO(data)))
        except Exception:
            if attempt == retries - 1:
                raise
            time.sleep(retry_delay)
    return []


def extract_sheet_id(team_html: str) -> str | None:
    match = re.search(r"sheet\?id=([^&\"]+)(?:&amp;|&)gid=0", team_html)
    if match:
        return match.group(1)
    match = re.search(r"spreadsheets/d/e/([^/]+)/", team_html)
    if match:
        return match.group(1)
    return None


def _find_class_and_name(row: list[str], start_idx: int | None) -> tuple[str | None, str | None]:
    indices = range(start_idx - 1, -1, -1) if start_idx is not None else range(len(row) - 1, -1, -1)
    for class_idx in indices:
        cell = row[class_idx].strip()
        if not CLASS_RE.match(cell):
            continue
        for name_idx in range(class_idx - 1, max(class_idx - 15, -1), -1):
            name_cell = row[name_idx].strip()
            if not name_cell:
                continue
            if name_cell.lower() in {"starter", "backup", "split", "rotation"}:
                continue
            if CLASS_RE.match(name_cell):
                continue
            if NAME_RE.match(name_cell):
                return name_cell, cell
    return None, None


def extract_player(row: list[str]) -> dict[str, str] | None:
    role_idx = None
    role = ""
    for idx, cell in enumerate(row):
        if cell and ROLE_RE.search(cell):
            role_idx = idx
            role = cell.strip()
            break

    name, player_class = _find_class_and_name(row, role_idx)
    if not name or not player_class:
        return None

    if not role:
        role = "Unlisted"

    return {"name": name, "class": player_class, "role": role}


def parse_depth_chart(rows: list[list[str]]) -> dict[str, list[dict[str, str]]]:
    positions: dict[str, list[dict[str, str]]] = {}
    current_position: str | None = None

    for row in rows:
        if not row:
            continue
        if row[0].strip() and any("STARTER" in cell for cell in row):
            raw_position = row[0].strip()
            current_position = normalize_position(raw_position)
            if current_position:
                positions.setdefault(current_position, [])
            continue
        if current_position and row[0].strip().upper().startswith("FUTURE ADDITIONS"):
            current_position = None
            continue
        if not current_position:
            continue

        player = extract_player(row)
        if player:
            existing = positions[current_position]
            if all(p["name"] != player["name"] for p in existing):
                existing.append(player)

    return positions


def slugify(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")


def format_depth(
    conf_teams: dict[str, list[str]],
    delay: float,
    timeout: float,
    retries: int,
    retry_delay: float,
) -> tuple[str, list[dict[str, object]]]:
    output_lines: list[str] = []
    players_out: list[dict[str, object]] = []
    for conf, team_links in conf_teams.items():
        output_lines.append(f"## {conf}")
        for link in team_links:
            team_slug = link.rstrip("/").split("/")[-1]
            team_display = team_slug.replace("-", " ").upper()
            team_page = link if link.startswith("http") else f"https://{link}"
            try:
                html = fetch_text(team_page, timeout=timeout, retries=retries, retry_delay=retry_delay)
            except Exception:
                output_lines.append(f"### {team_slug}\n- not sure (team page fetch failed)")
                continue

            sheet_id = extract_sheet_id(html)
            if not sheet_id:
                output_lines.append(f"### {team_slug}\n- not sure (depth chart sheet not found)")
                continue

            csv_url = (
                f"https://docs.google.com/spreadsheets/d/e/{sheet_id}/pub"
                f"?gid=0&single=true&output=csv"
            )
            try:
                rows = fetch_csv(csv_url, timeout=timeout, retries=retries, retry_delay=retry_delay)
            except Exception:
                output_lines.append(f"### {team_slug}\n- not sure (depth chart sheet fetch failed)")
                continue

            positions = parse_depth_chart(rows)
            if not positions:
                output_lines.append(f"### {team_slug}\n- not sure (no positions parsed)")
                continue

            output_lines.append(f"### {team_slug}")
            for position in ORDERED_POSITIONS:
                players = positions.get(position, [])
                if not players:
                    output_lines.append(f"- {position}: not sure")
                    continue

                trimmed = players[:3]
                formatted_players = []
                for depth, player in enumerate(trimmed, start=1):
                    formatted_players.append(
                        f"{depth}. {player['name']} ({player['class']}) [{player['role']}]"
                    )
                    players_out.append(
                        {
                            "id": slugify(f"{conf}-{team_slug}-{position}-{depth}"),
                            "name": player["name"],
                            "classYear": player["class"],
                            "role": player["role"],
                            "position": position,
                            "team": team_display,
                            "teamSlug": team_slug,
                            "conference": conf,
                            "depth": depth,
                        }
                    )
                output_lines.append(f"- {position}: " + "; ".join(formatted_players))
            output_lines.append("")
            time.sleep(delay)
    return "\n".join(output_lines).strip(), players_out


def main() -> None:
    parser = argparse.ArgumentParser(description="Scrape Power Four depth charts from cfbdepth.com")
    parser.add_argument(
        "--output",
        default="scripts/cfbdepth_power4_depth_charts.md",
        help="Output markdown file",
    )
    parser.add_argument(
        "--output-json",
        default="",
        help="Optional JSON output path for player data",
    )
    parser.add_argument("--delay", type=float, default=0.1, help="Delay between team requests")
    parser.add_argument("--timeout", type=float, default=15.0, help="Network timeout in seconds")
    parser.add_argument("--retries", type=int, default=2, help="Retry count for network fetches")
    parser.add_argument("--retry-delay", type=float, default=0.6, help="Delay between retries")
    parser.add_argument(
        "--conferences",
        default="",
        help="Comma-separated subset: SEC,Big Ten,ACC,Big 12",
    )
    parser.add_argument(
        "--max-teams",
        type=int,
        default=0,
        help="Limit teams per conference for debugging",
    )
    args = parser.parse_args()

    index_html = fetch_text(
        "https://www.cfbdepth.com/depth-charts/",
        timeout=args.timeout,
        retries=args.retries,
        retry_delay=args.retry_delay,
    )
    parser_index = DepthChartIndexParser()
    parser_index.feed(index_html)

    conf_links = parser_index.conf_links
    if args.conferences:
        requested = {conf.strip() for conf in args.conferences.split(",") if conf.strip()}
        conf_links = {conf: links for conf, links in conf_links.items() if conf in requested}
    if args.max_teams > 0:
        conf_links = {conf: links[: args.max_teams] for conf, links in conf_links.items()}

    output, players_out = format_depth(
        conf_links,
        delay=args.delay,
        timeout=args.timeout,
        retries=args.retries,
        retry_delay=args.retry_delay,
    )
    with open(args.output, "w", encoding="utf-8") as f:
        f.write(output)

    if args.output_json:
        payload = {
            "source": "cfbdepth.com",
            "generatedAt": datetime.now(timezone.utc).isoformat(),
            "players": players_out,
        }
        with open(args.output_json, "w", encoding="utf-8") as f:
            json.dump(payload, f, indent=2)

    print(f"Wrote {args.output}")
    if args.output_json:
        print(f"Wrote {args.output_json}")


if __name__ == "__main__":
    main()
