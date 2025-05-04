################################################################
# I initialy created this llm as the brain of the operation
# to feed the livekit ai agent but i had to feed the livekit
# the prompt itself direclty making use of the same LLM model
# baased on the requirement to feed the assistant the prompt

###############################################################


from groq import AsyncGroq
import os, sys
import json
from typing import Dict, Any, Tuple
from dotenv import load_dotenv
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from db.models import Request

load_dotenv()


class SalonAIAssistant:
    """Salon AI Assistant that uses Groq for responses"""
    def __init__(self, business_info):
        self.business_info = business_info
        self.system_prompt = self._build_system_prompt()
        self.client = AsyncGroq(api_key=os.getenv('GROQ_API_KEY'))
        self.message_history = []  # Initialize conversation history


    def _build_system_prompt(self):
        """Creates a strictly‐constrained system prompt based on the salon data."""
        # Dump the complete salon_info JSON
        data = json.dumps(self.business_info, indent=2)

        return (
            f"You are the AI assistant for {self.business_info['name']}.\n"
            "You must use **only** the information between <<<JSON>>> and <<<END JSON>>>\n"
            "Do NOT add, infer, or invent any details not present in that data.\n"
            "If asked about anything outside that data, respond exactly:\n"
            "I am not sure\n\n"
            "<<<JSON>>>\n"
            f"{data}\n"
            "<<<END JSON>>>"
        )


    async def get_response(self, user_prompt):
        """Asks Groq and returns the smart salon response while maintaining conversation history."""
        # Add the user's message to the history
        self.message_history.append({"role": "user", "content": user_prompt})

        # Include the system prompt and message history in the request
        messages = [{"role": "system", "content": self.system_prompt}] + self.message_history

        # Get the response from the AI model
        response = await self.client.chat.completions.create(
            model="llama3-8b-8192",  # or another Groq model like "mixtral-8x7b-32768"
            messages=messages,
            temperature=0.0,
        )

        # Extract the assistant's response
        assistant_response = response.choices[0].message.content

        # Add the assistant's response to the history
        self.message_history.append({"role": "assistant", "content": assistant_response})

        return assistant_response


async def process_salon_query(query: str, call_id: str = None, customer_phone: str = None) -> Tuple[str, bool]:
    """
    Process a user query through the salon AI assistant
    Returns the response and a boolean indicating if escalation is needed
    """

    salon_info = os.getenv('SALON_INFO_PATH')
    with open(salon_info, 'r') as f:
        salon_data = json.load(f)   
    assistant = SalonAIAssistant(salon_data)
    
    # Get response from Groq-powered assistant
    response = await assistant.get_response(query)
    
    # Check if we need to escalate (if response contains "I am not sure")
    needs_escalation = "I am not sure" in response
    
    # If we need to escalate and have call tracking info, create a request
    if needs_escalation and call_id and customer_phone:
        Request.create(customer_phone, query, call_id, category="general")  # default category is general when ai canot answer
    
    return response, needs_escalation
