from types import SimpleNamespace

from System import chorus_node_server as server
from System.swarm_web_global_chat_gate import SessionRateLimiter, submit_web_message
from System import swarm_web_global_chat_night_worker as worker


def test_robot_host_is_isolated_from_working_chat():
    for host in ('stigmergicode.com', 'localhost:8100', 'stigmergicoin.com.attacker.test'):
        assert server.ChorusHandler._landing_page(SimpleNamespace(headers={'Host': host})) == server.WEB_CHAT_PAGE
    page = server.ChorusHandler._landing_page(SimpleNamespace(headers={'Host': 'stigmergicoin.com'}))
    assert 'id="switchCamera"' in page
    assert "face_signal" in page
    assert 'getUserMedia' in page
    assert 'id="enableEverything"' in page
    assert 'pagehide' in page


def test_worker_follows_cortex_between_turns(monkeypatch, tmp_path):
    monkeypatch.setattr(worker, 'STATE_DIR', tmp_path)
    monkeypatch.setattr(worker, 'LOCK_PATH', tmp_path / 'worker.lock')
    monkeypatch.setattr(worker, '_STOP', False)
    monkeypatch.setattr(worker.signal, 'signal', lambda *args: None)
    monkeypatch.setattr(worker, '_append_health', lambda *args, **kwargs: None)
    monkeypatch.setattr(worker.time, 'sleep', lambda *args: None)
    choices = iter(['old-model', 'krishna', 'new-owner-choice'])
    monkeypatch.setattr(worker, 'choose_local_model', lambda: next(choices))
    calls = []
    def process(**kwargs):
        calls.append(kwargs['model'])
        if len(calls) == 2:
            worker._STOP = True
    monkeypatch.setattr(worker, 'process_one', process)
    worker.run_forever()
    assert calls == ['krishna', 'new-owner-choice']


def test_phone_capture_accepts_frame_audio_and_bounded_provenance(tmp_path, monkeypatch):
    import System.swarm_web_global_chat_gate as gate

    ingress = tmp_path / 'ingress.jsonl'
    conversation = tmp_path / 'conversation.jsonl'
    monkeypatch.setattr(gate, '_REPO', tmp_path)
    monkeypatch.setattr(gate, 'WEB_ATTACHMENT_DIR', tmp_path / 'attachments')
    result = submit_web_message(
        'Describe this moment.',
        'phone-session',
        attachments=[
            {'name': 'frame.jpg', 'mime': 'image/jpeg', 'data_url': 'data:image/jpeg;base64,/9j/AA=='},
            {'name': 'audio.ogg', 'mime': 'audio/ogg', 'data_url': 'data:audio/ogg;base64,T2dnUw=='},
        ],
        capture={
            'schema_version': 'sifta.capture.v1',
            'capture_id': 'capture-1',
            'frame_sha256': 'f' * 64,
            'audio_sha256': 'a' * 64,
            'device_id': 'browser:phone',
            'unknown_field': 'discarded',
        },
        ingress_path=ingress,
        conversation_path=conversation,
        rate_limiter=SessionRateLimiter(limit=10),
    )
    assert result['accepted'] is True
    assert [row['kind'] for row in result['attachments']] == ['image', 'audio']
    assert result['capture']['capture_id'] == 'capture-1'
    assert 'unknown_field' not in result['capture']
