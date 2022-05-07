# List number of messages in INBOX folder
# and print details of the messages that are not deleted

import datetime
import multiprocessing
import threading
import imaptraverser
import gmailclient
import logging
import argparse

class Imap2GMail:
    def __init__(self, imap_credentials, google_credentials, nrthreads,
                 start_date, before_date,include_deleted, cache_file  ):
        self._imapcredentials = imap_credentials
        self._nrThreads = nrthreads
        self._start_date = start_date
        self._before_date = before_date
        self._include_deleted=include_deleted
        self._message_cache_file = cache_file



        maintraverser = imaptraverser.ImapTraverser( self._imapcredentials )
        maintraverser.retrieveFolders()

        self._lock = multiprocessing.Lock()
        self._currentFolderIdx = 0

        self._folders = maintraverser.getFolders()

        self._gmailclient = gmailclient.GMailClient( google_credentials )
        self._gmailclient.loadLabels()
        self._gmailclient.addImapFolders( self._folders )
    
    def process(self):
        threads = []
        for threadidx in range(self._nrThreads):
            thread = threading.Thread(target=threadFunction,args=(self,threadidx,))
            thread.start()
            threads.append(thread)

        for thread in threads:
            thread.join()

    def threadFunction(self,threadnr):
        traverser = imaptraverser.ImapTraverser( self._imapcredentials )
        traverser.setBeforeDate( self._before_date )
        traverser.setStartDate( self._start_date )
        traverser.includeDeleted( self._include_deleted )

        folderidx = 0
        while folderidx<len(self._folders):
            self._lock.acquire()
            folderidx = self._currentFolderIdx
            self._currentFolderIdx += 1
            self._lock.release()

            if folderidx>=len(self._folders):
                break

            currentfolder = self._folders[folderidx]
            traverser.setFolder( currentfolder )

            messagecache = None
            if self._message_cache_file:
                messagecache = imaptraverser.ImapMessageIDList()
                cachefile = self._message_cache_file + "_" + currentfolder + ".json"

                messagecache.load( cachefile )

            while traverser.nextMessage():
                messageid = traverser.currentMessageID()
                if messagecache.contains( messageid )==False:

                    logging.info(  f"Thread {threadnr}: Processing message {traverser.currentMessageIdx()+1} of {traverser.nrMessagesInFolder()} (UID: {traverser.currentMessageID().id}) in folder {folderidx+1} of {len(self._folders)}: {currentfolder}")
                    message = traverser.getCurrentMessage()
                    if message==None:
                        logging.error(f"Thread {threadnr}: Cannot fetch message UID: {traverser.currentMessageID().id}) in folder {traverser.currentFolderIdx()+1}")
                        continue

                    self._gmailclient.addMessage( message, messageid.folder )

                    messagecache.list.append( messageid )
                    if args.cache_file:
                        messagecache.write( cachefile )
                else:
                    logging.info( f"Thread {threadnr}: Skipping message {traverser.currentMessageIdx()+1} of {traverser.nrMessagesInFolder()} (UID: {traverser.currentMessageID().id}) in folder {folderidx+1} of {len(self._folders)}: {currentfolder}")
            

def threadFunction(obj,threadnr):
    obj.threadFunction(threadnr)

logging.basicConfig(level=logging.INFO )

parser = argparse.ArgumentParser()

# IMAP server arguments
parser.add_argument("--imap_host")
parser.add_argument("--imap_user")
parser.add_argument("--imap_password")
parser.add_argument("--imap_credentials_file" )

# Google credential file
parser.add_argument("--google_credentials", help="Credentials file for the application, as downloaded from GCP." )

# Cache file
parser.add_argument("--cache_file", help="File where a list of completed e-mails will be kept" )

parser.add_argument("--include_deleted", action='store_const', const=True,
                     help="Should messaged marked as deleted be included.")
parser.add_argument('--start_date',type=lambda s: datetime.datetime.strptime(s, '%Y-%m-%d'),)
parser.add_argument('--before_date',type=lambda s: datetime.datetime.strptime(s, '%Y-%m-%d'))

args = parser.parse_args()

#Parse imap creds
imapcredentials = imaptraverser.ImapCredentials()

if args.imap_credentials_file:
    imapcredentials.readFile( args.imap_credentials_file )

else:
    if args.imap_host==False or args.imap_user==False or args.imap_password==False:
        print("You most specify either imap_credentials file or imap_host, imap_user, and imap_password")
        exit(1)

    imapcredentials.host = args.imap_host
    imapcredentials.user = args.imap_user
    imapcredentials._password = args.imap_password


if imapcredentials.isOK()==False:
    logging.error("Credentials not read")
    exit(1)

processor = Imap2GMail( imapcredentials, args.google_credentials, multiprocessing.cpu_count(),
                 args.start_date, args.before_date,args.include_deleted,
                 args.cache_file )

processor.process()



    
    