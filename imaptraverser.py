import json
from imapclient import IMAPClient
import logging

from sqlalchemy import null


# Defines a message (with a message ID in a folder)
class ImapMessageID:
    def __init__(self,folder,id):
        self.folder = folder
        self.id = id

    def __iter__(self):
        yield from {
            "folder": self.folder,
            "id": self.id,
        }.items()

class ImapCredentials:

    _host = ""
    _user = ""
    _password = ""

    def readFile(self, filename):
        f = open(filename,)
        input = json.load(f)
        f.close()

        self.host = input["host"]
        self.password = input["password"]
        self.user = input["user"]

    def isOK(self):
        return self.host!='' and self.password!='' and self.user!=''



# Traverses an IMAP server with a search criteria (defalut ALL), and 
#
# Happy flow is to initiate, and call nextMessage() until it returns False.
# The current message can be fetched from ther server on request.
#
class ImapTraverser:
    def __init__( self, credentials, criteria="ALL" ):
        self._criteria = criteria
        self._client = IMAPClient( credentials.host, ssl=True, use_uid=True )
        self._client.login( credentials.user, credentials.password )
        self._folders = []
        folders = self._client.list_folders()
        for folder in folders:
            self._folders.append( folder[2] )

        self._currentFolderIdx = -1
        self._currentMessageIdx = 0

    def __del__(self):
        self._client.logout()

    def nrFolders(self):
        return len(self._folders)

    def currentFolderIdx(self):
        return self._currentFolderIdx

    def currentFolder(self):
        if self._currentFolderIdx==-1 or self._currentFolderIdx>=len(self._folders):
            return ""
        
        return self._folders[self._currentFolderIdx]

    def nrMessagesInFolder(self):
        return len(self._messageIds)
    
    def currentMessageIdx(self):
        return self._currentMessageIdx

    def currentMessageID(self):
        if self._currentMessageIdx==-1 or self._currentMessageIdx>=len(self._messageIds):
            return ImapMessageID( "", -1 )
        
        return ImapMessageID( self.currentFolder(), self._messageIds[self._currentMessageIdx] )

    def nextMessage(self):
        #First init
        if self._currentFolderIdx==-1:
            if self._nextFolder()==False:
                return False
        else: #Not first init, advance
            self._currentMessageIdx += 1
            if self._currentMessageIdx>=self.nrMessagesInFolder():
                if self._nextFolder()==False:
                    return False
        
        return True

    def getCurrentMessage(self):
        response = self._client.fetch(self._messageIds[self._currentMessageIdx], ["ENVELOPE", "FLAGS", "RFC822.SIZE"])

        if len(response)==0:
            return null
        
        return response[0]





    def _nextFolder(self):

        while True:
            self._currentFolderIdx += 1
            if self._currentFolderIdx>=len(self._folders):
                return False

            logging.info( f"Switching to folder {self.currentFolder()}")

            self._client.select_folder( self._folders[self._currentFolderIdx] )
            self._messageIds = self._client.search( self._criteria )
            self._currentMessageIdx = 0

            if len(self._messageIds)>0:
                break

        return True