#!/usr/bin/python3 -O
#
# Copyright 2025 Daniel Balparda (balparda@gmail.com)
# GNU General Public License v3 (http://www.gnu.org/licenses/gpl-3.0.txt)
#
"""Pawnalyzer statistical analysis.

pawnalyzer.py
"""

import argparse
import logging
# import pdb
from typing import Optional

from baselib import base
from pawnalyze import pawnlib
from pawnalyze import pawnzobrist

__author__ = 'balparda@gmail.com (Daniel Balparda)'
__version__ = (1, 0)


def Main() -> None:
  """Main Pawnalyzer."""
  # parse the input arguments, do some basic checks
  parser: argparse.ArgumentParser = argparse.ArgumentParser()
  parser.add_argument(
      '-z', '--zobrist', type=str, default='',
      help='If given expects a zobrist hash in the DB for a starting position (32 char hex string, 16 bytes)')
  parser.add_argument(
      '-r', '--readonly', type=bool, default=False,
      help='If "True" will not save database (default: False)')
  args: argparse.Namespace = parser.parse_args()
  db_readonly = bool(args.readonly)
  # start
  print(f'{base.TERM_BLUE}{base.TERM_BOLD}***********************************************')
  print(f'**                {base.TERM_LIGHT_RED}Pawnalyzer{base.TERM_BLUE}                 **')
  print('**   balparda@gmail.com (Daniel Balparda)    **')
  print(f'***********************************************{base.TERM_END}')
  success_message: str = f'{base.TERM_WARNING}premature end? user paused?'
  try:
    # creates objects
    database: pawnlib.PGNData = pawnlib.PGNData(readonly=db_readonly)
    try:
      # execute the evaluations
      print()
      with base.Timer() as op_timer:
        start_position: Optional[pawnzobrist.Zobrist] = (
            pawnzobrist.ZobristFromHash(args.zobrist.strip()) if args.zobrist.strip() else None)
        print('Collecting stats for DB')
        for stat in database.CollectGameStats(start_position=start_position):
          line_position: str = pawnlib.PrettyPositionLine(
              stat['pos'], stat['plys'], stat['eco'], stat['board'], stat['moves'],
              stat['flags'], stat['extras'], stat['engine'])
          print(f'{line_position}: {stat["n_games"]} games')
        print()
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
