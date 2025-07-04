# 
# Copyright © 2022 Tingdahl ICT Management
# Licenced under the MIT licence, see license.md
# 

import queue
import threading
from .imapreader import ImapMessageID,ImapMessageIDList,ImapReader
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
    __slots__ = '_imapcredentials', '_nrthreads', \
                '_startdate', '_beforedate', '_includedeleted', \
                '_folderqueue', '_messagequeue', '_gmailclient', '_imapreaders', \
                '_initialmessagecache', '_messagecache', '_cachefile', '_nrmessages'

    def __init__(self, imapcredentials, gmailclient, nrthreads,
                 startdate, beforedate,includedeleted, cachefile):
        self._imapcredentials = imapcredentials
        self._nrthreads = nrthreads
        self._startdate = startdate
        self._beforedate = beforedate
        self._includedeleted=includedeleted

        self._folderqueue = queue.SimpleQueue()
        self._messagequeue = queue.SimpleQueue()

        self._gmailclient = gmailclient
        if self._gmailclient.isOK()==False:
            return

        if self._gmailclient.loadLabels()==False:
            return

        logging.info(f"Initiating {self._nrthreads} threads.")
        self._imapreaders = []
        for threadidx in range(self._nrthreads):
            reader = ImapReader( self._imapcredentials )
            if reader.isOK()==False:
                return

            self._imapreaders.append( reader ) 

        self._initialmessagecache = ImapMessageIDList()
        self._initialmessagecache.loadJsonFile( cachefile )

        self._messagecache = ImapMessageIDList()
        self._messagecache.loadJsonFile( cachefile )
        self._cachefile = cachefile

    def isOK(self):
        return self._gmailclient.isOK() and len(self._imapreaders)>0

    # Create a queue of all messages on the imap server that should be imported

    def discoverMessages(self):
        folders = self._imapreaders[0].retrieveAllFolders()
        if len(folders)<1:
            return False

        if self._gmailclient.addImapFolders( folders )==False:
            return False

        for folder in folders:
            self._folderqueue.put( folder )

        self._messagecache.setFolders( folders )
        self._initialmessagecache.setFolders( folders )

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

        return True

    
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

            folderdisplayname = message._folder.replace(".","/")

            if self._initialmessagecache.contains( message )==True:
                logging.info( f"Thread {threadidx}: Skipping message {messageidx} of {self._nrmessages} (UID: {message._id} in folder {folderdisplayname})")
                continue

            if reader.setCurrentFolder( message._folder )==False:
                continue

            logging.info(  f"Thread {threadidx}: Processing message {messageidx} of {self._nrmessages} (UID: {message._id} in folder {folderdisplayname})")
            imapmessage = reader.loadMessage( message._id )

            if imapmessage==None:
                logging.error(f"Thread {threadidx}: Cannot fetch message UID: {message._id}) in folder {folderdisplayname}")
                continue

            res = self._gmailclient.importImapMessage( imapmessage, message._folder )
            if res is None:
                self._messagecache._foldersidslist[message._folder].append( message._id )
                if threadidx==0 and self._cachefile:
                    self._messagecache.writeJSonFile( self._cachefile )
            else:
                logging.error(f"Message UID: {message._id} in folder {folderdisplayname} not imported. Error: {res}")

        reader.logout()

# Wrapper function for discoverFolderThreadFunction        
        
def discoverFolderThreadFunction(obj,threadnr):
    obj.discoverFolderThreadFunction(threadnr)    

# Wrapper function for processThreadFunction

def processThreadFunction(obj,threadnr):
    obj.processThreadFunction(threadnr)

