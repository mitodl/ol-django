## SCIM

## Prerequisites

- You need the following a local [Keycloak](https://www.keycloak.org/) instance
  running. Note which major version you are running (should be at least 26.x).
  - You should have custom user profile fields setup on your `olapps` realm:
    - `fullName`: required, otherwise defaults
    - `emailOptIn`: defaults

## Install the scim-for-keycloak plugin

Sign up for an account on https://scim-for-keycloak.de and follow the
instructions here:
https://scim-for-keycloak.de/documentation/installation/install

## Configure SCIM

In the SCIM admin console, do the following:

### Configure Remote SCIM Provider

- Create the access token Keycloak will send, owned by a staff service account:
  `./manage.py create_scim_token --username scim-service`. It prints the
  generated token; pass `--token <value>` to set a known one instead (the
  command is idempotent for a given token). The default scope is `scim`.
  Re-running without `--token` adds a token and leaves the earlier ones valid
  until they expire, so delete the old one in django-admin when rotating.
- Go to Remote SCIM Provider
- Click the `+` button
- Specify a base URL for your learn API backend:
  `http://<IP_OR_HOSTNAME>:8063/scim/v2/`
- At the bottom of the page, click "Use default configuration"
- Add a new authentication method:
  - Type: Long Life Bearer Token
  - Bearer Token: the access token you created above
- On the Schemas tab, edit the User schema and add these custom attributes:
  - Add a `fullName` attribute and set the Custom Attribute Name to `fullName`
  - Add an attribute named `emailOptIn` with the following settings:
    - Type: integer
    - Custom Attribute Name: `emailOptIn`
  - Add an `emailVerified` attribute (using the option specific to this in the
    dropdown)
- On the Realm Assignments tab, assign to the `olapps` realm
- Go to the Synchronization tab and perform one:
  - Identifier attribute: email
  - Synchronization strategy: Search and Bulk
