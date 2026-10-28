import json
import os
import unittest
from unittest.mock import patch
from urllib.parse import urlsplit

import httpx
from fastmcp import FastMCP
from fastmcp.server.auth.providers.auth0 import Auth0Provider
from key_value.aio.stores.memory import MemoryStore
from starlette.testclient import TestClient

import auth_config


class Auth0Tests(unittest.TestCase):
    def setUp(self):
        self.env = {
            'COUPLEHUB_AUTH_MODE': 'auth0',
            'COUPLEHUB_AUTH0_DOMAIN': 'test-tenant.auth0.com',
            'COUPLEHUB_AUTH0_CLIENT_ID': 'test-client',
            'COUPLEHUB_AUTH0_CLIENT_SECRET': 'test-only-placeholder-secret',
            'COUPLEHUB_AUTH0_AUDIENCE': 'https://couplehub.example/api',
            'COUPLEHUB_MCP_PUBLIC_URL': 'https://mcp.example',
            'COUPLEHUB_MCP_REDIRECT_URIS': json.dumps(['https://chatgpt.example/callback']),
        }

    def test_default_requires_auth0(self):
        with patch.dict(os.environ, {}, clear=True), patch.object(auth_config, 'Auth0Provider') as provider:
            with self.assertRaisesRegex(RuntimeError, 'COUPLEHUB_AUTH0_DOMAIN'):
                auth_config.build_auth()
            provider.assert_not_called()

    def test_all_required_configuration_is_checked(self):
        for name in self.env:
            if name == 'COUPLEHUB_AUTH_MODE':
                continue
            env = self.env | {name: ''}
            with self.subTest(name=name), patch.dict(os.environ, env, clear=True), \
                    patch.object(auth_config, 'Auth0Provider') as provider:
                with self.assertRaises(RuntimeError):
                    auth_config.build_auth()
                provider.assert_not_called()

    def test_unsafe_urls_and_modes_rejected(self):
        cases = [('COUPLEHUB_AUTH_MODE', 'none'),
                 ('COUPLEHUB_AUTH0_DOMAIN', 'https://tenant.auth0.com/path'),
                 ('COUPLEHUB_MCP_PUBLIC_URL', 'http://mcp.example'),
                 ('COUPLEHUB_MCP_PUBLIC_URL', 'https://mcp.example/path'),
                 ('COUPLEHUB_MCP_REDIRECT_URIS', '[]'),
                 ('COUPLEHUB_MCP_REDIRECT_URIS', 'not json'),
                 ('COUPLEHUB_MCP_REDIRECT_URIS', '["https://*.example/callback"]'),
                 ('COUPLEHUB_MCP_REDIRECT_URIS', '["http://client.example/callback"]')]
        for name, value in cases:
            with self.subTest(name=name), patch.dict(os.environ, self.env | {name: value}, clear=True):
                with self.assertRaises(RuntimeError):
                    auth_config.build_auth()

    def test_local_mode_is_explicit_and_loopback_only(self):
        with patch.dict(os.environ, {'COUPLEHUB_AUTH_MODE': 'local',
                                    'COUPLEHUB_API_BASE': 'http://127.0.0.1:8001/api'}, clear=True):
            self.assertIsNone(auth_config.build_auth())
            with patch.dict(os.environ, {'COUPLEHUB_API_BASE': 'https://production.example/api'}):
                with self.assertRaises(RuntimeError):
                    auth_config.build_auth()

    def test_real_provider_rejects_tokens_and_exposes_discovery(self):
        discovery = {
            'issuer': 'https://test-tenant.auth0.com/',
            'authorization_endpoint': 'https://test-tenant.auth0.com/authorize',
            'token_endpoint': 'https://test-tenant.auth0.com/oauth/token',
            'jwks_uri': 'https://test-tenant.auth0.com/.well-known/jwks.json',
            'response_types_supported': ['code'],
            'subject_types_supported': ['public'],
            'id_token_signing_alg_values_supported': ['RS256'],
        }
        response = httpx.Response(200, json=discovery,
                                  request=httpx.Request('GET', 'https://test-tenant.auth0.com/.well-known/openid-configuration'))

        def create(**kwargs):
            self.assertTrue(kwargs['require_authorization_consent'])
            self.assertEqual(kwargs['required_scopes'], ['openid', 'couplehub:access'])
            return Auth0Provider(**kwargs, client_storage=MemoryStore())

        with patch.dict(os.environ, self.env, clear=True), \
                patch('fastmcp.server.auth.oidc_proxy.httpx.get', return_value=response), \
                patch.object(auth_config, 'Auth0Provider', side_effect=create):
            provider = auth_config.build_auth()
        app = FastMCP('auth-test', auth=provider).http_app(transport='sse')
        with TestClient(app, base_url='https://mcp.example') as client:
            denied = client.get('/sse')
            self.assertEqual(denied.status_code, 401)
            challenge = denied.headers['www-authenticate']
            self.assertIn('resource_metadata=', challenge)
            self.assertEqual(client.get('/sse', headers={'Authorization': 'Bearer invalid'}).status_code, 401)
            metadata_url = challenge.split('resource_metadata="', 1)[1].split('"', 1)[0]
            metadata = client.get(urlsplit(metadata_url).path)
            self.assertEqual(metadata.status_code, 200)
            self.assertIn('couplehub:access', metadata.json()['scopes_supported'])
            oauth = client.get('/.well-known/oauth-authorization-server')
            self.assertEqual(oauth.status_code, 200)
            self.assertEqual(oauth.json()['issuer'], 'https://mcp.example/')


if __name__ == '__main__':
    unittest.main()
