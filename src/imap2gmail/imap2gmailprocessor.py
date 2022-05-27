# 
# Copyright © 2022 Tingdahl ICT Management
# Licenced under the MIT licence, see license.md
# 

import queue
import threading
from .imapreader import ImapMessageID,ImapMessageIDList,ImapReader
from .gmailimapimporter import GMailImapImporter
import logging

# Reads data from an IMAP server and imports them into GMail. IMAP folders
# becomes GMail labels.
# There are two stages in the processing
# 1. discovery
#    The imap server's directory structure is read and each directory is added to a
#    queue. Each directory is searched for messages that match the date and include-deleted
#    criteria. All messages in from all directories are added to the messagequeue.
#
# 2. processing
#    The queue is processed from a number of threads. Each message is checked if it is
#    present in the cache. If so, it is skipped. Otherwise, it is read from the imap server
#    and imported to GMail.


class Imap2GMailProcessor:
    def __init__(self, imapcredentials, googlecredentials, nrthreads,
                 startdate, beforedate,includedeleted, cachefile):
        self._imapcredentials = imapcredentials
        self._nrthreads = nrthreads
        self._startdate = startdate
        self._beforedate = beforedate
        self._includedeleted=includedeleted

        self._folderqueue = queue.SimpleQueue()
        self._messagequeue = queue.SimpleQueue()

        self._gmailclient = GMailImapImporter( googlecredentials )
        self._gmailclient.loadLabels()

        logging.info(f"Initiating {self._nrthreads} threads.")
        self._imapreaders = []
        for threadidx in range(self._nrthreads):
            self._imapreaders.append( ImapReader( self._imapcredentials ) ) 

        self._initialmessagecache = ImapMessageIDList()
        self._initialmessagecache.loadJsonFile( cachefile )

        self._messagecache = ImapMessageIDList()
        self._messagecache.loadJsonFile( cachefile )
        self._cachefile = cachefile

    # Create a queue of all messages on the imap server that should be imported

    def discoverMessages(self):
        folders = self._imapreaders[0].retrieveAllFolders()
        self._gmailclient.addImapFolders( folders )

        for folder in folders:
            self._folderqueue.put( folder )

        threads = []
        for threadidx in range(self._nrthreads):
            thread = threading.Thread(target=discoverFolderThreadFunction,
                                      args=(self,threadidx,))
            thread.start()
            threads.append(thread)

        # Wait for all to finish
        for thread in threads:
            thread.join()

        self._nrmessages = self._messagequeue.qsize()

    
    # DiscoverFolder function for each thread. Processes messages in the queue

    def discoverFolderThreadFunction(self,threadidx):

        reader = self._imapreaders[threadidx]

        while True:
            try:
                folder = self._folderqueue.get_nowait()
            except:
                break

            if reader.setCurrentFolder( folder ):
                messageids = reader.searchMessages(self._startdate,self._beforedate,
                                                     self._includedeleted)

                for messageid in messageids:
                    self._messagequeue.put( ImapMessageID( folder, messageid ))

    # Goes through the queue of all messages and imports them to GMail        

    def process(self):

        threads = []
        for threadidx in range(self._nrthreads):
            thread = threading.Thread(target=processThreadFunction,args=(self,threadidx,))
            thread.start()
            threads.append(thread)

        # Wait for all threads to finish
        for thread in threads:
            thread.join()      

        if self._cachefile:
            self._messagecache.writeJSonFile( self._cachefile )

    def processThreadFunction(self,threadidx):
        reader = self._imapreaders[threadidx]
        
        while True:
            try:
                message = self._messagequeue.get_nowait()
            except:
                break

            messageidx = self._nrmessages - self._messagequeue.qsize()

            if self._initialmessagecache.contains( message )==True:
                logging.info( f"Skipping message {messageidx} of {self._nrmessages} (UID: {message.id} in folder {message.folder})")
                continue

            if reader.setCurrentFolder( message.folder )==False:
                continue

            logging.info(  f"Processing message {messageidx} of {self._nrmessages} (UID: {message.id} in folder {message.folder})")
            imapmessage = reader.loadMessage( message.id )

            if imapmessage==None:
                logging.error(f"Cannot fetch message UID: {message.id}) in folder {message.folder}")
                continue

            if self._gmailclient.importImapMessage( imapmessage, message.folder )!=False:
                self._messagecache.list.append( message )
                if threadidx==0 and self._cachefile:
                    self._messagecache.writeJSonFile( self._cachefile )

        reader.logout()

# Wrapper function for discoverFolderThreadFunction        
        
def discoverFolderThreadFunction(obj,threadnr):
    obj.discoverFolderThreadFunction(threadnr)    

# Wrapper function for processThreadFunction

def processThreadFunction(obj,threadnr):
    obj.processThreadFunction(threadnr)

