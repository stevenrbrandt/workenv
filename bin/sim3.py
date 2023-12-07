from typing import Optional, cast, Dict, List, Union, Tuple, Set
from subprocess import PIPE, Popen
from shutil import which
import os, re, sys
import argparse
import json

def cmd(cmd : List[str], cwd : Optional[str]=None)-> Tuple[str,str,int]:
    if cwd != None:
        p = Popen(cmd, stdout=PIPE, stderr=PIPE, universal_newlines=True, cwd=cwd)
    else:
        p = Popen(cmd, stdout=PIPE, stderr=PIPE, universal_newlines=True)
    o, e = p.communicate()
    print(o,end='')
    if p.returncode != 0:
        print(e,end='')
        print(cmd)
    return o,e,p.returncode

def get_machine()->str:
    o, e, rc = cmd(["hostname"])
    return o.strip()

parser = argparse.ArgumentParser(prog='simfactory3', description='A tool for building and running cactus')
parser.add_argument('--add-par', type=str, nargs=1, help='Add another par file to the set')
parser.add_argument('--rm-par', type=str, nargs=1, help='Add another par file to the set')
parser.add_argument('--config', type=str, nargs=1, required=True, help='The name of the config')
parser.add_argument('--machine', type=str, nargs=1, help='The name of the current machine')
parser.add_argument('--master', type=str, nargs=1, help='The name of the current machine')
parser.add_argument('--default-queue', type=str, nargs=1, help='The name of the queue to submit to')
parser.add_argument('--update-repos', action='store_true', default=False, help='Update git repos')
parser.add_argument('--gen-thornlist', action='store_true', default=False, help='Force regeneration of the thornlist')
parser.add_argument('--list-pars', action='store_true', default=False, help='List parameter files')
parser.add_argument('--make', action='store_true', default=False, help='Whether to build the thornlist')
pres=parser.parse_args(sys.argv[1:])

if pres.config is not None:
    config_name = pres.config[0]

config_file = os.path.join(".", "configs", f"{config_name}-config.json")
thorn_list = os.path.join(".", "configs", config_name, "ThornList")
tmp_config_file = os.path.join(".", "configs", f".{config_name}-config.json")

if os.path.exists(config_file):
    with open(config_file) as fd:
        config = json.loads(fd.read())
else:
    config = {}

if pres.update_repos:
    successes = 0
    failed = []
    for d in os.listdir("repos"):
        if os.path.exists(os.path.join("repos",d,".git")):
            print("Updating:",d)
            o,e,r=cmd(["git","pull"],cwd=os.path.join("repos",d))
            if r == 0:
                successes += 1
            else:
                failed += [d]
    print()
    print("Repos updated successfully:",successes)
    print("Failed Updates")
    for d in failed:
        print(" =>",d)

gen_thornlist = False

# Ensure "pars"
if "pars" not in config:
    config["pars"] = []
if "master_thornlist" not in config:
    config["master_thornlist"] = "./thornlists/einsteintoolkit.th"
if pres.master is not None:
    assert os.path.exists(pres.master[0]), f"File does not exist: {pres.master[0]}"
    config["master"] = pres.master[0]
if "machine" not in config:
    config["machine"] = get_machine()
if pres.machine is not None:
    config["machine"] = pres.machine[0]

old_parfiles = [x for x in config["pars"]]

if pres.add_par is not None:
    par_file = pres.add_par[0]
    assert par_file.endswith(".par") or par_file.endswith(".rpar"), \
        f"Bad suffix for par file '{par_file}'. It shoud be '.par' or '.rpar"
    if par_file.endswith(".rpar"):
       o,e,r = cmd([sys.executable, par_file])
       assert r == 0, f"Execution of {par_file} failed"
       par_file = re.sub(r'\.rpar',r'.par',par_file)
    if os.path.exists(par_file):
        config["pars"] += [par_file]
        config["pars"] = list(set(config["pars"]))
        gen_thornlist = True
    else:
        raise Exception(f"par file does not exist: {pres.add_par}")

if pres.rm_par is not None:
    par_file = pres.rm_par[0]
    config["pars"] = [x for x in config["pars"] if x != par_file]
    gen_thornlist = True

if pres.list_pars:
    for par in config["pars"]:
        print(par)

if not os.path.exists(thorn_list) and len(config["pars"]) > 0:
    gen_thornlist = True

if pres.gen_thornlist:
    gen_thornlist = True

if gen_thornlist:
    o, e, rc = cmd(["./utils/Scripts/MakeThornList","-o",thorn_list,"--master="+config["master_thornlist"]]+config["pars"])
    if rc != 0:
        print("Discarding thorn:",pres.add_par)
        config["pars"] = old_parfiles

# Actions:
#  (1) Compile configuration
#  (2) Update repos
#  (3) Run
#      set-parfile
#      set-threads-per-task
#      set-tasks-per-node
#      set-tasks
#  (4) Configure thorns:
#      add-parfile .par
#      list-parfiles
#  (5) Detect Slurm
#      (a) Select queue
#  (6) Detect Spack

#assert which("mpirun") is not None, "'mpirun' is not in path"

class Sinfo(json.JSONEncoder):
    def __init__(self, nodes:int, sockets:int, cores:int, threads:int, max_time:str, default : bool)->None:
        self.nodes = nodes
        self.sockets = sockets
        self.cores = cores
        self.threads = threads
        self.max_time = max_time
        self.default = default
    def par(self)->int:
        return self.sockets * self.nodes * self.cores * self.threads

stype = Dict[str,Sinfo]

def slurm()->stype:
    if which("sinfo") is None:
        return {}
    print("Slurm detected")
    p = Popen(["sinfo","--format=%P,%a,%D,%z,%l"],stdout=PIPE,stderr=PIPE,universal_newlines=True)
    o, e = p.communicate()
    assert p.returncode == 0, "The sinfo command returned an error"
    first_line = True
    result : stype = {}
    for line in o.split('\n'):
        rows = line.strip().split(",")
        if len(rows) == 5 and rows[1] == 'up':
            if first_line:
                first_line = False
            else:
                cpu = rows[3].split(":")
                if rows[0].endswith("*"):
                    rows[0] = rows[0][:-1]
                    is_default = True
                else:
                    is_default = False
                sdata = Sinfo(
                    nodes=int(rows[2]),
                    sockets=int(cpu[0]),
                    cores=int(cpu[1]),
                    threads=int(cpu[2]),
                    max_time=rows[4],
                    default=is_default)
                result[rows[0]] = sdata

    return result

def configure_slurm()->Dict[str,Union[stype,str]]:
    sinfo = slurm()
    if len(sinfo) > 0:
        print("Configuring Slurm:")
        default_queue = "?"
        best_par_queue = "?"
        best_par = 0
        default_par = 0
        for queue in sinfo:
            print(queue,":",sep="")
            qinfo = sinfo[queue]
            for item in qinfo.__dict__:
                print(" ",item,"=",getattr(qinfo,item))
            par = qinfo.par()
            print(" ","par","=",par)
            if par > best_par:
                best_par_queue = queue
                best_par = par
            if qinfo.default:
                default_queue = queue
                default_par = par
        if default_queue == best_par_queue:
            print("Default queue:",default_queue,"par:",default_par)
        else:
            print("Default queue:",default_queue,"par:",default_par)
            print("Biggest queue:",best_par_queue,"best:",best_par)
    return {"queues":sinfo, "default_queue":default_queue}

if "slurm" not in config:
    config["slurm"] = configure_slurm()

if pres.default_queue is not None:
    assert pres.default_queue[0] in config["slurm"]["queues"], f"Invalid queue 'pres.default_queue[0]'"
    config["slurm"]["default_queue"] = pres.default_queue[0]

# Save the config file
os.makedirs(os.path.dirname(config_file),exist_ok=True)
with open(tmp_config_file, "w") as fd:
    fd.write(json.dumps(config, default=vars))
if os.path.exists(config_file):
    os.unlink(config_file)
os.link(tmp_config_file, config_file)
os.unlink(tmp_config_file)

if pres.make:
    o,e,r = cmd(["make", pres.config[0]])
    print(o,e,end='')
