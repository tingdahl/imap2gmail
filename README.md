# imap2gmail

imap2gmail reads e-mails from an IMAP server and pushes that into GMail, using GMail's
REST API's.

## USAGE

  1. Cleanup your IMAP. Every e-mail you don't have to migrate is a bonus.
  2. If your 'trashed' emails are sitting in a separate 'Trash' folder, that folder will be
     converted. If you have e-mailes 'flagged' with the delete flag in IMAP, you have to turn on
     the --include_deleted flag should be used. These messages will be added to the 'Trash' folder in GMail. Note: GMail will permanently remove these e-mails after 30 days.
  3. Specify the imail credetials either on the command line, or with the --credentials-file. Use
     the imap_credentials.example.json file as a template.
  4. Specify the gmail credentials file. This is the credentials of the application, NOT of the
     GMail account. The credentials file can be obtained int the Google Cloud Platform, under the "API / Create credentials" section. The following scope must be supported:
  
         'https://www.googleapis.com/auth/gmail.modify'
  
     When these credentials are created, point to it with the --google_credentials argument.
  5. To avoid transferring new emails every time, specify the --cache_file. When specified,
     a list of transferred messages will be stored locally. Note, changes to these messages (such as new edits of drafts, changes to flags (read, starred, etc)) will not be updated at subsequal runs.
  6. It is recommended that large inboxes are migrated in chunks based on age. Start by  
     specifying the --before_date YYYY-MM-DD, and then run it again with a later date.
  7. At first run, the browser will start, and ask you for permission to run the application. The
     resulting token will be stored in a local file (gmail_token.json).

## Installation

The by far easiest way to use imap2gmail is to use the snapstore:

[![Get it from the Snap Store](https://snapcraft.io/static/images/badges/en/snap-store-white.svg)](https://snapcraft.io/imap2gmail)

### Snapstore

Inststall imap2gmail and keep it up 2 date by

    snap install imap2gmail

### Without installation

The software can be run without any installation. Note that all dependencies must be installed for this option to work.

    git clone https://github.com/tingdahl/imap2gmail.git
    cd imap2gmail
    python3 -m src.imap2gmail.imap2gmail
