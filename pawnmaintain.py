#!/usr/bin/python3 -O
#
# Copyright 2025 Daniel Balparda (balparda@gmail.com)
# GNU General Public License v3 (http://www.gnu.org/licenses/gpl-3.0.txt)
#
"""Pawnalyze maintain PGNs Database.

pawnmaintain.py

This module performs various maintenance tasks on the Pawnalyze SQLite database of PGN
games via subcommands:

Subcommands:
  1) "print"
     Prints database moves/positions (and optionally games).
     -p/--positions <N>  : how many positions to print (default 1000; 0 => no limit)
     -z/--zobrist <hash> : start from this 32-char hex position hash if given
     -g/--games [bool]   : if True, also print associated games from those positions

  2) "dedup"
     Deduplicates games in the Pawnalyze DB using specified soft/hard ply thresholds.
     -s/--softlimit N    : games with ply depth >= N are more likely duplicates (default 40)
     -l/--hardlimit M    : games with ply depth >= M are always duplicates (default 60)

  3) "check"
     Runs a database consistency check (e.g. verifying unreachable positions, duplicates, etc.)

You can run:
  ./pawnmaintain.py print -p 20
  ./pawnmaintain.py dedup -s 30 -l 55
  ./pawnmaintain.py check

In all commands, you can pass:
  -r/--readonly bool  : If True, do not commit changes to the database.

Examples:
  # Print the first 10 positions in the database
  ./pawnmaintain.py print -p 10

  # Deduplicate games with a soft limit of 50 and hard limit of 70
  ./pawnmaintain.py dedup -s 50 -l 70

  # Run a DB check in readonly mode
  ./pawnmaintain.py check -r True
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


_DEFAULT_LINES_PRINTED: int = 1000

_SOFT_PLY_LIMIT: int = 40  # games with >= ply depth than this are easier to declare duplicates
_HARD_PLY_LIMIT: int = 60  # games with >= ply depth than this are always considered duplicates


def Main() -> None:
  """Main PawnMaintain."""
  # parse the input arguments, add subparser for `command`
  parser: argparse.ArgumentParser = argparse.ArgumentParser()
  command_arg_subparsers = parser.add_subparsers(dest='command')
  # "print" command
  print_parser: argparse.ArgumentParser = command_arg_subparsers.add_parser(
      'print', help='Print database moves')
  print_parser.add_argument(
      '-p', '--positions', type=int, default=_DEFAULT_LINES_PRINTED,
      help='Maximum number of database positions to print; 0 == infinite '
           f'(default: {_DEFAULT_LINES_PRINTED})')
  print_parser.add_argument(
      '-z', '--zobrist', type=str, default='',
      help='If given expects a zobrist hash in the DB for a starting position (32 char hex string, 16 bytes)')
  print_parser.add_argument(
      '-g', '--games', type=bool, default=False,
      help='If "True" will show games too (default: False)')
  # "dedup" command
  dedup_parser: argparse.ArgumentParser = command_arg_subparsers.add_parser(
      'dedup', help='Run DB deduplication')
  dedup_parser.add_argument(
      '-s', '--softlimit', type=int, default=_SOFT_PLY_LIMIT,
      help='Games with ply depth >= than this are easier to declare duplicates '
           f'(min/default: {_SOFT_PLY_LIMIT})')
  dedup_parser.add_argument(
      '-l', '--hardlimit', type=int, default=_HARD_PLY_LIMIT,
      help='Games with ply depth >= than this are always considered duplicates '
           f'(min/default: {_HARD_PLY_LIMIT})')
  # "check" command
  command_arg_subparsers.add_parser('check', help='Run DB check')
  # ALL commands
  parser.add_argument(
      '-r', '--readonly', type=bool, default=False,
      help='If "True" will not save database (default: False)')
  args: argparse.Namespace = parser.parse_args()
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
        # "print" command
        if args.command == 'print':
          zob: Optional[pawnzobrist.Zobrist] = (
              pawnzobrist.ZobristFromHash(args.zobrist) if args.zobrist.strip() else None)
          print(f'Printing database moves, starting at {"ROOT" if zob is None else str(zob)}')
          print()
          for i, line in database.PrintMovesDB(start_position=zob, expand_games=args.games):
            if args.positions and i >= args.positions:
              print()
              print(f'Reached positions limit: {i}')
              break
            print(line)
        # "dedup" command
        elif args.command == 'dedup':
          if (args.softlimit < _SOFT_PLY_LIMIT or args.hardlimit < _HARD_PLY_LIMIT or
              args.softlimit >= args.hardlimit):
            raise ValueError(
                f'Minimum soft limit is {_SOFT_PLY_LIMIT} and minimum hard limit is {_HARD_PLY_LIMIT}')
          print(f'Starting game DEDUPLICATION {args.softlimit=} / {args.hardlimit=}...')
          changed_data: int = len(database.DeduplicateGames(args.softlimit, args.hardlimit))
          print(f'{changed_data} games deduplicated')
        # "check" command
        elif args.command == 'check':
          print('Starting DB check')
          for line in database.PrintDatabaseCheck():
            print(line)
          print('DB check ended')
        # no valid command
        else:
          parser.print_help()
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
