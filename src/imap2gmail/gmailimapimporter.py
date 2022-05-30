# 
# Copyright © 2022 Tingdahl ICT Management
# Licenced under the MIT licence, see license.md
# 

import os.path
import logging
import google_auth_httplib2
import httplib2

from ratelimit import limits, RateLimitException, sleep_and_retry
from base64 import urlsafe_b64decode, urlsafe_b64encode

from google.auth.transport.requests import Request
from google.auth.exceptions import GoogleAuthError
from google.oauth2.credentials import Credentials

from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

# If modifying these scopes, delete the file token.json.
SCOPES = ['https://www.googleapis.com/auth/gmail.labels',
        'https://www.googleapis.com/auth/gmail.insert']

MAX_CALLS_PER_SECOND=9
ONE_SECOND = 1

# Representation of an GMail label, and its IMAP folder source

class GMailLabel:
    name = ''
    IMAPfolder = ''
    GMailID = ''

    def __init__(self, name, folder, gmailid):
        self.name = name
        self.IMAPfolder = folder
        self.GMailID = gmailid

# Collection of GMailLabels. 

class GMailLabels:

    # Find the corresponding label for an IMAP folder. Labels that are read from
    # GMail does not know their (original) IMAP folder. It is assumed that their
    # display name matches the folder name.

    def findLabelForImapFolder(self,imapfolder):
        for label in self.labels:
            if label.IMAPfolder ==imapfolder:
                return label
            if label.name == imapfolder:
                return label

        return None

    labels = []

# Class import messages to 

class GMailImapImporter:
    TOKENFILE = 'gmail_token.json'

    def __init__(self,credentialsfile,reauthenticate):
        self._service = None
        
        if self._loadCredentials( credentialsfile,reauthenticate )==False:
            return

        try:
            self._service = build('gmail', 'v1', credentials=self._creds)
        except HttpError as error:
            # TODO(developer) - Handle errors from gmail API.
            logging.error(f'An error occurred: {error}')

    # Load the current labels in GMail and try to map them to 
    # known system folders (inbox, sent, drafts, ...) and states (read, starred, ...)

    def isOK(self):
        return self._service!=None

    def loadLabels(self):
        logging.info("Reading current GMail labels.")
        self._labels = None

        try:
            results = self._service.users().labels().list(userId='me').execute()
            labels = results.get('labels', [])
        except HttpError as error:
            logging.critical(f"Cannot read labels: {error}")
            self._service = None #Triggers isOK==False
            return False
        except GoogleAuthError as error:
            # TODO(developer) - Handle errors from gmail API.
            logging.critical(f"Authentification error: {error}. Try re-authenticate by running with --reauthenticate")
            self._service = None #Triggers isOK==False
            return False

        if not labels:
            logging.error("No labels found in GMail.")
            return False

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

        return True

    # Prepare the client for a number of imap folder. Create corresponding labels in
    # GMail if necessary.

    def addImapFolders(self,folders):
        for folder in folders:
            label = self._labels.findLabelForImapFolder( folder )
            if label!=None: # Label exists
                continue

            label_obj = {'name': folder}
            
            if self._refreshToken()==False:
                logging.critical("Refresh token failed.")
                return False
                
            try:
                result = self._service.users().labels().create(userId='me', body=label_obj).execute()
                logging.info(f"Created label {result['id']}")
            
            except Exception as error:
                logging.error(f"An error occurred while creating label {folder}: {error}")
                return False

            self._labels.labels.append( GMailLabel( folder, folder, result['id']))

        return True

    # Add message to Gmail, with the apropriate labels based on flags and folder.
    # The message is expected to have the FLAGS and RFC822 parts.

    @sleep_and_retry
    @limits(calls=MAX_CALLS_PER_SECOND, period=ONE_SECOND)
    def importImapMessage(self, message, folder ):
        flags = message[b'FLAGS']
        messagelabels = []
  
        # Find label based on folder name
        folderlabel = self._labels.findLabelForImapFolder(folder)
        if folderlabel!=None:
            messagelabels.append( folderlabel.GMailID )

        # Search for flagged and seen flags, and set labels accordingly
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

        # Prepare message to be posted to API

        message_obj = {'raw': urlsafe_b64encode(message[b'RFC822']).decode(),
                       'labelIds': messagelabels }

        
        if self._refreshToken()==False:
            logging.critical("Refresh token failed.")
            return False

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

    # If a token doe snot exists, use credentials file to ask user for permission 
    # and get a token. 

    def _loadCredentials(self,credentialsfile,reauthenticate):
        self._creds = None
        if reauthenticate==False and os.path.exists( self.TOKENFILE ):
            self._creds = Credentials.from_authorized_user_file(self.TOKENFILE, SCOPES)

        if not self._creds:
            try:
                flow = InstalledAppFlow.from_client_secrets_file(
                    credentialsfile, SCOPES)
            except OSError as err:
                logging.critical( f"Cannot create secrets from {credentialsfile}: {err}")
                return False

            try:
                self._creds = flow.run_local_server(port=0)
            except Exception as err:
                logging.critical(f"No valid client created: {err} Check if google credentials are correct.")
                return False

            self._writeToken()

        return self._creds!=None

    # Refresh the token

    def _refreshToken(self):
        if self._creds and self._creds.expired and self._creds.refresh_token:
            try:
                self._creds.refresh(Request())
            except:
                return False

            self._writeToken()

        return self._creds and self._creds.valid

    # Save the credentials for the next run

    def _writeToken(self):
        
        with open(self.TOKENFILE, 'w') as token:
            try:
                token.write(self._creds.to_json())
            except OSError as err:
                logging.error(f"Cannot write file {self.TOKENFILE}: {err}")
