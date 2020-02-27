#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os
import re
import threading
from queue import Queue
import time
from typing import List

import inotify.adapters
from vprint import vprint

from psyncd.job import SyncJob, JobDict
from psyncd.subproc import subproc_with_yield

shutdown_event = threading.Event()

DEFAULT_EVENTS = {
    "IN_CLOSE_WRITE",
    "IN_CREATE",
    "IN_DELETE",
    "IN_MOVED_FROM",
    "IN_MOVED_TO",
    "IN_MODIFY",
}
PAT_PERC = r"(?P<perc>\d*\.?\d*\%)"

# Use float formatting for count and total in bar_format
BAR_FMT = (
    u"{desc}{desc_pad}{percentage:3.0f}%|{bar}| {count:{len_total}.1f}/{total:.1f} "
    + u"[{elapsed}<{eta}, {rate:.2f}{unit_pad}{unit}/s]"
)

COUNTER_FMT = (
    u"{desc}{desc_pad}{count:.1f} {unit}{unit_pad}"
    + u"[{elapsed}, {rate:.2f}{unit_pad}{unit}/s]{fill}"
)


def job_to_command(job):
    # type: (SyncJob) -> List[str]
    logfile = job.get("logfile", "/tmp/psyncd/rsync.log")
    os.makedirs(os.path.dirname(logfile), exist_ok=True)
    cmd = [
        "rsync",
        "--archive",
        "--log-file={}".format(logfile),
        "--delete",
        "--info=progress2",
        job.get("source"),
        job.get("dest"),
    ]
    return cmd


class InotifyThread(threading.Thread):
    """
    Convenience class for calling a callback at a specified rate
    """

    def __init__(self, jobdict, job, period=10, sync_on_start=True, run_event=None):
        """
        Constructor.
        @param period: desired sleep period between callbacks
        @type  period: float
        @param queue:
        @type queue: Queue
        @param job: configuration of a job
        @type job: SyncJob
        @:param run_event:
        @type run_event: threading.Event
        """
        if job in jobdict:
            raise RuntimeError("Job is already present in jobdict: {}".format(job))
        super(InotifyThread, self).__init__(name="inotify")
        self._queue = Queue(maxsize=1)
        if sync_on_start:
            self._queue.put(True)
        jobdict[job] = self._queue
        self._job = job
        self._jobdict = jobdict
        self._callback = None
        self._period = period
        self._run_event = run_event
        if not self._job.get('nolisten', False):
            if os.path.isdir(job.source):
                self.adapter = inotify.adapters.InotifyTree(job.source)
            elif os.path.isfile(job.source):
                self.adapter = inotify.adapters.Inotify(job.source)
                self.adapter.add_watch(job.source)
            else:
                raise FileNotFoundError('Job source target not found: {}'.format(job.source))
        self.daemon = True
        self.start()

    def shutdown(self):
        """
        Stop firing callbacks.
        """
        self._run_event.clear()

    def sleep(self):
        time.sleep(self._period)

    def run_nolisten(self):
        # hack: this totally breaks the pattern but I don't wanna code a server-client rn
        while self._run_event.is_set():
            self._queue.put(True)
            self.sleep()

    def run(self):
        vprint("Inotify start: {}".format(self._job))
        if self._job.get('nolisten', False):
            self.run_nolisten()
            return

        while self._run_event.is_set():
            for event in self.adapter.event_gen(yield_nones=False):
                header, type_names, path, filename = event
                if filename and filename != '.git':
                    vprint('{}: {}'.format(filename, type_names))
                # todo: there is some kind of bug here where it isn't picking up files being changed correctly in nested dirs
                if DEFAULT_EVENTS.intersection(set(type_names)):
                    if self._queue.full():
                        continue
                    self._queue.put(True)
                    vprint("Put: {}: {}".format(filename, type_names))



class RSyncThread(threading.Thread):
    def __init__(self, jobdict, job, rsync_bar, run_event=None):
        # type: (JobDict[SyncJob, Queue[bool]], SyncJob, Any, threading.Event) -> None
        super(RSyncThread, self).__init__(name="rsync")
        self._queue = jobdict[job]
        self._job = job
        self._jobdict = jobdict
        self._cmd = job_to_command(job)
        self._rsync_bar = rsync_bar
        self._run_event = run_event

        self.daemon = True

        self.start()

    def shutdown(self):
        """
        Stop firing callbacks.
        """
        self._run_event.clear()

    def run(self):
        vprint("RSync start: {}".format(self._job))
        while self._run_event.is_set():
            # block until queue is filled
            self._queue.get()
            vprint("Synching: {}".format(self._job))
            cmd = job_to_command(self._job)
            for out in subproc_with_yield(cmd):

                res = re.search(PAT_PERC, out)
                if res:
                    if "perc" in res.groupdict():
                        perc = float(res.groupdict()["perc"].strip("%"))
                        self._rsync_bar.count = int(perc)
                        self._rsync_bar.refresh()
            vprint("Synchronization finished.")
            self._rsync_bar.count = 100
            self._rsync_bar.refresh()
            if not self._jobdict:
                vprint("Nothing to do!")
                continue
