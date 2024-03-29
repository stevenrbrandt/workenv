#!/usr/bin/env python3
# USAGE: doc-dev.py docker-image-name
#
# This command starts a new shell in the current directory.
# This shell has read/write access to the local directory,
# but all other files and directories will come from the image.
#
# Note that inside the environment created by this new shell,
# the current directory will be /usr/mnt, regardless of what
# it appears to be to the external system.
#
import os
import sys
from subprocess import call
import pwd

if len(sys.argv) < 1:
    print("Usage: "+sys.argv[0]+" docker-image")
    exit(2)

image = sys.argv[1]
user_id = os.getuid()
pw = pwd.getpwuid(user_id)
user_name = pw.pw_name
here = os.getcwd()

# The directory to use inside the shell
dir_name = here #"/usr/mnt"
if len(sys.argv) > 1:
    args = " ".join(sys.argv[2:])
else:
    args = ""

vimrc = os.path.join(here, ".vimrc")
if not os.path.exists(vimrc):
    try:
        with open(vimrc,"w") as fd:
            print("set ai nu ic sw=2 ts=2 expandtab",file=fd)
    except:
        print_exc()

bashrc = os.path.join(here, ".bashrc")
if not os.path.exists(bashrc):
    try:
        with open(bashrc,"w") as fd:
            print("""
if [ "" != "${SPACK_ROOT}" ]
then
    source "$SPACK_ROOT/share/spack/setup-env.sh"
fi
alias vi=vim
""".strip(),file=fd)
    except:
        print_exc()

cmd = ["docker","run","--rm","-it","--user","0","--mount",f"type=bind,source={here},target={dir_name}","-w",dir_name,image,"bash","-c",f"useradd -m {user_name} -u {user_id} -s /bin/bash -d '{dir_name}' > /dev/null; usermod -d '{here}' $(cut -d: -f1,3 < /etc/passwd|grep :{user_id}|cut -d: -f1); su $(cut -d: -f1,3 < /etc/passwd|grep :{user_id}|cut -d: -f1) {args}"]
print(cmd)
call(cmd)
