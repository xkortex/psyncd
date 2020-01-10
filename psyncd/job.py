#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Describes a job, where a single job is a single config to sync one source to one dest.

This is super quick and hacky, where a job is defined by its unique fields of options.
One job is the same as another if it has the same options. Hence, we can use a
job object as a hashable item, and therefore a key in a dict/set.
"""
import addict
from collections import OrderedDict


class HashaDictMixin(dict):
    def __hash__(self):
        # type: () -> int
        ordered = sorted(self.items())
        msg = 0
        for k, v in ordered:
            msg += hash(k) + hash(v)

        return msg


class SyncJob(addict.Dict, HashaDictMixin):
    __slots__ = ['source', 'dest', 'nolisten']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)


class JobDict(OrderedDict, HashaDictMixin):
    """A Dict[SyncJob, Queue[Bool]] which allows each job to have a queue of size 1.
    This way you can't issue multiple rsync jobs when it is already running one
    todo: this is bad, don't do this
    """
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

