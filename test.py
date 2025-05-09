import asyncio
import logging
from datetime import datetime
from typing import Optional
from dataclasses import dataclass

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
    AudioConfig,
    BackgroundAudioPlayer,
    BuiltinAudioClip,
    WorkerOptions,
    get_job_context,
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

# Instructions for the agent
instructions = (
    f"Your name is Joy. You are a friendly and witty receptionist at {SALON_INFO['name']}. "
    "Use the salon info when answering questions about hours, location, services, and contact information. "
    "When asked about services, list all services we offer in a friendly way. "
    "If you must escalate, say exactly: 'Let me check with my supervisor and get back to you.' "
    "IMPORTANT: Never show function calls in your responses. Always speak naturally as a salon receptionist."
)
@dataclass
class UserInfo:
    user_name: str | None = None
    call_record: CallHistory | None = None

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


class BioCollector(Agent):
    def __init__(self):
        super().__init__(
            instructions="""You are a voice AI agent simulating a receptionist for a salon with the singular task to collect
            just name from the user. you must be friendly"""
        )

    async def on_enter(self) -> None:
        await self.session.say("Hello, Welcome to Veluxe Beauty Lounge, can i know your name please", allow_interruptions=False)
        # Start disconnect monitor

    @function_tool()
    async def record_name(self, context: RunContext[UserInfo], name: str) -> None:
        """Use this tool to record that name has been given by the user.
        Args:
            name (str): The name given by the user.
        """
        context.userdata.user_name = name
        print(f"User name recorded: {name}")

        # if name is recorded, handoff to the next agent
        return self._handoff_if_done()
    
    def _handoff_if_done(self):
        if self.session.userdata.user_name:
            return SalonAgent()
        else:
            return None
        
    @function_tool()
    async def end_call(self, ctx: RunContext) -> None:
        """Use this tool to indicate when the user says bye or signify they want to end the call"""
        await self.session.say("Thank you for your time, have a wonderful day.")
        job_ctx = get_job_context()
        current_speech = ctx.session.current_speech
        if current_speech:
            await current_speech.wait_for_playout()
        await job_ctx.api.room.delete_room(api.DeleteRoomRequest(room=job_ctx.room.name))

class SalonAgent(Agent):
    def __init__(self):
        super().__init__(instructions=instructions)
    
    async def on_enter(self) -> None:
        await self.session.say("Hello! Welcome to Veluxe Beauty Lounge. How can I assist you today?", allow_interruptions=False)
        
    @function_tool(
        name="process_query",
        description="Process a customer question and provide a response."
    )
    async def process_query(self, context: RunContext[UserInfo], query: str) -> str:
        """Processes a customer question and returns a response.
        Args:
            query (str): The user's question to be processed.

        Returns:
            str: The generated response to the user's question.
        """
        call_record = context.userdata.call_history
        phone = call_record.customer_phone
        call_id = call_record.id
        name = context.userdata.user_name

        # first check if the customer's query needs human intervention
        needs, reason = needs_human_intervention(query)
        if needs:
            req = Request.create(customer_phone=phone, query=query, call_id=call_id, category=reason)
            logger.info(f"Escalation request created for {name}: {req.id}")
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
            services_list = ", ".join(SALON_INFO["services"])
            return f"At {SALON_INFO['name']}, we offer {services_list}."
            
        # unknown → general escalation
        req = Request.create(customer_phone=phone, query=query, call_id=call_id, category="general")
        logger.info(f"Pending request created: {req.id}")
        return "Let me check with my supervisor and get back to you."

    @function_tool()
    async def end_call(self, ctx: RunContext) -> None:
        """Use this tool to indicate when the user says bye or signify they want to end the call"""
        await self.session.say("Thank you for your time, have a wonderful day.")
        job_ctx = get_job_context()
        current_speech = ctx.session.current_speech
        if current_speech:
            await current_speech.wait_for_playout()
        await job_ctx.api.room.delete_room(api.DeleteRoomRequest(room=job_ctx.room.name))


async def entrypoint(ctx: JobContext):
    await ctx.connect()
    logger.info(f"Connected to room: {ctx.room.name}")
    
    # List participants in the room
    async with api.LiveKitAPI() as lkapi:
        res = await lkapi.room.list_participants(ListParticipantsRequest(
            room=ctx.room.name
        ))
        print(f"Participants in room: {[p.identity for p in res.participants]}")
        print(f"this is their sid: {[p.sid for p in res.participants]}")
    
    agent = BioCollector()
    # Simulate extracting caller info 
    customer_phone = "+2348001234567"
    call_record = CallHistory.create(customer_phone=customer_phone)
    call_id = call_record.id
    logger.info(f"Call started: {call_id}") 

    asyncio.create_task(monitor_disconnects(ctx.room.name, call_record))

    # set the call record in the user data
    user_info = UserInfo(call_record=call_record)

    # Custom STT node to log user speech
    async def custom_stt_node(self, audio, settings):
        async for ev in Agent.default.stt_node(self, audio, settings):
            if isinstance(ev, SpeechEvent) and getattr(ev, "alternatives", None):
                txt = ev.alternatives[0].text
                if txt:
                    logger.info(f"User said: {txt}")
            yield ev
    agent.stt_node = custom_stt_node.__get__(agent, Agent)

    # Building session
    session = AgentSession[UserInfo](
        vad=silero.VAD.load(),
        stt=groq.STT(model="whisper-large-v3-turbo"),
        llm=groq.LLM(),
        tts=groq.TTS(
            model="playai-tts",
            voice="Arista-PlayAI"),
        userdata=user_info,
    )

    # Start the conversation
    await session.start(
        agent=agent,
        room=ctx.room,
        room_input_options=RoomInputOptions(),
        room_output_options=RoomOutputOptions(transcription_enabled=False),
    )
    background_audio = BackgroundAudioPlayer(
    # play office ambience sound looping in the background
    ambient_sound=AudioConfig(BuiltinAudioClip.OFFICE_AMBIENCE, volume=0.8),
    # play keyboard typing sound when the agent is thinking
    thinking_sound=[
        AudioConfig(BuiltinAudioClip.KEYBOARD_TYPING, volume=0.5),
        AudioConfig(BuiltinAudioClip.KEYBOARD_TYPING2, volume=0.5),
    ],
    )
    await background_audio.start(room=ctx.room, agent_session=session)

  

if __name__ == "__main__":
    cli.run_app(WorkerOptions(entrypoint_fnc=entrypoint))