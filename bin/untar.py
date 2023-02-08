#!/usr/bin/env python3
from typing import Set, Optional, Iterable, Callable, Final
from termcolor import colored as is_colored
import tarfile
import sys
import os

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

def untar(file_tgz : str)->None:
    tar = tarfile.open(file_tgz, "r:gz")
    print(colored("Untar starting... Please wait...","green"))
    members = tar.getmembers()
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
        if p != progress:
            print(colored("Progress %4d%%:" % percent,"cyan"),m.name)
            progress = p
        dname = os.path.dirname(m.name)
        mk_dir(dname)

        # If this is a symbolic link, create or recreate it
        if m.linkpath != "":
            try:
                os.unlink(m.name)
            except:
                pass
            os.symlink(m.linkpath, m.name)
            continue

        # Load the status object
        try:
            st = os.stat(m.name)
        except FileNotFoundError as fnf:
            st = None

        # Does the file need updating?
        if st is None or st.st_size != m.size or st.st_mode != m.mode:

            # Attempt to extract the file
            try:
                f = tar.extractfile(m)
            except:
                print(colored("Skipping:","red"),m.name)
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
                    os.chmod(m.name, m.mode)
                # Update mtime if needed
                if m.mtime != st.st_mtime:
                    os.utime(m.name, (m.mtime, m.mtime))
                # If size matches, do nothing
                if m_size == st.st_size:
                    continue

            # Write the file
            with open(m.name, "wb") as fd:
                fd.write(content)
            os.chmod(m.name, m.mode)
            os.utime(m.name, (m.mtime, m.mtime))

            # Check that the write worked
            st = os.stat(m.name)
            assert st.st_size == m_size, f"Failed writing file {m.name}. Size should be {m_size}, was {st.st_size}"

    print(colored("Successfully unpacked file:","green"),file_tgz)

if __name__ == "__main__":
    untar(sys.argv[1])
#untar("/usr/etuser/Cactus.tar.gz")
#untar("t.tgz")
