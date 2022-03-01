from colored import colored

def here(*args):
    import inspect
    stack = inspect.stack()
    frame = stack[1]
    fname = frame.filename
    if fname.startswith(_here):
        fname = fname[len(_here)+1:]
    print(colored("HERE:","cyan"),fname+":"+colored(frame.lineno,"yellow"), *args, flush=True)
    frame = None
    stack = None
