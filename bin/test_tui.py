#!/usr/bin/env python3
"""
Cactus Test TUI - Interactive test suite manager.

Navigate with arrow keys / j/k, press r to run the highlighted thorn's tests.
Status indicators:
  ?  Not run yet
  ~  Running
  ✓  All tests passed (green)
  ✗  Some tests failed (red)
  !  All tests unrunnable — missing active thorns (yellow)
  *  Tests passed, but the source repo has newer commits (yellow)
"""

import argparse
import curses
import os
import re
import json
import subprocess
import sys
import threading
import time
from pathlib import Path
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional, List

def _find_cactus_home() -> Path:
    """Return the Cactus root: prefer cwd if it looks like one, else fall back to script dir."""
    cwd = Path.cwd()
    script_dir = Path(os.path.dirname(os.path.abspath(__file__)))
    for candidate in (cwd, script_dir):
        if (candidate / "configs").is_dir() or (candidate / "arrangements").is_dir():
            return candidate
    return cwd  # best guess; --debug will reveal the mismatch

CACTUS_HOME = _find_cactus_home()


_DEBUG = False        # set by _resolve_config(); read by main()
RUN_COMMAND: Optional[str] = None  # CCTK_TESTSUITE_RUN_COMMAND override

_DEFAULT_RUN_COMMAND = 'mpirun --bind-to none --oversubscribe -np $nprocs $exe $parfile'


def _resolve_config() -> str:
    global _DEBUG, RUN_COMMAND
    parser = argparse.ArgumentParser(
        description="Cactus test suite TUI",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "config", nargs="?", metavar="CONFIG",
        help="Config name (e.g. sim-cpu). Auto-detected when exactly one config exists.",
    )
    parser.add_argument(
        "--run-command", metavar="CMD",
        help=("Override CCTK_TESTSUITE_RUN_COMMAND (e.g. "
              "'srun --overlap -n $nprocs $exe $parfile'). "
              "Also honoured from the environment variable of the same name."),
    )
    parser.add_argument(
        "--debug", action="store_true",
        help="Print test-detection diagnostics and exit (does not start the TUI).",
    )
    args = parser.parse_args()
    _DEBUG = args.debug
    # CLI flag > env var > built-in default (applied at run time)
    RUN_COMMAND = (args.run_command
                   or os.environ.get('CCTK_TESTSUITE_RUN_COMMAND')
                   or _DEFAULT_RUN_COMMAND)
    if args.config:
        return args.config
    configs_dir = CACTUS_HOME / "configs"
    if configs_dir.is_dir():
        found = sorted(
            d.name for d in configs_dir.iterdir()
            if d.is_dir() and (d / "ThornList").exists()
        )
    else:
        found = []
    if len(found) == 1:
        return found[0]
    if found:
        print(f"Multiple configs found: {', '.join(found)}", file=sys.stderr)
        print("Specify one as an argument:  python test_tui.py <config>", file=sys.stderr)
    else:
        print("No configs found under configs/", file=sys.stderr)
        print("Specify config name as an argument:  python test_tui.py <config>", file=sys.stderr)
    sys.exit(1)


CONFIG = _resolve_config()
TESTS_DIR = CACTUS_HOME / "TEST" / CONFIG
STATE_FILE = TESTS_DIR / "tui_state.json"
TIMES_FILE = TESTS_DIR / "tui_times.json"
THORNLIST = CACTUS_HOME / "configs" / CONFIG / "ThornList"
ARRANGEMENTS = CACTUS_HOME / "arrangements"
EXE = CACTUS_HOME / "exe" / f"cactus_{CONFIG}"


# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------

class TestStatus(Enum):
    NOT_RUN    = "not_run"
    RUNNING    = "running"
    SUCCESS    = "success"
    FAIL       = "fail"
    UNRUNNABLE = "unrunnable"
    OUT_OF_DATE = "out_of_date"


# (display character, color-pair index)
STATUS_DISPLAY = {
    TestStatus.NOT_RUN:     ("?", 1),
    TestStatus.RUNNING:     ("~", 2),
    TestStatus.SUCCESS:     ("✓", 3),
    TestStatus.FAIL:        ("✗", 4),
    TestStatus.UNRUNNABLE:  ("!", 5),
    TestStatus.OUT_OF_DATE: ("*", 6),
}


@dataclass
class ThornInfo:
    name: str
    arrangement: str
    runnable: List[str] = field(default_factory=list)    # runnable test names
    unrunnable: List[str] = field(default_factory=list)  # unrunnable test names
    missing_reasons: dict = field(default_factory=dict)  # {test -> "THORN1 THORN2"}
    status: TestStatus = TestStatus.NOT_RUN
    repo_path: Optional[Path] = None
    stored_hash: Optional[str] = None   # git hash at time of last run
    current_hash: Optional[str] = None  # git hash right now
    passed: List[str] = field(default_factory=list)
    failed: List[str] = field(default_factory=list)
    elapsed: Optional[float] = None   # seconds the last run took

    @property
    def n_tests(self):
        return len(self.runnable) + len(self.unrunnable)

    def compute_status(self):
        if not self.runnable:
            self.status = TestStatus.UNRUNNABLE
            return
        if not self.passed and not self.failed:
            self.status = TestStatus.NOT_RUN
            return
        if self.failed:
            self.status = TestStatus.FAIL
            return
        # All passed — check if out of date
        if (self.stored_hash and self.current_hash
                and self.stored_hash != self.current_hash):
            self.status = TestStatus.OUT_OF_DATE
        else:
            self.status = TestStatus.SUCCESS


# ---------------------------------------------------------------------------
# Git helpers
# ---------------------------------------------------------------------------

def get_git_hash(repo_path: Path) -> Optional[str]:
    try:
        r = subprocess.run(
            ["git", "-C", str(repo_path), "rev-parse", "HEAD"],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            universal_newlines=True, timeout=5
        )
        return r.stdout.strip() if r.returncode == 0 else None
    except Exception:
        return None


def find_thorn_repo(arrangement: str, thorn: str) -> Optional[Path]:
    """Follow symlink for a thorn and walk up to find its git root."""
    thorn_path = ARRANGEMENTS / arrangement / thorn
    if not thorn_path.exists():
        return None
    try:
        resolved = thorn_path.resolve()
        candidate = resolved
        for _ in range(10):
            if (candidate / ".git").is_dir():
                return candidate
            parent = candidate.parent
            if parent == candidate:
                break
            candidate = parent
    except Exception:
        pass
    return None


# ---------------------------------------------------------------------------
# ThornList / test-directory scanning
# ---------------------------------------------------------------------------

def load_thornlist() -> List[tuple]:
    """Return list of (arrangement, thorn) from the active ThornList."""
    result, seen = [], set()
    if not THORNLIST.exists():
        return result
    with open(THORNLIST) as f:
        for raw in f:
            line = raw.strip()
            if not line or line.startswith('#') or line.startswith('!'):
                continue
            parts = line.split('/', 1)
            if len(parts) == 2:
                arr, thorn = parts[0].strip(), parts[1].strip()
                key = f"{arr}/{thorn}"
                if key not in seen:
                    seen.add(key)
                    result.append((arr, thorn))
    return result


_ARCHIVE_EXTS = ['.tar', '.tar.gz', '.tgz', '.tar.bz2', '.tbz', '.tar.xz', '.txz']

def find_par_tests(arrangement: str, thorn: str) -> List[str]:
    """Return par-file base-names that have matching reference data dirs/archives."""
    test_dir = ARRANGEMENTS / arrangement / thorn / "test"
    if not test_dir.is_dir():
        return []
    tests = []
    for par in sorted(test_dir.glob("*.par")):
        base = par.stem
        has_data = (test_dir / base).is_dir() or any(
            (test_dir / f"{base}{ext}").exists() for ext in _ARCHIVE_EXTS
        )
        if has_data:
            tests.append(base)
    return tests


# ---------------------------------------------------------------------------
# State persistence
# ---------------------------------------------------------------------------

def load_state() -> dict:
    if STATE_FILE.exists():
        try:
            with open(STATE_FILE) as f:
                return json.load(f)
        except Exception:
            pass
    return {}


def save_state(state: dict):
    TESTS_DIR.mkdir(parents=True, exist_ok=True)
    with open(STATE_FILE, 'w') as f:
        json.dump(state, f, indent=2)


def load_times() -> dict:
    if TIMES_FILE.exists():
        try:
            with open(TIMES_FILE) as f:
                return json.load(f)
        except Exception:
            pass
    return {}


def save_times(times: dict):
    TESTS_DIR.mkdir(parents=True, exist_ok=True)
    with open(TIMES_FILE, 'w') as f:
        json.dump(times, f, indent=2)


# ---------------------------------------------------------------------------
# Parse existing summary.log for initial status
# ---------------------------------------------------------------------------

def _parse_log_text(text: str) -> tuple:
    """Parse summary/run-out text; return (passed, failed, missed, reasons) dicts."""
    passed_by_thorn: dict = {}
    failed_by_thorn: dict = {}
    missed_by_thorn: dict = {}
    reasons_by_thorn: dict = {}

    # --- "Tests missed for lack of thorns" / nprocs section ---
    # Block format (4-space indent on the test line, 6-space on sub-lines):
    #     testname in ThornName
    #       (description or par path)
    #       Missing:  THORN1 THORN2
    block_re = re.compile(
        r'^ {4}(\S+) in (\w+)\s*\n'        # test + thorn
        r'(?:^ {6}\([^\n]*\)\s*\n)?'        # optional description
        r'^ {6}(Missing:.*?|Requires.*?)\s*$',
        re.MULTILINE
    )
    for m in block_re.finditer(text):
        test_name, thorn, reason = m.group(1), m.group(2), m.group(3).strip()
        missed_by_thorn.setdefault(thorn, []).append(test_name)
        reasons_by_thorn.setdefault(thorn, {})[test_name] = reason

    # --- "Tests passed:" section ---
    m = re.search(r'Tests passed:\n(.*?)(?:Tests failed:|={4,})', text, re.DOTALL)
    if m:
        for pm in re.finditer(r'(\S+) \(from (\w+)\)', m.group(1)):
            passed_by_thorn.setdefault(pm.group(2), []).append(pm.group(1))

    # --- "Tests failed:" section ---
    m = re.search(r'Tests failed:\n(.*?)(?:={4,})', text, re.DOTALL)
    if m:
        for pm in re.finditer(r'(\S+) \(from (\w+)\)', m.group(1)):
            failed_by_thorn.setdefault(pm.group(2), []).append(pm.group(1))

    return passed_by_thorn, failed_by_thorn, missed_by_thorn, reasons_by_thorn


def parse_summary_log() -> tuple:
    """
    Read from all available run logs (summary.log, run.out, run1.out …) and
    return the results from whichever file has the most complete data.

    Returns four dicts:
      passed_by_thorn   {thorn_name -> [test, ...]}
      failed_by_thorn   {thorn_name -> [test, ...]}
      missed_by_thorn   {thorn_name -> [test, ...]}  (unrunnable tests)
      reasons_by_thorn  {thorn_name -> {test -> "MISSING_THORN ..."}}
    """
    candidates = [
        TESTS_DIR / "summary.log",
        *sorted(CACTUS_HOME.glob("run*.out"), key=lambda p: p.stat().st_mtime,
                reverse=True),
    ]

    best: tuple = ({}, {}, {}, {})
    best_score = -1

    for path in candidates:
        if not path.exists():
            continue
        try:
            text = path.read_text(errors='replace')
        except OSError:
            continue
        result = _parse_log_text(text)
        passed, failed, missed, _ = result
        score = sum(len(v) for v in passed.values()) + sum(len(v) for v in missed.values())
        if score > best_score:
            best_score = score
            best = result

    return best


# ---------------------------------------------------------------------------
# Build thorn list
# ---------------------------------------------------------------------------

def build_thorns(state: dict, times: dict) -> List[ThornInfo]:
    """Assemble ThornInfo objects for all thorns that have tests."""
    pairs = load_thornlist()
    passed_log, failed_log, missed_log, reasons_log = parse_summary_log()

    # All thorn names that appear anywhere in the summary
    summary_thorns = set(passed_log) | set(failed_log) | set(missed_log)

    result: List[ThornInfo] = []
    for arrangement, thorn_name in pairs:
        par_tests = find_par_tests(arrangement, thorn_name)
        in_summary = thorn_name in summary_thorns

        if not par_tests and not in_summary:
            continue  # no tests at all

        info = ThornInfo(name=thorn_name, arrangement=arrangement)

        # Determine runnable vs unrunnable split from summary.log
        missed = set(missed_log.get(thorn_name, []))
        info.runnable = [t for t in par_tests if t not in missed]
        info.unrunnable = list(missed)
        info.missing_reasons = reasons_log.get(thorn_name, {})

        # Repo / git hash
        info.repo_path = find_thorn_repo(arrangement, thorn_name)
        if info.repo_path:
            info.current_hash = get_git_hash(info.repo_path)

        # Load from tui_state.json (overrides summary.log)
        if thorn_name in state:
            s = state[thorn_name]
            info.stored_hash = s.get('hash')
            info.passed = s.get('passed', [])
            info.failed = s.get('failed', [])
            # Per-test times (from tui_times.json) take priority over the
            # total wall time stored in tui_state.json; they exclude Perl
            # startup overhead so the clock indicator is more accurate.
            thorn_times = times.get(thorn_name, {})
            if thorn_times:
                info.elapsed = sum(thorn_times.values())
            else:
                info.elapsed = s.get('elapsed')
            # If the TUI previously learned (via a real run) which tests are
            # unrunnable, restore that finer-grained info.
            if 'unrunnable' in s:
                saved_unrunnable = s['unrunnable']
                saved_set = set(saved_unrunnable)
                info.runnable = [t for t in info.runnable if t not in saved_set]
                for t in saved_unrunnable:
                    if t not in info.unrunnable:
                        info.unrunnable.append(t)
            if 'missing_reasons' in s:
                info.missing_reasons.update(s['missing_reasons'])
        else:
            # Bootstrap from summary.log
            info.passed = passed_log.get(thorn_name, [])
            info.failed = failed_log.get(thorn_name, [])

        info.compute_status()
        result.append(info)

    result.sort(key=lambda t: t.name.lower())
    return result


# ---------------------------------------------------------------------------
# Background test runner
# ---------------------------------------------------------------------------

class TestRunner:
    def __init__(self, thorn: ThornInfo):
        self.thorn = thorn
        self._lock = threading.Lock()
        self._lines: List[str] = []
        self.done = False
        self.killed = False
        self.passed: List[str] = []
        self.failed: List[str] = []
        self._proc: Optional[subprocess.Popen] = None
        self.returncode: Optional[int] = None
        self.elapsed: Optional[float] = None
        self._start_time: float = 0.0
        self._raw_count = 0           # total lines received before filtering
        self._raw_lines: List[str] = []  # all lines, unfiltered, for vi view
        self.test_times: dict = {}    # test_name -> elapsed seconds (per individual test)
        self._test_start: float = 0.0

    @property
    def perl_pid(self) -> Optional[int]:
        return self._proc.pid if self._proc else None

    def start(self):
        threading.Thread(target=self._run, daemon=True).start()

    def kill(self):
        """Kill the running subprocess and its children."""
        self.killed = True
        proc = self._proc
        if proc and proc.poll() is None:
            try:
                import signal, os as _os
                _os.killpg(_os.getpgid(proc.pid), signal.SIGTERM)
            except Exception:
                try:
                    proc.kill()
                except Exception:
                    pass
        self._append("[KILLED]")

    def lines(self) -> List[str]:
        with self._lock:
            return list(self._lines)

    # Lines the Perl script always emits as boilerplate (menu, separators,
    # summary headers) that are noise in the TUI output panel.
    _MENU_NOISE = re.compile(
        r'^\s*('
        # separator lines (dashes or equals)
        r'-{3,}|={3,}'
        # PrintHeader banner
        r'|Cactus Code Test Suite Tool'
        # interactive menu items
        r'|--- Menu ---'
        r'|Run entire set of tests'
        r'|Choose test from'
        r'|Rerun previous test'
        r'|Print tolerance table'
        r'|Compare all files'
        r'|Customize testsuite'
        r'|Quit \[Q\]'
        r'|Select choice'
        # run header
        r'|Processes: \d'
        # WriteFullResults section headers and stats
        r'|Warnings for configuration'
        r'|Tests missed for lack of thorns'
        r'|Testsuite Summary for'
        r'|Suitable testsuite parameter'
        r'|Thorns with no valid'
        r'|Thorns with unrecognized'
        r'|Run details for configuration'
        r'|Summary for configuration'
        r'|Total available tests'
        r'|Unrunnable tests'
        r'|Runnable tests'
        r'|Total number of thorns'
        r'|Number of tested'
        r'|Number of tests passed'
        r'|Number passed only'
        r'|set tolerance'
        r'|Number failed'
        r'|Tests passed:'
        r'|Tests failed:'
        # "Tests missed" sub-lines
        r'|Missing:'
        r'|Requires:'
        r')'
    )
    # Matches individual "  testname (from Thorn)" lines in the summary lists.
    _SUMMARY_ENTRY = re.compile(r'^\s+\S+ \(from \w+\)\s*$')
    # Matches "    testname in ThornName" lines (unrunnable-test block entries).
    _MISSED_ENTRY = re.compile(r'^\s+\S+ in \w+\s*$')
    # Matches "      (description text)" lines in the unrunnable-test block.
    _DESC_LINE = re.compile(r'^\s+\(')

    def _append(self, line: str):
        self._raw_count += 1
        with self._lock:
            self._raw_lines.append(line)
            if len(self._raw_lines) > 5000:
                self._raw_lines.pop(0)
        if not line.strip():
            return
        if (self._MENU_NOISE.search(line)
                or self._SUMMARY_ENTRY.match(line)
                or self._MISSED_ENTRY.match(line)
                or self._DESC_LINE.match(line)):
            return
        with self._lock:
            self._lines.append(line)
            if len(self._lines) > 200:
                self._lines.pop(0)

    def _run(self):
        env = dict(os.environ)
        env['CCTK_TESTSUITE_RUN_TESTS'] = self.thorn.name
        env['CCTK_TESTSUITE_RUN_PROCESSORS'] = '2'
        env['CCTK_TESTSUITE_RUN_COMMAND'] = RUN_COMMAND

        cmd = [
            'perl', '-s',
            str(CACTUS_HOME / 'repos' / 'flesh' / 'lib' / 'sbin' / 'RunTest.pl'),
            'no', str(CACTUS_HOME), CONFIG,
        ]

        current_test = None
        self._start_time = time.monotonic()
        try:
            proc = subprocess.Popen(
                cmd, env=env, cwd=str(CACTUS_HOME),
                stdin=subprocess.DEVNULL,   # prevent srun/SLURM from touching the TUI terminal
                stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                universal_newlines=True, bufsize=1,
                start_new_session=True,  # put in own process group for clean kill
            )
            self._proc = proc
            for raw in proc.stdout:
                if self.killed:
                    break
                line = raw.rstrip()
                self._append(line)

                m = re.match(r'\s+Test \w+: (\S+)', line)
                if m:
                    current_test = m.group(1)
                    self._test_start = time.monotonic()

                if current_test:
                    if re.search(r'\bSuccess:', line):
                        self.test_times[current_test] = time.monotonic() - self._test_start
                        self.passed.append(current_test)
                        current_test = None
                    elif re.search(r'\bFailure:', line):
                        self.test_times[current_test] = time.monotonic() - self._test_start
                        self.failed.append(current_test)
                        current_test = None

            self.returncode = proc.wait()
        except Exception as exc:
            self._append(f"[ERROR] {exc}")
            self.returncode = -1

        self.elapsed = time.monotonic() - self._start_time
        self.done = True


# ---------------------------------------------------------------------------
# Process-tree helper
# ---------------------------------------------------------------------------

def _direct_children(pid: int) -> List[int]:
    """Return direct child PIDs for `pid` using /proc/{pid}/task/*/children.
    This reads only the target process's entries — not all of /proc — so it
    stays fast even on a cluster with thousands of running processes."""
    result = []
    try:
        task_dir = f'/proc/{pid}/task'
        for tid in os.listdir(task_dir):
            try:
                with open(f'{task_dir}/{tid}/children') as fh:
                    for token in fh.read().split():
                        try:
                            result.append(int(token))
                        except ValueError:
                            pass
            except OSError:
                pass
    except OSError:
        pass
    return result


def _descendants_named(root_pid: int, name: str) -> List[str]:
    """Return PIDs (as strings) of all descendants of root_pid whose comm == name."""
    result = []
    queue = [root_pid]
    seen: set = set()
    while queue:
        pid = queue.pop(0)
        if pid in seen:
            continue
        seen.add(pid)
        for child in _direct_children(pid):
            try:
                comm = open(f'/proc/{child}/comm').read().strip()
                if comm == name:
                    result.append(str(child))
            except OSError:
                pass
            queue.append(child)
    return result


# ---------------------------------------------------------------------------
# TUI
# ---------------------------------------------------------------------------

_SPIN = "⠋⠙⠹⠸⠼⠴⠦⠧⠇⠏"


def _clock_indicator(elapsed: Optional[float]) -> str:
    """Return a slow-run indicator: ⏱ per minute over 1 min, ⏱×N at 3+."""
    if elapsed is None or elapsed < 60:
        return ""
    minutes = int(elapsed // 60)
    if minutes == 1:
        return " ⏱"
    elif minutes == 2:
        return " ⏱⏱"
    else:
        return f" ⏱×{minutes}"


class TUI:
    def __init__(self):
        self.state: dict = load_state()
        self.times: dict = load_times()   # {thorn_name: {test_name: seconds}}
        self.thorns: List[ThornInfo] = []
        self.selected = 0
        self.scroll = 0
        self.runner: Optional[TestRunner] = None
        self.run_queue: List[ThornInfo] = []   # pending thorns for 'A' run-all
        self.out_lines: List[str] = []   # general (non-thorn) messages
        self.msg = ""
        self._spin_i = 0
        self._spin_t = 0.0
        self._cactus_pids: dict = {}   # thorn_name -> List[str] of cactus child PIDs
        self._last_pid_check = 0.0
        self._out_paths: dict = {}        # thorn_name -> Path of saved raw output
        self.runners: dict = {}           # thorn_name -> TestRunner
        self._queue_runners: set = set()  # names of runners started by A/t (queue slots)
        self._queue_parallelism: int = 1  # max simultaneous queue runners (set by digit keys)
        self._last_out_lines: dict = {}   # thorn_name -> final panel lines after done
        self._scr_h: int = 24             # last known screen height (updated each tick)
        self._pid_scan_busy: bool = False # True while a background scan thread is running
        self._empty_pid_count: int = 0    # consecutive all-empty scan results (SLURM backoff)
        self._waiting_to_quit: bool = False  # set by 'wait' choice in quit prompt

    # ------------------------------------------------------------------
    # Setup
    # ------------------------------------------------------------------

    @staticmethod
    def _init_colors():
        curses.start_color()
        curses.use_default_colors()
        curses.init_pair(1, -1, -1)                              # default
        curses.init_pair(2, curses.COLOR_CYAN,    -1)            # running
        curses.init_pair(3, curses.COLOR_GREEN,   -1)            # success
        curses.init_pair(4, curses.COLOR_RED,     -1)            # fail
        curses.init_pair(5, curses.COLOR_YELLOW,  -1)            # unrunnable
        curses.init_pair(6, curses.COLOR_YELLOW,  -1)            # out-of-date
        curses.init_pair(7, curses.COLOR_WHITE, curses.COLOR_BLUE)  # selected row
        curses.init_pair(8, curses.COLOR_BLACK, curses.COLOR_CYAN)  # header/footer
        curses.init_pair(9, curses.COLOR_YELLOW, curses.COLOR_BLACK)  # notification bar

    # ------------------------------------------------------------------
    # Drawing
    # ------------------------------------------------------------------

    def _list_height(self, h: int) -> int:
        out_h = min(8, max(3, h // 4))
        return h - 2 - 1 - out_h  # header + footer + divider + output

    def _out_height(self, h: int) -> int:
        return min(8, max(3, h // 4))

    def _spin_char(self) -> str:
        now = time.monotonic()
        if now - self._spin_t > 0.1:
            self._spin_i = (self._spin_i + 1) % len(_SPIN)
            self._spin_t = now
        return _SPIN[self._spin_i]

    def _draw_row(self, stdscr, row: int, w: int, thorn: ThornInfo, selected: bool):
        if thorn.status == TestStatus.RUNNING:
            ch = self._spin_char()
        else:
            ch, _ = STATUS_DISPLAY[thorn.status]
        _, cpair = STATUS_DISPLAY[thorn.status]

        n_run   = len(thorn.runnable)
        n_unrun = len(thorn.unrunnable)
        if n_unrun and not n_run:
            test_info = f"{n_unrun} tests (unrunnable)"
        elif n_unrun:
            test_info = f"{n_run} run + {n_unrun} unrunnable"
        else:
            test_info = f"{n_run} tests"

        name_col = f"{thorn.name:<38}"
        line = f"  [{ch}] {name_col} {test_info}{_clock_indicator(thorn.elapsed)}"

        if selected:
            stdscr.attron(curses.color_pair(7) | curses.A_BOLD)
            try:
                stdscr.addstr(row, 0, line.ljust(w)[:w - 1])
            except curses.error:
                pass
            stdscr.attroff(curses.color_pair(7) | curses.A_BOLD)
        else:
            try:
                stdscr.addstr(row, 0, "  [")
                stdscr.attron(curses.color_pair(cpair) | curses.A_BOLD)
                stdscr.addstr(ch)
                stdscr.attroff(curses.color_pair(cpair) | curses.A_BOLD)
                stdscr.addstr(row, 4, f"] {name_col} {test_info}{_clock_indicator(thorn.elapsed)}"[:w - 5])
            except curses.error:
                pass

    def draw(self, stdscr):
        h, w = stdscr.getmaxyx()
        stdscr.erase()

        list_h = self._list_height(h)
        out_h  = self._out_height(h)

        # Header
        title = f" Cactus Test Suite [{CONFIG}]  ({len(self.thorns)} thorns with tests)"
        try:
            stdscr.attron(curses.color_pair(8) | curses.A_BOLD)
            stdscr.addstr(0, 0, title.ljust(w)[:w - 1])
            stdscr.attroff(curses.color_pair(8) | curses.A_BOLD)
        except curses.error:
            pass

        # Thorn list
        for i in range(list_h):
            idx = i + self.scroll
            if idx >= len(self.thorns):
                break
            self._draw_row(stdscr, i + 1, w, self.thorns[idx], idx == self.selected)

        # Scroll indicators
        if self.scroll > 0:
            try:
                stdscr.addstr(1, w - 3, " ↑ ")
            except curses.error:
                pass
        if self.scroll + list_h < len(self.thorns):
            try:
                stdscr.addstr(list_h, w - 3, " ↓ ")
            except curses.error:
                pass

        # Divider
        div_row = 1 + list_h
        try:
            stdscr.attron(curses.color_pair(8))
            stdscr.addstr(div_row, 0, ("─" * w)[:w - 1])
            stdscr.attroff(curses.color_pair(8))
        except curses.error:
            pass

        # Notification bar — always visible below the divider when msg is set.
        msg_rows = 0
        if self.msg:
            msg_row = div_row + 1
            if msg_row < h - 1:
                try:
                    stdscr.attron(curses.color_pair(9) | curses.A_BOLD)
                    stdscr.addstr(msg_row, 0, f" {self.msg}".ljust(w)[:w - 1])
                    stdscr.attroff(curses.color_pair(9) | curses.A_BOLD)
                except curses.error:
                    pass
                msg_rows = 1

        # Determine output for the selected thorn.
        sel_thorn = self.thorns[self.selected] if self.thorns else None
        sel_runner = self.runners.get(sel_thorn.name) if sel_thorn else None
        if sel_runner and not sel_runner.done:
            panel_lines = sel_runner.lines() or [f"Running {sel_thorn.name} … (no output yet)"]
        elif sel_thorn and sel_thorn.name in self._last_out_lines:
            panel_lines = self._last_out_lines[sel_thorn.name]
        else:
            panel_lines = self.out_lines or []

        # If the selected thorn is running, pin a status banner above the output.
        banner_rows = 0
        if sel_runner and not sel_runner.done:
            spin = self._spin_char()
            n_done = len(sel_runner.passed) + len(sel_runner.failed)
            n_total = len(sel_runner.thorn.runnable)
            n_active = sum(1 for r in self.runners.values() if not r.done)
            queue_info = f"  ({len(self.run_queue)} queued)" if self.run_queue else ""
            parallel_info = f"  [{n_active} running]" if n_active > 1 else ""
            perl_pid = sel_runner.perl_pid
            pid_str = f"  perl:{perl_pid}" if perl_pid else ""
            cpids = self._cactus_pids.get(sel_thorn.name, [])
            cactus_str = ("  cactus:" + ",".join(cpids) if cpids else "  cactus:none")
            banner = (f" {spin} RUNNING: {sel_thorn.name}"
                      f"  {n_done}/{n_total} done{queue_info}{parallel_info}"
                      f"{pid_str}{cactus_str}"
                      f"  k:kill ")
            try:
                stdscr.attron(curses.color_pair(2) | curses.A_BOLD)
                stdscr.addstr(div_row + 1 + msg_rows, 0, banner.ljust(w)[:w - 1])
                stdscr.attroff(curses.color_pair(2) | curses.A_BOLD)
                banner_rows = 1
            except curses.error:
                pass

        body_h = out_h - msg_rows - banner_rows
        for i, line in enumerate(panel_lines[-body_h:]):
            row = div_row + 1 + msg_rows + banner_rows + i
            if row >= h - 1:
                break
            try:
                stdscr.addstr(row, 0, line[:w - 1])
            except curses.error:
                pass

        # Footer
        sel_active = sel_runner and not sel_runner.done
        k_hint = "k:Kill" if sel_active else "k/↑:Up"
        n_running = sum(1 for r in self.runners.values() if not r.done)
        run_note = f"  [{n_running} running]" if n_running else ""
        queue_note = f"  [{len(self.run_queue)} queued]" if self.run_queue else ""
        par_note = f"  [par:{self._queue_parallelism}]" if self._queue_parallelism > 1 else ""
        footer = (f" ↑↓/j{k_hint}  r:Run  A:All?  t:Retry✗  c:Clear✗  C:ClearAll  n:Next  s:Status  v:View  w:Write  f:Refresh  q:Quit"
                  f"{run_note}{queue_note}{par_note}   ?:not-run  ✓:pass  ✗:fail  !:unrunnable  *:stale ")
        try:
            stdscr.attron(curses.color_pair(8))
            stdscr.addstr(h - 1, 0, footer.ljust(w)[:w - 1])
            stdscr.attroff(curses.color_pair(8))
        except curses.error:
            pass

        stdscr.refresh()

    # ------------------------------------------------------------------
    # Actions
    # ------------------------------------------------------------------

    def _clamp_scroll(self, h: int):
        list_h = self._list_height(h)
        if self.selected < self.scroll:
            self.scroll = self.selected
        elif self.selected >= self.scroll + list_h:
            self.scroll = self.selected - list_h + 1
        self.scroll = max(0, min(self.scroll, max(0, len(self.thorns) - list_h)))

    def _ensure_visible(self, thorn_name: str):
        """Scroll so the named thorn's row is on-screen (does not move selection)."""
        try:
            idx = next(i for i, t in enumerate(self.thorns) if t.name == thorn_name)
        except StopIteration:
            return
        list_h = self._list_height(self._scr_h)
        if idx < self.scroll:
            self.scroll = idx
        elif idx >= self.scroll + list_h:
            self.scroll = idx - list_h + 1
        self.scroll = max(0, min(self.scroll, max(0, len(self.thorns) - list_h)))

    def _start_runner(self, thorn: ThornInfo):
        thorn.status = TestStatus.RUNNING
        r = TestRunner(thorn)
        r._finalized = False
        self.runners[thorn.name] = r
        # Reset PID scan backoff so the first scan after launch is prompt.
        self._empty_pid_count = 0
        self._last_pid_check = 0.0
        r.start()

    def run_selected(self):
        """Run (or re-run) the highlighted thorn; explain if unrunnable."""
        thorn = self.thorns[self.selected]
        existing = self.runners.get(thorn.name)
        if existing and not existing.done:
            self.msg = f"{thorn.name} is already running."
            return
        # Remove from the A/t queue so the queue slot doesn't re-run it later.
        self.run_queue = [t for t in self.run_queue if t is not thorn]
        if not thorn.runnable:
            lines = [f"{thorn.name}: no runnable tests — all require missing active thorns:"]
            for test in thorn.unrunnable:
                reason = thorn.missing_reasons.get(test, "reason unknown")
                lines.append(f"  {test}: {reason}")
            self.out_lines = lines
            return
        self._start_runner(thorn)

    def _queue_active(self) -> bool:
        """True if any queue-managed runner is still running."""
        return any(
            not self.runners[n].done
            for n in self._queue_runners
            if n in self.runners
        )

    def _launch_queue_batch(self, needs_run: list):
        """Start up to _queue_parallelism runners from needs_run; rest go to run_queue."""
        self._queue_runners.clear()
        n = min(self._queue_parallelism, len(needs_run))
        self.run_queue = list(needs_run[n:])
        for thorn in needs_run[:n]:
            self._start_runner(thorn)
            self._queue_runners.add(thorn.name)

    def _jump_to_first_runner(self, names: list):
        """Move the cursor to the first thorn in `names` that exists in self.thorns."""
        for name in names:
            try:
                idx = next(i for i, t in enumerate(self.thorns) if t.name == name)
                self.selected = idx
                self._ensure_visible(name)
                return
            except StopIteration:
                pass

    def run_all(self):
        """Queue all NOT_RUN and OUT_OF_DATE thorns (skips failures — use t to retry those)."""
        if self._queue_active():
            names = [n for n in self._queue_runners if n in self.runners and not self.runners[n].done]
            self.msg = f"Queue already running ({', '.join(names)}) — press k to kill."
            return
        needs_run = [
            t for t in self.thorns
            if t.runnable and t.status in (TestStatus.NOT_RUN, TestStatus.OUT_OF_DATE)
        ]
        if not needs_run:
            self.msg = "No unrun or stale thorns — use t to retry failures, c to clear them."
            return
        self._launch_queue_batch(needs_run)
        self._jump_to_first_runner([t.name for t in needs_run[:self._queue_parallelism]])
        par = self._queue_parallelism
        self.msg = f"Run-all: {len(needs_run)} thorns queued, parallelism={par}."

    def _clear_thorn(self, thorn: 'ThornInfo'):
        """Reset a thorn's pass/fail results to NOT_RUN and persist the change."""
        thorn.passed = []
        thorn.failed = []
        thorn.compute_status()
        self.state[thorn.name] = {
            'hash': thorn.stored_hash,
            'passed': [],
            'failed': [],
            'elapsed': thorn.elapsed,
            'unrunnable': thorn.unrunnable,
            'missing_reasons': thorn.missing_reasons,
        }

    def clear_failed(self):
        """Reset all FAIL thorns to NOT_RUN and save state."""
        targets = [t for t in self.thorns if t.status == TestStatus.FAIL]
        if not targets:
            self.msg = "No failed thorns to clear."
            return
        target_set = {t.name for t in targets}
        self.run_queue = [t for t in self.run_queue if t.name not in target_set]
        for thorn in targets:
            self._clear_thorn(thorn)
        snap = dict(self.state)
        threading.Thread(target=lambda: save_state(snap), daemon=True).start()
        self.msg = f"Cleared {len(targets)} failed thorn(s) → ?."

    def clear_all(self):
        """Reset all non-unrunnable, non-running thorns to NOT_RUN and save state."""
        targets = [t for t in self.thorns
                   if t.status not in (TestStatus.UNRUNNABLE, TestStatus.RUNNING)]
        if not targets:
            self.msg = "Nothing to clear."
            return
        target_set = {t.name for t in targets}
        self.run_queue = [t for t in self.run_queue if t.name not in target_set]
        for thorn in targets:
            self._clear_thorn(thorn)
        snap = dict(self.state)
        threading.Thread(target=lambda: save_state(snap), daemon=True).start()
        self.msg = f"Cleared {len(targets)} thorn(s) → ?."

    def show_status(self):
        """Show per-test pass/fail/unrunnable breakdown for the highlighted thorn."""
        thorn = self.thorns[self.selected]
        lines = [f"=== {thorn.name} ==="]
        if thorn.passed:
            lines.append(f"  Passed  ({len(thorn.passed)}): {', '.join(thorn.passed)}")
        if thorn.failed:
            lines.append(f"  Failed  ({len(thorn.failed)}): {', '.join(thorn.failed)}")
        if thorn.unrunnable:
            lines.append(f"  Unrunnable ({len(thorn.unrunnable)}):")
            for test in thorn.unrunnable:
                reason = thorn.missing_reasons.get(test, "reason unknown")
                lines.append(f"    {test}: {reason}")
        if not thorn.passed and not thorn.failed and not thorn.unrunnable:
            lines.append("  Not run yet.")
        self.out_lines = lines

    def retry_failed(self):
        """Queue and run all thorns whose last run had failures."""
        if self._queue_active():
            names = ', '.join(n for n in self._queue_runners if n in self.runners and not self.runners[n].done)
            self.msg = f"Queue already running ({names}) — press k to kill."
            return
        needs_run = [t for t in self.thorns if t.runnable and t.status == TestStatus.FAIL]
        if not needs_run:
            self.msg = "No failed thorns to retry."
            return
        self._launch_queue_batch(needs_run)
        self._jump_to_first_runner([t.name for t in needs_run[:self._queue_parallelism]])
        par = self._queue_parallelism
        self.msg = f"Retry: {len(needs_run)} failed thorn(s) queued, parallelism={par}."

    def kill_running(self):
        """Kill the selected thorn's runner.

        If it was a queue-managed runner, also kill all other queue runners and
        clear the pending queue so the entire run-all/retry is aborted.
        """
        thorn = self.thorns[self.selected]
        r = self.runners.get(thorn.name)
        if r and not r.done:
            r.kill()
            if thorn.name in self._queue_runners:
                # Abort the whole queue batch.
                for name in list(self._queue_runners):
                    if name != thorn.name:
                        other = self.runners.get(name)
                        if other and not other.done:
                            other.kill()
                self._queue_runners.clear()
                self.run_queue.clear()
                self.msg = f"Killed {thorn.name} — queue cleared."
            else:
                self.msg = f"Killed {thorn.name}."
        else:
            self.msg = f"{thorn.name} is not currently running."

    def next_untested(self, h: int):
        """Move the cursor to the next NOT_RUN or FAIL thorn."""
        n = len(self.thorns)
        for offset in range(1, n + 1):
            idx = (self.selected + offset) % n
            if self.thorns[idx].status in (TestStatus.NOT_RUN, TestStatus.FAIL):
                self.selected = idx
                self._clamp_scroll(h)
                return
        self.msg = "No untested or failed thorns remaining."

    def _finish_runner(self, r: 'TestRunner'):
        r._finalized = True
        thorn = r.thorn
        thorn.passed = r.passed
        thorn.failed = r.failed
        if thorn.repo_path:
            thorn.stored_hash = thorn.current_hash

        # Snapshot raw output early so we can parse it below.
        with r._lock:
            raw_snapshot = list(r._raw_lines)

        # If no tests ran, parse the raw output for "Tests missed for lack of
        # thorns" entries.  The Perl script found all tests unrunnable and
        # exited without running anything; update runnable/unrunnable so that
        # compute_status() can return UNRUNNABLE instead of NOT_RUN.
        if not r.passed and not r.failed and not r.killed:
            raw_text = '\n'.join(raw_snapshot)
            _, _, missed_map, reasons_map = _parse_log_text(raw_text)
            newly_missed = missed_map.get(thorn.name, [])
            if newly_missed:
                missed_set = set(newly_missed)
                thorn.runnable = [t for t in thorn.runnable if t not in missed_set]
                for t in newly_missed:
                    if t not in thorn.unrunnable:
                        thorn.unrunnable.append(t)
                thorn.missing_reasons.update(reasons_map.get(thorn.name, {}))

        thorn.compute_status()

        # Merge per-test times into self.times and recompute thorn.elapsed.
        if r.test_times:
            self.times.setdefault(thorn.name, {}).update(r.test_times)
        thorn_times = self.times.get(thorn.name, {})
        thorn.elapsed = sum(thorn_times.values()) if thorn_times else r.elapsed

        self.state[thorn.name] = {
            'hash': thorn.stored_hash,
            'passed': thorn.passed,
            'failed': thorn.failed,
            'elapsed': r.elapsed,
            'unrunnable': thorn.unrunnable,
            'missing_reasons': thorn.missing_reasons,
        }
        self._cactus_pids.pop(thorn.name, None)

        # Snapshot everything needed for disk I/O before leaving the main thread.
        state_snapshot = dict(self.state)
        times_snapshot = {k: dict(v) for k, v in self.times.items()}
        out_dir = CACTUS_HOME / 'TEST' / CONFIG
        out_file = out_dir / f'{thorn.name}_tui.out'
        thorn_name = thorn.name

        def _write_files():
            try:
                save_state(state_snapshot)
            except Exception:
                pass
            try:
                save_times(times_snapshot)
            except Exception:
                pass
            try:
                out_dir.mkdir(parents=True, exist_ok=True)
                out_file.write_text('\n'.join(raw_snapshot) + '\n')
                self._out_paths[thorn_name] = out_file
            except Exception:
                pass

        threading.Thread(target=_write_files, daemon=True).start()

        rc = r.returncode
        rc_str = f"exit {rc}" if rc is not None else "exit ?"
        killed_str = "  [KILLED]" if r.killed else ""
        summary = (f"[DONE] {thorn.name}: {len(r.passed)} passed, "
                   f"{len(r.failed)} failed  ({rc_str}){killed_str}"
                   f"  perl_pid={r.perl_pid}"
                   f"  raw={r._raw_count} lines")

        visible = r.lines()
        if not visible:
            stored = [summary,
                      f"  (all {r._raw_count} output lines were filtered as boilerplate)"]
        else:
            stored = [summary] + visible
        self._last_out_lines[thorn.name] = stored

        # If this was a queue-managed runner, free its slot and fill it from the queue.
        if thorn.name in self._queue_runners:
            self._queue_runners.discard(thorn.name)
            while self.run_queue and len(self._queue_runners) < self._queue_parallelism:
                next_thorn = self.run_queue.pop(0)
                existing = self.runners.get(next_thorn.name)
                if existing and not existing.done:
                    continue  # already running via manual r — skip this slot
                if next_thorn.runnable:
                    self._start_runner(next_thorn)
                    self._queue_runners.add(next_thorn.name)
                    self._ensure_visible(next_thorn.name)
        # Always keep the just-finished thorn visible so the user can see its result.
        self._ensure_visible(thorn.name)

    def write_testsuite_output(self):
        """Generate a SimFactory-compatible testsuite output file.

        File is written to TEST/<config>/<hostname>__<nprocs>_<nprocs>.log and
        contains the concatenated raw Perl output for every thorn run so far,
        followed by the Testsuite Summary section in the standard SimFactory
        format so the file can be dropped into the et-tester results directory
        for comparison against other machines.
        """
        import socket
        import datetime

        # Prefer simfactory's machine name; fall back to the OS hostname.
        sim_bin = CACTUS_HOME / 'simfactory' / 'bin' / 'sim'
        hostname = None
        if sim_bin.exists():
            try:
                result = subprocess.run(
                    [str(sim_bin), 'whoami'],
                    stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                    timeout=10,
                )
                # Output: "Current machine: <name>"
                for line in result.stdout.decode().splitlines():
                    if line.startswith('Current machine:'):
                        hostname = line.split(':', 1)[1].strip()
                        break
            except Exception:
                pass
        if not hostname:
            hostname = socket.gethostname().split('.')[0]
        nprocs = 2  # matches CCTK_TESTSUITE_RUN_PROCESSORS
        out_file = TESTS_DIR / f'{hostname}__{nprocs}_{nprocs}.log'

        # Collect stats from the current thorn list.
        all_passed: list = []   # (test_name, thorn_name)
        all_failed: list = []
        total_tests = 0
        runnable_tests = 0
        unrunnable_tests = 0
        tested_thorns: set = set()

        for thorn in self.thorns:
            total_tests += len(thorn.runnable) + len(thorn.unrunnable)
            runnable_tests += len(thorn.runnable)
            unrunnable_tests += len(thorn.unrunnable)
            for t in thorn.passed:
                all_passed.append((t, thorn.name))
                tested_thorns.add(thorn.name)
            for t in thorn.failed:
                all_failed.append((t, thorn.name))
                tested_thorns.add(thorn.name)

        try:
            total_thorns = len(load_thornlist())
        except Exception:
            total_thorns = len(self.thorns)

        # Build the output content (file I/O for each thorn's raw log happens
        # in the background thread below).
        def _write():
            lines: list = []
            lines.append(f'Running simulation {hostname}')
            lines.append(f'Running test suite {CONFIG}-testsuite')
            lines.append('')

            # Concatenate each thorn's raw Perl output in alphabetical order.
            for thorn in sorted(self.thorns, key=lambda t: t.name.lower()):
                raw_file = TESTS_DIR / f'{thorn.name}_tui.out'
                if raw_file.exists():
                    try:
                        lines.append(raw_file.read_text().rstrip())
                        lines.append('')
                    except Exception:
                        pass

            # Testsuite Summary section.
            lines.append('------------------------------------------------------------------------')
            lines.append('')
            lines.append(f'  Testsuite Summary for configuration {CONFIG}')
            lines.append('  -----------------')
            lines.append('')
            lines.append('  Suitable testsuite parameter files found in:')
            lines.append('')
            for thorn in sorted(self.thorns, key=lambda t: t.name.lower()):
                n = len(thorn.runnable) + len(thorn.unrunnable)
                if n:
                    lines.append(f'    {thorn.name} [{n}]')
            lines.append('')
            lines.append(f'  Run details for configuration {CONFIG}')
            lines.append('  -----------------')
            lines.append('')
            user = os.environ.get('USER', os.environ.get('LOGNAME', 'unknown'))
            lines.append(f'    User                     -> {user}')
            lines.append('')
            lines.append(f'    Total available tests    -> {total_tests}')
            lines.append(f'    Unrunnable tests         -> {unrunnable_tests}')
            lines.append(f'    Runnable tests           -> {runnable_tests}')
            lines.append(f'    Total number of thorns   -> {total_thorns}')
            lines.append(f'    Number of tested thorns  -> {len(tested_thorns)}')
            lines.append(f'    Number of tests passed   -> {len(all_passed)}')
            lines.append(f'    Number failed            -> {len(all_failed)}')
            lines.append('')
            lines.append('  Tests passed:')
            lines.append('')
            for test, thorn in all_passed:
                lines.append(f'    {test} (from {thorn})')
            lines.append('')
            lines.append('  Tests failed:')
            lines.append('')
            for test, thorn in all_failed:
                lines.append(f'    {test} (from {thorn})')
            lines.append('')
            lines.append('========================================================================')
            lines.append('')
            ts = datetime.datetime.now().strftime('%a %d %b %Y %I:%M:%S %p')
            lines.append(f'Simfactory Done at date: {ts}')
            lines.append('')

            try:
                TESTS_DIR.mkdir(parents=True, exist_ok=True)
                out_file.write_text('\n'.join(lines))
                self.msg = f'Written: {out_file}'
            except Exception as exc:
                self.msg = f'Error writing testsuite output: {exc}'

        threading.Thread(target=_write, daemon=True).start()
        self.msg = f'Writing {out_file.name} …'

    def view_output(self, stdscr):
        """Open the last raw output for the selected thorn in vi -R."""
        thorn = self.thorns[self.selected]
        out_path = self._out_paths.get(thorn.name)
        if not out_path or not out_path.exists():
            self.msg = f"No output captured for {thorn.name} yet — run it first (r)."
            return
        curses.endwin()
        subprocess.run(['vi', '-R', str(out_path)])
        stdscr.refresh()
        curses.doupdate()

    def _refresh_cactus_pids(self):
        """Kick off a background /proc scan (never blocks the draw loop).

        Interval starts at 2 s.  After 3 consecutive all-empty results (the
        common SLURM case where cactus runs on a remote compute node) the
        interval backs off to 10 s to avoid constant futile scanning.  A
        busy-flag prevents a new scan from starting before the previous one
        has finished, eliminating overlapping threads."""
        if self._pid_scan_busy:
            return
        now = time.monotonic()
        interval = 10.0 if self._empty_pid_count >= 3 else 2.0
        if now - self._last_pid_check < interval:
            return
        self._last_pid_check = now
        # Snapshot the runners we care about so the thread doesn't race on self.runners.
        targets = [(name, r._proc.pid)
                   for name, r in list(self.runners.items())
                   if not r.done and r._proc is not None]
        if not targets:
            return
        self._pid_scan_busy = True

        def _scan():
            try:
                results = {name: _descendants_named(pid, EXE.name)
                           for name, pid in targets}
                # Under SLURM, srun hands off to slurmstepd so the cactus
                # processes are not /proc descendants of perl.  Fall back to a
                # system-wide pgrep when the walk comes up empty.
                any_found = any(pids for pids in results.values())
                if not any_found:
                    try:
                        pr = subprocess.run(
                            ['pgrep', '-x', EXE.name],
                            stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                            timeout=2,
                        )
                        fallback = ([p.strip() for p in
                                     pr.stdout.decode().splitlines() if p.strip()]
                                    if pr.returncode == 0 else [])
                    except Exception:
                        fallback = []
                    for name in results:
                        if not results[name]:
                            results[name] = fallback
                    any_found = any(pids for pids in results.values())
                if any_found:
                    self._empty_pid_count = 0
                else:
                    self._empty_pid_count += 1
                for name, pids in results.items():
                    self._cactus_pids[name] = pids
            finally:
                self._pid_scan_busy = False

        threading.Thread(target=_scan, daemon=True).start()

    def poll_runner(self):
        any_active = False
        for r in list(self.runners.values()):
            if not r.done:
                any_active = True
            elif not r._finalized:
                self._finish_runner(r)
        if any_active:
            self._refresh_cactus_pids()

    # ------------------------------------------------------------------
    # Quit prompt overlay
    # ------------------------------------------------------------------

    def _draw_quit_prompt(self, stdscr) -> str:
        """Draw a modal quit-confirmation box over the current screen.

        Blocks until the user presses a valid key.
        Returns 'kill', 'wait', 'complete', or 'cancel'.
        'complete' is only offered when the A queue has pending items.
        """
        n_active = sum(1 for r in self.runners.values() if not r.done)
        n_queued = len(self.run_queue)
        has_queue = n_queued > 0

        body = [
            f"  {n_active} test(s) running, {n_queued} queued  ",
            "",
            "  [1]  Kill all jobs and exit now",
            "  [2]  Wait for running tests to finish, then exit",
        ]
        if has_queue:
            body.append("  [3]  Complete all queued (A) tests, then exit")
        body.append("  [Esc / q]  Cancel — stay in TUI")

        title = " Quit? "
        inner_w = max(len(l) for l in body + [title]) + 2
        box_h = len(body) + 4   # top border + title row + blank + body + bottom border
        box_w = inner_w + 2     # left + right border

        h, w = stdscr.getmaxyx()
        r0 = max(0, (h - box_h) // 2)
        c0 = max(0, (w - box_w) // 2)

        def _box_str(row_content: str) -> str:
            return ("│" + row_content.ljust(inner_w) + "│")[:w - c0 - 1]

        try:
            top = ("┌" + title.center(inner_w, "─") + "┐")[:w - c0 - 1]
            stdscr.attron(curses.color_pair(8) | curses.A_BOLD)
            stdscr.addstr(r0, c0, top)
            stdscr.attroff(curses.color_pair(8) | curses.A_BOLD)

            for i, line in enumerate(body):
                row = r0 + 1 + i
                if row >= h - 1:
                    break
                if line.startswith("  ["):
                    stdscr.attron(curses.color_pair(7))
                    stdscr.addstr(row, c0, _box_str(line))
                    stdscr.attroff(curses.color_pair(7))
                else:
                    stdscr.attron(curses.color_pair(8))
                    stdscr.addstr(row, c0, _box_str(line))
                    stdscr.attroff(curses.color_pair(8))

            bot_row = r0 + 1 + len(body)
            if bot_row < h - 1:
                bot = ("└" + "─" * inner_w + "┘")[:w - c0 - 1]
                stdscr.attron(curses.color_pair(8) | curses.A_BOLD)
                stdscr.addstr(bot_row, c0, bot)
                stdscr.attroff(curses.color_pair(8) | curses.A_BOLD)
        except curses.error:
            pass

        stdscr.refresh()

        while True:
            ch = stdscr.getch()
            if ch == ord('1'):
                return 'kill'
            elif ch == ord('2'):
                return 'wait'
            elif ch == ord('3') and has_queue:
                return 'complete'
            elif ch in (27, ord('q'), ord('Q')):  # 27 = Esc
                return 'cancel'

    # ------------------------------------------------------------------
    # Main loop
    # ------------------------------------------------------------------

    def main(self, stdscr):
        self._init_colors()
        curses.curs_set(0)
        stdscr.nodelay(True)
        stdscr.timeout(100)

        self.msg = "Loading thorns …"
        self.draw(stdscr)
        self.thorns = build_thorns(self.state, self.times)
        self.msg = f"Loaded {len(self.thorns)} thorns with tests.  r:Run  A:Run-all  n:Next?/✗  f:Refresh  q:Quit"

        while True:
            h, w = stdscr.getmaxyx()
            list_h = self._list_height(h)
            self._scr_h = h

            self.poll_runner()
            self.draw(stdscr)
            ch = stdscr.getch()

            if ch == -1:
                # On idle ticks, check whether a pending quit is now satisfied.
                if self._waiting_to_quit:
                    no_runners = not any(not r.done for r in self.runners.values())
                    if no_runners and not self.run_queue:
                        break
                continue

            if ch in (ord('q'), ord('Q')):
                active = any(not r.done for r in self.runners.values())
                if self._waiting_to_quit:
                    # Second q while waiting → kill immediately.
                    for r in list(self.runners.values()):
                        if not r.done:
                            r.kill()
                    break
                elif active or self.run_queue:
                    choice = self._draw_quit_prompt(stdscr)
                    if choice == 'kill':
                        for r in list(self.runners.values()):
                            if not r.done:
                                r.kill()
                        self.run_queue.clear()
                        self._queue_runners.clear()
                        break
                    elif choice == 'wait':
                        self.run_queue.clear()   # no new tests start
                        self._queue_runners.clear()
                        self._waiting_to_quit = True
                        self.msg = "Waiting for running tests to finish … (q again to kill)"
                    elif choice == 'complete':
                        # Queue keeps draining; exit when everything is done.
                        self._waiting_to_quit = True
                        n = len(self.run_queue) + sum(1 for r in self.runners.values() if not r.done)
                        self.msg = f"Completing all {n} remaining test(s), then exiting … (q again to kill)"
                    # 'cancel' → fall through, stay in TUI
                else:
                    break

            elif ch == ord('k'):
                sel_r = self.runners.get(self.thorns[self.selected].name)
                if sel_r and not sel_r.done:
                    self.kill_running()
                else:
                    self.selected = max(0, self.selected - 1)
                    self._clamp_scroll(h)

            elif ch == curses.KEY_UP:
                self.selected = max(0, self.selected - 1)
                self._clamp_scroll(h)

            elif ch in (curses.KEY_DOWN, ord('j')):
                self.selected = min(len(self.thorns) - 1, self.selected + 1)
                self._clamp_scroll(h)

            elif ch == curses.KEY_PPAGE:
                self.selected = max(0, self.selected - list_h)
                self.scroll   = max(0, self.scroll - list_h)
                self._clamp_scroll(h)

            elif ch == curses.KEY_NPAGE:
                self.selected = min(len(self.thorns) - 1, self.selected + list_h)
                self.scroll   = min(max(0, len(self.thorns) - list_h),
                                    self.scroll + list_h)
                self._clamp_scroll(h)

            elif ch == curses.KEY_HOME:
                self.selected = 0
                self._clamp_scroll(h)

            elif ch == curses.KEY_END:
                self.selected = len(self.thorns) - 1
                self._clamp_scroll(h)

            elif ch in (ord('r'), ord('R'), ord('\n'), ord('\r'), curses.KEY_ENTER):
                self.run_selected()

            elif ch == ord('A'):
                self.run_all()

            elif ch in (ord('n'), ord('N')):
                self.next_untested(h)

            elif ch in (ord('s'), ord('S')):
                self.show_status()

            elif ch in (ord('t'), ord('T')):
                self.retry_failed()

            elif ch in (ord('v'), ord('V')):
                self.view_output(stdscr)

            elif ch in (ord('w'), ord('W')):
                self.write_testsuite_output()

            elif ch == ord('c'):
                self.clear_failed()

            elif ch == ord('C'):
                self.clear_all()

            elif ord('1') <= ch <= ord('9'):
                self._queue_parallelism = ch - ord('0')
                self.msg = (f"Parallelism set to {self._queue_parallelism} "
                            f"— next A/t will run {self._queue_parallelism} tests at a time.")
            elif ch == ord('0'):
                self._queue_parallelism = 1
                self.msg = "Parallelism reset to 1 (sequential)."

            elif ch in (ord('f'), ord('F')):
                active = [r for r in self.runners.values() if not r.done]
                if active:
                    names = ', '.join(r.thorn.name for r in active)
                    self.msg = f"Cannot refresh while tests are running ({names})."
                else:
                    self.run_queue.clear()
                    self._queue_runners.clear()
                    self.state  = load_state()
                    self.times  = load_times()
                    self.thorns = build_thorns(self.state, self.times)
                    self.selected = min(self.selected, max(0, len(self.thorns) - 1))
                    self._clamp_scroll(h)
                    self.msg = f"Refreshed — {len(self.thorns)} thorns."

            # Redraw immediately so key-handler state changes appear without
            # waiting for the next poll tick.
            h, w = stdscr.getmaxyx()
            self._scr_h = h
            self.draw(stdscr)


def _print_debug():
    """Print diagnostic information about test detection and exit."""
    def yn(p: Path) -> str:
        return "exists" if p.exists() else "NOT FOUND"

    print(f"CACTUS_HOME : {CACTUS_HOME}")
    print(f"CONFIG      : {CONFIG}")
    print(f"EXE         : {EXE}  [{yn(EXE)}]")
    print(f"THORNLIST   : {THORNLIST}  [{yn(THORNLIST)}]")
    print(f"TESTS_DIR   : {TESTS_DIR}  [{yn(TESTS_DIR)}]")
    print(f"STATE_FILE  : {STATE_FILE}  [{yn(STATE_FILE)}]")
    print()

    pairs = load_thornlist()
    print(f"ThornList: {len(pairs)} thorns listed")
    if not pairs:
        print("  (ThornList empty or not found — nothing to display)")
        return
    print()

    with_tests, without_tests = [], []
    for arr, thorn in pairs:
        tests = find_par_tests(arr, thorn)
        if tests:
            with_tests.append((arr, thorn, tests))
        else:
            without_tests.append((arr, thorn))

    print(f"Thorns with detected tests: {len(with_tests)}")
    for arr, thorn, tests in with_tests[:20]:
        print(f"  {arr}/{thorn}: {', '.join(tests)}")
    if len(with_tests) > 20:
        print(f"  ... and {len(with_tests) - 20} more")
    print()

    print(f"Thorns with NO detected tests: {len(without_tests)}")
    for arr, thorn in without_tests[:10]:
        test_dir = ARRANGEMENTS / arr / thorn / "test"
        if not test_dir.is_dir():
            reason = f"no test/ dir at {test_dir}"
        else:
            pars = list(test_dir.glob("*.par"))
            if not pars:
                reason = f"test/ exists but no .par files"
            else:
                reason = f"{len(pars)} .par file(s) but no matching reference data"
        print(f"  {arr}/{thorn}: {reason}")
    if len(without_tests) > 10:
        print(f"  ... and {len(without_tests) - 10} more")
    print()

    # Summary log status
    candidates = [
        TESTS_DIR / "summary.log",
        *sorted(CACTUS_HOME.glob("run*.out"), key=lambda p: p.stat().st_mtime, reverse=True),
    ]
    print("Log files checked for initial state:")
    for p in candidates:
        print(f"  {p}  [{yn(p)}]")


def main():
    if _DEBUG:
        _print_debug()
        return
    curses.wrapper(TUI().main)


if __name__ == "__main__":
    main()
