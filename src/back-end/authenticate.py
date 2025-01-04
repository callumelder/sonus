from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
import os


def get_token(SCOPES):
    creds = None
    
    # Get path to utilities directory
    current_dir = os.path.dirname(os.path.abspath(__file__))
    utilities_dir = os.path.join(os.path.dirname(current_dir), 'utilities')
    
    # Set paths for both files in utilities
    credentials_path = os.path.join(utilities_dir, 'credentials.json')
    token_path = os.path.join(utilities_dir, 'token.json')
    
    # Load existing token if it exists
    if os.path.exists(token_path):
        try:
            creds = Credentials.from_authorized_user_file(token_path, SCOPES)
        except ValueError:
            # If the token is invalid or missing refresh token, remove it
            os.remove(token_path)
            creds = None
    
    # If no valid credentials available, try to refresh or get new ones
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            try:
                creds.refresh(Request())
            except Exception as e:
                print(f"Error refreshing token: {str(e)}")
                creds = None
        
        # If we still don't have valid credentials, get new ones
        if not creds:
            # Check if credentials file exists
            if not os.path.exists(credentials_path):
                raise FileNotFoundError(f"credentials.json not found at {credentials_path}")
            
            # Create flow with offline access
            flow = InstalledAppFlow.from_client_secrets_file(
                credentials_path,
                SCOPES,
                # Configure OAuth session for offline access
                redirect_uri='http://localhost:8080'
            )
            
            # Run the flow with offline access prompt
            creds = flow.run_local_server(
                port=8080,
                prompt='consent',  # Force consent screen
                access_type='offline'  # Enable offline access
            )
            
            # Save the credentials for the next run
            with open(token_path, 'w') as token:
                token.write(creds.to_json())
    
    return creds