# 
# Copyright © 2022 Tingdahl ICT Management
# Licenced under the MIT licence, see license.md
# 

# List number of messages in INBOX folder
# and print details of the messages that are not deleted

import datetime
import multiprocessing
import imapreader
import logging
import argparse
import imap2gmailprocessor

def imap2gmail():
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

    # MT
    parser.add_argument( "--max_threads", help="Maximum number of threads. Default is 16 threads.")

    parser.add_argument("--include_deleted", action='store_const', const=True,
                        help="Should messaged marked as deleted be included.")
    parser.add_argument('--start_date',type=lambda s: datetime.datetime.strptime(s, '%Y-%m-%d'),)
    parser.add_argument('--before_date',type=lambda s: datetime.datetime.strptime(s, '%Y-%m-%d'))

    args = parser.parse_args()

    #Parse imap creds
    imapcredentials = imapreader.ImapCredentials()

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

    maxnrthreads = 16
    if args.max_threads:
        maxnrthreads = int(args.max_threads)

    nrthreads = min(multiprocessing.cpu_count()*2,maxnrthreads)

    processor = imap2gmailprocessor.Imap2GMailProcessor( imapcredentials, args.google_credentials, nrthreads,
                    args.start_date, args.before_date,args.include_deleted,
                    args.cache_file )

    processor.discoverMessages()
    processor.process()

if __name__ == "__main__":
    imap2gmail()

    
    