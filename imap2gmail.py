# List number of messages in INBOX folder
# and print details of the messages that are not deleted

import datetime
import multiprocessing
import threading
import imaptraverser
import gmailclient
import logging
import argparse
import imap2gmailprocessor

logging.basicConfig( level=logging.INFO )

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
    imapcredentials.loadJsonFile( args.imap_credentials_file )

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

processor = imap2gmailprocessor.Imap2GMail( imapcredentials, args.google_credentials, multiprocessing.cpu_count()*2,
                 args.start_date, args.before_date,args.include_deleted,
                 args.cache_file )

processor.discoverMessages()
processor.process()



    
    