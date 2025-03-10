#!/usr/bin/python3 -O
#
# Copyright 2025 Daniel Balparda (balparda@gmail.com)
# GNU General Public License v3 (http://www.gnu.org/licenses/gpl-3.0.txt)
#
"""Pawnalyze maintain PGNs Database.

pawnmaintain.py

This module performs maintenance tasks on the Pawnalyze SQLite database of PGN
games. Currently, it focuses on deduplicating game records.

Typical usage:
  ./pawnmaintain.py
    - Deduplicates games in the Pawnalyze DB using the default soft/hard ply thresholds (40/60).

Optional arguments:
  -s/--softlimit N    : Games with ply depth >= N are more likely duplicates.
  -l/--hardlimit M    : Games with ply depth >= M are always marked duplicates.
  -r/--readonly bool  : If True, do not commit changes to the database.
"""

import argparse
import logging
# import pdb

from baselib import base
from pawnalyze import pawnlib

__author__ = 'balparda@gmail.com (Daniel Balparda)'
__version__ = (1, 0)


_SOFT_PLY_LIMIT: int = 40  # games with >= ply depth than this are easier to declare duplicates
_HARD_PLY_LIMIT: int = 60  # games with >= ply depth than this are always considered duplicates


def Main() -> None:
  """Main PawnMaintain."""
  # parse the input arguments, do some basic checks
  parser: argparse.ArgumentParser = argparse.ArgumentParser()
  parser.add_argument(
      '-s', '--softlimit', type=int, default=_SOFT_PLY_LIMIT,
      help=f'Games with ply depth >= than this are easier to declare duplicates (min/default: {_SOFT_PLY_LIMIT})')
  parser.add_argument(
      '-l', '--hardlimit', type=int, default=_HARD_PLY_LIMIT,
      help=f'Games with ply depth >= than this are always considered duplicates (min/default: {_HARD_PLY_LIMIT})')
  parser.add_argument(
      '-r', '--readonly', type=bool, default=False,
      help='If "True" will not save database (default: False)')
  args: argparse.Namespace = parser.parse_args()
  soft_limit: int = args.softlimit
  hard_limit: int = args.hardlimit
  if soft_limit < _SOFT_PLY_LIMIT or hard_limit < _HARD_PLY_LIMIT:
    raise ValueError(
        f'Minimum soft limit is {_SOFT_PLY_LIMIT} and minimum hard limit is {_HARD_PLY_LIMIT}')
  db_readonly = bool(args.readonly)
  # start
  print(f'{base.TERM_BLUE}{base.TERM_BOLD}***********************************************')
  print(f'**        {base.TERM_LIGHT_RED}Pawnalyze Maintain PGNs{base.TERM_BLUE}            **')
  print('**   balparda@gmail.com (Daniel Balparda)    **')
  print(f'***********************************************{base.TERM_END}')
  success_message: str = f'{base.TERM_WARNING}premature end? user paused?'
  try:
    # creates objects
    database: pawnlib.PGNData = pawnlib.PGNData(readonly=db_readonly)
    try:
      # execute the DB checks
      print()
      with base.Timer() as op_timer:
        print(f'Starting game DEDUPLICATION {soft_limit=} / {hard_limit=}...')
        changed_data: int = len(database.DeduplicateGames(soft_limit, hard_limit))
        print(f'{changed_data} games deduplicated')
        print()
        print('Starting DB check')
        database.PrintDatabaseCheck()
        print('DB check ended')
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
