"""
Provides a CLI for QCEngine
"""

import argparse
import json
import os.path
import sys
from typing import Any, Dict

from . import get_program  # run and run-procedure; info
from . import (
    __version__,
    compute,
    compute_procedure,
    get_procedure,
    list_all_procedures,
    list_all_programs,
    list_available_procedures,
    list_available_programs,
)
from .config import global_repr  # info

__all__ = ["main"]

info_choices = frozenset(["version", "programs", "procedures", "config", "bulletin", "all"])


def parse_args():
    parser = argparse.ArgumentParser(description="A CLI for the QCEngine.")
    parser.add_argument("--version", action="version", version=f"{__version__}")

    parent_parser = argparse.ArgumentParser(add_help=False)
    task_group = parent_parser.add_argument_group(
        "Task Configuration", "Extra configuration related to running the computation"
    )
    task_group.add_argument("--ncores", type=int, help="The number of cores to use for the task")
    task_group.add_argument("--nnodes", type=int, help="The number of nodes to use")
    task_group.add_argument("--memory", type=float, help="The amount of memory (in GiB) to use")
    task_group.add_argument("--scratch-directory", type=str, help="Where to store temporary files")
    task_group.add_argument("--retries", type=int, help="Number of retries for random failures")
    task_group.add_argument("--mpiexec-command", type=str, help="Command used to launch MPI tasks")
    task_group.add_argument(
        "--use-mpiexec",
        action="store_true",
        default=None,
        help="Whether it is necessary to use MPI to run an executable",
    )
    task_group.add_argument("--cores-per-rank", type=int, help="Number of cores per MPI rank")
    task_group.add_argument(
        "--scratch-messy",
        action="store_true",
        default=None,
        help="Leave the scratch directory and contents on disk after completion",
    )

    subparsers = parser.add_subparsers(dest="command")

    info = subparsers.add_parser("info", help="Print information about QCEngine setup, version, and environment.")
    info.add_argument(
        "category", nargs="*", default="all", choices=info_choices, help="The information categories to show."
    )

    run = subparsers.add_parser(
        "run", parents=[parent_parser], help="Run a program on a given task. Output is printed as a JSON blob."
    )
    run.add_argument("program", type=str, help="The program to run.")
    run.add_argument(
        "data",
        type=str,
        help="Data describing the task to run. "
        "One of: (i) A JSON blob, "
        "(ii) A file name, "
        "(iii) '-', indicating data will be read from STDIN.",
    )

    run_procedure = subparsers.add_parser(
        "run-procedure",
        parents=[parent_parser],
        help="Run a procedure on a given task. Output is printed as a JSON blob.",
    )
    run_procedure.add_argument("procedure", type=str, help="The procedure to run.")
    run_procedure.add_argument(
        "data",
        type=str,
        help="Data describing the task to run. "
        "One of: (i) A JSON blob, "
        "(ii) A file name, "
        "(iii) '-', indicating data will be read from STDIN.",
    )

    args = vars(parser.parse_args())
    if args["command"] is None:
        parser.print_help(sys.stderr)
        exit(1)

    return args


def info_cli(args):
    def info_version():
        import qcelemental

        print(">>> Version information")
        print(f"QCEngine:    {__version__}")
        print(f"QCElemental: {qcelemental.__version__}")
        print()

    def info_programs():  # lgtm: [py/similar-function]
        print(">>> Program information")
        all_progs = list_all_programs()
        avail_progs = list_available_programs()
        print("Available programs:")
        for prog_name in sorted(avail_progs):
            program = get_program(prog_name)
            version = program.get_version()
            for loc, ver in program.version_cache.items():
                if ver == version:
                    which = loc
                    break
            else:
                which = "???"
            if version is None:
                version = "???"
            print(f"{prog_name + ':':12} v{version:20} {which}")

        print()
        print("Other supported programs:")
        print(" ".join(sorted(all_progs - avail_progs)))
        print()
        print(
            """If you think available programs are missing, query for details: `python -c "import qcengine as qcng; qcng.get_program('<program>')"`"""
        )
        print()

    def info_procedures():  # lgtm: [py/similar-function]
        print(">>> Procedure information")
        all_procs = list_all_procedures()
        avail_procs = list_available_procedures()
        print("Available procedures:")
        for proc_name in sorted(avail_procs):
            version = get_procedure(proc_name).get_version()
            if version is None:
                version = "???"
            print(f"{proc_name} v{version}")

        print()
        print("Other supported procedures:")
        print(" ".join(sorted(all_procs - avail_procs)))
        print()

    def info_bulletin():
        print(">>> Bulletin")
        bull_items = []
        bull_items.append(
            """  * [Apr 2025; v0.32.0] Program Harness 'qcore'/'entos' is deprecated with Prof. Manby's approval.
     It will cease to be tested as soon as Python minimum bumps >3.7. It may be removed as soon as 2026."""
        )
        bull_items.append(
            """  * [Apr 2025; v0.32.0] Program Harness 'dftd3' is deprecated in favor of the maintained 's-dftd3'.
     Its testing will become narrower (w/o Psi4). It may be removed as soon as 2026."""
        )
        bull_items.append(
            """  * [Apr 2025; v0.32.0] Program Harness 'gcp' is deprecated in favor of the maintained 'mctc-gcp'.
     Its testing will become narrower (w/o Psi4). It may be removed as soon as 2026."""
        )
        print("\n".join(bull_items))
        print()

    # default=["all"] does is not allowed by argparse
    if not isinstance(args["category"], list):
        args["category"] = [args["category"]]
    cat = set(args["category"])

    if "version" in cat or "all" in cat:
        info_version()
    if "programs" in cat or "all" in cat:
        info_programs()
    if "procedures" in cat or "all" in cat:
        info_procedures()
    if "bulletin" in cat or "all" in cat:
        info_bulletin()
    if "config" in cat or "all" in cat:
        print(">>> Configuration information")
        print()
        print(global_repr())


def data_arg_helper(data_arg: str) -> Dict[str, Any]:
    """
    Converts the data argument of run and run-procedure commands to a dict for compute or compute_procedure

    Parameters
    ----------
    data_arg: str
        Either a data blob or file name or '-' for STDIN

    Returns
    -------
    Dict[str, Any]
        An input for compute or compute_procedure.
    """
    if data_arg == "-":
        return json.load(sys.stdin)
    elif os.path.isfile(data_arg):
        return json.load(open(data_arg))
    else:
        return json.loads(data_arg)


def main(args=None):
    # Grab CLI args if not present
    if args is None:
        args = parse_args()

    # Break out a task config
    task_config = {
        "ncores": args.pop("ncores", None),
        "memory": args.pop("memory", None),
        "nnodes": args.pop("nnodes", None),
        "scratch_directory": args.pop("scratch_directory", None),
        "retries": args.pop("retries", None),
        "mpiexec_command": args.pop("mpiexec_command", None),
        "use_mpiexec": args.pop("use_mpiexec", None),
        "cores_per_rank": args.pop("cores_per_rank", None),
        "scratch_messy": args.pop("scratch_messy", None),
    }

    # Prune None values and let other config functions handle defaults
    task_config = {k: v for k, v in task_config.items() if v is not None}

    command = args.pop("command")
    if command == "info":
        info_cli(args)
    elif command == "run":
        ret = compute(data_arg_helper(args["data"]), args["program"], task_config=task_config)
        print(ret.json())
    elif command == "run-procedure":
        ret = compute_procedure(data_arg_helper(args["data"]), args["procedure"], task_config=task_config)
        print(ret.json())
