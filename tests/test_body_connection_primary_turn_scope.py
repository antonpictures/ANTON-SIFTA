from System.stigmerobotics_body_connection import _talk_primary_turn_source


def test_primary_turn_ignores_worker_in_other_method():
    source = '''
class Talk:
    def other_lane(self):
        self._brain = _BrainWorker()
    def _start_brain(self):
        answer_recent_activity_query(text)
        build_body_connection_proof()
        self._brain = _BrainWorker()
'''
    primary = _talk_primary_turn_source(source)
    assert primary.index('answer_recent_activity_query') < primary.index('self._brain')
    assert 'other_lane' not in primary


def test_missing_or_invalid_method_is_not_passed():
    assert _talk_primary_turn_source('def other(): pass') == ''
    assert _talk_primary_turn_source('invalid python !!!') == ''
