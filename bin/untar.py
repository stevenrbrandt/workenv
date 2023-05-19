#!/usr/bin/env python3
from typing import Set, Optional, Iterable, Callable, Final, Union, Dict
from termcolor import colored as is_colored
import tarfile
import sys
import os
import re

def not_colored(s:str, _1:Optional[str])->str:
    return s

colored : Callable[[str, Optional[str]], str]
if not sys.stdout.isatty():
    colored = not_colored
else:
    colored = is_colored

dirs : Set[str] = set()
dirs.add("")
dirs.add(".")

def mk_dir(dname:str)->None:
    if dname in dirs:
        return
    os.makedirs(dname,exist_ok=True)
    dirs.add(dname)

def untar(file_tgz : str, require_common_dir:Union[str,bool]=False)->None:
    tar = tarfile.open(file_tgz, "r:gz")
    print(colored("Untar starting... Please wait...","green"))
    members = tar.getmembers()

    # Determine the number of directories
    dirs : Dict[str,int] = {}
    for m in members:
        g = re.match(r'^(.*)/', m.name)
        if g:
            dirname = g.group(1)
        else:
            dirname = m.name
        dirs[dirname] = dirs.get(dirname,0)+1

    new_name : str
    if type(require_common_dir) == bool and require_common_dir == True:
        if len(dirs) != 1:
            raise Exception("No common dir in tarball: "+str(list(dirs.keys())))
        rename = False
        add_name = False
    elif type(require_common_dir) == str:
        new_name = require_common_dir
        if len(dirs) == 1:
            rename = True
            add_name = False
        else:
            rename = False
            add_name = True
    else:
        add_name = False
        rename = False

    total_files : Final = len(members)
    print("Total files to unpack:",total_files)
    steps : Final = 40
    progress_factor = steps/total_files
    progress = 0
    n = 0
    for m in members:
        n += 1
        p = int(n*progress_factor)
        percent = int(100*n/total_files)
        m_name : str = m.name
        if add_name:
            m_name = new_name + "/" + m.name
        elif rename:
            m_name = re.sub(r'^[^/]*', new_name, m.name)
        if p != progress:
            print(colored("Progress %4d%%:" % percent,"cyan"),m_name)
            progress = p
        dname = os.path.dirname(m_name)
        mk_dir(dname)

        # If this is a symbolic link, create or recreate it
        if m.linkpath != "":
            try:
                os.unlink(m_name)
            except:
                pass
            os.symlink(m.linkpath, m_name)
            continue

        # Load the status object
        try:
            st = os.stat(m_name)
        except FileNotFoundError as fnf:
            st = None

        # Does the file need updating?
        if st is None or st.st_size != m.size or st.st_mode != m.mode:

            # Attempt to extract the file
            try:
                f = tar.extractfile(m)
            except:
                print(colored("Skipping:","red"),m_name)
                continue

            if f is None:
                continue

            # Compute m_size. Not sure why m.size is sometimes 0
            content = f.read()
            if m.size == 0:
                m_size = len(content)
            else:
                m_size = m.size

            if st is not None:
                # Update mode if needed
                if m.mode != st.st_mode:
                    os.chmod(m_name, m.mode)
                # Update mtime if needed
                if m.mtime != st.st_mtime:
                    os.utime(m_name, (m.mtime, m.mtime))
                # If size matches, do nothing
                if m_size == st.st_size:
                    continue

            # Write the file
            with open(m_name, "wb") as fd:
                fd.write(content)
            os.chmod(m_name, m.mode)
            os.utime(m_name, (m.mtime, m.mtime))

            # Check that the write worked
            st = os.stat(m_name)
            assert st.st_size == m_size, f"Failed writing file {m_name}. Size should be {m_size}, was {st.st_size}"

    print(colored("Successfully unpacked file:","green"),file_tgz)

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(prog='untar', description='Python-Based Untarring Command')
    parser.add_argument('filename', type=str, help='file to untar')
    parser.add_argument('--output-dir', type=str, nargs=1, help='Put files in output dir')
    parser.add_argument('--one-dir', action='store_true', default=False, help='Only untar if all files are in a common dir')
    pres=parser.parse_args(sys.argv[1:])
    if pres.output_dir:
        untar(pres.filename, require_common_dir=pres.output_dir[0])
    elif pres.one_dir:
        untar(pres.filename, require_common_dir=True)
    else:
        untar(pres.filename)
#untar("/usr/etuser/Cactus.tar.gz")
#untar("t.tgz")
