import logging
from datetime import datetime, timezone
from typing import Optional

from dotenv import load_dotenv
from livekit import api
from livekit.agents import (
    Agent,
    AgentSession,
    RoomInputOptions,
    RoomOutputOptions,
    RunContext,
    WorkerOptions,
    cli,
    metrics,
)
from livekit.agents.llm import function_tool
from livekit.agents.voice import MetricsCollectedEvent

########################################################################################
# I am not sure this relates to the project but i just import it to see the use case
# which i think it should return the list of participants in the room and details
from livekit.api import LiveKitAPI
from livekit.api import ListParticipantsRequest
from livekit.api import RoomParticipantIdentity
##########################################################################################

from livekit.plugins import groq, silero

# Import database models and intervention checker
from db.models import Request, CallHistory, db
from utils.help import needs_human_intervention

# Configure logging and environment
logger = logging.getLogger("salon-agent")
load_dotenv()

# Business info for Veluxe Beauty Lounge
SALON_INFO = {
    "name": "Veluxe Beauty Lounge",
    "address": "123 Beauty St, Lagos",
    "hours": "9am to 7pm Monday through Saturday",
    "phone": "+2348001234567",
    "services": [
        "hair styling",
        "manicure & pedicure",
        "facials",
        "makeup artistry"
    ]
}

# Agent instructions embedding salon details
common_instructions = (
    f"You are a courteous AI assistant for {SALON_INFO['name']}. "
    f"Greet the customer with 'Welcome to {SALON_INFO['name']}, how can I assist you today?'. "
    "Use the salon information when answering: "
    f"Address: {SALON_INFO['address']}, "
    f"Hours: {SALON_INFO['hours']}, "
    f"Phone: {SALON_INFO['phone']}, "
    "Services: " + ", ".join(SALON_INFO['services']) + ". "
    "If you don't know or the query needs human, respond exactly: 'Let me check with my supervisor and get back to you.'"
)

class SalonAgent(Agent):
    def __init__(self) -> None:
        super().__init__(instructions=common_instructions)

    async def on_enter(self):
        # Greet the caller by directly playing text (bypassing LLM/tool logic)
        greeting = f"Welcome to {SALON_INFO['name']}, how can I assist you today?"
        await self.session.generate_reply(instructions=greeting)

    # This function will be called when the agent receives a message
    # it is expected for the ai to get its info from here
    @function_tool
    async def handle_query(
        self,
        context: RunContext,
        query: str,
    ):
        customer_phone = context.userdata.get("customer_phone")
        call_id = context.userdata.get("call_id")

        # Retrieve the original user message
        try:
            # i have been trying to figure out how to get the original query
            # from the chat context but i am not sure how to do this but let's
            # see if this works :)
            original_query = context.chat_ctx.messages[-1].content
            logger.info(f"Original query: {original_query}")
        except Exception:
            logger.error("Failed to retrieve original query from chat context.")
            original_query = query

        # Check if query needs human intervention based on my what i
        # said in the last video interview
        needs, reason = needs_human_intervention(original_query)
        if needs:
            req = Request.create(
                customer_phone=customer_phone,
                query=original_query,
                call_id=call_id,
                category=reason
            )
            logger.info(f"Escalation ({reason}) request created: {req.id}")
            await self.session.generate_reply(
                instructions="Let me check with my supervisor and get back to you."
            )
            CallHistory.get(call_id).end_call(escalated=True, request_id=req.id)
            return None

        # Attempt automated answer
        answer = self._lookup_answer(original_query)
        if answer:
            await self.session.generate_reply(instructions=answer)
            return answer

        # Default escalation for unknown queries
        req = Request.create(
            customer_phone=customer_phone,
            query=original_query,
            call_id=call_id,
            category="general"
        )
        logger.info(f"Pending request created: {req.id}")
        await self.session.generate_reply(
            instructions="Let me check with my supervisor and get back to you."
        )
        CallHistory.get(call_id).end_call(escalated=True, request_id=req.id)
        return None

    # called to get the answer to the query
    def _lookup_answer(self, query: str) -> Optional[str]:
        q = query.lower()
        if "hours" in q:
            return f"Our hours are {SALON_INFO['hours']}."
        if "address" in q or "location" in q:
            return f"We are located at {SALON_INFO['address']}."
        if "phone" in q or "contact" in q:
            return f"You can reach us at {SALON_INFO['phone']}."
        for svc in SALON_INFO['services']:
            if svc in q:
                return f"Yes, we offer {svc} at {SALON_INFO['name']}."
        return None


async def entrypoint(ctx: RunContext):

    # i see i can add room name and identity for participants handling
    room_name = "veluxe-beauty-lounge"
    identity = "salon-assistant" 
    await ctx.connect(room_name=room_name, identity=identity)  # hoping this would work
    logger.info(f"Connected to room: {room_name}")
    
    # i am simulating phone number extraction which i guess would be gotten
    # from the telephony plugin or SIP :)
    customer_phone = "+2348001234567"
    call_record = CallHistory.create(customer_phone=customer_phone)
    call_id = call_record.id  # simulating unique call ID generation
    logger.info(f"Call started: {call_id}")

    async with api.LiveKitAPI() as lkapi:
        # should return list of participants in the room
        res = await lkapi.room.list_participants(ListParticipantsRequest(
            room=room_name
        ))
        logger.info(f"Participants in room: {[p.identity for p in res.participants]}") # hopefully this works

    # Initializing session
    session = AgentSession(
        vad=silero.VAD.load(),  # yet to know what this does but i see i need it
        stt=groq.STT(),  # this should be openai but i am stuck with groq for free credits
        llm=groq.LLM(model="llama3-8b-8192"),
        tts=groq.TTS(model="playai-tts"),
        userdata={"call_id": call_id, "customer_phone": customer_phone}  # i will be using this in function tools
    )

    # Metrics collection
    usage = metrics.UsageCollector()  # from the docs. i see it logs out metrics of the session
    @session.on("metrics_collected")
    def log_metrics(ev: MetricsCollectedEvent):
        metrics.log_metrics(ev.metrics)
        usage.collect(ev.metrics)

    # Shutdown should summary of the session though i am not sure this works yet
    async def on_shutdown():
        logger.info(f"Total usage: {usage.get_summary()}")
    ctx.add_shutdown_callback(on_shutdown)

    # Starting agent session
    await session.start(
        agent=SalonAgent(),   # the agent class i defined earlier
        room=ctx.room,
        room_input_options=RoomInputOptions(),
        room_output_options=RoomOutputOptions(transcription_enabled=True),
    )

if __name__ == "__main__":
    cli.run_app(WorkerOptions(entrypoint))  # code runs from here
