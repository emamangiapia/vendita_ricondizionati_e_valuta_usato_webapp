import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
import job_runner
import windows_agent

class CombinedExecutionTests(unittest.TestCase):
    def test_combined_order_is_sale_then_all_six_trade_steps(self):
        def repo(env, candidates, required):
            return Path('sales') if env == 'WEFIX_SALES_REPO' else Path('trade')
        with patch.object(job_runner, 'find_repo', side_effect=repo), \
             patch.object(job_runner, 'python_for', return_value=sys.executable):
            result=job_runner.commands('all_scrapers')
        self.assertEqual([script.name for _,script,_ in result],
                         ['scaper_trovaprezzi.py', *job_runner.SCRIPTS_TRADE])
        self.assertEqual(result[0][2],Path('sales'))
        self.assertTrue(all(cwd == Path('trade') for _,_,cwd in result[1:]))

    def test_failure_stops_before_trade_steps(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp); first=root/'sale.py'; second=root/'trade.py'; marker=root/'ran.txt'
            first.write_text('raise SystemExit(7)\n',encoding='utf-8')
            second.write_text(f'from pathlib import Path\nPath({str(marker)!r}).write_text("ran")\n',encoding='utf-8')
            events=[]
            def fake_post(route, payload):
                events.append((route,payload))
                return {'continue':False}
            with patch.object(windows_agent,'post',side_effect=fake_post), \
                 patch.object(windows_agent,'commands',return_value=[(sys.executable,first,root),(sys.executable,second,root)]):
                windows_agent.run({'id':1,'action':'all_scrapers'})
            self.assertFalse(marker.exists())
            finish=[p for r,p in events if r=='/agent/finish'][-1]
            self.assertEqual(finish['exit_code'],7)
            self.assertIn('sale.py',finish['error'])

if __name__=='__main__':unittest.main()
