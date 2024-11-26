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
from googleapiclient.discovery import build

def get_gmail_contacts(credentials):
    """
    Retrieves Gmail contacts using provided credentials.
    
    Args:
        credentials: Valid Google OAuth2 credentials object
    
    Returns:
        List of dictionaries containing contact information:
        [{'name': 'Contact Name', 'email': 'email@example.com'}, ...]
    """
    # Build the People API service
    service = build('people', 'v1', credentials=credentials)
    
    # Initialize empty list for all contacts
    all_contacts = []
    page_token = None
    
    try:
        while True:
            # Request contacts from the API
            results = service.people().connections().list(
                resourceName='people/me',
                pageSize=1000,  # Maximum allowed page size
                pageToken=page_token,
                personFields='names,emailAddresses'
            ).execute()
            
            connections = results.get('connections', [])
            
            # Process each contact
            for person in connections:
                names = person.get('names', [])
                emails = person.get('emailAddresses', [])
                
                if emails:  # Only include contacts with email addresses
                    contact = {
                        'name': names[0].get('displayName', 'No Name') if names else 'No Name',
                        'email': emails[0].get('value', '')
                    }
                    all_contacts.append(contact)
            
            # Get the next page token
            page_token = results.get('nextPageToken')
            if not page_token:
                break
                
        return all_contacts
        
    except Exception as e:
        print(f"Error retrieving contacts: {str(e)}")
        return []

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
    SCOPES = ["https://www.googleapis.com/auth/gmail.modify", "https://www.googleapis.com/auth/contacts.readonly"]
    
    # Get authentication token
    get_token(SCOPES)
    
    # Setup credentials and API resource
    credentials = get_gmail_credentials(
        token_file="token.json",
        scopes=SCOPES,
        client_secrets_file="credentials.json",
    )
    api_resource = build_resource_service(credentials=credentials)
    
    # Setup contacts
    contacts = get_gmail_contacts(credentials)
    print(contacts)
    
    # Setup Gmail toolkit and get tools
    toolkit = GmailToolkit(api_resource=api_resource)
    return toolkit.get_tools()

example_emails = """
    ---
    Hi Roozbeh and Greg,

    Just letting you know that I have an appointment this Wednesday (6th of November) in the morning. I will most likely be 15-20 minutes late.

    Thanks,
    Callum
    ---
    Hi James,

    Just following up from our discussion last Thursday. I had a talk to my supervisor Roozbeh about what a company can potentially do with a $10,000 budget. He said a static chatbot is possible for around $8,000 to $12,000 per year. Static as in the data is ingested once (no data pipeline) and a chatbot is given access to the data.

    If you have any further questions, please ask.

    Thanks,
    Callum
"""


def setup_assistant(tools: List[BaseTool]):
    """Setup and return an email assistant with the provided tools"""
    # Setup LLM with tools
    llm = ChatOpenAI(model="gpt-4o")
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
        
        The following are examples of emails written by the user. Carefully analyze:
        - How they structure their emails (greetings, body format, bullet points vs. paragraphs)
        - Their writing style and tone
        - How they sign off their emails
        - Their name and preferred signature format
        You must use these examples to structure your email.
        Always send from the user.
        
        Use these examples as your template for writing emails, ensuring you maintain their personal style:
        {{example_emails}}

        Messages:
        {messages}"""
    )
    
    # Create and return assistant
    assistant_runnable = email_assistant_prompt | llm_with_tools
    return Assistant(assistant_runnable)