from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
import os


def get_token(SCOPES):
    creds = None
    # Check if the token.json file already exists
    if os.path.exists('token.json'):
        creds = Credentials.from_authorized_user_file('token.json', SCOPES)
    else:
        # Initiate OAuth 2.0 flow if token.json is not found
        current_dir = os.path.dirname(os.path.abspath(__file__))
        credentials_path = os.path.join(current_dir, 'credentials.json')
        flow = InstalledAppFlow.from_client_secrets_file(credentials_path, SCOPES)
        creds = flow.run_local_server(port=8080)
        
        # Save the access and refresh tokens in token.json for future use
        with open('token.json', 'w') as token:
            token.write(creds.to_json())