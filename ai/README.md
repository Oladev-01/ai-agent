# Salon AI Agent with Human Fallback

This project implements a simple AI agent for a salon that can handle basic customer inquiries and request human help when needed.

## Features

- Receives and responds to customer calls using LiveKit
- Handles basic salon information queries
- Requests human supervisor help when it doesn't know an answer
- Stores help requests in a simple database (expandable to Firebase/DynamoDB)

## Setup Instructions

### Prerequisites

- Python 3.8+
- LiveKit account and API keys

### Installation

1. Clone this repository
2. Install dependencies:
   ```
   pip install livekit-agents python-dotenv
   ```
3. Create a `.env` file with your LiveKit and Groq credentials:
   ```
   LIVEKIT_API_KEY=your_api_key
   LIVEKIT_API_SECRET=your_api_secret
   LIVEKIT_URL=your_livekit_url
   GROQ_API_KEY=your_groq_api_key
   ```

### Running the Agent

1. Start the agent:
   ```
   python salon_agent.py
   ```
2. Connect to the agent using the LiveKit CLI or web interface

## Project Structure

- `salon_agent.py`: Main agent implementation with speech handling and human fallback
- For production, replace the SimpleDB class with Firebase/DynamoDB integration

## How It Works

1. The agent listens for incoming calls through LiveKit
2. When a user speaks, the `UserInputTranscribedEvent` captures their speech
3. The agent processes the query with its salon knowledge base
4. If the agent can't answer, it:
   - Tells the customer it will check with a supervisor
   - Creates a help request in the database
   - Simulates notifying a human supervisor
   - The supervisor can then follow up with the customer

## Extending the System

To use Firebase instead of the simple in-memory database:

1. Install Firebase:
   ```
   pip install firebase-admin
   ```
2. Update the database code:
   ```python
   import firebase_admin
   from firebase_admin import credentials, firestore
   
   # Initialize Firebase
   cred = credentials.Certificate("path/to/service-account.json")
   firebase_admin.initialize_app(cred)
   db = firestore.client()
   
   # Then in SalonAssistant class:
   def request_human_help(self, question: str) -> str:
       doc_ref = db.collection('help_requests').add({
           'question': question,
           'timestamp': firestore.SERVER_TIMESTAMP,
           'status': 'pending'
       })
       # Rest of the function...
   ```

## Troubleshooting

- If you experience connection issues, check your LiveKit URL and credentials
- For speech recognition problems, ensure your microphone is properly configured
- If agent functions aren't being called, verify that your tool definitions match the function implementations