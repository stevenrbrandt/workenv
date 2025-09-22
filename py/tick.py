from typing import Dict
from time import time, sleep
import inspect
import re
import os

_here:str = re.sub(r'/*$','/',os.path.realpath(os.getcwd()))
fd = open("timing-log.txt","w")
t0:float = time()
tc:float = t0
last_key:str = "start"
timing_table:Dict[str,float] = dict()

def tick()->float:
    global t0, tc, last_key, timing_table

    t:float = time()
    frame = inspect.currentframe().f_back
    fname = os.path.realpath(frame.f_code.co_filename)
    if fname.startswith(_here):
        fname = fname[len(_here):]
    key = f"{fname}:{frame.f_lineno}"
    tm = t - tc
    tab_key = last_key + " -> " + key
    if tab_key not in timing_table:
        timing_table[tab_key] = 0
    val = timing_table[tab_key] 
    val += tm
    timing_table[tab_key] = val
    print("timing %s) %.2f %.2f" % (tab_key, tm, val))
    print("%s) %.2f %.2f" % (tab_key, tm, val),file=fd)
    fd.flush()
    tc = t
    last_key = key
    return t

def notick():
    return 0

def tick_summary():
    t:float = tick()
    print("="*50)
    print("Total time: %.f" % (t-t0))
    keys = list(timing_table.keys())
    keys = sorted(keys, key= lambda x: -timing_table[x])
    for k in keys:
        print("%20s : %.2f" % (k, timing_table[k]))

if __name__ == "__main__":
    tick()
    sleep(1)
    tick()
    sleep(2)
    tick()
    tick_summary()
