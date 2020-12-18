#!/usr/bin/python3
import os

ftest = '/tmp/k.txt'
fd = os.open(ftest,os.O_CREAT|os.O_WRONLY,0o0644)
os.write(fd,b'\xef\xbb\xbfHello\n')
os.close(fd)

try:
    open(ftest,'r').read()
except UnicodeDecodeError as ude:
    print("Locality is not set up correctly. Until this is done, Python3 will not function properly.")
    for e in ["LANGUAGE", "LC_ALL", "LANG"]:
        if e not in os.environ:
            print("Consider setting the environment variable:",e)
finally:
    os.unlink(ftest)
