from __future__ import print_function


import os.path
import logging

from base64 import urlsafe_b64decode, urlsafe_b64encode

import httplib2
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
import google_auth_httplib2
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

# If modifying these scopes, delete the file token.json.
SCOPES = ['https://www.googleapis.com/auth/gmail.labels',
        'https://www.googleapis.com/auth/gmail.insert']

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
        self._unreadlabel = None
        self._starredlabel = None
        self._junklabel = None
        self._trashlabel = None
        
        for label in labels:
            imapfolder = ''
            labelid = label['id']
            if labelid=='SENT':
                imapfolder = 'Sent'
            elif labelid=='DRAFT':
                imapfolder = 'Drafts'
            elif labelid=='INBOX':
                imapfolder = 'INBOX'
            elif labelid=='SPAM':
                imapfolder = 'Junk'
            elif labelid=='TRASH':
                imapfolder = 'Trash' 

            newlabel = GMailLabel( label['name'], imapfolder, labelid)
            if labelid=='UNREAD':
                self._unreadlabel = newlabel
            elif labelid=="STARRED":
                self._starredlabel = newlabel
            elif labelid=="SPAM":
                self._junklabel = newlabel
            elif labelid=="TRASH":
                self._trashlabel = newlabel


            self._labels.labels.append( newlabel )


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

    #Add message to Gmail, with the apropriate labels based on flags and folder
    def addMessage(self, message, folder ):
        flags = message[b'FLAGS']
        messagelabels = []
  
        folderlabel = self._labels.findLabel(folder)
        if folderlabel!=None:
            messagelabels.append( folderlabel.GMailID )

        #Search for flagged and seen flags, and set labels accordingly
        seen = False
        flagged = False
        junk = False
        deleted = False

        for flag in flags:
            if flag==b'\\Seen':
                seen = True
            elif flag==b'\\Flagged':
                flagged = True
            elif flag==b'Junk':
                junk = True
            elif flag==b'NonJunk':
                junk = False
            elif flag==b'\\Deleted':
                deleted = True
            
        if seen==False:
            messagelabels.append( self._unreadlabel.GMailID )

        if flagged==True:
            messagelabels.append( self._starredlabel.GMailID )
        
        #Don't apply junk/trash if it is already in trash.
        if folderlabel.GMailID!=self._trashlabel.GMailID:
            if junk==True:
                messagelabels.append( self._junklabel.GMailID )

            if deleted==True:
                messagelabels.append( self._trashlabel.GMailID )

        message_obj = {'raw': urlsafe_b64encode(message[b'RFC822']).decode(),
                       'labelIds': messagelabels }

        
        if self._refreshToken()==False:
            logging.critical("Refresh token failed.")

        try:
            http = google_auth_httplib2.AuthorizedHttp( self._creds, http=httplib2.Http() )
            result = self._service.users().messages().import_(
                userId="me",
                body=message_obj,
                internalDateSource='dateHeader',
                processForCalendar=False,
                neverMarkSpam=True,
                ).execute(num_retries=2,http=http)
        except Exception as error:
            logging.error(f"Could not upload message to GMail: {error}")
            return False

        return True

    def _loadCredentials(self,credentialsfile):
        self._creds = None
        if os.path.exists( self.TOKENFILE ):
            self._creds = Credentials.from_authorized_user_file(self.TOKENFILE, SCOPES)

        if not self._creds:
            flow = InstalledAppFlow.from_client_secrets_file(
                    credentialsfile, SCOPES)
            self._creds = flow.run_local_server(port=0)
            self._writeToken()

        return self._creds

    def _refreshToken(self):
        if self._creds and self._creds.expired and self._creds.refresh_token:
            try:
                self._creds.refresh(Request())
            except:
                return False

            self._writeToken()

        return self._creds and self._creds.valid


    def _writeToken(self):
        # Save the credentials for the next run
        with open(self.TOKENFILE, 'w') as token:
            token.write(self._creds.to_json())
