import ctypes as c
from bisect import bisect_right
from contextlib import contextmanager
from pathlib import Path
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
