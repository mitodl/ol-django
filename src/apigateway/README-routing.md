# APISIX Routing and Config

## Background

Letting APISIX manage authentication for your Django app requires some care in setting up your routes in APISIX.

All Django endpoints need to be covered by an APISIX route so that APISIX will know to handle the request. APISIX's routing configuration is pretty flexible, and can match requests using lists and wildcards; in addition, routes can be ordered, so some routes can take precedence over others. Routes are also how you configure APISIX to perform any processing and transformation tasks that need to happen during the request's lifecycle. This is done using plugins, and there are plugins for a lot of different things, including authentication.

We use the `openid-connect` plugin to provide authentication for APISIX routes. As the name suggests, the plugin uses OpenID Connect to authenticate the user against an identity provider service, and then passes the user data on to the application for its purposes. It uses a user session that is maintained within APISIX itself to store the user's authenticated data (as a Web application generally would). If that user session is invalid or nonexistant, the plugin may take one of three actions, depending on the `unauth_action` setting:
- If set to `auth`, the user is redirected to the identity provider.
- If set to `deny`, the request is denied and APISIX returns a HTTP 401.
- If set to `pass`, the request is allowed, but as an anonymous user.

If the plugin does see a valid session, it will attach a few headers to the request before it is sent on to the Django application. These include `X-Userinfo` and `X-ID-Token` and `X-Refresh-Token`. Of these, the `X-Userinfo` is the most useful as it contains the user profile data that was retrieved from the identity provider when the session began. (The `apigateway` code uses the `X-Userinfo` header.)

> Note that you can turn these headers _off_ in the plugin configuration, but you can't rename them. (Additionally, you should not turn off the `X-Userinfo` header.)

## Configuration

With this in mind, it's typically best to separate your Django app's endpoints into three buckets:

- Explicitly unauthenticated: endpoints that do not need any sort of user data at all.
- Uses user data: endpoints that can use user data.
- Explicitly requires authentication: endpoints that absolutely _must_ have a valid user session.

These buckets correspond to these three `openid-connect` plugin configuration scenarios:

- Explicitly unauthenticated: no `openid-connect` plugin configured. Not only will APISIX do no authenticated user check here, it will also _not_ send _any_ user data to the application, even if an established session exists.
- Uses user data: `openid_connect` is defined and configured for the route, and is set with `unauth_action: "pass"`.
- Explicitly requires authentication: `openid_connect` is configured with `unauth_action: "auth"`.

The "Uses user data" bucket is the recommended bucket for **most** of your Django endpoints, if not **all** of them. The reason for this is that it allows _authorization_ to be done within the Django app, while _authentication_ remains in the APISIX realm. That is, APISIX makes sure there's a user but your app maintains its own logic for determining if that user is allowed to perform the requested action.

This also solves a problem that happens with REST API endpoints: if they are set up in APISIX with `unauth_action: "auth"`, APISIX will redirect the user if it doesn't see a valid session. This can break the client app; especially when using `fetch`, `axios`, or similar in the frontend, the redirect won't be meaningful because it will be redirecting a client expecting (ex.) JSON to a full web page. (In practice, this results in a CORS error.)

> **Using deny:** You can also set routes up to deny users that don't have a session via APISIX. However, while this would make API clients happy, it does blur the line between authorization and authentication; your app will still need to authorize the user if they have a valid session anyway.

It's recommend that the _only_ route that you have that is in the "Explicitly requires authentication" bucket is one that is designated for establishing a session within your application (as a whole). There needs to be at least one route for which APISIX will enforce authentication, or the APISIX session will never be established.

This route doesn't necessarily need to be an actual endpoint within your application. APISIX includes a `redirect` plugin that can be used to create a route that requires auth and then redirects the user to an actual endpoint within your application. You may want a specific endpoint in your app for this, though, especially if you need to do any post-login processing. (For instance, if your application needs to flag new users so they can go through an onboarding process, you may want to have a login endpoint within your app that contains the logic for that.)

### The Logout Route Is Special

`openid-connect` uses `/logout` as the route for logging the user out. You can change this with the `logout_path` setting. This does not get passed on to the application; instead, set `post_logout_redirect_uri` to the URL you want to redirect to.

It's recommended to set up a second redirect route to either add or remove the trailing slash from the logout URI. An example is below.


## Example Configuration

In this scenario, the application exposes a frontend at the root URL (`/`) and has a REST API available at `/api/`. Django Admin is available at `/admin/`. The frontend is a SPA and does not use authentication.

### Basic/catchall configuration

This takes care of the frontend and any missed routes. It also sets up the (single) upstream:

```yaml
upstreams:
  - id: 1
    nodes:
      "nginx:8073": 1
    type: roundrobin

routes:
  - id: 1
    name: "app-wildcard"
    desc: "General route for the application, includes user data if any."
    priority: 0
    upstream_id: 1
    plugins:
      openid-connect:
        client_id: ${{KEYCLOAK_CLIENT_ID}}
        client_secret: ${{KEYCLOAK_CLIENT_SECRET}}
        discovery: ${{KEYCLOAK_DISCOVERY_URL}}
        realm: ${{KEYCLOAK_REALM}}
        scope: "openid profile ol-profile"
        bearer_only: false
        introspection_endpoint_auth_method: "client_secret_post"
        ssl_verify: false
        session:
          secret: ${{APISIX_SESSION_SECRET_KEY}}
        logout_path: "/logout"
        post_logout_redirect_uri: ${{APP_LOGOUT_URL}}
        unauth_action: "pass"
    uris:
      - "/*"

```

This next route adds a `login` route that redirects to the user's dashboard:

```yaml
  - id: 1
    name: "app-login"
    desc: "Establish a session for the user."
    priority: 10
    upstream_id: 1
    plugins:
      openid-connect:
        client_id: ${{KEYCLOAK_CLIENT_ID}}
        client_secret: ${{KEYCLOAK_CLIENT_SECRET}}
        discovery: ${{KEYCLOAK_DISCOVERY_URL}}
        realm: ${{KEYCLOAK_REALM}}
        scope: "openid profile ol-profile"
        bearer_only: false
        introspection_endpoint_auth_method: "client_secret_post"
        ssl_verify: false
        session:
          secret: ${{APISIX_SESSION_SECRET_KEY}}
        logout_path: "/logout"
        post_logout_redirect_uri: ${{APP_LOGOUT_URL}}
        unauth_action: "auth"
      redirect:
      	uri: "/dashboard"
    uris:
      - "/login*"

```

Note that this is configured with the URI `/login*`; this will catch `/login` and `/login/`. It'll also match if the user appends anything to the URI (such as a query string or anything else). Also note that the priority is set to 10 here - higher numbers are higher priority and this ensures that this route takes precedence over the wildcard route that was set first. It is also set with `unauth_action: "auth"` explicitly for clarity. The app itself does not contain a "/login" endpoint.

This final route strips the trailing slash from `/logout`:

```yaml
  - id: 3
    name: "logout-redirect"
    desc: "Strip trailing slash from logout redirect."
    priority: 10
    upstream_id: 1
    uri: "/logout/*"
    plugins:
      redirect:
        uri: "/logout"

```
