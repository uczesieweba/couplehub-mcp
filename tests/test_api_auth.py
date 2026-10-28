import os
import secrets
import unittest
from unittest.mock import patch

import httpx
import server


class ApiAuthenticationTests(unittest.TestCase):
    def setUp(self):
        self.token = secrets.token_hex(32)
        self.env = patch.dict(os.environ, {'COUPLEHUB_API_TOKEN': self.token})
        self.env.start()
        self.base = patch.object(server, 'API_BASE', 'https://staging.example/api')
        self.base.start()
        self.addCleanup(self.env.stop)
        self.addCleanup(self.base.stop)

    def test_token_forwarding(self):
        def handle(request):
            self.assertEqual(request.url, 'https://staging.example/api/recipes')
            self.assertEqual(request.headers['Authorization'], 'Bearer '+self.token)
            return httpx.Response(200, json=[])
        client = httpx.Client(transport=httpx.MockTransport(handle))
        with patch.object(server.httpx, 'Client', return_value=client) as factory:
            self.assertEqual(server.api('GET', '/recipes'), [])
            self.assertFalse(factory.call_args.kwargs['follow_redirects'])

    def test_no_network_when_unconfigured(self):
        for value in ['', ' ', 'invalid token']:
            with patch.dict(os.environ, {'COUPLEHUB_API_TOKEN': value}), \
                    patch.object(server.httpx, 'Client') as client:
                with self.assertRaises(RuntimeError):
                    server.api('GET', '/recipes')
                client.assert_not_called()
        with patch.object(server, 'API_BASE', ''), patch.object(server.httpx, 'Client') as client:
            with self.assertRaises(RuntimeError):
                server.api('GET', '/recipes')
            client.assert_not_called()

    def test_unsafe_destination_rejected_before_network(self):
        for base in ['http://remote.example/api', 'https://user:password@example.com/api',
                     'https://example.com/api?key=value', 'https://example.com/api#fragment']:
            with patch.object(server, 'API_BASE', base), patch.object(server.httpx, 'Client') as client:
                with self.assertRaises(RuntimeError):
                    server.api('GET', '/recipes')
                client.assert_not_called()

    def test_redirect_does_not_receive_token(self):
        seen = []
        def handle(request):
            seen.append(str(request.url))
            return httpx.Response(307, headers={'Location': 'https://other.example/collect'})
        client = httpx.Client(transport=httpx.MockTransport(handle), follow_redirects=False)
        with patch.object(server.httpx, 'Client', return_value=client):
            with self.assertRaises(httpx.HTTPStatusError):
                server.api('GET', '/recipes')
        self.assertEqual(seen, ['https://staging.example/api/recipes'])


if __name__ == '__main__':
    unittest.main()
