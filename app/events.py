import asyncio

class DeviceBus:
    def __init__(self):
        self.subs = {}

    async def subscribe(self, uuid: str):
        q = asyncio.Queue(maxsize=100)
        self.subs.setdefault(uuid, set()).add(q)
        return q

    async def unsubscribe(self, uuid: str, q: asyncio.Queue):
        s = self.subs.get(uuid)
        if s and q in s:
            s.remove(q)
            if not s:
                self.subs.pop(uuid, None)

    async def publish(self, uuid: str, payload: dict):
        s = self.subs.get(uuid)
        if not s:
            return
        for q in list(s):
            try:
                q.put_nowait(payload)
            except asyncio.QueueFull:
                pass

bus = DeviceBus()
