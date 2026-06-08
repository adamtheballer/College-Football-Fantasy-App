from api.app.api.routes.leagues import _apply_adp_formula, _apply_projection_name_overrides


def test_projection_overrides_raise_top_tight_ends_and_mario_craver_and_cap_calvin_russell():
    rows = [
        {"name": "Trey'Dez Green", "position": "TE", "projected_fantasy_points": 179.8},
        {"name": "Terrance Carter Jr.", "position": "TE", "projected_fantasy_points": 143.5},
        {"name": "Jamari Johnson", "position": "TE", "projected_fantasy_points": 131.2},
        {"name": "DJ Vonnahme", "position": "TE", "projected_fantasy_points": 151.2},
        {"name": "Luke Hasz", "position": "TE", "projected_fantasy_points": 149.2},
        {"name": "Mario Craver", "position": "WR", "projected_fantasy_points": 241.0},
        {"name": "Calvin Russell 3", "position": "WR", "projected_fantasy_points": 213.9},
    ]

    _apply_projection_name_overrides(rows)

    projection_by_name = {row["name"]: row["projected_fantasy_points"] for row in rows}
    assert projection_by_name["Trey'Dez Green"] == 252.0
    assert projection_by_name["Terrance Carter Jr."] == 238.0
    assert projection_by_name["Jamari Johnson"] == 228.0
    assert projection_by_name["DJ Vonnahme"] == 222.0
    assert projection_by_name["Luke Hasz"] == 216.0
    assert projection_by_name["Mario Craver"] == 258.0
    assert projection_by_name["Calvin Russell 3"] == 190.0


def test_draft_value_formula_keeps_requested_top_board_order():
    rows = [
        {"name": "Jeremiah Smith", "position": "WR", "projected_fantasy_points": 342.8},
        {"name": "Ahmad Hardy", "position": "RB", "projected_fantasy_points": 347.4},
        {"name": "Kewan Lacy", "position": "RB", "projected_fantasy_points": 338.0},
        {"name": "Cam Cook", "position": "RB", "projected_fantasy_points": 332.0},
        {"name": "LJ Martin", "position": "RB", "projected_fantasy_points": 327.4},
        {"name": "Malachi Toney", "position": "WR", "projected_fantasy_points": 323.0},
        {"name": "Trinidad Chambliss", "position": "QB", "projected_fantasy_points": 414.0},
        {"name": "Mark Fletcher Jr.", "position": "RB", "projected_fantasy_points": 317.0},
        {"name": "Devon Dampier", "position": "QB", "projected_fantasy_points": 408.5},
        {"name": "Cam Coleman", "position": "WR", "projected_fantasy_points": 311.0},
        {"name": "Arch Manning", "position": "QB", "projected_fantasy_points": 404.0},
        {"name": "Extra RB", "position": "RB", "projected_fantasy_points": 390.0},
        {"name": "Extra WR", "position": "WR", "projected_fantasy_points": 390.0},
    ]

    _apply_adp_formula(rows)

    ordered_names = [row["name"] for row in sorted(rows, key=lambda row: row["adp"])[:11]]
    assert ordered_names == [
        "Ahmad Hardy",
        "Jeremiah Smith",
        "Kewan Lacy",
        "Cam Cook",
        "LJ Martin",
        "Malachi Toney",
        "Trinidad Chambliss",
        "Mark Fletcher Jr.",
        "Devon Dampier",
        "Cam Coleman",
        "Arch Manning",
    ]


def test_draft_value_formula_places_top_tight_ends_after_early_rounds():
    rows = [
        {"name": f"QB {index}", "position": "QB", "projected_fantasy_points": 420.0 - index * 5}
        for index in range(12)
    ]
    rows += [
        {"name": f"RB {index}", "position": "RB", "projected_fantasy_points": 350.0 - index * 4}
        for index in range(20)
    ]
    rows += [
        {"name": f"WR {index}", "position": "WR", "projected_fantasy_points": 340.0 - index * 4}
        for index in range(20)
    ]
    rows += [
        {"name": "Trey'Dez Green", "position": "TE", "projected_fantasy_points": 179.8},
        {"name": "Terrance Carter Jr.", "position": "TE", "projected_fantasy_points": 143.5},
        {"name": "Jamari Johnson", "position": "TE", "projected_fantasy_points": 131.2},
        {"name": "DJ Vonnahme", "position": "TE", "projected_fantasy_points": 151.2},
        {"name": "Luke Hasz", "position": "TE", "projected_fantasy_points": 149.2},
        {"name": "Replacement TE", "position": "TE", "projected_fantasy_points": 135.0},
    ]

    _apply_projection_name_overrides(rows)
    _apply_adp_formula(rows)

    top_te_adps = sorted(
        float(row["adp"])
        for row in rows
        if row["name"] in {"Trey'Dez Green", "Terrance Carter Jr.", "Jamari Johnson", "DJ Vonnahme", "Luke Hasz"}
    )
    assert len(top_te_adps) == 5
    assert min(top_te_adps) >= 25
    assert min(top_te_adps) <= 45
    assert max(top_te_adps) <= 65


def test_draft_value_formula_lifts_mid_tier_tight_ends():
    rows = [
        {"name": f"QB {index}", "position": "QB", "projected_fantasy_points": 420.0 - index * 4}
        for index in range(18)
    ]
    rows += [
        {"name": f"RB {index}", "position": "RB", "projected_fantasy_points": 350.0 - index * 3}
        for index in range(45)
    ]
    rows += [
        {"name": f"WR {index}", "position": "WR", "projected_fantasy_points": 340.0 - index * 3}
        for index in range(45)
    ]
    rows += [
        {"name": f"TE {index}", "position": "TE", "projected_fantasy_points": 210.0 - index * 2}
        for index in range(30)
    ]

    _apply_adp_formula(rows)

    mid_tier_te_adps = sorted(
        float(row["adp"])
        for row in rows
        if row["position"] == "TE" and 6 <= int(row["name"].split()[-1]) + 1 <= 30
    )
    assert mid_tier_te_adps
    assert max(mid_tier_te_adps[:10]) < 140
