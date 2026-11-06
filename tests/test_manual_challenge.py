import io
import json
import unittest
from unittest.mock import Mock, patch
import manual_challenge

class ManualChallengeTests(unittest.TestCase):
    def test_same_page_receives_drag_and_resume_then_closes_channel(self):
        page = Mock()
        page.is_closed.return_value = False
        page.screenshot.return_value = b'\xff\xd8test'
        page.viewport_size = {'width':1000, 'height':500}
        events = [{'type':'down','x':.1,'y':.2}, {'type':'move','x':.8,'y':.2},
                  {'type':'up','x':.8,'y':.2}, {'type':'continue'}]
        calls = []
        def respond(req, timeout):
            calls.append(json.loads(req.data))
            return io.BytesIO(json.dumps({'events':events if len(calls)==1 else []}).encode())
        with patch.dict('os.environ', {'WEFIX_CHALLENGE_API':'http://127.0.0.1:8766',
                                      'WEFIX_CHALLENGE_TOKEN':'fixture', 'WEFIX_CHALLENGE_JOB':'12'}), patch.object(manual_challenge, 'urlopen', respond):
            manual_challenge.wait_for_verification(page)
        self.assertEqual(page.mouse.move.call_args_list[0].args, (100,100))
        self.assertEqual(page.mouse.move.call_args_list[1].args, (800,100))
        page.mouse.down.assert_called_once()
        self.assertEqual(calls[-1], {'id':12,'frame':None})
        page.goto.assert_not_called()
