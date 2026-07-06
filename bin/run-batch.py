#!/usr/bin/env python3
import os
import sys
import subprocess
import time
import signal
import select
import termios
import tty
import re
from pathlib import Path
import json

HERE = os.getcwd()
ACCOUNT = os.environ.get("ACCOUNT")

def submit_job(cmd_args):
    script = f"""#!/bin/bash
#SBATCH -N 1
#SBATCH -A {ACCOUNT}
#SBATCH -p checkpt
cd {HERE}
{" ".join(cmd_args)}
"""
    tmp_script = "sbatch_tmp.sh"
    Path(tmp_script).write_text(script)
    os.chmod(tmp_script, 0o755)

    result = subprocess.run(
        ["sbatch", tmp_script],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        universal_newlines=True
    )
    if result.returncode != 0:
        print("sbatch failed:", result.stderr)
        sys.exit(1)

    for line in result.stdout.splitlines():
        g = re.search(r"Submitted batch job (\d+)", line)
        if g:
            jobid = g.group(1)
            print(f"JOB: ({jobid})")
            return jobid
    print("Failed to parse JOBID")
    sys.exit(1)

def get_output_path(jobid):
    return f"slurm-{jobid}.out"

def print_new_lines(path, last_pos):
    if not os.path.exists(path):
        return last_pos
    with open(path, "r") as f:
        f.seek(last_pos)
        new_content = f.read()
        if new_content:
            print(new_content, end="", flush=True)
        return f.tell()

def cleanup(jobid):
    print("\nCleaning up...")
    try:
        subprocess.run(["scancel", jobid], check=False)
    except Exception:
        pass
    print("Job cancelled.")

def main():
    if len(sys.argv) < 2:
        print("Usage: run-batch.py <command> [args...]")
        sys.exit(1)

    print("***********************************")
    print("Running", " ".join(sys.argv[1:]))

    jobid = submit_job(sys.argv[1:])

    def sig_handler(signum, frame):
        cleanup(jobid)
        sys.exit(0)

    signal.signal(signal.SIGINT, sig_handler)
    signal.signal(signal.SIGTERM, sig_handler)

    out_path = get_output_path(jobid)
    last_pos = 0
    print("Monitoring output (space = force update, Ctrl+C = cancel)...")

    fd = sys.stdin.fileno()
    old_settings = termios.tcgetattr(fd)
    tty.setcbreak(fd)

    try:
        while True:
            last_pos = print_new_lines(out_path, last_pos)

            result = subprocess.run(
                ["squeue", "--json", "-j", jobid],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                universal_newlines=True
            )
            result_data = json.loads(result.stdout)
            if len(result_data["jobs"]) == 0:
                job_state = "DEAD"
            else:
                job_state = result_data["jobs"][0]["job_state"][0]
            if job_state not in ["RUNNING", "PENDING"]:
                print(f"\nJob ({jobid}) is finished: {job_state}.")
                break

            rlist, _, _ = select.select([sys.stdin], [], [], 20)
            if rlist:
                key = sys.stdin.read(1)
                if key == " ":
                    print("\n--- Manual update ---")
                    last_pos = print_new_lines(out_path, last_pos)
    finally:
        termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)

if __name__ == "__main__":
    main()
