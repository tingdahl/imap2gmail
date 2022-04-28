from __future__ import print_function


import os.path
import logging

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

# If modifying these scopes, delete the file token.json.
SCOPES = ['https://www.googleapis.com/auth/gmail.readonly']


class GMailClient:
    TOKENFILE = 'gmail_token.json'

    def __init__(self,credentialsfile):
        if self._loadCredentials( credentialsfile )==False:
            return

        try:
            self._service = build('gmail', 'v1', credentials=self._creds)
        except HttpError as error:
            # TODO(developer) - Handle errors from gmail API.
            logging.error(f'An error occurred: {error}')

    def __del__(self):
        self._writeToken()


    def _loadCredentials(self,credentialsfile):
        self._creds = None
        if os.path.exists( self.TOKENFILE ):
            self._creds = Credentials.from_authorized_user_file(self.TOKENFILE, SCOPES)

        if not self._creds:
            flow = InstalledAppFlow.from_client_secrets_file(
                    credentialsfile, SCOPES)
            self._creds = flow.run_local_server(port=0)

        return self._creds

            

    def _refreshToken(self):
        if self._creds and self._creds.expired and self._creds.refresh_token:
            self._creds.refresh(Request())

        return self._creds and self._creds.valid


    def _writeToken(self):
        # Save the credentials for the next run
        with open(self.TOKENFILE, 'w') as token:
            token.write(self._creds.to_json())
