#!/usr/bin/env python3

from time import sleep
import os
import fcntl
import re
from subprocess import Popen, PIPE, call
import socket
import sys

home = os.environ["HOME"]

lock_name = os.path.join(home, ".allow-lock")
perm_file = os.path.join(home, ".allow-perm")
cmd_file = os.path.join(home, ".allow-cmd")
out_file = os.path.join(home, ".allow-out")
err_file = os.path.join(home, ".allow-err")

defaults = {
    "SSH_ORIGINAL_COMMAND" : "bash",
    "SSH_CONNECTION" : "unknown"
}

def get_host(h):
    h0 = h[0]
    h1 = ""
    if len(h) > 1:
        if len(h[1]) > 0:
            h1 = h[1][0] # long host name
    if len(h0) > len(h1):
        return h0
    else:
        return h1

hosts = {}
def lookup_hosts(line):
    s = ''
    pos = 0
    for g in re.finditer(r'\d+(\.\d+){3}', line):
        s += line[pos:g.start()]
        ip = g.group(0)
        if ip in hosts:
            s += hosts[ip]
        else:
            h = socket.gethostbyaddr(ip)
            host = get_host(h)
            hosts[ip] = host
            s += host
        pos = g.end()
    s += line[pos:]
    return s

with open(lock_name, "a") as f:
    fcntl.flock(f.fileno(), fcntl.LOCK_EX)

    try:
        os.remove(perm_file)
    except:
        pass
    assert not os.path.exists(perm_file)

    env = {}
    with open(cmd_file, "w") as fd:
        for e in ["SSH_ORIGINAL_COMMAND","SSH_CONNECTION"]:
            val = lookup_hosts(os.environ.get(e,defaults[e]))
            print(e,":",val,sep='',file=fd)
            env[e] = val

    cmd = env["SSH_ORIGINAL_COMMAND"]
    for i in range(30):
        fcntl.flock(f.fileno(), fcntl.LOCK_UN)
        try:
            with open(perm_file, "r") as fd:
                if fd.read().strip() == cmd:
                    if cmd == "bash":
                        call(["bash"])
                    else:
                        p = Popen(re.split(r'[ \t]+', cmd),stdout=PIPE,stderr=PIPE,universal_newlines=True)
                        out, err = p.communicate()
                        with open(out_file, "w") as fw:
                            fw.write(out)
                        with open(err_file, "w") as fw:
                            fw.write(err)
                        print(out,end='')
                        print(err,end='',file=sys.stderr)
                    break
        except:
            pass
        fcntl.flock(f.fileno(), fcntl.LOCK_EX)
        with open(cmd_file, "r") as fd:
            for line in fd.readlines():
                g = re.match(r"^(\w+):(.*)", line)
                if g:
                    var = g.group(1)
                    val = g.group(2)
                    assert val == lookup_hosts(env[var]), \
                      "%s: '%s' != '%s'" % (var, val, lookup_hosts(env[var]))
        sleep(1)
