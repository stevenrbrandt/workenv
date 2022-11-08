#!/usr/bin/env python3
import os
import sys
from subprocess import call
import pwd

if len(sys.argv) != 2:
    print("Usage: "+sys.argv[0]+" docker-image")
    exit(2)

image = sys.argv[1]
user_id = os.getuid()
pw = pwd.getpwuid(user_id)
user_name = pw.pw_name
here = os.getcwd()
dir_name = "/usr/mnt"

cmd = ["docker","run","--rm","-it","--user","0","--mount",f"type=bind,source={here},target={dir_name}","-w",dir_name,image,"bash","-c",f"useradd -m {user_name} -u {user_id} -s /bin/bash -d {dir_name} && su - {user_name}"]
print(cmd)
call(cmd)
