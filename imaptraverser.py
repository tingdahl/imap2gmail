import json
import os
import socket
from imapclient import IMAPClient
import logging


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

class ImapMessageIDList:
    def __init__(self):
        self.list = []

    def contains(self, checkid):
        for listid in self.list:
            if listid.id == checkid.id and listid.folder==checkid.folder:
                return True

        return False


    def load(self,filename):
        if os.path.exists( filename ):
            file =  open(filename, 'rb')

            importlist = []
            try:
                importlist = json.load( file )
            except:
                logging.error("Could not read cache file.")
                self.list = []

            file.close()

            for id in importlist:
                self.list.append( ImapMessageID(id['folder'],id['id'] ))

            logging.info(f"Loaded {len(self.list)} cache items from {filename}.")

    def write(self,filename):
        file =  open(filename, 'w')

        json_string = json.dumps([ob.__dict__ for ob in self.list])

        file.write( json_string )

        file.close()


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

    _includeDeleted = False
    _startDate = None
    _beforeDate = None
    _folder = ""

    def __init__( self, credentials ):

        try:
            self._client = IMAPClient( credentials.host, ssl=True, use_uid=True )
        except (IMAPClient.Error, socket.error) as err:
            logging.critical(f"Cannot connect to IMAP server: {err}")

        try:
            self._client.login( credentials.user, credentials.password )
        except (IMAPClient.Error, socket.error) as err:
            logging.critical(f"Cannot login to IMAP server: {err}")



    def __del__(self):
        try:
            self._client.logout()
        except (IMAPClient.Error, socket.error) as err:
            logging.error( f"Exception cought when logging out from IMAP server: {err}")

    def includeDeleted(self,includedeleted):
        self._includeDeleted = includedeleted

    def setStartDate(self,startdate):
        self._startDate = startdate

    def setBeforeDate(self,beforedate):
        self._beforeDate = beforedate

    #Get a list of folders from server.
    def retrieveFolders(self):
        try:
            imapfolders = self._client.list_folders()
        except (IMAPClient.Error, socket.error) as err:
            logging.critical(f"Cannot retrieve IMAP folders: {err}")
            return []

        folders = []    

        for folder in imapfolders:
            folders.append( folder[2] )

        return folders

    def setFolder(self,folder):
        if folder==self._folder:
            return True

        logging.info( f"Switching to folder {folder}")

        try:
            self._client.select_folder( folder )
        except (IMAPClient.Error, socket.error) as err:
            logging.error(
                    f"Cannot switch to folder {folder}: {err}")
            return False

        self._folder = folder
        return True

        

    def getMessageIds(self):
        criteria = ""
        if self._includeDeleted==False:
            criteria += "NOT DELETED"

        if self._startDate!=None:
            criteria += f" SINCE \"{self._startDate.strftime('%d-%b-%Y')}\""

        if self._beforeDate!=None:
            criteria += f" BEFORE \"{self._beforeDate.strftime('%d-%b-%Y')}\""

        if len(criteria)==0:
            criteria.append("ALL")

        logging.info( f"Searching in {self._folder}")
        try:
            messages = self._client.search( criteria.strip() )
        except (IMAPClient.Error, socket.error) as err:
            logging.error(
                    f"Cannot switch to folder {self._folder}: {err}")
            return []
        
        return messages

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

    def loadMessage(self,msgid):
        try:
            response = self._client.fetch(msgid, ["ENVELOPE", "FLAGS", "RFC822"])

            if len(response)==0:
                return None
        except (IMAPClient.Error, socket.error) as err:
            logging.error(f"Cannot retrieve message {msgid} in folder {self._folder}: {err}")
            return None

        return response[msgid]

    def _nextFolder(self):

        criteria = ""
        if self._includeDeleted==False:
            criteria += "NOT DELETED"

        if self._startDate!=None:
            criteria += f" SINCE \"{self._startDate.strftime('%d-%b-%Y')}\""

        if self._beforeDate!=None:
            criteria += f" BEFORE \"{self._beforeDate.strftime('%d-%b-%Y')}\""

        if len(criteria)==0:
            criteria.append("ALL")

        while True:
            self._currentFolderIdx += 1
            if self._currentFolderIdx>=len(self._folders):
                return False

            logging.info( f"Switching to folder {self.currentFolder()}")

            try:
                self._client.select_folder( self.currentFolder() )
                self._messageIds = self._client.search( criteria.strip() )
            except (IMAPClient.Error, socket.error) as err:
                logging.error(
                    f"Cannot switch to folder {self.currentFolder()}: {err}")
            self._currentMessageIdx = 0

            if len(self._messageIds)>0:
                break

        return True