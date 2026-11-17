"""Health probes must not allocate SSE sessions or depend on the downstream API."""

import unittest
from unittest.mock import patch

from mcp.server.sse import SseServerTransport
from starlette.testclient import TestClient

from server import mcp


class HealthTests(unittest.TestCase):
    def test_repeated_get_and_head_bypass_mcp_and_api(self):
        with (
            patch.object(SseServerTransport, "connect_sse") as connect_sse,
            patch("server.api") as api,
            TestClient(mcp.sse_app()) as client,
        ):
            for _ in range(100):
                for method in ("GET", "HEAD"):
                    response = client.request(method, "/health")
                    self.assertEqual(response.status_code, 200)
                    self.assertEqual(response.text, "OK" if method == "GET" else "")
                    self.assertNotIn("text/event-stream", response.headers["content-type"])
            connect_sse.assert_not_called()
            api.assert_not_called()


if __name__ == "__main__":
    unittest.main()
