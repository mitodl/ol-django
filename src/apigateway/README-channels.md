# apigateway for Django Channels

Django Channels includes an `AuthMiddleware` that can use an existing Django session to retrieve the current user. This works with the standard Django middleware provided by the app, but there has to be a request to the Django side of the app _first_, or there won't be a session for it to retrieve the user from.

If this isn't the case for your app - i.e., you're opening a WebSocket connection from a totally separate frontned - you will need to use the `ApisixAuthMiddleware` (or, more specifically, the `ApisixAuthMiddlewareStack`), which will parse the APISIX headers to ge the user to load.

This middleware uses the provided `ApisixRemoteUserBackend` so it will use the settings that are described in the main `README.md`.

## Implementing

A wrapper is included that wraps the middleware in `CookieMiddleware` and `SessionMiddleware` as a convenience. This is called `ApisixAuthMiddlewareStack` and is located in `middleware_channels.py`. You can use it in your `asgi.py` (or wherever you've set up your ProtocolTypeRouter) like this:

```python
from mitol.apigateway.middleware_channels import ApisixAuthMiddlewareStack

application = ProtocolTypeRouter({
    "websocket": AllowedHostsOriginValidator(
            ApisixAuthMiddlewareStack(
                URLRouter(urlpatterns)
        )
    ),
})
```

Your consumers should then see the user in the scope as `scope["user"]`. This will be an AnonymousUser if there's no header or the user isn't found, or the relevant user object otherwise. This will respect your settings for creating or updating users based on the APISIX headers - it uses the same backend as the regular middleware.

## Considerations

WebSocket requests start with an HTTP handshake. This is where headers are attached to the request, and is where the middleware will get the data that it needs to find the user. Once the handshake is complete, the connection stays open and the protocol switches to the WebSocket protocol, and the connection stays open until it's explicitly closed.

This means that changes in the upstream session aren't propogated down into open WebSocket connections. If the user's APISIX session changes - the user logs out, or the session expires - any open WebSockets that the user has will still have the user information associated with them. Your app should account for this - maybe by polling a Django-side API or restarting the WebSocket connection occasionally.
