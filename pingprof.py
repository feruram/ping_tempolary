import ctypes
from contextlib import ExitStack, nullcontext
from pathlib import Path
import queue
import tempfile
import threading
import time
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
import winsound

from audio import SOUNDS, audition, cues, read, render
from mouse import HorizontalLimit, mouse_filter


def main():
    root = tk.Tk()
    root.title("PingProf")
    panel = ttk.Frame(root,padding=16)
    panel.pack(fill="both",expand=True)
    file = tk.StringVar()
    limited = tk.BooleanVar()
    margin = tk.StringVar(value="160")
    status = tk.StringVar(value="お手本の操作記録を選んでください")
    stop = threading.Event()
    messages = queue.Queue()
    worker = None
    closing = False
    user = ctypes.windll.user32
    user.GetForegroundWindow.restype = ctypes.c_void_p
    def choose():
        selected = filedialog.askopenfilename(filetypes=[("操作記録","*.json")])
        if selected:
            file.set(selected)
    ttk.Label(panel,text="手動操作の音ガイド").pack(anchor="w")
    bar = ttk.Frame(panel)
    bar.pack(fill="x",pady=6)
    ttk.Entry(bar,textvariable=file,width=55).pack(side="left",fill="x",expand=True)
    ttk.Button(bar,text="開く…",command=choose).pack(side="left")
    sounds = ttk.LabelFrame(panel,text="合図を試聴")
    sounds.pack(fill="x")
    for i,k in enumerate(SOUNDS):
        ttk.Button(sounds,text=k,command=lambda label=k:audition(label)).grid(row=i//3,column=i%3,sticky="ew")
    ttk.Checkbutton(panel,text="手動のマウス移動をお手本の左右範囲に制限する",variable=limited).pack(anchor="w",pady=(10,0))
    row = ttk.Frame(panel)
    row.pack(anchor="w")
    ttk.Label(row,text="左右の許容量（マウスのカウント）").pack(side="left")
    ttk.Entry(row,textvariable=margin,width=8).pack(side="left")
    ttk.Label(panel,text="開始音までに対象を前面にし、開始位置と視線を合わせてください。F8で終了。").pack(anchor="w",pady=5)
    ttk.Label(panel,textvariable=status,wraplength=480).pack(anchor="w")

    def run(path, width, own):
        def check():
            if stop.is_set() or user.GetAsyncKeyState(0x77)&0x8000:
                raise InterruptedError
        try:
            take = read(path)
            notes = cues(take)
            if not notes:
                raise ValueError("案内できる入力がありません")
            limit = HorizontalLimit(take["events"],width) if width is not None else None
            with tempfile.TemporaryDirectory() as tmp, ExitStack() as playback:
                playback.callback(winsound.PlaySound,None,0)
                wav = str(Path(tmp)/"guide.wav")
                render(wav,notes,take["duration"],check)
                messages.put(("status","3秒以内にガイド対象へ切り替えてください"))
                for pitch in (440,554,660):
                    check()
                    winsound.Beep(pitch,90)
                    if stop.wait(.91):
                        raise InterruptedError
                target = user.GetForegroundWindow()
                if not target or target==own:
                    raise ValueError("対象ウィンドウを前面にしてから開始してください")
                def on_target():
                    return user.GetForegroundWindow()==target
                with mouse_filter() if limit else nullcontext() as process:
                    winsound.PlaySound(wav,winsound.SND_ASYNC|winsound.SND_FILENAME|winsound.SND_NODEFAULT)
                    start = time.perf_counter()
                    messages.put(("status","手動ガイド中"))
                    while time.perf_counter()-start<take["duration"]:
                        check()
                        if not on_target():
                            raise InterruptedError
                        if process:
                            process(limit,start,on_target)
                        else:
                            stop.wait(.015)
        except InterruptedError:
            result = "ガイドを停止しました"
        except Exception as exc:
            result = str(exc)
        else:
            result = "ガイドが終了しました"
        messages.put(("done",result))

    def start():
        nonlocal worker
        if worker:
            stop.set()
            return
        try:
            width = int(margin.get()) if limited.get() else None
            if width is not None and width<=0:
                raise ValueError
        except ValueError:
            messagebox.showerror("左右の許容量","正の整数を入力してください")
            return
        if not Path(file.get()).is_file():
            choose()
            if not Path(file.get()).is_file():
                return
        stop.clear()
        worker = threading.Thread(target=run,args=(file.get(),width,user.GetForegroundWindow()))
        button.configure(text="ガイドを停止")
        for child in sounds.winfo_children():
            child.configure(state="disabled")
        status.set("ガイドを準備しています")
        worker.start()

    def refresh():
        nonlocal worker
        while not messages.empty():
            event,text = messages.get_nowait()
            status.set(text)
            if event=="done":
                worker = None
                if closing:
                    root.destroy()
                    return
                button.configure(text="ガイドを開始")
                for child in sounds.winfo_children():
                    child.configure(state="normal")
        root.after(100,refresh)

    def close():
        nonlocal closing
        closing = True
        if worker:
            stop.set()
        else:
            root.destroy()
    button = ttk.Button(panel,text="ガイドを開始",command=start)
    button.pack(anchor="e",pady=8)
    root.protocol("WM_DELETE_WINDOW",close)
    refresh()
    root.mainloop()


if __name__=="__main__":
    main()
