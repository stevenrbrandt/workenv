#!/usr/bin/env python3

from time import sleep
import os
import fcntl
import re
from subprocess import call

home = os.environ["HOME"]

lock_name = os.path.join(home, ".allow-lock")
perm_file = os.path.join(home, ".allow-perm")
cmd_file = os.path.join(home, ".allow-cmd")

with open(lock_name, "a") as f:
    fcntl.flock(f.fileno(), fcntl.LOCK_EX)

    try:
        os.remove(perm_file)
    except:
        pass
    assert not os.path.exists(perm_file)

    with open(cmd_file, "r") as fd:
        for line in fd.readlines():
            print(line,end='')
            pre="SSH_ORIGINAL_COMMAND:"
            if line.startswith(pre):
                cmd = line[len(pre):].strip()

    ok = input("execute? ")
    if ok.strip().lower() in ["y","yes","ok"]:
        with open(perm_file,"w") as fd:
            print(cmd,file=fd)
