import pytest

from spotify import _spotify_search_query
from tools import (
    duckduckgo_search_url,
    parse_music_request,
    resolve_site_url,
    spotify_app_uri,
    spotify_search_uri,
    tavily_search_url,
)


def test_duckduckgo_search_url_encodes_query() -> None:
    assert (
        duckduckgo_search_url("  current weather in New York  ")
        == "https://duckduckgo.com/?q=current+weather+in+New+York"
    )


def test_duckduckgo_search_url_rejects_empty_query() -> None:
    with pytest.raises(ValueError, match="query cannot be empty"):
        duckduckgo_search_url("  ")


@pytest.mark.parametrize(
    ("destination", "expected"),
    [
        ("example.com", "https://example.com"),
        ("example.com/path", "https://example.com/path"),
        ("https://example.com/path", "https://example.com/path"),
    ],
)
def test_resolve_site_url(destination: str, expected: str) -> None:
    assert resolve_site_url(destination) == expected


def test_spotify_search_uri_encodes_song_query() -> None:
    assert spotify_search_uri("Daft Punk Around the World") == (
        "spotify:search:Daft%20Punk%20Around%20the%20World"
    )


def test_spotify_search_uri_rejects_empty_query() -> None:
    with pytest.raises(ValueError, match="song query cannot be empty"):
        spotify_search_uri("  ")


def test_spotify_app_uri() -> None:
    assert spotify_app_uri() == "spotify:"


def test_parse_music_request_separates_song_and_artist() -> None:
    assert parse_music_request("Purnota by Warfaze") == ("Purnota", "Warfaze")


def test_spotify_artist_only_search_is_not_a_track_title_search() -> None:
    assert _spotify_search_query("Habib Wahid", None) == "Habib Wahid"
    assert _spotify_search_query("Purnota", "Warfaze") == (
        'track:"Purnota" artist:"Warfaze"'
    )


@pytest.mark.parametrize(
    ("spoken_destination", "expected"),
    [
        ("Search for YouTube", "https://www.youtube.com"),
        ("Open YouTube", "https://www.youtube.com"),
    ],
)
def test_resolve_spoken_site_requests(
    spoken_destination: str, expected: str
) -> None:
    assert resolve_site_url(spoken_destination) == expected


def test_tavily_search_url() -> None:
    assert tavily_search_url("LiveKit agents") == "https://api.tavily.com/search"
