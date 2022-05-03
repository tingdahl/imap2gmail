# List number of messages in INBOX folder
# and print details of the messages that are not deleted

import datetime
import imaptraverser
import gmailclient
import logging
import argparse


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

parser.add_argument("--include_deleted", help="Should pruned messages be included.")
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



traverser = imaptraverser.ImapTraverser( imapcredentials )
if args.start_date:
    traverser.setStartDate( args.start_date )

if args.before_date:
    traverser.setBeforeDate( args.before_date )

gmailclient = gmailclient.GMailClient( args.google_credentials )
gmailclient.loadLabels()
gmailclient.addImapFolders( traverser.getFolders() )

messagecache = imaptraverser.ImapMessageIDList()
cachechange = False

if args.cache_file:
    messagecache.load( args.cache_file )

while traverser.nextMessage():
    messageid = traverser.currentMessageID()
    if messagecache.contains( messageid )==False:

        logging.info(  f"Processing message {traverser.currentMessageIdx()+1} of {traverser.nrMessagesInFolder()} (UID: {traverser.currentMessageID().id}) in folder {traverser.currentFolderIdx()+1} of {traverser.nrFolders()}: {traverser.currentFolder()}")
        message = traverser.getCurrentMessage()
        if message==None:
            logging.error(f"Cannot fetch message UID: {traverser.currentMessageID().id}) in folder {traverser.currentFolderIdx()+1}")
            continue

        gmailclient.addMessage( message, messageid.folder )

        messagecache.list.append( messageid )
        cachechange = True
    
#Write completed cache
if args.cache_file and cachechange:
    messagecache.write( args.cache_file )