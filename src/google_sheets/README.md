mitol-django-google-sheets
---

This is the Open Learning Django Google Sheets core library. The purpose of it is to wrap core functionality around Google Sheets for consumption in more feature specific libraries.

### Setup

`pip install mitol-django-google-sheets`

Add the google sheets app:

```python
INSTALLED_APPS = [
    ...
    "mitol.google_sheets.apps.GoogleSheetsApp",
]
```

### Configuration

First, gather a few of ID-type values from Drive:

1. The "Client ID" and "Client secret" values for the web application credentials you created
    above ([API Console Credentials section](https://console.developers.google.com/apis/credentials))
1. Your API project ID, which you can find in Google Cloud Platform > IAM & Admin > Settings > Project ID.
    Example: `my-api-project-1234567890123`
1. Drive file ID for the request spreadsheets. These can be found by opening a spreadsheet from
    Drive and inspecting the URL. Copy the id for the change of enrollment sheet.
    
    Example: 
    > `https://docs.google.com/spreadsheets/d/THIS_IS_THE_ID_VALUE/edit#gid=0`
    

*If it's not obvious, remove the angle brackets (`<>`) for the actual values.*

```dotenv
MITOL_GOOGLE_SHEETS_DRIVE_CLIENT_ID=<Client ID from step 1>
MITOL_GOOGLE_SHEETS_DRIVE_CLIENT_SECRET=<Client secret from step 1>
MITOL_GOOGLE_SHEETS_DRIVE_API_PROJECT_ID=<Project ID from step 2>
MITOL_GOOGLE_SHEETS_PROCESSOR_APP_NAME=<Name of the app processing the request>
MITOL_GOOGLE_SHEETS_ENROLLMENT_CHANGE_SHEET_ID=<Change of enrollment request sheet ID from step 3>
MITOL_GOOGLE_SHEETS_PROCESS_ONLY_LAST_ROWS_NUM=<Optional: the number of rows to process from the bottom>
```


### Usage
The usage of this library is only possible in conjusction with `mitol-google-sheets-refunds` or `mitol-google-sheets-deferrals`.


Here's an example workflow for making a request for refunds:

1. Fill out and submit the spreadsheet request form. This should add a row to the
 first worksheet in the enrollment code request spreadsheet.
2. Run the management command to process the sheet:
 `./manage.py process_refund_requests -i "<spreadsheet id>"`. This should
 update the "Date Processed" column for the row you added.
3. Check the status of the request in the spreadsheet.


### Integration with mitol-google-sheets

Add this to your settings file:
```python
# import_settings_module, imports the default settings defined in mitol-google-sheets app
from mitol.common.envs import import_settings_modules
import_settings_modules(globals(), "mitol.google-sheets.settings.google_sheets")
```

Create spreadsheed config, for example:
```python
from mitol.google_sheets.utils import SingletonSheetConfig
class RefundRequestSheetConfig(SingletonSheetConfig, subclass_type=<type_of_spreadsheet>):
    """Metadata for the refund request spreadsheet"""
    def __init__(self):
        self.sheet_type = "<type_of_spreadsheet>"
        self.sheet_name = "Refund Request sheet"
        self.worksheet_type = WORKSHEET_TYPE_REFUND
        self.worksheet_name = "Refunds"
```
Subclassing `SingletonSheetConfig` will allow you have your spreadsheet type registered in the base class. This
allows to determine the appropriate config class based on the type of spreadsheet
by running `SingletonSheetConfig.get_subclass_by_type(<type_of_sheet>)`. This is used in various
tasks, and management commands where you want to set up file watch on all current registered
spreadsheets.

In your `urls.py`:
```python
urlpatterns = (
    [
        ...
        path("", include("mitol.google_sheets.urls")),
    ]
)
```


## Developer Setup
This guide contains instructions for hacking on the sheets feature in your own
development environment.

These are steps that only need to be completed once before you start hacking on this feature.

### 1) Dependencies

1. A Google account
1. [ngrok](https://ngrok.com/) – This is a tool that makes your localhost accessible
    to the wider internet. This is necessary for authenticating your locally-running
    xPRO app to make changes to your Google Drive files. If your app is deployed somewhere
    or you have an equivalent tool, ngrok isn't strictly necessary, but these instructions
    assume its use.

### 2) Configure credentials and permissions

1. Create an API project in Google Cloud Platform: https://console.cloud.google.com/home/dashboard
2. Create web application credentials for that project
    1. Visit the credential section of the Google Developer Console: https://console.developers.google.com/apis/credentials
    1. Click Create Credentials > OAuth client ID
    1. Select "Web application", give the credentials an intuitive name ("xPRO auth", et. al.), and submit.
1. Enable the Drive API for your project
    1. Visit the API console: https://console.developers.google.com/apis/library
    1. Select your Google Cloud Platform project from the dropdown at the top of the page.
    1. Find the Drive API, click on it, and enable it. 

### 3) Copy an xPRO Drive project folder

An xPRO Drive folder should have the following artifacts:

1. **Spreadsheets** for each type of "request" we're servicing. As of 7/2020 that includes
  an enrollment code request spreadsheet, and an enrollment change request spreadsheet.
1. **Forms** for submitting new requests to those spreadsheets. As of 7/2020 that includes
  an enrollment code request form, a refund request form, and a deferral request form.
1. A **folder** which is the target for enrollment code assignment sheets that we generate.

**The contents of this folder should be copied from a "template" folder to a folder in your local Drive.** 
There is a template folder on the MIT shared drive, or you can ask a fellow developer to share one. 
**Just chat or email someone on the team to point you to one of these template folders.** 
Once you can access a template folder, do the following to make your own copy:

1. Create a folder on your local Drive. Call it something like "Local xPRO Enrollments".
1. Create an empty subfolder for assignment sheets. Call it something like "Local Assignment Sheets".
1. In the template folder, select the spreadsheets (NOT the forms or any folders), and make a copy of them.
    - *NOTE: This will automatically create copies of the forms since the forms are linked to the spreadsheets already. This is intentional.*
    - *ALSO NOTE: These spreadsheets each have a single test response already entered, and should be visible on the main worksheets. Leave those test responses where they are.*
1. Select the copied spreadsheets *and* forms, and move them to your xPRO enrollments folder that you created above.

Your Drive folder should look something like this when you're done:

![Enrollment Code Request form](images/sheets-drive-folder.png)

### 4) Add initial settings 
Update your .env file with the settings listed above, that begin with `MITOL_GOOGLE_SHEETS...`.

### Authenticating

Your local xPRO needs permissions to be able to read/write to your Drive. This can
be done via OAuth with the help of ngrok.

1. Run ngrok using the nginx port for this app: `ngrok http 8013`
2. Visit the credential section of the Google Developer Console: https://console.developers.google.com/apis/credentials,
select your auth client and update `Authorized redirect URIs` if it changed.
3. Begin domain verification
    1. Visit Webmasters home: https://www.google.com/webmasters/verification/home?hl=en
    1. Enter the **HTTPS** URL that ngrok is exposing (use the full URL including the protocol)
    1. Select Alternate Methods > HTML Tag auth, and copy the "content" attribute value from tag (just the value, not the full HTML tag)
4. Update your .env
 ```dotenv
<your_app_name>_BASE_URL=<Full ngrok HTTPS URL, including protocol>
GOOGLE_DOMAIN_VERIFICATION_TAG_VALUE=<"content" attribute value from step 2.iii>
```
For example
```dotenv
MITX_ONLINE_BASE_URL= https://12345abc6789.ngrok.io
GOOGLE_DOMAIN_VERIFICATION_TAG_VALUE=ETRM2VjAZ3BF52L_ait6r...
```
4. (Re)start containers
5. Click Verify in Domain verify page once containers are fully running. This should succeed.
6. Add Google API console configs ([API console link](https://console.cloud.google.com/apis/dashboard))
    1. Domain verification ([link](https://console.cloud.google.com/apis/credentials/domainverification)): 
        Add the ngrok domain (e.g.: `12345abc6789.ngrok.io`)
    2. OAuth consent screen ([link](https://console.cloud.google.com/apis/credentials/consent))
       1. Under "Test users" click "add users", add your email address
       2. Click "Edit App"
       3. Add a domain in the "Authorized domains" section. **Hit Enter to add**.
       4. **Click Save at the bottom**
    3. Credentials ([link](https://console.cloud.google.com/apis/credentials))
        1. Click on the name of your web app credential in the OAuth 2.0 Client ID section
        1. In the "Authorized redirect URIs" section, click "Add URI", and enter the ngrok HTTPS URL appended with `/sheets/auth-complete/`, e.g.: `https://12345abc6789.ngrok.io/sheets/auth-complete/`
        1. **Click Save**
7. Log into xPRO via Django admin using the ngrok HTTP URL (e.g.: `http://12345abc6789.ngrok.io/admin/`)
8. Authenticate/authorize the app
    1. Navigate to the sheets admin page (`/sheets/admin/`) with the ngrok HTTP URL (e.g.: `http://12345abc6789.ngrok.io/sheets/admin/`)
    1. Click the Authorize button and go through Google OAuth flow
        - *NOTE: You will hit a warning page after selecting your user. To continue, click "Advanced", then click the "Go to \<url\>" link at bottom*
    
### On setting up the google spreadsheets and request form

You need to link the refund form responses form to output to the spreadsheet. You can do that by opening the form 
and Responses->Settings->Select response destination-> Select existing spreadsheet.
When you fill out the form it will create a new worksheet, called something like "Form Response 1". You can
rename this tab to "Refund Form Response".
In the "Refund Form Response" sheet make sure that the "Timestamp" column format is set to "Date" and not to "Date Time".
The main google worksheet gets updated by the "Refund Response" worksheet by the following query:

```markdown
={QUERY({'Refund Form Response'!A2:G, ARRAYFORMULA(if(isblank('Refund Form Response'!A2:A),"",ROW('Refund Form Response'!A2:G)))},"SELECT Col8, Col1, Col3, Col4, Col2, Col5, Col6, Col7",0)}
```
Add this query to the first data row and column (4:A).