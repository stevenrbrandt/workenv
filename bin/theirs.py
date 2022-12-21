import sys
from subprocess import call
old = False
with open(sys.argv[1],"r") as fdr:
    with open("x","w") as fdw:
        for line in fdr.readlines():
            if "<"*7 in line:
                old = True
            elif "="*7 in line:
                old = False
            elif ">"*7 in line:
                pass
            elif not old:
                print(line,end='',file=fdw)
call(["mv","x",sys.argv[1]])
