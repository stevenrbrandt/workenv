#!/usr/bin/env python3

import json
import os
import re
from subprocess import Popen, PIPE, call
import sys

if sys.stdout.isatty():
    try:
        from termcolor import colored
    except:
        def colored(a, _):
            return a
else:
    def colored(a, _):
        return a

home = os.environ["HOME"]

def call_cmd(cmd):
    print("Calling:"," ".join(cmd))
    return call(cmd)==0

def find_cmd(cmd):
    print(f"Looking for {cmd}...",end='')
    for p in os.environ["PATH"].split(os.path.pathsep):
        exe = os.path.join(p, cmd)
        if os.path.exists(exe) and os.access(exe, os.X_OK):
            print(exe)
            return exe
    print("Failed!")
    return None

if not find_cmd("spack"):
    print("Cannot find the spack command")
    exit(1)

print("Checking for infiniband")
ibstatus = find_cmd("ibstatus")
if ibstatus is None or not call_cmd(["ibstatus"]):
    has_fabric = False
    print("Infiniband is NOT present")
else:
    has_fabric = True
    print("Infiniband is present")

packages = os.path.join(home,".spack","packages.yaml")
if not os.path.exists(packages):
    pass
    #print("You don't have a 'packages.yaml' file yet. Configuring...")
    #call_cmd(["spack","external","find"])
else:
    print(packages,"is present")

def pp(cmd,silent=False):
    if not silent:
        print("Running command:"," ".join(cmd))
    p = Popen(cmd,stdout=PIPE,stderr=PIPE,universal_newlines=True)
    out, err = p.communicate()
    #print(out,end='')
    print(colored(err,"red"),end='')
    return out, err


def check_mpi():
    usable = {}

    out, err= pp(["spack","find","--json","mpi"])

    if "No package matches" in out:
        return usable

    print("Considering installd mpi implementations...")
    for impl in json.loads(out):
        name = impl["name"]
        h = impl["hash"]
        print(f"  impl: {name}/{h}")
        if name == "mpich":
            if "dependencies" not in impl:
                continue
            has_libfabric = "libfabric" in impl["dependencies"]
            if has_libfabric and (not has_fabric):
                good = False
            elif (not has_libfabric) and has_fabric:
                good = False
            else:
                good = True
            print("    has_fabric:",has_fabric)
        else:
            good = True
        has_hwloc = "hwloc" in impl["dependencies"]
        if not has_hwloc:
            good = true
        print("    has_hwloc:",has_hwloc)
        print("    usable:",good)
        if good:
            if name not in usable:
                usable[name] = set()
            usable[name].add(h)
    return usable

usable_mpis = check_mpi()

if len(usable_mpis) == 0:
    print("Installing mpi...")
    if has_fabric:
        out,err = pp(["spack","install","mpich"])
    else:
        out,err = pp(["spack","install","mpich","netmod=tcp","device=ch3"])
    usable_mpis = check_mpi()

def check_hdf5():
    out, err = pp(["spack","find","--json","hdf5"])

    if "No package matches" in out:
        return None

    print("Considering installed hdf5 implementations...")
    for impl in json.loads(out):
        print("  impl:",impl["hash"])
        print("    has hl?",impl["parameters"]["hl"])
        print("    has fortran?",impl["parameters"]["fortran"])
        if impl["parameters"]["hl"] and impl["parameters"]["fortran"]:
            good = True
        else:
            good = False
        print("    dependencies:")
        deps = impl["dependencies"]
        for dep in deps:
            h = deps[dep]["hash"]
            print("     ",dep, h)
            if dep in usable_mpis:
                if h not in usable_mpis[dep]:
                    good = False
                
        print("    usable:",good)
        if good:
            return impl

hdf5_impl = check_hdf5()
if hdf5_impl is None:
    install_hdf5 = True
else:
    install_hdf5 = False

if install_hdf5:
    # Prioritize mpich
    mpi_hash = None
    for mpi in ["openmpi", "mpich"]:
       if mpi in usable_mpis:
           for mpi_hash in usable_mpis[mpi]:
               break
    if mpi_hash is None:
        print("MPI install failed")
        exit(1)
    print("hdf5 not installed. Create spec")
    out, err = pp(["spack","spec","-y","hdf5","fortran=true","hl=true",f"^{mpi}/{mpi_hash}"])
    with open("spec.yaml", "w") as fd:
        fd.write(out)
    out, err = pp(["spack","install","-f","spec.yaml"])
    out, err = pp(["spack","find","--json","hdf5"])

    hdf5_impl = check_hdf5()

dirs = {}

assert hdf5_impl is not None, "HDF5 failed to install"
deps = hdf5_impl["dependencies"]
for mpi_type in deps:
    if mpi_type in ["mpich", "openmpi"]:
        mpi_hash = deps[mpi_type]["hash"]
        out, err = pp(["spack","find","--json",f"{mpi_type}/{mpi_hash}"])
        jdata = json.loads(out)
        hwloc_hash = jdata[0]["dependencies"]["hwloc"]["hash"]
        print(f"{mpi_type}_hash:",mpi_hash)
        dirs["MPI_DIR"]=f"{mpi_type}/{mpi_hash}"
        print("hwloc_hash:",hwloc_hash)
        dirs["HWLOC_DIR"]=f"hwloc/{hwloc_hash}"
        print("hdf5_hash:",hwloc_hash)
for p in ["netlib-lapack", "libjpeg", "openssl", "fftw", "zlib", "papi"]:
    out, err = pp(["spack","find","--json",p])
    if "No package matches" in out:
        out, err = pp(["spack","install",p])
        out, err = pp(["spack","find","--json",p])
    jdata = json.loads(out)
    h = jdata[0]["hash"]
    dirs[p.upper()+"_DIR"] = f"{p}/{h}"
    print(f"{p}_hash:",h)
with open("base.cfg", "w") as fd:
    for k in dirs:
        out, err = pp(["spack","find","--paths",dirs[k]])
        out = re.sub(r'(?s).*\n', '', out.strip())
        out = re.sub(r'\S+\s+', '', out)
        if k == "NETLIB-LAPACK_DIR":
            print("LAPACK_DIR=",out.strip(),sep='',file=fd)
            print("BLAS_DIR=",out.strip(),sep='',file=fd)
        else:
            print(k,"=",out.strip(),sep='',file=fd)
