from typing import Any
from colored import colored
import os
import re

_here = re.sub(r'/*$','/',os.path.realpath(os.getcwd()))

def here(*args:Any, **kwargs:Any)->None:
    herell(False, *args, **kwargs)

def herecc(*args:Any, **kwargs:Any)->None:
    herell(True,*args, **kwargs)

def herell(usecc:bool, *args:Any, **kwargs:Any)->None:
    import inspect
    stack = inspect.stack()
    frame = stack[2]
    if usecc:
        context = frame.code_context
        assert context is not None
        assert len(context) > 0
        herestr = re.sub(r"^herecc\((.*)\)$",r"HERE: \1:",context[0].strip())
    else:
        herestr = "HERE:"
    fname = os.path.realpath(frame.filename)
    if fname.startswith(_here):
        fname = fname[len(_here):]
    print(colored(herestr,"cyan"),fname+":"+colored(frame.lineno,"yellow"), *args, flush=True, **kwargs)
    frame = None
    stack = None

def foo():
    here()
if __name__ == "__main__":
    here(1,_here)
    herecc(2,_here)
    foo()
