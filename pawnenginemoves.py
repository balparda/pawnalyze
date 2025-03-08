#!/usr/bin/python3 -O
#
# Copyright 2025 Daniel Balparda (balparda@gmail.com)
# GNU General Public License v3 (http://www.gnu.org/licenses/gpl-3.0.txt)
#
"""Pawnalyze add Engine Moves to PGNs.

pawnenginemoves.py

This module spawns threads or processes to evaluate repeat positions in the Pawnalyze
database using a chess engine. Positions that have multiple branches (i.e., more
than one move from a single position) and no existing engine evaluation are
discovered, then fed to worker threads.

Typical usage:
  ./pawnenginemoves.py

Optional Arguments:
  -n/--numthreads int : Number of worker threads/processes to launch (default=8)
  -d/--depth int : Depth, in plies, to evaluate (default=20)
  -e/--engine str : Engine command to use (default='stockfish')
  -t/--tasks int: Max number of tasks/positions to evaluate (default: 1000000)
  -r/--readonly bool  : If True, do not commit changes to the DB
"""

import argparse
import logging
# import pdb

from baselib import base
from pawnalyze import pawnlib

__author__ = 'balparda@gmail.com (Daniel Balparda)'
__version__ = (1, 0)


_WORKER_THREADS_DEFAULT: int = 8       # number of worker threads to spawn
_WORKER_TIMEOUT_SECONDS: float = 10.0  # seconds until a worker is considered timed-out
_MIN_DEPTH: int = 3
_DEFAULT_DEPTH: int = pawnlib.ELO_CATEGORY_TO_PLY['super']
_MAX_DEPTH: int = _DEFAULT_DEPTH + 4
_MAX_NUMBER_TASKS: int = 1000000


def AddEvaluationsOfRepeatPositionsToDB(
    database: pawnlib.PGNData, num_threads: int, depth: int, engine_command: str) -> None:
  """Adds engine evaluations of repeat positions to chess DB. Multithreaded and efficient."""
  # get and display the numbers we will be sending to the engine
  result: dict[int, dict[str, dict[int, str]]] = database.GetPositionsWithMultipleBranches(
      filter_engine_done=True)
  print()
  print('Found the following counts of repeated positions without engine evaluations:')
  print()
  all_jobs: list[str] = []
  for n in sorted(result.keys(), reverse=True):
    n_per_count: int = len(result[n])
    print(f'  Branching into {n} moves: {n_per_count} positions')
    all_jobs.extend(sorted(result[n].keys()))
  print()
  print(f'Total: {len(all_jobs)} positions; STARTING threads to evaluate them')
  print()
  pawnlib.RunEvalWorkers(
      num_threads, database.is_readonly, all_jobs, _WORKER_TIMEOUT_SECONDS, depth, engine_command)


def AddEvaluationsOfFinalPositionsToDB(
    database: pawnlib.PGNData, num_threads: int, depth: int,
    num_tasks: int, engine_command: str) -> None:
  """Adds engine evaluations of final positions to chess DB. Multithreaded and efficient."""
  all_jobs: list[str] = [str(r[0]) for r in database.GetPositions(
      has_eval=False, has_game=True, limit=num_tasks)]
  print(f'Total: {len(all_jobs)} positions; STARTING threads to evaluate them')
  pawnlib.RunEvalWorkers(
      num_threads, database.is_readonly, all_jobs, _WORKER_TIMEOUT_SECONDS, depth, engine_command)


def Main() -> None:
  """Main PawnEngineMoves."""
  # parse the input arguments, do some basic checks
  parser: argparse.ArgumentParser = argparse.ArgumentParser()
  parser.add_argument(
      '-n', '--numthreads', type=int, default=_WORKER_THREADS_DEFAULT,
      help=f'Number of worker threads to spawn (default: {_WORKER_THREADS_DEFAULT})')
  parser.add_argument(
      '-d', '--depth', type=int, default=_DEFAULT_DEPTH,
      help=f'Depth, in plies, to evaluate (default: {_DEFAULT_DEPTH})')
  parser.add_argument(
      '-e', '--engine', type=str, default=pawnlib.DEFAULT_ENGINE,
      help=f'Engine command to use (default: {pawnlib.DEFAULT_ENGINE!r})')
  parser.add_argument(
      '-t', '--tasks', type=int, default=_MAX_NUMBER_TASKS,
      help=f'Max number of tasks/positions to evaluate (default: {_MAX_NUMBER_TASKS})')
  parser.add_argument(
      '-r', '--readonly', type=bool, default=False,
      help='If "True" will not save database (default: False)')
  args: argparse.Namespace = parser.parse_args()
  db_readonly = bool(args.readonly)
  num_threads: int = args.numthreads
  if not 1 <= num_threads <= 32:
    raise ValueError('Keep number of threads (-n/--numthreads) between 1 and 32')
  ply_depth: int = args.depth
  if not _MIN_DEPTH <= ply_depth <= _MAX_DEPTH:
    raise ValueError(f'Keep ply depth (-d/--depth) between {_MIN_DEPTH} and {_MAX_DEPTH}')
  engine_command: str = args.engine.strip()
  if not engine_command:
    raise ValueError('You must provide an engine command (-e/--engine)')
  num_tasks: int = args.tasks
  if not 10 <= num_tasks <= 100000000:
    raise ValueError('Keep number of tasks (-t/--tasks) between 10 and 100 million')
  # start
  print(f'{base.TERM_BLUE}{base.TERM_BOLD}***********************************************')
  print(f'**       {base.TERM_LIGHT_RED}Pawnalyze Add Engine Moves{base.TERM_BLUE}          **')
  print('**   balparda@gmail.com (Daniel Balparda)    **')
  print(f'***********************************************{base.TERM_END}')
  success_message: str = f'{base.TERM_WARNING}premature end? user paused?'
  try:
    # creates objects
    database: pawnlib.PGNData = pawnlib.PGNData(readonly=db_readonly)
    try:
      # execute the source reads
      print()
      with base.Timer() as op_timer:
        logging.info('Starting evaluation engine')
        # AddEvaluationsOfRepeatPositionsToDB(database, num_threads, ply_depth, engine_command)
        AddEvaluationsOfFinalPositionsToDB(
            database, num_threads, ply_depth, num_tasks, engine_command)
      print()
      print(f'Executed in {base.TERM_GREEN}{op_timer.readable}{base.TERM_END}')
      print()
      success_message = f'{base.TERM_GREEN}success'
    finally:
      if database:
        database.Close()
  except Exception as err:
    success_message = f'{base.TERM_FAIL}error: {err}'
    raise
  finally:
    print(f'{base.TERM_BLUE}{base.TERM_BOLD}THE END: {success_message}{base.TERM_END}')


if __name__ == '__main__':
  logging.basicConfig(level=logging.INFO, format=base.LOG_FORMAT)  # set this as default
  Main()
