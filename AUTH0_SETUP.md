# Auth0 setup (not deployed)

This branch protects ChatGPT-to-MCP with FastMCP's Auth0 OAuth proxy. The
MCP-to-PHP Bearer credential stays separate and is never given to ChatGPT.
Hosted sign-in has not been tested: a real tenant/application is still needed.
The PHP dashboard still needs its browser session/login implementation before
any production rollout of the PHP guard. Do not merge/deploy either branch yet.

## Create the Auth0 resources

1. Create/select your Auth0 tenant. Create a **Regular Web Application** for
   CoupleHub MCP, using the Authorization Code grant. Enable Refresh Token grant
   and API offline access if persistent connections are desired.
2. Add a **Custom API** with an identifier you choose, for example
   `https://couplehub.example/mcp-access`, using RS256. Define the permission
   `couplehub:access`. This identifier is an audience; it need not host a website.
3. Set the application's Allowed Callback URLs to exactly
   `<MCP public HTTPS origin>/auth/callback`. This is the proxy-to-Auth0 callback,
   not ChatGPT's callback. Do not change the live MCP connection until rollout.
4. Restrict access to the household. Merely having an Auth0 account or a scope
   named `couplehub:access` does not restrict who can sign up. Add a Post Login
   Action, bind it to the Login flow, and configure its secrets
   `COUPLEHUB_MCP_CLIENT_ID` and `COUPLEHUB_ALLOWED_USER_IDS` (comma-separated
   Auth0 user IDs, available in User Management). For example:

   ```javascript
   exports.onExecutePostLogin = async (event, api) => {
     const client = event.secrets.COUPLEHUB_MCP_CLIENT_ID;
     if (!client) {
       api.access.deny('CoupleHub access policy is not configured');
       return;
     }
     if (event.client.client_id !== client) return;
     const allowed = (event.secrets.COUPLEHUB_ALLOWED_USER_IDS || '')
       .split(',').map(x => x.trim()).filter(Boolean);
     if (!allowed.includes(event.user.user_id)) {
       api.access.deny('This account is not allowed to access CoupleHub');
       return;
     }
     api.accessToken.addScope('couplehub:access');
   };
   ```

   Verify an unlisted test account is denied. Disabling public signup is also
   recommended, but does not replace the allowlist. Test and deploy the Action
   in Auth0 and attach it to the flow before exposing a privileged backend.

## MCP environment variables

| Variable | Meaning |
| --- | --- |
| `COUPLEHUB_AUTH0_DOMAIN` | Tenant hostname, e.g. `your-tenant.au.auth0.com` |
| `COUPLEHUB_AUTH0_CLIENT_ID` | Regular Web Application client ID |
| `COUPLEHUB_AUTH0_CLIENT_SECRET` | Application secret, entered securely |
| `COUPLEHUB_AUTH0_AUDIENCE` | Custom API identifier |
| `COUPLEHUB_MCP_PUBLIC_URL` | MCP server's public HTTPS origin, without `/sse` |
| `COUPLEHUB_MCP_REDIRECT_URIS` | JSON array of exact HTTPS callbacks supplied by the ChatGPT connector; no wildcards |
| `COUPLEHUB_API_BASE` | Explicit PHP backend HTTPS URL |
| `COUPLEHUB_API_TOKEN` | PHP service token, entered securely; same as PHP runtime |
| `FASTMCP_HOME` | Persistent private writable directory for encrypted OAuth state |

Auth0 is the default. Missing configuration prevents startup; it never falls
back to anonymous access. Consent is enabled. Do not disable consent or allow
arbitrary callback URLs. Preserve the client secret and OAuth state across
restarts; rotating the secret may require reconnecting clients. A single Render
instance can use a private persistent disk; multi-instance deployment requires
shared OAuth state and is not configured by this branch. Protect state backups
as credentials. Do not store them in Git or a public web directory.

The public URL determines metadata, issuer and callback addresses. Changing it
requires updating Auth0 callbacks and reconnecting ChatGPT. Provide the exact
callback shown by the connector rather than guessing it from examples.

## Validation

Install `requirements.txt`, then run:

```sh
python -m unittest discover -s tests -v
python tests/integration_auth.py
```

The suite uses fixture OIDC discovery with the real Auth0 provider and middleware
to verify missing/invalid token rejection, OAuth discovery, required scope and
configuration validation. It does not contact an Auth0 tenant or prove hosted
login. The integration test uses explicit `COUPLEHUB_AUTH_MODE=local`, loopback
PHP and the imported local MariaDB. Never configure local mode on hosting.
The standalone entry point binds only loopback in local mode; do not mount this
mode behind a public ASGI/WSGI server or forward its port.

Before deployment, test the real Auth0 round trip, ChatGPT callback, allowed and
denied accounts, required scope, token expiry/refresh and reconnect after server
restart. Browser dashboard sessions are still separate outstanding work.

Render's `python server.py` ASGI path is the supported test target. The legacy
`wsgi.py` adapter still requires `a3wsgi`, which is absent from requirements;
shared-hosting WSGI deployment is not validated here.
