"""Exercise the real model transport against two loopback HTTP gateways."""

import json
from contextlib import contextmanager
from http.server import BaseHTTPRequestHandler, HTTPServer
from threading import Thread

import pytest

from mcp_task_runner.failover import CircuitBreaker, CircuitState
from mcp_task_runner.providers import ProviderConfig
from mcp_task_runner.routed_client import RoutedModelClient


@contextmanager
def gateway(name):
    requests = []
    status = [200]

    class Handler(BaseHTTPRequestHandler):
        def do_POST(self):
            requests.append(self.path)
            self.rfile.read(int(self.headers['Content-Length']))
            code = status[0] if self.path == '/v1/chat/completions' else 404
            body = json.dumps({'choices': [{'message': {'content': name}}]} if code == 200 else {}).encode()
            self.send_response(code)
            self.send_header('Content-Type', 'application/json')
            self.send_header('Content-Length', str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, *args):
            pass

    with HTTPServer(('127.0.0.1', 0), Handler) as server:
        worker = Thread(target=server.serve_forever, kwargs={'poll_interval': 0.01})
        worker.start()
        try:
            yield ProviderConfig(name, f'http://127.0.0.1:{server.server_port}/v1', 'test-model'), requests, status
        finally:
            server.shutdown()
            worker.join()


@pytest.fixture
def pair(monkeypatch):
    monkeypatch.setenv('no_proxy', '127.0.0.1')
    with gateway('A') as (a, requests_a, status_a), gateway('B') as (b, requests_b, _):
        client = RoutedModelClient([a, b], breaker=CircuitBreaker(failure_threshold=2, cooldown_seconds=10))
        yield client, requests_a, requests_b, status_a


def chat(client, **flags):
    return client.chat([{'role': 'user', 'content': 'local probe'}], model='test-model', **flags)


@pytest.mark.parametrize('status,flags,expected_b', [
    (503, {}, 1), (429, {}, 1), (401, {}, 0), (403, {}, 0),
    (503, {'response_started': True}, 0), (503, {'external_side_effect': True}, 0),
])
def test_http_replay_decision(pair, status, flags, expected_b):
    client, requests_a, requests_b, status_a = pair
    status_a[0] = status
    result = chat(client, **flags)
    assert (len(requests_a), len(requests_b)) == (1, expected_b)
    assert len(result.errors) == 1 and str(status) in result.errors[0]
    if expected_b:
        assert result.attempts == ('A', 'B') and result.route == 'B'
        assert result.reply.text == 'B'
    else:
        assert result.attempts == ('A',) and result.reply is None


def test_http_circuit_recovery(pair, monkeypatch):
    client, requests_a, requests_b, status_a = pair
    now = 100
    monkeypatch.setattr('mcp_task_runner.failover.monotonic', lambda: now)
    status_a[0] = 503
    for _ in range(2):
        assert chat(client).attempts == ('A', 'B')
    assert client.breaker.state('A') is CircuitState.OPEN
    status_a[0] = 200
    now += 9
    assert chat(client).attempts == ('B',)
    assert (len(requests_a), len(requests_b)) == (2, 3)
    now += 1
    assert client.breaker.state('A') is CircuitState.HALF_OPEN
    assert chat(client).reply.text == 'A'
    assert client.breaker.state('A') is CircuitState.CLOSED
    assert chat(client).attempts == ('A',)
    assert (len(requests_a), len(requests_b)) == (4, 3)
