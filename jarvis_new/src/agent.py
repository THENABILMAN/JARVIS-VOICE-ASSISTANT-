import asyncio
import re
from pathlib import Path

from dotenv import load_dotenv
from google.genai import types as genai_types
from livekit.agents import (
    Agent,
    AgentServer,
    AgentSession,
    JobContext,
    TurnHandlingOptions,
    cli,
    inference,
    room_io,
)
from livekit.agents.beta.tools import EndCallTool
from livekit.plugins import ai_coustics, google

from browser import BrowserManager
from memory import Mem0Error, MemoryService
from prompts import AGENT_INSTRUCTIONS
from tools import BrowserTools

load_dotenv(".env.local")

USER_PROFILE_FILE = Path(__file__).with_name("user_profile.md")


def load_user_profile() -> str:
    try:
        return USER_PROFILE_FILE.read_text(encoding="utf-8").strip()
    except OSError:
        return ""


def preferred_name_from_profile(profile: str) -> str:
    match = re.search(r"^\s*Preferred name:\s*(.+?)\s*$", profile, re.IGNORECASE | re.MULTILINE)
    return match.group(1).strip() if match else ""


class Assistant(Agent):
    def __init__(
        self,
        browser: BrowserManager | None = None,
        memory_context: str = "",
        profile_context: str = "",
    ) -> None:
        preferred_name = preferred_name_from_profile(profile_context)
        name_instruction = (
            f"The profile identifies the user's preferred name as {preferred_name}. "
            "When asked the user's name, answer with that value."
            if preferred_name
            else "The profile does not contain a preferred name; do not invent one."
        )
        self.browser = browser or BrowserManager(headless=True)
        self.browser_tools = BrowserTools(self.browser)
        self._end_call_tool = EndCallTool(
            extra_description=(
                "Only end the call after the user clearly says they are finished, "
                "says goodbye, or directly asks to end the call."
            ),
            end_instructions=(
                "Give Jarvis's brief, polite British-English farewell, then end the call."
            ),
        )
        super().__init__(
            # A Large Language Model (LLM) is your agent's brain, processing user input and generating a response
            # See all available models at https://docs.livekit.io/agents/models/llm/
            # llm=inference.LLM(model="google/gemma-4-31b-it"),
            llm=google.beta.realtime.RealtimeModel(
                model="gemini-3.1-flash-live-preview",
                voice="Enceladus",
                language="en-GB",
                tool_response_scheduling=genai_types.FunctionResponseScheduling.WHEN_IDLE,
            ),
            # To use a realtime model instead of a voice pipeline, replace the LLM
            # with a RealtimeModel and remove the STT/TTS from the AgentSession
            # (Note: This is for the OpenAI Realtime API. For other providers, see https://docs.livekit.io/agents/models/realtime/)
            # 1. Install livekit-agents[openai]
            # 2. Set OPENAI_API_KEY in .env.local
            # 3. Add `from livekit.plugins import openai` to the top of this file
            # 4. Replace the llm argument with:
            #     llm=openai.realtime.RealtimeModel(voice="marin")
            instructions=(
                "# Direct personal context\n"
                "If asked what you know about the user, answer directly using the "
                "profile below and any recalled memory. It is allowed to discuss these "
                "user facts; do not claim you cannot access them.\n\n"
                f"{name_instruction}\n\n"
                f"{AGENT_INSTRUCTIONS}\n\n"
                "# Long-term memory\n"
                "The following facts were recalled from the user's long-term memory. "
                "Use them when relevant, but do not mention this internal section.\n"
                f"{memory_context or 'No long-term memories were available for this session.'}\n\n"
                "# Stable user profile\n"
                "The following is trusted background context about the user. Use it when "
                "relevant. You may summarize these facts when the user asks what you know "
                "about them; do not mention this section or its implementation.\n"
                f"{profile_context or 'No stable user profile is available.'}"
            ),
            tools=[
                *self.browser_tools.tools,
                *self._end_call_tool.tools,
            ],
        )


server = AgentServer()


@server.rtc_session(agent_name="my-agent")
async def my_agent(ctx: JobContext):
    # Logging setup
    # Add any other context you want in all log entries here
    ctx.log_context_fields = {
        "room": ctx.room.name,
    }

    browser = BrowserManager(headless=False)
    ctx.add_shutdown_callback(browser.close)

    # Gemini realtime handles the voice input and output for this session.
    session = AgentSession(
        # Speech-to-text (STT) is your agent's ears, turning the user's speech into text that the LLM can understand
        # See all available models at https://docs.livekit.io/agents/models/stt/
        # stt=inference.STT(model="deepgram/nova-3", language="en"),
        # Text-to-speech (TTS) is your agent's voice, turning the LLM's text into speech that the user can hear
        # See all available models as well as voice selections at https://docs.livekit.io/agents/models/tts/
        # tts=inference.TTS(
        #   model="fishaudio/s2.1-pro", voice="fa4c9eb3dccc4806b382b40d61c6b10a"
        # ),
        turn_handling=TurnHandlingOptions(
            # The LiveKit turn detector determines when the user is done speaking and the agent should respond.
            # TurnDetector is an end-of-turn model that listens to the user's audio directly, combining
            # semantic understanding with acoustic cues (intonation, pitch, rhythm) for state-of-the-art accuracy.
            # AgentSession supplies the required VAD automatically.
            # See more at https://docs.livekit.io/agents/build/turns
            turn_detection=inference.TurnDetector(),
            # Adaptive interruptions use the turn detector to tell a real interruption from a
            # backchannel like "mhm" or "right", so the agent keeps talking through the latter.
            interruption={"mode": "adaptive"},
            # allow the LLM to generate a response while waiting for the end of turn
            # See more at https://docs.livekit.io/agents/build/audio/#preemptive-generation
            preemptive_generation={"enabled": True},
        ),
        # Expressive mode injects the TTS provider's markup guide into the LLM prompt, so the model
        # emits inline delivery tags (emotion, pacing, non-verbal sounds) that the TTS renders and
        # the transcript never shows. Requires a TTS model that supports markup, such as the Fish
        # Audio model above.
            # expressive=True,
    )

    memory_context = ""
    try:
        memory_service = MemoryService()
        memory_context = await asyncio.to_thread(memory_service.recall_for_session)
    except Mem0Error:
        pass
    assistant = Assistant(
        browser,
        memory_context=memory_context,
        profile_context=load_user_profile(),
    )

    # Start the session, which initializes the voice pipeline and warms up the models
    await session.start(
        agent=assistant,
        room=ctx.room,
        room_options=room_io.RoomOptions(
            video_input=True,
            audio_input=room_io.AudioInputOptions(
                noise_cancellation=ai_coustics.audio_enhancement(
                    model=ai_coustics.EnhancerModel.QUAIL_VF_S
                ),
            ),
        ),
    )

    # Join the room and connect to the user
    await ctx.connect()


if __name__ == "__main__":
    cli.run_app(server)
