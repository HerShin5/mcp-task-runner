"""Exercise the real model transport against two loopback HTTP gateways."""

import json
from contextlib import contextmanager
from dataclasses import replace
from http.server import BaseHTTPRequestHandler, HTTPServer
from threading import Event, Thread

import pytest

from mcp_task_runner.failover import CircuitBreaker, CircuitState
from mcp_task_runner.providers import ProviderConfig
from mcp_task_runner.routed_client import RoutedModelClient


@contextmanager
def gateway(name, *, reply=None, wait=None):
    requests = []
    status = [200]

    class Handler(BaseHTTPRequestHandler):
        def do_POST(self):
            requests.append(self.path)
            self.rfile.read(int(self.headers['Content-Length']))
            if wait is not None:
                wait.wait(5)
                return
            code = status[0] if self.path == '/v1/chat/completions' else 404
            body = json.dumps({'choices': [{'message': {'content': reply or name}}]} if code == 200 else {}).encode()
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


def test_socket_read_timeout_does_not_repeat_duplicate_route(monkeypatch):
    monkeypatch.setenv('no_proxy', '127.0.0.1')
    release = Event()
    with gateway('A', wait=release) as (a, hits_a, _), gateway('B') as (b, hits_b, _):
        try:
            result = chat(RoutedModelClient([replace(a, timeout=0.25), b]), route_order=['A', 'A', 'B'])
        finally:
            release.set()
        assert result.attempts == ('A', 'B') and result.reply.text == 'B'
        assert len(result.errors) == 1 and 'timed out' in result.errors[0].lower()
        assert (len(hits_a), len(hits_b)) == (1, 1)


def test_live_plan_posts_only_to_management_eligible_gateway(tmp_path, monkeypatch, capsys):
    from mcp_task_runner.cli import run
    from mcp_task_runner.providers import ProviderHealth

    monkeypatch.setenv('no_proxy', '127.0.0.1')
    monkeypatch.setattr('mcp_task_runner.gateway_catalog.check_provider', lambda p:
                        ProviderHealth(p.name, True, 200, 'ok', p.model, True, 10))
    plan = json.dumps({'goal': 'probe', 'requires_approval': False, 'steps': [
        {'id': '1', 'tool': 'health', 'arguments': {}, 'purpose': 'probe', 'verify': True}]})
    with gateway('A', reply=plan) as (a, hits_a, _), gateway('B', reply=plan) as (b, hits_b, _):
        config = tmp_path / 'providers.json'
        config.write_text(json.dumps({'providers': [
            {'name': p.name, 'base_url': p.base_url, 'model': p.model,
             'pricing': {'short': {'input': cost, 'output': cost}}}
            for p, cost in [(a, 1), (b, 2)]]}), encoding='utf-8')
        config.with_suffix('.management.json').write_text(json.dumps({'provider': 'A', 'groups': [
            {'name': 'disabled', 'enabled': False, 'models': [a.model]}]}), encoding='utf-8')
        profiles = tmp_path / 'profiles.json'
        profiles.write_text(json.dumps({'models': [{'name': a.model, 'capabilities': {
            'reasoning': 5, 'structured_output': 5}}]}), encoding='utf-8')
        code = run(['live-plan', 'probe', '--providers', str(config), '--profiles', str(profiles)])
        assert code == 0 and json.loads(capsys.readouterr().out)['selected_gateway'] == 'B'
        assert (len(hits_a), len(hits_b)) == (0, 1)
