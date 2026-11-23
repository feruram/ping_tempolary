import json
import os
from pathlib import Path
import re
import time


class ObserverStop:
    def __init__(self, folder, pid, started):
        self.pid = pid
        self.started = started
        self.next_poll = 0
        self.last = None
        self.paths = [folder/"state.json", folder/"state-next.json"]
        config = folder/"triggers.json"
        try:
            self.rules = json.loads(config.read_text(encoding="utf-8"))
        except FileNotFoundError:
            self.rules = {}
        if not isinstance(self.rules, dict):
            raise ValueError("停止条件 triggers.json の形式が不正です")
        slots = self.rules.get("slots", [])
        if not isinstance(slots,list) or any(type(i) is not int or not 0<=i<36 for i in slots):
            raise ValueError("停止条件のスロット番号には0～35を指定してください")
        self.slot_mask = sum(1 << i for i in set(slots))

    def check(self):
        now = time.monotonic()
        if now < self.next_poll:
            return None
        self.next_poll = now + .05
        revisions = []
        for path in self.paths:
            try:
                revisions.append((path.stat().st_mtime_ns,path))
            except (FileNotFoundError, PermissionError):
                continue
        if not revisions:
            return None
        revision = max(revisions)
        if self.last == revision:
            return None
        try:
            frame = json.loads(revision[1].read_bytes())
        except (FileNotFoundError, PermissionError, ValueError):
            return None
        self.last = revision
        if not isinstance(frame,dict) or frame.get("online") is not True or frame.get("client_pid")!=self.pid:
            return None
        stamp = frame.get("sample_ms")
        now_ms = time.time_ns()//1_000_000
        if type(stamp) is not int or not 0 <= now_ms-stamp <= 500:
            return None
        chat = frame.get("chat_match_ms")
        if type(chat) is int and self.started <= chat <= stamp:
            return "チャットが停止条件に一致"
        facts = frame.get("facts")
        if isinstance(facts,dict):
            if self.rules.get("full") and facts.get("inventory_full"):
                return "インベントリが満杯"
            if self.rules.get("enemy") and facts.get("enemy_nearby"):
                return "敵の接近"
        slots = frame.get("occupied_slots")
        if type(slots) is int and slots >= 0 and slots & self.slot_mask:
            return "指定スロットが使用中"
        return None


def channel_folder():
    root = Path(os.getenv("LOCALAPPDATA") or Path.home()) / "GeneralMacros/minecraft"
    channel = os.getenv("GENERALMACROS_MINECRAFT_CHANNEL","")
    if channel and not re.fullmatch("[a-z0-9_-]{1,40}",channel):
        raise ValueError("Observerの接続名が不正です")
    return root/"channels"/channel if channel else root
