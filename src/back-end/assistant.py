from typing import List, Dict
from dataclasses import dataclass
from dotenv import load_dotenv
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables import Runnable, RunnableConfig
from langgraph.graph import MessagesState
from langchain_core.tools import BaseTool
from langchain_google_community import GmailToolkit
from langchain_google_community.gmail.utils import build_resource_service, get_gmail_credentials
from authenticate import get_token
from googleapiclient.discovery import build
from google.oauth2.credentials import Credentials

from langchain_anthropic import ChatAnthropic
from time import time
import os


@dataclass
class GmailConfig:
    SCOPES = [
        "https://www.googleapis.com/auth/gmail.modify",
        "https://www.googleapis.com/auth/contacts.readonly"
    ]
    TOKEN_FILE = "token.json"
    CREDENTIALS_FILE = "credentials.json"

class GmailService:
    _instance = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance
    
    def __init__(self):
        if not self._initialized:
            self._api_resource = None
            self._credentials = None
            self._contacts = None
            
            try:
                # Get credentials - will only trigger auth flow if needed
                self._credentials = get_token(GmailConfig.SCOPES)
                
                # Build API resource with valid credentials
                self._api_resource = build_resource_service(credentials=self._credentials)
                
                # Fetch contacts immediately
                self._contacts = self._fetch_contacts()
                    
            except Exception as e:
                print(f"Authentication error: {str(e)}")
                self._credentials = None
                self._api_resource = None
                self._contacts = None
                raise
                
            self._initialized = True
    
    def _fetch_contacts(self) -> List[Dict[str, str]]:
        """Fetch Gmail contacts using the People API"""
        service = build('people', 'v1', credentials=self._credentials)
        all_contacts = []
        page_token = None
        
        try:
            while True:
                results = service.people().connections().list(
                    resourceName='people/me',
                    pageSize=1000,
                    pageToken=page_token,
                    personFields='names,emailAddresses'
                ).execute()
                
                for person in results.get('connections', []):
                    names = person.get('names', [])
                    emails = person.get('emailAddresses', [])
                    
                    if emails:
                        contact = {
                            'name': names[0].get('displayName', 'No Name') if names else 'No Name',
                            'email': emails[0].get('value', '')
                        }
                        all_contacts.append(contact)
                
                page_token = results.get('nextPageToken')
                if not page_token:
                    break
                    
            return all_contacts
            
        except Exception as e:
            print(f"Error retrieving contacts: {str(e)}")
            return []

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
    ---
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
        """You are an intelligent assistant that helps users manage their emails and inbox. You communicate naturally with users about their email needs and only use formal email formatting when actually drafting or sending emails.
        
        You are to be concise with your responses, unless specifically told to be more verbose.

        You have access to these tools:
        - GmailCreateDraft - Creates and saves email drafts for later review/editing before sending
        - GmailSendMessage - Immediately sends out email messages to specified recipients 
        - GmailSearch - Searches your Gmail inbox using Gmail's search syntax and returns matching email IDs
        - GmailGetMessage - Retrieves the full content of a single email message using its ID
        - GmailGetThread - Fetches an entire email conversation thread including all replies and forwards
        
        User's name:
        {user_name}

        When specifically asked to draft or send an email, use these examples as templates for the proper format and style:
        {example_emails}

        Email Style Guidelines (ONLY apply these when drafting/sending emails):
        - Match the user's email structure (greetings, body format, paragraphs)
        - Use their typical tone and writing style
        - Copy their signature
        - Send from the user's perspective

        Available contacts for sending emails:
        {contacts}

        For all other interactions, maintain a natural conversational tone. Only use email formatting when explicitly drafting or sending emails.

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