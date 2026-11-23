import ctypes as c
from bisect import bisect_right
from contextlib import contextmanager
from pathlib import Path
import math
from statistics import median
import sys
import time


class MouseStroke(c.Structure):
    _fields_ = [("state",c.c_ushort),("flags",c.c_ushort),("rolling",c.c_short),
                ("x",c.c_int),("y",c.c_int),("information",c.c_uint)]


class HorizontalLimit:
    def __init__(self, events, margin):
        if margin <= 0:
            raise ValueError("左右の許容量を正のカウントで指定してください")
        self.margin = margin
        self.times = []
        self.centers = [0]
        for t, kind, dx, _ in events:
            if kind == "move":
                self.times.append(t)
                self.centers.append(self.centers[-1]+dx)
        if not self.times:
            raise ValueError("マウス移動を含むお手本が必要です")
        self.actual = 0

    @classmethod
    def from_degrees(cls, take, angle, per_turn=None):
        limit = cls(take["events"],1)
        if not math.isfinite(angle) or not 0 < angle < 180:
            raise ValueError("左右の許容角度は0度より大きく180度未満で指定してください")
        if per_turn is None:
            ratios = []
            prev = None
            for frame in (take.get("position") or {}).get("frames", []):
                t,yaw = frame.get("t"),frame.get("yaw")
                if not all(isinstance(v,(float,int)) and math.isfinite(v) for v in (t,yaw)):
                    prev = None
                    continue
                x = limit.centers[bisect_right(limit.times,t)]
                space = frame.get("space")
                if prev and space == prev[3] and 0 <= t-prev[0]<.5:
                    continue
                if prev and space == prev[3] and .5 <= t-prev[0] <= 1:
                    dy = (yaw-prev[1]+180)%360-180
                    dx = x-prev[2]
                    if 12<abs(dy)<140 and abs(dx)>20:
                        ratios.append(dy/dx)
                prev = (t,yaw,x,space)
            scale = median(ratios) if ratios else 0
            if (take.get("input_edited") or len(ratios)<4 or not scale or
                    sum(abs(r-scale)<=abs(scale)*.2 for r in ratios)<.6*len(ratios)):
                raise ValueError("感度を安定して推定できません。現在の感度で360度回すカウント数を入力してください")
            per_turn = 360/abs(scale)
        if not math.isfinite(per_turn) or per_turn<=0:
            raise ValueError("1回転のカウント数には正の数を入力してください")
        limit.margin = math.floor(angle*per_turn/360)
        if not limit.margin:
            raise ValueError("許容角度がマウスの1カウントより小さいため、角度を広げてください")
        return limit

    def apply(self, elapsed, dx):
        center = self.centers[bisect_right(self.times,elapsed)]
        error = self.actual-center
        lower = min(0,-self.margin-error)
        upper = max(0,self.margin-error)
        accepted = max(lower,min(upper,dx))
        self.actual += accepted
        return accepted


@contextmanager
def mouse_filter():
    path = Path(sys.executable if getattr(sys,"frozen",False) else __file__).with_name("interception.dll")
    if not path.is_file():
        raise ValueError("入力制限には導入済みのInterceptionドライバーと、アプリの隣の64ビット版interception.dllが必要です。音だけの案内も使えます。")
    lib = c.CDLL(str(path.resolve()))
    ctx_t = c.c_void_p
    predicate = c.CFUNCTYPE(c.c_int,c.c_int)
    def bind(name, result, *params):
        fn = getattr(lib,"interception_"+name)
        fn.restype,fn.argtypes = result,params
        return fn
    create = bind("create_context",ctx_t)
    destroy = bind("destroy_context",None,ctx_t)
    set_filter = bind("set_filter",None,ctx_t,predicate,c.c_ushort)
    is_mouse = predicate(("interception_is_mouse",lib))
    wait = bind("wait_with_timeout",c.c_int,ctx_t,c.c_ulong)
    receive = bind("receive",c.c_int,ctx_t,c.c_int,c.POINTER(MouseStroke),c.c_uint)
    send = bind("send",c.c_int,ctx_t,c.c_int,c.POINTER(MouseStroke),c.c_uint)
    ctx = create()
    if not ctx:
        raise ValueError("入力ドライバーを開けません。音だけの案内を利用できます。")
    packet = MouseStroke()
    def process(limit, start, current_target):
        device = wait(ctx,10)
        if device and receive(ctx,device,c.byref(packet),1)==1:
            if current_target() and not packet.flags & 1:
                packet.x = limit.apply(time.perf_counter()-start,packet.x)
            if send(ctx,device,c.byref(packet),1)!=1:
                raise OSError("マウス入力を転送できませんでした")
    try:
        set_filter(ctx,is_mouse,0x1000)
        yield process
    finally:
        destroy(ctx)
