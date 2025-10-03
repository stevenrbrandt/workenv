#!/usr/bin/env python3
import os
import re
import sys
from subprocess import Popen, PIPE, call

if "MPI_CMD" not in os.environ:
    values = set()
    for path in os.environ["PATH"].split(os.pathsep):
        if not os.path.exists(path):
            continue
        for f in os.listdir(path):
            if re.search(r'mpirun', f) or re.search(r'mpiexec', f):
                fn = os.path.join(path, f)
                if not os.access(fn, os.X_OK):
                    continue
                fn = os.path.realpath(fn)
                if fn != __file__:
                    values.add(fn)
    if len(values) != 1:
        print("Environment variable MPI_CMD is not set.")
        if len(values) > 0:
            print("Suggested values are as follows:")
            for fn in values:
                print(" ->",fn)
        exit(1)
    else:
        for v in values:
            os.environ["MPI_CMD"] = v

from unslurm import unslurm

num_procs = 1
num_nodes = 1
node_list = None
tasks_per_node = None
for ev in os.environ:
    if ev == "SLURM_NPROCS":
        num_procs = int(os.environ["SLURM_NPROCS"])
    if ev == "SLURM_NTASKS_PER_NODE":
        tasks_per_node = int(os.environ["SLURM_NTASKS_PER_NODE"])
    if ev == "SLURM_JOB_NUM_NODES":
        num_procs = int(os.environ["SLURM_JOB_NUM_NODES"])
    if ev == "SLURM_NODELIST":
        node_list = ",".join(unslurm(os.environ["SLURM_NODELIST"]))
    if re.search(r'SLURM', ev):
        del os.environ[ev]
    if re.search(r'MODULE', ev):
        del os.environ[ev]

num_procs_arg = False
ppn_arg = False

args = []
for arg in sys.argv[1:]:
    if re.match(r'^-?-np?(=.*|)$',arg):
        num_procs_arg = True
    elif re.match(r'^-?-ppn(=.*|)$', arg):
        ppn_arg = True

if num_procs_arg and ppn_arg:
    pass
elif ppn_arg:
    pass
elif num_procs_arg:
    if tasks_per_node is not None:
        args += ["-ppn",str(tasks_per_node)]
else:
    args += ["-np",str(num_procs)]
    if tasks_per_node is not None:
        args += ["-ppn",str(tasks_per_node)]
if node_list is not None:
    args += ["-hosts", node_list]

mpi_cmd = os.environ["MPI_CMD"]
assert mpi_cmd != __file__, "Please set the MPI_CMD environment variable"
mpi_args = [mpi_cmd,"-launcher","ssh","-launcher-exec","/home/sbrandt/bin/singssh"] + args + sys.argv[1:]
    
call(mpi_args)
