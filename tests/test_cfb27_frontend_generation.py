from scripts.generate_cfb27_frontend import load_rating_rows, render_frontend_module


def test_frontend_cfb27_ratings_are_generated_from_backend_source():
    expected = render_frontend_module(load_rating_rows())

    with open("web/client/lib/cfb27Ratings.ts", encoding="utf-8") as frontend_file:
        assert frontend_file.read() == expected
