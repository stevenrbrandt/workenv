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

*End of reference. When in doubt, read `gmake help`, `configs/<cfg>/config-info`, and the failing thorn’s `configuration.ccl` + `src/detect.sh`.*
