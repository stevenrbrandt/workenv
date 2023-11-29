#!/usr/bin/env python3
import sys, os

if len(sys.argv) != 2:
    print(f"Usage: {sys.argv[0]} name")
    exit(2)

name = sys.argv[1]

dfname = "Dockerfile"

template =  f"""
version: '3'

#volumes:
#    home_{name}:

services:

  {name}-service:
    build:
        context: .
        dockerfile: {dfname}
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
else:
    print(f"Creating {dc}")
    with open(dc, "w") as fd:
        fd.write(template.lstrip())

dockerfile = """
FROM ubuntu:22.04
ENV DEBIAN_FRONTEND noninteractive
"""
if os.path.exists(dfname):
    print(f"{dfname} already exists")
else:
    print(f"Creating {dfname}")
    with open(dfname, "w") as fd:
        fd.write(dockerfile)
