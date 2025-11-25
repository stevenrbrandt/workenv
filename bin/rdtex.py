#!/usr/bin/env python3
import os, sys, re, json
from termcolor import colored
from subprocess import run

rd = "reading.json"
rddata = dict()
if os.path.exists(rd):
    with open(rd, "r") as fd:
        rddata = json.loads(fd.read())
elif len(sys.argv) >= 2 and os.path.exists(sys.argv[1]):
    rddata["file"] = sys.argv[1]
    if len(sys.argv) >= 3:
        rddata["skip"] = int(sys.argv[2])
    else:
        rddata["skip"] = 0
else:
    print(f"Usage: {sys.argv[0]} file skiplines")
    exit(1)

filename = rddata["file"]
assert isinstance(filename,str)

skip = rddata["skip"]
assert isinstance(skip,int)

def save():
    rddata["skip"] = skip
    with open(rd,"w") as fd:
        fd.write(json.dumps(rddata))

try:
    skip = int(sys.argv[1])-1
    save()
except:
    pass

print("Reading:", filename)
with open(filename, "r") as fd:
    for _ in range(skip):
        fd.readline()
    for line in fd.readlines():
        if re.match(r'^\s*%', line):
            skip += 1
        elif re.match(r'\\documentclass', line):
            skip += 1
        elif re.match(r'\\usepackage', line):
            skip += 1
        elif re.match(r'\\author', line):
            skip += 1
        elif re.match(r'\\end', line):
            skip += 1
        elif re.match(r'^\s*$', line):
            skip += 1
        else:
            line_raw = line

            for g in re.finditer(r'\\%|%', line):
                if g.group(0) == '%':
                    line = line[g.start()-1]
                    break

            line = re.sub(r'\\label{([^{}]*)}', r' ', line)
            line = re.sub(r'\\title{(.*)}', r'Title: \1', line)
            line = re.sub(r'\\caption{(.*)}', r'Caption: \1', line)
            line = re.sub(r'\\subsubsection{(.*)}', r'Sub Sub Section: \1', line)
            line = re.sub(r'\\subsection{(.*)}', r'Sub Section: \1', line)
            line = re.sub(r'\\section{(.*)}', r'Section: \1', line)
            line = re.sub(r'\\texttt{([^{}]*)}', r'\1', line)
            line = re.sub(r'\\textbf{([^{}]*)}', r'\1', line)
            line = re.sub(r'\\textit{([^{}]*)}', r'\1', line)
            line = re.sub(r'\~\\cite{([^{}]*)}', r' CITE', line)
            line = re.sub(r'\~\\ref{([^{}]*)}', r' REF', line)
            line = re.sub(r'\~\\eqref{([^{}]*)}', r' EQUATION', line)
            line = re.sub(r'\\_', r' ', line)
            line = re.sub(r'\s+$', '', line)
            line = re.sub(r'\\begin{itemize}', r'LIST', line)
            line = re.sub(r'\\begin{figure}.*', r'', line)
            line = re.sub(r'\\begin{minipage}.*', r'', line)
            line = re.sub(r'\\end{minipage}.*', r'', line)
            line = re.sub(r'\\centering', r'', line)
            line = re.sub(r'\\includegraphics.*', r'', line)
            line = re.sub(r'\\footnotesize', r'', line)
            line = re.sub(r'\\item ', r'ITEM ', line)
            line_raw = re.sub(r'\s+$', '', line_raw)
            print(colored(skip+1,"yellow"), line_raw)
            run(["rdme"], input=line.encode(), capture_output=True)
            save()
            skip += 1
