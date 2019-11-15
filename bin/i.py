#!/usr/bin/python3
import sys
ind = int(sys.argv[1])
if ind >= 0:
    sp = ' ' * ind
    for line in sys.stdin.readlines():
        print(sp,line,sep='',end='')
else:
    for line in sys.stdin.readlines():
        print(line[-ind:],sep='',end='')
