from colored import colored
import os
import re

_here = re.sub(r'/*$','/',os.path.realpath(os.getcwd()))

def here(*args):
    herell(False,*args)

def herecc(*args):
    herell(True,*args)

def herell(usecc,*args):
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
    print(colored(herestr,"cyan"),fname+":"+colored(frame.lineno,"yellow"), *args, flush=True)
    frame = None
    stack = None

if __name__ == "__main__":
    here(1,_here)
    herecc(2,_here)
