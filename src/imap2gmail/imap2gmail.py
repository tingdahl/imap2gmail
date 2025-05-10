#
# Copyright © 2022 Tingdahl ICT Management
# Licenced under the MIT licence, see license.md
#

import datetime
import multiprocessing
import os
import sys
from .imapreader import ImapCredentials
import logging
import argparse
from .imap2gmailprocessor import Imap2GMailProcessor
from .gmailimapimporter import GMailImapImporter

CURRENT_DIR = './'

# Checks file access


def checkFileAccess(filename, read):
    if filename is None:
        return True

    if read:
        if os.path.exists(filename) is False:
            logging.critical(f"{filename} is not found or accessible")
            return False

        if os.access(filename, os.R_OK) is False:
            logging.critical(f"{filename} is not readable")
            return False
    else:
        if os.path.exists(filename):
            if os.access(filename, os.W_OK) is False:
                logging.critical(f"{filename} is not writable")
                return False
        else:
            directory = os.path.dirname(filename)
            if directory == '':
                directory = CURRENT_DIR
            if os.access(directory, os.W_OK) is False:
                logging.critical(f"{filename} is not writable")
                return False

    return True


def imap2gmail():
    logging.basicConfig(level=logging.INFO)

    parser = argparse.ArgumentParser()

    # Google credential file
    parser.add_argument("--google_credentials",
                        help="Credentials file for the application,"
                        " as downloaded from GCP.",
                        required=True)

    # IMAP server arguments
    imapgroup = parser.add_mutually_exclusive_group()
    imapgroup.add_argument("--imap_credentials_file")
    imapcligroup = imapgroup.add_argument_group()

    imapcligroup.add_argument("--imap_host")
    imapcligroup.add_argument("--imap_user")
    imapcligroup.add_argument("--imap_password")

    # Cache file
    parser.add_argument("--cache_file",
                        default="./imap2gmail_cache.json",
                        help="File where a list of completed e-mails "
                        "will be kept")

    # MT
    parser.add_argument("--max_threads",
                        help="Maximum number of threads. "
                        "Default is 16 threads.")

    parser.add_argument("--include_deleted", action='store_const', const=True,
                        help="Should messaged marked as deleted be included.")

    # Login/logout
    parser.add_argument("--login", action='store_const', const=True,
                        help="Log in to GMail and store the credentials.")
    parser.add_argument("--logout", action='store_const', const=True,
                        help="Remove any GMail credentials")
    parser.add_argument("--reauthenticate", action='store_const', const=True,
                        help="Force new authentification by Google.")

    # Date limits
    parser.add_argument('--start_date',
                        type=lambda s: datetime.datetime.strptime(s,
                                                                  '%Y-%m-%d'),)
    parser.add_argument('--before_date',
                        type=lambda s: datetime.datetime.strptime(s,
                                                                  '%Y-%m-%d'))

    try:
        args = parser.parse_args()
    except Exception:
        parser.print_help()
        return False

    # Check general parsing stuff
    if args.google_credentials is None:
        parser.print_help()
        return False

    # Check file permissions
    permissionError = False
    if os.access(CURRENT_DIR, os.W_OK) is False:
        logging.critical("No write access in current directory.")
        permissionError = True

    if checkFileAccess(args.imap_credentials_file, True) is False or \
       checkFileAccess(args.google_credentials, True) is False or \
       checkFileAccess(args.cache_file, False) is False:
        permissionError = True

    if permissionError:
        logging.error(
            f"Not sufficient file system access. If {sys.argv[0]} is installed"
            " through a snap, the program must be run from the user's home"
            " directory, or a subdirectory thereof. All files must also be in"
            " the users home directory, or a subdirectory thereof.")
        return False

    if args.login and args.logout:
        logging.error("Both login and logout given. Select one ore the other")
        return False

    gmailclient = GMailImapImporter()

    if args.logout:
        gmailclient.logout()
        return True

    if gmailclient.login(args.google_credentials,
                         args.reauthenticate is not None) is False:
        logging.error("Cannot login to GMail")
        return False

    if args.login:
        logging.info("Logged into GMail")
        return True

    # Parse imap creds
    imapcredentials = ImapCredentials()

    if args.imap_credentials_file:
        imapcredentials.loadJsonFile(args.imap_credentials_file)
    else:
        if args.imap_host is None or \
                args.imap_user is None or \
                args.imap_password is None:
            print("You most specify either imap_credentials file or imap_host,"
                  " imap_user, and imap_password")
            parser.print_help()
            return False

        imapcredentials._host = args.imap_host
        imapcredentials._user = args.imap_user
        imapcredentials._password = args.imap_password

    if imapcredentials.isOK() is False:
        logging.error("IMAP Credentials not read")
        return False

    maxnrthreads = 16
    if args.max_threads:
        maxnrthreads = int(args.max_threads)

    nrthreads = min(multiprocessing.cpu_count()*2, maxnrthreads)
    nrthreads = max(nrthreads, 1)

    processor = Imap2GMailProcessor(imapcredentials, gmailclient, nrthreads,
                                    args.start_date, args.before_date,
                                    args.include_deleted,
                                    args.cache_file)

    if processor.isOK() is False:
        return False

    if processor.discoverMessages() is False:
        return False

    processor.process()

    return True


if __name__ == "__main__":
    if imap2gmail() is True:
        sys.exit(0)

    sys.exit(1)
