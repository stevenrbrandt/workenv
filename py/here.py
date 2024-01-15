from colored import colored
import os
import re

_here = re.sub(r'/*$','/',os.path.realpath(os.getcwd()))

def here(*args, **kwargs):
    herell(False, *args, **kwargs)

def herecc(*args, **kwargs):
    herell(True,*args, **kwargs)

def herell(usecc, *args, **kwargs):
    import inspect
    stack = inspect.stack()
    frame = stack[2]
    if usecc:
        herestr = re.sub(r"^herecc\((.*)\)$",r"HERE: \1:",frame.code_context[0].strip())
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
