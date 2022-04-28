# List number of messages in INBOX folder
# and print details of the messages that are not deleted

import imaptraverser
import logging
import argparse


logging.basicConfig(level=logging.INFO )

parser = argparse.ArgumentParser()

# IMAP server arguments
parser.add_argument("--imap_host")
parser.add_argument("--imap_user")
parser.add_argument("--imap_password")
parser.add_argument("--imap_credentials_file" )

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

while traverser.nextMessage():
    logging.info(  f"Processing message {traverser.currentMessageIdx()+1} of {traverser.nrMessagesInFolder()} (UID: {traverser.currentMessageID().id}) in folder {traverser.currentFolderIdx()+1} of {traverser.nrFolders()}: {traverser.currentFolder()}")


#        for msgid, data in response.items():
#            logging.info(f"Pro")
#            print(
#                "   ID %d: %d bytes, flags=%s, envelope=%s" % (msgid, data[b"RFC822.SIZE"], data[b"FLAGS"], data[b"ENVELOPE"])
#            )
#        return 