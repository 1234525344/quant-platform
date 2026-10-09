"""Run locally only; never commit credentials."""
import os
from google_auth_oauthlib.flow import InstalledAppFlow

flow = InstalledAppFlow.from_client_secrets_file(os.getenv('GOOGLE_OAUTH_CLIENT_JSON','client_secret.json'), scopes=['https://www.googleapis.com/auth/gmail.modify'])
creds = flow.run_local_server(port=0, access_type='offline', prompt='consent')
print('Configure your refresh token privately in Render:', creds.refresh_token)
