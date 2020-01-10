#!/usr/bin/env python
# -*- coding: utf-8 -*-

from typing import List, Generator
import subprocess


def subproc_with_yield(cmd):
    # type: (List[str]) -> Generator[str, None, None]
    popen = subprocess.Popen(cmd, stdout=subprocess.PIPE, universal_newlines=True)
    for stdout_line in iter(popen.stdout.readline, ""):
        yield stdout_line
    popen.stdout.close()
    return_code = popen.wait()
    if return_code:
        raise subprocess.CalledProcessError(return_code, cmd)
