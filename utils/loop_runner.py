# loop_runner.py
import asyncio
import threading
from concurrent.futures import Future

class LoopRunner:
    def __init__(self):
        self._loop = asyncio.new_event_loop()
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def _run(self):
        asyncio.set_event_loop(self._loop)
        self._loop.run_forever()

    def run(self, coro):
        # Schedule coro on the loop thread and wait synchronously.
        return asyncio.run_coroutine_threadsafe(coro, self._loop).result()

# singleton
loop_runner = LoopRunner()
