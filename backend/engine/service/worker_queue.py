import asyncio, uuid
class WorkerBroker:
    def __init__(self): self.q=asyncio.Queue(); self.waiters={}
    async def enqueue(self, kind,payload_json): wid=str(uuid.uuid4()); await self.q.put({'work_id':wid,'kind':kind,'payload_json':payload_json}); fut=asyncio.get_event_loop().create_future(); self.waiters[wid]=fut; return wid,fut
    async def subscribe(self, worker_id:str):
        while True: yield await self.q.get()
    async def finish(self, work_id,status,result_json):
        if work_id in self.waiters: self.waiters[work_id].set_result({'status':status,'result_json':result_json})
