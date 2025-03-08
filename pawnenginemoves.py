#!/usr/bin/python3 -O
#
# Copyright 2025 Daniel Balparda (balparda@gmail.com)
# GNU General Public License v3 (http://www.gnu.org/licenses/gpl-3.0.txt)
#
"""Pawnalyze add Engine Moves to PGNs.

Typical examples:

./pawnenginemoves.py
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


def AddEvaluationsOfRepeatPositionsToDB(database: pawnlib.PGNData, num_threads: int) -> None:
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
  pawnlib.RunEvalWorkers(num_threads, all_jobs, _WORKER_TIMEOUT_SECONDS)


def Main() -> None:
  """Main PawnEngineMoves."""
  # parse the input arguments, do some basic checks
  parser: argparse.ArgumentParser = argparse.ArgumentParser()
  parser.add_argument(
      '-n', '--numthreads', type=int, default=_WORKER_THREADS_DEFAULT,
      help=f'Number of worker threads to spawn (default: {_WORKER_THREADS_DEFAULT})')
  parser.add_argument(
      '-r', '--readonly', type=bool, default=False,
      help='If "True" will not save database, will only print (default: False)')
  args: argparse.Namespace = parser.parse_args()
  db_readonly = bool(args.readonly)
  num_threads: int = args.numthreads
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
        logging.info('Starting game DEDUPLICATION')
        AddEvaluationsOfRepeatPositionsToDB(database, num_threads)
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
