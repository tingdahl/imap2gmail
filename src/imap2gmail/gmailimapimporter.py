#
# Copyright © 2022 Tingdahl ICT Management
# Licenced under the MIT licence, see license.md
#

import os.path
import logging
import re
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
SCOPES = ['https://www.googleapis.com/auth/gmail.modify']

MAX_CALLS_PER_SECOND = 8
ONE_SECOND = 1
INBOX = 'INBOX'


# Representation of an GMail label, and its IMAP folder source
class GMailLabel:
    __slots__ = '_name', '_IMAPfolder', '_GMailID'

    def __init__(self, name, folder, gmailid):
        self._name = name
        self._IMAPfolder = folder
        self._GMailID = gmailid


# Collection of GMailLabels.
class GMailLabels:
    __slots__ = '_labels'

    def __init__(self):
        self._labels = []

    # Find the corresponding label for an IMAP folder. Labels that are read
    # from GMail does not know their (original) IMAP folder. It is assumed
    # that their display name matches the folder name.

    def findLabelForImapFolder(self, imapfolder):
        for label in self._labels:
            if label._IMAPfolder == imapfolder:
                return label
            if label._name == imapfolder:
                return label

        return None


# Class import messages to
class GMailImapImporter:
    __slots__ = '_service', '_labels', '_unreadlabel', \
                '_starredlabel', '_junklabel', '_draftlabel', \
                 '_trashlabel', '_inboxlabel', '_creds'
    TOKENFILE = 'gmail_token.json'

    def __init__(self):
        self._service = None

    def logout(self):
        try:
            os.remove(self.TOKENFILE)
        except OSError:
            pass

    def login(self, credentialsfile, reauthenticate: bool):

        if self._loadCredentials(credentialsfile, reauthenticate) is False:
            return

        try:
            self._service = build('gmail', 'v1', credentials=self._creds)
        except HttpError as error:
            # TODO(developer) - Handle errors from gmail API.
            logging.error(f'An error occurred: {error}')

        if self._refreshToken() is False:
            logging.critical("Refresh token failed.")
            return False

        return self.isOK()

    def isOK(self):
        return self._service is not None

    # Load the current labels in GMail and try to map them to
    # known system folders (inbox, sent, drafts, ...) and states (read,
    # starred, ...)

    def loadLabels(self):
        logging.info("Reading current GMail labels.")
        self._labels = None

        try:
            results = self._service.users().labels().list(
                userId='me').execute()
            labels = results.get('labels', [])
        except HttpError as error:
            logging.critical(f"Cannot read labels: {error}")
            self._service = None  # Triggers isOK==False
            return False
        except GoogleAuthError as error:
            # TODO(developer) - Handle errors from gmail API.
            logging.critical(f"Authentification error: {error}. "
                             f"Try re-authenticate by running with "
                             f"--reauthenticate")
            self._service = None  # Triggers isOK==False
            return False

        if not labels:
            logging.error("No labels found in GMail.")
            return False

        self._labels = GMailLabels()
        self._unreadlabel = None
        self._starredlabel = None
        self._junklabel = None
        self._trashlabel = None
        self._inboxlabel = None

        for label in labels:
            imapfolder = ''
            labelid = label['id']
            if labelid == 'SENT':
                imapfolder = 'Sent'
            elif labelid == 'DRAFT':
                imapfolder = 'Drafts'
            elif labelid == INBOX:
                imapfolder = INBOX
            elif labelid == 'SPAM':
                imapfolder = 'Junk'
            elif labelid == 'TRASH':
                imapfolder = 'Trash'

            newlabel = GMailLabel(label['name'], imapfolder, labelid)
            if labelid == 'UNREAD':
                self._unreadlabel = newlabel
            elif labelid == "STARRED":
                self._starredlabel = newlabel
            elif labelid == "SPAM":
                self._junklabel = newlabel
            elif labelid == "TRASH":
                self._trashlabel = newlabel
            elif labelid == "DRAFT":
                self._draftlabel = newlabel
            elif labelid == INBOX:
                self._inboxlabel = newlabel

            self._labels._labels.append(newlabel)

        return True

    # Prepare the client for a number of imap folder. Create corresponding
    # labels in GMail if necessary.

    def addImapFolders(self, folders):
        # Sort labels to start with short ones. Then we will add parent
        # folders before their eventual childeren. This will make GMail work
        # with nested folders

        sortedlabels = sorted(folders, key=len)
        for folder in sortedlabels:
            clean_folder = GMailImapImporter._cleanFolderName(folder)
            label = self._labels.findLabelForImapFolder(clean_folder)
            if label is not None:  # Label exists
                continue

            label_obj = {'name': clean_folder}

            if self._refreshToken() is False:
                logging.critical("Refresh token failed.")
                return False

            try:
                result = self._service.users().labels().create(
                    userId='me',
                    body=label_obj).execute()
                logging.info(f"Created label \"{clean_folder}\" "
                             f"({result['id']})")

            except Exception as error:
                logging.error(f"An error occurred while creating label \""
                              f"{clean_folder}\": {error}")
                return False

            self._labels._labels.append(GMailLabel(clean_folder, clean_folder,
                                                   result['id']))

        return True

    # Add message to Gmail, with the apropriate labels based on flags and
    # folder. The message is expected to have the FLAGS and RFC822 parts.

    @sleep_and_retry
    @limits(calls=MAX_CALLS_PER_SECOND, period=ONE_SECOND)
    def importImapMessage(self, message, folder):
        folder = GMailImapImporter._cleanFolderName(folder)
        flags = message[b'FLAGS']
        messagelabels = []

        # Find label based on folder name
        folderlabel = self._labels.findLabelForImapFolder(folder)

        if self._refreshToken() is False:
            logging.critical("Refresh token failed.")
            return False

        # Drafts are handled separately with a separate drafts.create call.
        if folderlabel._GMailID == self._draftlabel._GMailID:
            message_body = \
                {'raw': urlsafe_b64encode(message[b'RFC822']).decode()}
            message = {'message': message_body}
            try:
                http = google_auth_httplib2.AuthorizedHttp(
                    self._creds, http=httplib2.Http())
                self._service.users().drafts().create(
                    userId="me",
                    body=message,
                    ).execute(num_retries=2, http=http)
            except Exception as error:
                logging.error(f"Could not upload draft to GMail: {error}")
                return False

            return True

        # Search for flagged and seen flags, and set labels accordingly
        seen = False
        flagged = False
        junk = folderlabel._GMailID == self._junklabel._GMailID
        deleted = folderlabel._GMailID == self._trashlabel._GMailID
        inbox = folderlabel._GMailID == self._inboxlabel._GMailID

        for flag in flags:
            if flag == b'\\Seen':
                seen = True
            elif flag == b'\\Flagged':
                flagged = True
            elif flag == b'Junk':
                junk = True
            elif flag == b'NonJunk':
                junk = False
            elif flag == b'\\Deleted':
                deleted = True

        # INBOX, TRASH and SPAM are mutually exclusive
        if deleted:
            messagelabels.append(self._trashlabel._GMailID)
        elif junk:
            messagelabels.append(self._junklabel._GMailID)
        elif inbox:
            messagelabels.append(self._inboxlabel._GMailID)

        # Set any label not INBOX, TRASH, SPAM
        if folderlabel._GMailID != self._inboxlabel._GMailID and \
                folderlabel._GMailID != self._trashlabel._GMailID and \
                folderlabel._GMailID != self._junklabel._GMailID:
            messagelabels.append(folderlabel._GMailID)

        if seen is False:
            messagelabels.append(self._unreadlabel._GMailID)

        if flagged is True:
            messagelabels.append(self._starredlabel._GMailID)

        message_obj = {'raw': urlsafe_b64encode(message[b'RFC822']).decode(),
                       'labelIds': messagelabels}

        try:
            http = google_auth_httplib2.AuthorizedHttp(
                self._creds, http=httplib2.Http())
            self._service.users().messages().import_(
                    userId="me",
                    body=message_obj,
                    internalDateSource='dateHeader',
                    processForCalendar=False,
                    neverMarkSpam=True,
                    ).execute(num_retries=2, http=http)
        except Exception as error:
            logging.error(f"Could not upload message to GMail: {error}")
            return False

        return True

    # If a token does not exists, use credentials file to ask user for
    # permission and get a token.

    def _loadCredentials(self, credentialsfile, reauthenticate):
        self._creds = None
        if reauthenticate is False and os.path.exists(self.TOKENFILE):
            self._creds = Credentials.from_authorized_user_file(
                self.TOKENFILE, SCOPES)

        if not self._creds:
            try:
                flow = InstalledAppFlow.from_client_secrets_file(
                    credentialsfile, SCOPES)
            except OSError as err:
                logging.critical(
                    f"Cannot create secrets from {credentialsfile}: {err}")
                return False

            try:
                self._creds = flow.run_local_server(port=0)
            except Exception as err:
                logging.critical(f"No valid client created: {err}."
                                 f"Check if Google credentials are correct.")
                return False

            self._writeToken()

        return self._creds is not None

    # Refresh the token

    def _refreshToken(self):
        if self._creds and self._creds.expired and self._creds.refresh_token:
            try:
                self._creds.refresh(Request())
            except Exception as error:
                logging.error(f"Could not upload message to GMail: {error}")
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

    # Replace the '.' with a forward slash '/' in folder name
    # Remove whitespaces at the end or beginning
    def _cleanFolderName(folder: str) -> str:
        # Replace multiple spaces
        folder_without_spaces = re.sub(r'\s+', ' ', folder)
        return folder_without_spaces.replace(".", "/").strip()
