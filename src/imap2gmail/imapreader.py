# 
# Copyright © 2022 Tingdahl ICT Management
# Licenced under the MIT licence, see license.md
# 

import json
import os
import socket
from imapclient import IMAPClient
import logging


# Defines a message (with a message ID in a folder)
class ImapMessageID:
    folderKey = 'folder'
    idKey = 'id'
    __slots__ = 'folder', 'id'
    def __init__(self,folder,id):
        self.folder = folder
        self.id = id

    def json_serialize(self):
         return {ImapMessageID.folderKey: self.folder, ImapMessageID.idKey: self.id}

    def __iter__(self):
        yield from {
            ImapMessageID.folderKey: self.folder,
            ImapMessageID.idKey: self.id,
        }.items()

# List of ImapMessageIDs.
class ImapMessageIDList:
    __slots__ = 'list'
    def __init__(self):
        self.list = []

    # Returns true if checkid exists in the list
    def contains(self, checkid):
        for listid in self.list:
            if listid.id == checkid.id and listid.folder==checkid.folder:
                return True

        return False

    # Load list from json file
    def loadJsonFile(self,filename):
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

    # Write list to json file
    def writeJSonFile(self,filename):
        file =  open(filename, 'w')

        json_string = json.dumps([ob.json_serialize() for ob in self.list])

        file.write( json_string )

        file.close()

# Holds host, user, password for an IMAP server
class ImapCredentials:
    __slots__ = 'host', 'user', 'password'

    def loadJsonFile(self, filename):
        try:
            f = open(filename,)
        except OSError as err:
            logging.critical(f"Cannot open file {filename}: {err}")
            return False

        input = json.load(f)
        f.close()

        self.host = input["host"]
        self.password = input["password"]
        self.user = input["user"]
        return True

    def isOK(self):
        return self.host!='' and self.password!='' and self.user!=''

# Opens connection to an IMAP server, and provides limited services
# to read data from it 
#
# Happy flow is to initiate, and call retrieveFolders, traverse over all folders
# and read messages in those folders.
# At the end, log out from the server.

class ImapReader:

    __slots__ = '_folder', '_client'

    def __init__( self, credentials ):
        self._folder = ""
        self._client = None
        try:
            self._client = IMAPClient( credentials.host, ssl=True, use_uid=True )
        except (IMAPClient.Error, socket.error) as err:
            logging.critical(f"Cannot connect to IMAP server {credentials.host}: {err}")
            return

        try:
            self._client.login( credentials.user, credentials.password )
        except (IMAPClient.Error, socket.error) as err:
            logging.critical(f"Cannot login to IMAP server: {err}")
            self._client = None
            return

    def isOK(self):
        return self._client != None

    #Get a list of folders from server.
    def retrieveAllFolders(self):
        try:
            imapfolders = self._client.list_folders()
        except (IMAPClient.Error, socket.error) as err:
            logging.critical(f"Cannot retrieve IMAP folders: {err}")
            return []

        folders = []    

        for folder in imapfolders:
            attributes = folder[0]

            skip_folder = False
            for attribute in attributes:
                if attribute == b'\\Noselect':
                    skip_folder = True
                    break

            if skip_folder==True:
                continue

            folders.append( folder[2] )

        return folders

    def setCurrentFolder(self,folder):
        if folder==self._folder:
            return True

        folderdisplayname = folder.replace(".","/")

        logging.info( f"Switching to folder {folderdisplayname}")

        try:
            self._client.select_folder( folder, readonly=True )
        except (IMAPClient.Error, socket.error) as err:
            logging.error(
                    f"Cannot switch to folder {folderdisplayname}: {err}")
            return False

        self._folder = folder
        return True

    # Gets a list of all message ids in the current folder.

    def searchMessages(self,startdate,beforedate,includedeleted):
        criteria = ""
        if includedeleted==False:
            criteria += "NOT DELETED"

        if startdate!=None:
            criteria += f" SINCE \"{startdate.strftime('%d-%b-%Y')}\""

        if beforedate!=None:
            criteria += f" BEFORE \"{beforedate.strftime('%d-%b-%Y')}\""

        if len(criteria)==0:
            criteria = "ALL"

        logging.info( f"Searching in {self._folder}")
        try:
            messages = self._client.search( criteria.strip() )
        except (IMAPClient.Error, socket.error) as err:
            logging.error(
                    f"Cannot search messages in folder {self._folder}: {err}")
            return []
        
        return messages

    # Loads a message in current folder. Returns an array of Flags, and RFC822
    # message

    def loadMessage(self,msgid):
        try:
            response = self._client.fetch(msgid, ["FLAGS", "RFC822"])

            if len(response)==0:
                return None
        except (IMAPClient.Error, socket.error) as err:
            logging.error(f"Cannot retrieve message {msgid} in folder {self._folder}: {err}")
            return None

        return response[msgid]
    
    def logout(self):
        if self._client==None:
            return

        try:
            self._client.logout()
        except (IMAPClient.Error, socket.error) as err:
            logging.error( f"Exception cought when logging out from IMAP server: {err}")

        self._client = None
