#!/usr/bin/env python3
from subprocess import Popen, PIPE
import sys
import re

assert len(sys.argv) == 3, f"Usage: {sys.argv[0]} key_file cert_file"

key_file = sys.argv[1]
cert_file = sys.argv[2]

assert re.match(r'.*\.key$', key_file), f"Not a key file: '{key_file}'"
assert re.match(r'.*\.(cer|crt|pem)$', cert_file), f"Not a cert file: '{cert_file}'"

cmd1 = ["openssl","rsa","-modulus","-noout","-in",key_file]
cmd2 = ["openssl","x509","-modulus","-noout","-in",cert_file]

def get_val(cmd):
    p = Popen(cmd, stdout=PIPE, stderr=PIPE, universal_newlines=True)
    o, e = p.communicate()
    assert e == "", f"Error from '{cmd}' is '{e}'"
    return o

val1 = get_val(cmd1)
val2 = get_val(cmd2)
if val1 == val2:
    print("Keys match!")
    exit(0)
else:
    print("Keys do NOT match!")
    exit(1)
