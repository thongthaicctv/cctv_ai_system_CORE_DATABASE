import gc
import threading
import time


class RuntimeCleanup:
    def __init__(self, interval=180, full_collect_every=10):
        self.interval = interval
        self.full_collect_every = max(1, int(full_collect_every))
        self.running = True
        self._cycle_count = 0
        self._thread = None

    def start(self):
        if self._thread and self._thread.is_alive():
            return

        self._thread = threading.Thread(target=self.run, daemon=True)
        self._thread.start()

    def run(self):
        while self.running:
            try:
                self._cycle_count += 1
                gc.collect(0)
                if self._cycle_count % self.full_collect_every == 0:
                    gc.collect(2)
            except Exception as exc:
                print("[RUNTIME CLEAN ERROR]", exc)

            time.sleep(self.interval)

    def stop(self):
        self.running = False
