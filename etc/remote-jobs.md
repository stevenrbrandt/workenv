# Running jobs remotely
- You have a number of machines available on which to run remote jobs. You can find them in ~/.ssh/config tagged with a comment `# job runner`.
- The home directory is frequently a poor choice for building and running jobs. The comment `# work dir: /work/sbrandt` will identify the one you should use.
- These machines will be managed by slurm. Use sinfo to find available nodes.
- Many of these machines are heterogeneous. That means that some queues will run on a different architecture, or have one or more GPUs. You may keep metadata on the various machines in md files in the ~/.ssh/machines directory.
- Log in to machines once with ssh and sftp and keep the sessions open. Don't re-open per command or file transfer.
- You may need the help of a human to respond to prompts to login.
- Use sinfo to find open queues.
- Machines and queues can often be quirky and do things in bespoke ways.
- Use of job watchers should not poll more than once a minute on remote machines.
- Docker builds may be started on this machine or mel5

## Einstein Toolkit jobs
- Use https://github.com/einsteintoolkit/brain to understand the Einstein Toolkit.
- Compiling should be done inside a queue.
- Use simfactory. If it does not work for a given machine, we should work together to ensure that it does.
- **FIRST, ALWAYS: update simfactory to the latest master before doing any simfactory work,
  in every tree you are about to use.** The mdb is shared and moves; a stale checkout will
  have you debugging machine entries that were fixed upstream months ago.

  ```bash
  cd <cactus>/repos/simfactory2 && git fetch origin && git merge --ff-only origin/master
  ```

  If that refuses with "local changes would be overwritten", check whether the local mdb
  edits are a stale copy of work that is now upstream before you keep them -- e.g.
  `CactusFW3/repos/simfactory2` carries uncommitted mel5 edits that upstream already has.

  How this bit on 2026-10-17: two Cactus trees (watannabe and melete05) both sat at
  `97dc516`, **24 commits behind** `origin/master`. At that commit `mel5.ini` still
  described melete05 as a machine with no batch system at all -- `submit = sh @SCRIPTFILE@ &`,
  `getstatus = ps`, `stop = kill`, `ppn = 80`, `num-threads = 80` -- so `sim create-submit`
  would have forked the job on the login node instead of submitting it, and defaulted to one
  rank with 80 threads on a machine that caps a job at 12 cores. Upstream had already fixed
  exactly this in `5ed3413` ("Make the mel5 configuration actually submit through slurm") and
  `804766e` ("Make this a real simfactory build, with OpenMP actually on"), and had added
  rostam (`aadc50e`) and buran (`75ef81f`) entries. Time was spent diagnosing "broken files in
  the repo" that were not broken -- they were just old. A `git fetch` first would have cost
  seconds.
- **Do not mix `gmake` and simfactory in one tree.** A configuration created by
  `gmake <cfg>-config` has no `properties.ini`, and `sim build <cfg>` then refuses it with
  "Configuration <cfg> has no properties.ini file ... or the configuration has become
  corrupted". The fix is `rm -rf configs/<cfg>` and let `sim build` create it. (Seen on
  melete05, job 219.)
- A machine config only counts as working when a clean `sim build` from the **committed**
  optionlist produces a usable executable and `sim create-submit` runs it -- with OpenMP
  on. Check `CCTK_OPENMP_MODE = yes` in `configs/<cfg>/config-data/make.config.defn`,
  `ldd exe/cactus_sim | grep gomp`, and Carpet's "OpenMP is enabled" at runtime.
- Changing an **optionlist** needs a *reconfigure*, not just a rebuild, and only a change
  to its `VERSION` string triggers the `realclean` that discards objects built against
  the old libraries.
- Changing a **submit or run script** in `mdb/` does **not** reach an existing
  configuration. `lib/sim-build.py` copies into `configs/<cfg>/` only when there is no
  stored copy, when `--submitscript`/`--runscript` is passed explicitly, or on a
  reconfigure; a plain content change merely prints
  `warning: default run script contents have changed` and copies nothing. So pass the
  flag, or `cp` it yourself:

  ```bash
  cp simfactory/mdb/runscripts/<m>.run    configs/<cfg>/RunScript
  cp simfactory/mdb/submitscripts/<m>.sub configs/<cfg>/SubmitScript
  ```

  And there is a *third* copy: `sim create*` writes its own into
  `<simdir>/SIMFACTORY/run/`, which is what later restarts of that simulation use. Before
  trusting a run, check which version it actually executed:
  `grep map-by <simdir>/output-NNNN/SIMFACTORY/RunScript`.
- Verified per-machine details for melete05 and rostam are below.

## Checking whether a job actually worked

**`sacct` saying `COMPLETED 0:0` does not mean a Cactus run succeeded.** SimFactory
launches the executable through `ExecuteReplaceCommand` and discards the child's exit
status (`lib/simrestart.py`, `lib/simlib.py`), so a run that aborted on every rank still
exits 0 and slurm records success. This is not machine-specific; it applies wherever
SimFactory is used.

Verify a run three ways instead:

```bash
grep -c '^Done\.$' <rundir>/output-0000/<simname>.out   # runscript reached the end
ls <rundir>/output-0000/*/backtrace.*.txt 2>/dev/null   # must be empty
tail <rundir>/output-0000/<simname>.err                 # real errors land here
```

Two live examples of being fooled: jobs that ran `Funwave/test/hump_wide-1.par` on 12 and
16 ranks all died with `CarpetLib dh.cc:2103  The grid structure is inconsistent` — that
parfile's domain is 30/0.5 = 61 cells a side and cannot be split that many ways with 3
ghost zones — and every one of them was reported `COMPLETED 0:0`. **Pick a test whose
grid actually decomposes over the rank count you are testing.**

## melete05 ("mel5")

Single node, no cluster: `melete05.cct.lsu.edu` is both login and compute node.
2x Intel Xeon E5-2698 v4 (Broadwell), 20 cores/socket = 40 physical cores, 80 logical,
251 GB. One slurm partition, `batch`.

- **A job is capped at 12 physical cores** by `/etc/slurm/job_submit.lua`. The plugin
  scores the *request* as `ceil(ntasks*cpus_per_task/2)` cores, so `-n 12 -c 2` is
  accepted and `-n 16 -c 2` is rejected with
  `Rejected: jobs are limited to 12 cores (24 CPUs)`. Beware: the submit script passes
  `--hint=nomultithread`, so the *allocation* is twice the request in CPUs -- asking for
  24 CPUs yields `AllocCPUS 48`, i.e. 24 real cores, and the plugin does not notice.
  `ppn = 12` in the mdb entry keeps request and allocation both inside the policy.
- **Launch with `mpirun`, never `srun`.** The system OpenMPI 4.1.6 is not built with
  slurm PMI/PMIx, so `srun` fails with `MPI_Init_thread on a NULL communicator`.
- **`mpirun` needs explicit binding.** Unbound, every rank gets the whole NUMA node and
  OpenMPI's default `--map-by socket` oversubscribes half the ranks, because slurm hands
  out an asymmetric cpuset. The runscript uses
  `--map-by slot:PE=@NUM_THREADS@ --bind-to core --report-bindings`.
- Dependencies are **Ubuntu 24.04 system packages**, not the spack view under
  `/home/sbrandt/spack`. That view has OpenMPI 5.0.5 while `mpirun` is 4.1.6; mixing them
  gives `libmpi_cxx.so.40: undefined symbol: ompi_mpi_errors_throw_exceptions`.
- Cactus tree: `/home/sbrandt/newrepos/boussinesx/CactusFW3`. Note `/home`, not `/work`.
- Build inside the queue (`sbatch` a script that calls `sim build`); `makejobs = 12`
  matches the cap.

### Prebuilt third-party libraries: /opt/etk  (do NOT rebuild these per user)

`/opt/etk/ubuntu24-gcc13-ompi4` is a root-owned, world-readable tree built once on
2026-10-17 so that nobody has to build these again:

    ADIOS2  AMReX  BLAS  Boost  LAPACK  LORENE  NSIMD  Silo  openPMD  ssht     (2.3 GB)

`mel5.cfg` points at them, so a CarpetX/AsterX/nuX thornlist now configures in seconds
instead of spending ~15 minutes rebuilding 2.3 GB into `configs/<cfg>/scratch/external`
-- per configuration, per user.  `/opt/etk/<tree>/README` carries the provenance.

Ubuntu genuinely does not package ADIOS2, AMReX, openPMD, Silo, LORENE, NSIMD, ssht or a
linkable Boost.  It *does* package BLAS and LAPACK (`libblas-dev`, `liblapack-dev`, netlib
3.12.0 -- the same reference implementation); those two are in the tree only for a
self-consistent stack, and using the system ones needs
`BLAS_DIR = /usr/lib/x86_64-linux-gnu` spelled out, because `ExternalLibraries/BLAS`
searches `/usr/lib` and `/usr/lib64` but not the multiarch directory.

- The directory name records the toolchain the `.a` files are tied to: **gcc 13.3 and the
  system OpenMPI 4.1.6**, which is what `mel5.cfg` selects and what `mel5.run` launches.
  They are not compatible across either, so if the distro compiler or the default MPI
  changes, build a *new* tree beside this one; do not overwrite it.
- The libraries are **baseline x86-64**: they were built before `-march=broadwell` went
  into `mel5.cfg`, so they carry no AVX2 (`objdump -d libamrex_3d.a | grep -c '%ymm'` is
  0). That is safe -- only Cactus itself is compiled `-march=broadwell`. Rebuild the tree
  if you want the libraries vectorised too.
- They were built by the Cactus ExternalLibraries thorns themselves, so the layout is
  exactly what those thorns expect. To refresh:

  ```bash
  # In a SCRATCH COPY of mel5.cfg set each of the ten to the literal string BUILD:
  #     ADIOS2_DIR = BUILD    AMREX_DIR = BUILD    ... etc
  # Do NOT simply delete the lines: Boost, BLAS and LAPACK would then be found under
  # /usr and never built, leaving an incomplete tree -- and Boost found under /usr is
  # exactly the "cannot find -lboost_filesystem" failure described below.
  sim build <cfg> --optionlist=<scratch copy> --thornlist=<one activating all ten>

  # /opt/etk is root-owned, so installing needs sudo:
  sudo mkdir -p /opt/etk/<new-name>
  sudo cp -a configs/<cfg>/scratch/external/. /opt/etk/<new-name>/
  sudo chown -R root:root /opt/etk/<new-name>
  sudo chmod -R a+rX /opt/etk/<new-name>

  # Rewrite the builder's home out of the three files that bake it in, or
  # pkg-config / find_package / libtool users get a nonexistent prefix:
  sudo sed -i 's|<the builder .../scratch/external path>|/opt/etk/<new-name>|g' \
    /opt/etk/<new-name>/openPMD/lib/pkgconfig/openPMD.pc \
    /opt/etk/<new-name>/ADIOS2/lib/cmake/adios2/thirdparty/dill-config.cmake \
    /opt/etk/<new-name>/Silo/lib/libsiloh5.la
  ```
- What is NOT here, deliberately: GSL, HDF5 (serial), MPI, hwloc, libjpeg, zlib, yaml-cpp
  and FFTW3 all come from Ubuntu packages. **Boost does not** -- `libboost-dev` is headers
  only and no `libboost_filesystem`/`libboost_system` runtime package is installed (only
  date-time, regex and serialization), so the Boost thorn asks for `-lboost_filesystem`
  the moment it sees headers under /usr and the link fails with
  `cannot find -lboost_filesystem`. That is why Boost is in the prebuilt stack rather than
  set to NO_BUILD. The prebuilt Boost is **1.55** -- the version bundled with the thorn,
  older than the system 1.83 and ahead of it on the include path. Installing
  `libboost-filesystem-dev` + `libboost-system-dev` (~2 MB) and setting `BOOST_DIR = /usr`
  is the lighter alternative if that ever matters.

Verified on 2026-10-17 (jobs 224/225): a clean `sim build` from the committed `mel5.cfg`
with `configs/nux` deleted finished in 12 minutes with 0 errors and an empty
`scratch/external`, all ten capability defns resolving to /opt/etk; `sim create-submit`
then ran it through slurm with `OMP_NUM_THREADS=2`, no backtraces, and the thorn's own
self-test passing.

Two honest caveats on that verification:
  * It is **link-level** for most of the stack. The acceptance run was a 2-second CarpetX
    self-test, which exercised MPI and OpenMP; ADIOS2, openPMD, Silo, LORENE, ssht, BLAS,
    LAPACK and Boost were linked but never called.
  * It used **locally patched thorn sources**, not a pristine checkout: `BNSTools/RNSReader`
    with the `ALL_UTILS` line disabled (see the next section) and `SpacetimeX/Cartoon2DX`
    + `TestCartoon2DXVector` with uncommitted fixes. Anyone reproducing it from committed
    sources alone will hit the RNSReader `utils` failure.

### `sim build` builds `utils`; `gmake <config>` does not

This is a real difference, not a detail. BNSTools/RNSReader declares
`ALL_UTILS += RNS RNS_readID` in `src/make.configuration.defn` but ships neither `RNS.c`
nor `RNS_readID.c` -- the utility rule builds `<util>.o` from `$(SRC_DIR)/<util>.c`, and
those two files simply do not exist -- so `make utils` dies with
`No rule to make target '<exe>/<config>/RNS', needed by 'utils'`.
A plain `gmake <config>` never builds that target and so never notices. If a build
succeeds under gmake and fails under simfactory at the very end, look here first.

Verified recipe (2026-10-15):

```bash
ssh mel5
C=/home/sbrandt/newrepos/boussinesx/CactusFW3
# build -- inside the queue, 12 cores
sbatch --wrap="cd $C && ./simfactory/bin/sim build sim \
  --optionlist=simfactory/mdb/optionlists/mel5.cfg \
  --thornlist=configs_input/ThornList" -p batch -t 4:00:00 -N1 -n1 -c 12 --hint=nomultithread
# run -- --procs is TOTAL cores; num-threads=2 makes it 6 ranks x 2 threads
cd $C && ./simfactory/bin/sim create-submit <name> --parfile=<par> --procs=12 --walltime=<hh:mm:ss>
```

`mars/mel5_smoke.par` in the CactusFW3 tree is a 200-iteration smoke test on the real
Mars grid; use it rather than `hump_wide-1.par`, which cannot decompose past a few ranks.

## rostam

Heterogeneous: **every partition is different hardware**, so each needs its own mdb entry
*and* its own optionlist. The login node, the `medusa` partition, and the `buran`
partition are configured. The other partitions are not.

    medusa (default) 16 nodes  Intel Xeon Gold 6148  40 cores   94 GB   AVX-512
    buran            16 nodes  AMD EPYC 7352         48 cores  252 GB   NO AVX-512
    marvin           16 nodes  16 cores                         37 GB
    risc5             2 nodes  64 cores
    plus cuda / V100 / A100 / DGX-A100 / mi100 / spark (aarch64)

- `rostam.cfg` compiles with `-mavx512f` and friends. medusa's Xeon 6148 has AVX-512.
  buran's EPYC 7352 does not, and that binary gets `SIGILL` there. The buran optionlist
  is `buran.cfg`. See the buran recipe below.
- `srun` works here (unlike mel5) and binds ranks by default.
- No slurm accounting enforcement: supply no allocation, and keep `--account` out of the
  submit script. A placeholder like `NO_ALLOCATION` is silently ignored and the job
  charges the default association, which hides the problem until you move to a site that
  enforces associations.
- Cactus tree: `/work/sbrandt/CactusFW3`. `/work`, not `/home`.
- Jobs re-resolve nothing: the submit templates pass `--machine=@MACHINE@` substituted on
  the login node, so `aliaspattern` does not affect submitted jobs. It *does* affect
  running `sim` by hand inside an `srun`/`salloc` shell, where a login-node-only pattern
  gives `Current machine: None`.
- **`rostam.cfg` still hardcodes a dependency tree under `/work/sbrandt`**
  (OpenMPI 4.0.6, HDF5, FFTW3, ...), which nobody else can read. The directory
  permission is not the thing to fix -- the hardcoded path is. An up-to-date Einstein
  Toolkit finds these itself: with `MPI_DIR = NO_BUILD` and no `MPI_INC_DIRS`/`LIB_DIRS`,
  `ExternalLibraries/MPI` asks `mpic++ --showme`, and a library it cannot find is built
  from source into `configs/<cfg>/scratch/external`. `mel5.cfg` was converted to that
  form and builds cleanly; rostam has not been converted yet, because it needs a rebuild
  and a rerun to confirm. The externals tree exists only because the sole modulised MPI
  here is OpenMPI 5.x, which dropped the MPI C++ bindings -- but nothing in the Funwave
  thornlist uses them, so a module or self-built MPI is very likely fine.
- rostam is the only machine here whose SSH key can push to Bitbucket.

Verified recipe (2026-10-13):

```bash
ssh rostam
C=/work/sbrandt/CactusFW3
# build -- inside the queue
sbatch -p medusa -N1 -n1 -c 20 -t 4:00:00 --wrap="cd $C && ./simfactory/bin/sim build sim \
  --optionlist=simfactory/mdb/optionlists/rostam.cfg --thornlist=configs_input/ThornList"
# run -- num-threads=2, so --procs=32 is 16 ranks x 2 threads on one node
cd $C && ./simfactory/bin/sim create-submit <name> --parfile=<par> --procs=32 --ppn-used=32 --walltime=<hh:mm:ss>
```

### buran

AMD EPYC 7352. `lscpu` on buran09 (2026-10-15): 2 sockets x 24 cores, 1 thread per
core, 48 CPUs, no AVX-512 flag. `MemTotal` 263173852 kB. Slurm `RealMemory` is
252909 MB. 16 nodes. `srun` binds ranks. No `--account`.

`rostam.cfg` is AVX-512. A binary that executed `vmovapd %zmm0` (`gcc -O0 -mavx512f`)
got `SIGILL` on buran09. The buran optionlist is `buran.cfg`: `-mavx2 -mfma`,
`VERSION = buran-2026-10-15`, OpenMP on, same OpenMPI 4.0.6 tree under
`/work/sbrandt/etk/externas-rostam`. A 2-rank MPI hello ran on buran09. UCX warns
that the loaded `libucp` is 1.17 and the library wants >= 1.18, and `mlx5_0` does
not initialise. The single-node smoke still finished. Multi-node buran is not verified.

Machine entry `buran` (`buran.ini`): `ppn = 48`, `min-ppn = 1`, `num-smt = 1`,
`max-num-threads = 48`, `makejobs = 16`, `queue = buran`, `memory = 252909`,
`num-threads = 2` carried over from the medusa timing and not remeasured here.
`aliaspattern = ^buran[0-9]+`. `hostname = buran00`, so a login-node `sim whoami`
still resolves to `rostam`. Pass `--machine=buran`. Submit and run scripts are
`buran.sub` and `buran.run` (`srun`, `--exclusive`, no `--account` line).

Committed and pushed to `https://bitbucket.org/simfactory/simfactory2` master as `75ef81f0` (`Add the buran partition on rostam.`). The four files are `mdb/machines/buran.ini`, `mdb/optionlists/buran.cfg`, `mdb/submitscripts/buran.sub`, and `mdb/runscripts/buran.run`. HTTPS push to Bitbucket returns 410 because app passwords are retired. The push went over SSH from rostam: `git@bitbucket.org:simfactory/simfactory2.git`.

`buran.cfg` sets `NSIMD_DIR = BUILD`. The prebuilt library in `externas-rostam` is Skylake 512-bit only, which is illegal on this CPU. `detect.sh` then builds SIMD CPU into the configuration scratch. The Funwave smoke did not include NSIMD, so that from-source build has not been run. The other prebuilt libraries under `/work/sbrandt/etk/externas-rostam` are unchanged, and `/work/sbrandt` is mode 700, so this optionlist builds for its owner.

Verified on CactusFW3 (2026-10-15) before the NSIMD line was changed. The etk checkout is the one that was pushed. It has not been built.

```bash
ssh rostam
C=/work/sbrandt/CactusFW3
# build -- inside the queue, 16 cores. Produces exe/cactus_buran.
sbatch -p buran -N1 -n1 -c 16 -t 4:00:00 --wrap="cd $C && ./simfactory/bin/sim build buran \
  --machine=buran --optionlist=simfactory/mdb/optionlists/buran.cfg \
  --thornlist=configs_input/ThornList"
# run -- --procs is total threads. num-threads=2 makes --procs=4 into 2 ranks x 2 threads.
cd $C && ./simfactory/bin/sim create-submit <name> --machine=buran --configuration=buran \
  --parfile=<par> --procs=4 --num-threads=2 --ppn-used=4 --walltime=<hh:mm:ss>
```

Job 210715 built `exe/cactus_buran`. `CCTK_OPENMP_MODE = yes`, `ldd` links `libgomp.so.1`,
and the stored `CFLAGS` are `-mavx2 -mfma`. Job 210717 (`buran-smoke2`, 2 ranks, 2 threads,
buran09) printed `OpenMP is enabled`, reached iteration 1, and printed `Done.`
`/work/sbrandt/tmp-buran-probe/smoke.par` is that one-iteration grid. The first submit,
`buran-smoke`, aborted because `IOASCII` needs `CarpetSlab`. That was the parameter file.

Pushing to Bitbucket from here: apply patches to a clone on rostam and push from there,
then `git fetch rostam:<path> master` back to the workstation to realign hashes. The
workstation has no Bitbucket key, and its stored app password is dead -- Atlassian retired
app passwords, so an HTTPS push returns HTTP 410.

## Sizing Cactus jobs

MPI ranks are worth more than threads, but filling a node with ranks is *absolutely*
slower, not merely inefficient. Measured on medusa with a 1.56M-cell Funwave problem
(`mars/hybrid_probe_medusa.out` in CactusFW3):

    ranks x threads   cores   ms/step
         40 x 1         40      903.1
         20 x 2         40      650.1
         16 x 2         32      621.8   <- best
         16 x 1         16      650.5
         10 x 4         40      877.9

Use ~2 threads per rank and keep the rank count high; 4 threads is already too few ranks.
Multi-node scaling of this problem is poor -- 4x the nodes bought 1.25x -- so for
parameter studies run several independent jobs on one node each rather than one wide job.
