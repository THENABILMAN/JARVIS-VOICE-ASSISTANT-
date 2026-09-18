# JARVIS

**Created by Nabil**

JARVIS is a voice-first personal AI assistant built with Python, LiveKit, Gemini realtime voice, browser automation, Spotify, web search, and persistent memory.

## Architecture

```text
User voice
   |
Next.js frontend
   |
LiveKit realtime room
   |
Python AgentServer + Gemini
   |
Tools: Browser | Spotify | Tavily | Mem0
```

The frontend provides the voice interface and LiveKit connection. The Python agent handles conversation, memory, tool selection, browser control, Spotify playback, and web search. The user profile is loaded from `src/user_profile.md`, while conversational memories are stored in Mem0.

## Features

- Realtime voice conversations
- Persistent user profile and long-term memory
- Dynamic name and preference recall
- Chrome and Playwright browser automation
- Page inspection, reading, clicking, typing, scrolling, and screenshots
- Consequential-action confirmation
- Spotify OAuth, track search, and playback
- Tavily web search
- LiveKit and Next.js frontend
- Python tests and Ruff linting

## Project Structure

```text
src/
├── agent.py          # LiveKit agent entry point
├── browser.py        # Playwright browser manager
├── memory.py         # Mem0 memory service
├── prompts.py        # Jarvis behavior and tool rules
├── spotify.py        # Spotify integration
├── tavily.py         # Web search integration
├── tools.py          # Agent tools
└── user_profile.md   # Stable user profile

frontend/             # Next.js and React voice interface
tests/                # Python tests
Dockerfile            # Agent deployment image
pyproject.toml        # Python dependencies and tooling
```

## Setup

Requirements: Python 3.10-3.14, `uv`, Node.js, `pnpm`, LiveKit, and Gemini credentials.

```powershell
uv sync
Copy-Item .env.example .env.local
cd frontend
pnpm install
```

Configure `.env.local` with:

```dotenv
LIVEKIT_URL=
LIVEKIT_API_KEY=
LIVEKIT_API_SECRET=
SPOTIFY_CLIENT_ID=
SPOTIFY_CLIENT_SECRET=
TAVILY_API_KEY=
MEM0_API_KEY=
MEM0_USER_ID=
```

## Run

Start the agent:

```powershell
uv run python src/agent.py dev
```

Start the frontend in another terminal:

```powershell
cd frontend
pnpm dev
```

Then open `http://localhost:3000`.

## Test

```powershell
uv run pytest
uv run ruff check src tests
```

## License

Copyright (c) 2026 Nabil.

This project uses the MIT License. See [frontend/LICENSE](frontend/LICENSE).
