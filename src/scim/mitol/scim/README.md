## SCIM

## Prerequisites

- You need the following a local [Keycloak](https://www.keycloak.org/) instance running. Note which major version you are running (should be at least 26.x).
  - You should have custom user profile fields setup on your `olapps` realm:
    - `fullName`: required, otherwise defaults
    - `emailOptIn`: defaults

## Install the scim-for-keycloak plugin

Sign up for an account on https://scim-for-keycloak.de and follow the instructions here: https://scim-for-keycloak.de/documentation/installation/install

## Configure SCIM

In the SCIM admin console, do the following:

### Configure Remote SCIM Provider

- In django-admin, go to OAuth Toolkit and create a new access token
- Go to Remote SCIM Provider
- Click the `+` button
- Specify a base URL for your learn API backend: `http://<IP_OR_HOSTNAME>:8063/scim/v2/`
- At the bottom of the page, click "Use default configuration"
- Add a new authentication method:
  - Type: Long Life Bearer Token
  - Bearer Token: the access token you created above
- On the Schemas tab, edit the User schema and add these custom attributes:
  - Add a `fullName` attribute and set the Custom Attribute Name to `fullName`
  - Add an attribute named `emailOptIn` with the following settings:
    - Type: integer
    - Custom Attribute Name: `emailOptIn`
- On the Realm Assignments tab, assign to the `olapps` realm
- Go to the Synchronization tab and perform one:
  - Identifier attribute: email
  - Synchronization strategy: Search and Bulk
