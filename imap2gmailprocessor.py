# List number of messages in INBOX folder
# and print details of the messages that are not deleted

from json.tool import main
import multiprocessing
import queue
import threading
import imaptraverser
import gmailclient
import logging


class Imap2GMail:
    def __init__(self, imap_credentials, google_credentials, nrthreads,
                 start_date, before_date,include_deleted, cachefile  ):
        self._imapcredentials = imap_credentials
        self._nrThreads = nrthreads
        self._start_date = start_date
        self._before_date = before_date
        self._include_deleted=include_deleted

        self._lock = multiprocessing.Lock()
        self._folderqueue = queue.SimpleQueue()
        self._messagequeue = queue.SimpleQueue()

        self._gmailclient = gmailclient.GMailClient( google_credentials )
        self._gmailclient.loadLabels()

        self._imapclients = []
        for threadidx in range(self._nrThreads):
            self._imapclients.append( imaptraverser.ImapTraverser( self._imapcredentials ) ) 

        self._initialmessagecache = imaptraverser.ImapMessageIDList()
        self._initialmessagecache.load( cachefile )

        self._messagecache = imaptraverser.ImapMessageIDList()
        self._messagecache.load( cachefile )
        self._cachefile = cachefile

    def discoverMessages(self):
        folders = self._imapclients[0].retrieveFolders()
        self._gmailclient.addImapFolders( folders )

        for folder in folders:
            self._folderqueue.put( folder )

        threads = []
        for threadidx in range(self._nrThreads):
            thread = threading.Thread(target=discoverFolder,args=(self,threadidx,))
            thread.start()
            threads.append(thread)

        for thread in threads:
            thread.join()

        self._nrMessages = self._messagequeue.qsize()


    def discoverFolder(self,threadidx):
        traverser = self._imapclients[threadidx]

        while True:
            try:
                folder = self._folderqueue.get_nowait()
            except:
                break

            if traverser.setFolder( folder ):
                traverser.setBeforeDate( self._before_date )
                traverser.setStartDate( self._start_date )
                traverser.includeDeleted( self._include_deleted )
                messageids = traverser.getMessageIds()

                for messageid in messageids:
                    self._messagequeue.put( imaptraverser.ImapMessageID( folder, messageid ))

            

    def process(self):

        threads = []
        for threadidx in range(self._nrThreads):
            thread = threading.Thread(target=processFunction,args=(self,threadidx,))
            thread.start()
            threads.append(thread)

        for thread in threads:
            thread.join()      

        if self._cachefile:
            self._messagecache.write( self._cachefile )

    def processFunction(self,threadidx):
        traverser = self._imapclients[threadidx]
        
        while True:
            try:
                message = self._messagequeue.get_nowait()
            except:
                break

            messageidx = self._nrMessages - self._messagequeue.qsize()

            if self._initialmessagecache.contains( message )==True:
                logging.info( f"Skipping message {messageidx} of {self._nrMessages} (UID: {message.id} in folder {message.folder})")
                continue

            traverser.setFolder( message.folder )

            logging.info(  f"Processing message {messageidx} of {self._nrMessages} (UID: {message.id} in folder {message.folder})")
            imapmessage = traverser.loadMessage( message.id )

            if imapmessage==None:
                logging.error(f"Cannot fetch message UID: {message.id}) in folder {message.folder}")
                continue

            if self._gmailclient.addMessage( imapmessage, message.folder )!=False:
                self._messagecache.list.append( message )
                if threadidx==0 and self._cachefile:
                    self._messagecache.write( self._cachefile )



        
def discoverFolder(obj,threadnr):
    obj.discoverFolder(threadnr)    

def processFunction(obj,threadnr):
    obj.processFunction(threadnr)

