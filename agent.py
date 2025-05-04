import asyncio
import logging
from datetime import datetime
from typing import Optional

from dotenv import load_dotenv
from livekit import api
from livekit.api import ListParticipantsRequest
from livekit.agents import (
    Agent,
    AgentSession,
    JobContext,
    RunContext,
    RoomInputOptions,
    RoomOutputOptions,
    WorkerOptions,
    cli,
)
from livekit.agents.llm import function_tool
from livekit.agents.stt import SpeechEvent
from livekit.plugins import groq, silero

# Your DB models and helper
from db.models import Request, CallHistory
from utils.help import needs_human_intervention

load_dotenv()
logger = logging.getLogger("salon-agent")

# Salon business info
SALON_INFO = {
    "name": "Veluxe Beauty Lounge",
    "address": "123 Beauty St, Lagos",
    "hours": "9am to 7pm Monday through Saturday",
    "phone": "+2348001234567",
    "services": ["hair styling", "manicure & pedicure", "facials", "makeup artistry"],
}

#
instructions = (
    f"Your name is Joy. You are a friendly and witty receptionist at {SALON_INFO['name']}. "
    "Use the salon info when answering. If you must escalate, say exactly: "
    "Let me check with my supervisor and get back to you."
)

async def monitor_disconnects(room_name: str, call_record: CallHistory, interval: float = 2.0):
    """when our caller leaves, end the call and updates call history."""
    prev = set()
    async with api.LiveKitAPI() as lkapi:
        res = await lkapi.room.list_participants(ListParticipantsRequest(room=room_name))
        # I am assuming a single caller
        prev = {p.identity for p in res.participants}

    while True:
        await asyncio.sleep(interval)
        async with api.LiveKitAPI() as lkapi:
            res = await lkapi.room.list_participants(ListParticipantsRequest(room=room_name))
            current = {p.identity for p in res.participants}
        gone = prev - current
        if gone:
            for identity in gone:
                print(f"Participant disconnected: {identity}")
            # End the call (no escalation here)
            call_record.end_call(escalated=False)
            break
        prev = current

class SalonAgent(Agent):
    def __init__(self):
        super().__init__(instructions=instructions)

    @function_tool(name="handle_query", description="Process a customer question")
    async def handle_query(self, context: RunContext, query: str) -> Optional[str]:
        """Tool: decide if we need human intervention, else answer or escalate."""

        call_record = context.userdata['call_record']
        phone = call_record.customer_phone
        call_id = call_record.id

        # first check if the customer's query needs human intervention
        needs, reason = needs_human_intervention(query)
        if needs:
            req = Request.create(customer_phone=phone, query=query, call_id=call_id, category=reason)
            logger.info(f"Escalation request created: {req.id}")
            return "Let me check with my supervisor and get back to you."

        # simple lookup
        q = query.lower()
        if "hours" in q:
            return f"Our hours are {SALON_INFO['hours']}."
        if "address" in q or "location" in q:
            return f"We are located at {SALON_INFO['address']}."
        if "phone" in q or "contact" in q:
            return f"You can reach us at {SALON_INFO['phone']}."
        if "services" in q or "offer" in q:
            for svc in SALON_INFO["services"]:
                if svc in q:
                    return f"Yes, we offer {svc} at {SALON_INFO['name']}."

        # unknown → general escalation
        req = Request.create(customer_phone=phone, query=query, call_id=call_id, category="general")
        logger.info(f"Pending request created: {req.id}")
        return "Let me check with my supervisor and get back to you."

async def entrypoint(ctx: JobContext):
    await ctx.connect()
    logger.info(f"Connected to room: {ctx.room.name}")
    instructions = "Greet every guest with “Welcome to Veluxe Beauty Lounge, how can I assist you today?”"
    # this is not too related but just to see and list participants
    # and their sid
    async with api.LiveKitAPI() as lkapi:
        # List participants in the room
        res = await lkapi.room.list_participants(ListParticipantsRequest(
            room=ctx.room.name
        ))
        print(f"Participants in room: {[p.identity for p in res.participants]}")
        print(f"this is their sid: {[p.sid for p in res.participants]}")
    
    # Simulate extracting caller info
    customer_phone = "+2348001234567"
    call_record = CallHistory.create(customer_phone=customer_phone)
    call_id = call_record.id  # i could also store the unique id as the sid of the current participant
    logger.info(f"Call started: {call_id}")

    # Start disconnect monitor
    asyncio.create_task(monitor_disconnects(ctx.room.name, call_record))

    agent = SalonAgent()
    async def custom_stt_node(self, audio, settings):
        async for ev in Agent.default.stt_node(self, audio, settings):
            if isinstance(ev, SpeechEvent) and getattr(ev, "alternatives", None):
                txt = ev.alternatives[0].text
                if txt:
                    logger.info(f"User said: {txt}") # this should log the caller queries
            yield ev
    agent.stt_node = custom_stt_node.__get__(agent, Agent)

    # Building session
    session = AgentSession(
        vad=silero.VAD.load(),
        stt=groq.STT(model="whisper-large-v3-turbo"), # this is default model, can leave it out or use a different model
        llm=groq.LLM(),
        tts=groq.TTS(model="playai-tts"),
        userdata={"call_record": call_record},
    )

    # Start the conversation
    await session.start(
        agent=agent,
        room=ctx.room,
        room_input_options=RoomInputOptions(),
        room_output_options=RoomOutputOptions(transcription_enabled=True), # can be set to false if we don't want transcriptions
    )

    session.generate_reply()
if __name__ == "__main__":
    cli.run_app(WorkerOptions(entrypoint_fnc=entrypoint))
