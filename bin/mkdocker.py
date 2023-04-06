#!/usr/bin/env python3
import sys, os

if len(sys.argv) != 2:
    print(f"Usage: {sys.argv[0]} name")
    exit(2)

name = sys.argv[1]
template =  f"""
version: '3'

#volumes:
#    home_{name}:

services:

  {name}-service:
    build:
        context: .
        dockerfile: Dockerfile
    image: stevenrbrandt/{name}
    hostname: {name}-host
    container_name: {name}
    #ports:
    #  - 8888:8888
    #volumes:
    #  - home_{name}:/home
    entrypoint: sleep infinity
"""
dc = "docker-compose.yml"
if os.path.exists(dc):
    print(f"{dc} already exists")
    exit(1)
else:
    with open(dc, "w") as fd:
        fd.write(template.lstrip())
