import os

def decoder2(bs):
    s = ''
    for c in bs:
        s += chr(c)
    return s

def readb(fd):
    fno = fd.fileno()
    b = ''
    first = True
    while True:
        c = os.read(fno, 255)
        if first:
            if c[0] == 0o357 and c[1] == 0o273 and c[2] == 0o277:
                c = c[3:]
            first = False
        if len(c) == 0:
            break
        b += decoder2(c)
    return b

def csv_split(line, delim, quote):
    row = []
    out = ""
    in_quote = False
    assert type(delim) == str
    assert type(quote) == str
    assert type(line) == str
    n = len(line)
    i = 0
    while i < n:
        c = line[i]
        i += 1
        if (not in_quote) and c == delim:
            row.append(out)
            out = ''
        elif (not in_quote) and c == '\n':
            if len(out) > 0:
                row.append(out)
            yield row
            row = []
            out = ""
        elif c == quote:
            if in_quote and i < n and line[i] == quote:
                out += quote
                i += 1
            else:
                in_quote = not in_quote
        else:
            out += c
    if len(out) > 0:
        row.append(out)
    return row

def csv_reader(fname, delim=',', quote='"'):
    with open(fname, "rb", encoding=None) as fd:
        bline = readb(fd)
    return csv_split(bline, delim=delim, quote=quote)
