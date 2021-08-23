#!/usr/bin/python3
import os
import sys
if sys.stdout.isatty():
    try:
        from termcolor import colored
    except:
        def colored(a,_):
            return a
else:
    def colored(a,_):
        return a

ftest = '/tmp/k.txt'
fd = os.open(ftest,os.O_CREAT|os.O_WRONLY,0o0644)
os.write(fd,b'\xef\xbb\xbfhello\n')
os.close(fd)

def run_test():
    try:
        open(ftest,'r').read()
        print(colored("Success", "green"))
    except UnicodeDecodeError as ude:
        print(colored("Failure","red"))

print("Test of current env:",end=' ')
run_test()
for utf in ["0", "1", "Unset"]:
    os.environ["PYTHONUTF8"] = utf
    if utf == "Unset":
        del os.environ["PYTHONUTF8"]
    for lang in ["C", "en_US.ISO-8859-1", "en_US.UTF-8"]:
        os.environ["LANG"] = lang
        os.environ["LANGUAGE"] = lang
        os.environ["LC_ALL"] = lang
        print("Setting PYTHONUTF8=",utf, " LANG=",lang, sep='', end=' ')
        run_test()
