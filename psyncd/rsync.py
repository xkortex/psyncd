#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os
import subprocess
import threading
from queue import Queue, Empty
import time
from typing import List

import inotify.adapters
from vprint import vprint

from psyncd.job import SyncJob, JobDict

DEFAULT_EVENTS = {
    "IN_CLOSE_WRITE",
    "IN_CREATE",
    "IN_DELETE",
    "IN_MOVED_FROM",
    "IN_MOVED_TO",
    "IN_MODIFY",
}


def job_to_command(job):
    # type: (SyncJob) -> List[str]
    logfile = job.get("logfile", "/tmp/psyncd/rsync.log")
    os.makedirs(os.path.dirname(logfile), exist_ok=True)
    cmd = [
        "rsync",
        "--archive",
        "--log-file={}".format(logfile),
        "--delete",
        job.get("source"),
        job.get("dest"),
    ]
    return cmd


class InotifyThread(threading.Thread):
    """
    Convenience class for calling a callback at a specified rate
    """

    def __init__(self, jobdict, job, period=0.1):
        """
        Constructor.
        @param period: desired sleep period between callbacks
        @type  period: float
        @param queue:
        @type queue: Queue
        @param job: configuration of a job
        @type job: SyncJob
        """
        if job in jobdict:
            raise RuntimeError("Job is already present in jobdict: {}".format(job))
        super(InotifyThread, self).__init__(name="inotify")
        self._queue = Queue(maxsize=1)
        jobdict[job] = self._queue
        self._job = job
        self._jobdict = jobdict
        self._callback = None
        self._period = period
        self._running = True
        self.adapter = inotify.adapters.Inotify()
        self.adapter.add_watch(job.source)
        self.daemon = True
        self.start()

    def shutdown(self):
        """
        Stop firing callbacks.
        """
        self._running = False

    def sleep(self):
        time.sleep(self._period)

    def run(self):
        vprint("Inotify start: {}".format(self._job))
        while self._running:
            self.sleep()  # is this necessary?
            for event in self.adapter.event_gen(yield_nones=False):
                header, type_names, path, filename = event
                if DEFAULT_EVENTS.intersection(set(type_names)):
                    if self._queue.full():
                        continue
                    self._queue.put(True)
                    vprint("Put: {}: {}".format(filename, type_names))


class RSyncThread(threading.Thread):
    def __init__(self, jobdict, job):
        # type: (JobDict[SyncJob, Queue[bool]], SyncJob) -> None
        super(RSyncThread, self).__init__(name="rsync")
        self._queue = jobdict[job]
        self._job = job
        self._jobdict = jobdict
        self._cmd = job_to_command(job)

        self.daemon = True

        self._running = True
        self.start()

        def shutdown(self):
            """
            Stop firing callbacks.
            """
            self._running = False

    def run(self):
        vprint("RSync start: {}".format(self._job))
        while self._running:
            # block until queue is filled
            self._queue.get()
            vprint("Synching: {}".format(self._job))
            cmd = job_to_command(self._job)
            proc = subprocess.Popen(cmd, stdin=subprocess.PIPE)
            stdout, stderr = proc.communicate()
            vprint("rsync status: {}".format(stdout))
            proc.wait()
            vprint("Synchronization finished.")
            if not self._jobdict:
                vprint("Nothing to do!")
                continue
