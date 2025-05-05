import logging
from dataclasses import dataclass, field
from typing import Annotated, Optional
import yaml
from dotenv import load_dotenv
from livekit.agents import JobContext, WorkerOptions, cli
from livekit.agents.llm import function_tool
from livekit.agents.voice import Agent, AgentSession, RunContext
from livekit.agents.voice.room_io import RoomInputOptions
from livekit.plugins import groq, silero
# from livekit.plugins import noise_cancellation

logger = logging.getLogger("restaurant-example")
logger.setLevel(logging.INFO)
load_dotenv()

async def entrypoint(ctx: JobContext):
    await ctx.connect()

    session = AgentSession(
        vad=silero.VAD.load(),
        stt=groq.STT(model="whisper-large-v3-turbo"),
        llm=groq.LLM(),
        tts=groq.TTS(model="playai-tts"),
    )
    await session.start(
        agent=Agent(instructions="you're an assistant for a logistics company"),
        room=ctx.room)
    
    await session.say("Welcome to Toota! How can I assist you today?",
                      allow_interruptions=False)


if __name__ == "__main__":
    cli.run_app(WorkerOptions(entrypoint_fnc=entrypoint))
