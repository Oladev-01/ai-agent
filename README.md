# Salon AI Assistant

This project implements an AI-powered assistant for Veluxe Beauty Lounge. The assistant is designed to simulate a point of contact via a call mode to handle customer queries, provide salon information, and escalate requests to human supervisors when necessary.

## Features

- Provides salon details such as hours, address, phone number, and services.
- Checks first for the customer query for need of escalation 
- Handles customer queries using a natural language model.
- Escalates queries requiring human intervention.
- Logs call history and session metrics.
- Integrates with LiveKit for real-time communication.

---

## Setup Instructions

### Prerequisites

1. **Python**: Ensure Python 3.8 or higher is installed.
2. **Virtual Environment**: Use a virtual environment to manage dependencies.
3. **Environment Variables**: Create a `.env` file in the project root with necessary configurations.

### Installation Steps

1. Clone the repository:
```bash
   git clone <repository-url>
   cd ai-agent
```

2. Create and activate a virtual environment:
```bash
    python3 -m venv venv
    source venv/bin/activate  # On Windows: venv\Scripts\activate
```

3. Install dependencies:
```bash
    pip install -r requirements.txt
```

4. Set up the .env file:

5. Add any required environment variables for LiveKit, database, or other integrations.
Ensure the help.csv file is in the project directory. This file contains phrases to determine if a query needs human intervention.
*KEYS* to set up:
```bash
    *-* GROQ_API_KEY
    *-* LIVEKIT_URL
    *-* LIVEKIT_API_KEY
    *-* LIVEKIT_API_SECRET
```

## Running the Application
To start the AI assistant, run the following command:
```bash
    python main.py dev
```

## Project Structure
* `agent.py`: Main entry point for the AI assistant. Implements the SalonAgent class and handles customer interactions.
* `db/models.py`: Contains database models for requests and call history.
* `utils/help.py`: Includes the needs_human_intervention function to determine if a query requires escalation.
* `db/engine/help.csv`: A CSV file containing phrases to identify queries needing human intervention.

## Key Components
SalonAgent Class
The SalonAgent class is the core of the assistant. It:

* Welcomes customers.
* Handles queries using the `_lookup_answer` method.
* Escalates queries when necessary.

### Escalation Logic
The `needs_human_intervention` function (from `utils/help.py`) checks if a query matches any phrase in `db/engine/help.csv`. If a match is found, the query is escalated.

### Metrics Collection
Session metrics are collected using the `metrics.UsageCollector` and logged for analysis.

### Example Queries
- Here are some example queries the assistant can handle:

* "What are your hours?"
* "Where are you located?"
* "What services do you offer"
* "Can I speak to a supervisor?" (Triggers escalation)

- Here are some example queries that needs human escalation

* I will like to talk to your supervisor
* Can i speak to a human
* This is not what i asked (you must include it twice in the query)
*check the help.csv for more queries*

### What is missing
- Call integration: I saw that to set that up, i need set up SIP and then integrate it to livekit via telephony
- could add real-time notification to a supervisor or staff via email or established communication channels. for now, a console log is used
- could also add more phrases to the list of phrases users could say to signify that they need human assistance
- could also integrate noise cancellation but i feel it's an overkill for this project


*Note:* I added some livekit utilities and events trigger just to test out its function though they may not really be needed for the project and *I am also yet to fully understand livekit.*