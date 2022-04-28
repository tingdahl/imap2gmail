# List number of messages in INBOX folder
# and print details of the messages that are not deleted

import pickle
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

parser.add_argument("--google_credentials" )

parser.add_argument("--cache_file" )

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
gmailclient = gmailclient.GMailClient( args.google_credentials )

messagecache = imaptraverser.ImapMessageIDList()
cachechange = False

if args.cache_file:
    messagecache.load( args.cache_file )

while traverser.nextMessage():
    messageid = traverser.currentMessageID()
    if messagecache.contains( messageid )==False:

        logging.info(  f"Processing message {traverser.currentMessageIdx()+1} of {traverser.nrMessagesInFolder()} (UID: {traverser.currentMessageID().id}) in folder {traverser.currentFolderIdx()+1} of {traverser.nrFolders()}: {traverser.currentFolder()}")
        messagecache.list.append( messageid )
        cachechange = True
    

if args.cache_file and cachechange:
    messagecache.write( args.cache_file )
   


#        for msgid, data in response.items():
#            logging.info(f"Pro")
#            print(
#                "   ID %d: %d bytes, flags=%s, envelope=%s" % (msgid, data[b"RFC822.SIZE"], data[b"FLAGS"], data[b"ENVELOPE"])
#            )
#        return 