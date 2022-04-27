# List number of messages in INBOX folder
# and print details of the messages that are not deleted

import imaptraverser
import logging

logging.basicConfig(level=logging.INFO )

imapcredentials = imaptraverser.ImapCredentials( "imap_credentials.json")
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