import asyncio
import os
import re
import shutil
import subprocess
import sys
from urllib.parse import quote, urlencode, urlparse

from livekit.agents import RunContext, function_tool
from livekit.agents.llm import ToolError

from browser import BrowserError, BrowserManager
from memory import Mem0Error, MemoryService
from spotify import SpotifyError
from spotify import connect as connect_spotify_account
from spotify import play as play_spotify
from tavily import TavilyError
from tavily import result_text as tavily_result_text
from tavily import search as tavily_search


def duckduckgo_search_url(query: str) -> str:
    query = query.strip()
    if not query:
        raise ValueError("The search query cannot be empty.")
    return f"https://duckduckgo.com/?{urlencode({'q': query})}"


def resolve_site_url(destination: str) -> str:
    """Turn a spoken site name, domain, or URL into a safe web URL."""
    destination = destination.strip()
    if not destination:
        raise ValueError("The destination cannot be empty.")

    destination = re.sub(
        r"^(?:search|open|go to)\s+(?:for\s+)?", "", destination, flags=re.I
    )
    known_sites = {
        "youtube": "https://www.youtube.com",
        "spotify": "https://open.spotify.com",
        "google": "https://www.google.com",
    }
    known_site = known_sites.get(destination.casefold())
    if known_site:
        return known_site

    parsed_destination = urlparse(destination)
    candidate = destination if parsed_destination.scheme else f"https://{destination}"
    parsed = urlparse(candidate)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise ValueError("Say a website name, domain, or complete http or https URL.")
    if parsed.username or parsed.password:
        raise ValueError("URLs containing embedded credentials are not allowed.")
    return candidate


def spotify_search_uri(song_query: str) -> str:
    song_query = song_query.strip()
    if not song_query:
        raise ValueError("The song query cannot be empty.")
    return f"spotify:search:{quote(song_query, safe='')}"


def spotify_app_uri() -> str:
    return "spotify:"


def parse_music_request(request: str) -> tuple[str, str | None]:
    request = request.strip()
    separator = request.casefold().find(" by ")
    if separator > 0:
        return request[:separator].strip(), request[separator + 4 :].strip()
    return request, None


def tavily_search_url(query: str) -> str:
    return "https://api.tavily.com/search"


def _chrome_executable() -> str | None:
    candidates = [
        shutil.which("chrome"),
        shutil.which("chrome.exe"),
        os.path.expandvars(r"%ProgramFiles%\Google\Chrome\Application\chrome.exe"),
        os.path.expandvars(r"%ProgramFiles(x86)%\Google\Chrome\Application\chrome.exe"),
        os.path.expandvars(r"%LocalAppData%\Google\Chrome\Application\chrome.exe"),
    ]
    return next((candidate for candidate in candidates if candidate and os.path.exists(candidate)), None)


class BrowserTools:
    def __init__(self, browser: BrowserManager) -> None:
        self.browser = browser
        self.memory = MemoryService()
        self._confirmed_target: str | None = None

    @property
    def tools(self) -> list:
        return [
            self.open_url,
            self.search_the_web,
            self.open_chrome,
            self.open_spotify,
            self.connect_spotify,
            self.play_music,
            self.remember_this,
            self.recall_memory,
            self.read_page,
            self.inspect_page,
            self.go_back,
            self.take_screenshot,
            self.click,
            self.confirm_browser_action,
            self.type_text,
            self.scroll,
            self.press_key,
        ]

    @function_tool()
    async def search_the_web(
        self,
        context: RunContext,
        query: str,
    ) -> dict[str, str]:
        """Search the web with Tavily and return concise sourced results.

        Use this for general web searches when no specific website was requested.

        Args:
            query: A concise DuckDuckGo search query containing all relevant context.
        """
        try:
            payload = await asyncio.to_thread(tavily_search, query)
            return {"query": query, "results": tavily_result_text(payload)}
        except (TavilyError, ValueError) as exc:
            raise ToolError(str(exc)) from exc

    @function_tool()
    async def open_chrome(self, context: RunContext, destination: str) -> dict[str, str]:
        """Open any requested website in the user's Chrome profile.

        Use this for requests such as "open YouTube", "open example.com", or
        "search the web for ..." when the user explicitly wants Chrome.
        """
        try:
            url = resolve_site_url(destination)
            executable = _chrome_executable()
            if executable is None:
                return await self.browser.open_url(url)
            subprocess.Popen([executable, url], close_fds=True)
            return {"browser": "Chrome", "url": url}
        except (BrowserError, OSError, ValueError) as exc:
            raise ToolError(f"I could not open {destination!r} in Chrome: {exc}") from exc

    @function_tool()
    async def open_url(self, context: RunContext, url: str) -> dict[str, str]:
        """Open a public website, domain, or complete URL directly in the browser.

        Prefer this over DuckDuckGo whenever the user names a website, service, domain,
        or specific destination. Site names such as Spotify, Discord, Chrome, and Brave
        are resolved to their web destinations automatically.

        Args:
            url: A website name, domain, or complete http or https URL.
        """
        try:
            return await self.browser.open_url(resolve_site_url(url))
        except (BrowserError, ValueError) as exc:
            raise ToolError(str(exc)) from exc

    @function_tool()
    async def play_music(self, context: RunContext, song: str) -> dict[str, str]:
        """Search Spotify and start the best matching song on an available device.

        Requires Spotify to be connected once with connect_spotify. The user must
        have Spotify open on at least one playback device.

        Args:
            song: The song title, artist, or both to search for.
        """
        try:
            return await asyncio.to_thread(play_spotify, song)
        except (SpotifyError, ValueError) as exc:
            raise ToolError(str(exc)) from exc

    @function_tool()
    async def connect_spotify(self, context: RunContext) -> str:
        """Connect the user's Spotify account through a browser OAuth window."""
        try:
            return await asyncio.to_thread(connect_spotify_account)
        except SpotifyError as exc:
            raise ToolError(str(exc)) from exc

    @function_tool()
    async def remember_this(self, context: RunContext, fact: str) -> str:
        """Save a user preference, identity detail, or fact to long-term memory.

        Args:
            fact: The preference, name, identity detail, or fact to remember.
        """
        try:
            await asyncio.to_thread(self.memory.remember, fact)
            return "I will remember that."
        except Mem0Error as exc:
            raise ToolError(str(exc)) from exc

    @function_tool()
    async def recall_memory(self, context: RunContext, query: str) -> str:
        """Search the user's long-term memories for relevant preferences or facts.

        Args:
            query: A concise description of the information to recall.
        """
        try:
            memories = await asyncio.to_thread(self.memory.recall, query)
            return self.memory.summarize(memories)
        except Mem0Error as exc:
            raise ToolError(str(exc)) from exc

    @function_tool()
    async def open_spotify(self, context: RunContext) -> dict[str, str]:
        """Launch the installed Spotify desktop app on Windows.

        Use this for requests such as "open Spotify". Use play_music when the user
        also asks for a song or artist.
        """
        if sys.platform != "win32":
            raise ToolError("Opening the Spotify desktop app is supported on Windows.")

        try:
            import os

            os.startfile(spotify_app_uri())  # type: ignore[attr-defined]
            return {"app": "Spotify", "opened": "true"}
        except OSError as exc:
            raise ToolError(
                "Spotify is not installed or Windows could not launch it."
            ) from exc

    @function_tool()
    async def read_page(self, context: RunContext) -> dict[str, str | bool]:
        """Read the visible text from the current browser page."""
        try:
            return await self.browser.read_page()
        except BrowserError as exc:
            raise ToolError(str(exc)) from exc

    @function_tool()
    async def inspect_page(self, context: RunContext) -> dict[str, object]:
        """Inspect the current page, including readable text and interactive element names.

        Use this before clicking or typing so you can choose a visible control by its
        returned name or role.
        """
        try:
            return await self.browser.inspect_page()
        except BrowserError as exc:
            raise ToolError(str(exc)) from exc

    @function_tool()
    async def go_back(self, context: RunContext) -> dict[str, str]:
        """Go back to the previous page in the agent-controlled browser."""
        try:
            return await self.browser.go_back()
        except BrowserError as exc:
            raise ToolError(str(exc)) from exc

    @function_tool()
    async def take_screenshot(self, context: RunContext) -> dict[str, str | int | bool]:
        """Capture the current browser page for diagnostics."""
        try:
            return await self.browser.take_screenshot()
        except BrowserError as exc:
            raise ToolError(str(exc)) from exc

    @function_tool()
    async def click(self, context: RunContext, target: str) -> dict[str, str]:
        """Click a visible control by its accessible name.

        Args:
            target: The visible or accessible name of the control to click.
        """
        if self._requires_confirmation(target):
            if self._confirmed_target != target.casefold():
                raise ToolError(
                    f"This action may be consequential. Ask the user to confirm clicking {target!r} before retrying."
                )
            self._confirmed_target = None

        try:
            return await self.browser.click(target)
        except BrowserError as exc:
            raise ToolError(str(exc)) from exc

    @function_tool()
    async def confirm_browser_action(self, context: RunContext, target: str) -> str:
        """Authorize one previously discussed consequential browser click.

        Call this only after the user explicitly confirms the exact action.

        Args:
            target: The exact accessible name of the control the user approved.
        """
        self._confirmed_target = target.casefold()
        return f"The user confirmed clicking {target!r}."

    @function_tool()
    async def type_text(
        self,
        context: RunContext,
        target: str,
        text: str,
    ) -> dict[str, str]:
        """Fill a visible text field by its label, placeholder, or accessible name.

        Args:
            target: The label, placeholder, or accessible name of the text field.
            text: The text to enter.
        """
        try:
            return await self.browser.type_text(target, text)
        except BrowserError as exc:
            raise ToolError(str(exc)) from exc

    @function_tool()
    async def scroll(self, context: RunContext, direction: str) -> dict[str, str]:
        """Scroll the current browser page up or down.

        Args:
            direction: Either 'up' or 'down'.
        """
        try:
            return await self.browser.scroll(direction)  # type: ignore[arg-type]
        except BrowserError as exc:
            raise ToolError(str(exc)) from exc

    @function_tool()
    async def press_key(self, context: RunContext, key: str) -> dict[str, str]:
        """Press a safe navigation key in the current browser page.

        Args:
            key: One of Enter, Escape, Tab, an arrow key, or Backspace.
        """
        try:
            return await self.browser.press_key(key)
        except BrowserError as exc:
            raise ToolError(str(exc)) from exc

    @staticmethod
    def _requires_confirmation(target: str) -> bool:
        risky_words = {
            "buy",
            "confirm",
            "delete",
            "purchase",
            "remove",
            "send",
            "submit",
        }
        return bool(risky_words.intersection(target.casefold().split()))
