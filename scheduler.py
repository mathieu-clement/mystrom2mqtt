#!/usr/bin/env python3

import ischedule
import threading


class Scheduler:
    def run_periodically(self, target, period):
        ischedule.schedule(target, interval=period)
        thread = threading.Thread(target=ischedule.run_loop, daemon=True)
        thread.start()
        
