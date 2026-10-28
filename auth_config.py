"""Fail-closed Auth0 configuration for the MCP resource server."""
import json
import os
import re
from urllib.parse import urlsplit

from fastmcp.server.auth.providers.auth0 import Auth0Provider


def required(name):
    value = os.environ.get(name, '').strip()
    if not value:
        raise RuntimeError(f'{name} must be configured')
    return value


def https_url(value, name, origin_only=False):
    url = urlsplit(value)
    if (url.scheme != 'https' or not url.hostname or url.username or url.password
            or url.query or url.fragment or '*' in value
            or (origin_only and url.path not in ['', '/'])):
        raise RuntimeError(f'{name} must be an HTTPS '+('origin' if origin_only else 'URL'))
    return value.rstrip('/') if origin_only else value


def build_auth():
    mode = os.environ.get('COUPLEHUB_AUTH_MODE', 'auth0')
    if mode == 'local':
        url = urlsplit(required('COUPLEHUB_API_BASE'))
        if url.scheme != 'http' or url.hostname not in {'localhost', '127.0.0.1', '::1'}:
            raise RuntimeError('Local auth mode requires a loopback HTTP backend')
        return None
    if mode != 'auth0':
        raise RuntimeError('COUPLEHUB_AUTH_MODE must be auth0 or local')

    domain = required('COUPLEHUB_AUTH0_DOMAIN')
    if not re.fullmatch(r'[A-Za-z0-9](?:[A-Za-z0-9.-]*[A-Za-z0-9])?', domain) or '.' not in domain:
        raise RuntimeError('COUPLEHUB_AUTH0_DOMAIN must be a tenant hostname, without a scheme or path')
    client_id = required('COUPLEHUB_AUTH0_CLIENT_ID')
    client_secret = required('COUPLEHUB_AUTH0_CLIENT_SECRET')
    audience = required('COUPLEHUB_AUTH0_AUDIENCE')
    base = https_url(required('COUPLEHUB_MCP_PUBLIC_URL'), 'COUPLEHUB_MCP_PUBLIC_URL', True)
    try:
        redirects = json.loads(required('COUPLEHUB_MCP_REDIRECT_URIS'))
    except json.JSONDecodeError:
        raise RuntimeError('COUPLEHUB_MCP_REDIRECT_URIS must be a JSON array') from None
    if not isinstance(redirects, list) or not redirects or not all(isinstance(x, str) for x in redirects):
        raise RuntimeError('COUPLEHUB_MCP_REDIRECT_URIS must be a nonempty JSON array of HTTPS URLs')
    for uri in redirects:
        https_url(uri, 'MCP client redirect URI')
    return Auth0Provider(
        config_url=f'https://{domain}/.well-known/openid-configuration',
        client_id=client_id, client_secret=client_secret, audience=audience,
        base_url=base, required_scopes=['openid', 'couplehub:access'],
        redirect_path='/auth/callback', allowed_client_redirect_uris=redirects,
        require_authorization_consent=True,
    )
