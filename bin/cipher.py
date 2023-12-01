#!/usr/bin/env python3
import sys, os, re

nz = ord('z')
nZ = ord('Z')
na = ord('a')
nA = ord('A')
n = nZ - nA + 1

off = int(sys.argv[1])
newargv = []
for txt in sys.argv[2:]:
    newtxt = ""
    for c in txt:
        n1 = ord(c)
        if na <= n1 and n1 <= nz:
            n2 = na + (n1 - na + off) % n
        elif nA <= n1 and n1 <= nZ:
            n2 = nA + (n1 - nA + off) % n
        else:
            n2 = n1
        newtxt += chr(n2)
    newargv += [newtxt]
print(" ".join(newargv))
