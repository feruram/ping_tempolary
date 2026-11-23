from array import array
from collections import defaultdict
from functools import lru_cache
from io import BytesIO
import math
from pathlib import Path
import wave
import winsound

import json


# Frequency and stereo pan. Different pitches also distinguish directions in mono.
SOUNDS = {"タスク":(640,0),"前進":(440,0), "後退":(260,0), "左移動":(330,-1), "右移動":(550,1),
          "左旋回":(740,-1), "右旋回":(990,1), "ジャンプ":(1320,0),
          "左クリック":(1550,-.5), "右クリック":(1800,.5)}
KEYS = {17:"前進",31:"後退",30:"左移動",32:"右移動",57:"ジャンプ"}
RATE = 12000
STEP = .12


def task_starts(take):
    tags = take.get("epoch_tags", [])
    excluded = sorted(t for t,tag in tags if tag=="exclude")
    spans = list(take.get("workpoints", []))
    if "blocks" in take:
        spans.extend((b["start"],b["end"]) for b in take["blocks"] if b["kind"]=="task")
    else:
        held = set()
        for t,kind,code,down in take["events"]:
            if kind not in ("key","button") or kind=="key" and code in (17,30,31,32,42,54,57,328,331,333,336):
                continue
            token = kind,code
            if down:
                if not held:
                    start = t
                held.add(token)
            elif token in held:
                held.remove(token)
                if not held and t-start<=8:
                    spans.append((start,t))
    spans = [(a,b) for a,b in spans if not any(a<=t<=b for t in excluded)]
    spans.extend((t,t) for t,tag in tags if tag=="task")
    end = -1
    for a,b in sorted(spans):
        if a>end:
            yield a
        end = max(end,b)


def cues(take):
    groups = defaultdict(set)
    held = set()
    for t, kind, code, down in take["events"]:
        label = KEYS.get(code) if kind=="key" else {1:"左クリック",2:"右クリック"}.get(code) if kind=="button" else None
        if label and bool(down) != (label in held):
            if down:
                held.add(label)
            else:
                held.discard(label)
            groups[int(t/STEP)].add((label,bool(down)))
    for t in task_starts(take):
        groups[int(t/STEP)].add(("タスク",True))
    turn = 0
    for t,kind,dx,_ in take["events"]:
        if kind == "move":
            turn += dx
            if abs(turn) >= 80:
                groups[int(t/STEP)].add(("右旋回" if turn>0 else "左旋回",True))
                turn = 0
    return groups


@lru_cache(maxsize=128)
def chord(notes):
    samples = array("h")
    for i in range(round(RATE*STEP)):
        t = i/RATE
        envelope = min(1, t/.008, (STEP-t)/.015)
        left = right = 0
        for label,down in notes:
            freq, pan = SOUNDS[label]
            phase = t + (.38 if down else -.38)*(t*t/STEP-t/2)
            value = math.sin(math.tau*freq*phase)*envelope
            left += value*(1-.75*max(pan,0))
            right += value*(1+.75*min(pan,0))
        gain = 12500/len(notes)
        samples.extend((int(left*gain),int(right*gain)))
    return samples.tobytes()


def render(dest, groups, duration, poll):
    silence = bytes(round(RATE*STEP)*4)
    with wave.open(dest, "wb") as wav:
        wav.setparams((2,2,RATE,0,"NONE",""))
        for idx in range(max(math.ceil(duration/STEP),max(groups,default=0)+1)):
            if idx%32 == 0:
                poll()
            notes = groups.get(idx)
            wav.writeframesraw(chord(tuple(sorted(notes))) if notes else silence)


def audition(label):
    buf = BytesIO()
    render(buf,{0:{(label,True)},2:{(label,False)}},3*STEP,lambda:None)
    winsound.PlaySound(buf.getvalue(),winsound.SND_MEMORY)


def read(path):
    take = json.loads(Path(path).read_text(encoding="utf-8-sig"))
    if not isinstance(take,dict) or take.get("version") != 1 or not isinstance(take.get("events"),list):
        raise ValueError("対応する操作記録JSONを開いてください")
    duration = take.get("duration")
    if type(duration) not in (int,float) or not math.isfinite(duration) or not 0 <= duration < 89000:
        raise ValueError("ガイド音声の長さがWAVの範囲外です")
    previous = 0
    for event in take["events"]:
        if not isinstance(event,list) or len(event)!=4:
            raise ValueError("操作イベントの形式が不正です")
        t, kind, a, b = event
        if (type(t) not in (int,float) or not previous <= t <= duration or
                kind not in ("move","key","button","wheel") or type(a)!=int or type(b)!=int):
            raise ValueError("操作イベントの時刻または入力値が不正です")
        previous = t
    return take
