# Cactus / Einstein Toolkit — Developer Reference

Assembled from `repos/flesh/doc/{UsersGuide,ReferenceManual,MaintGuide,FAQ,ReleaseNotes}`
cross-checked against the live source tree at
`/home/sbrandt/.cactup/cacti/Ticket2961/Cactus` (flesh = `repos/flesh`, thorns under
`arrangements/*` → symlinked into `repos/*`). Verified 2026-08-20.

Every doc claim below that was spot-checked against source is cited `file:line`. Known
places where the shipped documentation is wrong, stale, or silent are collected in
**§7 Known Documentation Issues** — check there before trusting an edge case from the
LaTeX sources directly.

## Table of Contents
1. [Overview & Checkout Layout](#1-overview--checkout-layout)
2. [Writing and Modifying Thorns](#2-writing-and-modifying-thorns)
3. [CCTK Core API Reference — Part 1](#3-cctk-core-api-reference--part-1)
4. [CCTK Core API Reference — Part 2, Driver, Util](#4-cctk-core-api-reference--part-2-driver-util)
5. [Build System & Maintainer Internals](#5-build-system--maintainer-internals)
6. [FAQ, Reference Tables & Recent Changes](#6-faq-reference-tables--recent-changes)
7. [Known Documentation Issues (consolidated)](#7-known-documentation-issues-consolidated)

---

## 1. Overview & Checkout Layout

**What this is.** Cactus is a "flesh + thorns" framework: a small core (the *flesh*,
`repos/flesh/src`) provides parameter parsing, scheduling, variable/grid-group
management, and driver/IO APIs; application code lives in *thorns* grouped into
*arrangements* (e.g. `CactusBase`, `EinsteinEvolve`). The Einstein Toolkit (ET) is a
curated arrangement/thorn set for numerical relativity built on the flesh. A thorn is
always addressed as `<Arrangement>/<Thorn>` (e.g. `CactusBase/CartGrid3D`) — in
ThornLists, `ActiveThorns`, and parameter files.

**How this checkout is actually laid out** (root = repo root):
- `repos/` — real git checkouts, one per source repository (`repos/flesh`,
  `repos/cactusbase`, `repos/einsteinevolve`, `repos/simfactory2`, `repos/manifest`,
  `repos/CRL`, `repos/einsteinexamples`, ~30 `ExternalLibraries-*`, etc). Each still has
  its own `.git`; e.g. `repos/flesh` → `bitbucket.org/cactuscode/cactus.git`, checked
  out at `ET_2026_05`.
- `arrangements/<Arrangement>/<Thorn>` — **symlinks**, not real directories, into the
  matching `repos/*` checkout: `arrangements/CactusBase/Boundary ->
  ../../repos/cactusbase/Boundary`. This is how the flesh build system (which expects
  thorns under `arrangements/`) finds thorns living in separately-cloned per-arrangement
  repos. Note the case difference: `repos/*` names are lowercase, `arrangements/*`
  names are canonical CamelCase.
- `repos/manifest/einsteintoolkit.th` and `thornlists/installation-default.th` are
  identical (`diff` → exit 0): a **Component Retrieval Language (CRL)** file consumed by
  `bin/GetComponents` (→ `repos/CRL/GetComponents`, a Perl script from
  `github.com/gridaphobe/CRL`). Each repo gets a `!DEFINE`/`!TARGET`/`!TYPE`/`!URL`/
  `!REPO_BRANCH`/`!CHECKOUT` block, `ET_RELEASE = ET_2026_05` in this checkout, then a
  flat alphabetical `Arrangement/Thorn` list telling GetComponents which subdirs to
  symlink into `arrangements/`. `bin/GetComponents --update --root=. thornlists/installation-default.th`
  reproduces/updates the checkout. **This whole mechanism is Einstein-Toolkit tooling
  and is not documented in the flesh UsersGuide.**
- Top-level symlinks: `doc -> repos/flesh/doc`, `lib -> repos/flesh/lib`,
  `src -> repos/flesh/src`, `manifest -> repos/manifest`,
  `par -> repos/einsteinexamples/par` (example parfiles, e.g. `par/qc0-mclachlan.par`,
  `par/GW150914/`), `simfactory -> repos/simfactory2`. `Makefile`, `README.md`,
  `COPYRIGHT`, `CONTRIBUTORS`, `.clang-format` are likewise symlinked from
  `repos/flesh`.
- `configs/<name>/` — build output for one named configuration (here: `configs/sim/`).
  Contains `ThornList` (the thornlist actually used — byte-identical to
  `thornlists/installation-default.th` here, since the flesh's ThornList parser ignores
  `#`/`!`-prefixed lines, so a full CRL file works as a ThornList directly),
  `config-info`, `config-data/` (autoconf output: `cctk_Config.h`, `make.config.defn`,
  ...), `bindings/` (CST-generated glue from thorns' `.ccl` files), `build/<Thorn>/`,
  `lib/libthorn_<Thorn>.a`, `scratch/` (Fortran `.mod` files).
- `simfactory` (= `repos/simfactory2`) — the higher-level run/build tool ("Simulation
  Factory"). `./simfactory/bin/sim` (bash wrapper execing `sim.py` via python3) is the
  normal entry point for `sim build`, `sim create-run --parfile=... --procs=N`, restart
  management, and per-machine config (`mdb/machines/*.ini`, `mdb/optionlists/`,
  `mdb/runscripts/`). Also Einstein-Toolkit-specific, not in the flesh UsersGuide.

**Configuring/building** (flesh UsersGuide, `Notes.tex`, still accurate against this
checkout):
- `gmake <config>` creates/builds a named configuration; first build prompts for a
  ThornList unless `THORNLIST=<file>` is given.
- Options: env vars + `gmake <config>-config`, `${HOME}/.cactus/config`,
  `CACTUS_CONFIG_FILES=<list>`, or `gmake <config>-config options=<file>`.
- Confirmed Makefile targets (`repos/flesh/Makefile`): `<config>`, `<config>-config`,
  `<config>-reconfig`, `<config>-build BUILDLIST=...`, `<config>-clean`/`-realclean`/
  `-delete`, `<config>-editthorns`/`-thornlist`, `<config>-testsuite`,
  `<config>-ThornGuide`, `<config>-utils`, plus `help`, `configinfo`, `distclean`,
  `newthorn`, `TAGS`/`tags`, `UsersGuide`/`ReferenceManual`/`ArrangementDoc`/
  `ThornDoc`/`AllDoc`. The Makefile calls itself via `$(MAKE)`, so plain `make` works.

**Running.** Executables are `cactus_<config>`. `./cactus_<config> <parfile> [options]`.
Parameter files (`*.par`) start with `ActiveThorns = "..."`, then
`thorn::parameter = value` lines. CLI flags: `-O`/`--describe-all-parameters`,
`-S`/`--print-schedule`, `-T`/`--list-thorns`, `-L`/`-W`/`-E` logging/warning/error
levels, `-r`/`-R` redirect, `--parameter-level=strict|normal|relaxed`. In practice, use
`./simfactory/bin/sim create-run <name> --parfile=<par> --procs=N` instead of invoking
`cactus_sim` directly — simfactory handles machine-specific MPI launch commands,
directories, and restarts, none of which the flesh UsersGuide covers.

**Thorn directory conventions:** `interface.ccl`, `param.ccl`, `schedule.ccl`
(+ optional `configuration.ccl`), `src/`, usually `par/` (example parfiles) and
`doc/documentation.tex` (aggregated into a ThornGuide via `gmake <config>-ThornGuide`).

---

## 2. Writing and Modifying Thorns

*This is the single most important section for fixing bugs/adding features.* CCL
("Cactus Configuration Language") files are parsed by a Piraha PEG grammar; the
authoritative grammars live at `repos/flesh/src/piraha/pegs/{interface,param,schedule,config}.peg`
and are ground truth for anything ambiguous in the prose docs below.

### 2.1 `interface.ccl`
Header: `implements: <name>`, optional `inherits: <impl>[,...]`, `friend: <impl>[,...]`
— inheritance transitive, friendship transitive (`ApplicationThorns.tex:230-275`,
`interface.peg:26-28`). Example: `repos/mclachlan/ML_BSSN/interface.ccl:3-5`
(`implements: ML_BSSN` / `inherits: ADMBase Boundary GenericFD Grid TmunuBase`,
space-separated).

Variable access levels: **`public:`/`protected:`/`private:`** only (default private) —
bare line, not per-declaration (`ApplicationThorns.tex:305-309`, `interface.peg:53`).
This is a *different* vocabulary from `param.ccl`'s `global`/`restricted`/`private`.

Includes: `USES INCLUDE [SOURCE|HEADER]: <file>`, `INCLUDE[S] [SOURCE|HEADER]: <file> in <file>`
(`Appendices.tex:440-441`).

**Group declaration syntax:**
```
<data_type> <group_name>[[<vector_size>]] [TYPE=SCALAR|GF|ARRAY] [DIM=n]
  [TIMELEVELS=n] [SIZE=...] [DISTRIB=DEFAULT|CONSTANT] [GHOSTSIZE=...]
  [TAGS='k=v ...'] [STAGGER=...] [CENTERING={...}]
  { vars } "description"
```
(`ApplicationThorns.tex:990-1000`, `Appendices.tex:511-595`). Data types `CHAR/BYTE/
INT/REAL/COMPLEX`, optional size suffix (`CCTK_INT1/2/4/8`, `CCTK_REAL4/8/16`,
`CCTK_COMPLEX8/16/32`), case-insensitive, `CCTK_` prefix optional. Default
`TYPE=SCALAR`, default `DIM=3`, default 1 timelevel. Examples:
`repos/cactusbase/Time/interface.ccl:7-11`, `repos/einsteinevolve/GRHydro/interface.ccl:415`.

- **`TAGS='...'`** is a free-form key/value string (`Util_TableSetFromString`); the CST
  doesn't interpret it. Real driver-specific keys not in either UsersGuide chapter:
  `tensortypealias`, `tensorweight`, `Prolongation`, `checkpoint="no"` — see
  `repos/mclachlan/ML_BSSN/interface.ccl:48`,
  `repos/cactusnumerical/SummationByParts/interface.ccl:141,146`,
  `repos/einsteinevolve/GRHydro/interface.ccl:419-430`.
- **`STAGGER=` / `CENTERING={...}`** — grammar-level attributes
  (`interface.peg:62,65,72`) used by CarpetX/multipatch-era thorns for vertex- vs
  cell-centered variables, e.g. `repos/SpacetimeX/TestNewRadX/interface.ccl:11`
  (`CENTERING={VVV}`), `repos/GRHayLET/GRHayLHDX/interface.ccl:15`. **Not documented
  in either ApplicationThorns.tex or the Appendix** (see §7).

**Function aliasing** (declared here, not a separate file):
```
<ret_type> FUNCTION <alias>(<type> <IN|OUT|INOUT> [ARRAY] <arg>, ...)
REQUIRES FUNCTION <alias>      # caller, hard dependency
USES FUNCTION <alias>          # caller, optional — guard with CCTK_IsFunctionAliased
PROVIDES FUNCTION <alias> WITH <impl_fn> LANGUAGE C|Fortran   # provider
```
`SUBROUTINE` = `void FUNCTION`. Return type restricted to `void|CCTK_INT|CCTK_REAL|
CCTK_COMPLEX|CCTK_POINTER|CCTK_POINTER_TO_CONST`; argument types add `STRING`;
function-pointer args use `CCTK_FPOINTER` (no nesting) (`ApplicationThorns.tex:4361-
4453`). Example: `repos/cactusbase/Boundary/interface.ccl:12-22` — note the provider
thorn also does `USES FUNCTION` on its own alias so it can call it generically.

### 2.2 `param.ccl`
Access levels **`global:`/`restricted:`/`private:`** (default private); `shares:
<implementation>` pulls in another thorn's restricted parameters, entries then
prefixed `USES` (keep range, no default allowed) or `EXTENDS` (add values, no default
allowed) (`ApplicationThorns.tex:323-332,408-444`, `param.peg:18-20,49,60-70`).
Example: `repos/cactusbase/Boundary/param.ccl:4-6` (`shares: cactus` /
`USES KEYWORD presync_mode`).

Types: `INT`, `REAL`, `KEYWORD`, `STRING`, `BOOLEAN` (`CCTK_` prefix optional), each
with type-specific range syntax (`lower:upper:stride`, `(`/`)`/`[`/`]` open/closed,
`*` = infinity for INT/REAL; quoted-list/regex for KEYWORD/STRING; no range for
BOOLEAN).

Per-parameter modifiers on the declaration line: `AS <alias>`,
**`STEERABLE=NEVER|ALWAYS|RECOVER`** (only these three spellings — the CST parser
`CreateParameterBindings.pl:466-482` rejects anything else, case-insensitive),
`ACCUMULATOR=<expr of x,y>`, `ACCUMULATOR-BASE=<parameter name>` (may be
fully-qualified `thorn::param`, unlike `schedule.ccl`'s `STORAGE:` timelevel
parameter which must be unqualified). Real accumulator pair: base
`repos/cactusnumerical/MoL/param.ccl:10` fed by
`repos/mclachlan/ML_BSSN/param.ccl:302` (`ACCUMULATOR-BASE=MethodofLines::MoL_Num_Evolved_Vars`).

⚠️ **`Appendices.tex:764` prose says `RECOVERY`, not `RECOVER`** — this is a doc bug,
the parser only accepts `RECOVER` (see §7).

### 2.3 `schedule.ccl`
Full grammar (`Appendices.tex:838-854`, `schedule.peg:51-74`):
```
schedule [GROUP] <name> [AT <bin>|IN <group>] [AS <alias>] [WHILE <var>] [IF <var>]
         [BEFORE|AFTER <item>|(<item> <item>...)]
{
  LANG: C|FORTRAN
  OPTIONS: <opt>[,...]
  TAGS: <key=value>[,...]
  STORAGE: <group>[[timelevels]][,...]
  READS: <group-or-var>[(region)][,...]
  WRITES: <group-or-var>[(region)][,...]
  INVALIDATES: <group-or-var>[,...]     # grammar-valid, see §7 — undocumented, unused in this checkout
  SYNC: <group>[,...]
  TRIGGERS: <group>[,...]
} "description"
```
- **`AT`/`IN` are both optional at the grammar level** (`schedule.peg:38-39`) — you can
  declare a "bare" `schedule GROUP Foo { } "..."` with no location, later populated
  `IN Foo` from other thorns. Example: `repos/cactusbase/Boundary/schedule.ccl:17-19`
  (declares `GROUP ApplyBCs`), consumed by
  `repos/EinsteinExact/KerrSchild/schedule.ccl:148` (`schedule group ApplyBCs ... in MoL_PostStep after ...`).
- `LANG: C` also covers C++ (`extern "C"` linkage).
- `STORAGE:` timelevels: a literal or an **unqualified**, thorn-local integer
  parameter name (`0` deactivates storage); `thorn::param` is *not* allowed here.
- **`READS`/`WRITES` regions**: `ApplicationThorns.tex:563-564` only lists
  `EVERYWHERE, INTERIOR, BOUNDARY` — the real/complete set (Appendix + grammar) is
  `EVERYWHERE|ALL|INTERIOR|IN|INTERIORWITHBOUNDARY|BOUNDARY|scalar`; default region is
  `EVERYWHERE` for READS, `INTERIOR` for WRITES. (See §7 — the main chapter is
  incomplete here.)
- `OPTIONS`: `meta[-early/-late]`, `global[-early/-late]`, `level`, `singlemap`,
  `local` (default), plus at most one `loop_meta|loop_global|loop_level|
  loop_singlemap|loop_local`.
- Conditionals: `if (CCTK_Equals(param,"value")) { ... }` — **`else`/`else if` chains
  are legal** (`schedule.peg:65-69`) though the main chapter only shows a bare `if`.
  Real 4-way chain: `repos/cactusbase/Time/schedule.ccl:13-62`.
- Top-level (outside any block) `STORAGE: group[,...]` toggles storage for the whole
  run, independent of file position.
- Standard schedule bins, in execution order (verified against
  `src/main/CactusDefaultInitialise.c`/`CactusDefaultEvolve.c`/`ScheduleInterface.c`
  and the canonical list in `lib/sbin/ScheduleParser.pl`'s `@schedule_bins`):
  ```
  CCTK_RECOVER_PARAMETERS, CCTK_STARTUP, CCTK_WRAGH, CCTK_PARAMCHECK,
  CCTK_PREREGRIDINITIAL, CCTK_POSTREGRIDINITIAL, CCTK_BASEGRID, CCTK_INITIAL,
  CCTK_POSTINITIAL, CCTK_POSTRESTRICTINITIAL, CCTK_POSTPOSTINITIAL,
  CCTK_RECOVER_VARIABLES, CCTK_POST_RECOVER_VARIABLES, CCTK_CPINITIAL,
  CCTK_CHECKPOINT, CCTK_PREREGRID, CCTK_POSTREGRID, CCTK_PRESTEP, CCTK_EVOL,
  CCTK_POSTRESTRICT, CCTK_POSTSTEP, CCTK_ANALYSIS, CCTK_TERMINATE, CCTK_SHUTDOWN
  ```
  `CCTK_RECOVER_PARAMETERS` is special-cased: no grid variables, routines run
  alphabetical-by-thorn until one returns positive, `BEFORE/AFTER/WHILE/IF` ignored.
  Routines scheduled at `CCTK_STARTUP`/`CCTK_SHUTDOWN`/`CCTK_RECOVER_PARAMETERS` take
  **no** `CCTK_ARGUMENTS` — signature is `int fn(void)`, not the usual
  `void fn(CCTK_ARGUMENTS)`. This is an easy new-thorn mistake (also flagged by
  FAQ:1143-1151 as a segfault-right-after-schedule-print symptom).
  Only in the `ANALYSIS` bin: if two routines trigger on the same variable, the
  *first* scheduled one runs and the second is skipped, by design (FAQ:1450-1457).

### 2.4 `configuration.ccl`
```
PROVIDES <Capability> { SCRIPT <script>  [VERSION <ver>]  LANG <lang>  [OPTIONS <opt>[,...]] }
REQUIRES <Capability> [(<op><version>)]     # op in << <= = >= >>
OPTIONAL <Capability> { DEFINE <macro> }
```
⚠️ `ApplicationThorns.tex:741-746` only shows `SCRIPT`/`LANG` inside `PROVIDES {...}` —
`VERSION` and `OPTIONS` are real and pervasive (`repos/ExternalLibraries-LORENE/configuration.ccl`)
but only appear in the Appendix (§7). Config-script output vocabulary:
`BEGIN/END DEFINE`, `INCLUDE_DIRECTORY`, `BEGIN/END MAKE_DEFINITION`,
`BEGIN/END MAKE_DEPENDENCY`, `LIBRARY`, `LIBRARY_DIRECTORY`.

### 2.5 Grid variables in code
Group types: `SCALAR` (not communicated), `GF` (grid function, driver-uniform
size/ghostzones), `ARRAY` (like GF, own `SIZE`/`GHOSTSIZE`/`DISTRIB`). Timelevels
rotate each step; current level has no suffix, previous levels get `_p`, `_p_p`, ...
In C, data is Fortran-style laid out (first index fastest); index with
`CCTK_GFINDEX3D(cctkGH,i,j,k)` or the loop macros
`CCTK_LOOP{1,2,3}_{ALL,INT,BND,INTBND}(name,cctkGH,i,j,k[,ni,nj,nk]) { ... }
CCTK_ENDLOOP...(name);` (macros in `repos/flesh/src/include/cctk_Loop.h`, e.g.
`CCTK_LOOP1_ALL` at line 444), typically wrapped in `#pragma omp parallel`. Verified
match: `repos/cactustest/TestLoop/src/TestLoopC.c:20-24`. In Fortran, GFs are simply
`rho(i,j,k)`.

### 2.6 `CCTK_ARGUMENTS` / parameters in routines
`#include "cctk_Arguments.h"`, then `DECLARE_CCTK_ARGUMENTS` (all thorn-visible
variables) or `DECLARE_CCTK_ARGUMENTS_CHECKED(<function_name>)` (only variables named
in that routine's `READS`/`WRITES`, declared `const`/`intent(in)`). The `_CHECKED`
macro literally expands to `DECLARE_CCTK_ARGUMENTS_<funcname>`
(`lib/sbin/rdwr.pl:484`) — a CST-generated per-function macro thorns can also call
directly, e.g. `repos/cactusnumerical/SummationByParts/src/DeltaInitial.F90:15`.
Real full example: `repos/cactusnumerical/MoL/src/RK3.c:65-69` (also shows the
`CCTK_FILEVERSION(...)` convention, not mentioned in ApplicationThorns.tex — see
§2.8/§5 style notes).

Standard `CCTK_ARGUMENTS` fields: `cctkGH, cctk_dim, cctk_lsh, cctk_ash, cctk_gsh,
cctk_iteration, cctk_delta_time, cctk_time, cctk_delta_space, cctk_nghostzones,
cctk_origin_space`.

Parameters: `#include "cctk_Parameters.h"`, `DECLARE_CCTK_PARAMETERS` — these are
**read-only local copies**; calling `CCTK_ParameterSet` does not change the value seen
in the *calling* routine (FAQ:1477-1489). KEYWORD/STRING params are opaque C string
pointers in Fortran — use `CCTK_Equals`/`CCTK_FortranString`, not Fortran string ops
(FAQ:1419-1427). BOOLEAN params are not Fortran LOGICAL — no portable machine
representation (FAQ:1504-1509).

No grid variables/`CCTK_ARGUMENTS` in `CCTK_STARTUP`/`CCTK_SHUTDOWN` — no grid
hierarchy exists yet.

Same-thorn cross-routine calls: `CCTK_PASS_FTOF` (F→F) / `CCTK_PASS_CTOC` (C→C) plus
`CCTK_ARGUMENTS` again in the callee signature.

### 2.7 Aliased functions — practical notes
Caller: `REQUIRES FUNCTION <alias>` (hard dep, checked at startup) or
`USES FUNCTION <alias>` (optional — **must** guard the call with
`CCTK_IsFunctionAliased("<alias>")`, since calling an unregistered aliased function
aborts). Provider: `PROVIDES FUNCTION <alias> WITH <impl_fn> LANGUAGE C|Fortran`.

### 2.8 Driver/infrastructure layer
A driver thorn creates a GH extension (`CCTK_RegisterGHExtension`,
`SetupGH`/`InitGH`/`ScheduleTraverseGH`) and overloads a fixed set of
communication/storage functions. ⚠️ For **storage**, there are *two distinct*
overload points in the flesh: `CCTK_OverloadEnableGroupStorage`/
`DisableGroupStorage` (`CommOverloadables.h:53-54`) vs.
`CCTK_OverloadGroupStorageIncrease`/`GroupStorageDecrease` (line 131-132). The
reference driver PUGH actually overloads the **Increase/Decrease** pair
(`repos/cactuspugh/PUGH/src/Startup.c:68,73`), not Enable/Disable as
`InfrastructureThorns.tex` implies — see §7. I/O methods self-register via
`CCTK_RegisterIOMethod` + `CCTK_RegisterIOMethodOutputGH/TimeToOutput/TriggerOutput/
OutputVarAs`. Checkpoint/recovery hooks: write at `CCTK_CPINITIAL/CCTK_CHECKPOINT/
CCTK_TERMINATE`, read at `CCTK_RECOVER_PARAMETERS/CCTK_RECOVER_VARIABLES`.

### 2.9 Practical workflow: adding/modifying a thorn
1. `gmake newthorn` or create the directory under an arrangement; write
   `interface.ccl`/`param.ccl`/`schedule.ccl` (`configuration.ccl` only if you need an
   external library/capability).
2. Declare every grid variable/group you touch (own or inherited) in `interface.ccl`;
   every parameter you read in `param.ccl` (own, or `shares:` + `USES`/`EXTENDS`).
3. Schedule routines with the narrowest `STORAGE`/`READS`/`WRITES`/`SYNC` — these
   drive automatic ghostzone sync and (with `presync_mode`) automatic boundary/ghost
   updates.
4. Per routine: `#include "cctk.h"`, `"cctk_Arguments.h"`, `"cctk_Parameters.h"` as
   needed; `DECLARE_CCTK_ARGUMENTS[_CHECKED(name)]` first, then
   `DECLARE_CCTK_PARAMETERS`.
5. List source files in `src/make.code.defn` (`SRCS = ...`, `SUBDIRS = ...`) unless
   supplying a custom `src/Makefile`.
6. **Before renaming/retyping a `public`/`protected` group, a `restricted`/`global`
   parameter, or an aliased-function signature**: grep the whole checkout for its
   name. CCL gives no cross-thorn compile-time type checking beyond what the CST
   enforces at build time — other thorns' `inherits`/`friend`/`shares`/
   `USES FUNCTION` will silently break or (worse) build with mismatched assumptions.

---

## 3. CCTK Core API Reference — Part 1

*Covers `CCTKReference.tex` lines 1–~7700 (alphabetical index, then `CCTK_Abort`
through `CCTK_InterpHandle`).* ⚠️ = a signature verified wrong against source; see §7
for the full list.

### Termination / Basic GH control
| Function | Signature | Doc | Source |
|---|---|---|---|
| `CCTK_Abort` | `int(cGH*, int exitcode)` ⚠️doc says `const cGH*` | 954 | `CommOverloadables.h:80,88` |
| `CCTK_Exit` | `int(cGH*, int value)`, noreturn | 3495 | `CommOverloadables.h` |
| `CCTK_Barrier` | `int(const cGH*)` | 1374 | `CommOverloadables.h:66,69` |

### Group storage & communication control (all overloadable)
`CCTK_EnableGroupStorage`/`I`, `CCTK_DisableGroupStorage`/`I`,
`CCTK_EnableGroupComm`/`I`, `CCTK_DisableGroupComm`/`I` — ⚠️ **7 of 8 of these are
documented with a plain `cGH *cctkGH` first argument; the real signature is
`const cGH *GH`** in all cases except `CCTK_DisableGroupStorageI`, which the doc
happens to get right (`CommOverloadables.h:53-57`, `cctk_GroupsOnGH.h:45-48`) — see
§7. `CCTK_GroupStorageIncrease`/`Decrease(const cGH*, int n_groups, const int
*groups, const int *timelevels, int *status)` — CCTKReference.tex:5992/5931 —
`CommOverloadables.h:128-132`, `src/comm/CactusDefaultComm.c:784,893`.

### Variable & group introspection
- `CCTK_GroupIndex`/`CCTK_GroupIndexFromVar`/`I` — name↔index — `cctk_Groups.h:52-54`
- `CCTK_FirstVarIndex`/`I` — `cctk_Groups.h:41-42`
- `CCTK_FullGroupName`/`FullVarName`/`FullName(int index)` — `cctk_Groups.h:56,44,43`
- `CCTK_GroupName`/`GroupNameFromVarI` — `cctk_Groups.h:55,57`
- `CCTK_DecomposeName(const char *fullname, char **imp, char **name)` — `cctk_Groups.h:37-39`
- `CCTK_GroupData(int group_index, cGroup *buf)` — static group metadata. ⚠️ Real
  `cGroup` struct (`cctk_Groups.h:14-26`) has a `centeringtable` field the doc's
  Discussion omits.
- `CCTK_GroupDynamicData(const cGH*, int group, cGroupDynamicData *data)` — driver's
  dynamic size/shape. ⚠️ Real `cGroupDynamicData` (`cctk_GroupsOnGH.h:14-33`) has
  `alignment`, `alignment_offset`, `maxtimelevels` fields the doc omits (11 vs 14
  members) — material for manual GF indexing/padding.
- `CCTK_GroupDimI`/`DimFromVarI`, `CCTK_GroupGhostsizesI`, `CCTK_GroupSizesI`,
  `CCTK_GroupTypeI`/`TypeFromVarI`, `CCTK_GroupTagsTable`/`I` (→table handle) —
  `cctk_Groups.h:47-48,50,59,60,62,102-103`.
- Per-dimension family `(const cGH*, int dim, int *out, <selector>)` for GI/GN/VI/VN:
  `CCTK_Groupbbox*` (⚠️ doc param name `dim`, header calls it `size`),
  `CCTK_Groupgsh*`, `CCTK_Grouplbnd*`, `CCTK_Groupubnd*`, `CCTK_Grouplsh*`,
  `CCTK_Groupash*` (⚠️ doc param name `size`, header calls it `dim`),
  `CCTK_Groupnghostzones*` — `cctk_GroupsOnGH.h:50-83`.
- `CCTK_DeclaredTimeLevels(GN/GI/VI/VN)` (max declared) — `cctk_Groups.h:72-76`;
  `CCTK_ActiveTimeLevels(GI/GN/VI/VN)` (currently active) —
  `cctk_GroupsOnGH.h:85-89`, `src/main/GroupsOnGH.c:615-747`.
- `CCTK_ImpFromVarI(int index)` → implementation/thorn for a variable. ⚠️ Doc says
  `char*` return; real is `const char*` (`cctk_Groups.h:64`).
- `CCTK_ArrayGroupSize(const cGH*, int dir, const char*)`/`I` — ⚠️ Doc drops `const`
  on the `int*` return; real is `const int *` (`cctk_Comm.h:37-38`).

### Grid-function indexing macros
`CCTK_GFINDEX1D/2D/3D/4D(const cGH *restrict cctkGH, i[,j[,k[,l]]])` — flatten
multidim index — `cctk_core.h:236,245,254,264`.

### GH extensions
`CCTK_GHExtension(const cGH *GH, const char *name)` → `void*` (⚠️ doc synopsis
mistakenly types the first param `const GH *`, should be `const cGH *`) —
`cctk_GHExtensions.h:33`. `CCTK_GHExtensionHandle(const char *name)` → int.

### Coordinates (all "(deprecated)" — superseded by thorn CoordBase)
`CCTK_CoordDir`, `CCTK_CoordIndex`, `CCTK_CoordRange`, `CCTK_CoordRegisterData`,
`CCTK_CoordRegisterRange`, `CCTK_CoordRegisterSystem` (macro), `CCTK_CoordSystemDim`,
`CCTK_CoordSystemHandle`, `CCTK_CoordSystemName` — `cctk_Coord.h`. Note: a second,
incompatible 3-arg `CCTK_CoordRegisterSystem` macro also exists in `cctk_core.h:88`
that expands to a 4-arg call not matching any 3-param prototype — likely dead/orphaned
macro, undocumented ambiguity.

### Error / warning / info reporting
`CCTK_ERROR(msg)` → `CCTK_Error(__LINE__,__FILE__,CCTK_THORNSTRING,msg)`;
`CCTK_Error(int line, const char *file, const char *thorn, const char *message)`,
noreturn — `cctk_WarnLevel.h:35-39`. `CCTK_INFO(msg)` → `CCTK_Info(CCTK_THORNSTRING,
msg)`; `CCTK_Info(const char*, const char*)` → int. `CCTK_InfoCallbackRegister(void
*data, cctk_infofunc callback)`.

### Timers & clocks
`CCTK_ClockRegister(const char *name, const cClockFuncs *functions)`.
`CCTK_GetClockValue`/`I(name/index, const cTimerData*)` → `cTimerVal*`. ⚠️
**`CCTK_GetClockName`/`Resolution`/`Seconds` documented (CCTKReference.tex:3979,4005,
4036) but do not exist anywhere in source** — the real functions are
`CCTK_TimerClockName`/`Resolution`/`Seconds` (`cctk_Timers.h:95-97`), same signatures.
Also ⚠️ the `CCTK_GetClockValueI` doc entry's own C synopsis (line 4108) mistakenly
reads `CCTK_GetClockValue(...)` (missing the `I`).

### Complex numbers (all "(deprecated)")
`CCTK_Cmplx`, `CmplxAdd/Sub/Mul/Div/Conjg/Sin/Cos/Exp/Log/Sqrt`, `CmplxReal/Imag` —
`cctk_Complex.h`, `src/main/Complex.c`. ⚠️ **`CCTK_CmplxAbs` documented as returning
`CCTK_COMPLEX`; a magnitude is real — it actually returns `CCTK_REAL`.** Note: despite
being labeled "deprecated in favor of native C99/C++ complex," `cctk_Complex.h`
deliberately avoids `<complex.h>` in plain C (to keep `I` out of the global
namespace) — so no real native replacement is wired in for C thorns; the deprecation
label is aspirational.

### Interpolation
`CCTK_InterpGridArrays(...)` (overloadable, 13-arg, in `CommOverloadables.h:146-160`,
*not* `cctk_Interp.h`), `CCTK_InterpHandle(const char *name)` → int,
`CCTK_GridArrayReductionOperator(void)`.

### Thorn/implementation introspection
`CCTK_ActivatingThorn`, `CCTK_CompiledImplementation`/`CompiledThorn`,
`CCTK_ImplementationRequires`/`Thorn`, `CCTK_ImpThornList` — `cctk_ActiveThorns.h`.

### Misc utilities
`CCTK_CommandLine(char ***outargv)` → argc. `CCTK_CompileDate`/`DateTime`/`Time`.
`CCTK_CreateDirectory(int mode, const char *pathname)`. `CCTK_Equals(const char
*parameter, const char *value)` — case-insensitive STRING/KEYWORD compare. ⚠️
`CCTK_FortranString(const char*, char*, CCTK_FORTRAN_STRLEN_T)` — doc shows plain
`int` for the length param; real typedef can be 64-bit `ptrdiff_t` depending on
build — plain `int` is wrong on such builds.

---

## 4. CCTK Core API Reference — Part 2, Driver, Util

*Covers `CCTKReference.tex` lines ~6985–15161 (Interp… through
WARNCallbackRegister), `DriverReference.tex` (full), `UtilReference.tex` (full).*

### Interpolation (`cctk_Interp.h`)
`CCTK_InterpHandle`, `CCTK_InterpGridArrays` (overloadable), `CCTK_InterpLocalUniform`
(13-arg local uniform-grid interpolator, `cctk_Interp.h:72-90`, exact doc match),
`CCTK_InterpRegisterOpLocalUniform`. Undocumented but real:
`CCTK_InterpOperatorImplementation`, `CCTK_InterpOperator`, `CCTK_NumInterpOperators`
(`cctk_Interp.h:64-66`) — zero mentions in `CCTKReference.tex`.

### Thorn/implementation introspection
`CCTK_IsFunctionAliased(const char *functionname)` (generated at build time by
`lib/sbin/CreateFunctionBindings.pl` — no static header; ⚠️ the real generated decl is
`CCTK_INT CCTK_IsFunctionAliased(const char *function)`, param named `function` not
`functionname`, return type `CCTK_INT` which is a config-dependent width typedef, not
necessarily identical to plain `int`). `CCTK_IsImplementationActive`/`Compiled`,
`CCTK_IsThornActive`/`Compiled` (`cctk_ActiveThorns.h:21-24`, exact match).
`CCTK_NumCompiledImplementations`, `CCTK_NumCompiledThorns` (⚠️ doc's own code sample
at line 9266 typos this as `CCTK_NumCompiledThornss` — double s). `CCTK_ThornImplementation`
(⚠️ doc synopsis literally shows `CCTK_ThornImplementationThorn` — spurious "Thorn"
suffix).

### Reduction
`CCTK_LocalArrayReduceOperator`/`Implementation`, `CCTK_LocalArrayReductionHandle`,
`CCTK_NumLocalArrayReduceOperators`, `CCTK_NumGridArrayReductionOperators`,
`CCTK_NumReductionArraysGloballyOperators`, `CCTK_ReduceArraysGlobally`,
`CCTK_ReduceGridArrays`, `CCTK_ReduceLocalArrays`, `CCTK_ReductionHandle`,
registration macros `CCTK_RegisterGridArrayReductionOperator`/
`RegisterLocalArrayReductionOperator`/`RegisterReduceArraysGloballyOperator` — all
match `cctk_Reduction.h`. ⚠️ **`CCTK_RegisterReductionOperator` doc synopsis shows a
zero-arg call; the real macro takes 2 args**: `#define
CCTK_RegisterReductionOperator(a,b) CCTKi_RegisterReductionOperator(CCTK_THORNSTRING,a,b)`
(`cctk_Reduction.h:132-137`). No point-to-point/broadcast API exists in Cactus; fan out
a scalar via `CCTK_ReduceLocalScalar` with `"sum"` (zero elsewhere) (FAQ:1240-1253);
true point-to-point needs raw MPI, and thorns are discouraged from calling MPI
directly (keeps drivers swappable) (FAQ:1265-1274).

### Groups / variables
`CCTK_MaxDim`/`MaxGFDim` — `cctk_Groups.h:66-67`. `CCTK_MaxTimeLevels` — correctly
documented as **deprecated**, superseded by `CCTK_DeclaredTimeLevels`; no source
declaration exists at all (consistent, not a bug). `CCTK_MaxActiveTimeLevels`
(+GI/GN/VI/VN). `CCTK_NumGroups`, `CCTK_NumVars`, `CCTK_NumVarsInGroup`/`I` — exact
match `cctk_Groups.h:69,79-81`. `CCTK_QueryGroupStorage`/`B`/`I`.
`CCTK_VarDataPtr(const cGH*, int timelevel, const char *fullvarname)` — ⚠️ doc shows
non-const `char *name`; real 3rd arg is `const char *`. `CCTK_VarDataPtrB`/`I`.
`CCTK_VarIndex`, `CCTK_VarName`, `CCTK_VarTypeI`, `CCTK_VarTypeSize`.
`CCTK_PrintGroup`/`PrintVar(int)` — ⚠️ **doc gives a C-callable synopsis/example, but
these exist ONLY as Fortran-linkage wrappers** (`CCTK_FCALL CCTK_FNAME(...)`,
`src/main/Groups.c:1798,1814`) — there is no plain-C symbol to call as shown.
`CCTK_VECTGFINDEX1D–4D(cctkGH,i[,j[,k[,l]]],n)` vector GF index macros.

### Parallel / comm / sync
`CCTK_MyProc`/`nProcs(const cGH*)` (both accept NULL safely, `CommOverloadables.h:
65-71`). `CCTK_ParallelInit(cGH*)`. `CCTK_SyncGroup`/`I`/`SyncGroupsI`.
`CCTK_RegexMatch(const char*, const char*, int nmatch, regmatch_t*)`.
`CCTK_RunTime(void)` — seconds since startup, `cctk_Misc.h:53`.
`CCTK_NullPointer()`/`CCTK_PointerTo(var)` — **Fortran-only, no C form** (correctly
documented as such).

Convention: use `const cGH *cctkGH` for all `CCTK_` calls unless mutating
(FAQ:1277-1308). Two grid-array groups of identical size/ghostzones/distribution
are guaranteed identical local shapes (`lsh`) even with different types/timelevels
(FAQ:1320-1326). Can't sync individual group members or non-current timelevels — only
a whole group's current timelevel (FAQ:1459-1475).

### I/O
`CCTK_NumIOMethods`, `CCTK_OutputGH(const cGH*)` (overloadable), `CCTK_OutputVar`,
`CCTK_OutputVarAs`, `CCTK_OutputVarAsByMethod`, `CCTK_OutputVarByMethod` — all exact
matches. `CCTK_RegisterIOMethod` (macro) + `...OutputGH/OutputVarAs/TimeToOutput/
TriggerOutput(int handle, callback)`. `IOHDF5` supports complex grid vars for
checkpointing; `IOFlexIO` does not (no native complex type) (FAQ:1640-1648).

### GH extensions
`CCTK_RegisterGHExtension(const char*)`, `CCTK_RegisterGHExtensionSetupGH(int handle,
void *(*func)(tFleshConfig*, int, cGH*))` (correct). ⚠️
`CCTK_RegisterGHExtensionInitGH` — doc callback type shows `void *(*func)(cGH*)`; real
is `int (*func)(cGH*)` (`cctk_GHExtensions.h:25-26`) — looks like copy/paste from the
neighboring SetupGH entry. `CCTK_RegisterGHExtensionScheduleTraverseGH(int handle, int
(*func)(cGH*, const char*))`. Undocumented but real: `CCTK_UnregisterGHExtension`
(`cctk_GHExtensions.h:19`) — zero mentions in `CCTKReference.tex`.

### Scheduling / setup / termination
`CCTK_SchedulePrintTimes`/`ToFile`, `CCTK_ScheduleQueryCurrentFunction`,
`CCTK_ScheduleTraverse(const char *where, void *data, CallFunction_t)` (header
typedef is actually `cCallFunction`, cosmetic only). ⚠️ `CCTK_SetupGH` — doc synopsis
passes `tFleshConfig config` **by value**; real overloadable signature is
`cGH *CCTK_SetupGH(tFleshConfig *config, int convergence_level)` — pointer.
`CCTK_TerminateNext`, `CCTK_TerminationReached`.

### Parameters
`CCTK_ParameterData`, `CCTK_ParameterFilename`, `CCTK_ParameterGet`,
`CCTK_ParameterLevel`, `CCTK_ParameterQueryTimesSet`, `CCTK_ParameterSet`,
`CCTK_ParameterSetNotifyRegister`/`Unregister`, `CCTK_ParameterValString`,
`CCTK_ParameterWalk` — all matched. `CCTK_PARAMWARN`/`CCTK_ParamWarn`/`VParamWarn`.
Parameters are only *conventionally* read-only — Fortran can technically mutate them,
but must not (FAQ:1595-1601).

### Timers
`CCTK_Timer`/`TimerI(name/index, cTimerData*)`. `CCTK_TimerCreate(const char*)`,
`CCTK_TimerCreateI(void)` — ⚠️ **the `TimerCreateI` doc entry's synopsis is
copy-pasted from `TimerCreate`** (shows `CCTK_TimerCreate()` instead of
`CCTK_TimerCreateI()`). `CCTK_TimerCreateData`/`DestroyData`. `CCTK_TimerDestroy`/`I`.
`CCTK_TimerReset`/`I`, `TimerStart`/`I`, `TimerStop`/`I`, `TimerIsRunning`/`I` — ⚠️ the
one-line purpose text for **both** `CCTK_TimerReset` and `CCTK_TimerStop` reads "Gets
values from all the clocks in the given timer" (copy-paste artifact; actual behavior
per `src/util/CactusTimers.c:751,897` is reset/stop, not value retrieval — that's
`CCTK_Timer`/`TimerI`). `CCTK_NumTimerClocks(const cTimerData*)` — ⚠️ doc shows `int`
return; real is `unsigned int` (`cctk_Timers.h:92`).

### Warn / info / error
`CCTK_WARN(level,msg)` macro. ⚠️ **`CCTK_Warn`'s own function synopsis
(CCTKReference.tex:14953) shows `void` return; real declaration returns `int`**
(`cctk_WarnLevel.h:23-27`) — contradicting the doc's own `CCTK_WARN` macro footnote a
few pages earlier, which correctly shows `int`. `CCTK_VWARN`/`CCTK_VWarn` — ⚠️ doc
Discussion says `CCTK_VWARN` "expands to a call to `CCTK_Warn()`"; it actually expands
to `CCTK_VWarn(level,__LINE__,__FILE__,CCTK_THORNSTRING,...)` (`cctk_core.h:442-443`).
`CCTK_INFO`/`CCTK_VINFO` → `CCTK_Info`/`CCTK_VInfo`. `CCTK_ERROR`/`CCTK_VERROR` — ⚠️
doc Discussion for `CCTK_VERROR` omits `__LINE__`/`__FILE__` from the claimed
expansion; real macro is `CCTK_VError(__LINE__,__FILE__,CCTK_THORNSTRING,...)`
(`cctk_core.h:444-445`). `CCTK_WarnCallbackRegister`. ⚠️ `CCTK_RegisterBanner` — doc
synopsis implies `void` return; real is `int CCTK_RegisterBanner(const char*)`
(`cctk_Banner.h:20`).

### Driver_* API (`DriverReference.tex`, full file — used by AMR drivers like Carpet)
⚠️ **4 of the 6 documented functions have wrong names/signatures in their C code
samples** — real names always start `Driver_`, not `CCTK_`, and always take
`cctkGH` as the first argument:
| Doc shows (wrong) | Real (source: `Carpet_Prototypes.h`) |
|---|---|
| `CCTK_GetValidRegion(int vi, int tl)` | `CCTK_INT Driver_GetValidRegion(const CCTK_POINTER_TO_CONST cctkGH, const CCTK_INT vi, const CCTK_INT tl)` — line 118 |
| `CCTK_SetValidRegion(int vi, int tl, int where)` | `void Driver_SetValidRegion(cctkGH, CCTK_INT vi, CCTK_INT tl, CCTK_INT wh)` — line 169 |
| `CCTK_NotifyDataModified(...)` | `CCTK_INT Driver_NotifyDataModified(cctkGH, int *variable_list, int *time_level_list, int num_variables, int *where_list)` — line 125 |
| `CCTK_RequireValidData(...)` | `CCTK_INT Driver_RequireValidData(cctkGH, ...)` — line 136 |

`Driver_SelectGroupForBC`/`Driver_SelectVarForBC` correctly use the `Driver_` prefix,
but both have a syntax typo (`int table handle,` — missing underscore) and both carry
a leftover `\Parameter{where_list}` not in their actual signature (copy-paste from the
NotifyDataModified/RequireValidData entries above them).

### `Util_Table*` API (`util_Table.h`)
`Util_TableCreate`/`FromString`/`Clone`/`Destroy`.
`Util_TableSet<Type>`/`GetArray` for `POINTER, FPOINTER, CHAR, BYTE, INT, INT1/2/4/8/16,
REAL, REAL4/8/16, COMPLEX, COMPLEX8/16/32, PointerToConst` — ⚠️ the doc's enumerated
type list (UtilReference.tex:1640-1643, 3665-3668) **omits `INT16`** even though the
matching-width `REAL16`/`COMPLEX32` are listed; `Util_TableSetInt16`/`GetInt16`/Array
variants all exist (`util_Table.h:212,294,377,460`). ⚠️
`Util_TableSetPointerToConst`/`Array`/`Util_TableGetPointerToConst`/`Array`
(`util_Table.h:183,245,347,410`) are **not documented anywhere** — no type-family
listing, no individual entry. Iterator API: `Util_TableItCreate`/`Clone`/`Destroy`/
`Advance`/`ResetToStart`/`SetToKey`/`SetToNull`/`QueryIsNull`/`QueryIsNonNull`/
`QueryKeyValueInfo`/`QueryTableHandle`. Introspection: `Util_TableQueryFlags`/
`ValueInfo`/`MaxKeyLength`/`NKeys`. Debug: `Util_TablePrint`/`PrintAll`/
`PrintAllIterators`/`PrintPretty`.

### `Util_String*` API (`util_String.h`)
`Util_StrCmpi`, `Util_Strlcat`/`Strlcpy`. ⚠️ `Util_StrSep(const char **stringp, const
char *delim)` — doc shows non-const `char *` return; real is `const char *`
(`util_String.h:24`). Undocumented but real: `Util_SplitString`, `Util_SplitFilename`
(appear only as commented-out placeholders in the doc), `Util_StrMemCmpi`,
`Util_asnprintf` (`util_String.h:27,32,43,51`).

### Util misc
`Util_CurrentDate`/`Time`/`DateTime`. `Util_asprintf(char**, const char*, ...)`.
`Util_snprintf`/`vsnprintf` — documented as deprecated in favor of standard
`snprintf`/`vsnprintf`.

### Additional spot-checks from `CCTKReference.tex` lines 8043–10000
(alphabetical: `CCTK_InterpRegisterOpLocalUniform` through `CCTK_ParallelInit`) — all
34 functions in this range matched their header declarations exactly **except** the 3
already listed above (`CCTK_NumCompiledThorns` typo, `CCTK_NumTimerClocks` return
type, `CCTK_IsFunctionAliased` return type/param name). `CCTK_InterpLocalWarped` and
its registration function are entirely `%notyet`-commented in the LaTeX source (not
real/callable — don't rely on them).

---

## 5. Build System & Maintainer Internals

### Top-level flow
`repos/flesh/Makefile` (`Makefile:298-299`) invokes, per configuration:
```
$(MAKE) -f $(CCTK_HOME)/lib/make/make.configuration TOP=$(CONFIGS_DIR)/$@ \
  CCTK_HOME=$(CCTK_HOME) $(TPARFLAGS)      # TPARFLAGS = -j TJOBS
```
Config creation → `lib/make/setup_configuration.pl` (parses an options file, runs the
autoconf-generated `configure`). `lib/make/make.configuration:207-277` regenerates
`ThornList` (offering `$EDITOR`) and `make.thornlist`.

### `lib/make/make.configuration`
`CONFIG = $(TOP)/config-data`, `BINDINGS_DIR = $(TOP)/bindings`. CST invocation
(line 214): `+$(PERL) $(CST) -config_dir=$(CONFIG) -cctk_home=$(CCTK_HOME)
-top=$(TOP) $<`, where `$(CST)` = `$(CCTK_HOME)/lib/sbin/CST` — **the CST driver
script's actual name/location is never stated in `CST.tex`**. `make.thornlist`'s
dependency list includes every thorn's 4 CCL files plus `lib/make/force-rebuild`, so
touching any CCL file (or that sentinel) retriggers the CST. Per-thorn build loop also
sets `USESTHORNS_<thorn>` (from CST-generated dependency data) — not documented.

### `lib/make/make.thornlib` / `make.subdir` / `make.pre` / `make.post`
`make.code.defn` provides `SRCS`/`SUBDIRS`; subdirs recurse via `make.subdir`;
`CCTK_SRCS` accumulates via the `foreach` + `make.pre`/`make.post` wrapper
(`make.pre` resets `SRCS:=`, `make.post` prefixes the subdir name and appends to
`CCTK_SRCS`). Also includes a generated `make.$(THORN).defn` from
`$(BINDINGS_DIR)/Configuration/Thorns/` per thorn — not mentioned in Makesystem.tex.

### Autoconf layer (`repos/flesh/lib/make/`)
Driven by **`configure.ac`** (`AC_CONFIG_HEADERS([cctk_Config.h])`), *not*
`configure.in`/`config.h` as `Makesystem.tex:202-213` claims (stale from the
historical autoconf `.in`→`.ac` rename — see §7). Produces `config-data/
{cctk_Config.h, make.config.defn, make.config.rules, make.config.deps}`.
`known-architectures/<host_os>` files are sourced twice, gated by
`$CCTK_CONFIG_STAGE` = `preferred-compilers` then `misc`. 23 architecture files exist
today (many for long-dead platforms — aix, bgl, irix, unicos*, etc). Helper functions
`CCTK_Search`/`CCTK_CreateFile`/`CCTK_WriteLine` live in **`CCTK_Functions.sh`**
(capital F; Makesystem.tex:292 writes it lowercase — cosmetic doc typo).

### The CST (`lib/sbin/CST`, 847 lines) — actual 3-stage pipeline
CST.tex's chapters ("The Databases", "The Parsing Routines", "The Output Routines",
etc.) are **empty stubs**; this is reconstructed from the script itself:
1. **Parse**: `CreateThornList` reads `ThornList`, then `CreateConfigurationDatabase`,
   `create_interface_database`, `create_parameter_database`, `create_schedule_database`
   populate `%configuration_database`, `%interface_database`, `%parameter_database`,
   `%schedule_database`.
2. **Cross-check**: `ProcessConfiguration` (runs `configuration.ccl` scripts),
   `check_schedule_database`, `CheckImpParamConsistency`, `CheckCrossConsistency`
   (thorns sharing an implementation must agree on restricted-parameter defaults).
3. **Generate bindings**: `CreateBindings` calls, in order,
   `CreateImplementationBindings` → `CreateParameterBindings` →
   `CreateVariableBindings` → `CreateScheduleBindings` → `CreateFunctionBindings` →
   `GenerateArguments`, writes `bindings/make.code.defn`
   (`SUBDIRS = Functions Implementations Parameters Variables Schedule` — useful map
   from bug symptom → which generated-binding subtree to inspect, e.g. aliased-function
   link errors → `bindings/Functions`; schedule-order bugs → `bindings/Schedule`).
   Then `CreateConfigurationBindings`, `CreateThornsHeaders` (writes
   `bindings/include/thornlist.h`, `cctk_DefineThorn.h`, per-thorn
   `definethisthorn.h`), `BuildHeaders`, `CreateLogFile`, finally
   `CreateMakeThornlist` writes `config-data/make.thornlist`.

**Not documented anywhere in `CST.tex`, but architecturally central:**
- All 4 CCL parsers (`interface_parser.pl`, `parameter_parser.pl`,
  `ScheduleParser.pl`, `ConfigurationParser.pl`) are **PEG-grammar based** on a shared
  `Piraha` module (`lib/sbin/Piraha.pm`, grammars `src/piraha/pegs/*.peg`), with a
  build-time cache dir `$TOP/piraha` (cleaned by `make.configuration`'s
  `cleandeps` target). This is the biggest single architectural fact about "how CCL
  files get parsed" and it's absent from the MaintGuide.
- Thorn/arrangement name validation (max 27 chars, must start with a letter) —
  `CST:270-285` (`TestName`).
- Topological thorn-link ordering (`TopoSort`, `CST:622-691`) — considers
  inheritance, `PROVIDES`/`REQUIRES` capabilities, direct `REQUIRES THORNS`/
  `USES THORNS` — the actual algorithm behind `THORN_LINKLIST`.
- `CreateScheduleBindings.pl`'s `ScheduleSelectRDWR`/`SelectGroups`/`SelectRoutines`/
  `SelectVars` (lines 808-1171) implement the `READS`/`WRITES` (PreSync) auto-sync/
  auto-boundary machinery — completely undocumented in the (also-empty) `Schedule.tex`.
- `CreateFunctionBindings.pl` (2600+ lines, the largest binding generator) implements
  the aliased-function/Fortran-bridging machinery — `CreateFunctionBindings`,
  `RegisterAllFunctions`/`AliasedFunctions`, `UsesPrototypes`/`ProvidedFunctions`.
- The canonical, authoritative ordered list of schedule bins lives only in
  `lib/sbin/ScheduleParser.pl`'s `@schedule_bins` array — **that**, not the empty
  `Schedule.tex`, is the ground truth when debugging bin-ordering issues (cross-checked
  against §2.3's list — consistent).

### Coding style vs. reality
Style guide (`Style.tex`) largely matches real code (grdoc file/function headers,
`CCTK_FILEVERSION(...)`, `<arrangement>_<thorn>_<file>_<ext>` naming, include guards
`#ifndef _NAME_H_`, `extern "C"` guards, 2-space indent/no tabs, `CCTK_*`/`CCTKi_*`/
`cctk_*` naming) — **except**:
- ⚠️ **Brace style**: `Style.tex:37-44` mandates opening braces on their own line;
  `repos/flesh/.clang-format:38` sets `BreakBeforeBraces: Attach` (K&R/same-line), and
  real thorn code follows *that*, e.g. `repos/cactusbase/Boundary/src/Boundary.c:415,
  429,445-448`. Enforced tooling and doc are opposite.
- ⚠️ **"Single return point" rule** (`Style.tex:224-227`) is violated by real,
  actively-maintained code, e.g. `Bdry_Boundary_SelectVarForBCI` in
  `repos/cactusbase/Boundary/src/Boundary.c:411-500` has 3 return points.

### Practical debugging map
| Symptom | Where to look |
|---|---|
| Aliased-function link error | `configs/<cfg>/bindings/Functions` |
| Schedule ordering wrong | `lib/sbin/ScheduleParser.pl` `@schedule_bins`; `configs/<cfg>/bindings/Schedule` |
| CCL syntax rejected unexpectedly | `repos/flesh/src/piraha/pegs/{interface,param,schedule,config}.peg` |
| Stale generated bindings after CCL edit | touch any CCL file or `lib/make/force-rebuild`, rerun `gmake <config>` |
| Build hangs / weird "checking status of libX.a" | `VERBOSE=yes`; check clock skew (FAQ:429-439) |
| Undefined-reference/link-order error | almost always a missing `inherits:` in `interface.ccl` (FAQ:644-673) |

---

## 6. FAQ, Reference Tables & Recent Changes

### Build/configure troubleshooting (`repos/flesh/doc/FAQ`)
- `DECLARE_CCTK_PARAMETERS`/`DECLARE_CCTK_ARGUMENTS` "undefined" → missing
  `#include "cctk_Parameters.h"` / `"cctk.h"`+`"cctk_Arguments.h"` (FAQ:445,852).
  In Fortran, "dummy argument CCTK_DIM has not been given a type" means the same
  thing (FAQ:840-845,1310-1318,1437-1441) — and a **missing
  `DECLARE_CCTK_PARAMETERS` in Fortran gives silently wrong parameter values, no
  compile error** (FAQ:1437-1441).
- `#if 0 ... #endif` blocks containing `DECLARE_CCTK_ARGUMENTS`/`_PARAMETERS` break
  the CST's automatic closing-brace insertion — keep commented-out code in matched
  `{}` (FAQ:857-891).
- Force build order: `configuration.ccl` `PROVIDES`/`REQUIRES <capability>` for
  thorn-level; `make.code.deps` entries (`using.F90.o: module.F90.o`, note `.o`
  suffix convention) for file-level (FAQ:482-503,994-1002).
- Stale/renamed includes → `gmake <config>-cleandeps` (FAQ:596-613).
- Low disk space → `CACTUS_CONFIGS_DIR` env var relocates `configs/` (FAQ:519-533).
- Build one thorn in isolation (no link): `make <config>-build BUILDLIST="<thorns>"`
  (FAQ:935-941). Per-thorn optimisation override: `C_OPTIMISE_FLAGS`/
  `CXX_OPTIMISE_FLAGS`/`F77_OPTIMISE_FLAGS`/`F90_OPTIMISE_FLAGS` in that thorn's
  `make.code.defn` (FAQ:978-991). Faster dev builds: `OPTIMISE=no` (FAQ:832-837).
- F77 and F90 code must use the **same compiler** (name-mangling/calling-convention
  compatibility) (FAQ:1050-1058).
- A gmake object file can come out silently empty if the compiler OOMs on a complex
  file → bogus "unresolved text symbol" for a scheduled function; `touch` + rebuild,
  maybe at lower optimisation (FAQ:914-926).

### Runtime troubleshooting
- `mpirun ... "Unknown option -np"` → add `-i`: `mpirun ./cactus_foo par -i -np 8`
  (FAQ:1082-1090).
- No C++ on some cluster nodes → configure `CXX=none` if no thorn needs C++
  (FAQ:1093-1097).
- `libhdf5.so` load errors → `LD_LIBRARY_PATH`, or strip `.so` from the lib dir to
  force static linking; if it only fails under `mpirun`, the launcher's remote shell
  isn't propagating `LD_LIBRARY_PATH` (FAQ:1100-1127).
- **Segfault right after the schedule tree prints** → a `CCTK_STARTUP` routine
  declared with `CCTK_ARGUMENTS` — grid vars don't exist yet at STARTUP, use `void`
  (FAQ:1143-1151; matches §2.3's schedule-bin note).
- `cctk_final_time`/`terminate="time"` to run to a coordinate time instead of
  `cctk_itlast`. `IOBasic::outInfo_*` needs a reduction thorn (e.g. `PUGHReduce`)
  active to print min/max (FAQ:1176-1188).
- `"CCTK_Equals: First string null"` → usually mis-detected Fortran name-mangling;
  full `realclean` + reconfigure/rebuild (FAQ:1190-1202).
- MPICH `ch_p4` executables must always be started via `mpirun` — running directly
  changes the CWD used to resolve relative parfile paths (FAQ:1204-1217).

### Thorn-writing gotchas (beyond §2)
- No C++ comments (`//`) in C thorn code — portability (FAQ:1443-1447).
- `#ifdef ARRANGEMENTNAME_THORNNAME` (via `cctk_DefineThorn.h`) conditionally compiles
  on ThornList membership but is discouraged (hidden coupling); prefer
  `CCTK_IsThornActive` (FAQ:1328-1357). Check MPI presence via makefile var `HAVE_MPI`
  or macro `CCTK_MPI` (FAQ:1359-1373).
- `CCTK_Exit`/`CCTK_Abort` need `cctkGH` — pass NULL deep in call stacks if the driver
  tolerates it (FAQ:1375-1385).
- Fortran macro calls (`CCTK_EQUALS`, `CCTK_INFO`, `CCTK_WARN`) need C-style backslash
  continuation, not Fortran `$`/`&`/column-6 — they're preprocessor macros
  (FAQ:1387-1417).
- No `STRING` grid-scalar type — only `CCTK_CHAR` arrays with `DISTRIB=CONSTANT`
  (FAQ:1557-1561). Array-parameter sizes in `param.ccl` must be compile-time
  integers, not other parameters (Fortran needs fixed-size arrays) (FAQ:1654-1658).
- No way to recover exact source version from a binary — use the `Formaline` thorn to
  embed full source (FAQ:1537-1543).
- `MPI_Init` is called once in the flesh, before parsing argv, because MPI is allowed
  to mangle argv (FAQ:1512-1534).

### Reference tables (`Appendices.tex`)
- **Thorn naming**: unique (case-insensitive), start with a letter, letters/digits/
  underscore only, **≤27 characters**, name `doc` reserved; dirs starting `#` or
  ending `~`/`.bak` are ignored.
- **CCL files**: `interface.ccl`/`param.ccl`/`schedule.ccl` compulsory,
  `configuration.ccl` optional.
- **Flesh's own private/restricted parameters** (`repos/flesh/src/param.ccl`) —
  private: `allow_mixeddim_gfs`, `cctk_brief_output`, `cctk_full_warnings`,
  `cctk_run_title`, `cctk_show_banners`, `cctk_show_schedule`,
  `cctk_strong_param_check`, `cctk_timer_output`, `recovery_mode`,
  `highlight_warning_messages`, `info_format`; restricted: `cctk_final_time`,
  `cctk_initial_time`, `cctk_itlast`, `max_runtime`, `presync_mode`
  (`off|warn-only|mixed-warn|mixed-error|presync-only`), `terminate`
  (`never|iteration|time|runtime|any|all`), `terminate_next`.
- **ThornList line syntax**: `<arrangement>/<thorn>`; CRL directives
  `!CRL_VERSION`/`!DEFINE`/`!TARGET`/`!TYPE`/`!URL`/`!REPO_BRANCH`/`!REPO_PATH`/
  `!NAME`/`!CHECKOUT` — matches `thornlists/installation-default.th` and
  `repos/manifest/einsteintoolkit.th` exactly.
- `gmake ThornDoc` / `gmake ArrangementDoc` build ThornGuide docs; missing thorns in
  output usually mean bad ThornGuide markup in an earlier thorn (FAQ:1607-1619).

### Recent changes / staleness
- ⚠️ **`repos/flesh/doc/ReleaseNotes` is effectively dead**: newest-first ordering,
  but the most recent entry is dated **16 May 2014** (Cactus 4.0 ET_2014_05_v0),
  while this checkout targets `ET_2026_05` — ~12 years of Cactus/ET development are
  not logged here. The one substantive logged change: native C99/C++
  `_Complex`/`std::complex` support for `COMPLEX` grid vars, deprecating the old
  `CCTK_Cmplx*` functions (consistent with §3's note that these are marked
  deprecated).
- ⚠️ **`README.Windows` is fully obsolete** — Cygwin on WinXP/NT/2000, GNU make
  3.77-3.81, MS Visual C 6.0/Digital Fortran/Intel 4.5. No modern-Windows guidance at
  all, not flagged as outdated anywhere.
- FAQ contains many entries tied to compilers/OSes that no longer exist in practice
  (old Intel/Absoft/Pacific-Sierra Fortran compilers, SGI/Irix, RedHat 8/9 glibc
  bugs) — harmless to skip, listed in §7 for completeness.

---

## 7. Known Documentation Issues (consolidated)

Grouped by doc file. Each was independently verified against source, not just
asserted by one pass. Use this list to avoid being misled by the shipped LaTeX when
debugging or extending code.

### `CCTKReference.tex` (Reference Manual) — API signature bugs
1. **`CCTK_Abort`**: doc shows `const cGH*`; real is non-const `cGH *GH`
   (`CommOverloadables.h:80,88`).
2. **`CCTK_ArrayGroupSize`/`I`**: doc drops `const` on `int *` return; real is
   `const int *` (`cctk_Comm.h:37-38`).
3. **`CCTK_CmplxAbs`**: doc says returns `CCTK_COMPLEX`; really returns `CCTK_REAL`.
4. **7 of 8 group enable/disable functions** (`Disable/EnableGroupComm`/`I`,
   `Disable/EnableGroupStorage`/`I` except `DisableGroupStorageI`): doc uses
   non-const `cGH *cctkGH`; real is `const cGH *GH` — internally inconsistent doc.
5. **`CCTK_FortranString`**: doc's length param is `int`; real is
   `CCTK_FORTRAN_STRLEN_T` (can be 64-bit).
6. **`CCTK_CoordRegisterSystem`**: two incompatible macro definitions exist
   (`cctk_Coord.h` 2-arg vs `cctk_core.h:88` 3-arg expanding to a mismatched 4-arg
   call) — doc doesn't flag the ambiguity; the second looks like dead code.
7. **`CCTK_GetClockName`/`Resolution`/`Seconds`**: documented (lines 3979,4005,4036)
   but don't exist — real names are `CCTK_TimerClockName`/`Resolution`/`Seconds`
   (`cctk_Timers.h:95-97`).
8. **`CCTK_GetClockValueI`**: doc's own C synopsis (line 4108) reads
   `CCTK_GetClockValue(...)` (missing the `I`).
9. **`CCTK_GHExtension`**: synopsis typos the param type as `const GH *` (should be
   `const cGH *`); separately its own Discussion/Example calls
   `CCTK_GHExtension(...)` where it means `CCTK_GHExtensionHandle(...)`.
10. **`CCTK_GroupData`**: doc's `cGroup` struct listing omits the real
    `centeringtable` field.
11. **`CCTK_GroupDynamicData`**: doc's `cGroupDynamicData` struct listing omits real
    `alignment`, `alignment_offset`, `maxtimelevels` fields (11 vs 14 members).
12. **`CCTK_GroupbboxGI/GN/VI/VN`** vs **`CCTK_GroupashGI/GN`**: parameter names
    `dim`/`size` are swapped between doc and header.
13. **`CCTK_ImpFromVarI`**: doc return type `char *`; real is `const char *`.
14. **`CCTK_GroupTagsTable`/`I`**: Fortran synopsis shows `CCTK_VarIndex(...)` calls —
    copy-paste leftover.
15. **`CCTK_GroupStorageDecrease`**: doc has a duplicated `\Parameter{groups}` entry
    contradicting itself (copy-pasted from `GroupStorageIncrease`).
16. **`CCTK_DisableGroupComm`/`DisableGroupStorage`/`EnableGroupComm`**: doc's
    parameter list omits `\Parameter{group}` even though it's in the synopsis.
17. **`CCTK_NumCompiledThorns`**: doc's own code example (line 9266) typos the name
    as `CCTK_NumCompiledThornss` (extra `s`).
18. **`CCTK_ThornImplementation`**: doc synopsis (line 12915) shows
    `CCTK_ThornImplementationThorn` — spurious suffix.
19. **`CCTK_TimerCreateI`**: doc synopsis copy-pasted from `CCTK_TimerCreate` (shows
    the wrong function name).
20. **`CCTK_NumTimerClocks`**: doc shows `int` return; real is `unsigned int`.
21. **`CCTK_RegisterBanner`**: doc implies `void` return; real is
    `int CCTK_RegisterBanner(const char*)`.
22. **`CCTK_RegisterGHExtensionInitGH`**: doc callback type `void *(*func)(cGH*)`;
    real is `int (*func)(cGH*)` — mixed up with the neighboring `SetupGH` entry.
23. **`CCTK_SetupGH`**: doc shows `tFleshConfig config` by value; real is
    `tFleshConfig *config` (pointer).
24. **`CCTK_VarDataPtr`**: doc's 3rd param is non-const `char *`; real is `const
    char *`.
25. **`CCTK_Warn`**: doc's own function synopsis shows `void` return; real is `int` —
    contradicts the doc's own `CCTK_WARN` macro footnote nearby.
26. **`CCTK_RegisterReductionOperator`**: doc shows a 0-arg call; real macro takes 2
    required args.
27. **`CCTK_VERROR`/`CCTK_VWARN` Discussion text**: both misdescribe their own macro
    expansions (omit `__LINE__`/`__FILE__`, or say "calls `CCTK_Warn()`" when it calls
    `CCTK_VWarn(...)`).
28. **`CCTK_TimerReset`/`CCTK_TimerStop`**: one-line purpose text for both wrongly
    reads "Gets values from all the clocks in the given timer" (copy-paste; neither
    function retrieves values).
29. **`CCTK_PrintGroup`/`CCTK_PrintVar`**: doc gives a C-callable example; these are
    actually Fortran-linkage-only wrappers with no plain-C symbol.
30. Missing entirely from `CCTKReference.tex`: `CCTK_InterpOperatorImplementation`,
    `CCTK_InterpOperator`, `CCTK_NumInterpOperators`, `CCTK_UnregisterGHExtension`.
31. `CCTK_IsFunctionAliased`: doc shows plain `int`/param `functionname`; the
    generated real signature is `CCTK_INT`/param `function`.

### `DriverReference.tex`
32. **4 of 6 documented functions have wrong names in their C code samples** — real
    names are `Driver_GetValidRegion`, `Driver_SetValidRegion`,
    `Driver_NotifyDataModified`, `Driver_RequireValidData` (doc shows `CCTK_*` names
    that don't exist, and omits the required `cctkGH` first argument in two cases).
33. `Driver_SelectGroupForBC`/`SelectVarForBC`: literal syntax error `int table
    handle,` (missing underscore) in the C synopsis; both also carry a stray,
    non-existent `\Parameter{where_list}` entry.

### `UtilReference.tex`
34. `Util_StrSep`: doc return type `char *`; real is `const char *`.
35. Type-family lists (Set/Get) omit `INT16` even though the real API has it.
36. `Util_TableSetPointerToConst`/`GetPointerToConst` (+Array variants): real,
    implemented, not documented anywhere.
37. `Util_SplitString`, `Util_SplitFilename`, `Util_StrMemCmpi`, `Util_asnprintf`:
    real, declared/implemented, essentially undocumented (first two only appear as
    commented-out placeholders).

### `ApplicationThorns.tex` / `Appendices.tex` (UsersGuide) — omissions & inconsistencies
38. **`READS`/`WRITES` region keyword list is incomplete in the main chapter**:
    `ApplicationThorns.tex:563-564` lists only `EVERYWHERE, INTERIOR, BOUNDARY` and no
    default; the Appendix has the real list (`EVERYWHERE|ALL|INTERIOR|IN|
    INTERIORWITHBOUNDARY|BOUNDARY`) and default-region rule; neither location
    mentions the grammar-valid `scalar` region.
39. **`configuration.ccl`'s `PROVIDES` block**: main chapter shows only `SCRIPT`/
    `LANG`; `VERSION`/`OPTIONS` (both real and common) only appear in the Appendix.
40. **`INVALIDATES:` schedule directive** is grammar-valid (`schedule.peg`) but
    undocumented anywhere in either the main chapter or Appendix; unused in this
    checkout, so purpose is unclear.
41. **`STAGGER=`/`CENTERING={...}` group attributes** — real grammar productions used
    by CarpetX/multipatch thorns — missing from both the interface.ccl narrative and
    the Appendix entirely.
42. **`STEERABLE` value typo**: `Appendices.tex:764` prose says `RECOVERY`; the CST
    parser only accepts `RECOVER` (`CreateParameterBindings.pl:466-482`) — using
    `RECOVERY` is a fatal build error.
43. **Driver storage-overload mismatch**: `InfrastructureThorns.tex` implies a driver
    overloads `CCTK_EnableGroupStorage`/`DisableGroupStorage`; the actual reference
    driver PUGH overloads the separate `GroupStorageIncrease`/`Decrease` pair instead
    (`PUGH/src/Startup.c:68,73`) — the doc doesn't distinguish the two overload
    points.
44. **`else`/`else if` schedule conditionals** are legal (`schedule.peg:65-69`) and
    used extensively in real thorns, but the main chapter only ever shows a bare
    `if`.
45. Dangling `.emacs`/`grdoc` reference in `Appendices.tex:14-33` — no `grdoc.el` (or
    anything named `grdoc*`) ships anywhere in the repo.

### `MaintGuide/*` — stale/empty
46. **`CST.tex`, `Schedule.tex`, `Comm.tex`, `IO.tex`, `Util.tex` are empty
    stubs** — headings only, no content. The CST's PEG/Piraha-based parsing
    architecture, the schedule-bin list, and the READS/WRITES (PreSync) auto-sync
    mechanism — all real and load-bearing — are documented nowhere.
47. `Makesystem.tex:202-213`: refers to `configure.in`/`config.h.in`/`config.h`; real
    files are `configure.ac`/`cctk_Config.h.in`/`cctk_Config.h`.
48. `Style.tex:37-44` (opening-brace-on-own-line) contradicts `.clang-format`
    (`BreakBeforeBraces: Attach`) and real code.
49. `Style.tex:224-227` ("single return point") is violated by real, maintained code
    (e.g. `Boundary.c:411-500`).
50. `Procedures.tex:14` self-admits the whole chapter is "out-dated and needs a
    rewrite"; `Procedures.tex:70-73` still describes BitBucket as the issue tracker.
51. `Makesystem.tex:292` "CCTK_functions.sh" — real filename is `CCTK_Functions.sh`
    (capital F) — cosmetic.

### `FAQ` / `Appendices.tex` / `ReleaseNotes` / `README.Windows`
52. `Appendices.tex:958` typo: "the drier" → "the driver".
53. `ReleaseNotes` last entry dated 2014-05-16 vs. this checkout's `ET_2026_05` — ~12
    years with no changelog entries.
54. `README.Windows` fully describes an obsolete Cygwin/WinXP-era build path with no
    modern-Windows guidance, not flagged as outdated.
55. FAQ has numerous entries tied to defunct compilers/OSes (old Intel/Absoft/
    Pacific-Sierra Fortran, SGI/Irix, RedHat 8/9-era glibc bugs, MacOS Absoft F90) —
    harmless but potentially misleading to a present-day reader; not flagged as
    historical in the file itself.
56. A few FAQ/Appendix entries point to `cactuscode.org` URLs (mailing-list archive,
    a `FixParametersForBETA13.pl` script) whose liveness could not be verified
    (no network access) but are ~20 years old.

---

*This document reflects a one-time snapshot audit (2026-08-20) of
`repos/flesh/doc/*` against `repos/flesh/src/*` and a sample of thorns
(`CactusBase/{Boundary,Time,CartGrid3D}`, `McLachlan/ML_BSSN`, `MoL`,
`SummationByParts`, `NewRad`, `GRHydro`, `EinsteinExact/KerrSchild`,
`SpacetimeX/TestNewRadX`, `GRHayLET/GRHayLHDX`, `PUGH`). It is not a substitute for
the full LaTeX manuals — treat it as a fast-lookup index plus an errata sheet, and
re-verify anything load-bearing against the cited `file:line` before depending on it.*
