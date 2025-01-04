from typing import List, Dict

from langchain_google_community.gmail.utils import build_resource_service
from authenticate import get_token
from googleapiclient.discovery import build


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