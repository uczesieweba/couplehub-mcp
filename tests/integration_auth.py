"""Local-only MCP/SSE -> PHP -> MariaDB authentication integration check.

Run from this checkout: python tests/integration_auth.py
Uses the onboarding runtime; never uses inherited production DB credentials.
"""
import asyncio
import json
import os
from pathlib import Path
import secrets
import socket
import subprocess
import time
import uuid

import httpx
from fastmcp import Client

ROOT = Path(__file__).resolve().parents[1]
RUNTIME = Path('/workspace/couplehub-runtime')


def port():
    with socket.socket() as sock:
        sock.bind(('127.0.0.1', 0))
        return sock.getsockname()[1]


def ready(url, process):
    for _ in range(100):
        if process.poll() is not None:
            raise RuntimeError('Local test service exited before readiness')
        try:
            with httpx.Client(trust_env=False, timeout=0.5) as client:
                # OPTIONS avoids opening an SSE stream or reading any records.
                client.options(url)
                return
        except httpx.TransportError:
            time.sleep(0.1)
    raise RuntimeError('Local test service did not become ready')


async def exercise_mcp(url):
    async with Client(url) as mcp:
        tools = await mcp.list_tools()
        assert any(tool.name == 'get_recipes' for tool in tools)

        async def call(name, arguments=None):
            content = await mcp.call_tool(name, arguments)
            if hasattr(content, 'content'):
                content = content.content
            text = [part.text for part in content if part.type == 'text']
            # FastMCP 2.2 serializes list results as one content item per row.
            parsed = [json.loads(value) for value in text]
            return parsed[0] if len(parsed) == 1 else parsed

        await call('get_recipes')
        await call('get_chores', {'all': 1})
        record_id = None
        marker = 'auth-integration-' + str(uuid.uuid4())
        try:
            created = await call('create_chore', {'created_by': 1, 'title': marker,
                                                 'recurrence': 'none', 'points': 1})
            record_id = created['id']
            await call('update_chore', {'id': record_id, 'title': marker+' updated'})
            # Query the local backend through its MCP-configured API helper to
            # verify persisted values without printing other household records.
            rows = await call('get_chores', {'all': 1})
            if isinstance(rows, dict):
                rows = [rows]
            assert any(row['id'] == record_id and row['title'] == marker+' updated' for row in rows)
        finally:
            if record_id is not None:
                await call('delete_chore', {'id': record_id})
        rows = await call('get_chores', {'all': 1})
        if isinstance(rows, dict):
            rows = [rows]
        assert all(row['id'] != record_id for row in rows)
        print('PASS: real SSE MCP initialization, tool listing, reads and temporary chore CRUD/cleanup')


def main():
    assert (RUNTIME / 'mysql.sock').exists(), 'Start the local MariaDB first'
    token = secrets.token_urlsafe(32)
    php_port, mcp_port, unset_port = port(), port(), port()
    base = f'http://127.0.0.1:{php_port}/CoupleHub_DEV/api'
    env = os.environ.copy()
    env.update(COUPLEHUB_DB_HOST='localhost', COUPLEHUB_DB_NAME='couplehub_dev',
               COUPLEHUB_DB_USER='agent', COUPLEHUB_DB_PASSWORD='',
               COUPLEHUB_API_TOKEN=token, COUPLEHUB_API_BASE=base, COUPLEHUB_AUTH_MODE='local')
    php = [str(RUNTIME / 'php'), '-d', f'pdo_mysql.default_socket={RUNTIME}/mysql.sock']
    processes = []
    try:
        def start(command, child_env):
            process = subprocess.Popen(command, env=child_env, cwd=ROOT,
                                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            processes.append(process)
            return process
        p = start(php+['-S', f'127.0.0.1:{php_port}', str(RUNTIME/'router.php')], env)
        ready(base+'/recipes', p)
        with httpx.Client(trust_env=False) as client:
            for method in ['GET', 'POST', 'PATCH', 'DELETE']:
                for headers in [{}, {'Authorization': 'Bearer incorrect'}]:
                    response = client.request(method, base+'/chores', headers=headers, json={})
                    assert response.status_code == 401
                    assert response.json() == {'error': 'Unauthorized'}
                    assert response.headers['www-authenticate'].startswith('Bearer')
                    assert 'access-control-allow-origin' not in response.headers
            assert client.options(base+'/recipes').status_code == 204
            assert client.get(base+'/recipes?token='+token).status_code == 401
        print('PASS: unauthenticated/invalid reads and writes rejected; query token rejected; preflight allowed')

        unset_env = env.copy()
        unset_env.pop('COUPLEHUB_API_TOKEN')
        p = start(php+['-S', f'127.0.0.1:{unset_port}', str(RUNTIME/'router.php')], unset_env)
        unset_url = f'http://127.0.0.1:{unset_port}/CoupleHub_DEV/api/recipes'
        ready(unset_url, p)
        assert httpx.get(unset_url, trust_env=False).status_code == 503
        print('PASS: unconfigured PHP fails closed with 503')

        import sys
        command = [sys.executable, '-c',
                   f'import server, uvicorn; uvicorn.run(server.mcp.http_app(transport="sse"), host="127.0.0.1", port={mcp_port}, log_level="error")']
        p = start(command, env)
        url = f'http://127.0.0.1:{mcp_port}/sse'
        ready(url, p)
        asyncio.run(exercise_mcp(url))
    finally:
        for process in reversed(processes):
            process.terminate()
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait()


if __name__ == '__main__':
    main()
