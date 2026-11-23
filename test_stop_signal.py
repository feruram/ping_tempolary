import json
from pathlib import Path
from tempfile import TemporaryDirectory
import time
import unittest
from unittest.mock import patch

from pingprof import stop_tone
from stop_signal import ObserverStop


class StopSignalTest(unittest.TestCase):
    def test_adapter_conditions_and_ignored_states(self):
        now = time.time_ns()//1_000_000
        with TemporaryDirectory() as tmp:
            folder = Path(tmp)
            (folder/"triggers.json").write_text(json.dumps(dict(full=True,enemy=True,slots=[4])))
            def reason(**fields):
                frame = dict(online=True,client_pid=123,sample_ms=now)
                frame.update(fields)
                (folder/"state-next.json").write_text(json.dumps(frame))
                return ObserverStop(folder,123,now-100).check()
            with patch("stop_signal.time.time_ns",return_value=now*1_000_000):
                self.assertEqual(reason(chat_match_ms=now),"チャットが停止条件に一致")
                self.assertEqual(reason(facts=dict(enemy_nearby=True)),"敵の接近")
                self.assertEqual(reason(facts=dict(inventory_full=True)),"インベントリが満杯")
                self.assertEqual(reason(occupied_slots=16),"指定スロットが使用中")
                self.assertIsNone(reason(chat_match_ms=now-101))
                self.assertIsNone(reason(occupied_slots=16,client_pid=321))
                self.assertIsNone(reason(occupied_slots=16,sample_ms=now-501))
                self.assertIsNone(reason(occupied_slots=2))
                (folder/"triggers.json").write_text("{}")
                self.assertIsNone(reason(facts=dict(enemy_nearby=True,inventory_full=True),occupied_slots=16))

    def test_stop_sound(self):
        with patch("winsound.Beep") as beep:
            stop_tone()
        self.assertEqual([call.args for call in beep.call_args_list],[(1250,140),(850,140),(450,140)])
