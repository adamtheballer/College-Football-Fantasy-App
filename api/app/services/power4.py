from __future__ import annotations

import re


def normalize_school(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", name.lower())


CANONICAL_POWER4_TEAMS: dict[str, tuple[str, ...]] = {
    "SEC": (
        "Alabama",
        "Arkansas",
        "Auburn",
        "Florida",
        "Georgia",
        "Kentucky",
        "LSU",
        "Mississippi State",
        "Missouri",
        "Oklahoma",
        "Ole Miss",
        "South Carolina",
        "Tennessee",
        "Texas",
        "Texas A&M",
        "Vanderbilt",
    ),
    "BIG10": (
        "Illinois",
        "Indiana",
        "Iowa",
        "Maryland",
        "Michigan",
        "Michigan State",
        "Minnesota",
        "Nebraska",
        "Northwestern",
        "Ohio State",
        "Oregon",
        "Penn State",
        "Purdue",
        "Rutgers",
        "UCLA",
        "USC",
        "Washington",
        "Wisconsin",
    ),
    "BIG12": (
        "Arizona",
        "Arizona State",
        "Baylor",
        "BYU",
        "Cincinnati",
        "Colorado",
        "Houston",
        "Iowa State",
        "Kansas",
        "Kansas State",
        "Oklahoma State",
        "TCU",
        "Texas Tech",
        "UCF",
        "Utah",
        "West Virginia",
    ),
    "ACC": (
        "Boston College",
        "California",
        "Clemson",
        "Duke",
        "Florida State",
        "Georgia Tech",
        "Louisville",
        "Miami",
        "NC State",
        "North Carolina",
        "Pittsburgh",
        "SMU",
        "Stanford",
        "Syracuse",
        "Virginia",
        "Virginia Tech",
        "Wake Forest",
    ),
}

SCHOOL_ALIASES: dict[str, str] = {
    "Louisiana State": "LSU",
    "Mississippi": "Ole Miss",
    "Texas A and M": "Texas A&M",
    "Southern California": "USC",
    "Brigham Young": "BYU",
    "Central Florida": "UCF",
    "Cal": "California",
    "Miami (FL)": "Miami",
    "Pitt": "Pittsburgh",
    "Southern Methodist": "SMU",
    "Bama": "Alabama",
    "Vandy": "Vanderbilt",
    "Mizzou": "Missouri",
    "Miss St": "Mississippi State",
    "Miss State": "Mississippi State",
    "Mississippi St": "Mississippi State",
    "Aub": "Auburn",
    "UGA": "Georgia",
    "Tenn": "Tennessee",
    "UK": "Kentucky",
    "TAMU": "Texas A&M",
    "A&M": "Texas A&M",
    "Aggies": "Texas A&M",
    "UoSC": "South Carolina",
    "USCar": "South Carolina",
    "OleMiss": "Ole Miss",
    "Penn St": "Penn State",
    "PSU": "Penn State",
    "Ohio St": "Ohio State",
    "OSU (Big Ten)": "Ohio State",
    "Mich St": "Michigan State",
    "MSU (Big Ten)": "Michigan State",
    "NW": "Northwestern",
    "Rut": "Rutgers",
    "ASU": "Arizona State",
    "Iowa St": "Iowa State",
    "KSU": "Kansas State",
    "KU": "Kansas",
    "Okla St": "Oklahoma State",
    "OSU (Big 12)": "Oklahoma State",
    "TTU": "Texas Tech",
    "WVU": "West Virginia",
    "FSU": "Florida State",
    "GT": "Georgia Tech",
    "NCSU": "NC State",
    "UNC": "North Carolina",
    "VT": "Virginia Tech",
    "BC": "Boston College",
}

NORMALIZED_TO_CONFERENCE: dict[str, str] = {}
NORMALIZED_TO_CANONICAL: dict[str, str] = {}
for conference, schools in CANONICAL_POWER4_TEAMS.items():
    for school in schools:
        normalized = normalize_school(school)
        NORMALIZED_TO_CONFERENCE[normalized] = conference
        NORMALIZED_TO_CANONICAL[normalized] = school
for alias, canonical in SCHOOL_ALIASES.items():
    normalized = normalize_school(alias)
    canonical_normalized = normalize_school(canonical)
    NORMALIZED_TO_CONFERENCE[normalized] = NORMALIZED_TO_CONFERENCE[canonical_normalized]
    NORMALIZED_TO_CANONICAL[normalized] = canonical


def resolve_power4_school(name: str) -> str | None:
    normalized = normalize_school(name)
    if not normalized:
        return None
    direct = NORMALIZED_TO_CANONICAL.get(normalized)
    if direct:
        return direct
    collapsed = (
        normalized.replace("university", "")
        .replace("college", "")
        .replace("athletics", "")
        .strip()
    )
    if collapsed:
        return NORMALIZED_TO_CANONICAL.get(collapsed)
    return None


def canonical_school_name(name: str) -> str | None:
    return resolve_power4_school(name)


def conference_for_school(name: str) -> str | None:
    normalized = normalize_school(name)
    conference = NORMALIZED_TO_CONFERENCE.get(normalized)
    if conference:
        return conference
    canonical = resolve_power4_school(name)
    if not canonical:
        return None
    return NORMALIZED_TO_CONFERENCE.get(normalize_school(canonical))


def is_power4_school(name: str) -> bool:
    return conference_for_school(name) is not None


def list_power4_teams(conference: str | None = None) -> list[str]:
    if conference:
        conference_key = conference.upper().replace(" ", "")
        if conference_key not in CANONICAL_POWER4_TEAMS:
            return []
        return sorted(CANONICAL_POWER4_TEAMS[conference_key])
    all_teams: list[str] = []
    for teams in CANONICAL_POWER4_TEAMS.values():
        all_teams.extend(teams)
    return sorted(all_teams)
