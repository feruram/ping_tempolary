import unittest
from audio import cues, task_starts
from mouse import HorizontalLimit


class GuideRequirements(unittest.TestCase):
    def test_jump_during_marked_task(self):
        take = dict(events=[[1,"key",57,1],[1.4,"key",57,0]],
                    blocks=[dict(kind="task",start=1,end=1.5)],epoch_tags=[[1.2,"task"]])
        self.assertEqual(list(task_starts(take)),[1])
        self.assertEqual(cues(take)[8],{("ジャンプ",True),("タスク",True)})

    def test_untagged_task_and_exclusion(self):
        take = dict(events=[[1,"key",19,1],[6,"key",19,0]],manual_fixed=[[0,8]])
        self.assertEqual(list(task_starts(take)),[1])
        take["epoch_tags"]=[[3,"exclude"]]
        self.assertEqual(list(task_starts(take)),[])

    def test_calibrated_limit(self):
        frames=[dict(t=i/2,yaw=(i*15+170)%360) for i in range(8)]
        take=dict(events=[[i/2,"move",100,0] for i in range(1,8)],position=dict(frames=frames))
        for override in (None,2400):
            limit=HorizontalLimit.from_degrees(take,15,override)
            self.assertEqual(limit.apply(0,300),100)
            self.assertEqual(limit.apply(0,1),0)
            self.assertEqual(limit.apply(1,0),0)
        with self.assertRaises(ValueError):
            HorizontalLimit.from_degrees(dict(take,position={}),15)
