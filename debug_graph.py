import asyncio
import os
from dotenv import load_dotenv

load_dotenv()

from agent.graph import study_agent
from agent.state import AgentState

async def main():
    try:
        initial_state: AgentState = {
            "messages": [{"role": "user", "content": "explain virtual memory to me"}],
            "session_id": "dummy_session",
            "user_id": "dummy_user",
            "subject_id": "dummy_subject",
            "intent": "",
            "retrieved_chunks": [],
            "chunk_confidence": 0.0,
            "tool_results": {},
            "plan": [],
            "response": "",
            "awaiting_confirmation": False,
            "proposed_calendar_events": [],
        }
        
        result = await study_agent.ainvoke(initial_state)
        print("Success!")
        print(result["response"])
    except Exception as e:
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(main())
