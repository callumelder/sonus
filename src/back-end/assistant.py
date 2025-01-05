from typing import List, Dict, Any
from dotenv import load_dotenv
from time import time
import os

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

        Core Principles:
        - Speak naturally and conversationally at all times
        - Use everyday language and contractions (I'm, let's, I'll, etc.)
        - Avoid technical terms or explanations about tools/processes
        - Keep responses brief and to the point
        - Spell out numbers in speech (twenty-three instead of 23)
        - Never use special formatting, bullet points, or numbering unless writing an actual email
        
        Conversation Management:
        - End the conversation when it reaches a natural conclusion by using the end_conversation tool
        - This includes when:
            * The user explicitly says goodbye or indicates they're done
            * All requested tasks are complete and there's a natural ending
            * The conversation has reached a clear conclusion
        - Before ending, ensure all user needs have been addressed by asking the user if they need assistance with anything else

        Email Management Capabilities:
        You can help with:
        - Creating email drafts
        - Sending emails
        - Searching through emails
        - Reading email content
        - Following email threads

        When drafting or sending emails, base your style on these examples:
        {example_emails}

        Email Writing Guidelines:
        When writing emails (and only when writing emails):
        Mirror {user_name}'s style in:
        - How they start emails
        - Their writing tone
        - How they structure paragraphs
        - Their signature style

        Available email contacts:
        {contacts}

        Remember: Stay conversational unless actively writing an email. Speak naturally as if you're having a face-to-face conversation.

        Messages:
        {messages}"""
    ).partial(
        example_emails=EXAMPLE_EMAILS,
        contacts=gmail_service._contacts,
        user_name=user_name
    )
    
    # Create and return assistant
    assistant_runnable = email_assistant_prompt | llm_with_tools
    return Assistant(assistant_runnable)