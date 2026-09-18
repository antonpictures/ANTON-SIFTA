import hashlib
import http.client
import json
import threading
import time
from urllib.parse import urlsplit

import pytest

from System import sifta_phone_link as phone


@pytest.fixture
def link(tmp_path):
    server = phone.PhoneLink('local-test', tmp_path, reply_fn=lambda *_: ('Salut!', False))
    server.start('127.0.0.1')
    yield server
    server.stop()


def request(link, path, payload=None, cookie='', origin=None, host=None):
    url = urlsplit(link.origin)
    conn = http.client.HTTPConnection(url.hostname, url.port, timeout=3)
    headers = {'Host': host or url.netloc, 'Cookie': cookie}
    if payload is not None:
        headers.update({'Origin': origin or link.origin, 'Content-Type': 'application/json'})
    conn.request('GET' if payload is None else 'POST', path,
                 body=None if payload is None else json.dumps(payload), headers=headers)
    response = conn.getresponse()
    raw = response.read()
    result = response.status, dict(response.getheaders()), raw
    conn.close()
    return result


def pair(link):
    ticket = link.new_ticket().split('=', 1)[1]
    code, headers, _ = request(link, '/api/pair', {'ticket': ticket})
    assert code == 200
    assert 'HttpOnly' in headers['Set-Cookie']
    return headers['Set-Cookie'].split(';')[0]


def test_pairing_single_use_expiry_rotation_and_auth(link):
    assert request(link, '/api/history')[0] == 403
    first = link.new_ticket().split('=', 1)[1]
    cookie = pair(link)
    assert request(link, '/api/pair', {'ticket': first})[0] == 403
    assert request(link, '/api/history', cookie=cookie)[0] == 200
    ticket = link.new_ticket().split('=', 1)[1]
    link.ticket_until = 0
    assert request(link, '/api/pair', {'ticket': ticket})[0] == 403
    token = cookie.split('=', 1)[1]
    link.sessions[hashlib.sha256(token.encode()).hexdigest()]['until'] = 0
    assert request(link, '/api/history', cookie=cookie)[0] == 403


def test_origin_and_host_guards(link):
    ticket = link.ticket
    assert request(link, '/api/pair', {'ticket': ticket}, origin='https://evil.test')[0] == 403
    assert request(link, '/', host='evil.test')[0] == 403
    assert request(link, '/api/pair', ['not-object'])[0] == 400
    assert request(link, '/api/pair', {'ticket': ticket})[0] == 200
    assert request(link, '/api/pair', {'ticket': ticket})[0] == 403


def test_chat_persistence_isolation_dedup_and_bounds(link):
    cookie, other = pair(link), pair(link)
    body = {'text': 'Salut', 'request_id': 'one'}
    assert request(link, '/api/chat', body, cookie)[0] == 202
    for _ in range(100):
        data = json.loads(request(link, '/api/history', cookie=cookie)[2])
        if not data['pending']:
            break
        time.sleep(.01)
    assert [r['content'] for r in data['history']] == ['Salut', 'Salut!']
    assert request(link, '/api/chat', body, cookie)[0] == 202
    assert len(json.loads(request(link, '/api/history', cookie=cookie)[2])['history']) == 2
    assert json.loads(request(link, '/api/history', cookie=other)[2])['history'] == []
    assert request(link, '/api/chat', {'text': 'x'*4001, 'request_id': 'two'}, cookie)[0] == 400
    assert request(link, '/api/chat', {'text': 'changed', 'request_id': 'one'}, cookie)[0] == 400
    transcripts = list(link.state.glob('*.json'))
    assert len(transcripts) == 1
    assert transcripts[0].stat().st_mode & 0o777 == 0o600
    assert json.loads(transcripts[0].read_text()) == data['history']
    events = (link.state / 'events.jsonl').read_text()
    assert 'Salut' not in events and cookie.split('=', 1)[1] not in events


def test_busy_failed_model_and_revocation(link):
    ready, release = threading.Event(), threading.Event()
    def fail(*_):
        ready.set()
        release.wait(2)
        raise TimeoutError()
    link.reply_fn = fail
    cookie = pair(link)
    request(link, '/api/chat', {'text': 'hello', 'request_id': 'one'}, cookie)
    assert ready.wait(1)
    assert request(link, '/api/chat', {'text': 'again', 'request_id': 'two'}, cookie)[0] == 429
    release.set()
    for _ in range(100):
        data = json.loads(request(link, '/api/history', cookie=cookie)[2])
        if not data['pending']:
            break
        time.sleep(.01)
    assert data['history'][-1]['role'] == 'notice'
    link.stopped = True
    assert request(link, '/api/history', cookie=cookie)[0] == 403


def test_observation_is_private_idempotent_and_used_by_next_chat(link):
    calls = []
    link.reply_fn = lambda _model, messages: (calls.append(messages) or ('Seen.', False))
    cookie = pair(link)
    observation = {
        'observation_id': 'obs-1', 'sequence': 1, 'captured_at': time.time(),
        'description': 'A clear path and a blue chair.', 'model_id': 'SmolVLM-500M',
        'confidence': 0.8, 'prompt_version': 'lookie-v1',
    }
    assert request(link, '/api/observations', observation, cookie)[0] == 202
    assert request(link, '/api/observations', observation, cookie)[0] == 202
    duplicate = dict(observation, description='different')
    assert request(link, '/api/observations', duplicate, cookie)[0] == 400
    assert request(link, '/api/chat', {'text': 'What do you see?', 'request_id': 'chat-1'}, cookie)[0] == 202
    for _ in range(100):
        data = json.loads(request(link, '/api/history', cookie=cookie)[2])
        if not data['pending']:
            break
        time.sleep(.01)
    assert len(data['observations']) == 1
    assert data['history'][-1]['content'] == 'Seen.'
    assert any('A clear path and a blue chair.' in row['content'] for row in calls[0])


def test_observation_sequence_and_bounds(link):
    cookie = pair(link)
    base = {'observation_id': 'obs-1', 'sequence': 2, 'captured_at': time.time(),
            'description': 'frame', 'model_id': 'vision'}
    assert request(link, '/api/observations', base, cookie)[0] == 202
    assert request(link, '/api/observations', dict(base, observation_id='obs-2', sequence=2), cookie)[0] == 400
    assert request(link, '/api/observations', dict(base, observation_id='obs-3', sequence=3,
                                                   description='x' * 4001), cookie)[0] == 400


def test_old_observation_is_stored_but_not_forwarded_to_chat(link):
    calls = []
    link.reply_fn = lambda _model, messages: (calls.append(messages) or ('Okay.', False))
    cookie = pair(link)
    old = {'observation_id': 'old', 'sequence': 1, 'captured_at': time.time() - 30,
           'description': 'old frame', 'model_id': 'vision'}
    assert request(link, '/api/observations', old, cookie)[0] == 202
    assert request(link, '/api/chat', {'text': 'Hello', 'request_id': 'chat-old'}, cookie)[0] == 202
    for _ in range(100):
        data = json.loads(request(link, '/api/history', cookie=cookie)[2])
        if not data['pending']:
            break
        time.sleep(.01)
    assert not any('old frame' in row['content'] for row in calls[0])
    assert data['observations'][0]['fresh_at_receive'] is False


@pytest.mark.parametrize('metadata', [{'remote_host': 'https://ollama.com'},
                                    {'remote_model': 'abc'}, {}])
def test_remote_weights_rejected(monkeypatch, metadata):
    monkeypatch.setattr(phone, 'ollama_json', lambda *_: metadata)
    with pytest.raises(ValueError):
        phone.verify_local_model('a-model')


def test_local_weights_and_error_propagation(monkeypatch):
    calls = []
    def local(path, payload=None, **_):
        calls.append(path)
        if path == '/api/show':
            return {'model_info': {'parameter_count': 8_000_000_000}}
        return {'message': {'content': 'Hello'}, 'done_reason': 'length'}
    monkeypatch.setattr(phone, 'ollama_json', local)
    assert phone.local_reply('local', []) == ('Hello', True)
    assert calls == ['/api/show', '/api/chat']
    with pytest.raises(ValueError):
        phone.verify_local_model('model:cloud')


def test_only_private_interface_and_self_contained_page(tmp_path, link):
    for address in ('0.0.0.0', '8.8.8.8', '169.254.1.1'):
        with pytest.raises(ValueError):
            phone.PhoneLink('x', tmp_path).start(address)
    status, headers, page = request(link, '/')
    assert status == 200 and headers['X-Frame-Options'] == 'DENY'
    assert 'Access-Control-Allow-Origin' not in headers
    assert b'textContent=r.content' in page
    assert b'https://' not in page
    assert b'location.hash' in page and b'history.replaceState' in page
