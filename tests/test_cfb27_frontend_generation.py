import json

import pytest

from scripts.generate_cfb27_frontend import load_rating_rows, render_frontend_module


def test_frontend_cfb27_ratings_are_generated_from_backend_source():
    expected = render_frontend_module(load_rating_rows())

    with open("web/client/lib/cfb27Ratings.ts", encoding="utf-8") as frontend_file:
        assert frontend_file.read() == expected


def test_frontend_generator_rejects_a_board_rank_as_an_overall_rating(tmp_path):
    source_path = tmp_path / "ratings.json"
    source_path.write_text(
        json.dumps(
            [
                {
                    "rank": 33,
                    "name": "Example Receiver",
                    "school": "Ohio State",
                    "position": "WR",
                    "overall": 33,
                }
            ]
        ),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="expected 62-99"):
        load_rating_rows(source_path)
