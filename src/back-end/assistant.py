from typing import List
from dotenv import load_dotenv
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables import Runnable, RunnableConfig
from langgraph.graph import MessagesState
from langchain_core.tools import BaseTool
from langchain_google_community import GmailToolkit
from langchain_google_community.gmail.utils import build_resource_service, get_gmail_credentials
from authenticate import get_token

load_dotenv()

class Assistant:
    def __init__(self, runnable: Runnable):
        self.runnable = runnable

    def __call__(self, state: MessagesState, config: RunnableConfig):
        while True:
            configuration = config.get("configurable", {})
            customer_id = configuration.get("customer_id", None)
            state = {**state, "user_info": customer_id}
            result = self.runnable.invoke(state)
            # If the LLM happens to return an empty response, we will re-prompt it
            # for an actual response.
            if not result.tool_calls and (
                not result.content
                or isinstance(result.content, list)
                and not result.content[0].get("text")
            ):
                messages = state["messages"] + [("user", "Respond with a real output.")]
                state = {**state, "messages": messages}
            else:
                break
        print(f"Response: {result}")
        return {"messages": result}


def setup_gmail_tools():
    """Setup and return Gmail tools with proper authentication"""
    # Define the required scopes
    SCOPES = ["https://www.googleapis.com/auth/gmail.modify"]
    
    # Get authentication token
    get_token(SCOPES)
    
    # Setup credentials and API resource
    credentials = get_gmail_credentials(
        token_file="token.json",
        scopes=SCOPES,
        client_secrets_file="credentials.json",
    )
    api_resource = build_resource_service(credentials=credentials)
    
    # Setup Gmail toolkit and get tools
    toolkit = GmailToolkit(api_resource=api_resource)
    return toolkit.get_tools()


def setup_assistant(tools: List[BaseTool]):
    """Setup and return an email assistant with the provided tools"""
    # Setup LLM with tools
    llm = ChatOpenAI(model="gpt-4")
    llm_with_tools = llm.bind_tools(tools)
    
    # Setup assistant prompt
    email_assistant_prompt = ChatPromptTemplate.from_template(
        """You are an intelligent email assistant that helps with drafting, sending, searching and reading.
        When drafting emails, you create professional, well-structured content with clear subject lines, appropriate greetings, and proper signatures.
        Maintain a natural, professional yet friendly tone suitable for business communication.

        You have access to these tools:
        - GmailCreateDraft - Creates and saves email drafts for later review/editing before sending
        - GmailSendMessage - Immediately sends out email messages to specified recipients
        - GmailSearch - Searches your Gmail inbox using Gmail's search syntax and returns matching email IDs
        - GmailGetMessage - Retrieves the full content of a single email message using its ID
        - GmailGetThread - Fetches an entire email conversation thread including all replies and forwards

        Messages:
        {messages}"""
    )
    
    # Create and return assistant
    assistant_runnable = email_assistant_prompt | llm_with_tools
    return Assistant(assistant_runnable)