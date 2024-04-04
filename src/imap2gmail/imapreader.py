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
    __slots__ = '_folder', '_id'
    def __init__(self,folder,id):
        self._folder = folder
        self._id = id

    def json_serialize(self):
         return {ImapMessageID.folderKey: self._folder, ImapMessageID.idKey: self._id}

    def __iter__(self):
        yield from {
            ImapMessageID.folderKey: self._folder,
            ImapMessageID.idKey: self._id,
        }.items()


# List of ImapMessageIDs.
class ImapMessageIDList:
    __slots__ = '_foldersidslist'
    def __init__(self):
        self._foldersidslist = {}

    def setFolders(self, folders ) -> None:
        for foldername in folders:
            if foldername not in self._foldersidslist:
                self._foldersidslist[foldername] = []

    # Returns true if checkid exists in the list
    def contains(self, checkid):
        if checkid._folder in self._foldersidslist:
            return checkid._id in self._foldersidslist[checkid._folder]
        
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
                self._foldersidslist = {}

            file.close()

            for id in importlist:
                foldername = id['folder']
                if foldername not in self._foldersidslist:
                    self._foldersidslist[foldername] = []
                
                self._foldersidslist[foldername].append( id['id'] )

            logging.info(f"Loaded {len(importlist)} cache items from {filename}.")

    # Write list to json file
    def writeJSonFile(self,filename):
        file =  open(filename, 'w')

        exportlist = []
        
        for folder in self._foldersidslist:
            for id in self._foldersidslist[folder]:
                exportlist.append( ImapMessageID( folder, id ))


        json_string = json.dumps([ob.json_serialize() for ob in exportlist])
        logging.info(f"Saving cache file {filename}.")
        file.write( json_string )

        file.close()

# Holds host, user, password for an IMAP server
class ImapCredentials:
    __slots__ = '_host', '_user', '_password'

    def loadJsonFile(self, filename):
        try:
            f = open(filename,)
        except OSError as err:
            logging.critical(f"Cannot open file {filename}: {err}")
            return False

        input = json.load(f)
        f.close()

        self._host = input["host"]
        self._password = input["password"]
        self._user = input["user"]
        return True

    def isOK(self):
        return self._host!='' and self._password!='' and self._user!=''

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
            self._client = IMAPClient( credentials._host, ssl=True, use_uid=True )
        except (IMAPClient.Error, socket.error) as err:
            logging.critical(f"Cannot connect to IMAP server {credentials._host}: {err}")
            return

        try:
            self._client.login( credentials._user, credentials._password )
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
            logging.error( f"Exception caught when logging out from IMAP server: {err}")

        self._client = None
