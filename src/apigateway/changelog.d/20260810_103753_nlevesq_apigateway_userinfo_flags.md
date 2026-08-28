### Changed

- `MITOL_APIGATEWAY_USERINFO_CREATE` and `MITOL_APIGATEWAY_USERINFO_UPDATE` are now read from the environment, so they can be configured per-deployment without a settings override.
- **Breaking:** `MITOL_APIGATEWAY_USERINFO_UPDATE` now defaults to `False`. The userinfo the gateway attaches to a request is only refreshed at login, so updating on every request clobbers newer user data written by a backchannel process (SCIM, etc). Apps that rely on the middleware to keep users in sync must now set `MITOL_APIGATEWAY_USERINFO_UPDATE=True` explicitly.
