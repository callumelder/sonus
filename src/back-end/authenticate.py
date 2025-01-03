from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
import os


def get_token(SCOPES):
    """Get valid credentials for Google API access."""
    # Get path to utilities directory
    current_dir = os.path.dirname(os.path.abspath(__file__))
    utilities_dir = os.path.join(os.path.dirname(current_dir), 'utilities')
    
    # Set paths for both files in utilities
    credentials_path = os.path.join(utilities_dir, 'credentials.json')
    token_path = os.path.join(utilities_dir, 'token.json')
    
    # Always start fresh
    if os.path.exists(token_path):
        os.remove(token_path)
    
    # Check if credentials file exists
    if not os.path.exists(credentials_path):
        raise FileNotFoundError(f"credentials.json not found at {credentials_path}")
    
    # Start new authentication flow
    
    if os.path.exists(token_path):
        creds = Credentials.from_authorized_user_file(token_path, SCOPES)
    else:
        try:
            flow = InstalledAppFlow.from_client_secrets_file(credentials_path, SCOPES)
            creds = flow.run_local_server(port=8080)
            
            # Save the token
            with open(token_path, 'w') as token:
                token.write(creds.to_json())
                
            return creds
            
        except Exception as e:
            raise Exception(f"Error during authentication: {e}")