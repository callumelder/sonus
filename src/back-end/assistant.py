from typing import List, Dict, Any
from dotenv import load_dotenv
from time import time
import os
from datetime import datetime
import pytz

from gmail import GmailService

from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables import Runnable
from langchain_core.tools import BaseTool
from langgraph.graph import MessagesState
from langchain_google_community import GmailToolkit
from langchain_anthropic import ChatAnthropic


class Assistant:
    def __init__(self, runnable: Runnable):
        self.runnable = runnable

    def __call__(self, state: MessagesState):
        attempt = 1
        start_time = time()
        print("[Assistant] Starting LLM invocation...")
        
        while True:
            print(f"[Assistant] Attempt {attempt} starting at {time() - start_time:.2f}s")
            t0 = time()
            result = self.runnable.invoke(state)
            print(f"[Assistant] Invoke took {time() - t0:.2f}s")
            print(f"[Assistant] Result: {result}")
            
            if not result.tool_calls and (
                not result.content
                or isinstance(result.content, list)
                and not result.content[0].get("text")
            ):
                print(f"[Assistant] Got invalid response on attempt {attempt}, retrying...")
                messages = state["messages"] + [("user", "Respond with a real output.")]
                state = {**state, "messages": messages}
                attempt += 1
            else:
                print(f"[Assistant] Got valid response after {attempt} attempts")
                print(f"[Assistant] Total time: {time() - start_time:.2f}s")
                break
                
        return {"messages": result}

EXAMPLE_EMAILS = """
    Hi Roozbeh and Greg,\n\n

    Just letting you know that I have an appointment this Wednesday (6th of November) in the morning. I will most likely be 15-20 minutes late.\n\n

    Thanks,\n
    Callum
    ---
    Hi James,\n\n

    Just following up from our discussion last Thursday. I had a talk to my supervisor Roozbeh about what a company can potentially do with a $10,000 budget. 
    He said a static chatbot is possible for around $8,000 to $12,000 per year. Static as in the data is ingested once (no data pipeline) and a chatbot is given access to the data.\n\n

    If you have any further questions, please ask.\n\n

    Thanks,\n
    Callum
    """
    
def get_current_time():
    aest = pytz.timezone('Australia/Brisbane')
    return datetime.now(aest).strftime("%m/%d/%y %H:%M")
    
class EndConversationTool(BaseTool):
    name: str = "end_conversation"
    description: str = "End the current conversation when appropriate. Use this when the conversation has reached a natural conclusion or when explicitly requested by the user."
    
    def _run(self, reason: str = "natural_end") -> Dict[str, Any]:
        return {
            "status": "ended",
            "reason": reason
        }

def setup_gmail_tools():
    """Setup and return Gmail tools with proper authentication"""
    gmail_service = GmailService()
    toolkit = GmailToolkit(api_resource=gmail_service._api_resource)
    return toolkit.get_tools()

def setup_assistant(tools: List[BaseTool]):
    """Setup and return an email assistant with the provided tools"""
    load_dotenv()
    
    # Setup LLM with tools
    llm = ChatAnthropic(model="claude-3-5-sonnet-20241022")
    llm_with_tools = llm.bind_tools(tools)
    
    # Get contacts
    gmail_service = GmailService()
    
    # Get username
    user_name = os.getenv("USER_NAME", "User")  # Default to "User" if not set
    
    # Setup assistant prompt
    email_assistant_prompt = ChatPromptTemplate.from_template(
        r"""You are having a natural, spoken conversation with {user_name}. You help them manage their emails and inbox by speaking naturally, as a human assistant would.

        <core_behavior>
            <personality>
                - Speak naturally and conversationally at all times
                - Use everyday language and contractions (I'm, let's, I'll, etc.)
                - Keep responses brief and to the point
                - Spell out numbers in speech (twenty-three instead of 23)
            </personality>

            <formatting>
                - Never use special formatting, bullet points, or numbering unless writing an actual email
                - Avoid technical terms or explanations about tools/processes
            </formatting>

            <conversation_management>
                <end_conditions>
                    - User explicitly says goodbye or indicates they're done
                    - All requested tasks are complete and there's a natural ending
                    - The conversation has reached a clear conclusion
                </end_conditions>
                <end_protocol>
                    - Ensure all user needs are addressed before ending
                    - Ask if user needs anything else
                    - Use end_conversation tool to close session
                </end_protocol>
            </conversation_management>
        </core_behavior>

        <capabilities>
            <email_management>
                - Creating email drafts
                - Sending emails
                - Searching through emails
                - Reading email content
                - Following email threads
            </email_management>
        </capabilities>

        <email_style>
            <examples>
                {example_emails}
            </examples>
            
            <writing_guidelines>
                Mirror {user_name}'s style in:
                - Email openings
                - Writing tone
                - Paragraph structure
                - Signature format
            </writing_guidelines>
        </email_style>

        <configuration>
            <contacts>
                {contacts}
            </contacts>
        </configuration>

        <conversation_context>
            Remember: Stay conversational unless actively writing an email. Speak naturally as if you're having a face-to-face conversation.
        </conversation_context>
        
        <current_time>
            {time}
        </current_time>

        <messages>
            {messages}
        </messages>"""
    ).partial(
        example_emails=EXAMPLE_EMAILS,
        contacts=gmail_service._contacts,
        user_name=user_name,
        time=get_current_time()
    )
    
    # Create and return assistant
    assistant_runnable = email_assistant_prompt | llm_with_tools
    return Assistant(assistant_runnable)