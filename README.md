# imap2gmail

imap2gmail reads e-mails from an IMAP server and pushes that into GMail, using GMail's
REST API's.

# USAGE

  #. Cleanup your IMAP. Every e-mail you don't have to migrate is a bonus.
  #. If your 'trashed' emails are sitting in a separate 'Trash' folder, that folder will be
     converted. If you have e-mailes 'flagged' with the delete flag in IMAP, you have to turn on
     the --include_deleted flag should be used. These messages will be added to the 'Trash' folder in GMail. Note: GMail will permanently remove these e-mails after 30 days.
  #. Specify the imail credetials either on the command line, or with the credentials-file. Use
     the imap_credentials.example.json file as a template.
  #. Specify the gmail credentials file. This is the credentials of the application, NOT of the
     GMail account. The credentials file can be obtained int the Google Cloud Platform, under the "API / Create credentials" section. The following scopes must be supported:
        'https://www.googleapis.com/auth/gmail.labels',
        'https://www.googleapis.com/auth/gmail.insert',
    When these credentials are created, point to it with the --google_credentials argument.
  #. To avoid transferring new emails every time, specity the --cache_file. When specified,
     a list of transferred messages will be stored locally. Note, changes to these messages (such as new edits of drafts, changes to flags (read, starred, etc)) will not be updated at subsequal runs.
  #. It is recommended that large inboxes are migrated in chunks based on age. Start by  
     specifying the --before_date YYYY-MM-DD, and then run it again with a later date.
  #. At first run, the browser will start, and ask you for permission to run the application. The
     resulting token will be stored in a local file.
