from __future__ import print_function


import os.path
import logging

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

# If modifying these scopes, delete the file token.json.
SCOPES = ['https://www.googleapis.com/auth/gmail.readonly',  
        'https://www.googleapis.com/auth/gmail.labels',
        'https://www.googleapis.com/auth/gmail.insert',
        'https://www.googleapis.com/auth/gmail.modify']

class GMailLabel:
    name = '';
    IMAPfolder = ''
    GMailID = ''

    def __init__(self, name, folder, gmailid):
        self.name = name
        self.IMAPfolder = folder
        self.GMailID = gmailid

class GMailLabels:

    def findLabel(self,imapfolder):
        #TODO Map known folders (Inbox, Junk, Sent, Draft, ....)
        for label in self.labels:
            if label.IMAPfolder ==imapfolder:
                return label
            if label.name == imapfolder:
                return label

        return None


    #Get all labels for folders. May be SENT, but also subfolders of SENT.
    def getLabelList(self, imapfolder):
        return []

    labels = []

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

    def loadLabels(self):
        try:
            results = self._service.users().labels().list(userId='me').execute()
            labels = results.get('labels', [])

        except HttpError as error:
            # TODO(developer) - Handle errors from gmail API.
            logging.critical("Cannot read labels.")

        if not labels:
            print('No labels found.')
            return

        self._labels = GMailLabels()
        
        for label in labels:
            imapfolder = ''
            if label['id']=='SENT':
                imapfolder = 'Sent'
            elif label['id']=='DRAFT':
                imapfolder = 'Drafts'
            elif label['id']=='INBOX':
                imapfolder = 'INBOX'
            elif label['id']=='SPAM':
                imapfolder = 'Junk'
            elif label['id']=='TRASH':
                imapfolder = 'Trash' 

            self._labels.labels.append( GMailLabel( label['name'], imapfolder, label['id']))


    def addImapFolders(self,folders):
        for folder in folders:
            label = self._labels.findLabel( folder )
            if label!=None:
                continue

            label_obj = {'name': folder}
            
            if self._refreshToken()==False:
                logging.critical("Refresh token failed.")
                
            try:
                result = self._service.users().labels().create(userId='me', body=label_obj).execute()
                logging.info(f"Created label {result['id']}")
            
            except Exception as error:
                logging.error(f"An error occurred while creating label {folder}: {error}")

            self._labels.labels.append( GMailLabel( folder, folder, result['id']))

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
            try:
                self._creds.refresh(Request())
            except:
                return False

        return self._creds and self._creds.valid


    def _writeToken(self):
        # Save the credentials for the next run
        with open(self.TOKENFILE, 'w') as token:
            token.write(self._creds.to_json())


#try:
#    message = service.users().messages().modify(userId=user_id,
#                                                id=msg_id,
#                                                body=msg_labels).execute()
#
#    label_ids = message['labelIds']
#
#    logging.debug('Message ID: %s - With Label IDs %s' % (msg_id, label_ids))
#    return message
#except errors.HttpError, error:
#    logging.debug('An error occurred: %s' % error)