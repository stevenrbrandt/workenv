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
