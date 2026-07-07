#!/usr/bin/env python3
"""
simfactory-configure.py  —  Probe the current environment and generate
SimFactory machine-database files for the current host.

Run this on the target machine after loading the modules you plan to use
for building Cactus.  It probes compilers, MPI, GPU, libraries, and the
job scheduler, then writes:

  <name>.ini   — machine description  (mdb/machines/)
  <name>.cfg   — option list          (mdb/optionlists/)
  <name>.run   — run script           (mdb/runscripts/)
  <name>.sub   — submit script        (mdb/submitscripts/, cluster only)

Usage:
  python3 simfactory-configure.py [options]

Options:
  --name NAME          Machine nickname (default: from sim whoami)
  --install-into DIR   SimFactory root to install into (default: ./simfactory)
  --ppn N              Override physical cores per node
  --queue NAME         Default queue/partition name
  --allocation NAME    Default allocation/account name
  --scratch DIR        Scratch filesystem path (auto-detected for basedir)
  --sourcebasedir DIR  Source tree location (default: /home/@USER@)
  --email ADDR         Email for job notifications
  --cuda-arch ARCH     Override GPU SM architecture (e.g. sm_90a, sm_80)
  --verbose            Print all detected values
"""

import argparse
import datetime
import json
import os
import platform
import re
import shutil
import socket
import subprocess
import sys
import tarfile
from pathlib import Path
from typing import List, Optional, Tuple

def _tar_extractall(tf: "tarfile.TarFile", path) -> None:
    """Extract a tarfile, suppressing the RHEL/Python-3.12 security warning.

    Python 3.12 (and RHEL backports to 3.6) emit a RuntimeWarning when
    extractall() is called without an explicit filter.  Passing filter='data'
    silences it; the TypeError fallback handles truly ancient interpreters that
    don't know the parameter at all.
    """
    try:
        tf.extractall(path, filter="data")
    except TypeError:
        tf.extractall(path)

# ---------------------------------------------------------------------------
# Plan-mode globals  (set by show_plan; read by build_external_* functions)
# ---------------------------------------------------------------------------

_no_build: bool = False          # when True, build_external_* skips the real build
_build_would_build: set = set()  # populated by build_external_* in plan mode

# ---------------------------------------------------------------------------
# Externals-directory override  (set by main() from --externals-dir / state)
# ---------------------------------------------------------------------------

_ext_root: Optional[Path] = None   # resolved absolute path; None until main() runs

def _externals_dir(cactus_root: Path) -> Path:
    """Return the root of the externals tree (build/, install/, logs/)."""
    return _ext_root if _ext_root is not None else (cactus_root / "externals").resolve()

# ---------------------------------------------------------------------------
# Build logging helpers
# ---------------------------------------------------------------------------

def _open_build_log(cactus_root: Path, name: str):
    """Create externals/logs/<name>.log and return (path, writable file handle)."""
    log_dir = (_externals_dir(cactus_root) / "logs").resolve()
    log_dir.mkdir(parents=True, exist_ok=True)
    log_path = log_dir / f"{name}.log"
    return log_path, open(log_path, "w")


def _log_tail(log_path: Path, n: int = 30) -> None:
    """Print the last n lines of a build log to the terminal."""
    try:
        lines = log_path.read_text(errors="replace").splitlines()
        tail = lines[-n:] if len(lines) > n else lines
        sep = "=" * 60
        print(f"\n  {sep}", flush=True)
        print(f"  Build failed — last {len(tail)} lines of {log_path.name}:",
              flush=True)
        for line in tail:
            print(f"    {line}", flush=True)
        print(f"  Full log: {log_path}", flush=True)
        print(f"  {sep}\n", flush=True)
    except OSError:
        pass


_BUILD_CFG_ENV_KEYS = [
    "CC", "CXX", "FC", "F90", "CPP", "AR", "RANLIB",
    "CFLAGS", "CXXFLAGS", "FCFLAGS", "F90FLAGS", "CPPFLAGS", "LDFLAGS", "LIBS",
]

def _write_build_cfg(install_dir: Path, name: str,
                     env: dict, cmd: Optional[list] = None) -> None:
    """Write <install_dir>/build.cfg recording compilers, flags, and build command."""
    lines = [f"# Build configuration for {name}",
             f"# Written by simfactory-configure.py", ""]
    for key in _BUILD_CFG_ENV_KEYS:
        val = env.get(key)
        if val:
            lines.append(f"{key:<12} = {val}")
    if cmd:
        lines += ["", "# Build command:", "# " + " \\\n#   ".join(str(a) for a in cmd)]
    lines.append("")
    try:
        install_dir.mkdir(parents=True, exist_ok=True)
        (install_dir / "build.cfg").write_text("\n".join(lines))
    except OSError:
        pass   # non-fatal: the build succeeded; just skip the summary


# ---------------------------------------------------------------------------
# Utilities
# ---------------------------------------------------------------------------

import contextlib as _contextlib

@_contextlib.contextmanager
def _ignore_slurm_signals():
    """Temporarily ignore SIGTERM/SIGHUP while running a probe test inside a
    Slurm batch job.

    When srun fails (bad allocation, resource limit, etc.) inside an existing
    Slurm job, the Slurm daemon sends SIGTERM/SIGHUP to the batch job's process
    group.  Without this guard, Python receives the signal and dies before it
    can catch the RuntimeError from the failed probe — aborting the entire
    configure run.  On non-Slurm systems (no SLURM_JOB_ID) the signals are
    already at their defaults, so this is a no-op there.
    """
    if not os.environ.get("SLURM_JOB_ID"):
        yield
        return
    import signal as _signal
    old_term = _signal.signal(_signal.SIGTERM, _signal.SIG_IGN)
    old_hup  = _signal.signal(_signal.SIGHUP,  _signal.SIG_IGN)
    try:
        yield
    finally:
        _signal.signal(_signal.SIGTERM, old_term)
        _signal.signal(_signal.SIGHUP,  old_hup)


def run_cmd(*args, timeout=15, env=None) -> Tuple[int, str, str]:
    try:
        r = subprocess.run(list(args), stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                           timeout=timeout, env=env)
        return (r.returncode,
                r.stdout.decode("utf-8", errors="replace"),
                r.stderr.decode("utf-8", errors="replace"))
    except Exception as _e:
        print(f"  run_cmd({list(args)!r}) failed: {_e}", flush=True)
        return 1, "", ""

def which(cmd: str) -> Optional[str]:
    return shutil.which(cmd)

def today() -> str:
    return datetime.date.today().strftime("%Y-%m-%d")

def _resolve_compiler(name: str) -> str:
    """Return the absolute path to a compiler; keeps name as-is if not found."""
    if not name or name in ("NO_BUILD", "BUILD"):
        return name
    if Path(name).is_absolute():
        return name
    return which(name) or name


def env_dir(*var_names) -> Optional[str]:
    """Return value of first env var whose path exists."""
    for v in var_names:
        val = os.environ.get(v, "")
        if val and Path(val).exists():
            return val
    return None

_SIM = Path("simfactory/bin/sim")

def _sim_whoami() -> Optional[str]:
    """Ask SimFactory for the canonical machine name for this host."""
    sim_path = Path.cwd() / _SIM
    try:
        r = subprocess.run(
            [str(sim_path), "whoami"],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            timeout=15,
        )
        r.stdout = r.stdout.decode("utf-8", errors="replace")
        r.stderr = r.stderr.decode("utf-8", errors="replace")
        combined = r.stdout + r.stderr
        m = re.search(r"Current machine:\s*(\S+)", combined)
        if m:
            return m.group(1)
        # Didn't match — print what sim actually said so the user can diagnose
        print(f"  sim whoami: no 'Current machine' in output (rc={r.returncode})")
        for line in combined.splitlines():
            print(f"    {line}")
        return None
    except FileNotFoundError:
        print(f"  sim whoami: {sim_path} not found")
        return None
    except Exception as e:
        print(f"  sim whoami: failed ({e})")
        return None

def pkg_prefix(pkg: str) -> Optional[str]:
    if not which("pkg-config"):
        return None
    rc, out, _ = run_cmd("pkg-config", "--variable=prefix", pkg)
    return out.strip() or None if rc == 0 else None

_SYSTEM_DIRS = {"/usr", "/usr/local", "/"}

def _parse_flags(text: str, flag: str) -> List[str]:
    """Extract -I, -L, or -l values; skip system paths for -I/-L."""
    # Require flag to be preceded by space or start-of-string to avoid
    # matching e.g. '-l' inside '-L/path/lib'
    pattern = rf"(?:^|\s){re.escape(flag)}(\S+)"
    results = re.findall(pattern, text)
    # Intel MPI and HDF5 wrappers emit paths with literal surrounding quotes,
    # e.g.  -I"/path/to/include"  or  -L"/path/to/lib".  Strip them so the
    # resulting paths are valid filesystem paths.
    results = [r.strip("\"'") for r in results]
    if flag in ("-I", "-L"):
        results = [r for r in results if r not in _SYSTEM_DIRS]
    return results

def module_cmd(*args) -> Tuple[int, str]:
    """Run 'module <args>' through bash; return (rc, combined_output)."""
    cmd = "module " + " ".join(args) + " 2>&1"
    for init in (
        "source /etc/profile.d/modules.sh 2>/dev/null",
        "source /etc/profile.d/lmod.sh 2>/dev/null",
        "",
    ):
        prefix = init + "; " if init else ""
        rc, out, err = run_cmd("bash", "-c", f"{prefix}{cmd}", timeout=20)
        combined = out + err
        if combined.strip():
            return rc, combined
    return 1, ""

# ---------------------------------------------------------------------------
# Hardware
# ---------------------------------------------------------------------------

class Hardware:
    cpu_model = "unknown"
    logical_cpus = 1
    cores_per_socket = 1
    sockets = 1
    threads_per_core = 1
    mem_mb = 0
    simd = "NONE"   # SSE2 | AVX | AVX2 | AVX512F | NEON | SVE | VSX | NONE

    @property
    def ppn(self):
        return self.sockets * self.cores_per_socket


def _detect_simd() -> str:
    """Return the highest SIMD tier available on this CPU."""
    arch = platform.machine().lower()
    cpuinfo = Path("/proc/cpuinfo")

    if arch in ("x86_64", "amd64"):
        if cpuinfo.exists():
            for line in cpuinfo.read_text().splitlines():
                if line.startswith("flags"):
                    flags = set(line.split(":", 1)[1].split())
                    if "avx512f" in flags:
                        return "AVX512F"
                    if "avx2" in flags:
                        return "AVX2"
                    if "avx" in flags:
                        return "AVX"
                    if "sse2" in flags:
                        return "SSE2"
                    break
        return "SSE2"   # x86_64 architectural minimum

    if arch in ("aarch64", "arm64"):
        if cpuinfo.exists():
            for line in cpuinfo.read_text().splitlines():
                if line.startswith("Features"):
                    features = set(line.split(":", 1)[1].split())
                    if "sve" in features:
                        return "SVE"
                    break
        return "NEON"   # aarch64 architectural minimum

    if arch.startswith("ppc64"):
        return "VSX"

    return "NONE"


def _simd_flags(simd: str, compiler_kind: str) -> str:
    """Return additional compiler flags for the detected SIMD tier."""
    if compiler_kind in ("cray",):
        return ""   # Cray PE targeting flags are set by the wrapper

    mapping = {
        "AVX512F": "-mavx512f -mavx512cd -mavx512bw -mavx512dq -mavx512vl -mfma",
        "AVX2":    "-mavx2 -mfma",
        "AVX":     "-mavx",
        "SSE2":    "-msse2",
        "VSX":     "-mvsx",
    }
    if simd in mapping:
        return mapping[simd]

    if simd in ("SVE", "NEON"):
        if compiler_kind == "gnu":
            return "-march=native"
        if compiler_kind == "intel":
            return "-xHost"
        # nvhpc and others handle ARM arch automatically
        return ""

    return ""


def detect_hardware() -> Hardware:
    hw = Hardware()
    rc, out, _ = run_cmd("lscpu")
    if rc == 0:
        def field(name):
            m = re.search(rf"^{re.escape(name)}\s*:\s*(.+)$", out, re.MULTILINE)
            return m.group(1).strip() if m else None
        hw.cpu_model       = field("Model name") or "unknown"
        hw.logical_cpus    = int(field("CPU(s)") or 1)
        hw.threads_per_core = int(field("Thread(s) per core") or 1)
        hw.cores_per_socket = int(field("Core(s) per socket") or 1)
        hw.sockets          = int(field("Socket(s)") or 1)
    else:
        rc2, out2, _ = run_cmd("nproc")
        if rc2 == 0:
            hw.logical_cpus = hw.cores_per_socket = int(out2.strip())

    mi = Path("/proc/meminfo")
    if mi.exists():
        m = re.search(r"MemTotal:\s+(\d+)", mi.read_text())
        if m:
            hw.mem_mb = int(m.group(1)) // 1024

    hw.simd = _detect_simd()
    return hw

# ---------------------------------------------------------------------------
# Modules
# ---------------------------------------------------------------------------

class Modules:
    available = False
    loaded: List[str] = []

def detect_modules() -> Modules:
    m = Modules()
    m.loaded = []
    rc, out = module_cmd("list")
    # Real module systems print "Currently Loaded" in their output.
    # If that marker is absent the module command isn't present or failed.
    if "loaded" not in out.lower():
        return m
    m.available = True
    # Parse lines that contain N) module-tokens after the header
    in_list = False
    for line in out.splitlines():
        ll = line.lower()
        if "currently loaded" in ll or "loaded module" in ll:
            in_list = True
            continue
        if not in_list:
            continue
        # Each non-blank token may be prefixed by "N)"
        for chunk in line.split():
            chunk = re.sub(r'^\d+[)\.]', '', chunk).strip()
            # Strip module-system display annotations: (default), (loaded), (L), etc.
            chunk = re.sub(r'\([^)]*\)', '', chunk).strip()
            # Accept only plausible module names: contain letters, optionally /version
            if re.match(r'^[A-Za-z][A-Za-z0-9_\-+.]*(/[A-Za-z0-9_\-+.]+)*$', chunk):
                m.loaded.append(chunk)
    return m

# ---------------------------------------------------------------------------
# Scheduler
# ---------------------------------------------------------------------------

class Scheduler:
    kind = "none"           # slurm | pbs | lsf | none
    default_queue = ""
    submit = ""
    getstatus = ""
    stop = ""
    submitpattern = ""
    statuspattern = ""
    queuedpattern = ""
    runningpattern = ""
    holdingpattern = ""
    exechost = ""
    exechostpattern = ""

def detect_scheduler(queue_hint: str = "") -> Scheduler:
    s = Scheduler()

    if which("sbatch") and which("squeue"):
        s.kind = "slurm"
        s.default_queue = queue_hint or _slurm_default_queue()
        s.submit         = "sbatch @SCRIPTFILE@"
        s.getstatus      = "squeue -j @JOB_ID@"
        s.stop           = "scancel @JOB_ID@"
        s.submitpattern  = "Submitted batch job ([0-9]+)"
        s.statuspattern  = "@JOB_ID@ "
        s.queuedpattern  = " PD "
        s.runningpattern = " (CF|CG|R|TO) "
        s.holdingpattern = r"\(JobHeldUser\)"
        s.exechost       = "hostname -s"
        s.exechostpattern = r"(\S+)"

    elif which("qsub") and which("qstat"):
        s.kind = "pbs"
        s.default_queue  = queue_hint
        s.submit         = "qsub @SCRIPTFILE@"
        s.getstatus      = "qstat @JOB_ID@"
        s.stop           = "qdel @JOB_ID@"
        s.submitpattern  = r"(\d+\.\S+|\d+)"
        s.statuspattern  = "@JOB_ID@"
        s.queuedpattern  = " Q "
        s.runningpattern = " R "
        s.holdingpattern = " H "
        s.exechost       = "hostname -s"
        s.exechostpattern = r"(\S+)"

    elif which("bsub") and which("bjobs"):
        s.kind = "lsf"
        s.default_queue  = queue_hint
        s.submit         = "bsub < @SCRIPTFILE@"
        s.getstatus      = "bjobs @JOB_ID@"
        s.stop           = "bkill @JOB_ID@"
        s.submitpattern  = r"Job <(\d+)>"
        s.statuspattern  = "@JOB_ID@"
        s.queuedpattern  = "PEND"
        s.runningpattern = "RUN"
        s.holdingpattern = "USUSP"
        s.exechost       = "hostname -s"
        s.exechostpattern = r"(\S+)"

    else:
        s.kind           = "none"
        s.submit         = ("exec nohup @SCRIPTFILE@ < /dev/null "
                            "> @RUNDIR@/@SIMULATION_NAME@.out "
                            "2> @RUNDIR@/@SIMULATION_NAME@.err & echo $!")
        s.getstatus      = "ps @JOB_ID@"
        s.stop           = r"pkill -g $(ps -o pgid= -p @JOB_ID@)"
        s.submitpattern  = "(.*)"
        s.statuspattern  = '"^ *@JOB_ID@ "'
        s.queuedpattern  = "$^"
        s.runningpattern = "^"
        s.holdingpattern = "$^"
        s.exechost       = "echo localhost"
        s.exechostpattern = "(.*)"

    return s

def _slurm_default_queue() -> str:
    rc, out, _ = run_cmd("sinfo", "--noheader", "-o", "%P")
    if rc == 0:
        parts = [p.rstrip("*") for p in out.split()]
        for pref in ("cpu", "regular", "normal", "compute", "batch"):
            for p in parts:
                if pref in p.lower():
                    return p
        if parts:
            return parts[0]
    return "normal"

# ---------------------------------------------------------------------------
# Compilers
# ---------------------------------------------------------------------------

class Compilers:
    kind = "gnu"
    CC   = "gcc"
    CXX  = "g++"
    F90  = "gfortran"
    CPP  = "cpp"
    FPP  = "cpp"
    CFLAGS   = "-g -O2 -std=gnu99"
    CXXFLAGS = "-g -O2 -std=c++17 -D_GNU_SOURCE"
    F90FLAGS = "-g -O2 -fcray-pointer -ffixed-line-length-none"
    omp_flag   = "-fopenmp"
    omp_ld     = "-fopenmp"
    extra_libs = ""

def _is_cray() -> bool:
    return bool(
        os.environ.get("CRAYPE_DIR") or
        os.environ.get("PE_ENV") or
        os.environ.get("CRAY_SITE_LIST_DIR")
    )

def detect_compilers() -> Compilers:
    c = Compilers()

    if _is_cray():
        c.kind     = "cray"
        c.CC, c.CXX, c.F90 = "cc", "CC", "ftn"
        c.CFLAGS   = "-g -O2"
        c.CXXFLAGS = "-g -O2 -std=c++17"
        c.F90FLAGS = "-g -O2 -fcray-pointer -ffixed-line-length-none"
        return c

    if which("icx") or which("icc"):
        c.kind     = "intel"
        c.CC       = "icx"  if which("icx")  else "icc"
        c.CXX      = "icpx" if which("icpx") else "icpc"
        c.F90      = "ifx"  if which("ifx")  else "ifort"
        c.CFLAGS   = "-g -O2"
        c.CXXFLAGS = "-g -O2 -std=c++17"
        c.F90FLAGS = "-g -O2 -align -pad -xHOST"
        c.omp_flag = "-qopenmp"
        c.omp_ld   = "-qopenmp"
        c.extra_libs = "ifcoremt imf svml intlc"
        c.CC  = _resolve_compiler(c.CC)
        c.CXX = _resolve_compiler(c.CXX)
        c.F90 = _resolve_compiler(c.F90)
        return c

    if which("nvc") and which("nvc++"):
        c.kind     = "nvhpc"
        c.CC, c.CXX, c.F90 = "nvc", "nvc++", "nvfortran"
        c.CFLAGS   = "-g -O2"
        c.CXXFLAGS = "-g -O2 -std=c++17"
        c.F90FLAGS = "-g -O2"
        c.omp_flag = "-mp"
        c.omp_ld   = "-mp"
        c.CC  = _resolve_compiler(c.CC)
        c.CXX = _resolve_compiler(c.CXX)
        c.F90 = _resolve_compiler(c.F90)
        return c

    # GNU (default); Cray wrappers are short names resolved by the module
    # system, so only non-Cray paths reach here and all need full resolution.
    c.kind = "gnu"
    c.CC   = _resolve_compiler("gcc")
    c.CXX  = _resolve_compiler("g++")
    c.F90  = _resolve_compiler("gfortran") if which("gfortran") else "NO_BUILD"
    # GCC 8 and earlier ship std::filesystem in a separate libstdc++fs.
    # From GCC 9 onwards it is part of libstdc++ itself.
    if _gcc_major(c.CXX) < 9:
        c.extra_libs = "stdc++fs"
    return c

# ---------------------------------------------------------------------------
# MPI
# ---------------------------------------------------------------------------

class MPI:
    found       = False
    kind        = ""
    dir         = ""
    inc_dirs    = ""
    lib_dirs    = ""
    libs        = ""
    bin_dir     = ""          # added to PATH in envsetup; also set for fs-detected MPI not yet in PATH
    module_name = ""          # e.g. "mvapich2/2.3.7/intel-2021.5.0" — overrides loaded MPI module
    launcher    = "mpirun -np @NUM_PROCS@"
    cc  = ""        # underlying C compiler revealed by the MPI wrapper
    cxx = ""        # underlying C++ compiler
    f90 = ""        # underlying Fortran compiler


# Executables that are compiler caches / distributor wrappers, not compilers.
_COMPILER_CACHE_WRAPPERS = {"ccache", "distcc", "sccache", "icecc"}


def _gcc_major(cxx: str) -> int:
    """Return the GCC major version of `cxx`, or 0 on failure."""
    rc, out, _ = run_cmd(cxx, "--version")
    m = re.search(r'\b(\d+)\.\d+\.\d+', out or "")
    return int(m.group(1)) if m else 0


def _cuda_lib_dir(nvcc_path: str) -> str:
    """Return the CUDA library directory containing libcudart, or ''."""
    root = Path(nvcc_path).resolve().parent.parent
    for candidate in (
        root / "lib64",
        root / "lib",
        root / "targets" / "x86_64-linux" / "lib",
        root / "targets" / "aarch64-linux"  / "lib",
    ):
        if ((candidate / "libcudart.so").exists()
                or (candidate / "libcudart_static.a").exists()
                or list(candidate.glob("libcudart.so.*"))):
            return str(candidate)
    return ""


def _nvcc_max_gcc(nvcc_path: str) -> int:
    """Return the maximum GCC major version supported by this nvcc install.

    Reads the threshold directly from CUDA's host_config.h which contains
    ``#if __GNUC__ > N`` — the authoritative source, no hard-coded table needed.
    Returns 0 if the file cannot be found or parsed.
    """
    root = Path(nvcc_path).resolve().parent.parent
    for hcfg in (
        root / "targets" / "x86_64-linux" / "include" / "crt" / "host_config.h",
        root / "targets" / "aarch64-linux"/ "include" / "crt" / "host_config.h",
        root / "include" / "crt" / "host_config.h",
    ):
        if not hcfg.exists():
            continue
        try:
            text = hcfg.read_text(errors="replace")
        except OSError:
            continue
        m = re.search(r'__GNUC__\s*>\s*(\d+)', text)
        if m:
            return int(m.group(1))
    return 0


def _first_real_compiler(show_output: str) -> str:
    """Return the first non-flag, non-cache-wrapper token from mpicc -show output."""
    for tok in show_output.split():
        if tok.startswith("-"):
            break
        if Path(tok).name.lower() not in _COMPILER_CACHE_WRAPPERS:
            return tok
    return ""


def _query_mpi_compilers(bin_dir: str = "") -> Tuple[str, str, str]:
    """Ask MPI wrappers what underlying compilers they wrap.
    bin_dir: directory containing the wrappers; falls back to PATH if not given.
    Returns (cc, cxx, f90); any may be ''."""

    def _ask(names: List[str]) -> str:
        for name in names:
            if bin_dir:
                w = str(Path(bin_dir) / name)
                if not os.access(w, os.X_OK):
                    w = which(name) or ""
            else:
                w = which(name) or ""
            if not w:
                continue
            for flag in ("--showme:compile", "--compile-info", "-show"):
                rc, out, _ = run_cmd(w, flag)
                if rc == 0 and out.strip():
                    comp = _first_real_compiler(out)
                    if comp:
                        return comp
        return ""

    cc  = _ask(["mpicc",   "mpiicc"])
    cxx = _ask(["mpicxx",  "mpiicpc", "mpiCC",   "mpic++"])
    f90 = _ask(["mpifort", "mpiifort", "mpif90",  "mpif77"])
    return cc, cxx, f90


def _compilers_from_mpi(mpi: "MPI", existing: "Compilers") -> "Compilers":
    """Rebuild a Compilers object using the executables the MPI wrappers revealed.
    Keeps existing values for any field the wrappers didn't provide."""
    cc  = mpi.cc  or existing.CC
    cxx = mpi.cxx or existing.CXX
    f90 = mpi.f90 or existing.F90

    c      = Compilers()
    c.CC   = _resolve_compiler(cc)
    c.CXX  = _resolve_compiler(cxx)
    c.F90  = _resolve_compiler(f90)

    name = Path(cc).name.lower()
    if name in ("icc", "icx"):
        c.kind       = "intel"
        c.CFLAGS     = "-g -O2"
        c.CXXFLAGS   = "-g -O2 -std=c++17"
        c.F90FLAGS   = "-g -O2 -align -pad -xHOST"
        c.omp_flag   = "-qopenmp"
        c.omp_ld     = "-qopenmp"
        c.extra_libs = "ifcoremt imf svml intlc"
    elif name in ("nvc", "pgcc"):
        c.kind     = "nvhpc"
        c.CFLAGS   = "-g -O2"
        c.CXXFLAGS = "-g -O2 -std=c++17"
        c.F90FLAGS = "-g -O2"
        c.omp_flag = "-mp"
        c.omp_ld   = "-mp"
    elif name == "cc" and _is_cray():
        c.kind     = "cray"
        c.CFLAGS   = "-g -O2"
        c.CXXFLAGS = "-g -O2"
        c.F90FLAGS = "-g -O2 -fcray-pointer -ffixed-line-length-none"
    else:
        # GNU defaults are already set; check if stdc++fs is needed.
        if _gcc_major(c.CXX) < 9:
            c.extra_libs = "stdc++fs"
    return c

def _detect_mpi_system(sched=None, cactus_root=None) -> "MPI":
    """Find a working system MPI.
    On Slurm, each candidate must have PMI support and pass a live srun test."""

    if _is_cray():
        m = MPI()
        m.found    = True
        m.kind     = "cray"
        m.launcher = "srun -n @NUM_PROCS@"
        d = env_dir("CRAY_MPICH_DIR", "CRAY_MPICH_BASEDIR", "MPICH_DIR")
        if d:
            m.dir = d
        return m

    on_slurm = sched is not None and sched.kind == "slurm"

    # Collect candidate mpicc paths in priority order (deduplicated by realpath).
    seen: set = set()
    candidates: List[str] = []

    def _add(path: Optional[str]) -> None:
        if not path or not os.access(path, os.X_OK):
            return
        rp = str(Path(path).resolve())
        lp = rp.lower()
        if rp not in seen and "conda" not in lp and "anaconda" not in lp:
            seen.add(rp)
            candidates.append(path)

    # 1. mpicc already on PATH (module loaded by caller — highest priority)
    _add(which("mpicc"))

    # 2. Intel MPI via env-var root
    for _iv in ("I_MPI_ROOT", "IMPI_ROOT", "INTEL_MPI_ROOT", "I_MPI_SDK_ROOT"):
        _ir = os.environ.get(_iv, "")
        if _ir:
            _add(f"{_ir}/bin/mpicc")
            _add(f"{_ir}/intel64/bin/mpicc")
            break

    # 3. Filesystem scan: MPICH-family first (better Slurm/PMI integration),
    #    then OpenMPI.  Take the newest version (last when sorted lexically).
    import glob as _glob_sys
    for _pat in [
        "/usr/local/packages/mvapich2/*/*/bin/mpicc",
        "/usr/local/packages/mpich/*/*/bin/mpicc",
        "/opt/mvapich2/*/*/bin/mpicc",
        "/opt/mpich/*/*/bin/mpicc",
        "/usr/local/packages/openmpi/*/*/bin/mpicc",
        "/usr/local/packages/openmpi/*/bin/mpicc",
        "/opt/openmpi/*/bin/mpicc",
        "/apps/openmpi/*/bin/mpicc",
        "/apps/mpich/*/bin/mpicc",
        "/sw/openmpi/*/bin/mpicc",
        "/sw/mpich/*/bin/mpicc",
    ]:
        _hits = sorted(_glob_sys.glob(_pat))
        _add(next((h for h in reversed(_hits)), None))

    for mpicc in candidates:
        print(f"  MPI: probing {mpicc} …", flush=True)
        m = _extract_mpi_from_mpicc(mpicc)
        if m is None:
            print(f"  MPI: {mpicc} — wrapper unresponsive, skipping", flush=True)
            continue

        if on_slurm:
            lib_dir = (m.lib_dirs.split()[0] if m.lib_dirs
                       else str(Path(m.dir) / "lib"))
            if not _has_pmi_support(lib_dir):
                print(f"  MPI: {mpicc} — no PMI support, skipping", flush=True)
                continue
            if cactus_root and not _no_build:
                try:
                    _test_mpi(mpicc, cactus_root, sched, n_ranks=2,
                              module_name=m.module_name or "")
                except Exception as _te:
                    print(f"  MPI: {mpicc} — srun test failed ({_te}), skipping",
                          flush=True)
                    continue

        cc_desc = f"  CC={m.cc}" if m.cc else ""
        print(f"  MPI: selected {m.kind} at {m.dir}{cc_desc}", flush=True)
        return m

    # Env-var fallback (module loaded but mpicc not on PATH; skip srun test)
    d = env_dir("MPI_HOME", "MPI_DIR", "MPICH_DIR", "OMPI_HOME")
    if d:
        m = MPI()
        m.found    = True
        m.kind     = "unknown"
        m.dir      = d
        m.inc_dirs = f"{d}/include"
        m.lib_dirs = f"{d}/lib"
        m.libs     = "mpi"
        return m

    return MPI()


def _hpc_mpi_postprocess(m: "MPI", mpicc: str, prefix: str) -> None:
    """Post-process a filesystem-detected MPI: derive module name and set bin_dir."""
    for _pkg_root in ("/usr/local/packages/", "/opt/", "/apps/", "/sw/"):
        if prefix.startswith(_pkg_root):
            m.module_name = prefix[len(_pkg_root):]
            break
    if not which(Path(mpicc).name):
        m.bin_dir = str(Path(mpicc).parent)


def _extract_mpi_from_mpicc(mpicc_path: str) -> Optional["MPI"]:
    """Extract MPI metadata from an mpicc wrapper. Returns None if unresponsive."""
    prefix  = str(Path(mpicc_path).parent.parent)
    bin_dir = str(Path(mpicc_path).parent)
    m = MPI()

    # OpenMPI: --showme:compile / --showme:link
    rc, show, _ = run_cmd(mpicc_path, "--showme:compile")
    if rc == 0 and show.strip():
        rc2, lshow, _ = run_cmd(mpicc_path, "--showme:link")
        m.found    = True
        m.kind     = "openmpi"
        m.dir      = prefix
        m.inc_dirs = " ".join(_parse_flags(show, "-I"))
        m.lib_dirs = " ".join(_parse_flags(lshow, "-L")) if rc2 == 0 else ""
        libs = _parse_flags(lshow, "-l") if rc2 == 0 else []
        mpicxx = str(Path(bin_dir) / "mpicxx")
        if os.access(mpicxx, os.X_OK):
            rc3, lshow_cxx, _ = run_cmd(mpicxx, "--showme:link")
            if rc3 == 0 and lshow_cxx.strip():
                extra = [l for l in _parse_flags(lshow_cxx, "-l") if l not in libs]
                libs = extra + libs
        if "mpi_cxx" not in libs:
            try:
                libs.insert(libs.index("mpi"), "mpi_cxx")
            except ValueError:
                libs = ["mpi_cxx"] + libs
        m.libs = " ".join(libs)
        m.cc   = _first_real_compiler(show)
        _, m.cxx, m.f90 = _query_mpi_compilers(bin_dir=bin_dir)
        _hpc_mpi_postprocess(m, mpicc_path, prefix)
        return m

    # MPICH: -show
    rc, show, _ = run_cmd(mpicc_path, "-show")
    if rc == 0 and show.strip():
        mpicc_lower = mpicc_path.lower()
        m.found    = True
        m.kind     = ("mvapich2" if "mvapich"  in mpicc_lower else
                      "impi"    if any(k in mpicc_lower for k in ("intel", "impi")) else
                      "mpich")
        m.dir      = prefix
        m.inc_dirs = " ".join(_parse_flags(show, "-I"))
        m.lib_dirs = " ".join(_parse_flags(show, "-L"))
        m.libs     = " ".join(_parse_flags(show, "-l"))
        m.cc       = _first_real_compiler(show)
        _, m.cxx, m.f90 = _query_mpi_compilers(bin_dir=bin_dir)
        _hpc_mpi_postprocess(m, mpicc_path, prefix)
        return m

    # Path-structure fallback for wrappers that don't support either flag
    inc = Path(prefix) / "include"
    lib = Path(prefix) / "lib"
    if (inc / "mpi.h").exists() and lib.is_dir():
        m.found    = True
        m.kind     = "unknown"
        m.dir      = prefix
        m.inc_dirs = str(inc)
        m.lib_dirs = str(lib)
        m.libs     = "mpi"
        _, m.cxx, m.f90 = _query_mpi_compilers(bin_dir=bin_dir)
        _hpc_mpi_postprocess(m, mpicc_path, prefix)
        return m

    return None


def build_external_mpi(cactus_root: Path, opts: dict, jobs: int = 1,
                        pmi_prefix: str = "", clean: bool = False) -> Path:
    install_dir = (_externals_dir(cactus_root) / "install" / "mpi").resolve()
    if clean and install_dir.exists():
        print("  MPI: --mpi-clean requested — wiping existing build …", flush=True)
        import shutil as _mpi_rmsh
        _mpi_rmsh.rmtree(str(install_dir), ignore_errors=True)
    if (install_dir / "bin" / "mpicc").exists():
        # If caller needs PMI support but the existing build lacks it, rebuild.
        if pmi_prefix and not _has_pmi_support(str(install_dir / "lib")):
            print("  MPI: existing build lacks PMI support — rebuilding with "
                  f"--with-pmi={pmi_prefix} …", flush=True)
            import shutil as _mpi_rmsh
            _mpi_rmsh.rmtree(str(install_dir), ignore_errors=True)
        elif not (install_dir / "lib" / "libmpi_mpifh.a").exists():
            print("  MPI: Fortran bindings missing (libmpi_mpifh.a) — rebuilding …",
                  flush=True)
            import shutil as _mpi_rmsh
            _mpi_rmsh.rmtree(str(install_dir), ignore_errors=True)
        elif _has_intel_symbols(install_dir / "lib"):
            print("  MPI: existing build has Intel symbols — rebuilding with "
                  "current toolchain …", flush=True)
            import shutil as _mpi_rmsh
            _mpi_rmsh.rmtree(str(install_dir), ignore_errors=True)
        else:
            print("  MPI: already built, skipping.")
            return install_dir
    if _no_build:
        _build_would_build.add("mpi")
        return install_dir

    name = "openmpi-4.0.6"
    tarball = (cactus_root / "arrangements" / "ExternalLibraries"
               / "MPI" / "dist" / f"{name}.tar.gz")
    if not tarball.exists():
        raise FileNotFoundError(f"MPI tarball not found: {tarball}")

    build_root = (_externals_dir(cactus_root) / "build" / "mpi").resolve()
    build_root.mkdir(parents=True, exist_ok=True)
    install_dir.mkdir(parents=True, exist_ok=True)

    # Wipe stale source tree so autoconf cache from a previous (possibly
    # --disable-mpi-fortran) run doesn't interfere with a fresh configure.
    import shutil as _mpi_src_sh
    _mpi_src_pre = build_root / name
    if _mpi_src_pre.exists():
        _mpi_src_sh.rmtree(str(_mpi_src_pre))

    log_path, log = _open_build_log(cactus_root, "mpi")
    print(f"  MPI: extracting {tarball.name} …  (log → {log_path.name})")
    with tarfile.open(tarball) as tf:
        _tar_extractall(tf, build_root)

    src_dir = build_root / name

    env = os.environ.copy()
    # Use opts compilers explicitly; don't fall back to environment CC/CXX since
    # HPC environments often have Intel compilers loaded that are incompatible
    # with GCC-compiled Cactus.
    _defaults = {"CC": which("gcc") or "gcc", "CXX": which("g++") or "g++"}
    for var in ("CC", "CXX"):
        val = opts.get(var, _defaults[var])
        val = re.sub(r"^\s*ccache\s+(-\S+\s+)*", "", val).strip()
        if val:
            env[var] = val

    # If opts has Intel compilers, switch to GCC.  OpenMPI compiled with Intel
    # embeds calls to _intel_fast_memcpy/_intel_fast_memset (undefined refs to
    # libintlc.so.5) that cmake-based downstream builds (ADIOS2 etc.) cannot
    # resolve when linking with GCC, causing MPI_C/CXX_WORKS failures.
    _mpi_build_cc = env.get("CC", "gcc")
    if Path(_mpi_build_cc).name in ("icc", "icx") and which("gcc"):
        print(f"  MPI: switching CC {_mpi_build_cc} → gcc "
              "(avoids Intel runtime symbols in libmpi.a)", flush=True)
        env["CC"] = which("gcc")
    _mpi_build_cxx = env.get("CXX", "g++")
    if Path(_mpi_build_cxx).name in ("icpc", "icpx") and which("g++"):
        env["CXX"] = which("g++")

    # Use bare gfortran (not mpifort) as FC for the MPI build — avoids the
    # bootstrap problem of needing mpifort to build mpifort.  The result is
    # libmpi_mpifh.a which HDF5 Fortran configure needs.
    env.pop("FCFLAGS", None)
    env.pop("F90FLAGS",None)
    env.pop("LIBS",    None)
    env.pop("RPATH",   None)

    # Strip any system OpenMPI include dirs from CPATH.  When the openmpi
    # module is loaded, CPATH=/usr/local/packages/openmpi/.../include which
    # exposes hwloc.h to OpenMPI's configure.  That causes it to link against
    # the system hwloc (unrenamed symbols) instead of its bundled hwloc201
    # (renamed opal_hwloc_* symbols), producing multiply-defined hwloc symbols
    # when Cactus later links both libmpi.a and libhwloc.a.
    _cpath = env.get("CPATH", "")
    if _cpath:
        _clean = [d for d in _cpath.split(":") if d and "openmpi" not in d.lower()]
        if _clean:
            env["CPATH"] = ":".join(_clean)
        else:
            env.pop("CPATH", None)
    _gfc_for_mpi = (opts.get("F90") or opts.get("FC") or which("gfortran") or "")
    if _gfc_for_mpi and "mpifort" not in os.path.basename(_gfc_for_mpi):
        # Switch Intel Fortran to gfortran for the same reason as CC above.
        if Path(_gfc_for_mpi).name in ("ifort", "ifx") and which("gfortran"):
            _gfc_for_mpi = which("gfortran")
        env["FC"] = _gfc_for_mpi
    else:
        _gfc_for_mpi = which("gfortran") or ""
        if _gfc_for_mpi:
            env["FC"] = _gfc_for_mpi
        else:
            env.pop("FC", None)

    configure_args = [
        "./configure",
        f"--prefix={install_dir}",
        "--enable-mpi-cxx",
        "--enable-mpi-fortran",
        "--with-zlib=no",
        "--enable-mpi1-compatibility",
        "--without-memory-manager",
        "--enable-shared=no",
        "--enable-static=yes",
        # Omit --with-hwloc: OpenMPI 4.0.6 requires a shared libhwloc.so for
        # its configure AC_SEARCH_LIBS test; our static-only hwloc build has no
        # .so so --with-hwloc=<path> fails ("external hwloc cannot be built").
        # The resulting duplicate symbol (hwloc_linux_component defined in both
        # libhwloc.a and libopen-pal.a) is suppressed at Cactus link time by
        # -Wl,--allow-multiple-definition added in generate_cfg.
    ]
    if pmi_prefix:
        configure_args.append(f"--with-pmi={pmi_prefix}")
        print(f"  MPI: enabling PMI support (--with-pmi={pmi_prefix})", flush=True)

    try:
        print("  MPI: configuring …")
        subprocess.run(configure_args, cwd=src_dir, env=env, check=True,
                       stdout=log, stderr=subprocess.STDOUT)
        print("  MPI: building …")
        subprocess.run(["make", f"-j{jobs}"], cwd=src_dir, env=env, check=True,
                       stdout=log, stderr=subprocess.STDOUT)
        print("  MPI: installing …")
        subprocess.run(["make", f"-j{jobs}", "install"], cwd=src_dir, env=env, check=True,
                       stdout=log, stderr=subprocess.STDOUT)
    except subprocess.CalledProcessError:
        log.flush()
        _log_tail(log_path)
        raise
    finally:
        log.close()
    _write_build_cfg(install_dir, "mpi", env, configure_args)
    print(f"  MPI: installed to {install_dir}")
    return install_dir


def _mpi_from_install(install_dir: Path, opts: dict) -> MPI:
    """Populate an MPI object from an externals install."""
    m      = MPI()
    m.found   = True
    m.kind    = "openmpi"
    m.dir     = str(install_dir)
    m.bin_dir = str(install_dir / "bin")
    m.inc_dirs = str(install_dir / "include")
    m.lib_dirs = str(install_dir / "lib")

    # Use mpicc --showme:link for the base lib list, then supplement with
    # mpicxx --showme:link to pick up libmpi_cxx.  The C wrapper never emits
    # -lmpi_cxx; the C++ wrapper does.  Without it, any thorn that includes
    # <mpi.h> via a C++ header and uses MPI:: types gets unresolved references
    # to MPI::Comm::Comm() etc. at link time.
    mpicc = install_dir / "bin" / "mpicc"
    rc, lshow, _ = run_cmd(str(mpicc), "--showme:link")
    if rc == 0 and lshow.strip():
        libs = _parse_flags(lshow, "-l")
        mpicxx_bin = install_dir / "bin" / "mpicxx"
        rc2, lshow_cxx, _ = run_cmd(str(mpicxx_bin), "--showme:link")
        if rc2 == 0 and lshow_cxx.strip():
            extra = [l for l in _parse_flags(lshow_cxx, "-l") if l not in libs]
            libs = extra + libs
        if "mpi_cxx" not in libs:
            try:
                libs.insert(libs.index("mpi"), "mpi_cxx")
            except ValueError:
                libs = ["mpi_cxx"] + libs
        m.libs = " ".join(libs)
    else:
        # Fallback: hard-coded OpenMPI 4.x lib names.
        fc = opts.get("F90", "")
        have_fortran = bool(fc) and fc.strip().lower() not in ("none", "no_build", "")
        fortran_libs = "mpi_usempif08 mpi_usempi_ignore_tkr mpi_mpifh " if have_fortran else ""
        import platform
        linux_libs = " pthread rt util" if platform.system() == "Linux" else ""
        m.libs = f"{fortran_libs}mpi_cxx mpi open-rte open-pal{linux_libs}"

    # Populate the underlying compiler paths so _compilers_from_mpi can switch
    # to the right compiler suite (e.g. GCC 11 instead of system GCC 8).
    rc_c, show_c, _ = run_cmd(str(mpicc), "--showme:compile")
    if rc_c == 0 and show_c.strip():
        m.cc = _first_real_compiler(show_c)
    _cc_from_q, m.cxx, m.f90 = _query_mpi_compilers(bin_dir=str(install_dir / "bin"))
    if not m.cc and _cc_from_q:
        m.cc = _cc_from_q

    return m


_MPI_TEST_SRC = r"""
#include <mpi.h>
#include <stdio.h>
#include <string.h>
#include <unistd.h>

int main(int argc, char **argv) {
    MPI_Init(&argc, &argv);
    int rank, size;
    MPI_Comm_rank(MPI_COMM_WORLD, &rank);
    MPI_Comm_size(MPI_COMM_WORLD, &size);

    char host[256] = {0};
    gethostname(host, sizeof(host) - 1);
    printf("MPI_RANK %d/%d on %s\n", rank, size, host);
    fflush(stdout);

    if (size >= 2) {
        if (rank == 0) {
            int msg = 54321;
            MPI_Send(&msg, 1, MPI_INT, 1, 0, MPI_COMM_WORLD);
        } else if (rank == 1) {
            int msg = 0;
            MPI_Recv(&msg, 1, MPI_INT, 0, 0, MPI_COMM_WORLD, MPI_STATUS_IGNORE);
            if (msg != 54321) {
                fprintf(stderr, "rank 1: expected 54321 got %d\n", msg);
                MPI_Abort(MPI_COMM_WORLD, 1);
            }
        }
    }

    MPI_Barrier(MPI_COMM_WORLD);
    if (rank == 0) {
        printf("MPI_TEST_PASSED ranks=%d\n", size);
        fflush(stdout);
    }
    MPI_Finalize();
    return 0;
}
"""

_HDF5_C_TEST_SRC = r"""
#include <mpi.h>
#include <hdf5.h>
#include <hdf5_hl.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

int main(int argc, char **argv) {
    MPI_Init(&argc, &argv);
    int rank, size;
    MPI_Comm_rank(MPI_COMM_WORLD, &rank);
    MPI_Comm_size(MPI_COMM_WORLD, &size);

    /* --- Test 1: parallel HDF5 file via MPI-IO --- */
    hid_t fapl = H5Pcreate(H5P_FILE_ACCESS);
    H5Pset_fapl_mpio(fapl, MPI_COMM_WORLD, MPI_INFO_NULL);
    hid_t file = H5Fcreate("hdf5_mpi_test.h5", H5F_ACC_TRUNC, H5P_DEFAULT, fapl);
    H5Pclose(fapl);
    if (file < 0) {
        fprintf(stderr, "rank %d: H5Fcreate failed\n", rank);
        MPI_Abort(MPI_COMM_WORLD, 1);
    }

    /* --- Test 2: collective dataset create, each rank writes its slice --- */
    hsize_t total[1] = {(hsize_t)size};
    hid_t fspace = H5Screate_simple(1, total, NULL);
    hid_t dset = H5Dcreate2(file, "/parallel_data", H5T_NATIVE_INT,
                              fspace, H5P_DEFAULT, H5P_DEFAULT, H5P_DEFAULT);
    H5Sclose(fspace);
    if (dset < 0) {
        fprintf(stderr, "rank %d: H5Dcreate2 failed\n", rank);
        H5Fclose(file); MPI_Abort(MPI_COMM_WORLD, 1);
    }

    hsize_t start[1] = {(hsize_t)rank};
    hsize_t count[1] = {1};
    hid_t mspace  = H5Screate_simple(1, count, NULL);
    hid_t fspace2 = H5Dget_space(dset);
    H5Sselect_hyperslab(fspace2, H5S_SELECT_SET, start, NULL, count, NULL);
    int val = rank * 100;
    H5Dwrite(dset, H5T_NATIVE_INT, mspace, fspace2, H5P_DEFAULT, &val);
    H5Sclose(mspace); H5Sclose(fspace2);
    H5Dclose(dset);
    H5Fclose(file);

    MPI_Barrier(MPI_COMM_WORLD);

    /* --- Test 3: read back and verify (rank 0 only) --- */
    if (rank == 0) {
        hid_t f2 = H5Fopen("hdf5_mpi_test.h5", H5F_ACC_RDONLY, H5P_DEFAULT);
        if (f2 < 0) {
            fprintf(stderr, "H5Fopen failed\n");
            MPI_Abort(MPI_COMM_WORLD, 1);
        }
        hid_t d2 = H5Dopen2(f2, "/parallel_data", H5P_DEFAULT);
        int *buf = (int *)malloc(size * sizeof(int));
        H5Dread(d2, H5T_NATIVE_INT, H5S_ALL, H5S_ALL, H5P_DEFAULT, buf);
        for (int i = 0; i < size; i++) {
            if (buf[i] != i * 100) {
                fprintf(stderr, "readback[%d]=%d expected %d\n", i, buf[i], i*100);
                free(buf); H5Dclose(d2); H5Fclose(f2);
                MPI_Abort(MPI_COMM_WORLD, 1);
            }
        }
        free(buf); H5Dclose(d2); H5Fclose(f2);

        /* --- Test 4: HL API --- */
        hid_t hl_file = H5Fcreate("hdf5_hl_test.h5", H5F_ACC_TRUNC,
                                   H5P_DEFAULT, H5P_DEFAULT);
        if (hl_file < 0) {
            fprintf(stderr, "H5Fcreate HL failed\n");
            MPI_Abort(MPI_COMM_WORLD, 1);
        }
        hsize_t dims[1] = {4};
        int hl_data[4] = {10, 20, 30, 40};
        herr_t e = H5LTmake_dataset_int(hl_file, "/hl_data", 1, dims, hl_data);
        if (e < 0) {
            fprintf(stderr, "H5LTmake_dataset_int failed\n");
            H5Fclose(hl_file); MPI_Abort(MPI_COMM_WORLD, 1);
        }
        int hl_rb[4] = {0};
        e = H5LTread_dataset_int(hl_file, "/hl_data", hl_rb);
        if (e < 0 || hl_rb[0] != 10 || hl_rb[3] != 40) {
            fprintf(stderr, "HL readback failed\n");
            H5Fclose(hl_file); MPI_Abort(MPI_COMM_WORLD, 1);
        }
        H5Fclose(hl_file);

        printf("HDF5_C_TEST_PASSED ranks=%d\n", size);
        fflush(stdout);
    }

    MPI_Finalize();
    return 0;
}
"""

_HDF5_F90_TEST_SRC = """\
PROGRAM hdf5_f90_test
  USE HDF5
  IMPLICIT NONE
  INTEGER(HID_T)   :: file_id, dset_id, dspace_id
  INTEGER(HSIZE_T) :: dims(1)
  INTEGER          :: hdferr, i
  INTEGER          :: wdata(4), rdata(4)
  CHARACTER(LEN=24), PARAMETER :: fname = "hdf5_fortran_test.h5"

  CALL h5open_f(hdferr)
  IF (hdferr /= 0) STOP 1

  CALL h5fcreate_f(TRIM(fname), H5F_ACC_TRUNC_F, file_id, hdferr)
  IF (hdferr /= 0) STOP 2

  dims(1) = 4
  CALL h5screate_simple_f(1, dims, dspace_id, hdferr)
  CALL h5dcreate_f(file_id, "/fdata", H5T_NATIVE_INTEGER, dspace_id, dset_id, hdferr)

  wdata = (/ 111, 222, 333, 444 /)
  CALL h5dwrite_f(dset_id, H5T_NATIVE_INTEGER, wdata, dims, hdferr)
  IF (hdferr /= 0) STOP 3

  CALL h5dclose_f(dset_id, hdferr)
  CALL h5sclose_f(dspace_id, hdferr)
  CALL h5fclose_f(file_id, hdferr)

  CALL h5fopen_f(TRIM(fname), H5F_ACC_RDONLY_F, file_id, hdferr)
  CALL h5dopen_f(file_id, "/fdata", dset_id, hdferr)
  dims(1) = 4
  CALL h5dread_f(dset_id, H5T_NATIVE_INTEGER, rdata, dims, hdferr)
  DO i = 1, 4
    IF (rdata(i) /= wdata(i)) THEN
      WRITE(*,*) 'MISMATCH at i=', i, ' got ', rdata(i)
      STOP 4
    END IF
  END DO
  CALL h5dclose_f(dset_id, hdferr)
  CALL h5fclose_f(file_id, hdferr)
  CALL h5close_f(hdferr)

  WRITE(*,*) 'HDF5_FORTRAN_TEST_PASSED'
END PROGRAM hdf5_f90_test
"""


def _test_mpi(mpicc: str, cactus_root: Path, sched, n_ranks: int = 2,
              module_name: str = "") -> None:
    """Compile and run an MPI send/recv/barrier sanity test.  Raises on failure.

    module_name: if non-empty, a bash wrapper script does 'module purge &&
    module load <module_name>' before invoking srun, so that the compute
    nodes have the right runtime libraries (e.g. Intel libimf.so).
    """
    test_dir = (_externals_dir(cactus_root) / "build" / "mpi_test").resolve()
    test_dir.mkdir(parents=True, exist_ok=True)
    src = test_dir / "mpi_test.c"
    exe = test_dir / "mpi_test"

    src.write_text(_MPI_TEST_SRC)

    rc, out, err = run_cmd(mpicc, "-o", str(exe), str(src))
    if rc != 0:
        raise RuntimeError(f"MPI test compile failed:\n{out}\n{err}")
    print(f"  MPI test: compiled with {Path(mpicc).name}", flush=True)

    run_env = None  # used for non-module path; None means inherit caller's env

    if sched.kind == "slurm":
        # --nodes=1 keeps 2 tasks on a single node, satisfying the 'single'
        # partition's node constraint without requesting a multi-node allocation.
        # --overlap is required when srun is called inside an existing job.
        _overlap_flag = ["--overlap"] if os.environ.get("SLURM_JOB_ID") else []
        _srun_extra = os.environ.get("SRUN_FLAGS", "").split()
        srun_list = ["srun", *_overlap_flag, "--nodes=1", f"-n{n_ranks}", "--time=00:02:00",
                     *_srun_extra, str(exe)]
        if module_name:
            # Write a bash wrapper that re-initialises the module system,
            # purges the current environment, and loads only the target MPI
            # module.  This ensures compute nodes find the right runtime
            # libraries (Intel libimf.so, MPI libs, etc.) without any
            # stale compiler modules from the login shell.
            module_home = os.environ.get("MODULESHOME", "")
            if module_home and Path(f"{module_home}/init/bash").exists():
                init_line = f'source "{module_home}/init/bash"'
            elif Path("/etc/profile.d/modules.sh").exists():
                init_line = 'source /etc/profile.d/modules.sh'
            else:
                init_line = "true  # module init not found"
            srun_cmd = " ".join(srun_list)
            wrapper = test_dir / "mpi_test_run.sh"
            wrapper.write_text(
                "#!/bin/bash\n"
                f"{init_line}\n"
                "module purge\n"
                f"module load {module_name}\n"
                f"{srun_cmd}\n"
            )
            wrapper.chmod(0o755)
            launch = ["bash", str(wrapper)]
            runner = f"srun (module {module_name})"
        else:
            # Externals/local MPI — no module; inject lib dirs into LD_LIBRARY_PATH.
            run_env = os.environ.copy()
            for _flag in ("--showme:link", "-show"):
                _rc2, _show, _ = run_cmd(mpicc, _flag)
                if _rc2 == 0 and _show.strip():
                    for _ldir in _parse_flags(_show, "-L"):
                        _ldp = run_env.get("LD_LIBRARY_PATH", "")
                        if _ldir not in _ldp:
                            run_env["LD_LIBRARY_PATH"] = _ldir + (":" + _ldp if _ldp else "")
                    break
            launch = srun_list
            runner = "srun"
    else:
        mpirun = str(Path(mpicc).parent / "mpirun")
        if not os.access(mpirun, os.X_OK):
            mpirun = which("mpirun") or "mpirun"
        launch = [mpirun, "-n", str(n_ranks), str(exe)]
        runner = "mpirun"

    _launch_cmd = " ".join(launch)
    print(f"  MPI test: running {n_ranks} ranks via {runner} …", flush=True)
    print(f"  MPI test command: {_launch_cmd}", flush=True)
    with _ignore_slurm_signals():
        rc, out, err = run_cmd(*launch, env=run_env, timeout=180)
    combined = out + err

    if rc != 0:
        raise RuntimeError(f"MPI test failed (exit {rc}):\n  command: {_launch_cmd}\n{combined}")
    if "MPI_TEST_PASSED" not in combined:
        raise RuntimeError(f"MPI test did not print MPI_TEST_PASSED:\n{combined}")

    hosts = set()
    for line in combined.splitlines():
        if line.startswith("MPI_RANK"):
            parts = line.split()
            if len(parts) >= 4:
                hosts.add(parts[3])
    multi = len(hosts) > 1
    print(f"  MPI test: PASSED  ranks={n_ranks}  nodes={len(hosts)}"
          f"{'  (multi-node)' if multi else '  (single-node)'}", flush=True)


# ---------------------------------------------------------------------------
# HDF5 live-test helpers
# ---------------------------------------------------------------------------

def _hdf5_module_from_path(hdf5_dir: str) -> str:
    """Derive a module name from a filesystem HDF5 install path.

    Returns '' for Spack-hash paths (last component is a 7-char lowercase
    alphanumeric hash like '5zmcsdw') — those are internal Spack identifiers,
    not loadable module names.  Only paths whose last component looks like a
    human-readable qualifier (e.g. 'intel-2021.5.0-mvapich2-2.3.7') are
    converted to a module name by stripping the well-known package-root prefix.
    """
    last = Path(hdf5_dir).name
    if re.fullmatch(r"[a-z0-9]{7}", last):
        return ""   # Spack hash — not a real module name
    for pkg_root in ("/usr/local/packages/", "/opt/", "/apps/", "/sw/"):
        if hdf5_dir.startswith(pkg_root):
            return hdf5_dir[len(pkg_root):]
    return ""


def _find_hdf5_candidates(mpi_bin_dir: str = "") -> List[Tuple[str, str, str, str]]:
    """Return a list of (h5pcc_path, inc_dirs, lib_dirs, module_name) for parallel HDF5."""
    import glob as _glob_hdf5
    seen: set = set()
    results: List[Tuple[str, str, str, str]] = []

    def _probe(h5pcc: str) -> None:
        if not h5pcc or not os.access(h5pcc, os.X_OK):
            return
        rp = str(Path(h5pcc).resolve())
        lp = rp.lower()
        if rp in seen or "conda" in lp or "anaconda" in lp:
            return
        seen.add(rp)
        hdf5_dir = str(Path(h5pcc).parent.parent)
        # Skip serial HDF5 — Cactus needs parallel (H5Pset_fapl_mpio).
        if not _hdf5_is_parallel(hdf5_dir):
            return
        incs = ldirs = ""
        for flag in ("--show", "-show"):
            rc, show, _ = run_cmd(h5pcc, flag)
            if rc == 0 and show.strip():
                incs  = " ".join(_parse_flags(show, "-I"))
                ldirs = " ".join(_parse_flags(show, "-L"))
                break
        # Fallback: many Spack / module wrappers omit -I/-L from --show output
        # but the headers/libs are still in the standard prefix subdirectories.
        if not incs:
            inc_d = str(Path(hdf5_dir) / "include")
            if Path(inc_d).is_dir():
                incs = inc_d
        if not ldirs:
            lib_d = str(Path(hdf5_dir) / "lib")
            if Path(lib_d).is_dir():
                ldirs = lib_d
        if incs or ldirs:
            mod = _hdf5_module_from_path(hdf5_dir)
            results.append((h5pcc, incs, ldirs, mod))
        return

    # env-var hints
    for ev in ("CRAY_HDF5_PARALLEL_PREFIX_DIR", "CRAY_HDF5_DIR",
               "TACC_PHDF5_DIR", "TACC_HDF5_DIR",
               "HDF5_DIR", "HDF5_HOME", "HDF5_ROOT"):
        d = os.environ.get(ev, "")
        if d:
            _probe(str(Path(d) / "bin" / "h5pcc"))
            break

    # PATH
    _probe(which("h5pcc") or "")

    # Filesystem globs
    for pat in [
        "/usr/local/packages/hdf5/*/*/bin/h5pcc",
        "/usr/local/packages/phdf5/*/*/bin/h5pcc",
        "/usr/local/packages/hdf5/*/bin/h5pcc",
        "/usr/local/packages/phdf5/*/bin/h5pcc",
        "/opt/hdf5/*/bin/h5pcc",
        "/apps/hdf5/*/bin/h5pcc",
        "/sw/hdf5/*/bin/h5pcc",
    ]:
        for hit in sorted(_glob_hdf5.glob(pat)):
            _probe(hit)

    return results


def _test_hdf5(inc_dirs: str, lib_dirs: str,
               mpicc: str, mpifort: str,
               cactus_root: Path, sched,
               mpi_module: str = "", hdf5_module: str = "",
               h5pcc: str = "", h5pfc: str = "") -> None:
    """Compile and run HDF5+MPI sanity tests (C parallel + HL + Fortran).  Raises on failure.

    h5pcc / h5pfc: when provided, use the HDF5 compiler wrappers directly for
    compilation — they already embed the correct -I/-L flags.  Fall back to
    mpicc + explicit inc/lib flags (used for externals builds that don't yet
    have a wrapper).
    """
    test_dir = (_externals_dir(cactus_root) / "build" / "hdf5_test").resolve()
    test_dir.mkdir(parents=True, exist_ok=True)

    # Compile C test
    src_c = test_dir / "hdf5_c_test.c"
    exe_c = test_dir / "hdf5_c_test"
    src_c.write_text(_HDF5_C_TEST_SRC)
    if h5pcc and os.access(h5pcc, os.X_OK):
        # h5pcc already knows -I/-L for this HDF5 install — use it directly.
        rc, out, err = run_cmd(h5pcc, "-o", str(exe_c), str(src_c),
                               "-lhdf5_hl", timeout=60)
    else:
        inc_flags = [f"-I{d}" for d in inc_dirs.split() if d]
        lib_flags = [f"-L{d}" for d in lib_dirs.split() if d]
        rc, out, err = run_cmd(mpicc, "-o", str(exe_c), str(src_c),
                               *inc_flags, *lib_flags,
                               "-lhdf5_hl", "-lhdf5", "-lz", timeout=60)
    if rc != 0:
        raise RuntimeError(f"HDF5 C test compile failed:\n{out}\n{err}")
    print("  HDF5 test: compiled C test", flush=True)

    # Compile Fortran test (optional — system may lack Fortran bindings)
    _h5pfc_ok = bool(h5pfc and os.access(h5pfc, os.X_OK))
    has_fortran = _h5pfc_ok or bool(mpifort and os.access(mpifort, os.X_OK))
    src_f90 = test_dir / "hdf5_f90_test.f90"
    exe_f90 = test_dir / "hdf5_f90_test"
    if has_fortran:
        src_f90.write_text(_HDF5_F90_TEST_SRC)
        if _h5pfc_ok:
            rc2, out2, err2 = run_cmd(h5pfc, "-o", str(exe_f90), str(src_f90),
                                      "-lhdf5hl_fortran", "-lhdf5_fortran", timeout=60)
        else:
            inc_flags = [f"-I{d}" for d in inc_dirs.split() if d]
            lib_flags = [f"-L{d}" for d in lib_dirs.split() if d]
            rc2, out2, err2 = run_cmd(mpifort, "-o", str(exe_f90), str(src_f90),
                                      *inc_flags, *lib_flags,
                                      "-lhdf5hl_fortran", "-lhdf5_fortran", "-lhdf5", "-lz",
                                      timeout=60)
        if rc2 != 0:
            print(f"  HDF5 test: Fortran compile failed (no Fortran bindings?) — continuing",
                  flush=True)
            has_fortran = False
        else:
            print("  HDF5 test: compiled Fortran test", flush=True)

    # Build module init snippet (reused in wrapper)
    module_home = os.environ.get("MODULESHOME", "")
    if module_home and Path(f"{module_home}/init/bash").exists():
        init_line = f'source "{module_home}/init/bash"'
    elif Path("/etc/profile.d/modules.sh").exists():
        init_line = 'source /etc/profile.d/modules.sh'
    else:
        init_line = "true  # module init not found"

    # Write wrapper script
    wrapper = test_dir / "hdf5_test_run.sh"
    lines = ["#!/bin/bash", init_line, "module purge"]
    if mpi_module:
        lines.append(f"module load {mpi_module}")
    if hdf5_module:
        lines.append(f"module load {hdf5_module}")
    elif lib_dirs:
        # No valid module name (e.g. Spack-hash install); expose HDF5 libs via
        # LD_LIBRARY_PATH so the compute-node dynamic linker can find them.
        for _ldir in lib_dirs.split():
            if _ldir:
                lines.append(f'export LD_LIBRARY_PATH="{_ldir}:${{LD_LIBRARY_PATH}}"')
    lines.append(f"cd {test_dir}")

    _use_srun = bool((sched and sched.kind == "slurm") or which("srun"))
    _overlap  = "--overlap " if os.environ.get("SLURM_JOB_ID") else ""
    if _use_srun:
        lines.append(f"srun {_overlap}-n2 --time=00:02:00 {exe_c}")
        if has_fortran:
            lines.append(f"srun {_overlap}-n1 --time=00:02:00 {exe_f90}")
        runner = "srun"
    else:
        mpirun = str(Path(mpicc).parent / "mpirun")
        if not os.access(mpirun, os.X_OK):
            mpirun = which("mpirun") or "mpirun"
        lines.append(f"{mpirun} -n 2 {exe_c}")
        if has_fortran:
            lines.append(str(exe_f90))
        runner = "mpirun"

    wrapper.write_text("\n".join(lines) + "\n")
    wrapper.chmod(0o755)

    mods_desc = " ".join(filter(None, [mpi_module, hdf5_module])) or "none"
    print(f"  HDF5 test: running via {runner} (modules: {mods_desc}) …", flush=True)
    with _ignore_slurm_signals():
        rc, out, err = run_cmd("bash", str(wrapper), timeout=300)
    combined = out + err

    if rc != 0:
        raise RuntimeError(f"HDF5 test failed (exit {rc}):\n{combined}")
    if "HDF5_C_TEST_PASSED" not in combined:
        raise RuntimeError(f"HDF5 C test did not print HDF5_C_TEST_PASSED:\n{combined}")
    if has_fortran and "HDF5_FORTRAN_TEST_PASSED" not in combined:
        print(f"  HDF5 test: WARNING — Fortran test did not pass:\n{combined}", flush=True)
    print("  HDF5 test: PASSED", flush=True)


def detect_mpi(args, state: dict, cactus_root: Path, sched=None) -> MPI:
    # --without-mpi or a previous --without-mpi run (state) suppresses externals
    # build but must NOT suppress system-MPI detection: Intel MPI (and any other
    # module-loaded MPI) should still be picked up from PATH/env-vars so its
    # include/lib paths land in the OptionList.
    force_no_externals = (getattr(args, "without_mpi", False) or
                          state.get("with_mpi") is False)

    # --mpi-dir: user-supplied prefix → probe it directly, no further scanning.
    mpi_dir_hint = getattr(args, "mpi_dir", None)
    if mpi_dir_hint:
        _mpicc_hint = str(Path(mpi_dir_hint).resolve() / "bin" / "mpicc")
        if os.access(_mpicc_hint, os.X_OK):
            m = _extract_mpi_from_mpicc(_mpicc_hint)
            if m:
                return m
        print(f"  WARNING: --mpi-dir {mpi_dir_hint}: mpicc not found/runnable; "
              f"falling back to auto-detection")

    if not force_no_externals and not getattr(args, "with_mpi", False):
        # Re-use a pre-built externals MPI only when it passes the srun test.
        ext = (_externals_dir(cactus_root) / "install" / "mpi").resolve()
        _ext_mpicc = str(ext / "bin" / "mpicc")
        if os.access(_ext_mpicc, os.X_OK):
            # Fortran bindings are required for HDF5 Fortran configure.
            # If libmpi_mpifh.a is absent the mpifort wrapper links with -lmpi_mpifh
            # but the library doesn't exist, breaking every Fortran configure test.
            if not (ext / "lib" / "libmpi_mpifh.a").exists():
                print("  MPI: externals build missing Fortran bindings "
                      "(libmpi_mpifh.a) — rebuilding …", flush=True)
                import shutil as _ext_rmsh_f
                _ext_rmsh_f.rmtree(str(ext), ignore_errors=True)
            elif _has_intel_symbols(ext / "lib"):
                print("  MPI: externals build has Intel symbols — rebuilding with "
                      "current toolchain …", flush=True)
                import shutil as _ext_rmsh_i
                _ext_rmsh_i.rmtree(str(ext), ignore_errors=True)
            elif not getattr(args, "skip_mpi_test", False) and sched and not _no_build:
                try:
                    _test_mpi(_ext_mpicc, cactus_root, sched)
                    print(f"  MPI: externals build at {ext} passes srun test",
                          flush=True)
                except Exception as _ete:
                    # srun failure means the scheduler or environment isn't ready,
                    # NOT that the MPI build is wrong.  Keep the install so we don't
                    # rebuild from scratch on the next run, but stop here so the user
                    # can diagnose and fix the srun issue.
                    # Use --skip-mpi-test to bypass the test once it's resolved.
                    raise SystemExit(
                        f"\n  MPI srun test failed: {_ete}\n"
                        f"  The MPI install at {ext} has been kept.\n"
                        f"  Fix the srun issue and rerun, or pass --skip-mpi-test\n"
                        f"  to bypass the test."
                    ) from None
                opts = read_externals_options(cactus_root)
                return _mpi_from_install(ext, opts)
            else:
                opts = read_externals_options(cactus_root)
                return _mpi_from_install(ext, opts)

    # Try system MPI (tests each candidate with srun on Slurm).
    if not getattr(args, "with_mpi", False):
        m = _detect_mpi_system(sched=sched, cactus_root=cactus_root)
        if m.found:
            return m

    if force_no_externals:
        return MPI()

    # No system MPI passed — build external OpenMPI.
    # On Slurm, build with --with-pmi so srun can launch the processes.
    opts = read_externals_options(cactus_root)
    jobs = getattr(args, "jobs", 1) or 1
    pmi_prefix = (_find_slurm_pmi()
                  if sched and sched.kind == "slurm" else "")
    install_dir = build_external_mpi(cactus_root, opts, jobs=jobs,
                                     pmi_prefix=pmi_prefix,
                                     clean=getattr(args, "mpi_clean", False))
    if not getattr(args, "skip_mpi_test", False) and sched:
        try:
            _test_mpi(str(install_dir / "bin" / "mpicc"), cactus_root, sched)
        except Exception as _post_mpi_te:
            raise SystemExit(
                f"\n  MPI srun test failed after build: {_post_mpi_te}\n"
                f"  The MPI install at {install_dir} has been kept.\n"
                f"  Fix the srun issue and rerun, or pass --skip-mpi-test\n"
                f"  to bypass the test."
            ) from None
    return _mpi_from_install(install_dir, opts)

# ---------------------------------------------------------------------------
# GPU / CUDA
# ---------------------------------------------------------------------------

class GPU:
    found        = False
    nvcc_path    = "nvcc"
    sm_arch      = ""
    gpu_name     = ""
    cuda_version = ""

# Environment variables that may hold the CUDA installation root.
_CUDA_SEARCH_VARS = (
    "CUDA_HOME", "CUDA_PATH", "CUDA_DIR", "CUDA_ROOT",
    "NVHPC_CUDA_HOME", "CRAY_CUDATOOLKIT_DIR",
)

def _find_nvcc() -> Optional[str]:
    """Return path to nvcc, checking PATH then common CUDA env vars."""
    p = which("nvcc")
    if p:
        return p
    for var in _CUDA_SEARCH_VARS:
        d = os.environ.get(var, "")
        if d:
            c = Path(d) / "bin" / "nvcc"
            if c.is_file():
                return str(c)
    return None

def _detect_amd_arch() -> Optional[str]:
    """Return AMD GPU architecture (e.g. 'gfx90a') via rocminfo, or None."""
    for cmd in (["rocminfo"], ["rocm_agent_enumerator"]):
        rc, out, _ = run_cmd(*cmd, timeout=15)
        if rc == 0 and out:
            m = re.search(r'\bName:\s+(gfx\w+)', out)
            if m:
                return m.group(1)
            for line in out.splitlines():
                line = line.strip()
                if re.fullmatch(r"gfx\w+", line):
                    return line
    for var in ("ROCM_ARCH", "AMD_ARCH", "HIP_ARCH"):
        v = os.environ.get(var, "")
        if re.fullmatch(r"gfx\w+", v.strip()):
            return v.strip()
    return None


def _sm_to_cuda_arches(sm_arch: Optional[str]) -> str:
    """Convert 'sm_80' → '80', 'sm_90a' → '90a'.  Returns 'OFF' if empty."""
    if not sm_arch:
        return "OFF"
    cleaned = re.sub(r"^sm_?", "", sm_arch.strip(), flags=re.IGNORECASE)
    return cleaned if cleaned else "OFF"


def _detect_sm_arch(gpu_name: str = "") -> str:
    """Detect GPU SM architecture via multiple methods, best-effort."""
    import platform

    # Grace Hopper (GH200) needs sm_90a for full Hopper feature support.
    if re.search(r"GH\d{3}|Grace.?Hopper", gpu_name, re.IGNORECASE):
        return "sm_90a"

    # Method 1: nvidia-smi compute_cap query (fails on login nodes without GPU).
    smi = which("nvidia-smi")
    if smi:
        rc, out, _ = run_cmd(smi, "--query-gpu=compute_cap", "--format=csv,noheader")
        if rc == 0 and out.strip():
            cap = out.strip().splitlines()[0].strip().replace(".", "")
            if re.fullmatch(r"\d{2,3}", cap):
                return f"sm_{cap}"
        # Verbose fallback — works on some systems where the structured query fails.
        rc2, out2, _ = run_cmd(smi, "-a")
        m = re.search(r"CUDA Compute Capability\s*:\s*(\d+)\.\s*(\d+)", out2)
        if m:
            return f"sm_{m.group(1)}{m.group(2)}"

    # Method 2: env vars set by site modules or user.
    for var in ("GPU_ARCH", "CUDA_ARCH", "CRAY_ACCEL_TARGET"):
        v = os.environ.get(var, "")
        if not v:
            continue
        m = re.search(r"sm_?(\d{2,3}a?)", v, re.IGNORECASE)
        if m:
            return f"sm_{m.group(1)}"
        m = re.search(r"\b(\d{2,3})\b", v)
        if m and 30 <= int(m.group(1)) <= 120:
            return f"sm_{m.group(1)}"

    # Method 3: platform heuristic.
    # aarch64 with CUDA almost always means Grace Hopper (GH200) in HPC contexts.
    if platform.machine() == "aarch64":
        return "sm_90"

    return ""

def detect_gpu() -> GPU:
    g = GPU()
    nvcc = _find_nvcc()
    if not nvcc:
        return g
    g.found     = True
    g.nvcc_path = nvcc

    rc, out, _ = run_cmd(nvcc, "--version")
    m = re.search(r"release (\S+),", out)
    if m:
        g.cuda_version = m.group(1)

    # Get GPU name first — it informs the arch decision (e.g. Grace Hopper).
    smi = which("nvidia-smi")
    if smi:
        rc2, out2, _ = run_cmd(smi, "--query-gpu=name", "--format=csv,noheader")
        if rc2 == 0 and out2.strip():
            g.gpu_name = out2.strip().splitlines()[0].strip()

    g.sm_arch = _detect_sm_arch(g.gpu_name)
    return g

# ---------------------------------------------------------------------------
# Libraries (each returns (found: bool, cfg_lines: str))
# ---------------------------------------------------------------------------

def _lib_lines(prefix: str, d: str, inc="", lib_dirs="", libs="") -> str:
    lines = [f"{prefix}_DIR = {d}"]
    if inc:
        lines.append(f"{prefix}_INC_DIRS = {inc}")
    if lib_dirs:
        lines.append(f"{prefix}_LIB_DIRS = {lib_dirs}")
    if libs:
        lines.append(f"{prefix}_LIBS = {libs}")
    return "\n".join(lines)

def detect_hdf5(args, state: dict, cactus_root: Path,
                mpi_found: bool = False, mpi=None, sched=None) -> Tuple[bool, str, str]:
    """Returns (found, cfg_lines, hdf5_module_name)."""
    if getattr(args, "without_hdf5", False) or state.get("with_hdf5") is False:
        return False, "HDF5_DIR = BUILD", ""

    default_libs = "hdf5hl_fortran hdf5_fortran hdf5_hl hdf5"
    _run_test = (sched is not None and mpi is not None and getattr(mpi, "found", False)
                 and not _no_build)

    def _hdf5_actual_libs(install_dir: Path) -> str:
        """Return only the HDF5 libs that are actually present in the install."""
        lib_dir = install_dir / "lib"
        present = [
            lib for lib in ("hdf5hl_fortran", "hdf5_fortran", "hdf5_hl", "hdf5")
            if ((lib_dir / f"lib{lib}.a").exists()
                or (lib_dir / f"lib{lib}.so").exists())
        ]
        return " ".join(present) if present else "hdf5_hl hdf5"

    def _mpicc_path() -> str:
        if mpi and mpi.bin_dir:
            p = str(Path(mpi.bin_dir) / "mpicc")
            if os.access(p, os.X_OK):
                return p
        return which("mpicc") or "mpicc"

    def _mpifort_path() -> str:
        if mpi and mpi.bin_dir:
            p = str(Path(mpi.bin_dir) / "mpifort")
            if os.access(p, os.X_OK):
                return p
        return which("mpifort") or ""

    def _cfg(hdf5_dir: str, incs: str, ldirs: str, libs: str = "") -> str:
        l = libs if libs else default_libs
        return _lib_lines("HDF5", hdf5_dir, incs, ldirs, l)

    def _try_test(h5pcc_path: str, hdf5_dir: str, incs: str, ldirs: str,
                  hdf5_module: str) -> bool:
        """Run the live test; return True if passed, False if skipped or failed."""
        if not _run_test:
            return True  # no sched → accept without testing
        h5pfc_path = str(Path(h5pcc_path).parent / "h5pfc")
        h5pfc_path = h5pfc_path if os.access(h5pfc_path, os.X_OK) else ""
        try:
            _test_hdf5(incs, ldirs, _mpicc_path(), _mpifort_path(),
                       cactus_root, sched,
                       mpi_module=getattr(mpi, "module_name", "") or "",
                       hdf5_module=hdf5_module,
                       h5pcc=h5pcc_path, h5pfc=h5pfc_path)
            return True
        except Exception as _te:
            print(f"  HDF5: {hdf5_dir} failed test ({_te}) — trying next candidate",
                  flush=True)
            return False

    if not getattr(args, "with_hdf5", False):
        # --- candidates from _find_hdf5_candidates (h5pcc-based) ---
        mpi_bin_dir = getattr(mpi, "bin_dir", "") if mpi else ""
        for h5pcc_cand, incs, ldirs, h5mod in _find_hdf5_candidates(mpi_bin_dir):
            hdf5_dir = str(Path(h5pcc_cand).parent.parent)
            print(f"  HDF5: probing {h5pcc_cand} …", flush=True)
            if _try_test(h5pcc_cand, hdf5_dir, incs, ldirs, h5mod):
                print(f"  HDF5: selected {hdf5_dir}", flush=True)
                return True, _cfg(hdf5_dir, incs, ldirs, default_libs), h5mod

        # --- non-HPC fallbacks (pkg-config, /usr/include) — skip live test ---
        pc = pkg_prefix("hdf5")
        if pc:
            return True, _lib_lines("HDF5", pc, f"{pc}/include", f"{pc}/lib", default_libs), ""

        if Path("/usr/include/hdf5.h").exists():
            return True, _lib_lines(
                "HDF5", "/usr", "/usr/include", "/usr/lib64 /usr/lib", default_libs
            ), ""

        # Filesystem scan — covers module-tree installs where env vars weren't set
        # but h5pcc wasn't found via glob.
        fs = _find_hdf5_on_filesystem()
        if fs:
            hdf5_mod = _hdf5_module_from_path(fs)
            inc_fs = f"{fs}/include"
            lib_fs = f"{fs}/lib"
            _fs_h5pcc = str(Path(fs) / "bin" / "h5pcc")
            _fs_h5pcc = _fs_h5pcc if os.access(_fs_h5pcc, os.X_OK) else ""
            if _try_test(_fs_h5pcc, fs, inc_fs, lib_fs, hdf5_mod):
                return True, _lib_lines("HDF5", fs, inc_fs, lib_fs, default_libs), hdf5_mod

    # No system HDF5 found (or --with-hdf5 forces externals): pre-build it.
    opts = read_externals_options(cactus_root)
    install_dir = build_external_hdf5(
        cactus_root, opts, mpi_found=mpi_found,
        jobs=getattr(args, "jobs", 1) or 1,
    )
    actual_libs = _hdf5_actual_libs(install_dir)
    return True, (
        _lib_lines(
            "HDF5", str(install_dir),
            f"{install_dir}/include",
            f"{install_dir}/lib",
            actual_libs,
        ) + f"\nHDF5_INSTALL_DIR = {install_dir}"
    ), ""

def _find_hdf5_on_filesystem() -> Optional[str]:
    """Scan filesystem paths for HDF5, including module-installed prefixes."""
    roots = [
        "/usr", "/usr/local", "/opt/local", "/opt/homebrew",
        "/usr/local/packages", "/usr/local/apps",
        "/packages", "/apps", "/software", "/opt",
    ]
    for mp in os.environ.get("MODULEPATH", "").split(":"):
        if mp:
            roots.append(str(Path(mp).parent))

    seen: set = set()
    for root in roots:
        for sub in ("", "/hdf5", "/HDF5", "/phdf5", "/PHDF5"):
            d = root + sub
            if d in seen or not Path(d).is_dir():
                continue
            seen.add(d)
            for incsub in ("include", "include/hdf5"):
                inc = Path(d) / incsub
                if not (inc / "hdf5.h").exists():
                    continue
                for libsub in ("lib64", "lib"):
                    lib = Path(d) / libsub
                    if (lib / "libhdf5.a").exists() or (lib / "libhdf5.so").exists():
                        return d
    return None


def _find_fftw3_on_filesystem() -> Optional[str]:
    """Scan filesystem paths for FFTW3, including module-installed prefixes."""
    roots = [
        "/usr", "/usr/local", "/opt/local", "/opt/homebrew",
        "/usr/local/packages", "/usr/local/apps",
        "/packages", "/apps", "/software", "/opt",
    ]
    # MODULEPATH entries often sit beside the actual install trees.
    for mp in os.environ.get("MODULEPATH", "").split(":"):
        if mp:
            roots.append(str(Path(mp).parent))

    seen: set = set()
    for root in roots:
        for sub in ("", "/fftw3", "/fftw", "/FFTW3", "/FFTW"):
            d = root + sub
            if d in seen or not Path(d).is_dir():
                continue
            seen.add(d)
            if not (Path(d) / "include" / "fftw3.h").exists():
                continue
            for libsub in ("lib64", "lib"):
                lib = Path(d) / libsub
                if (lib / "libfftw3.a").exists() or (lib / "libfftw3.so").exists():
                    return d
    return None


def build_external_fftw3(cactus_root: Path, opts: dict, jobs: int = 1) -> Path:
    install_dir = (_externals_dir(cactus_root) / "install" / "fftw3").resolve()
    if (install_dir / "lib" / "libfftw3.a").exists():
        print("  FFTW3: already built, skipping.")
        return install_dir
    if _no_build:
        _build_would_build.add("fftw3")
        return install_dir

    name    = "fftw-3.3.10"
    tarball = (cactus_root / "arrangements" / "ExternalLibraries"
               / "FFTW3" / "dist" / f"{name}.tar.gz")
    if not tarball.exists():
        raise FileNotFoundError(f"FFTW3 tarball not found: {tarball}")

    build_root = (_externals_dir(cactus_root) / "build" / "fftw3").resolve()
    build_root.mkdir(parents=True, exist_ok=True)
    install_dir.mkdir(parents=True, exist_ok=True)

    log_path, log = _open_build_log(cactus_root, "fftw3")
    print(f"  FFTW3: extracting {tarball.name} …  (log → {log_path.name})")
    with tarfile.open(tarball) as tf:
        _tar_extractall(tf, build_root)

    src_dir = build_root / name

    env = os.environ.copy()
    for key, env_key in [("CC", "CC"), ("CXX", "CXX"),
                          ("CFLAGS", "CFLAGS"), ("CXXFLAGS", "CXXFLAGS")]:
        if key in opts:
            env[env_key] = opts[key]
    env["LIBS"] = "-lm"
    env.pop("RPATH", None)

    configure_args = [
        "./configure",
        f"--prefix={install_dir}",
        f"--libdir={install_dir}/lib",
    ]

    try:
        print("  FFTW3: configuring …")
        subprocess.run(configure_args, cwd=src_dir, env=env, check=True,
                       stdout=log, stderr=subprocess.STDOUT)
        print("  FFTW3: building …")
        subprocess.run(["make", f"-j{jobs}"], cwd=src_dir, env=env, check=True,
                       stdout=log, stderr=subprocess.STDOUT)
        print("  FFTW3: installing …")
        subprocess.run(["make", f"-j{jobs}", "install"], cwd=src_dir, env=env, check=True,
                       stdout=log, stderr=subprocess.STDOUT)
    except subprocess.CalledProcessError:
        log.flush()
        _log_tail(log_path)
        raise
    finally:
        log.close()
    _write_build_cfg(install_dir, "fftw3", env, configure_args)
    print(f"  FFTW3: installed to {install_dir}")
    return install_dir


def detect_fftw3(args, state: dict, cactus_root: Path) -> Tuple[bool, str]:
    if getattr(args, "without_fftw3", False) or state.get("with_fftw3") is False:
        return False, "FFTW3_DIR = BUILD"

    if not getattr(args, "with_fftw3", False):
        # MKL provides a drop-in FFTW3 interface.
        mkl = os.environ.get("MKLROOT", "")
        if mkl and Path(mkl).exists():
            return True, (
                f"FFTW3_DIR     = {mkl}\n"
                f"FFTW3_INC_DIRS = {mkl}/include/fftw\n"
                f"FFTW3_LIB_DIRS = {mkl}/lib/intel64\n"
                "FFTW3_LIBS    = mkl_intel_lp64 mkl_sequential mkl_core"
            )

        # Env vars set by a loaded module or user.
        d = env_dir(
            "CRAY_FFTW_DIR", "FFTW_HOME", "FFTW3_HOME",
            "FFTW_DIR", "FFTW3_DIR", "FFTW_ROOT", "FFTW3_ROOT",
            "TACC_FFTW3_DIR",
        )
        if d:
            return True, _lib_lines("FFTW3", d, f"{d}/include", f"{d}/lib", "fftw3")

        # pkg-config.
        pc = pkg_prefix("fftw3")
        if pc:
            if pc not in _SYSTEM_DIRS:
                return True, _lib_lines("FFTW3", pc, f"{pc}/include", f"{pc}/lib", "fftw3")
            return True, "# FFTW3: found in system paths\nFFTW3_LIBS = fftw3"

        # Filesystem scan — covers both system installs and module-tree installs.
        d = _find_fftw3_on_filesystem()
        if d:
            return True, _lib_lines("FFTW3", d, f"{d}/include", f"{d}/lib", "fftw3")

        # Also check our own externals install from a prior run.
        ext = (_externals_dir(cactus_root) / "install" / "fftw3").resolve()
        if (ext / "lib" / "libfftw3.a").exists():
            return True, _lib_lines("FFTW3", str(ext),
                                    f"{ext}/include", f"{ext}/lib", "fftw3")

    # Not found on system (or --with-fftw3): pre-build from the bundled tarball.
    opts        = read_externals_options(cactus_root)
    install_dir = build_external_fftw3(
        cactus_root, opts, jobs=getattr(args, "jobs", 1) or 1
    )
    return True, (
        f"FFTW3_DIR         = {install_dir}\n"
        f"FFTW3_INSTALL_DIR = {install_dir}\n"
        f"FFTW3_INC_DIRS    = {install_dir}/include\n"
        f"FFTW3_LIB_DIRS    = {install_dir}/lib\n"
        f"FFTW3_LIBS        = fftw3"
    )

def detect_blas() -> Tuple[bool, str]:
    mkl = os.environ.get("MKLROOT", "")
    if mkl and Path(mkl).exists():
        mkl_libs = "mkl_intel_lp64 mkl_sequential mkl_core"
        return True, (
            f"BLAS_DIR = {mkl}/lib/intel64\n"
            f"BLAS_LIBS = {mkl_libs}\n"
            f"OPENBLAS_DIR = {mkl}\n"
            f"OPENBLAS_LIB_DIRS = {mkl}/lib/intel64\n"
            f"OPENBLAS_LIBS = {mkl_libs}"
        )

    d = env_dir(
        "OPENBLAS_HOME", "OPENBLAS_DIR", "OPENBLAS_ROOT", "EBROOTOPENBLAS",
        "BLAS_HOME", "BLAS_DIR",
    )
    if d:
        lib_dir = f"{d}/lib" if not d.endswith("lib") else d
        return True, (
            f"BLAS_DIR = {lib_dir}\n"
            "BLAS_LIBS = openblas\n"
            f"OPENBLAS_DIR = {lib_dir}\n"
            "OPENBLAS_LIBS = openblas"
        )

    for soname, libname in (("libopenblas.so", "openblas"), ("libblas.so", "blas")):
        for sysdir in ("/usr/lib64", "/usr/lib/x86_64-linux-gnu", "/usr/lib"):
            if Path(sysdir, soname).exists():
                return True, (
                    f"BLAS_DIR = {sysdir}\n"
                    f"BLAS_LIBS = {libname}\n"
                    f"OPENBLAS_DIR = {sysdir}\n"
                    f"OPENBLAS_LIBS = {libname}"
                )

    return False, (
        "BLAS_DIR = BUILD\n"
        "OPENBLAS_DIR = NO_BUILD"
    )


def build_external_lapack(cactus_root: Path, opts: dict, jobs: int = 1) -> Path:
    import shutil as _shutil
    install_dir = (_externals_dir(cactus_root) / "install" / "lapack").resolve()
    if (install_dir / "lib" / "liblapack.a").exists():
        print("  LAPACK: already built, skipping.")
        return install_dir
    if _no_build:
        _build_would_build.add("lapack")
        return install_dir

    name    = "lapack-3.12.0"
    thorn   = cactus_root / "arrangements" / "ExternalLibraries" / "LAPACK"
    tarball = thorn / "dist" / f"{name}.tgz"
    if not tarball.exists():
        raise FileNotFoundError(f"LAPACK tarball not found: {tarball}")

    fc = opts.get("F90", "gfortran")
    # ifort/ifx produce Intel-specific runtime calls that can't link with GCC.
    # Prefer gfortran for LAPACK so the static library is GCC-compatible.
    _fc_base = Path(fc).name if fc not in ("NO_BUILD", "BUILD", "") else ""
    if _fc_base in ("ifort", "ifx") and which("gfortran"):
        fc = which("gfortran")
        print(f"  LAPACK: switching FC from {_fc_base} to gfortran to avoid "
              f"Intel runtime dependencies")
    if fc in ("NO_BUILD", "BUILD", ""):
        raise RuntimeError("LAPACK requires a Fortran compiler but none was detected. "
                           "Install gfortran or set F90 in options.cfg in the externals dir.")

    build_root = (_externals_dir(cactus_root) / "build" / "lapack").resolve()
    src_dir_pre = build_root / name
    if src_dir_pre.exists():
        import shutil as _shutil2
        _shutil2.rmtree(str(src_dir_pre))
    build_root.mkdir(parents=True, exist_ok=True)
    (install_dir / "lib").mkdir(parents=True, exist_ok=True)

    log_path, log = _open_build_log(cactus_root, "lapack")
    print(f"  LAPACK: extracting {tarball.name} …  (log → {log_path.name})")
    with tarfile.open(tarball) as tf:
        _tar_extractall(tf, build_root)

    src_dir = build_root / name
    fflags  = opts.get("F90FLAGS", "-O2")
    (src_dir / "make.inc").write_text(
        f"FC           = {fc}\n"
        f"FFLAGS       = {fflags}\n"
        "FFLAGS_DRV   = $(FFLAGS)\n"
        "TIMER        = NONE\n"
        "BLASLIB      = $(TOPSRCDIR)/libblas.a\n"
        "LAPACKLIB    = $(TOPSRCDIR)/liblapack.a\n"
        # Pin AR/ARFLAGS/RANLIB so that loaded toolchain modules (e.g. Intel
        # xiar) cannot override them via environment variables and cause make
        # to attempt to execute liblapack.a when AR expands to empty string.
        "AR           = ar\n"
        "ARFLAGS      = cr\n"
        "RANLIB       = ranlib\n"
    )

    env = os.environ.copy()
    for _var in ("LIBS", "AR", "ARFLAGS", "RANLIB", "F77", "FC"):
        env.pop(_var, None)

    try:
        print(f"  LAPACK: building (FC={fc}) …")
        subprocess.run(["make", f"-j{jobs}", "lapacklib"], cwd=src_dir, env=env,
                       check=True, stdout=log, stderr=subprocess.STDOUT)
        print("  LAPACK: installing …")
        _shutil.copy2(str(src_dir / "liblapack.a"),
                      str(install_dir / "lib" / "liblapack.a"))
    except subprocess.CalledProcessError:
        log.flush()
        _log_tail(log_path)
        raise
    finally:
        log.close()
    _write_build_cfg(install_dir, "lapack", env)
    print(f"  LAPACK: installed to {install_dir}")
    return install_dir


def detect_lapack(args, state: dict, cactus_root: Path) -> Tuple[bool, str]:
    """Detect or pre-build LAPACK.  Returns (found, cfg_str).

    System/env detection runs first (MKL, OpenBLAS, explicit env vars).
    If nothing is found, pre-builds from the bundled tarball automatically
    (same as passing --with-lapack).  Pass --without-lapack to delegate to
    Cactus instead.
    """
    if getattr(args, "without_lapack", False) or state.get("with_lapack") is False:
        return False, "LAPACK_DIR = BUILD"

    if not getattr(args, "with_lapack", False):
        # MKL bundles LAPACK
        mkl = os.environ.get("MKLROOT", "")
        if mkl and Path(mkl).exists():
            mkl_libs = "mkl_intel_lp64 mkl_sequential mkl_core"
            return True, (
                f"LAPACK_DIR      = {mkl}/lib/intel64\n"
                f"LAPACK_LIB_DIRS = {mkl}/lib/intel64\n"
                f"LAPACK_LIBS     = {mkl_libs}"
            )

        # Explicit LAPACK env var
        d = env_dir("LAPACK_DIR", "LAPACK_HOME", "LAPACK_ROOT")
        if d:
            lib_dir = str(Path(d) / "lib") if (Path(d) / "lib").is_dir() else d
            return True, (
                f"LAPACK_DIR      = {lib_dir}\n"
                f"LAPACK_LIB_DIRS = {lib_dir}\n"
                f"LAPACK_LIBS     = lapack"
            )

        # OpenBLAS bundles LAPACK
        d2 = env_dir("OPENBLAS_HOME", "OPENBLAS_DIR", "OPENBLAS_ROOT", "EBROOTOPENBLAS",
                     "BLAS_HOME", "BLAS_DIR")
        if d2:
            lib_dir = f"{d2}/lib" if not d2.endswith("lib") else d2
            return True, (
                f"LAPACK_DIR      = {lib_dir}\n"
                f"LAPACK_LIB_DIRS = {lib_dir}\n"
                f"LAPACK_LIBS     = openblas"
            )

        # Pre-built externals
        ext = (_externals_dir(cactus_root) / "install" / "lapack").resolve()
        _lapack_a = ext / "lib" / "liblapack.a"
        if _lapack_a.exists():
            # If the library was built with Intel ifort it has Intel AVX runtime
            # symbols that won't resolve when linking with GCC.  Delete it so
            # build_external_lapack() below rebuilds with gfortran.
            _nm_rc, _nm_out, _ = run_cmd("nm", str(_lapack_a))
            if _nm_rc == 0 and ("__intel_avx_rep_memset" in _nm_out
                                or "_intel_fast_memcpy" in _nm_out):
                print("  LAPACK: existing library has Intel symbols — "
                      "rebuilding with gfortran …")
                import shutil as _lp_shutil
                _lp_shutil.rmtree(str(ext / "lib"), ignore_errors=True)
            else:
                return True, (
                    f"LAPACK_DIR         = {ext}\n"
                    f"LAPACK_INSTALL_DIR = {ext}\n"
                    f"LAPACK_LIB_DIRS    = {ext}/lib\n"
                    f"LAPACK_LIBS        = lapack"
                )

        # System search: standalone liblapack.a/so
        for sysdir in ("/usr/lib64", "/usr/lib/x86_64-linux-gnu", "/usr/lib",
                       "/usr/lib/aarch64-linux-gnu"):
            for libfile, libname in (("liblapack.a",    "lapack"),
                                     ("liblapack.so",   "lapack"),
                                     ("libopenblas.so", "openblas"),
                                     ("libopenblas.a",  "openblas")):
                if Path(sysdir, libfile).exists():
                    return True, (
                        f"LAPACK_DIR      = {sysdir}\n"
                        f"LAPACK_LIB_DIRS = {sysdir}\n"
                        f"LAPACK_LIBS     = {libname}"
                    )

    # --with-lapack or nothing found: pre-build from bundled tarball
    install_dir = build_external_lapack(
        cactus_root, read_externals_options(cactus_root),
        jobs=getattr(args, "jobs", 1) or 1,
    )
    return True, (
        f"LAPACK_DIR         = {install_dir}\n"
        f"LAPACK_INSTALL_DIR = {install_dir}\n"
        f"LAPACK_LIB_DIRS    = {install_dir}/lib\n"
        f"LAPACK_LIBS        = lapack"
    )


def build_external_hwloc(cactus_root: Path, opts: dict, jobs: int = 1) -> Path:
    import shutil as _shutil
    install_dir = (_externals_dir(cactus_root) / "install" / "hwloc").resolve()
    if (install_dir / "lib" / "libhwloc.a").exists():
        print("  hwloc: already built, skipping.")
        return install_dir
    if _no_build:
        _build_would_build.add("hwloc")
        return install_dir

    name    = "hwloc-2.0.4"
    thorn   = cactus_root / "repos" / "ExternalLibraries-hwloc"
    tarball = thorn / "dist" / f"{name}.tar.gz"
    if not tarball.exists():
        raise FileNotFoundError(f"hwloc tarball not found: {tarball}")

    build_root  = (_externals_dir(cactus_root) / "build" / "hwloc").resolve()
    src_dir_pre = build_root / name
    if src_dir_pre.exists():
        _shutil.rmtree(str(src_dir_pre))
    build_root.mkdir(parents=True, exist_ok=True)
    (install_dir / "lib").mkdir(parents=True, exist_ok=True)

    log_path, log = _open_build_log(cactus_root, "hwloc")
    print(f"  hwloc: extracting {tarball.name} …  (log → {log_path.name})")
    with tarfile.open(tarball) as tf:
        _tar_extractall(tf, build_root)

    src_dir = build_root / name
    env = os.environ.copy()
    for _var in ("LIBS", "AR", "ARFLAGS", "RANLIB"):
        env.pop(_var, None)

    try:
        print("  hwloc: configuring …")
        subprocess.run(
            ["./configure", f"--prefix={install_dir}",
             "--disable-cairo", "--disable-libxml2",
             "--disable-cuda", "--disable-nvml", "--disable-opencl",
             "--disable-pci",   # avoid libpciaccess dependency in static link
             "--with-x=no", "--disable-gl",
             "--enable-shared=no", "--enable-static=yes"],
            cwd=src_dir, env=env, check=True,
            stdout=log, stderr=subprocess.STDOUT,
        )
        print("  hwloc: building …")
        subprocess.run(["make", f"-j{jobs}"], cwd=src_dir, env=env,
                       check=True, stdout=log, stderr=subprocess.STDOUT)
        print("  hwloc: installing …")
        subprocess.run(["make", "install"], cwd=src_dir, env=env,
                       check=True, stdout=log, stderr=subprocess.STDOUT)
    except subprocess.CalledProcessError:
        log.flush()
        _log_tail(log_path)
        raise
    finally:
        log.close()
    _write_build_cfg(install_dir, "hwloc", env, configure_args)
    print(f"  hwloc: installed to {install_dir}")
    return install_dir


def _openmpi_embeds_hwloc(mpi: "MPI") -> bool:
    """Return True if this OpenMPI was built with hwloc statically embedded in libopen-pal."""
    # ompi_info is the cleanest probe: "hwloc:location:full:internal" means embedded.
    rc, out, _ = run_cmd("ompi_info", "--parseable", "--all")
    if rc == 0:
        for line in out.splitlines():
            if "hwloc" in line and "location" in line:
                val = line.rstrip().rsplit(":", 1)[-1].strip()
                return val in ("internal", "embedded", "")
    # Fallback: nm on libopen-pal — if it defines hwloc_linux_component, hwloc is embedded.
    for lib_dir in (mpi.lib_dirs or "").split():
        for libname in ("libopen-pal.a", "libopen-pal.so", "libopen-pal.so.0"):
            lib = Path(lib_dir) / libname
            if lib.exists():
                rc2, syms, _ = run_cmd("nm", "--defined-only", str(lib))
                return rc2 == 0 and "hwloc_linux_component" in syms
    return False


def _openmpi_external_hwloc_prefix(mpi: "MPI") -> Optional[str]:
    """Return the hwloc install prefix if system OpenMPI was built against external hwloc."""
    rc, out, _ = run_cmd("ompi_info", "--parseable", "--all")
    if rc == 0:
        for line in out.splitlines():
            # ompi_info --parseable format: mca:fw:comp:param:name:key:value
            # Only look at :value: lines where the param name has both "hwloc"
            # and "location" — avoids false positives from :help: lines whose
            # description text contains "location" as a substring of "allocations".
            if ":value:" not in line:
                continue
            parts = line.split(":")
            # param name is the 5th colon-separated field (index 4)
            param_name = parts[4] if len(parts) > 4 else ""
            if "hwloc" not in param_name or "location" not in param_name:
                continue
            val = line.split(":value:", 1)[-1].strip()
            if val and val not in ("internal", "embedded") and Path(val).is_dir():
                return val
    return None


def detect_hwloc(args, state: dict, cactus_root: Path,
                 mpi: Optional["MPI"] = None) -> Tuple[bool, str]:
    """Detect or pre-build hwloc.  Returns (found, cfg_str).

    Checks env vars, pkg-config, and pre-built externals first.  If nothing
    is found, pre-builds from the bundled tarball (same as --with-hwloc).
    Pass --without-hwloc to delegate to Cactus instead.
    """
    if getattr(args, "without_hwloc", False) or state.get("with_hwloc") is False:
        return False, "HWLOC_DIR = BUILD"

    if not getattr(args, "with_hwloc", False):
        # For system OpenMPI: if hwloc is statically embedded in libopen-pal,
        # linking a separate libhwloc.a would produce duplicate-symbol errors.
        # Detect this and either use the external hwloc the MPI was built against,
        # or skip hwloc entirely (the symbols are already inside libopen-pal.a).
        if mpi and mpi.found and mpi.kind == "openmpi" and not mpi.bin_dir:
            # mpi.bin_dir is only set for externals-built MPI; empty means system MPI.
            if _openmpi_embeds_hwloc(mpi):
                # hwloc is baked into libopen-pal.a — don't link a separate copy.
                return False, "HWLOC_DIR = NO_BUILD"
            ext_prefix = _openmpi_external_hwloc_prefix(mpi)
            if ext_prefix:
                return True, _lib_lines(
                    "HWLOC", ext_prefix,
                    f"{ext_prefix}/include", f"{ext_prefix}/lib", "hwloc"
                )

        d = env_dir("HWLOC_DIR", "HWLOC_HOME", "HWLOC_ROOT", "EBROOTHWLOC")
        if d:
            return True, _lib_lines("HWLOC", d, f"{d}/include", f"{d}/lib", "hwloc")

        pc = pkg_prefix("hwloc")
        if pc:
            return True, _lib_lines("HWLOC", pc, f"{pc}/include", f"{pc}/lib", "hwloc")

        ext = (_externals_dir(cactus_root) / "install" / "hwloc").resolve()
        if (ext / "lib" / "libhwloc.a").exists():
            _hwloc_libs = "hwloc"
            # If hwloc was built with PCI device support, we need libpciaccess too
            _hwloc_nm_rc, _hwloc_nm, _ = run_cmd("nm", str(ext / "lib" / "libhwloc.a"))
            if _hwloc_nm_rc == 0 and "pci_system_init" in _hwloc_nm:
                _hwloc_libs = "hwloc pciaccess"
            return True, _lib_lines(
                "HWLOC", str(ext), f"{ext}/include", f"{ext}/lib", _hwloc_libs
            )

        # Nothing found: fall through to pre-build below.

    # --with-hwloc or nothing found: pre-build from bundled tarball.
    install_dir = build_external_hwloc(
        cactus_root, read_externals_options(cactus_root),
        jobs=getattr(args, "jobs", 1) or 1,
    )
    _hwloc_libs2 = "hwloc"
    _h_nm_rc, _h_nm, _ = run_cmd("nm", str(install_dir / "lib" / "libhwloc.a"))
    if _h_nm_rc == 0 and "pci_system_init" in _h_nm:
        _hwloc_libs2 = "hwloc pciaccess"
    return True, (
        _lib_lines(
            "HWLOC", str(install_dir),
            f"{install_dir}/include",
            f"{install_dir}/lib",
            _hwloc_libs2,
        ) + f"\nHWLOC_INSTALL_DIR = {install_dir}"
    )


def build_external_yaml_cpp(cactus_root: Path, opts: dict, jobs: int = 1) -> Path:
    install_dir = (_externals_dir(cactus_root) / "install" / "yaml_cpp").resolve()
    if (install_dir / "lib" / "libyaml-cpp.a").exists():
        if _has_intel_symbols(install_dir / "lib"):
            print("  yaml_cpp: Intel symbols found — rebuilding with g++ …")
            import shutil as _yc_sh; _yc_sh.rmtree(str(install_dir / "lib"), ignore_errors=True)
        else:
            print("  yaml_cpp: already built, skipping.")
            return install_dir
    if _no_build:
        _build_would_build.add("yaml_cpp")
        return install_dir

    name    = "yaml-cpp-0.6.3"
    thorn   = cactus_root / "repos" / "ExternalLibraries-yaml_cpp"
    tarball = thorn / "dist" / f"{name}.tar"
    if not tarball.exists():
        raise FileNotFoundError(f"yaml_cpp tarball not found: {tarball}")

    dist_dir = tarball.parent
    patches  = [
        dist_dir / "cmake_version.patch",
        dist_dir / "patchtest.patch",
    ]

    build_root = (_externals_dir(cactus_root) / "build" / "yaml_cpp").resolve()
    build_root.mkdir(parents=True, exist_ok=True)
    install_dir.mkdir(parents=True, exist_ok=True)

    import shutil as _yc_sh2
    _yc_src_pre = build_root / name
    if _yc_src_pre.exists():
        _yc_sh2.rmtree(str(_yc_src_pre))

    log_path, log = _open_build_log(cactus_root, "yaml_cpp")
    print(f"  yaml_cpp: extracting {tarball.name} …  (log → {log_path.name})")
    with tarfile.open(tarball) as tf:
        _tar_extractall(tf, build_root)

    src_dir = build_root / name

    env = os.environ.copy()
    cxx = opts.get("CXX", env.get("CXX", "g++"))
    # Force GCC-compatible C++ to avoid Intel runtime symbols
    if Path(cxx).name in ("icpc", "icpx") and which("g++"):
        cxx = which("g++")
    env.pop("LIBS", None)

    build_dir = src_dir / "build"
    build_dir.mkdir(exist_ok=True)

    cmake_ext = (_externals_dir(cactus_root) / "install" / "cmake" / "bin" / "cmake").resolve()
    cmake_exe = str(cmake_ext) if cmake_ext.exists() else "cmake"

    cmake_args = [
        cmake_exe,
        "-DCMAKE_BUILD_TYPE=Release",
        f"-DCMAKE_CXX_COMPILER={cxx}",
        "-DYAML_CPP_BUILD_TESTS=OFF",
        "-DBUILD_SHARED_LIBS=OFF",
        f"-DCMAKE_INSTALL_PREFIX={install_dir}",
        "-DCMAKE_INSTALL_LIBDIR=lib",
        "..",
    ]

    try:
        print("  yaml_cpp: applying patches …")
        patchtest_applied = False
        for patch in patches:
            if not patch.exists():
                print(f"  yaml_cpp: patch not found, skipping: {patch.name}")
                continue
            subprocess.run(["patch", "-p1", "-i", str(patch)], cwd=src_dir, check=True,
                           stdout=log, stderr=subprocess.STDOUT)
            if patch.name == "patchtest.patch":
                patchtest_applied = True
        patch_tmp = src_dir / ".patch_tmp"
        if patchtest_applied and not patch_tmp.exists():
            raise RuntimeError("yaml_cpp: patchtest.patch failed — patch command is too old")
        if patch_tmp.exists():
            patch_tmp.unlink()

        print("  yaml_cpp: configuring …")
        subprocess.run(cmake_args, cwd=build_dir, env=env, check=True,
                       stdout=log, stderr=subprocess.STDOUT)
        print("  yaml_cpp: building …")
        subprocess.run(["make", f"-j{jobs}"], cwd=build_dir, env=env, check=True,
                       stdout=log, stderr=subprocess.STDOUT)
        print("  yaml_cpp: installing …")
        subprocess.run(["make", f"-j{jobs}", "install"], cwd=build_dir, env=env, check=True,
                       stdout=log, stderr=subprocess.STDOUT)
    except subprocess.CalledProcessError:
        log.flush()
        _log_tail(log_path)
        raise
    finally:
        log.close()
    _write_build_cfg(install_dir, "yaml_cpp", env, cmake_args)
    print(f"  yaml_cpp: installed to {install_dir}")
    return install_dir


def detect_yaml_cpp(args, state: dict, cactus_root: Path) -> Tuple[bool, str]:
    if getattr(args, "without_yaml_cpp", False) or state.get("with_yaml_cpp") is False:
        return False, "YAML_CPP_DIR = BUILD\nYAML_CPP_ENABLE_FORTRAN = OFF"

    if not getattr(args, "with_yaml_cpp", False):
        d = env_dir("YAML_CPP_DIR", "YAML_CPP_HOME", "YAML_CPP_ROOT", "EBROOTYAMLCPP")
        if d:
            return True, (
                _lib_lines("YAML_CPP", d, f"{d}/include", f"{d}/lib", "yaml-cpp")
                + "\nYAML_CPP_ENABLE_FORTRAN = OFF"
            )
        pc = pkg_prefix("yaml-cpp")
        if pc:
            return True, (
                _lib_lines("YAML_CPP", pc, f"{pc}/include", f"{pc}/lib", "yaml-cpp")
                + "\nYAML_CPP_ENABLE_FORTRAN = OFF"
            )
        ext = (_externals_dir(cactus_root) / "install" / "yaml_cpp").resolve()
        if (ext / "lib" / "libyaml-cpp.a").exists():
            if _has_intel_symbols(ext / "lib"):
                print("  yaml_cpp: Intel symbols found — rebuilding with g++ …")
                import shutil as _yc2_sh; _yc2_sh.rmtree(str(ext / "lib"), ignore_errors=True)
            else:
                return True, (
                    _lib_lines("YAML_CPP", str(ext), f"{ext}/include", f"{ext}/lib", "yaml-cpp")
                    + f"\nYAML_CPP_INSTALL_DIR = {ext}"
                    + "\nYAML_CPP_ENABLE_FORTRAN = OFF"
                )
        # Nothing found: fall through to pre-build below.

    install_dir = build_external_yaml_cpp(
        cactus_root, read_externals_options(cactus_root),
        jobs=getattr(args, "jobs", 1) or 1,
    )
    return True, (
        _lib_lines(
            "YAML_CPP", str(install_dir),
            f"{install_dir}/include",
            f"{install_dir}/lib",
            "yaml-cpp",
        )
        + f"\nYAML_CPP_INSTALL_DIR = {install_dir}"
        + "\nYAML_CPP_ENABLE_FORTRAN = OFF"
    )


def detect_gsl() -> Tuple[bool, str]:
    d = env_dir("GSL_HOME", "GSL_DIR", "GSL_ROOT", "TACC_GSL_DIR", "EBROOTGSL")
    if d:
        return True, f"GSL_DIR = {d}"

    if which("gsl-config"):
        rc, out, _ = run_cmd("gsl-config", "--prefix")
        if rc == 0 and out.strip() and out.strip() not in _SYSTEM_DIRS:
            return True, f"GSL_DIR = {out.strip()}"

    pc = pkg_prefix("gsl")
    if pc and pc not in _SYSTEM_DIRS:
        return True, f"GSL_DIR = {pc}"

    if Path("/usr/include/gsl/gsl_version.h").exists():
        return True, "# GSL: found in system paths"

    return False, "GSL_DIR = BUILD"

_BOOST_LIBS = (
    "boost_atomic boost_filesystem "
    "boost_math_c99 boost_math_c99f boost_math_c99l "
    "boost_math_tr1 boost_math_tr1f boost_math_tr1l boost_system"
)


def build_external_boost(cactus_root: Path, opts: dict, jobs: int = 1) -> Path:
    install_dir = (_externals_dir(cactus_root) / "install" / "boost").resolve()
    if (install_dir / "lib" / "libboost_filesystem.a").exists():
        print("  Boost: already built, skipping.")
        return install_dir
    if _no_build:
        _build_would_build.add("boost")
        return install_dir

    name    = "boost_1_84_0"
    thorn   = cactus_root / "repos" / "ExternalLibraries-Boost"
    tarball = thorn / "dist" / f"{name}-stripped.tar.gz"
    if not tarball.exists():
        raise FileNotFoundError(f"Boost tarball not found: {tarball}")

    build_root = (_externals_dir(cactus_root) / "build" / "boost").resolve()
    build_root.mkdir(parents=True, exist_ok=True)
    install_dir.mkdir(parents=True, exist_ok=True)

    log_path, log = _open_build_log(cactus_root, "boost")
    print(f"  Boost: extracting {tarball.name} …  (log → {log_path.name})")
    with tarfile.open(tarball) as tf:
        _tar_extractall(tf, build_root)

    src_dir = build_root / name

    env = os.environ.copy()
    env.pop("LIBS", None)

    b2_opts = [
        "--with-filesystem",
        "--with-math",
        "--with-system",
        "link=static",
    ]

    try:
        print("  Boost: bootstrapping …")
        subprocess.run(
            ["./bootstrap.sh", f"--prefix={install_dir}"],
            cwd=src_dir, env=env, check=True,
            stdout=log, stderr=subprocess.STDOUT,
        )
        print("  Boost: building …")
        subprocess.run(
            ["./b2", f"-j{jobs}"] + b2_opts,
            cwd=src_dir, env=env, check=True,
            stdout=log, stderr=subprocess.STDOUT,
        )
        print("  Boost: installing …")
        subprocess.run(
            ["./b2", "install"] + b2_opts,
            cwd=src_dir, env=env, check=True,
            stdout=log, stderr=subprocess.STDOUT,
        )
    except subprocess.CalledProcessError:
        log.flush()
        _log_tail(log_path)
        raise
    finally:
        log.close()
    _write_build_cfg(install_dir, "boost", env,
                     ["./bootstrap.sh", f"--prefix={install_dir}",
                      "&&", "./b2"] + b2_opts)
    print(f"  Boost: installed to {install_dir}")
    return install_dir


def detect_boost(args, state: dict, cactus_root: Path) -> Tuple[bool, str]:
    if getattr(args, "without_boost", False) or state.get("with_boost") is False:
        return False, "BOOST_DIR = BUILD"

    if not getattr(args, "with_boost", False):
        d = env_dir("BOOST_HOME", "BOOST_DIR", "BOOST_ROOT", "TACC_BOOST_DIR", "EBROOTBOOST")
        if d:
            return True, _lib_lines(
                "BOOST", d, f"{d}/include", f"{d}/lib", _BOOST_LIBS
            )
        pc = pkg_prefix("boost")
        if pc:
            return True, _lib_lines(
                "BOOST", pc, f"{pc}/include", f"{pc}/lib", _BOOST_LIBS
            )
        ext = (_externals_dir(cactus_root) / "install" / "boost").resolve()
        if (ext / "lib" / "libboost_filesystem.a").exists():
            return True, (
                _lib_lines("BOOST", str(ext), f"{ext}/include", f"{ext}/lib", _BOOST_LIBS)
                + f"\nBOOST_INSTALL_DIR = {ext}"
            )
        # Nothing found: fall through to pre-build below.

    install_dir = build_external_boost(
        cactus_root, read_externals_options(cactus_root),
        jobs=getattr(args, "jobs", 1) or 1,
    )
    return True, (
        _lib_lines(
            "BOOST", str(install_dir),
            f"{install_dir}/include",
            f"{install_dir}/lib",
            _BOOST_LIBS,
        )
        + f"\nBOOST_INSTALL_DIR = {install_dir}"
    )

def _find_slurm_pmi() -> str:
    """Return the directory prefix (e.g. '/usr') containing Slurm's PMI2
    headers (pmi2.h or pmi.h) and libraries, or '' if not found.  Used to
    pass --with-pmi=<prefix> when building a PMI-capable OpenMPI."""
    for prefix in ("/usr", "/usr/local", "/opt/slurm", "/opt/ohpc/pub"):
        p = Path(prefix)
        if ((p / "include" / "pmi2.h").exists() or
                (p / "include" / "pmi.h").exists() or
                (p / "include" / "slurm" / "pmi2.h").exists()):
            return prefix
    return ""


def _has_pmi_support(lib_dir: str) -> bool:
    """Return True if the MPI installation was built with Slurm PMI support.

    For static OpenMPI (--enable-shared=no), PMI_Init lives in the system's
    libpmi.so and appears only as an undefined reference in libopen-pal.a, not
    in libmpi.a.  The reliable check is: ask the mpicc wrapper whether it adds
    -lpmi / -lpmi2 / -lpmix to the link command.  Fall back to scanning all
    .a files for any PMI reference (undefined or defined) if the wrapper is
    not available."""
    d = Path(lib_dir)
    # Primary: use mpicc --showme:link if the wrapper is present.
    mpicc = d.parent / "bin" / "mpicc"
    if mpicc.exists():
        rc, out, _ = run_cmd(str(mpicc), "--showme:link")
        if rc == 0 and out.strip():
            if any(flag in out for flag in ("-lpmi", "-lpmi2", "-lpmix")):
                return True
            # --showme:link succeeded but no PMI flags → no PMI support.
            return False
        # Wrapper present but unresponsive; fall through to nm scan.
    # Fallback: scan all .a and .so files for any PMI symbol reference.
    targets = (list(d.glob("libmpi.so*")) + list(d.glob("libmpi.a"))
               + list(d.glob("libopen-pal.a")) + list(d.glob("libopen-rte.a")))
    for t in targets:
        nm_args = ["nm", "-D", str(t)] if ".so" in t.name else ["nm", str(t)]
        rc, out, _ = run_cmd(*nm_args)
        if rc == 0 and any(sym in out.lower()
                           for sym in ("pmi_init", "pmi2_init", "pmix_init")):
            return True
    return False


def _has_openmpi_symbols(lib_path: Path) -> bool:
    """Return True if any .a file in lib_path contains OpenMPI ABI symbols
    (ompi_*).  These cause undefined-reference errors when linking with
    MPICH/MVAPICH2 because the two MPI families use incompatible object
    representations."""
    targets = (list(lib_path.glob("*.a")) if lib_path.is_dir()
               else [lib_path] if lib_path.exists() else [])
    for t in targets:
        rc, out, _ = run_cmd("nm", str(t))
        if rc == 0 and ("ompi_mpi_byte" in out
                        or "ompi_mpi_comm_null" in out
                        or "ompi_mpi_comm_world" in out):
            return True
    return False


def _has_intel_symbols(lib_path: Path) -> bool:
    """Return True if any .a file in lib_path (or the path itself) was compiled
    with Intel (icc/icx).  Intel-compiled objects call _intel_fast_memcpy and
    similar Intel runtime symbols as UNDEFINED external references (defined in
    libintlc.so.5).  Plain nm (no --defined-only) catches these undefined refs.
    GCC-compiled libraries contain ZERO references to these symbols, so there
    are no false positives for GCC-built code."""
    targets = (list(lib_path.glob("*.a")) if lib_path.is_dir()
               else [lib_path] if lib_path.exists() else [])
    for t in targets:
        rc, out, _ = run_cmd("nm", str(t))
        if rc == 0 and ("_intel_fast_memset" in out
                        or "_intel_fast_memcpy" in out
                        or "__intel_avx_rep_memset" in out):
            return True
    return False


def _has_intel_runtime_libs(lib_path: Path) -> bool:
    """Return True if a shared library (.so) depends on Intel runtime libs
    (libimf.so, libsvml.so, libintlc.so, libirng.so)."""
    targets = (list(lib_path.glob("*.so")) if lib_path.is_dir()
               else [lib_path] if lib_path.exists() else [])
    intel_libs = ("libimf.so", "libsvml.so", "libintlc.so", "libirng.so")
    for t in targets:
        rc, out, _ = run_cmd("ldd", str(t))
        if rc == 0 and any(il in out for il in intel_libs):
            return True
    return False


def _zlib_prefix_from_lib(lib_path: Path) -> Optional[Path]:
    """Given a path to libz.a or libz.so, return the installation prefix if
    include/zlib.h is reachable from it, else None.

    HDF5's build.sh passes --with-zlib=PREFIX which expects PREFIX/include/zlib.h
    and PREFIX/lib/libz.* to exist.  We walk up from the lib dir looking for a
    parent whose sibling 'include' directory has zlib.h.
    """
    lib_dir = lib_path.parent
    # Walk up at most two levels: lib → prefix, lib64 → prefix, lib/arch → prefix
    for candidate_prefix in [lib_dir.parent, lib_dir.parent.parent]:
        if (candidate_prefix / "include" / "zlib.h").exists():
            return candidate_prefix
    return None


def detect_zlib(args, state: dict, cactus_root: Path) -> Tuple[bool, str]:
    # Explicit --without-zlib or persisted False → let Cactus handle it
    if getattr(args, "without_zlib", False) or state.get("with_zlib") is False:
        return False, "ZLIB_DIR = BUILD"

    # Module/environment-provided prefix — proper install tree, use directly.
    d = env_dir("ZLIB_HOME", "ZLIB_DIR", "ZLIB_ROOT")
    if d:
        return True, f"ZLIB_DIR = {d}\nZLIB_LIBS = z"

    # HDF5 is built with --enable-static-exec which requires libz.a (not just
    # libz.so).  Only use a system prefix when a static library is present.
    search_dirs: List[Path] = []

    if which("pkg-config"):
        rc, out, _ = run_cmd("pkg-config", "--variable=libdir", "zlib")
        if rc == 0 and out.strip():
            search_dirs.append(Path(out.strip()))

    machine = platform.machine()
    arch_dirs = {
        "x86_64": ["/usr/lib/x86_64-linux-gnu", "/usr/lib64", "/usr/lib"],
        "aarch64": ["/usr/lib/aarch64-linux-gnu", "/usr/lib64", "/usr/lib"],
        "ppc64le": ["/usr/lib/powerpc64le-linux-gnu", "/usr/lib64", "/usr/lib"],
    }
    for d in arch_dirs.get(machine, ["/usr/lib64", "/usr/lib"]):
        search_dirs.append(Path(d))

    if not getattr(args, "with_zlib", False):
        for lib_dir in search_dirs:
            # Accept libz.a first; fall back to libz.so (dynamic is fine for apps)
            for lib_name in ("libz.a", "libz.so"):
                candidate = lib_dir / lib_name
                if candidate.exists():
                    prefix = _zlib_prefix_from_lib(candidate)
                    if prefix:
                        return True, f"ZLIB_DIR = {prefix}\nZLIB_LIBS = z"
                    break

    # No system zlib found (or --with-zlib forces externals): pre-build it.
    opts = read_externals_options(cactus_root)
    install_dir = build_external_zlib(cactus_root, opts, jobs=getattr(args, "jobs", 1) or 1)

    # If the built zlib has Intel symbols it won't link with GCC; fall back to system.
    _built_lz = Path(install_dir) / "lib" / "libz.a"
    if _built_lz.exists():
        _nm_rc, _nm_out, _ = run_cmd("nm", str(_built_lz))
        if _nm_rc == 0 and "_intel_fast_memcpy" in _nm_out:
            # Find any system libz (static or dynamic)
            for _ld in ("/usr/lib64", "/usr/lib/x86_64-linux-gnu",
                        "/usr/lib/aarch64-linux-gnu", "/usr/lib"):
                for _ln in ("libz.a", "libz.so"):
                    if Path(_ld, _ln).exists():
                        _pfx = _zlib_prefix_from_lib(Path(_ld, _ln))
                        if _pfx:
                            return True, f"ZLIB_DIR = {_pfx}\nZLIB_LIBS = z"

    return True, (
        f"ZLIB_DIR          = {install_dir}\n"
        f"ZLIB_INSTALL_DIR  = {install_dir}\n"
        f"ZLIB_LIBS         = z"
    )

def build_external_jpeg(cactus_root: Path, opts: dict, jobs: int = 1) -> Path:
    """Extract and build libjpeg into externals/; return the install prefix."""
    install_dir = (_externals_dir(cactus_root) / "install" / "jpeg").resolve()
    if (install_dir / "lib" / "libjpeg.a").exists():
        print("  JPEG: already built, skipping.")
        return install_dir
    if _no_build:
        _build_would_build.add("jpeg")
        return install_dir

    tarball = (cactus_root / "arrangements" / "ExternalLibraries"
               / "libjpeg" / "dist" / "jpeg-9f.tar.gz")
    if not tarball.exists():
        raise FileNotFoundError(f"libjpeg tarball not found: {tarball}")

    build_root = (_externals_dir(cactus_root) / "build" / "jpeg").resolve()
    build_root.mkdir(parents=True, exist_ok=True)
    install_dir.mkdir(parents=True, exist_ok=True)

    log_path, log = _open_build_log(cactus_root, "jpeg")
    print(f"  JPEG: extracting {tarball.name} …  (log → {log_path.name})")
    with tarfile.open(tarball) as tf:
        _tar_extractall(tf, build_root)

    src_dir = build_root / "jpeg-9f"

    env = os.environ.copy()
    if "CC" in opts:
        env["CC"] = opts["CC"]
    if "CFLAGS" in opts:
        env["CFLAGS"] = opts.get("CFLAGS", "")

    configure_args = [
        str(src_dir / "configure"),
        f"--prefix={install_dir}",
        "--enable-static",
        "--disable-shared",
    ]

    try:
        print("  JPEG: configuring …")
        subprocess.run(configure_args, cwd=src_dir, env=env, check=True,
                       stdout=log, stderr=subprocess.STDOUT)
        print("  JPEG: building …")
        subprocess.run(["make", f"-j{jobs}"], cwd=src_dir, env=env, check=True,
                       stdout=log, stderr=subprocess.STDOUT)
        print("  JPEG: installing …")
        subprocess.run(["make", "install"], cwd=src_dir, env=env, check=True,
                       stdout=log, stderr=subprocess.STDOUT)
    except subprocess.CalledProcessError:
        raise RuntimeError(f"libjpeg build failed — see {log_path}")

    print(f"  JPEG: installed to {install_dir}")
    return install_dir


def detect_jpeg(args, state: dict, cactus_root: Path) -> Tuple[bool, str]:
    if getattr(args, "without_jpeg", False) or state.get("with_jpeg") is False:
        return False, "LIBJPEG_DIR = BUILD"

    if not getattr(args, "with_jpeg", False):
        # Environment / module-set prefix
        d = env_dir("JPEG_HOME", "JPEG_DIR", "JPEG_ROOT", "LIBJPEG_DIR")
        if d:
            return True, f"LIBJPEG_DIR = {d}"

        # pkg-config
        if which("pkg-config"):
            for pc_name in ("libjpeg", "jpeg"):
                rc, out, _ = run_cmd("pkg-config", "--variable=prefix", pc_name, timeout=10)
                if rc == 0 and out.strip():
                    prefix = out.strip()
                    return True, f"LIBJPEG_DIR = {prefix}"

        # Common system locations
        machine = platform.machine()
        sys_lib_dirs = {
            "x86_64":  ["/usr/lib/x86_64-linux-gnu", "/usr/lib64", "/usr/lib"],
            "aarch64": ["/usr/lib/aarch64-linux-gnu", "/usr/lib64", "/usr/lib"],
            "ppc64le": ["/usr/lib/powerpc64le-linux-gnu", "/usr/lib64", "/usr/lib"],
        }.get(machine, ["/usr/lib64", "/usr/lib"])

        for lib_dir in sys_lib_dirs:
            for lib_name in ("libjpeg.a", "libjpeg.so"):
                if Path(lib_dir, lib_name).exists() and Path("/usr/include/jpeglib.h").exists():
                    return True, "LIBJPEG_DIR = /usr"

        # Check externals pre-built
        ext = (_externals_dir(cactus_root) / "install" / "jpeg").resolve()
        if (ext / "lib" / "libjpeg.a").exists():
            return True, (f"LIBJPEG_DIR         = {ext}\n"
                          f"LIBJPEG_INSTALL_DIR = {ext}")

    # --with-jpeg or no system JPEG found: pre-build from tarball.
    opts = read_externals_options(cactus_root)
    install_dir = build_external_jpeg(cactus_root, opts,
                                      jobs=getattr(args, "jobs", 1) or 1)
    return True, (
        f"LIBJPEG_DIR         = {install_dir}\n"
        f"LIBJPEG_INSTALL_DIR = {install_dir}"
    )


def detect_scratch() -> str:
    for var in ("SCRATCH", "WORK", "PROJWORK", "MEMBERWORK", "WORKDIR"):
        v = os.environ.get(var, "")
        if v and Path(v).exists():
            # strip trailing username component so we can add @USER@
            p = Path(v)
            user = os.environ.get("USER", "")
            if user and p.name == user:
                return str(p.parent) + "/@USER@"
            return v.rstrip("/")
    for candidate in ("/scratch", "/scratch1", "/work", "/lustre/scratch", "/project"):
        if Path(candidate).exists():
            return f"{candidate}/@USER@"
    return "/home/@USER@"

# ---------------------------------------------------------------------------
# Aggregate
# ---------------------------------------------------------------------------

class Probe:
    def __init__(self, args, state: dict, cactus_root: Path):
        self.hostname = socket.getfqdn()
        self.hw       = detect_hardware()
        self.modules  = detect_modules()
        self.sched    = detect_scheduler(args.queue or "")
        self.comp     = detect_compilers()
        write_externals_options(cactus_root, self.comp)
        self.mpi = detect_mpi(args, state, cactus_root, sched=self.sched)
        # Ensure the detected MPI's bin/include/lib dirs are first in PATH/CPATH/
        # LD_LIBRARY_PATH.  This is critical when the environment has a DIFFERENT
        # MPI loaded via a module (e.g. openmpi was module-loaded but we detected
        # mvapich2) — without prepending, cmake/make inside the externals builds
        # would use the module-loaded MPI wrappers and produce ABI-incompatible
        # object files.
        if self.mpi.found and self.mpi.dir:
            _mpi_bin_dir = Path(self.mpi.bin_dir) if self.mpi.bin_dir else Path(self.mpi.dir) / "bin"
            _mpi_inc_dir = self.mpi.inc_dirs.split()[0] if self.mpi.inc_dirs else str(Path(self.mpi.dir) / "include")
            _mpi_lib_dir = self.mpi.lib_dirs.split()[0] if self.mpi.lib_dirs else str(Path(self.mpi.dir) / "lib")
            _current_mpicc = which("mpicc") or ""
            if str(_mpi_bin_dir) not in _current_mpicc:
                if _mpi_bin_dir.is_dir():
                    os.environ["PATH"] = str(_mpi_bin_dir) + ":" + os.environ.get("PATH", "")
                    print(f"  MPI: prepending {_mpi_bin_dir} to PATH", flush=True)
            if _mpi_inc_dir and Path(_mpi_inc_dir).is_dir():
                _cpath = os.environ.get("CPATH", "")
                if _mpi_inc_dir not in _cpath:
                    os.environ["CPATH"] = _mpi_inc_dir + (":" + _cpath if _cpath else "")
            if _mpi_lib_dir and Path(_mpi_lib_dir).is_dir():
                for _ev in ("LD_LIBRARY_PATH", "LIBRARY_PATH"):
                    _lp = os.environ.get(_ev, "")
                    if _mpi_lib_dir not in _lp:
                        os.environ[_ev] = _mpi_lib_dir + (":" + _lp if _lp else "")
        # If the MPI wrapper reveals a specific underlying compiler, use it.
        # The selected MPI drives compiler choice; whatever compiler the MPI
        # was built with (icc, gcc, clang, …) is what we compile Cactus with.
        if self.mpi.found and self.mpi.cc and self.mpi.cc != self.comp.CC:
            print(f"  MPI uses {self.mpi.cc} — switching compiler suite to match",
                  flush=True)
            self.comp = _compilers_from_mpi(self.mpi, self.comp)
            write_externals_options(cactus_root, self.comp)
        if self.mpi.found:
            print(f"  Compiler: CC={self.comp.CC}  CXX={self.comp.CXX}"
                  f"  F90={self.comp.F90}", flush=True)
        # If the detected MPI has a specific module name, replace any existing MPI
        # module in the loaded list so the envsetup block uses the right one.
        if self.mpi.found and self.mpi.module_name:
            _mpi_kws = ("openmpi", "mpich", "mvapich", "intel-mpi", "impi")
            _new_loaded, _replaced = [], False
            for _mod in self.modules.loaded:
                if any(_kw in _mod.lower() for _kw in _mpi_kws):
                    if not _replaced:
                        _new_loaded.append(self.mpi.module_name)
                        _replaced = True
                    # else: drop duplicate MPI module entries
                else:
                    _new_loaded.append(_mod)
            if not _replaced and self.modules.available:
                _new_loaded.append(self.mpi.module_name)
            self.modules.loaded = _new_loaded
        # If the MPI installation changed since the last configure run, all
        # MPI-dependent externals must be rebuilt (OpenMPI ↔ MPICH ABI incompatibility).
        _prev_mpi_dir = state.get("_auto_mpi_dir", state.get("mpi_dir", ""))
        if (self.mpi.found and self.mpi.dir and _prev_mpi_dir
                and _prev_mpi_dir != self.mpi.dir):
            print(f"  MPI changed: {_prev_mpi_dir} → {self.mpi.dir}")
            print(f"  Removing MPI-dependent externals for rebuild …")
            import shutil as _mpi_ch_sh
            for _ext_name in ("hdf5", "silo", "adios2", "openpmd", "amrex"):
                _ext_lib = (_externals_dir(cactus_root) / "install" / _ext_name / "lib")
                if _ext_lib.exists():
                    _mpi_ch_sh.rmtree(str(_ext_lib), ignore_errors=True)
                    print(f"    → removed {_ext_name}/lib")
        # Persist the current MPI dir NOW, before running the HDF5/silo/etc.
        # probes.  If those probes crash (e.g. a srun signal kills Python mid-run
        # before the end-of-main _save_state call), the stale _auto_mpi_dir from
        # the previous run would survive and cause a spurious wipe on the next run.
        if self.mpi.found and self.mpi.dir:
            state["_auto_mpi_dir"] = self.mpi.dir
            _save_state(cactus_root, state)
        self.gpu      = detect_gpu()
        if getattr(args, "cuda_arch", None):
            self.gpu.found   = True   # explicit arch implies CUDA intent
            self.gpu.sm_arch = args.cuda_arch

        self.cmake_found, self.cmake_cfg, self.cmake_bin_dir = detect_cmake(args, state, cactus_root)
        if self.cmake_bin_dir:
            os.environ["PATH"] = str(self.cmake_bin_dir) + ":" + os.environ.get("PATH", "")
        nsimd_simd = _HW_SIMD_TO_NSIMD.get(self.hw.simd, "CPU")
        self.nsimd_found, self.nsimd_cfg = detect_nsimd(args, state, cactus_root, nsimd_simd)
        self.jpeg_found,  self.jpeg_cfg  = detect_jpeg(args, state, cactus_root)
        self.zlib_found,  self.zlib_cfg  = detect_zlib(args, state, cactus_root)
        self.hdf5_found, self.hdf5_cfg, _hdf5_mod = detect_hdf5(
            args, state, cactus_root,
            mpi_found=self.mpi.found, mpi=self.mpi, sched=self.sched)
        # Add the selected system HDF5 module to the envsetup module-load list.
        if self.hdf5_found and _hdf5_mod:
            _hdf5_kws = ("hdf5", "phdf5")
            _new_loaded, _replaced = [], False
            for _mod in self.modules.loaded:
                if any(_kw in _mod.lower() for _kw in _hdf5_kws):
                    if not _replaced:
                        _new_loaded.append(_hdf5_mod)
                        _replaced = True
                else:
                    _new_loaded.append(_mod)
            if not _replaced and self.modules.available:
                _new_loaded.append(_hdf5_mod)
            self.modules.loaded = _new_loaded
        self.silo_found,  self.silo_cfg  = detect_silo(args, state, cactus_root)
        self.fftw3_found, self.fftw3_cfg = detect_fftw3(args, state, cactus_root)
        self.blas_found,  self.blas_cfg    = detect_blas()
        self.lapack_found, self.lapack_cfg = detect_lapack(args, state, cactus_root)
        self.hwloc_found, self.hwloc_cfg      = detect_hwloc(args, state, cactus_root, self.mpi)
        self.yaml_cpp_found, self.yaml_cpp_cfg = detect_yaml_cpp(args, state, cactus_root)
        self.gsl_found,   self.gsl_cfg   = detect_gsl()
        self.boost_found, self.boost_cfg = detect_boost(args, state, cactus_root)

        self.adios2_found, self.adios2_cfg, _adios2_dir = detect_adios2(
            args, state, cactus_root, self.mpi.found
        )
        # Pass HDF5 root to openPMD only when the install has parallel support
        # (openPMD rejects serial HDF5 when MPI is enabled).
        _hdf5_root: Optional[str] = None
        if self.hdf5_found and self.mpi.found:
            _ext_hdf5 = (_externals_dir(cactus_root) / "install" / "hdf5").resolve()
            if (_ext_hdf5 / "lib" / "libhdf5.a").exists():
                if _hdf5_is_parallel(str(_ext_hdf5)):
                    _hdf5_root = str(_ext_hdf5)
            if not _hdf5_root:
                _d = env_dir(
                    "CRAY_HDF5_PARALLEL_PREFIX_DIR", "CRAY_HDF5_DIR",
                    "TACC_PHDF5_DIR", "TACC_HDF5_DIR",
                    "HDF5_DIR", "HDF5_HOME", "HDF5_ROOT",
                )
                if _d and _hdf5_is_parallel(_d):
                    _hdf5_root = _d
        self.openpmd_found, self.openpmd_cfg = detect_openpmd(
            args, state, cactus_root, self.mpi.found, _adios2_dir, _hdf5_root
        )

        _amd_arch = _detect_amd_arch()
        self.amrex_found, self.amrex_cfg = detect_amrex(
            args, state, cactus_root,
            mpi_found=self.mpi.found,
            gpu_found=self.gpu.found,
            sm_arch=self.gpu.sm_arch if self.gpu.found else None,
            amd_arch=_amd_arch,
        )

# ---------------------------------------------------------------------------
# .ini
# ---------------------------------------------------------------------------

def generate_ini(p: Probe, name: str, args) -> str:
    hw  = p.hw
    sc  = p.sched
    ppn = args.ppn or hw.ppn

    user  = os.environ.get("USER", os.environ.get("LOGNAME", "unknown"))
    email = args.email or f"{user}@unknown"

    sourcebasedir = args.sourcebasedir or "/home/@USER@"
    scratch       = args.scratch or detect_scratch()
    basedir       = scratch.rstrip("/") + "/simulations"

    # envsetup — collect extra PATH / LD_LIBRARY_PATH entries for externals
    extra_paths = [str(d) for d in [p.cmake_bin_dir,
                                    p.mpi.bin_dir if p.mpi.bin_dir else None]
                   if d]
    if extra_paths:
        path_export = 'export PATH="' + ":".join(extra_paths) + ':$PATH"\n'
    else:
        path_export = ""
    # When the MPI is from the externals directory (bin_dir is set and NOT a
    # system module path), also export LD_LIBRARY_PATH so that cactus_sim can
    # dlopen OpenMPI's PMI plugin at runtime.
    _ext_mpi_lib = (p.mpi.lib_dirs.split()[0]
                    if p.mpi.bin_dir and p.mpi.lib_dirs else "")
    if _ext_mpi_lib and "externals" in _ext_mpi_lib:
        ldlib_export = (f'export LD_LIBRARY_PATH="{_ext_mpi_lib}'
                        ':${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}"\n')
    else:
        ldlib_export = ""

    # Filter out modules superseded by our choices:
    #   • MPI modules (mpich/openmpi/mvapich/impi) when using externals MPI
    #   • Intel compiler modules and Intel-linked dep modules when using GCC
    _using_ext_mpi = bool(p.mpi and p.mpi.bin_dir and "externals" in p.mpi.bin_dir)
    _using_gcc     = (getattr(p.comp, "kind", "gnu") == "gnu")
    _mpi_mod_re    = re.compile(r'^(mpich|openmpi|mvapich2?|impi|intel.?mpi)\b',
                                re.IGNORECASE)
    def _keep_module(m: str) -> bool:
        if _using_ext_mpi and _mpi_mod_re.match(m):
            return False                            # superseded by externals MPI
        if _using_gcc and re.match(r'^intel/', m, re.IGNORECASE):
            return False                            # Intel compiler suite, using GCC
        if _using_gcc and re.search(r'/intel[-_]', m, re.IGNORECASE):
            return False                            # dep built for Intel (hwloc/X/intel-Y)
        return True
    _filtered_modules = [m for m in p.modules.loaded if _keep_module(m)]

    if p.modules.available and _filtered_modules:
        mod_lines = ["module purge &&"] + \
                    [f"module load {m} &&" for m in _filtered_modules]
        mod_lines[-1] = mod_lines[-1][:-3]   # remove trailing &&
        mod_block = "\n".join(f"  {l}" for l in mod_lines)
        _extra_env = "".join(f"  {e}" for e in [path_export, ldlib_export] if e)
        envsetup = f"envsetup = <<EOF\n{mod_block}\n{_extra_env}EOF"
    else:
        envsetup = ('envsetup = <<EOF\n'
                    '# No modules detected — adjust if needed.\n'
                    'export LIBRARY_PATH="${LIBRARY_PATH+$LIBRARY_PATH:}'
                    '/usr/local/lib64:/usr/local/lib:/usr/lib64:/usr/lib:/lib64:/lib"\n'
                    'export CPATH="${CPATH+$CPATH:}'
                    '/usr/local/include:/usr/include:/include"\n'
                    + (f'  {path_export}' if path_export else '')
                    + (f'  {ldlib_export}' if ldlib_export else '')
                    + 'EOF')

    hn = p.hostname
    _escaped_hn = hn.replace(".", r"\.")
    alias_pattern = getattr(args, "aliaspattern", None) or f"^{_escaped_hn}$"
    # Normalize: if the pattern was stored with double-escaped backslashes
    # (common when user typed \\d on the shell instead of \d), strip one level.
    # The ini file is read verbatim by SimFactory, so one backslash in the file
    # means one backslash in the regex, and \d means digit.
    if alias_pattern and not re.search(alias_pattern, hn):
        _ap2 = alias_pattern.replace("\\\\", "\\")
        if _ap2 != alias_pattern and re.search(_ap2, hn):
            alias_pattern = _ap2

    # cluster-only fields
    cluster_fields = ""
    if sc.kind in ("slurm", "pbs", "lsf"):
        alloc = args.allocation or "NO_ALLOCATION"
        queue = sc.default_queue
        mem   = hw.mem_mb
        cluster_fields = (
            f"allocation      = {alloc}\n"
            f"queue           = {queue}\n"
            f"memory          = {mem}\n"
            "maxwalltime     = 24:00:00\n"
        )

    out = f"""\
[{name}]

# Auto-generated by simfactory-configure.py on {today()}
# Review and adjust before use.

# Machine description
nickname        = {name}
name            = {hn}
location        = unknown
description     = Auto-configured
status          = personal

# Access
hostname        = {hn}
aliaspattern    = {alias_pattern}

{envsetup}

# Source tree management
sourcebasedir   = {sourcebasedir}
optionlist      = {name}.cfg
submitscript    = {name}.sub
runscript       = {name}.run
makejobs        = {ppn}
make            = make -j@MAKEJOBS@

# Simulation management
basedir         = {basedir}
cpu             = {hw.cpu_model}
ppn             = {ppn}
max-num-threads = {ppn}
num-threads     = {hw.threads_per_core}
nodes           = 1
{cluster_fields}
submit          = {sc.submit}
getstatus       = {sc.getstatus}
stop            = {sc.stop}
submitpattern   = {sc.submitpattern}
statuspattern   = {sc.statuspattern}
queuedpattern   = {sc.queuedpattern}
runningpattern  = {sc.runningpattern}
holdingpattern  = {sc.holdingpattern}
exechost        = {sc.exechost}
exechostpattern = {sc.exechostpattern}
stdout          = cat @SIMULATION_NAME@.out
stderr          = cat @SIMULATION_NAME@.err
stdout-follow   = tail -n 100 -f @SIMULATION_NAME@.out @SIMULATION_NAME@.err
"""
    return _clean(out)

# ---------------------------------------------------------------------------
# .cfg
# ---------------------------------------------------------------------------

def generate_cfg(p: Probe, name: str, args) -> str:
    c  = p.comp
    g  = p.gpu

    # Build LIBS and LIBDIRS lines.  For GCC we need the gfortran runtime so
    # that Cactus can link C executables that include Fortran objects (HDF5
    # Fortran bindings, LAPACK, any Cactus Fortran thorn).
    _extra_libs = list(c.extra_libs.split()) if c.extra_libs else []
    _libdirs: list = []
    if c.kind == "gnu" and c.F90 and "gfortran" in os.path.basename(c.F90).lower():
        _gfc_flags = _gcc_gfortran_fclibs(c.F90)
        if _gfc_flags:
            for _f in _gfc_flags.split():
                if _f.startswith("-L"):
                    _d = _f[2:]
                    # Skip system GCC dirs (e.g. /usr/lib/gcc/…/8) — those
                    # belong to the system GCC and may be a different major
                    # version than the compiler we're actually using.  Pointing
                    # Cactus there causes it to link against the wrong libstdc++.
                    if _d.startswith("/usr/lib/gcc/"):
                        continue
                    if _d not in _libdirs:
                        _libdirs.append(_d)
                elif _f.startswith("-l"):
                    _ln = _f[2:]
                    if _ln == "quadmath":
                        continue  # not needed; Cactus doesn't use __float128
                    if _ln not in _extra_libs:
                        _extra_libs.append(_ln)
        else:
            # _gcc_gfortran_fclibs found no path; add gfortran name only and
            # let the linker find it via LD_LIBRARY_PATH / LIBRARY_PATH.
            if "gfortran" not in _extra_libs:
                _extra_libs.append("gfortran")
    # CUDA runtime: add libcudart and the CUDA lib dir so that nvcc-generated
    # stub code (__cudaRegisterFunction etc.) links correctly.
    if g.found and g.nvcc_path:
        _clib = _cuda_lib_dir(g.nvcc_path)
        if _clib and _clib not in _libdirs:
            _libdirs.append(_clib)
        # Prefer static CUDA runtime so compute nodes don't need libcudart.so
        # in LD_LIBRARY_PATH.  libcudart_static.a internally uses dlopen (->dl),
        # POSIX timers (->rt), and pthreads (->pthread).
        # libcurand_static.a requires libculibos.a (CUDA OS-abstraction layer).
        for _clib_name in ("cudart_static", "curand_static", "culibos",
                           "dl", "rt", "pthread"):
            if _clib_name not in _extra_libs:
                _extra_libs.append(_clib_name)

    libs_line    = f"\nLIBS    = {' '.join(_extra_libs)}" if _extra_libs else ""
    libdirs_line = f"\nLIBDIRS = {' '.join(_libdirs)}"   if _libdirs    else ""

    simd      = p.hw.simd
    arch_flag = _simd_flags(simd, c.kind)

    # OpenMPI's static libopen-pal.a always embeds hwloc 2.0.4 source directly
    # (hwloc_linux_component, hwloc_linuxio_component).  When we also link our
    # standalone libhwloc.a the linker sees "multiple definition".  The two
    # copies are identical (same hwloc 2.0.4 source), so --allow-multiple-
    # definition is safe: the linker picks the first definition encountered.
    # OpenMPI's --with-hwloc=<path> configure test requires a shared .so which
    # our static-only hwloc build doesn't provide, so we can't avoid the
    # embedding by pointing OpenMPI at our hwloc.
    _extra_ldflags = (
        " -Wl,--allow-multiple-definition"
        if p.hwloc_found and p.mpi.found and p.mpi.kind == "openmpi"
        else ""
    )

    if g.found:
        sm = g.sm_arch or "sm_80"
        _host_gcc  = _gcc_major(c.CXX)
        _cuda_max  = _nvcc_max_gcc(g.nvcc_path) if g.nvcc_path else 0
        _allow_uns = (
            " -allow-unsupported-compiler"
            if _host_gcc and _cuda_max and _host_gcc > _cuda_max
            else ""
        )
        if _allow_uns:
            print(f"  CUDA: host GCC {_host_gcc} > nvcc max {_cuda_max} — "
                  "adding -allow-unsupported-compiler to CUCCFLAGS", flush=True)
        cuda_block = (
            f"CUCC  = nvcc\n"
            f"CUCCFLAGS = --compiler-bindir {c.CXX} -x cu -g -std=c++17"
            f" --expt-relaxed-constexpr --extended-lambda"
            f" --forward-unknown-to-host-compiler"
            f" --relocatable-device-code=true --objdir-as-tempdir"
            f" --gpu-architecture {sm}"
            f" --diag-suppress=20012"
            f"{_allow_uns}"
            f" -DSIMD_DISABLE\n"
            f"LD = nvcc --compiler-bindir {c.CXX} -g -fno-lto"
            f" --forward-unknown-to-host-compiler"
            f" --relocatable-device-code=true --objdir-as-tempdir\n"
            "CUCC_DEBUG_FLAGS    = -g3\n"
            "CUCC_OPTIMISE_FLAGS = -O3\n"
            "CUCC_WARN_FLAGS     = -Xcompiler -Wall\n"
            "CUCC_OPENMP_FLAGS   = -Xcompiler -fopenmp\n"
            "\n"
            "DISABLE_INT16  = yes\n"
            "DISABLE_REAL16 = yes\n"
            "\n"
            "AMREX_ENABLE_CUDA = yes"
        )
    else:
        cuda_block = "# CUCC = nvcc  # uncomment and configure for CUDA\nAMREX_ENABLE_CUDA = no"

    # MPI
    if p.mpi.found:
        if p.mpi.kind == "cray":
            mpi_block = "# MPI provided by Cray PE wrappers — no explicit MPI_DIR needed"
        else:
            lines = []
            if p.mpi.dir:      lines.append(f"MPI_DIR      = {p.mpi.dir}")
            if p.mpi.inc_dirs: lines.append(f"MPI_INC_DIRS = {p.mpi.inc_dirs}")
            if p.mpi.lib_dirs: lines.append(f"MPI_LIB_DIRS = {p.mpi.lib_dirs}")
            if p.mpi.libs:     lines.append(f"MPI_LIBS     = {p.mpi.libs}")
            mpi_block = "\n".join(lines) if lines else \
                        f"# MPI ({p.mpi.kind}): found via compiler wrapper; system paths should suffice"
    else:
        mpi_block = "# MPI not detected — Cactus ExternalLibraries/MPI will try to locate it"

    out = f"""\
# Option list for {name}
# Auto-generated by simfactory-configure.py on {today()}
# Review and adjust before use.

VERSION = {name}-{today()}

CPP = {c.CPP}
FPP = {c.FPP}
CC  = {c.CC}
CXX = {c.CXX}
F90 = {c.F90}

FPPFLAGS = -traditional
CFLAGS   = {(c.CFLAGS + " " + arch_flag).strip()}
CXXFLAGS = {(c.CXXFLAGS + " " + arch_flag).strip()}
F90FLAGS = {(c.F90FLAGS + " " + arch_flag).strip()}
LDFLAGS  = -rdynamic{_extra_ldflags}
{libs_line}{libdirs_line}

C_LINE_DIRECTIVES = yes
F_LINE_DIRECTIVES = yes

DEBUG           = no
CPP_DEBUG_FLAGS = -DCARPET_DEBUG
FPP_DEBUG_FLAGS = -DCARPET_DEBUG
C_DEBUG_FLAGS   = -g3
CXX_DEBUG_FLAGS = -g3
F90_DEBUG_FLAGS = -g3

OPTIMISE           = yes
CPP_OPTIMISE_FLAGS =
C_OPTIMISE_FLAGS   = -O2
CXX_OPTIMISE_FLAGS = -O2
F90_OPTIMISE_FLAGS = -O2

PROFILE           = no
C_PROFILE_FLAGS   = -pg
CXX_PROFILE_FLAGS = -pg
F90_PROFILE_FLAGS = -pg

WARN           = yes
CPP_WARN_FLAGS = -Wall
C_WARN_FLAGS   = -Wall
CXX_WARN_FLAGS = -Wall
F90_WARN_FLAGS = -Wall

OPENMP           = yes
CPP_OPENMP_FLAGS = {c.omp_flag}
FPP_OPENMP_FLAGS = -D_OPENMP
C_OPENMP_FLAGS   = {c.omp_flag}
CXX_OPENMP_FLAGS = {c.omp_flag}
F90_OPENMP_FLAGS = {c.omp_flag}
LD_OPENMP_FLAGS  = {c.omp_ld}

VECTORISE                = yes
VECTORISE_ALIGNED_ARRAYS = no
VECTORISE_INLINE         = yes

{cuda_block}

PTHREADS_DIR = NO_BUILD

{p.cmake_cfg}

{mpi_block}

{p.hdf5_cfg}

{p.fftw3_cfg}

{p.blas_cfg}

{p.lapack_cfg}

{p.hwloc_cfg}

{p.gsl_cfg}

{p.boost_cfg}

{p.jpeg_cfg}

{p.zlib_cfg}

{p.silo_cfg}

{p.nsimd_cfg}

{p.adios2_cfg}

{p.openpmd_cfg}

{p.amrex_cfg}

{p.yaml_cpp_cfg}
"""
    return _clean(out)

# ---------------------------------------------------------------------------
# .run
# ---------------------------------------------------------------------------

def generate_run(p: Probe, name: str) -> str:
    if p.sched.kind == "slurm" or p.mpi.kind == "cray":
        if p.mpi.kind == "openmpi":
            # OpenMPI + bare srun fails because Slurm's default PMI2/PMIx
            # doesn't interoperate with OpenMPI without --mpi=pmix.
            # Use mpirun (which picks up the Slurm allocation automatically)
            # for reliable multi-node execution.
            run_exec = "time mpirun -np @NUM_PROCS@ @EXECUTABLE@ -L 3 @PARFILE@"
        else:
            run_exec = "time srun -n @NUM_PROCS@ @EXECUTABLE@ -L 3 @PARFILE@"
    elif p.mpi.found:
        run_exec = (
            "if [ ${CACTUS_NUM_PROCS} = 1 ]; then\n"
            "    @EXECUTABLE@ -L 3 @PARFILE@\n"
            "else\n"
            "    mpirun -np @NUM_PROCS@ @EXECUTABLE@ -L 3 @PARFILE@\n"
            "fi"
        )
    else:
        run_exec = "@EXECUTABLE@ -L 3 @PARFILE@"

    mod_list = "module list\n" if p.modules.available else ""

    return f"""\
#! /bin/bash
# Run script for {name}
# Auto-generated by simfactory-configure.py on {today()}

echo "Preparing:"
set -x
set -e

cd @RUNDIR@-active

{mod_list}echo "Checking:"
pwd
hostname
date

echo "Environment:"
export CACTUS_NUM_PROCS=@NUM_PROCS@
export CACTUS_NUM_THREADS=@NUM_THREADS@
export GMON_OUT_PREFIX=gmon.out
export OMP_NUM_THREADS=@NUM_THREADS@
export OMP_STACKSIZE=8192
env | sort > SIMFACTORY/ENVIRONMENT

echo "Starting:"
export CACTUS_STARTTIME=$(date +%s)

{run_exec}

echo "Stopping:"
date
echo "Done."
"""

# ---------------------------------------------------------------------------
# .sub
# ---------------------------------------------------------------------------

def generate_sub(p: Probe, name: str, args) -> Optional[str]:
    if p.sched.kind == "slurm":
        return f"""\
#! /bin/bash
# Slurm submit script for {name}
# Auto-generated by simfactory-configure.py on {today()}
#SBATCH -t @WALLTIME@
#SBATCH --account=@ALLOCATION@
#SBATCH --partition=@QUEUE@
#SBATCH --nodes=@NODES@
#SBATCH --exclusive --mem=0
#SBATCH --ntasks-per-node=@NODE_PROCS@
#SBATCH --cpus-per-task=@NUM_THREADS@
#SBATCH --export=ALL
#SBATCH -J @SIMULATION_NAME@
#SBATCH --mail-type=ALL
#SBATCH --mail-user=@EMAIL@
#SBATCH --no-requeue
#SBATCH @("@CHAINED_JOB_ID@" != "" ? "-d afterany:@CHAINED_JOB_ID@" : "")@
#SBATCH -o @RUNDIR@/@SIMULATION_NAME@.out
#SBATCH -e @RUNDIR@/@SIMULATION_NAME@.err

cd @SOURCEDIR@
@SIMFACTORY@ run @SIMULATION_NAME@ --basedir=@BASEDIR@ --machine=@MACHINE@ --restart-id=@RESTART_ID@ @FROM_RESTART_COMMAND@
"""
    if p.sched.kind == "pbs":
        return f"""\
#! /bin/bash
# PBS submit script for {name}
# Auto-generated by simfactory-configure.py on {today()}
#PBS -l walltime=@WALLTIME@
#PBS -l nodes=@NODES@:ppn=@NODE_PROCS@
#PBS -q @QUEUE@
#PBS -A @ALLOCATION@
#PBS -N @SIMULATION_NAME@
#PBS -j oe
#PBS -m abe
#PBS -M @EMAIL@
#PBS -o @RUNDIR@/@SIMULATION_NAME@.out

cd @SOURCEDIR@
@SIMFACTORY@ run @SIMULATION_NAME@ --basedir=@BASEDIR@ --machine=@MACHINE@ --restart-id=@RESTART_ID@ @FROM_RESTART_COMMAND@
"""
    if p.sched.kind == "lsf":
        return f"""\
#! /bin/bash
# LSF submit script for {name}
# Auto-generated by simfactory-configure.py on {today()}
#BSUB -W @WALLTIME@
#BSUB -P @ALLOCATION@
#BSUB -q @QUEUE@
#BSUB -nnodes @NODES@
#BSUB -J @SIMULATION_NAME@
#BSUB -u @EMAIL@
#BSUB -N
#BSUB -o @RUNDIR@/@SIMULATION_NAME@.out
#BSUB -e @RUNDIR@/@SIMULATION_NAME@.err

cd @SOURCEDIR@
@SIMFACTORY@ run @SIMULATION_NAME@ --basedir=@BASEDIR@ --machine=@MACHINE@ --restart-id=@RESTART_ID@ @FROM_RESTART_COMMAND@
"""
    return None  # personal machine: no submit script

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _clean(text: str) -> str:
    """Collapse 3+ blank lines to 2."""
    return re.sub(r'\n{3,}', '\n\n', text).strip() + "\n"

def yn(b: bool) -> str:
    return "yes" if b else "no"

def report(p: Probe, name: str):
    print(f"\n{'='*62}")
    print(f"  simfactory-configure  —  {name}")
    print(f"{'='*62}")
    hw = p.hw
    print(f"  Host       : {p.hostname}")
    print(f"  CPU        : {hw.cpu_model}")
    print(f"  SIMD       : {hw.simd}")
    print(f"  PPn        : {hw.ppn} physical cores  ({hw.logical_cpus} logical, "
          f"{hw.sockets} socket(s) × {hw.cores_per_socket} cores/socket)")
    print(f"  Memory     : {hw.mem_mb} MB")
    print()
    print(f"  Modules    : {yn(p.modules.available)}"
          + (f"  ({len(p.modules.loaded)} loaded)" if p.modules.loaded else ""))
    print(f"  Scheduler  : {p.sched.kind}"
          + (f"  queue={p.sched.default_queue}" if p.sched.default_queue else ""))
    print()
    print(f"  Compilers  : {p.comp.kind}  "
          f"CC={p.comp.CC}  CXX={p.comp.CXX}  F90={p.comp.F90}")
    print(f"  MPI        : {yn(p.mpi.found)}"
          + (f"  ({p.mpi.kind})  dir={p.mpi.dir}" if p.mpi.found and p.mpi.dir else ""))
    if p.gpu.found:
        arch_str  = p.gpu.sm_arch or "(arch unknown — use --cuda-arch to set)"
        name_str  = f"  {p.gpu.gpu_name}" if p.gpu.gpu_name else ""
        nvcc_str  = f"  [{p.gpu.nvcc_path}]" if p.gpu.nvcc_path != "nvcc" else ""
        ver_str   = f"  nvcc {p.gpu.cuda_version}" if p.gpu.cuda_version else ""
        print(f"  CUDA/GPU   : yes{name_str}  {arch_str}{nvcc_str}{ver_str}")
    else:
        print("  CUDA/GPU   : no")
    print()
    print(f"  HDF5       : {yn(p.hdf5_found)}")
    print(f"  FFTW3      : {yn(p.fftw3_found)}")
    print(f"  BLAS       : {yn(p.blas_found)}")
    print(f"  LAPACK     : {yn(p.lapack_found)}")
    print(f"  GSL        : {yn(p.gsl_found)}")
    print(f"  Boost      : {yn(p.boost_found)}"
          + ("  (will BUILD)" if "boost" in _build_would_build else ""))
    print(f"  Silo       : {yn(p.silo_found)}")
    print(f"  JPEG       : {yn(p.jpeg_found)}")
    print(f"  zlib       : {yn(p.zlib_found)}")
    print(f"  NSIMD      : {yn(p.nsimd_found)}")
    print(f"  ADIOS2     : {yn(p.adios2_found)}")
    print(f"  openPMD    : {yn(p.openpmd_found)}")
    print(f"  AMReX      : {yn(p.amrex_found)}")
    print(f"{'='*62}")

# ---------------------------------------------------------------------------
# Externals — pre-build libraries outside the Cactus build system
# ---------------------------------------------------------------------------

def _state_path(root: Path, name: str) -> Path:
    return root / "simfactory" / "etc" / f"{name}.json"


def _load_state(root: Path, name: Optional[str] = None) -> dict:
    # 1. New location: simfactory/etc/{name}.json (per-machine, filesystem-safe)
    if name:
        p = _state_path(root, name)
        if p.exists():
            try:
                return json.loads(p.read_text())
            except Exception:
                pass

    # 2. All simfactory/etc/*.json — match current hostname
    _etc = root / "simfactory" / "etc"
    if _etc.is_dir():
        _hn = socket.gethostname()
        for _sf in sorted(_etc.glob("*.json")):
            try:
                _d = json.loads(_sf.read_text())
                if _hostname_matches_state(_hn, _d):
                    return _d
            except Exception:
                pass

    # 3. Legacy: cactus_root/externals/state.json
    p = root / "externals" / "state.json"
    if p.exists():
        try:
            return json.loads(p.read_text())
        except Exception:
            pass

    # 4. Glob sibling directories — state saved when CWD was different
    _hn = socket.gethostname()
    for _sp in sorted(root.parent.parent.glob("*/externals/state.json")):
        try:
            _d = json.loads(_sp.read_text())
            if _hostname_matches_state(_hn, _d):
                return _d
        except Exception:
            pass

    return {}


def _hostname_matches_state(hostname: str, state: dict) -> bool:
    """Return True if the state dict belongs to this machine.

    Checks in order:
      1. aliaspattern regex match (canonical)
      2. aliaspattern with one level less escaping (handles saved double-escaped patterns)
      3. name is a prefix of hostname (simple fallback for single-cluster setups)
    """
    pat = state.get("aliaspattern", "")
    name = state.get("name", "")
    if pat:
        try:
            if re.search(pat, hostname):
                return True
        except re.error:
            pass
        # Handle double-escaped patterns (e.g. \\d saved when user meant \d)
        pat2 = pat.replace("\\\\", "\\")
        if pat2 != pat:
            try:
                if re.search(pat2, hostname):
                    return True
            except re.error:
                pass
    # Simple prefix match: "mike" matches "mike1", "mike2", etc.
    if name and hostname.lower().startswith(name.lower()):
        return True
    return False


def _save_state(root: Path, state: dict) -> None:
    name = state.get("name")
    if name:
        d = root / "simfactory" / "etc"
        d.mkdir(parents=True, exist_ok=True)
        (d / f"{name}.json").write_text(json.dumps(state, indent=2) + "\n")
        # Remove legacy location on first successful migration
        _leg = root / "externals" / "state.json"
        if _leg.exists():
            try:
                _leg.unlink()
            except Exception:
                pass
    else:
        # Name not yet known — write to legacy location until name is set
        d = root / "externals"
        d.mkdir(exist_ok=True)
        (d / "state.json").write_text(json.dumps(state, indent=2) + "\n")


def write_externals_options(root: Path, comp) -> None:
    """Write options.cfg into the externals dir once; never overwrite so the user can edit."""
    p = _externals_dir(root) / "options.cfg"
    if p.exists():
        return
    p.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "# Compiler options used when building external libraries.",
        "# This file is written once and never overwritten — edit freely.",
        f"CC       = {comp.CC}",
        f"CXX      = {comp.CXX}",
        f"F90      = {comp.F90}",
        f"CPP      = {comp.CPP}",
        f"FPP      = {comp.FPP}",
        f"CFLAGS   = {comp.CFLAGS}",
        f"CXXFLAGS = {comp.CXXFLAGS}",
        f"F90FLAGS = {comp.F90FLAGS}",
    ]
    p.write_text("\n".join(lines) + "\n")
    print(f"  created: {p}")


def read_externals_options(root: Path) -> dict:
    """Parse options.cfg from the externals dir into a plain dict."""
    p = _externals_dir(root) / "options.cfg"
    opts: dict = {}
    if not p.exists():
        return opts
    for line in p.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if "=" in line:
            key, _, val = line.partition("=")
            opts[key.strip()] = val.strip()
    return opts


def build_external_zlib(cactus_root: Path, opts: dict, jobs: int = 1) -> Path:
    """Extract and build zlib into externals/; return the install prefix."""
    install_dir = (_externals_dir(cactus_root) / "install" / "zlib").resolve()
    if (install_dir / "lib" / "libz.a").exists():
        _lz = install_dir / "lib" / "libz.a"
        _nm_rc, _nm_out, _ = run_cmd("nm", str(_lz))
        if _nm_rc == 0 and "_intel_fast_memcpy" in _nm_out:
            print("  zlib: existing library has Intel symbols — rebuilding with gcc …")
            import shutil as _z_sh
            _z_sh.rmtree(str(install_dir / "lib"), ignore_errors=True)
        else:
            print("  zlib: already built, skipping.")
            return install_dir
    if _no_build:
        _build_would_build.add("zlib")
        return install_dir

    tarball = (cactus_root / "arrangements" / "ExternalLibraries"
               / "zlib" / "dist" / "zlib-1.2.8.tar.gz")
    if not tarball.exists():
        raise FileNotFoundError(f"zlib tarball not found: {tarball}")

    build_root = (_externals_dir(cactus_root) / "build" / "zlib").resolve()
    build_root.mkdir(parents=True, exist_ok=True)
    install_dir.mkdir(parents=True, exist_ok=True)

    log_path, log = _open_build_log(cactus_root, "zlib")
    print(f"  zlib: extracting {tarball.name} …  (log → {log_path.name})")
    with tarfile.open(tarball) as tf:
        _tar_extractall(tf, build_root)

    src_dir = build_root / "zlib-1.2.8"

    env = os.environ.copy()
    if "CC" in opts:
        env["CC"] = opts["CC"]
    if "CFLAGS" in opts:
        env["CFLAGS"] = opts["CFLAGS"]
    _zlib_cc = env.get("CC", "gcc")
    if Path(_zlib_cc).name in ("icc", "icx") and which("gcc"):
        env["CC"] = which("gcc")

    try:
        print("  zlib: configuring …")
        subprocess.run(
            ["./configure", f"--prefix={install_dir}", "--static"],
            cwd=src_dir, env=env, check=True,
            stdout=log, stderr=subprocess.STDOUT,
        )
        print("  zlib: building …")
        subprocess.run(["make", f"-j{jobs}"], cwd=src_dir, env=env, check=True,
                       stdout=log, stderr=subprocess.STDOUT)
        print("  zlib: installing …")
        subprocess.run(["make", f"-j{jobs}", "install"], cwd=src_dir, env=env, check=True,
                       stdout=log, stderr=subprocess.STDOUT)
    except subprocess.CalledProcessError:
        log.flush()
        _log_tail(log_path)
        raise
    finally:
        log.close()
    _write_build_cfg(install_dir, "zlib", env, configure_args)
    print(f"  zlib: installed to {install_dir}")
    return install_dir


def _fc_is_intel(fc_cmd: str) -> bool:
    """Return True if fc_cmd is (or wraps) an Intel Fortran compiler.

    MPICH's mpifort intercepts --version and prints MPICH's own version string,
    so we cannot rely on --version.  Instead we check the first token of
    'mpifort -show' (the underlying compiler binary) for ifort/ifx.
    """
    # Direct check first (works when fc_cmd IS ifort/ifx, not a wrapper)
    rc, out, _ = run_cmd(fc_cmd, "--version", timeout=10)
    if re.search(r"ifort|ifx|Intel.*Fortran", out, re.IGNORECASE):
        return True
    # MPI wrapper: 'mpifort -show' prints the actual compiler invocation
    rc2, show, _ = run_cmd(fc_cmd, "-show", timeout=10)
    if rc2 == 0 and show.strip():
        underlying = os.path.basename(show.split()[0])
        return bool(re.search(r"ifort|ifx", underlying, re.IGNORECASE))
    return False


def _intel_mpifort_fclibs(mpifort_cmd: str) -> str:
    """Return clean link flags from 'mpifort -show', filtering invalid -L paths.

    ifort's verbose (-v) output can contain bogus entries like '-L/usr/lib64/lib'
    that break HDF5's autoconf AC_FC_LIBRARY_LDFLAGS detection.  The '-show'
    output is the actual compiler invocation line and contains only valid flags;
    we filter out any -L whose directory does not exist.
    """
    rc, out, _ = run_cmd(mpifort_cmd, "-show", timeout=15)
    if rc != 0 or not out.strip():
        return ""
    tokens = []
    for tok in out.split():
        if tok.startswith("-l"):
            tokens.append(tok)
        elif tok.startswith("-L"):
            d = tok[2:]
            if d and Path(d).is_dir():
                tokens.append(tok)
    return " ".join(tokens)


def _gcc_gfortran_fclibs(gfortran_cmd: str) -> str:
    """Return ac_cv_fc_libs flags derived from bare gfortran's install location.

    Uses --print-file-name to locate libgfortran and libquadmath in the
    GCC installation directory.  These paths are always correct (the module
    system sets FC to the right gfortran); using mpifort -v instead can
    return /home/packages/... symlink paths that don't exist on every node.
    """
    dirs: set = set()
    for libname in ("libgfortran.a", "libgfortran.so"):
        rc, out, _ = run_cmd(gfortran_cmd, f"--print-file-name={libname}", timeout=10)
        if rc == 0:
            p = out.strip()
            if p and p != libname:   # returned a real path, not just the name
                d = str(Path(p).parent)
                if Path(d).is_dir():
                    dirs.add(d)
    if not dirs:
        return ""
    ldirs = " ".join(f"-L{d}" for d in sorted(dirs))
    return f"{ldirs} -lgfortran"


def _mpicc_link_flags(mpicc_cmd: str) -> Tuple[str, str]:
    """Return (lib_flags, libdir_flags) parsed from `mpicc -show`.

    Extracts -l and -L tokens so callers can append MPI libraries to LIBS /
    LDFLAGS.  Invalid -L paths (directory does not exist) are silently dropped.
    Returns ("", "") when the command fails.
    """
    rc, out, _ = run_cmd(mpicc_cmd, "-show", timeout=15)
    if rc != 0 or not out.strip():
        return "", ""
    libs, ldirs = [], []
    for tok in out.split():
        if tok.startswith("-l"):
            libs.append(tok)
        elif tok.startswith("-L"):
            d = tok[2:]
            if d and Path(d).is_dir():
                ldirs.append(tok)
    return " ".join(libs), " ".join(ldirs)


def _hdf5_is_parallel(prefix: str) -> bool:
    """Return True if the HDF5 at prefix was built with MPI parallel support.

    Strategy (most-reliable first):
    1. nm on libhdf5.a (static archive) — symbol presence is authoritative.
    2. nm -D on libhdf5.so (exported dynamic symbols) — authoritative for
       shared-only installs (e.g. Spack).  H5pubconf.h can lie when the Spack
       spec was configured for parallel but the .so was actually built serial;
       the nm check catches that.
    3. H5pubconf.h header check — only used when no library is present
       (unlikely in practice).
    """
    _nm = which("nm") or "nm"
    lib_dir = Path(prefix) / "lib"

    # Static archive — nm reads all object symbols directly.
    static_lib = lib_dir / "libhdf5.a"
    if static_lib.exists():
        rc, out, _ = run_cmd(_nm, str(static_lib), timeout=30)
        if rc == 0:
            return "H5Pset_fapl_mpio" in out

    # Shared library — use -D to restrict to exported (dynamic) symbols only.
    shared_lib = lib_dir / "libhdf5.so"
    if shared_lib.exists():
        rc, out, _ = run_cmd(_nm, "-D", str(shared_lib), timeout=30)
        if rc == 0:
            return "H5Pset_fapl_mpio" in out

    # No library found: fall back to header (least reliable — headers can be
    # copied from a parallel build into a serial install directory).
    inc = Path(prefix) / "include"
    for name in ("H5pubconf.h", "H5pubconf-64.h", "H5pubconf-32.h"):
        f = inc / name
        if f.exists():
            try:
                return "#define H5_HAVE_PARALLEL 1" in f.read_text()
            except OSError:
                pass
    return False


def build_external_hdf5(cactus_root: Path, opts: dict,
                         mpi_found: bool = False, jobs: int = 1) -> Path:
    """Extract and build HDF5 into externals/; return the install prefix.

    When mpi_found is True the build uses MPI wrappers (mpicc/mpifort) and
    enables the parallel file-system layer so that HDF5 is compatible with
    openPMD and parallel I/O thorns.
    """
    import shutil as _shutil

    install_dir = (_externals_dir(cactus_root) / "install" / "hdf5").resolve()
    if (install_dir / "lib" / "libhdf5.a").exists():
        already_parallel = _hdf5_is_parallel(str(install_dir))
        if mpi_found == already_parallel:
            # Rebuild if library was compiled with Intel — Intel runtime symbols
            # (_intel_fast_memcpy etc.) cause link failures in downstream GCC builds.
            if _has_intel_symbols(install_dir / "lib"):
                print("  HDF5: existing library has Intel symbols — rebuilding with gcc …")
                _shutil.rmtree(install_dir, ignore_errors=True)
            # Rebuild if Fortran bindings are missing — a previous run may have
            # used --enable-fortran=no, leaving libhdf5_fortran.a absent.
            elif mpi_found and not (install_dir / "lib" / "libhdf5_fortran.a").exists():
                print("  HDF5: Fortran bindings missing — rebuilding with --enable-fortran=yes …")
                _shutil.rmtree(install_dir, ignore_errors=True)
            # Also rebuild if library was built with OpenMPI but we're now
            # using an MPICH-family MPI — the two have incompatible ABIs.
            elif _has_openmpi_symbols(install_dir / "lib"):
                _cur_mpicc = which("mpicc") or ""
                _rc_show, _show_out, _ = run_cmd(_cur_mpicc, "--showme:compile") if _cur_mpicc else (1, "", "")
                _cur_is_openmpi = (_rc_show == 0 and bool(_show_out.strip()))
                if not _cur_is_openmpi:
                    print("  HDF5: existing lib has OpenMPI symbols but current MPI is MPICH/MVAPICH2 — rebuilding …")
                    _shutil.rmtree(install_dir, ignore_errors=True)
                else:
                    print("  HDF5: already built, skipping.")
                    return install_dir
            else:
                print("  HDF5: already built, skipping.")
                return install_dir
        else:
            # Parallel/serial mismatch — rebuild to match current MPI state.
            kind = "parallel" if mpi_found else "serial"
            print(f"  HDF5: rebuilding as {kind} (MPI state changed) …")
            _shutil.rmtree(install_dir, ignore_errors=True)
    if _no_build:
        _build_would_build.add("hdf5")
        return install_dir

    tarball = (cactus_root / "arrangements" / "ExternalLibraries"
               / "HDF5" / "dist" / "hdf5-1.12.0.tar.gz")
    if not tarball.exists():
        raise FileNotFoundError(f"HDF5 tarball not found: {tarball}")

    build_root = (_externals_dir(cactus_root) / "build" / "hdf5").resolve()
    # Remove stale build tree to avoid configure contamination after a rebuild.
    _shutil.rmtree(build_root, ignore_errors=True)
    build_root.mkdir(parents=True, exist_ok=True)
    install_dir.mkdir(parents=True, exist_ok=True)

    log_path, log = _open_build_log(cactus_root, "hdf5")
    print(f"  HDF5: extracting {tarball.name} …  (log → {log_path.name})")
    with tarfile.open(tarball) as tf:
        _tar_extractall(tf, build_root)

    src_dir = build_root / "hdf5-1.12.0"

    env = os.environ.copy()

    if mpi_found:
        mpicc   = which("mpicc")   or "mpicc"
        mpifort = which("mpifort") or which("mpif90") or ""
        env["CC"] = mpicc
        if "CFLAGS" in opts:
            env["CFLAGS"] = opts["CFLAGS"]
        if mpifort:
            env["FC"] = mpifort
        # Pre-populate ac_cv_fc_libs from bare gfortran so that autoconf's
        # AC_FC_LIBRARY_LDFLAGS uses correct /usr/local/packages/... paths
        # rather than running mpifort -v (which reports /home/packages/...
        # paths that may not exist on all nodes and cause the "link Fortran
        # from C" test to fail).  FC=mpifort is kept for the parallel MPI-IO
        # Fortran link test, which needs the MPI include/lib paths.
        # Find the underlying gfortran: mpifort -show prints the real compiler
        # as its first token; fall back to $FC from env or which("gfortran").
        _gfc = ""
        if mpifort:
            _rc_sh, _sh, _ = run_cmd(mpifort, "-show", timeout=10)
            if _rc_sh == 0 and _sh.strip():
                _tok = _sh.split()[0]
                if "gfortran" in os.path.basename(_tok).lower():
                    _gfc = which(_tok) or _tok  # resolve relative name to abs path
        if not _gfc:
            _gfc = which("gfortran") or ""
        if _gfc:
            _fclibs = _gcc_gfortran_fclibs(_gfc)
            if _fclibs:
                env["ac_cv_fc_libs"] = _fclibs
                print(f"  HDF5: presetting ac_cv_fc_libs from {os.path.basename(_gfc)}"
                      f" to bypass mpifort -v path issue")
        fortran_args  = ["--enable-fortran=yes", "--enable-fortran2003=yes"]
        parallel_args = ["--enable-parallel"]
    else:
        for key, env_key in [("CC", "CC"), ("CFLAGS", "CFLAGS")]:
            if key in opts:
                env[env_key] = opts[key]
        # Switch Intel CC to gcc — Intel-compiled HDF5 embeds undefined Intel
        # runtime refs that GCC-based downstream link tests (Silo, ADIOS2) fail.
        _h5_cc = env.get("CC", "gcc")
        if Path(_h5_cc).name in ("icc", "icx") and which("gcc"):
            env["CC"] = which("gcc")
        fc = opts.get("F90", "")
        if fc and fc.strip().upper() not in ("NONE", "NO_BUILD"):
            if Path(fc).name in ("ifort", "ifx") and which("gfortran"):
                fc = which("gfortran")
            env["FC"] = fc
            if "F90FLAGS" in opts:
                env["FCFLAGS"] = opts["F90FLAGS"]
            fortran_args = ["--enable-fortran=yes", "--enable-fortran2003=yes"]
        else:
            fortran_args = ["--enable-fortran=no"]
        parallel_args = []

    configure_args = [
        "./configure",
        f"--prefix={install_dir}",
        "--enable-tests=no",
        "--enable-tools=no",   # skip h5dump/h5ls etc.; Cactus only needs the .a libs
        "--disable-shared",
        "--enable-cxx=no",   # C++ HDF5 does not support parallel I/O
    ] + fortran_args + parallel_args

    # Use our externals zlib if already built.
    zlib_externals = (_externals_dir(cactus_root) / "install" / "zlib").resolve()
    if (zlib_externals / "lib" / "libz.a").exists():
        configure_args.append(f"--with-zlib={zlib_externals}")

    kind_str = "parallel" if mpi_found else "serial"
    try:
        print(f"  HDF5: configuring ({kind_str}) …")
        subprocess.run(configure_args, cwd=src_dir, env=env, check=True,
                       stdout=log, stderr=subprocess.STDOUT)
        print("  HDF5: building …")
        subprocess.run(["make", f"-j{jobs}"], cwd=src_dir, env=env, check=True,
                       stdout=log, stderr=subprocess.STDOUT)
        print("  HDF5: installing …")
        subprocess.run(["make", f"-j{jobs}", "install"], cwd=src_dir, env=env, check=True,
                       stdout=log, stderr=subprocess.STDOUT)
    except subprocess.CalledProcessError:
        log.flush()
        _log_tail(log_path)
        raise
    finally:
        log.close()
    _write_build_cfg(install_dir, "hdf5", env, configure_args)
    print(f"  HDF5: installed to {install_dir}")
    return install_dir


_BUNDLED_CMAKE_VERSION = (3, 23, 2)


def _cmake_system_version(cmake_exe: str) -> Optional[Tuple[int, ...]]:
    """Return the version tuple of cmake_exe, or None on failure."""
    try:
        r = subprocess.run([cmake_exe, "--version"], stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                           timeout=10)
        out = r.stdout.decode("utf-8", errors="replace")
        m = re.match(r"cmake version (\d+)\.(\d+)\.(\d+)", out)
        if m:
            return tuple(int(x) for x in m.groups())
    except Exception:
        pass
    return None


def build_external_cmake(cactus_root: Path, jobs: int = 1) -> Path:
    install_dir = (_externals_dir(cactus_root) / "install" / "cmake").resolve()
    if (install_dir / "bin" / "cmake").exists():
        print("  CMake: already built, skipping.")
        return install_dir
    if _no_build:
        _build_would_build.add("cmake")
        return install_dir

    name = f"cmake-{'.'.join(str(v) for v in _BUNDLED_CMAKE_VERSION)}"
    tarball = (cactus_root / "arrangements" / "ExternalLibraries"
               / "CMake" / "dist" / f"{name}.tar")
    if not tarball.exists():
        raise FileNotFoundError(f"CMake tarball not found: {tarball}")

    build_root = (_externals_dir(cactus_root) / "build" / "cmake").resolve()
    build_root.mkdir(parents=True, exist_ok=True)
    install_dir.mkdir(parents=True, exist_ok=True)

    log_path, log = _open_build_log(cactus_root, "cmake")
    print(f"  CMake: extracting {tarball.name} …  (log → {log_path.name})")
    with tarfile.open(tarball) as tf:
        _tar_extractall(tf, build_root)

    src_dir = build_root / name
    # cmake bootstraps itself; always use system gcc/g++ to avoid cross-compiler issues
    env = os.environ.copy()
    env["CC"]       = "gcc"
    env["CXX"]      = "g++"
    env["CFLAGS"]   = "-O2"
    env["CXXFLAGS"] = "-O2"
    env.pop("LIBS", None)

    try:
        print("  CMake: configuring …")
        subprocess.run(["./configure", f"--prefix={install_dir}"],
                       cwd=src_dir, env=env, check=True,
                       stdout=log, stderr=subprocess.STDOUT)
        print("  CMake: building …")
        subprocess.run(["make", f"-j{jobs}"], cwd=src_dir, env=env, check=True,
                       stdout=log, stderr=subprocess.STDOUT)
        print("  CMake: installing …")
        subprocess.run(["make", f"-j{jobs}", "install"], cwd=src_dir, env=env, check=True,
                       stdout=log, stderr=subprocess.STDOUT)
    except subprocess.CalledProcessError:
        log.flush()
        _log_tail(log_path)
        raise
    finally:
        log.close()
    _write_build_cfg(install_dir, "cmake", env,
                     ["./configure", f"--prefix={install_dir}"])
    print(f"  CMake: installed to {install_dir}")
    return install_dir


def detect_cmake(args, state: dict, cactus_root: Path) -> Tuple[bool, str, Optional[Path]]:
    """Detect or build cmake.  Returns (found, cfg_str, cmake_bin_dir_or_None)."""
    if getattr(args, "without_cmake", False) or state.get("with_cmake") is False:
        return False, "CMAKE_DIR = BUILD", None

    install_dir = (_externals_dir(cactus_root) / "install" / "cmake").resolve()

    if not getattr(args, "with_cmake", False):
        # Check for already-built externals cmake first.
        ext_cmake = install_dir / "bin" / "cmake"
        if ext_cmake.exists():
            ver = _cmake_system_version(str(ext_cmake))
            if ver and ver >= _BUNDLED_CMAKE_VERSION:
                bin_dir = install_dir / "bin"
                cfg = (f"CMAKE_DIR         = {install_dir}\n"
                       f"CMAKE_INSTALL_DIR = {install_dir}")
                return True, cfg, bin_dir

        # Check system cmake.
        sys_cmake = which("cmake")
        if sys_cmake:
            ver = _cmake_system_version(sys_cmake)
            if ver and ver >= _BUNDLED_CMAKE_VERSION:
                sys_dir = Path(sys_cmake).parent.parent  # strip bin/cmake
                cfg = f"CMAKE_DIR = {sys_dir}"
                return True, cfg, None  # system cmake already in PATH

    # Missing or too old — pre-build the bundled version.
    build_external_cmake(cactus_root, jobs=getattr(args, "jobs", 1) or 1)
    bin_dir = install_dir / "bin"
    cfg = (f"CMAKE_DIR         = {install_dir}\n"
           f"CMAKE_INSTALL_DIR = {install_dir}")
    return True, cfg, bin_dir


def _find_hdf5_dirs(cactus_root: Path) -> Tuple[str, str]:
    """Return (inc_dir, lib_dir) for HDF5 or raise if not found."""
    ext = (_externals_dir(cactus_root) / "install" / "hdf5").resolve()
    if (ext / "lib" / "libhdf5.a").exists():
        return str(ext / "include"), str(ext / "lib")

    d = env_dir(
        "CRAY_HDF5_PARALLEL_PREFIX_DIR", "CRAY_HDF5_DIR",
        "TACC_PHDF5_DIR", "TACC_HDF5_DIR",
        "HDF5_DIR", "HDF5_HOME", "HDF5_ROOT",
    )
    if d:
        return f"{d}/include", f"{d}/lib"

    for h5cc in ("h5pcc", "h5cc"):
        if which(h5cc):
            rc, show, _ = run_cmd(h5cc, "--show")
            if rc == 0 and show.strip():
                incs  = _parse_flags(show, "-I")
                ldirs = _parse_flags(show, "-L")
                if incs and ldirs:
                    return incs[0], ldirs[0]

    raise RuntimeError(
        "Silo requires HDF5 but none was found. "
        "Use --with-hdf5 to pre-build it, or set HDF5_DIR."
    )


def build_external_silo(cactus_root: Path, opts: dict, jobs: int = 1) -> Path:
    install_dir = (_externals_dir(cactus_root) / "install" / "silo").resolve()
    _silo_a = install_dir / "lib" / "libsiloh5.a"
    if _silo_a.exists():
        # If Silo was built with Intel icc/icpx its objects have Intel runtime
        # symbols (undefined references to _intel_fast_memcpy etc.) that won't
        # resolve when the application links with GCC.  Delete and rebuild.
        _nm_rc, _nm_out, _ = run_cmd("nm", str(_silo_a))
        if _nm_rc == 0 and ("_intel_fast_memset" in _nm_out
                            or "_intel_fast_memcpy" in _nm_out):
            print("  Silo: existing library has Intel symbols — "
                  "rebuilding with g++ …")
            import shutil as _silo_shutil
            _silo_shutil.rmtree(str(install_dir / "lib"), ignore_errors=True)
        elif _has_openmpi_symbols(install_dir / "lib"):
            # Check whether the current mpicc is also OpenMPI.  Use --version
            # output rather than --showme:compile: the latter can return exit-0
            # with empty output on some builds, making it an unreliable signal.
            _cur_mpicc = which("mpicc") or ""
            _rc_ver, _ver_out, _ = (run_cmd(_cur_mpicc, "--version", timeout=10)
                                    if _cur_mpicc else (1, "", ""))
            _cur_is_openmpi = (_rc_ver == 0
                               and "open mpi" in (_ver_out or "").lower())
            if not _cur_is_openmpi:
                print("  Silo: existing library has OpenMPI symbols — "
                      "rebuilding for MPICH/MVAPICH2 …")
                import shutil as _silo_shutil
                _silo_shutil.rmtree(str(install_dir / "lib"), ignore_errors=True)
            else:
                print("  Silo: already built, skipping.")
                return install_dir
        else:
            print("  Silo: already built, skipping.")
            return install_dir
    if _no_build:
        _build_would_build.add("silo")
        return install_dir

    # Silo requires HDF5.  Pre-build it automatically if it is not already
    # available (either from externals or from the environment).
    _hdf5_ext = (_externals_dir(cactus_root) / "install" / "hdf5").resolve()
    if not (_hdf5_ext / "lib" / "libhdf5.a").exists():
        try:
            _find_hdf5_dirs(cactus_root)   # raises if no system HDF5 either
        except RuntimeError:
            print("  Silo: HDF5 not found — pre-building HDF5 first …")
            build_external_hdf5(cactus_root, opts,
                                mpi_found=bool(which("mpicc")), jobs=jobs)

    name = "silo-4.11.1"
    tarball = (cactus_root / "arrangements" / "ExternalLibraries"
               / "Silo" / "dist" / f"{name}.tar")
    if not tarball.exists():
        raise FileNotFoundError(f"Silo tarball not found: {tarball}")

    dist_dir = tarball.parent
    # Patches must be applied in this exact order (see build.sh comments).
    patches = [
        dist_dir / "gcc_v_fix.patch",
        dist_dir / "config_site.patch",
        dist_dir / "permission_bits.patch",
        dist_dir / "patchtest.patch",
    ]

    build_root = (_externals_dir(cactus_root) / "build" / "silo").resolve()
    build_root.mkdir(parents=True, exist_ok=True)
    install_dir.mkdir(parents=True, exist_ok=True)

    # Remove any leftover source/build tree so old config.cache or .o files
    # (potentially compiled with a different compiler) don't persist.
    import shutil as _silo_shutil2
    _src_pre = build_root / name
    if _src_pre.exists():
        _silo_shutil2.rmtree(str(_src_pre))

    log_path, log = _open_build_log(cactus_root, "silo")
    print(f"  Silo: extracting {tarball.name} …  (log → {log_path.name})")
    with tarfile.open(tarball) as tf:
        _tar_extractall(tf, build_root)

    src_dir = build_root / name

    try:
        print("  Silo: applying patches …")
        patchtest_applied = False
        for patch in patches:
            if not patch.exists():
                print(f"  Silo: patch not found, skipping: {patch.name}")
                continue
            subprocess.run(["patch", "-p1", "-i", str(patch)], cwd=src_dir, check=True,
                           stdout=log, stderr=subprocess.STDOUT)
            if patch.name == "patchtest.patch":
                patchtest_applied = True
        patch_tmp = src_dir / ".patch_tmp"
        if patchtest_applied and not patch_tmp.exists():
            raise RuntimeError("Silo: patchtest.patch failed — patch command is too old")
        if patch_tmp.exists():
            patch_tmp.unlink()

        hdf5_inc_dir, hdf5_lib_dir = _find_hdf5_dirs(cactus_root)
        hdf5_prefix   = str(Path(hdf5_inc_dir).parent)
        hdf5_parallel = _hdf5_is_parallel(hdf5_prefix)

        env = os.environ.copy()
        for key, env_key in [("CC", "CC"), ("CXX", "CXX"),
                              ("CFLAGS", "CFLAGS"), ("CXXFLAGS", "CXXFLAGS")]:
            if key in opts:
                env[env_key] = opts[key]

        # Intel icc/icx/icpc/icpx introduces Intel runtime symbols
        # (_intel_fast_memset etc.) that won't link with GCC.  Force both CC
        # and CXX to GCC-family compilers for Silo's objects.
        _silo_cc = env.get("CC", "gcc")
        if Path(_silo_cc).name in ("icc", "icx") and which("gcc"):
            env["CC"] = which("gcc")
        _silo_cxx = env.get("CXX", "g++")
        if Path(_silo_cxx).name in ("icpc", "icpx") and which("g++"):
            env["CXX"] = which("g++")

        # Parallel HDF5 carries MPI symbols.  Using mpicc as the compiler
        # makes the linker resolve them automatically during configure's
        # H5open detection test — without it the test links fail even though
        # the library is present.
        mpicc_cmd = None
        if hdf5_parallel:
            mpicc_cmd = which("mpicc") or "mpicc"
            env["CC"] = mpicc_cmd

        # HDF5 1.12 changed H5Oget_info API; force old behaviour.
        env["CPPFLAGS"] = (
            env.get("CPPFLAGS", "")
            + f" -DH5Oget_info_vers=1 -DH5O_info_t_vers=1 -I{hdf5_inc_dir}"
        ).strip()

        # Silo uses HDF5's C API only — do NOT include the Fortran wrapper
        # libs (hdf5_fortran, hdf5hl_fortran) here.  Those require the Fortran
        # runtime (-lifcoremt, -lgfortran …) which the Silo configure link
        # tests don't provide, causing spurious "H5open not found" failures.
        # HDF5's plugin interface (H5PLint.c) uses dlopen/dlclose → needs -ldl.
        env["LIBS"]    = "-lhdf5_hl -lhdf5 -ldl"
        env["LDFLAGS"] = (env.get("LDFLAGS", "") + f" -L{hdf5_lib_dir}").strip()

        # Locate zlib so that Silo's configure can find it.  HDF5 was built
        # against zlib, so the H5open link test fails if zlib is not also
        # available.  We probe in order: externals → env-var prefix → pkg-config
        # → common system paths.  The result is passed as --with-zlib=INC,LIB
        # and also added to LIBS/LDFLAGS so the standalone -lz check passes.
        zlib_inc_dir = zlib_lib_dir = None
        _zlib_ext = (_externals_dir(cactus_root) / "install" / "zlib").resolve()
        _zlib_a = _zlib_ext / "lib" / "libz.a"
        if _zlib_a.exists():
            # Guard against an externals zlib compiled with a different toolchain
            # (e.g. Intel icc) that the current GCC-based link cannot resolve.
            _nm_rc, _nm_out, _ = run_cmd("nm", str(_zlib_a))
            _intel_zlib = _nm_rc == 0 and "_intel_fast_memcpy" in _nm_out
            if not _intel_zlib:
                zlib_inc_dir = str(_zlib_ext / "include")
                zlib_lib_dir = str(_zlib_ext / "lib")
        else:
            _zpfx = env_dir("ZLIB_HOME", "ZLIB_DIR", "ZLIB_ROOT")
            if _zpfx and (Path(_zpfx) / "include" / "zlib.h").exists():
                zlib_inc_dir = f"{_zpfx}/include"
                zlib_lib_dir = (f"{_zpfx}/lib64"
                                if (Path(_zpfx, "lib64", "libz.a").exists() or
                                    Path(_zpfx, "lib64", "libz.so").exists())
                                else f"{_zpfx}/lib")
            else:
                # Try pkg-config then common system paths.  Accept .so as well
                # as .a — many clusters only ship the shared zlib.
                _zcandidate = None
                if which("pkg-config"):
                    _rc, _out, _ = run_cmd("pkg-config", "--variable=libdir", "zlib")
                    if _rc == 0 and _out.strip():
                        _zcandidate = Path(_out.strip()) / "libz.so"
                        if not _zcandidate.exists():
                            _zcandidate = Path(_out.strip()) / "libz.a"
                        if not _zcandidate.exists():
                            _zcandidate = None
                if _zcandidate is None:
                    for _sd in ("/usr/lib64", "/usr/lib/x86_64-linux-gnu",
                                "/usr/lib/aarch64-linux-gnu", "/usr/lib"):
                        if Path(_sd, "libz.a").exists():
                            _zcandidate = Path(_sd, "libz.a")
                            break
                        if Path(_sd, "libz.so").exists():
                            _zcandidate = Path(_sd, "libz.so")
                            break
                if _zcandidate is not None:
                    _zpfx2 = _zlib_prefix_from_lib(_zcandidate)
                    if _zpfx2 and (_zpfx2 / "include" / "zlib.h").exists():
                        zlib_inc_dir = str(_zpfx2 / "include")
                        zlib_lib_dir = str(_zcandidate.parent)

        if zlib_lib_dir:
            env["LIBS"]    += " -lz"
            env["LDFLAGS"] += f" -L{zlib_lib_dir}"
        else:
            # No explicit path found but HDF5 always needs zlib; let the system
            # linker find it via its default search path.
            env["LIBS"] += " -lz"

        # When HDF5 is parallel, its static archive contains MPI object files.
        # libtool's final link for Silo tools (silock, etc.) uses a raw -lhdf5
        # and therefore needs the MPI libraries appended explicitly — mpicc as
        # CC is not enough because libtool may generate a raw ld invocation.
        if hdf5_parallel and mpicc_cmd:
            mpi_libs, mpi_ldirs = _mpicc_link_flags(mpicc_cmd)
            if mpi_libs:
                env["LIBS"] += " " + mpi_libs
                print(f"  Silo: parallel HDF5 — appending MPI libs: {mpi_libs}")
            if mpi_ldirs:
                env["LDFLAGS"] = (env["LDFLAGS"] + " " + mpi_ldirs).strip()

        env.pop("RPATH", None)
        env.pop("CPP",   None)

        # Silo's configure must run from a build/ subdirectory.
        build_dir = src_dir / "build"
        build_dir.mkdir(exist_ok=True)

        configure_args = [
            "../configure",
            f"--prefix={install_dir}",
            f"--libdir={install_dir}/lib",
            f"--with-hdf5={hdf5_inc_dir},{hdf5_lib_dir}",
            (f"--with-zlib={zlib_inc_dir},{zlib_lib_dir}"
             if zlib_inc_dir else "--with-zlib=yes"),
            "--disable-zfp",
            "--disable-fortran",
            "--disable-browser",   # skip browser tool — avoids MPI linker issues
            "--enable-optimization",
        ]

        print("  Silo: configuring …")
        subprocess.run(configure_args, cwd=build_dir, env=env, check=True,
                       stdout=log, stderr=subprocess.STDOUT)

        # Build and install only the library (src/ subdirectory).
        # The tools/ directory (silock, browser) links silock against libsiloh5
        # and libhdf5 — when HDF5 is parallel, libtool unwraps mpicc to gcc and
        # the MPI symbols in libhdf5.a become unresolved.  Cactus needs only
        # libsiloh5.a and silo.h; building src/ is sufficient.
        src_build_dir = build_dir / "src"
        print("  Silo: building …")
        subprocess.run(["make", f"-j{jobs}"], cwd=src_build_dir, env=env, check=True,
                       stdout=log, stderr=subprocess.STDOUT)
        print("  Silo: installing …")
        subprocess.run(["make", "install"], cwd=src_build_dir, env=env, check=True,
                       stdout=log, stderr=subprocess.STDOUT)
    except subprocess.CalledProcessError:
        log.flush()
        _log_tail(log_path)
        raise
    finally:
        log.close()
    _write_build_cfg(install_dir, "silo", env, configure_args)
    print(f"  Silo: installed to {install_dir}")
    return install_dir


def detect_silo(args, state: dict, cactus_root: Path) -> Tuple[bool, str]:
    if getattr(args, "without_silo", False) or state.get("with_silo") is False:
        return False, "SILO_DIR = BUILD"

    default_libs = "siloh5"

    if not getattr(args, "with_silo", False):
        d = env_dir("SILO_DIR", "SILO_HOME", "SILO_ROOT")
        if d:
            return True, _lib_lines("SILO", d, f"{d}/include", f"{d}/lib", default_libs)

        pc = pkg_prefix("silo")
        if pc:
            return True, _lib_lines("SILO", pc, f"{pc}/include", f"{pc}/lib", default_libs)

        if Path("/usr/include/silo.h").exists():
            return True, f"SILO_LIBS = {default_libs}"

    # No system Silo found (or --with-silo forces externals): pre-build it.
    opts = read_externals_options(cactus_root)
    install_dir = build_external_silo(
        cactus_root, opts, jobs=getattr(args, "jobs", 1) or 1
    )
    return True, (
        f"SILO_DIR         = {install_dir}\n"
        f"SILO_INSTALL_DIR = {install_dir}\n"
        f"SILO_INC_DIRS    = {install_dir}/include {install_dir}/lib\n"
        f"SILO_LIB_DIRS    = {install_dir}/lib\n"
        f"SILO_LIBS        = {default_libs}"
    )


_HW_SIMD_TO_NSIMD = {
    "SSE2":    "SSE2",
    "AVX":     "AVX",
    "AVX2":    "AVX2",
    "AVX512F": "AVX512_SKYLAKE",
    "NEON":    "AARCH64",
    "SVE":     "SVE",
    "VSX":     "VSX",
    "NONE":    "CPU",
}


def build_external_nsimd(cactus_root: Path, opts: dict,
                          nsimd_simd: str, jobs: int = 1) -> Path:
    install_dir = (_externals_dir(cactus_root) / "install" / "nsimd").resolve()
    # NSIMD 3.0.1 cmake builds a SHARED library (libnsimd_AVX2.so), not .a.
    # Use glob so we match .so, .so.X, .a, or whatever the platform produces.
    _nsimd_existing = list((install_dir / "lib").glob(f"libnsimd_{nsimd_simd}.*"))
    if _nsimd_existing:
        if _has_intel_runtime_libs(install_dir / "lib"):
            print("  NSIMD: existing library links Intel runtime — rebuilding with g++ …")
            for _p in _nsimd_existing:
                try:
                    _p.unlink()
                except Exception:
                    pass
        else:
            print("  NSIMD: already built, skipping.")
            return install_dir
    if _no_build:
        _build_would_build.add("nsimd")
        return install_dir

    name    = "nsimd-3.0.1"
    thorn   = cactus_root / "arrangements" / "ExternalLibraries" / "NSIMD"
    tarball = thorn / "dist" / f"{name}.tar"
    if not tarball.exists():
        raise FileNotFoundError(f"NSIMD tarball not found: {tarball}")

    dist_dir = tarball.parent
    patches  = [
        dist_dir / "version.patch",
        dist_dir / "sleef_zip.patch",
        dist_dir / "patchtest.patch",
    ]

    build_root = (_externals_dir(cactus_root) / "build" / "nsimd").resolve()
    build_root.mkdir(parents=True, exist_ok=True)
    install_dir.mkdir(parents=True, exist_ok=True)

    # Remove old source tree to avoid stale CMake cache from previous Intel build.
    import shutil as _nsimd_sh
    _src_pre = build_root / name
    if _src_pre.exists():
        _nsimd_sh.rmtree(str(_src_pre))

    log_path, log = _open_build_log(cactus_root, "nsimd")
    print(f"  NSIMD: extracting {tarball.name} …  (log → {log_path.name})")
    with tarfile.open(tarball) as tf:
        _tar_extractall(tf, build_root)

    src_dir = build_root / name

    env = os.environ.copy()
    cxx = opts.get("CXX", env.get("CXX", "g++"))
    _cxx_base = Path(cxx).name if cxx not in ("", "NO_BUILD", "BUILD") else ""
    if _cxx_base in ("icpc", "icpx") and which("g++"):
        print(f"  NSIMD: switching CXX from {_cxx_base} to g++ to avoid Intel runtime deps …")
        cxx = which("g++")
    # SRCDIR must point to the thorn's src/ so cmake can find sleef.zip via $SRCDIR/../dist/
    env["SRCDIR"] = str(thorn / "src")
    env.pop("LIBS", None)

    build_dir = src_dir / "build"
    build_dir.mkdir(exist_ok=True)

    # Use cmake from externals if we built it; otherwise rely on PATH.
    cmake_ext = (_externals_dir(cactus_root) / "install" / "cmake" / "bin" / "cmake").resolve()
    cmake_exe = str(cmake_ext) if cmake_ext.exists() else "cmake"

    cmake_args = [
        cmake_exe,
        "-DCMAKE_BUILD_TYPE=RelWithDebInfo",
        f"-DCMAKE_CXX_COMPILER={cxx}",
        f"-Dsimd={nsimd_simd}",
        f"-DCMAKE_INSTALL_PREFIX={install_dir}",
        "-DCMAKE_INSTALL_LIBDIR=lib",
        "..",
    ]

    try:
        print("  NSIMD: applying patches …")
        patchtest_applied = False
        for patch in patches:
            if not patch.exists():
                print(f"  NSIMD: patch not found, skipping: {patch.name}")
                continue
            subprocess.run(["patch", "-p1", "-i", str(patch)], cwd=src_dir, check=True,
                           stdout=log, stderr=subprocess.STDOUT)
            if patch.name == "patchtest.patch":
                patchtest_applied = True
        patch_tmp = src_dir / ".patch_tmp"
        if patchtest_applied and not patch_tmp.exists():
            raise RuntimeError("NSIMD: patchtest.patch failed — patch command is too old")
        if patch_tmp.exists():
            patch_tmp.unlink()

        print(f"  NSIMD: configuring (simd={nsimd_simd}) …")
        subprocess.run(cmake_args, cwd=build_dir, env=env, check=True,
                       stdout=log, stderr=subprocess.STDOUT)
        print("  NSIMD: building …")
        subprocess.run(["make", f"-j{jobs}"], cwd=build_dir, env=env, check=True,
                       stdout=log, stderr=subprocess.STDOUT)
        print("  NSIMD: installing …")
        subprocess.run(["make", f"-j{jobs}", "install"], cwd=build_dir, env=env, check=True,
                       stdout=log, stderr=subprocess.STDOUT)
    except subprocess.CalledProcessError:
        log.flush()
        _log_tail(log_path)
        raise
    finally:
        log.close()
    _write_build_cfg(install_dir, "nsimd", env, cmake_args)
    print(f"  NSIMD: installed to {install_dir}")
    return install_dir


def detect_nsimd(args, state: dict, cactus_root: Path,
                 nsimd_simd: str) -> Tuple[bool, str]:
    if getattr(args, "without_nsimd", False) or state.get("with_nsimd") is False:
        return False, "NSIMD_DIR = BUILD"

    if not getattr(args, "with_nsimd", False):
        d = env_dir("NSIMD_DIR", "NSIMD_HOME", "NSIMD_ROOT")
        if d:
            lib = f"nsimd_{nsimd_simd}"
            return True, (
                f"NSIMD_DIR      = {d}\n"
                f"NSIMD_INC_DIRS = {d}/include {d}/lib\n"
                f"NSIMD_LIB_DIRS = {d}/lib\n"
                f"NSIMD_LIBS     = {lib}\n"
                f"NSIMD_SIMD     = {nsimd_simd}"
            )

        ext = (_externals_dir(cactus_root) / "install" / "nsimd").resolve()
        if list((ext / "lib").glob(f"libnsimd_{nsimd_simd}.*")):
            if _has_intel_runtime_libs(ext / "lib"):
                print("  NSIMD: existing library links Intel runtime — triggering rebuild …")
                import shutil as _ns_det_sh
                for _p in list((ext / "lib").glob(f"libnsimd_{nsimd_simd}.*")):
                    try:
                        _p.unlink()
                    except Exception:
                        pass
            else:
                lib = f"nsimd_{nsimd_simd}"
                return True, (
                    f"NSIMD_DIR         = {ext}\n"
                    f"NSIMD_INSTALL_DIR = {ext}\n"
                    f"NSIMD_INC_DIRS    = {ext}/include {ext}/lib\n"
                    f"NSIMD_LIB_DIRS    = {ext}/lib\n"
                    f"NSIMD_LIBS        = {lib}\n"
                    f"NSIMD_SIMD        = {nsimd_simd}"
                )

    # Pre-build from the bundled tarball.
    opts        = read_externals_options(cactus_root)
    install_dir = build_external_nsimd(
        cactus_root, opts, nsimd_simd, jobs=getattr(args, "jobs", 1) or 1
    )
    lib = f"nsimd_{nsimd_simd}"
    return True, (
        f"NSIMD_DIR         = {install_dir}\n"
        f"NSIMD_INSTALL_DIR = {install_dir}\n"
        f"NSIMD_INC_DIRS    = {install_dir}/include {install_dir}/lib\n"
        f"NSIMD_LIB_DIRS    = {install_dir}/lib\n"
        f"NSIMD_LIBS        = {lib}\n"
        f"NSIMD_SIMD        = {nsimd_simd}"
    )


# ---------------------------------------------------------------------------
# ADIOS2
# ---------------------------------------------------------------------------

def _adios2_libs(mpi_found: bool, sst: bool = True) -> str:
    libs: List[str] = []
    if mpi_found:
        libs += ["adios2_cxx11_mpi", "adios2_c_mpi", "adios2_core_mpi"]
    libs += ["adios2_cxx11", "adios2_c", "adios2_core"]
    if sst:
        libs += ["adios2_evpath", "adios2_atl", "adios2_enet", "adios2_ffs", "adios2_dill"]
    return " ".join(libs)


def build_external_adios2(cactus_root: Path, opts: dict,
                           mpi_found: bool, jobs: int = 1) -> Path:
    install_dir = (_externals_dir(cactus_root) / "install" / "adios2").resolve()
    if (install_dir / "lib" / "libadios2_core.a").exists():
        if _has_intel_symbols(install_dir / "lib"):
            print("  ADIOS2: Intel symbols found — rebuilding with gcc/g++ …")
            import shutil as _ad_sh; _ad_sh.rmtree(str(install_dir / "lib"), ignore_errors=True)
        else:
            print("  ADIOS2: already built, skipping.")
            return install_dir
    if _no_build:
        _build_would_build.add("adios2")
        return install_dir

    name    = "ADIOS2-2.10.2"
    thorn   = cactus_root / "arrangements" / "ExternalLibraries" / "ADIOS2"
    tarball = thorn / "dist" / f"{name}.tar"
    if not tarball.exists():
        raise FileNotFoundError(f"ADIOS2 tarball not found: {tarball}")

    dist_dir = tarball.parent
    patches  = [
        dist_dir / "stdint.patch",
        dist_dir / "ent-no-docs.patch",
        dist_dir / "patchtest.patch",
    ]

    build_root = (_externals_dir(cactus_root) / "build" / "adios2").resolve()
    build_root.mkdir(parents=True, exist_ok=True)
    install_dir.mkdir(parents=True, exist_ok=True)

    import shutil as _ad_sh2
    _ad_src_pre = build_root / name
    if _ad_src_pre.exists():
        _ad_sh2.rmtree(str(_ad_src_pre))

    log_path, log = _open_build_log(cactus_root, "adios2")
    print(f"  ADIOS2: extracting {tarball.name} …  (log → {log_path.name})")
    with tarfile.open(tarball) as tf:
        _tar_extractall(tf, build_root)

    src_dir = build_root / name

    env = os.environ.copy()
    env.pop("LIBS", None)

    cmake_ext = (_externals_dir(cactus_root) / "install" / "cmake" / "bin" / "cmake").resolve()
    cmake_exe = str(cmake_ext) if cmake_ext.exists() else "cmake"

    cc  = opts.get("CC",  env.get("CC",  "gcc"))
    cxx = opts.get("CXX", env.get("CXX", "g++"))
    # Force GCC-compatible compilers to avoid Intel runtime symbols
    if Path(cc).name in ("icc", "icx") and which("gcc"):
        cc = which("gcc")
    if Path(cxx).name in ("icpc", "icpx") and which("g++"):
        cxx = which("g++")

    build_dir = src_dir / "build"
    build_dir.mkdir(exist_ok=True)

    cmake_args = [
        cmake_exe,
        f"-DCMAKE_C_COMPILER={cc}",
        f"-DCMAKE_CXX_COMPILER={cxx}",
        "-DCMAKE_BUILD_TYPE=Release",
        f"-DCMAKE_INSTALL_PREFIX={install_dir}",
        "-DCMAKE_INSTALL_LIBDIR=lib",
        f"-DADIOS2_USE_MPI={'ON' if mpi_found else 'OFF'}",
        "-DADIOS2_USE_HDF5=OFF",
        "-DADIOS2_USE_Fortran=OFF",
        "-DADIOS2_USE_Python=OFF",
        "-DADIOS2_USE_ZeroMQ=OFF",
        "-DADIOS2_USE_PNG=OFF",
        "-DADIOS2_USE_BZip2=OFF",
        "-DADIOS2_USE_SST=ON",
        "-DADIOS2_USE_BP5=ON",
        "-DADIOS2_USE_CUDA=OFF",
        "-DADIOS2_USE_Campaign=OFF",
        "-DBUILD_TESTING=OFF",
        "-DADIOS2_BUILD_EXAMPLES=OFF",
        "-DBUILD_SHARED_LIBS=OFF",
        # libopen-pal.a (static OpenMPI) calls dlopen/dlclose. cmake 3.23's
        # FindMPI strips 'dl' from MPI_LIBRARIES as an implicit system lib,
        # but with static libs the implicit assumption breaks. Adding -ldl to
        # CMAKE_EXE_LINKER_FLAGS ensures cmake's MPI test programs also get it.
        "-DCMAKE_EXE_LINKER_FLAGS=-ldl",
        "..",
    ]
    # Pass MPI compiler hints and pre-populate the per-library cache variable
    # MPI_mpi_LIBRARY so cmake's find_library never runs for libmpi.
    #
    # Root cause: externals OpenMPI is built --enable-shared=no (static only).
    # cmake's find_library prefers .so on Linux; it doesn't find libmpi.so in
    # the externals dir, falls through to LD_LIBRARY_PATH, and picks up a
    # system libmpi.so (here: Intel-compiled MPICH).  Linking OpenMPI's static
    # libmpi_cxx.a against Intel-compiled MPICH's libmpi.so then fails with
    # "undefined reference to _intel_fast_memset".
    #
    # MPI_C/CXX_LIBRARIES are result variables overwritten by FindMPI; the
    # per-library cache variable MPI_mpi_LIBRARY IS respected as user input.
    if mpi_found:
        _mpicc_w  = which("mpicc")  or which("mpiicc")
        _mpicxx_w = which("mpicxx") or which("mpiicpc") or which("mpiCC") or which("mpic++")
        if _mpicc_w:
            _mpi_lib_a = Path(_mpicc_w).parent.parent / "lib" / "libmpi.a"
            cmake_args.insert(-1, f"-DMPI_C_COMPILER={_mpicc_w}")
            if _mpi_lib_a.exists():
                cmake_args.insert(-1, f"-DMPI_mpi_LIBRARY:FILEPATH={_mpi_lib_a}")
        if _mpicxx_w:
            cmake_args.insert(-1, f"-DMPI_CXX_COMPILER={_mpicxx_w}")

    try:
        print("  ADIOS2: applying patches …")
        patchtest_applied = False
        for patch in patches:
            if not patch.exists():
                print(f"  ADIOS2: patch not found, skipping: {patch.name}")
                continue
            subprocess.run(["patch", "-p1", "-i", str(patch)], cwd=src_dir, check=True,
                           stdout=log, stderr=subprocess.STDOUT)
            if patch.name == "patchtest.patch":
                patchtest_applied = True
        patch_tmp = src_dir / ".patch_tmp"
        if patchtest_applied and not patch_tmp.exists():
            raise RuntimeError("ADIOS2: patchtest.patch failed — patch command is too old")
        if patch_tmp.exists():
            patch_tmp.unlink()

        print(f"  ADIOS2: configuring (MPI={'on' if mpi_found else 'off'}) …")
        subprocess.run(cmake_args, cwd=build_dir, env=env, check=True,
                       stdout=log, stderr=subprocess.STDOUT)
        print("  ADIOS2: building …")
        subprocess.run(["make", f"-j{jobs}"], cwd=build_dir, env=env, check=True,
                       stdout=log, stderr=subprocess.STDOUT)
        print("  ADIOS2: installing …")
        subprocess.run(["make", f"-j{jobs}", "install"], cwd=build_dir, env=env, check=True,
                       stdout=log, stderr=subprocess.STDOUT)
    except subprocess.CalledProcessError:
        log.flush()
        _log_tail(log_path)
        raise
    finally:
        log.close()
    _write_build_cfg(install_dir, "adios2", env, cmake_args)
    print(f"  ADIOS2: installed to {install_dir}")
    return install_dir


def detect_adios2(args, state: dict, cactus_root: Path,
                  mpi_found: bool) -> Tuple[bool, str, Optional[str]]:
    """Detect or build ADIOS2.  Returns (found, cfg_str, adios2_dir_or_None)."""
    if getattr(args, "without_adios2", False) or state.get("with_adios2") is False:
        return False, "ADIOS2_DIR = BUILD", None

    if not getattr(args, "with_adios2", False):
        d = env_dir("ADIOS2_DIR", "ADIOS2_HOME", "ADIOS2_ROOT")
        if d:
            libs = _adios2_libs(mpi_found)
            return True, (
                f"ADIOS2_DIR      = {d}\n"
                f"ADIOS2_INC_DIRS = {d}/include {d}/lib\n"
                f"ADIOS2_LIB_DIRS = {d}/lib\n"
                f"ADIOS2_LIBS     = {libs}"
            ), d

        ext = (_externals_dir(cactus_root) / "install" / "adios2").resolve()
        if (ext / "lib" / "libadios2_core.a").exists():
            if _has_intel_symbols(ext / "lib"):
                print("  ADIOS2: Intel symbols found — rebuilding with gcc/g++ …")
                import shutil as _ad2_sh; _ad2_sh.rmtree(str(ext / "lib"), ignore_errors=True)
            else:
                libs = _adios2_libs(mpi_found)
                return True, (
                    f"ADIOS2_DIR         = {ext}\n"
                    f"ADIOS2_INSTALL_DIR = {ext}\n"
                    f"ADIOS2_INC_DIRS    = {ext}/include {ext}/lib\n"
                    f"ADIOS2_LIB_DIRS    = {ext}/lib\n"
                    f"ADIOS2_LIBS        = {libs}"
                ), str(ext)

    install_dir = build_external_adios2(
        cactus_root, read_externals_options(cactus_root), mpi_found,
        jobs=getattr(args, "jobs", 1) or 1,
    )
    libs = _adios2_libs(mpi_found)
    return True, (
        f"ADIOS2_DIR         = {install_dir}\n"
        f"ADIOS2_INSTALL_DIR = {install_dir}\n"
        f"ADIOS2_INC_DIRS    = {install_dir}/include {install_dir}/lib\n"
        f"ADIOS2_LIB_DIRS    = {install_dir}/lib\n"
        f"ADIOS2_LIBS        = {libs}"
    ), str(install_dir)


# ---------------------------------------------------------------------------
# openPMD
# ---------------------------------------------------------------------------

def build_external_openpmd(cactus_root: Path, opts: dict,
                            adios2_dir: Optional[str],
                            hdf5_root: Optional[str],
                            mpi_found: bool, jobs: int = 1) -> Path:
    install_dir = (_externals_dir(cactus_root) / "install" / "openpmd").resolve()
    if (install_dir / "lib" / "libopenPMD.a").exists():
        if _has_intel_symbols(install_dir / "lib"):
            print("  openPMD: Intel symbols found — rebuilding with gcc/g++ …")
            import shutil as _op_sh; _op_sh.rmtree(str(install_dir / "lib"), ignore_errors=True)
        else:
            print("  openPMD: already built, skipping.")
            return install_dir
    if _no_build:
        _build_would_build.add("openpmd")
        return install_dir

    name      = "openPMD-api-0.16.1"
    json_name = "json-3.12.0"
    toml_name = "toml11-4.2.0"
    thorn     = cactus_root / "arrangements" / "ExternalLibraries" / "openPMD"
    tarball   = thorn / "dist" / f"{name}.tar"
    json_tar  = thorn / "dist" / f"{json_name}.tar"
    toml_tar  = thorn / "dist" / f"{toml_name}.tar"
    for tb in (tarball, json_tar, toml_tar):
        if not tb.exists():
            raise FileNotFoundError(f"openPMD tarball not found: {tb}")

    patches = [thorn / "dist" / "patchtest.patch"]

    build_root = (_externals_dir(cactus_root) / "build" / "openpmd").resolve()
    build_root.mkdir(parents=True, exist_ok=True)
    install_dir.mkdir(parents=True, exist_ok=True)

    import shutil as _op_sh2
    _op_src_pre = build_root / name
    if _op_src_pre.exists():
        _op_sh2.rmtree(str(_op_src_pre))

    log_path, log = _open_build_log(cactus_root, "openpmd")
    print(f"  openPMD: extracting archives …  (log → {log_path.name})")
    for tb in (tarball, json_tar, toml_tar):
        with tarfile.open(tb) as tf:
            _tar_extractall(tf, build_root)

    src_dir = build_root / name

    env = os.environ.copy()
    env.pop("LIBS", None)

    cmake_ext = (_externals_dir(cactus_root) / "install" / "cmake" / "bin" / "cmake").resolve()
    cmake_exe = str(cmake_ext) if cmake_ext.exists() else "cmake"

    cxx = opts.get("CXX", env.get("CXX", "g++"))
    # Force GCC-compatible C++ to avoid Intel runtime symbols
    if Path(cxx).name in ("icpc", "icpx") and which("g++"):
        cxx = which("g++")

    build_dir = src_dir / "build"
    build_dir.mkdir(exist_ok=True)

    use_adios2 = "ON" if adios2_dir else "OFF"
    use_hdf5   = "ON" if hdf5_root else "OFF"

    cmake_args = [
        cmake_exe,
        f"-DCMAKE_CXX_COMPILER={cxx}",
        "-DCMAKE_BUILD_TYPE=Release",
        f"-DCMAKE_INSTALL_PREFIX={install_dir}",
        "-DCMAKE_INSTALL_LIBDIR=lib",
        "-DCMAKE_CXX_STANDARD=14",
        f"-DopenPMD_USE_ADIOS2={use_adios2}",
        f"-DopenPMD_USE_HDF5={use_hdf5}",
        f"-DopenPMD_USE_MPI={'ON' if mpi_found else 'OFF'}",
        "-DopenPMD_USE_PYTHON=OFF",
        "-DopenPMD_BUILD_TESTING=OFF",
        "-DopenPMD_BUILD_EXAMPLES=OFF",
        "-DBUILD_CLI_TOOLS=OFF",
        "-DBUILD_TESTING=OFF",
        "-DBUILD_SHARED_LIBS=OFF",
        "-DFETCHCONTENT_FULLY_DISCONNECTED=ON",
        f"-DopenPMD_json_src={build_root / json_name}",
        f"-DopenPMD_toml11_src={build_root / toml_name}",
        "..",
    ]

    if adios2_dir:
        cmake_args.insert(-1, f"-DADIOS2_ROOT={adios2_dir}")
    if hdf5_root:
        cmake_args.insert(-1, f"-DHDF5_ROOT={hdf5_root}")
    if mpi_found:
        _mpicc_w2  = which("mpicc")  or which("mpiicc")
        _mpicxx_w2 = which("mpicxx") or which("mpiicpc") or which("mpiCC") or which("mpic++")
        if _mpicc_w2:
            _mpi_lib_a2 = Path(_mpicc_w2).parent.parent / "lib" / "libmpi.a"
            cmake_args.insert(-1, f"-DMPI_C_COMPILER={_mpicc_w2}")
            if _mpi_lib_a2.exists():
                cmake_args.insert(-1, f"-DMPI_mpi_LIBRARY:FILEPATH={_mpi_lib_a2}")
        if _mpicxx_w2:
            cmake_args.insert(-1, f"-DMPI_CXX_COMPILER={_mpicxx_w2}")

    try:
        print("  openPMD: applying patches …")
        patchtest_applied = False
        for patch in patches:
            if not patch.exists():
                print(f"  openPMD: patch not found, skipping: {patch.name}")
                continue
            subprocess.run(["patch", "-p1", "-i", str(patch)], cwd=src_dir, check=True,
                           stdout=log, stderr=subprocess.STDOUT)
            if patch.name == "patchtest.patch":
                patchtest_applied = True
        patch_tmp = src_dir / ".patch_tmp"
        if patchtest_applied and not patch_tmp.exists():
            raise RuntimeError("openPMD: patchtest.patch failed — patch command is too old")
        if patch_tmp.exists():
            patch_tmp.unlink()

        print(f"  openPMD: configuring (ADIOS2={use_adios2}, HDF5={use_hdf5}) …")
        subprocess.run(cmake_args, cwd=build_dir, env=env, check=True,
                       stdout=log, stderr=subprocess.STDOUT)
        print("  openPMD: building …")
        subprocess.run(["make", f"-j{jobs}"], cwd=build_dir, env=env, check=True,
                       stdout=log, stderr=subprocess.STDOUT)
        print("  openPMD: installing …")
        subprocess.run(["make", f"-j{jobs}", "install"], cwd=build_dir, env=env, check=True,
                       stdout=log, stderr=subprocess.STDOUT)
    except subprocess.CalledProcessError:
        log.flush()
        _log_tail(log_path)
        raise
    finally:
        log.close()
    _write_build_cfg(install_dir, "openpmd", env, cmake_args)
    print(f"  openPMD: installed to {install_dir}")
    return install_dir


def detect_openpmd(args, state: dict, cactus_root: Path,
                   mpi_found: bool,
                   adios2_dir: Optional[str],
                   hdf5_root: Optional[str]) -> Tuple[bool, str]:
    if getattr(args, "without_openpmd", False) or state.get("with_openpmd") is False:
        return False, "OPENPMD_DIR = BUILD"

    if not getattr(args, "with_openpmd", False):
        d = env_dir("OPENPMD_DIR", "OPENPMD_HOME", "OPENPMD_ROOT")
        if d:
            return True, (
                f"OPENPMD_DIR      = {d}\n"
                f"OPENPMD_INC_DIRS = {d}/lib {d}/include\n"
                f"OPENPMD_LIB_DIRS = {d}/lib\n"
                f"OPENPMD_LIBS     = openPMD"
            )

        ext = (_externals_dir(cactus_root) / "install" / "openpmd").resolve()
        if (ext / "lib" / "libopenPMD.a").exists():
            if _has_intel_symbols(ext / "lib"):
                print("  openPMD: Intel symbols found — rebuilding with gcc/g++ …")
                import shutil as _op2_sh; _op2_sh.rmtree(str(ext / "lib"), ignore_errors=True)
            else:
                return True, (
                    f"OPENPMD_DIR         = {ext}\n"
                    f"OPENPMD_INSTALL_DIR = {ext}\n"
                    f"OPENPMD_INC_DIRS    = {ext}/lib {ext}/include\n"
                    f"OPENPMD_LIB_DIRS    = {ext}/lib\n"
                    f"OPENPMD_LIBS        = openPMD"
                )

    install_dir = build_external_openpmd(
        cactus_root, read_externals_options(cactus_root),
        adios2_dir, hdf5_root, mpi_found,
        jobs=getattr(args, "jobs", 1) or 1,
    )
    return True, (
        f"OPENPMD_DIR         = {install_dir}\n"
        f"OPENPMD_INSTALL_DIR = {install_dir}\n"
        f"OPENPMD_INC_DIRS    = {install_dir}/lib {install_dir}/include\n"
        f"OPENPMD_LIB_DIRS    = {install_dir}/lib\n"
        f"OPENPMD_LIBS        = openPMD"
    )


# ---------------------------------------------------------------------------
# AMReX
# ---------------------------------------------------------------------------

def build_external_amrex(cactus_root: Path, opts: dict,
                          mpi_found: bool,
                          gpu_found: bool,
                          sm_arch: Optional[str],
                          amd_arch: Optional[str],
                          jobs: int = 1) -> Path:
    install_dir = (_externals_dir(cactus_root) / "install" / "amrex").resolve()
    if (install_dir / "lib" / "libamrex.a").exists():
        print("  AMReX: already built, skipping.")
        return install_dir
    if _no_build:
        _build_would_build.add("amrex")
        return install_dir

    name    = "amrex-25.11"
    thorn   = cactus_root / "arrangements" / "ExternalLibraries" / "AMReX"
    tarball = thorn / "dist" / f"{name}.tar"
    if not tarball.exists():
        raise FileNotFoundError(f"AMReX tarball not found: {tarball}")

    build_root = (_externals_dir(cactus_root) / "build" / "amrex").resolve()
    build_root.mkdir(parents=True, exist_ok=True)
    install_dir.mkdir(parents=True, exist_ok=True)

    # Wipe stale source tree so cmake never picks up a stale CMakeCache.txt
    # from a previous (possibly different-compiler) configure run.
    import shutil as _amrex_sh
    _amrex_src_pre = build_root / name
    if _amrex_src_pre.exists():
        _amrex_sh.rmtree(str(_amrex_src_pre))

    log_path, log = _open_build_log(cactus_root, "amrex")
    print(f"  AMReX: extracting {tarball.name} …  (log → {log_path.name})")
    with tarfile.open(tarball) as tf:
        _tar_extractall(tf, build_root)

    src_dir   = build_root / name
    build_dir = src_dir / "build"
    build_dir.mkdir(exist_ok=True)

    env = os.environ.copy()
    env.pop("LIBS", None)

    cmake_ext = (_externals_dir(cactus_root) / "install" / "cmake" / "bin" / "cmake").resolve()
    cmake_exe = str(cmake_ext) if cmake_ext.exists() else "cmake"

    cxx = opts.get("CXX", env.get("CXX", "g++"))
    cc  = opts.get("CC",  env.get("CC",  "gcc"))

    if mpi_found:
        # Use MPI compiler wrappers as cmake's compilers so that AMReX's own
        # try_compile checks (MPI feature probes, etc.) find MPI headers and
        # libs without extra -I/-L plumbing.  This matches the approach in the
        # AMReX thorn's own build.sh.
        cmake_cc  = which("mpicc")  or "mpicc"
        cmake_cxx = which("mpicxx") or which("mpiCC") or "mpicxx"
    else:
        cmake_cc  = cc
        cmake_cxx = cxx

    cmake_args = [
        cmake_exe,
        f"-DCMAKE_C_COMPILER={cmake_cc}",
        f"-DCMAKE_CXX_COMPILER={cmake_cxx}",
        "-DCMAKE_BUILD_TYPE=Release",
        f"-DCMAKE_INSTALL_PREFIX={install_dir}",
        "-DCMAKE_INSTALL_LIBDIR=lib",
        f"-DAMReX_MPI={'ON' if mpi_found else 'OFF'}",
        "-DAMReX_OMP=ON",
        "-DAMReX_PARTICLES=ON",
        "-DAMReX_ASSERTIONS=ON",
        "-DAMReX_FORTRAN=OFF",
        "-DBUILD_SHARED_LIBS=OFF",
        "-DAMReX_BUILD_TESTS=OFF",
    ]

    # GPU backend
    if gpu_found and sm_arch and not amd_arch:
        # CUDA path
        cuda_arches = _sm_to_cuda_arches(sm_arch)
        nvcc_path   = which("nvcc") or "nvcc"
        cmake_args += [
            "-DAMReX_GPU_BACKEND=CUDA",
            "-DAMReX_GPU_RDC=ON",
            "-DAMReX_CUDA_ERROR_CAPTURE_THIS=ON",
            "-DAMReX_CUDA_ERROR_CROSS_EXECUTION_SPACE_CALL=ON",
            f"-DCMAKE_CUDA_COMPILER={nvcc_path}",
            "-DCMAKE_CUDA_COMPILER_FORCED=ON",
            "-DCMAKE_CUDA_COMPILE_FEATURES=cuda_std_17",
            f"-DCMAKE_CUDA_ARCHITECTURES={cuda_arches}",
        ]
    elif amd_arch:
        cmake_args += [
            "-DAMReX_GPU_BACKEND=HIP",
            f"-DAMReX_AMD_ARCH={amd_arch}",
            f"-DCMAKE_CXX_COMPILER={cxx}",
        ]
    else:
        cmake_args.append("-DAMReX_GPU_BACKEND=NONE")

    cmake_args.append("..")

    gpu_desc = (f"CUDA={_sm_to_cuda_arches(sm_arch)}" if (gpu_found and sm_arch and not amd_arch)
                else (f"HIP={amd_arch}" if amd_arch else "CPU"))

    try:
        print(f"  AMReX: configuring (MPI={'on' if mpi_found else 'off'}, GPU={gpu_desc}) …")
        subprocess.run(cmake_args, cwd=build_dir, env=env, check=True,
                       stdout=log, stderr=subprocess.STDOUT)
        print("  AMReX: building …")
        subprocess.run(["make", f"-j{jobs}"], cwd=build_dir, env=env, check=True,
                       stdout=log, stderr=subprocess.STDOUT)
        print("  AMReX: installing …")
        subprocess.run(["make", f"-j{jobs}", "install"], cwd=build_dir, env=env, check=True,
                       stdout=log, stderr=subprocess.STDOUT)
    except subprocess.CalledProcessError:
        log.flush()
        _log_tail(log_path)
        raise
    finally:
        log.close()
    _write_build_cfg(install_dir, "amrex", env, cmake_args)
    print(f"  AMReX: installed to {install_dir}")
    return install_dir


def detect_amrex(args, state: dict, cactus_root: Path,
                 mpi_found: bool, gpu_found: bool,
                 sm_arch: Optional[str],
                 amd_arch: Optional[str]) -> Tuple[bool, str]:
    """Detect or pre-build AMReX.  Returns (found, cfg_str).

    Checks env vars and pre-built externals first.  If nothing is found,
    pre-builds from the bundled tarball automatically (same as --with-amrex).
    Pass --without-amrex to delegate to Cactus instead.
    """
    if getattr(args, "without_amrex", False) or state.get("with_amrex") is False:
        return False, "AMREX_DIR = BUILD"

    cuda_arches = _sm_to_cuda_arches(sm_arch) if (gpu_found and sm_arch and not amd_arch) else "OFF"
    enable_cuda = "yes" if (gpu_found and not amd_arch) else "no"
    enable_hip  = "yes" if amd_arch else "no"

    def _amrex_cfg(d: Path) -> str:
        lines = [
            f"AMREX_DIR                      = {d}",
            f"AMREX_INSTALL_DIR              = {d}",
            f"AMREX_INC_DIRS                 = {d}/include {d}/lib",
            f"AMREX_LIB_DIRS                 = {d}/lib",
            f"AMREX_LIBS                     = amrex",
            f"AMREX_ENABLE_FORTRAN           = OFF",
            f"AMREX_ENABLE_HIP               = {enable_hip}",
        ]
        if amd_arch:
            lines.append(f"AMREX_AMD_ARCH                 = {amd_arch}")
        lines.append(f"AMREX_CMAKE_CUDA_ARCHITECTURES = {cuda_arches}")
        return "\n".join(lines)

    if not getattr(args, "with_amrex", False):
        d = env_dir("AMREX_DIR", "AMREX_HOME", "AMREX_ROOT")
        if d:
            return True, _amrex_cfg(Path(d))

        ext = (_externals_dir(cactus_root) / "install" / "amrex").resolve()
        if (ext / "lib" / "libamrex.a").exists():
            return True, _amrex_cfg(ext)

        # Nothing found: fall through to pre-build below.

    install_dir = build_external_amrex(
        cactus_root, read_externals_options(cactus_root),
        mpi_found, gpu_found, sm_arch, amd_arch,
        jobs=getattr(args, "jobs", 1) or 1,
    )
    return True, _amrex_cfg(install_dir)


# ---------------------------------------------------------------------------
# Plan mode
# ---------------------------------------------------------------------------

def show_plan(args, state: dict, cactus_root: Path) -> None:
    """Print which packages will be built, already built, found on system, or skipped.

    Calls the real detect_* functions with _no_build=True so build_external_*
    functions record *would-build* intent without executing anything.
    """
    global _no_build, _build_would_build

    # Don't mutate the caller's state dict.
    state = dict(state)
    if state.get("with_openpmd") and not state.get("with_adios2"):
        state["with_adios2"] = True
    if state.get("with_silo") and not state.get("with_hdf5"):
        state["with_hdf5"] = True
    if state.get("with_hdf5") and not state.get("with_zlib"):
        state["with_zlib"] = True
    if state.get("with_amrex") and not state.get("with_cmake"):
        state["with_cmake"] = True

    _no_build = True
    _build_would_build.clear()

    simd       = _detect_simd()
    nsimd_simd = _HW_SIMD_TO_NSIMD.get(simd, "CPU")
    ext_root   = (_externals_dir(cactus_root) / "install").resolve()

    # Detect compilers and MPI up-front so we can print the compiler summary
    # and reuse the MPI result for the package table.
    comp = detect_compilers()
    mpi  = detect_mpi(args, state, cactus_root, sched=detect_scheduler(args.queue or ""))
    if mpi.found and mpi.cc and mpi.cc != comp.CC:
        comp = _compilers_from_mpi(mpi, comp)

    _BUNDLE_VERS = {
        "cmake":   ".".join(str(x) for x in _BUNDLED_CMAKE_VERSION),
        "zlib":    "1.2.8",
        "hdf5":    "1.12.0",
        "silo":    "4.11.1",
        "nsimd":   f"3.0.1  (SIMD={nsimd_simd})",
        "fftw3":   "3.3.10",
        "mpi":     "openmpi 4.0.6",
        "adios2":  "2.10.2",
        "openpmd": "0.16.1",
        "amrex":   "25.11",
        "lapack":   "3.12.0",
        "hwloc":    "2.0.4",
        "yaml_cpp": "0.6.3",
        "boost":    "1.84.0",
    }

    SENTINELS = {
        "cmake":   Path("cmake/bin/cmake"),
        "zlib":    Path("zlib/lib/libz.a"),
        "hdf5":    Path("hdf5/lib/libhdf5.a"),
        "silo":    Path("silo/lib/libsiloh5.a"),
        "nsimd":   Path(f"nsimd/lib/libnsimd_{nsimd_simd}.so"),
        "fftw3":   Path("fftw3/lib/libfftw3.a"),
        "mpi":     Path("mpi/bin/mpicc"),
        "adios2":  Path("adios2/lib/libadios2_core.a"),
        "openpmd": Path("openpmd/lib/libopenPMD.a"),
        "amrex":   Path("amrex/lib/libamrex.a"),
        "lapack":   Path("lapack/lib/liblapack.a"),
        "hwloc":    Path("hwloc/lib/libhwloc.a"),
        "yaml_cpp": Path("yaml_cpp/lib/libyaml-cpp.a"),
        "boost":    Path("boost/lib/libboost_filesystem.a"),
    }

    WILL_BUILD = "WILL BUILD  externals/"
    BUILT      = "already built"
    SYSTEM     = "system"
    SKIP       = "skip (Cactus BUILD)"

    def _classify(pkg: str, found: bool) -> str:
        if pkg in _build_would_build:
            return WILL_BUILD
        if not found:
            return SKIP
        if (ext_root / SENTINELS[pkg]).exists():
            return BUILT
        return SYSTEM

    def _cfg_detail(cfg: str) -> str:
        """Extract first useful path/value from a detect cfg block."""
        for line in cfg.splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "= BUILD" in line:
                continue
            key, _, val = line.partition("=")
            if "_LIBS" in key:
                continue
            val = val.strip().split()[0] if val.strip() else ""
            if val:
                return val
        return ""

    rows: List[Tuple[str, str, str]] = []

    def add(pkg: str, found: bool, detail_fn):
        action = _classify(pkg, found)
        if action == WILL_BUILD:
            detail = f"bundled {_BUNDLE_VERS[pkg]}"
        elif action == BUILT:
            detail = f"externals/install/{pkg}"
        elif action == SYSTEM:
            detail = detail_fn() or "system paths"
        else:  # SKIP
            detail = ""
        rows.append((pkg, action, detail))

    # cmake — 3-tuple return
    cmake_found, cmake_cfg, _ = detect_cmake(args, state, cactus_root)
    add("cmake", cmake_found, lambda: _cfg_detail(cmake_cfg))

    # zlib
    zlib_found, zlib_cfg = detect_zlib(args, state, cactus_root)
    add("zlib", zlib_found, lambda: _cfg_detail(zlib_cfg))

    # hdf5
    hdf5_found, hdf5_cfg, _ = detect_hdf5(args, state, cactus_root, mpi_found=mpi.found)
    add("hdf5", hdf5_found, lambda: _cfg_detail(hdf5_cfg))

    # silo
    silo_found, silo_cfg = detect_silo(args, state, cactus_root)
    add("silo", silo_found, lambda: _cfg_detail(silo_cfg))

    # nsimd
    nsimd_found, nsimd_cfg = detect_nsimd(args, state, cactus_root, nsimd_simd)
    add("nsimd", nsimd_found, lambda: _cfg_detail(nsimd_cfg))

    # fftw3
    fftw3_found, fftw3_cfg = detect_fftw3(args, state, cactus_root)
    add("fftw3", fftw3_found, lambda: _cfg_detail(fftw3_cfg))

    # hwloc
    hwloc_found, hwloc_cfg = detect_hwloc(args, state, cactus_root, mpi)
    add("hwloc", hwloc_found, lambda: _cfg_detail(hwloc_cfg))

    # yaml_cpp
    yaml_cpp_found, yaml_cpp_cfg = detect_yaml_cpp(args, state, cactus_root)
    add("yaml_cpp", yaml_cpp_found, lambda: _cfg_detail(yaml_cpp_cfg))

    # boost
    boost_found, boost_cfg = detect_boost(args, state, cactus_root)
    add("boost", boost_found, lambda: _cfg_detail(boost_cfg))

    # mpi — reuse the result already captured above
    mpi_detail = (f"{mpi.kind}  via {which('mpicc') or 'mpicc'}" if mpi.found
                  else "Cactus MPI thorn")
    action = _classify("mpi", mpi.found)
    if action == WILL_BUILD:
        detail = f"bundled {_BUNDLE_VERS['mpi']}"
    elif action == BUILT:
        detail = "externals/install/mpi"
    else:
        detail = mpi_detail if mpi.found else ""
    rows.append(("mpi", action, detail))

    # adios2
    adios2_found, adios2_cfg, _plan_adios2_dir = detect_adios2(
        args, state, cactus_root, mpi.found
    )
    add("adios2", adios2_found, lambda: _cfg_detail(adios2_cfg))

    # openpmd — pass adios2 dir; only pass hdf5 root if it has parallel support
    _plan_hdf5_root: Optional[str] = None
    if mpi.found and hdf5_found:
        _ext_hdf5 = ext_root / "hdf5"
        if (_ext_hdf5 / "lib" / "libhdf5.a").exists() and _hdf5_is_parallel(str(_ext_hdf5)):
            _plan_hdf5_root = str(_ext_hdf5)
    openpmd_found, openpmd_cfg = detect_openpmd(
        args, state, cactus_root, mpi.found, _plan_adios2_dir, _plan_hdf5_root
    )
    add("openpmd", openpmd_found, lambda: _cfg_detail(openpmd_cfg))

    # amrex — detect GPU/AMD arch for plan display
    _plan_gpu   = detect_gpu()
    _plan_amd   = _detect_amd_arch()
    _plan_sma   = _plan_gpu.sm_arch if _plan_gpu.found else None
    amrex_found, amrex_cfg = detect_amrex(
        args, state, cactus_root,
        mpi_found=mpi.found,
        gpu_found=_plan_gpu.found,
        sm_arch=_plan_sma,
        amd_arch=_plan_amd,
    )
    add("amrex", amrex_found, lambda: _cfg_detail(amrex_cfg))

    # lapack
    lapack_found, lapack_cfg = detect_lapack(args, state, cactus_root)
    add("lapack", lapack_found, lambda: _cfg_detail(lapack_cfg))

    _no_build = False

    # --- Print compiler summary ---
    cc_src = "MPI wrapper" if (mpi.found and mpi.cc) else "detected"
    print(f"\nCompilers  (kind={comp.kind},  source={cc_src})")
    print(f"  CC  = {comp.CC}")
    print(f"  CXX = {comp.CXX}")
    print(f"  F90 = {comp.F90}")
    jobs = getattr(args, "jobs", 1) or 1
    print(f"\nParallel build jobs  (-j): {jobs}")

    # --- Print package table ---
    print(f"\nBuild plan  (host SIMD={simd})\n")
    col_w = (12, 22, 0)
    header = f"  {'Package':<{col_w[0]}}  {'Action':<{col_w[1]}}  Details"
    print(header)
    print("  " + "-" * (len(header) - 2))
    for pkg, action, detail in rows:
        print(f"  {pkg:<{col_w[0]}}  {action:<{col_w[1]}}  {detail}")
    print()


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main():
    ap = argparse.ArgumentParser(
        description="Probe the environment and generate SimFactory config files.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    ap.add_argument("--name",
                    help="Machine nickname — required on first run; remembered thereafter.")
    ap.add_argument("--aliaspattern",
                    help="Regex for the aliaspattern ini field (e.g. '^login[0-9]+\\.hpc\\.example\\.edu$'); "
                         "required on first run; remembered thereafter.")
    ap.add_argument("--install-into",  dest="install_into",
                    help="SimFactory root to install into (default: ./simfactory)")
    ap.add_argument("--externals-dir", dest="externals_dir",
                    help="Root directory for externals build/install trees "
                         "(default: ./externals); persisted after first use.")
    ap.add_argument("--ppn",           type=int, help="Override physical cores per node")
    ap.add_argument("--queue",         help="Default queue/partition name")
    ap.add_argument("--allocation",    help="Default allocation/account name")
    ap.add_argument("--scratch",       help="Scratch filesystem path (for basedir)")
    ap.add_argument("--sourcebasedir", help="Source tree base (default: /home/@USER@)")
    ap.add_argument("--email",         help="Email for job notifications")
    ap.add_argument("--cuda-arch",     dest="cuda_arch",
                    help="Override GPU SM architecture (e.g. sm_90a, sm_80)")
    ap.add_argument("--verbose",       action="store_true")
    ap.add_argument("--plan",          action="store_true",
                    help="Show which packages will be built and exit (no files written)")
    ap.add_argument("-j", "--jobs",    dest="jobs", type=int, default=None,
                    metavar="N",
                    help="Parallel jobs for external library builds (persisted; default: 1)")
    zlib_grp = ap.add_mutually_exclusive_group()
    zlib_grp.add_argument("--with-zlib",    dest="with_zlib",    action="store_true",
                          default=False,
                          help="Force pre-building zlib in externals/ (state is saved)")
    zlib_grp.add_argument("--without-zlib", dest="without_zlib", action="store_true",
                          default=False,
                          help="Skip externals zlib; let Cactus build it (state is saved)")
    hdf5_grp = ap.add_mutually_exclusive_group()
    hdf5_grp.add_argument("--with-hdf5",    dest="with_hdf5",    action="store_true",
                          default=False,
                          help="Force pre-building HDF5 in externals/ (state is saved)")
    hdf5_grp.add_argument("--without-hdf5", dest="without_hdf5", action="store_true",
                          default=False,
                          help="Skip externals HDF5; let Cactus build it (state is saved)")
    cmake_grp = ap.add_mutually_exclusive_group()
    cmake_grp.add_argument("--with-cmake",    dest="with_cmake",    action="store_true",
                           default=False,
                           help="Force pre-building CMake in externals/ (state is saved)")
    cmake_grp.add_argument("--without-cmake", dest="without_cmake", action="store_true",
                           default=False,
                           help="Skip externals CMake; require cmake in PATH (state is saved)")
    silo_grp = ap.add_mutually_exclusive_group()
    silo_grp.add_argument("--with-silo",    dest="with_silo",    action="store_true",
                          default=False,
                          help="Force pre-building Silo in externals/ (implies HDF5; state is saved)")
    silo_grp.add_argument("--without-silo", dest="without_silo", action="store_true",
                          default=False,
                          help="Skip externals Silo; let Cactus build it (state is saved)")
    jpeg_grp = ap.add_mutually_exclusive_group()
    jpeg_grp.add_argument("--with-jpeg",    dest="with_jpeg",    action="store_true",
                          default=False,
                          help="Force pre-building libjpeg in externals/ (state is saved)")
    jpeg_grp.add_argument("--without-jpeg", dest="without_jpeg", action="store_true",
                          default=False,
                          help="Skip externals libjpeg; let Cactus build it (state is saved)")
    nsimd_grp = ap.add_mutually_exclusive_group()
    nsimd_grp.add_argument("--with-nsimd",    dest="with_nsimd",    action="store_true",
                           default=False,
                           help="Pre-build NSIMD with detected SIMD backend (state is saved)")
    nsimd_grp.add_argument("--without-nsimd", dest="without_nsimd", action="store_true",
                           default=False,
                           help="Skip externals NSIMD; let Cactus build it (state is saved)")
    fftw3_grp = ap.add_mutually_exclusive_group()
    fftw3_grp.add_argument("--with-fftw3",    dest="with_fftw3",    action="store_true",
                           default=False,
                           help="Force pre-building FFTW3 in externals/ (state is saved)")
    fftw3_grp.add_argument("--without-fftw3", dest="without_fftw3", action="store_true",
                           default=False,
                           help="Skip externals FFTW3; let Cactus build it (state is saved)")
    hwloc_grp = ap.add_mutually_exclusive_group()
    hwloc_grp.add_argument("--with-hwloc",    dest="with_hwloc",    action="store_true",
                           default=False,
                           help="Force pre-building hwloc in externals/ (state is saved)")
    hwloc_grp.add_argument("--without-hwloc", dest="without_hwloc", action="store_true",
                           default=False,
                           help="Skip externals hwloc; let Cactus build it (state is saved)")
    yaml_cpp_grp = ap.add_mutually_exclusive_group()
    yaml_cpp_grp.add_argument("--with-yaml_cpp",    dest="with_yaml_cpp",    action="store_true",
                              default=False,
                              help="Force pre-building yaml-cpp in externals/ (state is saved)")
    yaml_cpp_grp.add_argument("--without-yaml_cpp", dest="without_yaml_cpp", action="store_true",
                              default=False,
                              help="Skip externals yaml-cpp; let Cactus build it (state is saved)")
    boost_grp = ap.add_mutually_exclusive_group()
    boost_grp.add_argument("--with-boost",    dest="with_boost",    action="store_true",
                           default=False,
                           help="Force pre-building Boost in externals/ (state is saved)")
    boost_grp.add_argument("--without-boost", dest="without_boost", action="store_true",
                           default=False,
                           help="Skip externals Boost; let Cactus build it (state is saved)")
    ap.add_argument("--mpi-dir", dest="mpi_dir",
                    help="Path to a system/module MPI installation prefix "
                         "(e.g. /usr/local/packages/openmpi/4.1.3/gcc-11.2.0). "
                         "Suppresses the externals OpenMPI build; remembered across runs.")
    mpi_grp = ap.add_mutually_exclusive_group()
    mpi_grp.add_argument("--with-mpi",    dest="with_mpi",    action="store_true",
                         default=False,
                         help="Force pre-building OpenMPI in externals/ (state is saved)")
    mpi_grp.add_argument("--without-mpi", dest="without_mpi", action="store_true",
                         default=False,
                         help="Skip externals MPI; let Cactus MPI thorn handle it (state is saved)")
    ap.add_argument("--mpi-clean", dest="mpi_clean", action="store_true",
                    default=False,
                    help="Wipe and rebuild the externals OpenMPI from scratch")
    ap.add_argument("--skip-mpi-test", dest="skip_mpi_test", action="store_true",
                    default=False,
                    help="Skip the MPI send/recv sanity test after building external MPI")
    adios2_grp = ap.add_mutually_exclusive_group()
    adios2_grp.add_argument("--with-adios2",    dest="with_adios2",    action="store_true",
                            default=False,
                            help="Force pre-building ADIOS2 in externals/ (state is saved)")
    adios2_grp.add_argument("--without-adios2", dest="without_adios2", action="store_true",
                            default=False,
                            help="Skip externals ADIOS2; let Cactus build it (state is saved)")
    openpmd_grp = ap.add_mutually_exclusive_group()
    openpmd_grp.add_argument("--with-openpmd",    dest="with_openpmd",    action="store_true",
                             default=False,
                             help="Force pre-building openPMD in externals/ (implies ADIOS2; state is saved)")
    openpmd_grp.add_argument("--without-openpmd", dest="without_openpmd", action="store_true",
                             default=False,
                             help="Skip externals openPMD; let Cactus build it (state is saved)")
    amrex_grp = ap.add_mutually_exclusive_group()
    amrex_grp.add_argument("--with-amrex",    dest="with_amrex",    action="store_true",
                           default=False,
                           help="Pre-build AMReX in externals/ with detected GPU arch (implies CMake; state is saved)")
    amrex_grp.add_argument("--without-amrex", dest="without_amrex", action="store_true",
                           default=False,
                           help="Skip externals AMReX; let Cactus build it (state is saved)")
    lapack_grp = ap.add_mutually_exclusive_group()
    lapack_grp.add_argument("--with-lapack",    dest="with_lapack",    action="store_true",
                            default=False,
                            help="Pre-build LAPACK in externals/ from bundled tarball (state is saved)")
    lapack_grp.add_argument("--without-lapack", dest="without_lapack", action="store_true",
                            default=False,
                            help="Skip externals LAPACK; let Cactus build it (state is saved)")
    args = ap.parse_args()

    hostname = socket.gethostname()
    cactus_root = Path.cwd()

    # Determine machine name early so we can find the right state file.
    # Priority: --name CLI arg > sim whoami > None (loads legacy fallback).
    _pre_name: Optional[str] = None
    for _si, _sa in enumerate(sys.argv[1:], 1):
        if _sa == "--name" and _si < len(sys.argv):
            _pre_name = sys.argv[_si]
            break
        if _sa.startswith("--name="):
            _pre_name = _sa.split("=", 1)[1]
            break
    if not _pre_name:
        _sw_rc, _sw_out, _ = run_cmd(str(Path.cwd() / _SIM), "whoami")
        if _sw_rc == 0 and _sw_out.strip():
            _pre_name = _sw_out.strip()

    # Load persistent state and apply any CLI overrides.
    state = _load_state(cactus_root, _pre_name)
    # If still missing name, check the externals dir (--externals-dir CLI arg).
    # This handles state.json saved in a prior run from a different CWD.
    if not state.get("name") and getattr(args, "externals_dir", None):
        _alt = _load_state(Path(args.externals_dir), _pre_name)
        if _alt:
            state.update(_alt)

    # Persist all single-value options so they survive --plan dry runs.
    # CLI value wins; absent means restore from state.
    _persist_opts = [
        "jobs", "ppn", "queue", "allocation",
        "scratch", "sourcebasedir", "email", "cuda_arch", "install_into",
        "externals_dir",
    ]
    _changed = False
    for key in _persist_opts:
        val = getattr(args, key, None)
        if val is not None:
            state[key] = val
            _changed = True
        else:
            setattr(args, key, state.get(key))
    # -j defaults to 1 (not None) when absent; apply that after state restore.
    if args.jobs is None:
        args.jobs = state.get("jobs", 1)
    if _changed:
        _save_state(cactus_root, state)

    # Resolve the externals root now so every build/detect function sees it.
    global _ext_root
    _ext_root = (Path(args.externals_dir).resolve()
                 if args.externals_dir
                 else (cactus_root / "externals").resolve())

    # --name and --aliaspattern are required on the first run and remembered.
    if args.name:
        state["name"] = args.name
        _save_state(cactus_root, state)
    else:
        args.name = state.get("name")
    if args.aliaspattern:
        state["aliaspattern"] = args.aliaspattern
        _save_state(cactus_root, state)
    else:
        args.aliaspattern = state.get("aliaspattern")

    if args.with_zlib:
        state["with_zlib"] = True
        _save_state(cactus_root, state)
    elif args.without_zlib:
        state["with_zlib"] = False
        _save_state(cactus_root, state)
    if args.with_hdf5:
        state["with_hdf5"] = True
        _save_state(cactus_root, state)
    elif args.without_hdf5:
        state["with_hdf5"] = False
        _save_state(cactus_root, state)
    if args.with_cmake:
        state["with_cmake"] = True
        _save_state(cactus_root, state)
    elif args.without_cmake:
        state["with_cmake"] = False
        _save_state(cactus_root, state)
    if args.with_silo:
        state["with_silo"] = True
        _save_state(cactus_root, state)
    elif args.without_silo:
        state["with_silo"] = False
        _save_state(cactus_root, state)
    if args.with_jpeg:
        state["with_jpeg"] = True
        _save_state(cactus_root, state)
    elif args.without_jpeg:
        state["with_jpeg"] = False
        _save_state(cactus_root, state)
    if args.with_nsimd:
        state["with_nsimd"] = True
        _save_state(cactus_root, state)
    elif args.without_nsimd:
        state["with_nsimd"] = False
        _save_state(cactus_root, state)
    if args.with_fftw3:
        state["with_fftw3"] = True
        _save_state(cactus_root, state)
    elif args.without_fftw3:
        state["with_fftw3"] = False
        _save_state(cactus_root, state)
    if args.with_hwloc:
        state["with_hwloc"] = True
        _save_state(cactus_root, state)
    elif args.without_hwloc:
        state["with_hwloc"] = False
        _save_state(cactus_root, state)
    if args.with_yaml_cpp:
        state["with_yaml_cpp"] = True
        _save_state(cactus_root, state)
    elif args.without_yaml_cpp:
        state["with_yaml_cpp"] = False
        _save_state(cactus_root, state)
    if args.with_boost:
        state["with_boost"] = True
        _save_state(cactus_root, state)
    elif args.without_boost:
        state["with_boost"] = False
        _save_state(cactus_root, state)
    if args.with_mpi:
        state["with_mpi"] = True
        _save_state(cactus_root, state)
    elif args.without_mpi:
        state["with_mpi"] = False
        _save_state(cactus_root, state)
    if args.with_adios2:
        state["with_adios2"] = True
        _save_state(cactus_root, state)
    elif args.without_adios2:
        state["with_adios2"] = False
        _save_state(cactus_root, state)
    if args.with_openpmd:
        state["with_openpmd"] = True
        _save_state(cactus_root, state)
    elif args.without_openpmd:
        state["with_openpmd"] = False
        _save_state(cactus_root, state)
    if args.with_amrex:
        state["with_amrex"] = True
        _save_state(cactus_root, state)
    elif args.without_amrex:
        state["with_amrex"] = False
        _save_state(cactus_root, state)
    if args.with_lapack:
        state["with_lapack"] = True
        _save_state(cactus_root, state)
    elif args.without_lapack:
        state["with_lapack"] = False
        _save_state(cactus_root, state)

    # Propagate implied dependencies so downstream detectors see them.
    # --with-openpmd → need ADIOS2; --with-silo → need HDF5; --with-hdf5 → need zlib.
    # --with-amrex → need CMake.
    if state.get("with_openpmd") and not state.get("with_adios2"):
        state["with_adios2"] = True
    if state.get("with_silo") and not state.get("with_hdf5"):
        state["with_hdf5"] = True
    if state.get("with_hdf5") and not state.get("with_zlib"):
        state["with_zlib"] = True
    if state.get("with_amrex") and not state.get("with_cmake"):
        state["with_cmake"] = True
    if state.get("with_yaml_cpp") and not state.get("with_cmake"):
        state["with_cmake"] = True

    if args.plan:
        show_plan(args, state, cactus_root)
        return

    # --name is required; it must have been supplied on this run or a prior one.
    if not args.name:
        ap.error("--name NAME is required on the first run (it will be remembered "
                 "for future runs). Also supply --aliaspattern on the first run.")
    if not args.aliaspattern:
        ap.error("--aliaspattern PATTERN is required on the first run (it will be "
                 "remembered for future runs).")
    name = re.sub(r"[^a-zA-Z0-9._-]", "-", args.name)

    print(f"Probing {hostname} …", flush=True)
    p = Probe(args, state, cactus_root)
    # Persist the detected MPI dir under a separate key for change-detection.
    # We intentionally avoid overwriting state["mpi_dir"] here — that key is
    # reserved for user-supplied --mpi-dir hints that should persist across runs.
    if p.mpi.found and p.mpi.dir:
        state["_auto_mpi_dir"] = p.mpi.dir
        _save_state(cactus_root, state)
    report(p, name)

    # Always install directly into the simfactory mdb tree.
    sf = Path(args.install_into) if args.install_into else Path("simfactory")
    dirs = {
        "ini": sf / "mdb" / "machines",
        "cfg": sf / "mdb" / "optionlists",
        "run": sf / "mdb" / "runscripts",
        "sub": sf / "mdb" / "submitscripts",
    }
    for d in dirs.values():
        d.mkdir(parents=True, exist_ok=True)

    written = []

    def write(path: Path, content: str, executable: bool = False):
        if path.exists() and path.read_text() == content:
            return  # unchanged — skip the write to preserve mtime
        path.write_text(content)
        if executable:
            path.chmod(path.stat().st_mode | 0o111)
        written.append(str(path))

    write(dirs["ini"] / f"{name}.ini", generate_ini(p, name, args))
    write(dirs["cfg"] / f"{name}.cfg", generate_cfg(p, name, args))
    write(dirs["run"] / f"{name}.run", generate_run(p, name), executable=True)

    sub = generate_sub(p, name, args)
    if sub:
        write(dirs["sub"] / f"{name}.sub", sub)

    print("\nInstalled:")
    for f in written:
        print(f"  {f}")

    # Verify that SimFactory recognises this host as the machine we just configured.
    print("\nVerifying with 'sim whoami' …", flush=True)
    whoami_name = _sim_whoami()
    ini_path = dirs["ini"] / f"{name}.ini"
    if whoami_name is None:
        print(f"  WARNING: 'sim whoami' did not return a machine name — "
              f"could not verify configuration.\n"
              f"  Check that the aliaspattern in {ini_path} matches this host.")
    elif whoami_name.lower() == name.lower() and whoami_name != name:
        # Case mismatch: sim found an older ini with different capitalisation.
        # Treat as a warning — SimFactory is case-sensitive in machine names but
        # the aliaspattern itself matched, so the ini is correct.
        print(f"  WARNING: 'sim whoami' returned '{whoami_name}' but expected '{name}'.")
        print(f"  If an older {whoami_name}.ini exists alongside {name}.ini, remove it.")
    elif whoami_name != name:
        sys.exit(
            f"\nERROR: 'sim whoami' returned '{whoami_name}' but expected '{name}'.\n"
            f"  The aliaspattern in {ini_path} does not match this host's hostname.\n"
            f"  Fix the aliaspattern and re-run, or pass --aliaspattern to override."
        )
    else:
        print(f"  OK — sim whoami confirmed machine = {name}")

    print(f"\nNext steps:")
    print(f"  # Edit {sf}/etc/defs.local.ini — verify user/email/allocation")
    print(f"  sim setup --machine={name}")
    print()

if __name__ == "__main__":
    main()
