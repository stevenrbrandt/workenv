# Cactus Build System — Reference for AI Agents

This document describes how the **Cactus Code** flesh, the **CST**, **ThornLists**, **ExternalLibraries**, and **SimFactory** interact when building and linking a configuration. It is written for automated assistants working on Einstein Toolkit / CarpetX trees (including this repository’s `build_carpetx` / `bench.th` workflow).

Primary sources: Cactus flesh `Makefile` (v4.x, ET_2026_05), `lib/make/make.configuration`, `lib/make/make.thornlib`, `lib/make/setup_configuration.pl`, `lib/sbin/CST`, utilities `Scripts/MakeThornList`, ExternalLibraries `detect.sh`/`build.sh` pattern, SimFactory 2.

---

## 1. Mental model (two layers, two thornlist formats)

```
┌─────────────────────────────────────────────────────────────┐
│  GetComponents (CRL)  +  SimFactory (optional orchestration) │
│  checkout sources into Cactus/arrangements, simfactory/, …  │
└────────────────────────────┬────────────────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────┐
│  Cactus flesh Makefile  →  configure (optionlist + CST)     │
│  then compile thorn libraries and link the executable       │
└─────────────────────────────────────────────────────────────┘
```

| Concept | Role |
|--------|------|
| **Flesh** | Core CCTK under `Cactus/src`, top-level `Makefile`, `lib/make/*`, `lib/sbin/*` |
| **Arrangement / thorn** | Code under `arrangements/<Arrangement>/<Thorn>/` with `src/`, `*.ccl` |
| **Configuration** | Named build under `configs/<name>/` (e.g. `sim`) with its own option snapshot, bindings, objects |
| **CST** | Cactus Specification Tool — parses `*.ccl` + `ThornList`, generates bindings and `make.thornlist` |
| **ExternalLibraries** | Special thorns that **detect or build** third-party libraries before normal thorns compile |
| **SimFactory** | Wrapper that picks machine MDB + optionlist, runs `gmake <config>`, manages runs |

**Critical distinction — two “thornlist” formats:**

| Format | Example | Used by |
|--------|---------|---------|
| **CRL / GetComponents** | `bench.th` with `!TARGET`, `!URL`, `!CHECKOUT`, `!REPO_BRANCH` | Checkout only |
| **CST / compile ThornList** | Lines `Arrangement/Thorn` (optionally `#DISABLED …`) | Configure + compile |

Never pass a CRL file as Cactus `THORNLIST=` unless you first strip it to `Arrangement/Thorn` lines (this repo: `derive_bench_build_th.py` → `configs/…/ThornList` via SimFactory).

---

## 2. Directory layout (after a normal ET checkout)

```
Cactus/                          # CCTK_HOME
  Makefile                       # gmake entry (requires GNU make)
  src/                           # flesh sources + configuration.ccl
  lib/
    make/                        # make.configuration, make.thornlib, setup_configuration.pl, configure
    sbin/                        # CST, Perl helpers, MakeThornList may live under utils/
  arrangements/
    CactusBase/IOUtil/
    CarpetX/CarpetX/
    ExternalLibraries/AMReX/
    ExternalLibraries/HDF5/
    …
  configs/
    <config>/                    # one configuration
      ThornList                  # compiled thorn list (CST format)
      config-info                # recorded options / timestamps
      config-data/               # make.config.defn, cctk_Config.h, make.thornlist (generated)
      bindings/                  # generated from *.ccl
      build/<Thorn>/             # object files per thorn
      lib/libthorn_<Thorn>.a     # thorn static libraries
      scratch/                   # ExternalLibraries build trees, F90 modules, done/
      exe/ or ../../exe/         # linked executable (location depends on setup)
  simfactory/                    # if checked out (SimFactory2)
    bin/sim
    mdb/machines/ optionlists/ submitscripts/ runscripts/
    etc/defs.local.ini           # from `sim setup-silent` only
  thornlists/                    # optional copies of .th files
  repos/                         # optional GetComponents metadata
```

Environment variables of note:

| Variable | Meaning |
|----------|---------|
| `CCTK_HOME` | Root of flesh (directory containing top-level `Makefile`) |
| `CONFIGS_DIR` | Override for `configs/` (default `$CCTK_HOME/configs`) |
| `CACTUSRC` / `HOME/.cactus` | User defaults (`config`, MasterThornList) |
| `PROMPT` | `"yes"` (default) enables interactive prompts; scripts set non-interactive via SimFactory |

---

## 3. End-to-end build pipeline

### 3.1 Create / reconfigure a configuration

```bash
cd $CCTK_HOME
gmake <config>-config THORNLIST=path/to/compile.th options=path/to/optionlist.cfg
# or via SimFactory:
./simfactory/bin/sim build --configuration <config> --thornlist … --optionlist …
```

What happens:

1. **`setup_configuration.pl`** creates `configs/<config>/{build,lib,scratch,config-data}` if new.
2. Runs flesh **`lib/make/configure`** (autoconf-style) with environment variables derived from the **optionlist** and command-line `KEY=value` pairs.
3. Writes **`config-data/make.config.defn`**, **`cctk_Config.h`**, rules, etc.
4. Stores **`config-info`** (options + timestamps). Later builds may force **reconfig** if flesh `force-reconfigure` is newer than `config-info`.

**Configure-time only options** (ignored at pure compile time if only passed then — Makefile warns):

- `DEBUG`, `OPTIMISE` / `OPTIMIZE`, `PROFILE`, and typically compiler choice / OpenMP / arch flags baked into `make.config.defn`.

To change compilers, OpenMP, `CXX=nvcc`, `HDF5_DIR`, etc. after first configure: **reconfigure**

```bash
gmake <config>-config options=… THORNLIST=…     # overwrites options
# or
gmake <config>-reconfig                          # previous options
gmake <config>-delete && gmake <config>-config   # clean slate
```

SimFactory equivalent: remove `configs/<config>` and re-run `sim build` with thornlist + optionlist.

### 3.2 CST (rebuild of specification)

First full build or `gmake <config>-rebuild` runs the **CST** (`lib/sbin/CST`):

- Inputs: `configs/<config>/ThornList`, each thorn’s `param.ccl`, `interface.ccl`, `schedule.ccl`, `configuration.ccl`, flesh `configuration.ccl`.
- Outputs (under the configuration):
  - `config-data/make.thornlist` — Make variables `THORNS`, per-thorn `USESTHORNS_*`, link order
  - `bindings/` — generated C headers/sources for parameters, grid functions, schedule
  - various `make.<Thorn>.defn` fragments for include/lib paths from configuration.ccl **PROVIDES**

**Rule of thumb for agents:** if you change `interface.ccl` / `schedule.ccl` / `configuration.ccl` / ThornList membership, force CST:

```bash
gmake <config>-rebuild
# or delete config-data/make.thornlist and rebuild
```

### 3.3 Compile and link

```bash
gmake <config>                 # or: gmake -f lib/make/make.configuration TOP=configs/<config>
# parallel thorns: gmake <config> TJOBS=8
# parallel files within thorn: FJOBS=8
```

Per thorn (`make.configuration` → `make.thornlib`):

1. Print `Checking status of thorn <Name>`.
2. Ensure `configs/<config>/build/<Thorn>/`.
3. If thorn has `src/Makefile`, use it; else **`lib/make/make.thornlib`**.
4. Include `src/make.code.defn` (lists `SRCS`, `SUBDIRS`).
5. Compile objects with flags from `config-data/make.config.defn` + include dirs:
   - system + thorn `src/` + `config-data` + flesh `src/include` + `bindings/include` + **USESTHORNS** include/lib lines from dependent PROVIDES.
6. Archive to `lib/libthorn_<Thorn>.a`.

**ExternalLibraries** thorns often have a special `src/make.code.deps` that runs **`detect.sh`** then maybe **`build.sh`** before any object compile (status messages like `Checking status of thorn AMReX`, `AMReX: Configuring...`).

Final link: flesh `datestamp.c` + **whole-archive** (or ordered) link of all `libthorn_*.a` + `GENERAL_LIBRARIES` from configure (MPI, math, CUDA runtime, etc.).

Executable name is typically `exe/cactus_<config>` (SimFactory) or as set by `EXE` / `EXEDIR` in config.

---

## 4. Top-level `Makefile` targets (agents should prefer these)

| Target | Meaning |
|--------|---------|
| `gmake help` | List configurations and options |
| `gmake <config>` | Build configuration (configure if needed, then compile) |
| `gmake <config>-config` | Configure / reconfigure (needs `THORNLIST`, optional `options=`) |
| `gmake <config>-reconfig` | Reconfigure with **previous** options |
| `gmake <config>-rebuild` | Force CST + rebuild |
| `gmake <config>-build` | Build only thorns in `BUILDLIST` |
| `gmake <config>-clean` | Delete objects and deps |
| `gmake <config>-realclean` | Almost new; keeps `config-data` + `ThornList` |
| `gmake <config>-delete` | Delete entire configuration directory |
| `gmake <config>-thornlist` | Regenerate `ThornList` (dangerous if you manage it by hand) |
| `gmake <config>-configinfo` | Show recorded options |
| `VERBOSE=yes` | Show full compiler commands |
| `TJOBS` / `FJOBS` | Parallelism across thorns / files |

**Invalid configuration names:** must not end with reserved suffixes (`-build`, `-clean`, `-config`, `-delete`, …) — enforced in `setup_configuration.pl`.

---

## 5. Optionlists (configure-time key/value files)

Plain text, SimFactory/Cactus style:

```
KEY = value
# comments
```

Common keys (non-exhaustive):

| Key | Role |
|-----|------|
| `CC`, `CXX`, `F90`, `LD` | Compilers / linker |
| `CFLAGS`, `CXXFLAGS`, `F90FLAGS`, `LDFLAGS`, `LIBS`, `LIBDIRS` | Flags and libs |
| `CPPFLAGS` | Preprocessor (e.g. `-DSIMD_DISABLE`) |
| `OPENMP`, `*_OPENMP_FLAGS` | Host OpenMP |
| `DEBUG`, `OPTIMISE` | Configure-time only |
| `HDF5_DIR`, `AMREX_DIR`, `ADIOS2_DIR`, `YAML_CPP_DIR`, `MPI_DIR`, … | ExternalLibraries **detect** roots (`BUILD` = force bundled build) |
| `AMREX_ENABLE_CUDA`, `AMREX_CMAKE_CUDA_ARCHITECTURES` | Bundled AMReX CMake |
| `CUCC`, `CUCCFLAGS` | CUDA compiler for packages that honor them |
| `DISABLE_INT16`, `DISABLE_REAL16` | Needed for many CUDA stacks |

**SimFactory** copies the optionlist into the machine MDB and passes it when configuring. Changing the optionlist file without reconfiguring does **not** change an existing `configs/<name>/`.

### CUDA / nvcc special case

CarpetX CUDA builds often set:

```text
CXX = nvcc -x cu
LD  = nvcc --forward-unknown-to-host-compiler …
OPENMP = yes
CPPFLAGS = -DSIMD_DISABLE
```

Consequences for agents:

1. **Any ExternalLibraries package that runs CMake with `$CXX`** will try to use **nvcc** as a host compiler and often fail (`Unknown argument -x`, broken CMake CXX test). Examples: ADIOS2, NSIMD, yaml-cpp, openPMD, Silo when `DIR=BUILD`.
2. Prefer **prebuilt** libraries with **g++/mpicc** and set `*_DIR` (this repo’s `install_deps.sh`).
3. **AMReX OpenMP must match Cactus OpenMP** — CarpetX hard-errors if Cactus has OpenMP and AMReX was built without (`AMReX_OMP`).
4. If AMReX was built with **HDF5**, its public headers may `#include <hdf5.h>` even when CarpetX does not list HDF5 in `USESTHORNS`; inject `-I$HDF5_HOME/include` (and link `hdf5`) globally.

---

## 6. ThornList (compile list) format

### 6.1 CST ThornList (`configs/<config>/ThornList`)

```
# comment
Arrangement/ThornName
#DISABLED Arrangement/OtherThorn
```

- One thorn per line: `Arrangement/Thorn`.
- `#DISABLED` lines are inactive for this configuration.
- Order can matter for diagnostics; CST computes link order from dependencies.

### 6.2 CRL GetComponents list (`bench.th`)

```
!CRL_VERSION = 1.0
!DEFINE ROOT = Cactus
!DEFINE ET_RELEASE = ET_2026_05

!TARGET   = $ARR
!TYPE     = git
!URL      = https://github.com/…
!REPO_BRANCH = $ET_RELEASE
!CHECKOUT = Path/OnlyForSparseCheckout
Arrangement/ThornA
#DISABLED Arrangement/ThornB
```

- `!CHECKOUT` sparse-checkout paths are **not** the same as “enabled for compile”.
- A component can appear in `!CHECKOUT` **and** as `#DISABLED` (downloaded but not built) — **do not** also list it as an enabled body line (GetComponents “Duplicate checkouts”).
- Do not enable both `ExternalLibraries/BLAS` and `ExternalLibraries/OpenBLAS` in one build.

This repository:

| File | Role |
|------|------|
| `bench.th` | CRL checkout list (authoritative) |
| `derive_bench_build_th.py` | → CST list (`bench_build.th`), strips `#DISABLED` + CUDA blocklist (NSIMD, openPMD, Silo, OpenBLAS) |
| SimFactory `--thornlist` | CST list only |

---

## 7. `MakeThornList` (`utils/Scripts/MakeThornList` or under flesh)

**Purpose:** Given a **parameter file** (`.par`) and a **master thornlist** (CST-style `Arrangement/Thorn` with checkout metadata in older workflows, or a list of available thorns), produce a smaller ThornList sufficient to run that parfile.

**Algorithm (high level):**

1. Parse `.par` with Piraha grammar (`par.peg`) → extract `ActiveThorns`.
2. Load master list → map short thorn name → `Arrangement/Thorn` if directory exists under `arrangements/`.
3. Parse each thorn’s `configuration.ccl` (and interface/param as needed) → `REQUIRES`, `REQUIRES THORNS`, `OPTIONAL`, `OPTIONAL_IFACTIVE`, `PROVIDES`.
4. Transitively activate required capabilities/thorns (not mere `OPTIONAL_IFACTIVE` unless already active).
5. Write resulting `Arrangement/Thorn` lines.

**Usage:**

```bash
export CCTK_HOME=/path/to/Cactus
$CCTK_HOME/utils/Scripts/MakeThornList -o my.th -m master.th my.par
```

**Not the same as GetComponents.** MakeThornList assumes thorns already exist under `arrangements/` (or are listed in the master list path mapping).

---

## 8. ExternalLibraries thorns (detect vs build)

Each ExternalLibraries thorn typically provides:

| File | Role |
|------|------|
| `configuration.ccl` | `PROVIDES <Cap>` with `SCRIPT src/detect.sh` and `OPTIONS …_DIR …` |
| `src/detect.sh` | Decide BUILD vs use existing install; export make variables |
| `src/build.sh` | Build bundled tarball into `configs/<cfg>/scratch/external/<Thorn>` |
| `src/make.code.deps` | Make rule that runs detect/build before thorn “done” stamp |
| `dist/*.tar*` | Bundled upstream sources |

### 8.1 `detect.sh` contract (pattern)

```bash
# If FOO_DIR=BUILD → force build
# Else try find_lib FOO … "$FOO_DIR"
# If not found → set FOO_BUILD=1, FOO_DIR=$SCRATCH_BUILD/external/FOO
# Emit BEGIN MAKE_DEFINITION … END for FOO_INC_DIRS, FOO_LIB_DIRS, FOO_LIBS
```

Common options: `HDF5_DIR`, `AMREX_DIR`, `ADIOS2_DIR`, `YAML_CPP_DIR`, `MPI_DIR`, `ZLIB_DIR`, …  
Special value **`BUILD`** forces the bundled build path.

### 8.2 When Cactus builds vs detects

| Situation | Result |
|-----------|--------|
| `FOO_DIR` points at a valid install | Detect only; create `scratch/done/FOO` stamp |
| `FOO_DIR` unset/empty and not found | Bundled `build.sh` |
| `FOO_DIR=BUILD` | Bundled `build.sh` always |
| Prebuilt with wrong features (e.g. AMReX without OpenMP while Cactus has OpenMP) | **Compile-time `#error` in CarpetX** or link failures |

### 8.3 Capability vs thorn name

- `configuration.ccl`: `PROVIDES AMReX` / `REQUIRES MPI`
- Thorn directory may be `ExternalLibraries/AMReX`
- Dependent thorns `REQUIRES AMReX` get include/lib flags via generated `make.<Thorn>.defn` and `USESTHORNS`

**Optional capabilities** (`OPTIONAL ADIOS2` in CarpetX) are only linked if the providing thorn is active.

---

## 9. CCL files agents must respect

| File | Purpose |
|------|---------|
| `interface.ccl` | Implements / inherits, variables (GF, scalars), public headers |
| `param.ccl` | Steerable parameters |
| `schedule.ccl` | When functions run (schedule bins, group reads/writes) |
| `configuration.ccl` | Build deps: REQUIRES / OPTIONAL / PROVIDES, detect scripts |

CST fails or produces incomplete bindings if these are inconsistent with the ThornList.

---

## 10. SimFactory 2 (orchestration layer)

```
sim setup-silent          # creates etc/defs.local.ini from hostname → machine MDB
sim build -jN --configuration NAME --thornlist CST.th --optionlist file.cfg
sim whoami                # validates defs + machine
```

### 10.1 Machine MDB (`simfactory/mdb/`)

| Path | Role |
|------|------|
| `machines/<nick>.ini` | hostname/aliaspattern, optionlist name, submitscript, runscript, make jobs |
| `optionlists/*.cfg` | Cactus optionlists |
| `submitscripts/*.sub` | Batch/local submit templates |
| `runscripts/*.run` | How to launch the binary |

**Do not delete** `submitscripts/` or `runscripts/` when installing custom machines/optionlists — only add files.

`defs.local.ini` must be created by **`sim setup-silent`**, not hand-written. The key `machine = …` is only valid under **`[default]`**. Appending `machine=` after a `[db-sing-cpu]` section causes:

```text
Error: found invalid keys machine in section db-sing-cpu
```

### 10.2 Hostname and machine selection

SimFactory matches `hostname` against `aliaspattern` in machine files. Cluster images may match QB4/Deep Bayou MDBs. This repo forces `hostname` → `benchmarking` and installs `mdb/machines/benchmarking.ini`.

### 10.3 Relationship to Cactus

SimFactory ultimately invokes the flesh Makefile (configure + build). Debugging a failed `sim build` is the same as debugging `gmake <config>` once you have `configs/<config>/` and `config-data/`.

---

## 11. Parallelism and “Checking status of thorn …”

Build log pattern:

```text
Checking status of thorn HDF5
…
Checking status of thorn CarpetX
COMPILING CarpetX/.../driver.cxx
```

- Thorns can build in parallel (`TJOBS`) but ExternalLibraries often serialize on shared `scratch/`.
- A thorn rebuild is skipped when `make.checked` is up to date; change sources or `clean` to force.

---

## 12. Clean / delete semantics (do not confuse)

| Command | Removes | Keeps |
|---------|---------|--------|
| `<cfg>-clean` | objects, deps | config-data, ThornList, exe maybe rebuilt |
| `<cfg>-realclean` | almost all of config | config-data, ThornList |
| `<cfg>-delete` | entire `configs/<cfg>` | arrangements, flesh |
| `distclean` | all configurations | arrangements, flesh |

**Agents:** never `rm -rf simfactory/mdb` or random arrangement trees to “fix” a compile error. Prefer `<cfg>-delete` or reconfigure. Restore missing `generic.sub` / `generic.run` by copy/fetch, not by wiping SimFactory.

---

## 13. This repository’s integration (simflowny + CarpetX)

| Script | Role |
|--------|------|
| `install_deps.sh` | Prebuild **HDF5**, **AMReX (CUDA+OMP+HDF5)**, **ADIOS2 (g++)**, **yaml-cpp (g++)** under `$PREFIX` |
| `checkout_carpetx.sh` | GetComponents with **`bench.th`** (CRL); derive **`bench_build.th`** (CST) |
| `build_carpetx.sh` | SimFactory machine `benchmarking`, `setup-silent`, inject `*_DIR` + HDF5 `-I` flags, `sim build` |
| `run_bench_carpetx.sh` | Run `bench_CottonmouthZ4c.par` → `bench.log` only |
| `analyze_bench_carpetx.sh` | Parse `bench.log` / TimerReport → walltime & RHS cells/s |
| `derive_bench_build_th.py` | CRL → CST; strip CUDA-unsafe enabled lines |

**Shared deps injection (optionlist):**

```text
HDF5_DIR, AMREX_DIR, ADIOS2_DIR, YAML_CPP_DIR = $PREFIX/...
HDF5_ENABLE_CXX/FORTRAN = no   # install_deps HDF5 is C-only parallel
# Plus global -I$PREFIX/hdf5/include for AMReX headers that include hdf5.h
```

**OpenMP consistency:**

```text
install_deps:  -DAMReX_OMP=ON
optionlist:    OPENMP = yes
```

**Do not BUILD under `CXX=nvcc -x cu`:** NSIMD, openPMD, Silo, and any other pure CMake host package. Prefer `#DISABLED` or external g++ install + `*_DIR`.

---

## 14. Troubleshooting map (for agents)

| Symptom | Likely cause | Action |
|---------|--------------|--------|
| `CMake … CXX compiler nvcc … broken` / `Unknown argument -x` | ExternalLibraries CMake using CUDA CXX | Prebuild with g++; set `*_DIR`; or disable thorn |
| `Cactus OpenMP but AMReX without OpenMP` | AMReX_OMP ≠ OPENMP | Rebuild AMReX with OMP ON or turn Cactus OpenMP off |
| `hdf5.h: No such file` while compiling CarpetX | AMReX built with HDF5; includes not global | Add `-I$HDF5_HOME/include` to CPPFLAGS/CXXFLAGS/CUCCFLAGS |
| `Duplicate checkouts: …` (GetComponents) | Same Arr/Thorn in `!CHECKOUT` and enabled body | Keep only one form |
| `invalid keys machine in section db-sing-cpu` | `machine=` outside `[default]` in defs.local.ini | Delete defs; `sim setup-silent` only |
| `generic.sub does not exist` | Incomplete simfactory mdb | Restore submitscripts/runscripts; do not wipe mdb |
| Optionlist change has no effect | Config already configured | `<cfg>-delete` or `-config` with new `options=` |
| `SM Arch ('sm_52') not found` (nvlink) | Device link missing `-gencode`/`-arch` | Put arch on **link** line, not only compile |
| `/usr/bin/ld: cannot find -ludev` | **hwloc** (and some other stacks) link against **libudev** | Install **`libudev-dev`** (provides the `libudev.so` linker symlink). Runtime often only needs `libudev1`. This repo’s `Dockerfile` installs `libudev-dev`. On a bare cluster node without rebuild: `apt-get install -y libudev-dev` (or equivalent). |
| Thorn missing at runtime | Not in compile ThornList / ActiveThorns | Align CST list, parfile ActiveThorns, and arrangements |
| `mpicxx -show`/`-compile_info` prints literal `I_MPI_SUBSTITUTE_INSTALLDIR` | Intel oneAPI MPI wrapper needs `env/vars.sh` sourced to substitute real paths; Cactus's `MPI/src/detect.pl` only tries `-compile_info`/`--showme` (not the `-show` Intel supports) | Don't rely on wrapper auto-detect; set `MPI_DIR`/`MPI_INC_DIRS`/`MPI_LIB_DIRS`/`MPI_LIBS` manually in the optionlist |
| `mpirun`: `Unable to create UD QP` / `PSM3 can't open nic unit` | OFI/PSM3 provider tries the node's RoCE/IB NIC over verbs and fails (permissions, single-node run, non-IB-configured node) | `export I_MPI_FABRICS=shm` (+ `FI_PROVIDER=tcp` as a fallback) before `mpirun`, especially for single-node/single-rank runs |
| `ld.lld: unable to find library -lgfortran` (or unresolved `_gfortran_*` symbols) at final link | Final link done via `hipcc`/clang++, not `gfortran`; a Fortran thorn needs libgfortran but clang doesn't search gcc's private lib dir, and some distros only ship the unversioned `libgfortran.so` symlink there (e.g. `/usr/lib/gcc/x86_64-linux-gnu/11/`), not in the multiarch lib dir | Add `gfortran` to `LIBS` and that gcc private lib dir to `LIBDIRS` |
| Unresolved `hiprandCreateGenerator`/`hiprandGenerateUniformDouble`/etc. at final link | AMReX's HIP GPU backend (`AMReX_Random.cpp`) calls hipRAND directly; this isn't pulled in automatically | Add `hiprand rocrand` to `LIBS` (both live under `$ROCM_PATH/lib`) |
| `nproc` reports far fewer cores than the machine actually has (e.g. `1` on a big shared box) | Session/cgroup CPU quota, independent of `cpuset.cpus.effective`/`/proc/cpuinfo`/`free -h` which still show the full machine | Treat `nproc` as authoritative for `-j`/TJOBS/FJOBS; don't waste time parallelizing compiles the cgroup won't actually run concurrently. Consider trimming the ThornList to just what's needed (see §18) rather than compiling the full ET serially |

---

## 15. Minimal command sequences

### Flesh-only (no SimFactory)

```bash
cd Cactus
gmake sim-config THORNLIST=$PWD/thornlists/bench_build.th options=path/to/cuda_sm80.cfg
gmake -j8 sim VERBOSE=yes
./exe/cactus_sim my.par
```

### This repo (CarpetX CUDA bench)

```bash
cd $WORKDIR                    # PREFIX=$PWD
install_deps                   # hdf5, amrex, adios2, yaml-cpp
checkout_carpetx               # GetComponents bench.th → arrangements
build_carpetx                  # setup-silent + sim build (config default: sim)
run_bench_carpetx              # execute only → carpetx_bench_run/bench.log
analyze_bench_carpetx          # parse timers (re-runnable without re-executing)
```

### After changing optionlist or shared deps

```bash
rm -rf Cactus/configs/sim
build_carpetx                  # reconfigure + rebuild
```

---

## 16. Glossary

| Term | Definition |
|------|------------|
| **CCTK** | Cactus Computational Toolkit (flesh API) |
| **CST** | Specification tool generating bindings from CCL + ThornList |
| **Thorn** | Compile unit under an arrangement |
| **Arrangement** | Namespace directory grouping thorns |
| **Configuration** | Named option + thorn selection + object tree under `configs/` |
| **PROVIDES / REQUIRES** | configuration.ccl capability graph (not filesystem paths) |
| **USESTHORNS** | Make variable: other thorns whose includes/libs feed this thorn’s compile |
| **SCRATCH_BUILD** | `configs/<cfg>/scratch` — external builds and intermediate files |
| **CRL** | Component Retrieval Language (GetComponents `.th` files) |

---

## 17. Agent checklist before editing the build

1. Are you changing **checkout** (CRL) or **compile** (CST ThornList / optionlist)?
2. Will configure-time options change? If yes, plan **reconfig/delete config**.
3. Will CCL files change? Plan **CST rebuild**.
4. Does any ExternalLibraries thorn run **CMake** while `CXX=nvcc`? Prefer prebuilt + `*_DIR`.
5. Does AMReX feature set (OMP, CUDA, HDF5) still match optionlist and CarpetX checks?
6. Never invent deletions of `simfactory/mdb/*` or entire arrangements to clear a single compile error.
7. Prefer `VERBOSE=yes` on a single thorn (`BUILDLIST=CarpetX gmake sim-build`) when isolating failures.

---

## 18. AMD GPU (ROCm/HIP) build path — worked example

Everything above this section was written around the CUDA/nvcc case. This
section documents the parallel HIP/ROCm path, based on a working build on
a single-GPU workstation (`omnia`, one AMD Instinct MI210 / `gfx90a`,
ROCm 7.1.1 under `/opt/rocm`, cmake 3.22.1, **no system MPI package**,
Intel oneAPI MPI available, and a **1-CPU-core** session limit despite the
box having 144 cores/1.9TB RAM — see the troubleshooting row above about
`nproc`).

### 18.1 Mental model differences from CUDA

- HIP's `hipcc` is a **clang-based, ordinary host+device compiler** — not
  a two-compiler split like `CXX=g++` / `CUCC=nvcc`. In practice this
  means `CXX = CC = LD = hipcc --offload-arch=<gfxNNN>` **globally**, for
  every thorn, no `CUCC`-style conditional override needed (contrast with
  §5's CUDA special case, where only AMReX-consuming thorns get switched
  to `nvcc`).
- `AMReX/configuration.ccl` already exposes `AMREX_ENABLE_HIP` and
  `AMREX_AMD_ARCH` options (parallel to `AMREX_ENABLE_CUDA` /
  `AMREX_CMAKE_CUDA_ARCHITECTURES`), and `AMReX/src/build.sh`'s bundled
  build already branches on them
  (`-DAMReX_GPU_BACKEND=HIP -DAMReX_AMD_ARCH=...`). No thorn-side changes
  are needed to support HIP — only the OptionList.
- The `--offload-arch=gfxNNN` flag name is current (ROCm ≥ ~5.7); older
  ROCm/ Cactus examples (e.g. `simfactory/mdb/optionlists/frontier.cfg`,
  which targets `gfx90a` on a Cray system) use the older
  `--amdgpu-target=gfxNNN` spelling. Check `hipcc --help` on the target
  system rather than assuming.
- Get the exact `gfxNNN` from `rocminfo | grep -A5 gfx` (or `rocm-smi
  --showproductname`) — don't guess from the card name (MI210 = `gfx90a`,
  MI300 = `gfx942`, etc).

### 18.2 Building AMReX externally (recommended when the internal CMake path is awkward)

It's fine to build AMReX **outside** the Cactus build system and just
point `AMREX_DIR` at the install, letting `AMReX/src/detect.sh`'s
`find_lib` pick it up (skips the bundled `build.sh` entirely). This is
useful when: iterating on the AMReX CMake flags without re-running
Cactus's configure each time; the bundled build's CMake invocation
doesn't fit the local MPI/compiler setup; or you want to sanity-check the
AMReX+GPU build in isolation before wiring it into Cactus.

```bash
export ROCM_PATH=/opt/rocm
export ROCM_ARCH=gfx90a   # from rocminfo
cd externals/build/amrex-<version>
mkdir build-hip && cd build-hip
cmake .. \
  -DCMAKE_BUILD_TYPE=Release \
  -DCMAKE_CXX_COMPILER=hipcc \
  -DAMReX_GPU_BACKEND=HIP -DAMReX_CUDA=OFF -DAMReX_AMD_ARCH=${ROCM_ARCH} \
  -DAMReX_MPI=ON -DMPI_HOME=<mpi install prefix> \
  -DAMReX_OMP=OFF \
  -DAMReX_PARTICLES=ON -DAMReX_ASSERTIONS=ON -DAMReX_FORTRAN=OFF \
  -DCMAKE_INSTALL_PREFIX=<install prefix>
make -j<nproc actually available> && make install
```

CMake will warn `You are using the legacy wrapper 'hipcc' as the HIP
compiler; use amdclang++ instead` — this is non-fatal and matches what
Cactus's own `AMReX/src/build.sh` and `frontier.cfg` both do (`CXX =
hipcc`), so it's fine to ignore for consistency with the rest of the
Cactus optionlist.

Then in the Cactus OptionList: `AMREX_DIR = <install prefix>`,
`AMREX_ENABLE_HIP = yes`, `AMREX_AMD_ARCH = gfx90a` (this doesn't retrigger a build — Cactus's own AMReX thorn only reads `AMREX_ENABLE_HIP`/`AMREX_AMD_ARCH` inside its *bundled* `build.sh`; with `AMREX_DIR` pointing at a pre-built install, `detect.sh` finds it via `AMReX.H`/`libamrex` and never calls `build.sh`, so these two variables are just informational at that point).

### 18.3 Minimal worked OptionList (single-GPU workstation, no system MPI)

```text
CC  = hipcc --offload-arch=gfx90a
CXX = hipcc --offload-arch=gfx90a
LD  = hipcc --offload-arch=gfx90a
F90 = gfortran

CXXFLAGS = -g -std=c++17 -Wno-unused-command-line-argument -Wno-pass-failed
LDFLAGS  = -fgpu-rdc --hip-link
# gfortran runtime + AMReX's HIP RNG backend — see §14 troubleshooting rows
LIBS     = stdc++fs gfortran hiprand rocrand

SYS_INC_DIRS = /opt/rocm/include
LIBDIRS      = /opt/rocm/lib /usr/lib/gcc/x86_64-linux-gnu/11   # unversioned libgfortran.so lives here

OPENMP = no        # must match the OMP setting AMReX itself was built with (see §5's OpenMP rule — it's not CUDA-specific)

AMREX_DIR        = <externally-built AMReX install, or leave unset + AMREX_DIR=BUILD for the bundled path>
AMREX_ENABLE_HIP = yes
AMREX_AMD_ARCH   = gfx90a

# No system MPI package on this host; Intel oneAPI MPI is present instead.
# Set explicitly rather than relying on wrapper auto-detection (§14).
MPI_DIR      = /opt/intel/oneapi/mpi/latest
MPI_INC_DIRS = /opt/intel/oneapi/mpi/latest/include
MPI_LIB_DIRS = /opt/intel/oneapi/mpi/latest/lib/release /opt/intel/oneapi/mpi/latest/lib
MPI_LIBS     = mpicxx mpifort mpi rt pthread dl
```

Before any `mpirun` (build-time conftest links or actual runs), also
`source /opt/intel/oneapi/mpi/latest/env/vars.sh` and
`export I_MPI_FABRICS=shm FI_PROVIDER=tcp` — see §14.

### 18.4 Scoping the ThornList to the GPU driver only

When the only goal is "get CarpetX/AMReX running on the GPU" (as opposed
to a full physics production stack), it's legitimate — and, under a tight
core budget, important — to hand-build a small CST ThornList rather than
use the full ET manifest:

- CarpetX itself only `REQUIRES AMReX IOUtil MPI yaml_cpp zlib` (check
  `arrangements/CarpetX/CarpetX/configuration.ccl`); ADIOS2/openPMD_api/
  Silo/CUDA are all `OPTIONAL` and can be left out.
- Individual CarpetX thorns (`BoxInBox`, `Derivs`, `TestNorms`, etc.) each
  `REQUIRES Loop` (and sometimes `Arith`) but nothing heavier — check each
  thorn's `configuration.ccl` before assuming it needs more.
- `CarpetX/Algo` pulls in `Boost`; `CarpetX/PDESolvers` (and transitively
  `CarpetX/PoissonX`) pulls in `PETSc` — skip these three unless something
  you actually need requires them.
- `utils/Scripts/MakeThornList` *does* find thorns that exist under
  `arrangements/` even if the master `.th` file doesn't mention them
  (useful when the checked-out CarpetX repo has grown thorns since the
  manifest was last synced) — but it hard-errors ("not located in master
  thornlist") if a *required* thorn is only present `#DISABLED`, and each
  invocation costs ~2 minutes fixed overhead (scans every arrangement's
  `configuration.ccl`) regardless of how many parfiles you pass it. For
  more than one or two lookups, it's often faster to just read the
  relevant `configuration.ccl` REQUIRES lines by hand.
- To find "what does the test suite need," grep `ActiveThorns` out of
  every thorn's `test/*.par` rather than guessing:
  `find -L arrangements/CarpetX -path '*/test/*.par' -exec cat {} \; | perl -0777 -ne 'while (/ActiveThorns\s*=\s*"([^"]*)"/gs){print "$1\n"}' | tr -s ' \t\n' '\n' | sort -u`

### 18.5 Verifying the GPU is actually used

A successful `gmake <cfg>` + link doesn't confirm GPU offload. Check the
run's own output: AMReX prints a memory summary at shutdown —

```
Total GPU global memory (MB) spread across MPI: [65520 ... 65520]
Free  GPU global memory (MB) spread across MPI: [16010 ... 16010]
```

— matching the card's actual HBM capacity (65520 MB ≈ 64GB, MI210) is
good evidence AMReX initialized the GPU backend correctly, independent of
whatever `rocm-smi`/GPU-busy% shows for a short test-suite-sized run.

---

## 19. Adding a new SimFactory machine (worked example: a personal/no-scheduler workstation)

This section is for agents setting up `simfactory/mdb/machines/<name>.ini`
for a machine that doesn't already have one — typically a personal
workstation or a shared box with no batch scheduler, as opposed to an HPC
cluster with SLURM/PBS. Worked out on `omnia` (single MI210 GPU, 1-CPU
session limit — see §18).

### 19.1 Two separate things named similarly — don't confuse them

| Thing | Where | Created by | Purpose |
|-------|-------|-------------|---------|
| Machine **template** | `simfactory/mdb/machines/<name>.ini`, and the `optionlist`/`submitscript`/`runscript` files it names under `simfactory/mdb/{optionlists,submitscripts,runscripts}/` | You write this by hand | Describes the machine once; shared by every configuration built on it |
| Per-**configuration** stored copies | `configs/<cfg>/{OptionList,SubmitScript,RunScript}` (note the capitalization — no file extension) | `sim build` copies/substitutes the machine templates into these on every build | What SimFactory actually reads at run/submit time for *this* configuration |

**If you configure and build a configuration via the flesh Makefile
directly** (`gmake <cfg>-config THORNLIST=... options=...; gmake <cfg>`,
as in §18.4's flesh-only path) **instead of via `sim build`**, these
per-configuration stored copies never get created, even after you add a
perfectly good machine `.ini`. Any `sim` command that needs to actually
*run* something (`sim create-run`, `sim run`, `sim submit`, ...) will fail
partway through, one missing piece at a time:

1. `Error: empty/missing run script for configuration <cfg>` — copy the
   machine's runscript template to `configs/<cfg>/RunScript`:
   `cp simfactory/mdb/runscripts/<name>.run configs/<cfg>/RunScript && chmod +x configs/<cfg>/RunScript`
   (and similarly `SubmitScript` from `simfactory/mdb/submitscripts/`,
   optional for `create-run`/`run` but required for `submit`/`create-submit`).
   These are **raw, unsubstituted copies** — `@PLACEHOLDER@` tokens get
   filled in later, per-restart, not at copy time. `sim build`'s own logic
   for this is in `simfactory/lib/sim-build.py` ("deal with submit script
   now" / "deal with run script now"); it's just `shutil.copy`.
2. `Error: could not read from configs/<cfg>/OptionList: ... No such file` —
   copy the optionlist too: `cp simfactory/mdb/optionlists/<name>.cfg configs/<cfg>/OptionList`.
3. `FileNotFoundError: .../exe/<cfg>` (from `copyTestsuiteData` doing
   `shutil.copytree(.../exe/<cfg>, ...)`) — this directory holds thorn
   **utility programs** (`UTIL_DIR = $(EXEDIR)/$(CONFIG_NAME)` in
   `lib/make/make.configuration`), built by a separate Makefile target
   that the normal `gmake <cfg>` build does **not** run:
   `gmake <cfg>-utils PROMPT=no`. This is required only for testsuite runs
   through SimFactory (`copyTestsuiteData`); a bare `gmake <cfg>-testsuite`
   doesn't need it. It may end up nearly empty (e.g. just a copied
   `mpirun`) if no thorn in the ThornList registers utility programs —
   that's fine, it just needs to *exist*.

None of this reconfigures or rebuilds the actual Cactus executable — it's
purely SimFactory-side bookkeeping the flesh Makefile doesn't know about.
Doing it this way (rather than just running `sim build`) avoids the risk
described next.

**Do not just run a plain `sim build` to "fix" this** if the configuration
was set up by hand and you don't want it touched: `sim build` decides
whether to reconfigure by comparing `configs/<cfg>/OptionList`'s stored
content/version against the machine's current optionlist — since that
file doesn't exist yet, `hasStoredOptions` is false, `storedOptionSettings`
is `None`, so `hasOutdatedConfig` is unconditionally `True` and it will
reconfigure, and since the "old version" (from nothing) won't match the
optionlist's `VERSION` string, `removeConfig` becomes `True` too, which
runs `<cfg>-realclean` — deleting all your compiled object files for a
full rebuild. On a slow/serial build machine that's a large, unnecessary
cost. Populate the three files by hand instead (above) to avoid ever
triggering that path.

### 19.2 Minimal machine `.ini` for a scheduler-less workstation

Base this on an existing no-scheduler machine entry if one exists in your
`simfactory/mdb/machines/` (this repo already had one written for a prior,
different personal box — grep for `submit.*nohup` across
`machines/*.ini` to find a template to copy). Key fields, differing from
a real HPC cluster entry like `frontier.ini`:

```ini
[omnia]
nickname        = omnia
name            = omnia
hostname        = omnia
aliaspattern    = ^omnia$

# Sourced automatically by SimFactory before any command it runs directly
# (build, configure, rsync for testsuite data, ...) — see §19.4. Also
# sourced a second time, explicitly, inside the custom runscript (§19.3),
# since that script can run standalone later, outside SimFactory's own
# process.
envsetup = <<EOF
... machine-specific env (see §18.3) ...
EOF

optionlist      = omnia-hip.cfg
submitscript    = generic.sub      # reused as-is; just re-execs `sim run`
runscript       = omnia.run        # custom — see §19.3
make            = make -j@MAKEJOBS@
makejobs        = 1                # match the real core budget (§18, nproc gotcha)

basedir         = /path/to/simulations
ppn             = 1
max-num-threads = 1
num-threads     = 1
nodes           = 1

# No queue: launch directly, track by PID, kill by process group.
submit          = exec nohup @SCRIPTFILE@ < /dev/null > @RUNDIR@/@SIMULATION_NAME@.out 2> @RUNDIR@/@SIMULATION_NAME@.err & echo $!
getstatus       = ps @JOB_ID@
stop            = pkill -g $(ps -o pgid= -p @JOB_ID@)
submitpattern   = (.*)
statuspattern   = "^ *@JOB_ID@ "
queuedpattern   = $^
runningpattern  = ^
holdingpattern  = $^
exechost        = echo localhost
exechostpattern = (.*)
```

`generic.sub`/`generic.run` (under `simfactory/mdb/{submitscripts,runscripts}/`)
already implement this pattern and can usually be reused for the
submitscript unchanged; write a custom runscript only when you need
something injected before Cactus actually runs (see next).

### 19.3 Custom runscript vs `envsetup` — why you may need both

`envsetup` (§19.1's table, and the wrapping in `simfactory/lib/simlib.py`,
`command = "{ %s; } && { %s; }" % (envsetup, command)`) is applied by
SimFactory **only around commands SimFactory itself executes directly** —
building, configuring, the testsuite-data rsync, invoking `make
<cfg>-testsuite`. It is **not** automatically present when a *generated*
script (the per-restart `RunScript`, written to
`<restartdir>/SIMFACTORY/RunScript` and then exec'd, possibly much later,
possibly via `nohup` from the SubmitScript) actually runs — that script is
just a plain shell script on disk at that point, invoked directly, not
through SimFactory's Python wrapping.

Concretely, this matters if your machine needs `PATH`/`LD_LIBRARY_PATH`/
fabric selection/etc. set for the actual simulation executable to run at
all (e.g. an MPI implementation that isn't on the default `PATH` — see
§14's Intel oneAPI MPI rows). Fix: write your own
`simfactory/mdb/runscripts/<name>.run` based on `generic.run`, with a
`source /path/to/env-setup.sh` line inserted right after the `#!/bin/bash`
shebang (before `set -e`), and point the machine's `runscript` key at it.

This matters especially for the test suite: `sim create-run --testsuite`
does **not** invoke your executable via a bare `mpirun -np N exe parfile`
per test. Instead (`simfactory/lib/simrestart.py`, around
`if testsuite:`), it sets an environment variable
`CCTK_TESTSUITE_RUN_COMMAND` to a small shell snippet that ends by
invoking the *prepared* `RunScript` — and Cactus's own
`lib/sbin/RunTestUtils.pl` explicitly checks for and uses
`$ENV{CCTK_TESTSUITE_RUN_COMMAND}` in place of its own default `mpirun -np
$nprocs $exe $parfile` when present. So whatever your runscript does
(including sourcing your environment) runs for **every single test**, not
just once — which is exactly the mechanism to rely on rather than fight.

### 19.4 Machine resolution: aliaspattern, `--machine`, and shared-`$HOME` gotchas

`GetMachineName()` in `simfactory/lib/simlib.py` resolves a machine name
in this order:

1. `--machine=<name>` on the command line — wins outright, skips
   everything below. Use this to sanity-check a new `.ini` immediately
   (`sim whoami --machine=<name>`, `sim print-mdb-entry <name>`) without
   fighting hostname detection first.
2. `~/.hostname`, if it exists — its *contents* (not the real `hostname`
   output) become the string matched against every machine's `hostname`/
   `aliaspattern` field. This file lives in `$HOME`, so on a networked/
   shared home directory it is **the same file, and can silently override
   machine detection, on every machine that mounts that home** — if it
   was created for one specific box, it can quietly break resolution
   everywhere else the home is mounted. If a plain `sim whoami` resolves
   to some other, unexpected machine name, check this file first before
   suspecting your new `.ini`.
3. Otherwise, the real `hostname` command output.

Whatever string results, it's matched against every machine's `hostname`
key (exact match) or `aliaspattern` (regex) in
`simfactory/mdb/machines/*.ini`. If more than one machine matches (e.g.
because of an `~/.hostname` override colliding with another entry, or two
`aliaspattern`s that are too broad), SimFactory tries to disambiguate by
checking which candidate's `sourcebasedir` is a path-prefix of the actual
Cactus checkout directory (`simenv.CACTUS_PATH`) you're running `sim`
from; only if exactly one candidate's `sourcebasedir` matches does it
resolve automatically — otherwise it warns "Could not identify machine"
and gives up. Practical implications:

- Give each machine a distinct, correct `sourcebasedir` (the directory
  *containing* that machine's Cactus checkout) — it's not just cosmetic,
  it's load-bearing for this disambiguation.
- A stale `~/.hostname` pointing at a machine whose `sourcebasedir` no
  longer exists/matches anything is a real, silent trap: it can make
  `sim whoami` resolve to nothing (or the wrong machine) from a
  perfectly good checkout. If you find one and its target machine entry's
  `sourcebasedir` doesn't exist, it's very likely safe to delete — but
  confirm with the user first, since `$HOME` is shared and you may not
  know every machine relying on it.
- You can deliberately use this mechanism instead of editing `.ini`
  `aliaspattern`s narrowly: adding the *same* alias string to two
  machines' `aliaspattern` and letting `sourcebasedir` prefix-matching
  pick the right one (based on *which checkout directory you're running
  from*) is a legitimate way to let one shared-home identity resolve
  differently depending on where `sim` is invoked from — just make sure
  the `sourcebasedir`s are actually disjoint (one isn't a parent
  directory of the other), or the disambiguation itself becomes ambiguous
  again.

### 19.5 Quick verification sequence for a new machine entry

```bash
./simfactory/bin/sim whoami --machine=<name>        # confirm the .ini parses
./simfactory/bin/sim print-mdb-entry <name>          # dump all resolved fields, sanity-check them
./simfactory/bin/sim whoami                          # confirm it resolves with no flag (real usage)
# populate configs/<cfg>/{OptionList,SubmitScript,RunScript} per §19.1
# if the config was built outside `sim build`
./simfactory/bin/sim create-run <simname> --testsuite --select-tests <Arrangement>
```

`--select-tests` accepts `all`, an `Arrangement`, an `Arrangement/Thorn`,
or a specific `<test>.par` name (see `copyTestsuiteData` in
`simfactory/lib/simrestart.py` for the exact matching rules) — useful to
scope a verification run to just the thorns you actually built, the same
way §18.4 scopes the ThornList itself.

---

*End of reference. When in doubt, read `gmake help`, `configs/<cfg>/config-info`, and the failing thorn’s `configuration.ccl` + `src/detect.sh`.*
