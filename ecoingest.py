#!/usr/bin/python3 -O
#
# Copyright 2025 Daniel Balparda (balparda@gmail.com)
# GNU General Public License v3 (http://www.gnu.org/licenses/gpl-3.0.txt)
#
"""Pawnalyze Encyclopedia of Chess Openings (ECO) ingestion.

Will create the file ECO.json in the project. See:

https://en.wikipedia.org/wiki/Encyclopaedia_of_Chess_Openings

https://github.com/lichess-org/chess-openings

Specifically data is loaded from 5 URLs:

https://raw.githubusercontent.com/lichess-org/chess-openings/refs/heads/master/a.tsv
...
https://raw.githubusercontent.com/lichess-org/chess-openings/refs/heads/master/e.tsv

ecoingest.py

This module loads ECO data from GitHub and creates ECO.json file in Pawnalyze project.

Typical usage:
  ./ecoingest.py
"""

import csv
import io
import logging
# import pdb
from typing import Callable, Generator
import urllib.request

import chess
import chess.pgn

from baselib import base
from pawnalyze import pawnzobrist
from pawnalyze import pawnlib

__author__ = 'balparda@gmail.com (Daniel Balparda)'
__version__ = (1, 0)


_ECO_TEMPLATE: Callable[[str], str] = (
    lambda n: f'http://raw.githubusercontent.com/lichess-org/chess-openings/refs/heads/master/{n}.tsv')

_ECO_URLS: list[str] = [_ECO_TEMPLATE(n) for n in ('a', 'b', 'c', 'd', 'e')]


def _IngestTSV(url: str, eco_dict: dict[str, tuple[str, str]]) -> None:
  """Ingest one TSV `url`, adding to `eco_dict` (like {pgn: (eco, name)})."""
  # download
  with urllib.request.urlopen(url) as response:
    tsv_raw: bytes = response.read()
  # parse
  pgn: str
  for eco, name, pgn in csv.reader(io.StringIO(tsv_raw.decode('utf-8')), delimiter='\t'):
    pgn = pgn.strip()
    row: tuple[str, str] = (eco.strip(), name.strip())
    if row == ('eco', 'name'):
      continue  # skip first line
    if pgn in eco_dict:
      raise RuntimeError(f'Found duplicate row name: {pgn!r}: new {row!r} ; old {eco_dict[pgn]!r}')
    eco_dict[pgn] = row


def _ConvertData(eco_dict: dict[str, tuple[str, str]]) -> list[
    tuple[str, str, str, str, list[tuple[str, int, str, int]]]]:
  """Convert what was loaded to a more useful format.

  Returns:
    [(position, eco, name, pgn, [(san, encoded_ply, position, flags), (), ...]), ...]
    where position hashes are guaranteed to be unique
  """
  eco_position: list[tuple[str, str, str, str, list[tuple[str, int, str, int]]]] = []
  known_positions: set[str] = set()
  for pgn, (eco, name) in eco_dict.items():
    game: chess.pgn.Game = chess.pgn.read_game(io.StringIO(pgn))  # type:ignore
    if not game:
      raise RuntimeError(f'No game found in game lines: {pgn!r}')
    plys: list[tuple[str, int, str, int]] = []
    z_current: pawnzobrist.Zobrist = pawnzobrist.STARTING_POSITION_HASH
    for _, san, encoded_ply, (_, z_current), _, flags, _ in pawnlib.IterateGame(game):
      plys.append((san, encoded_ply, str(z_current), flags.value))
    position = str(z_current)
    if position in known_positions:
      raise RuntimeError(f'Repeat position: {position!r} / {(name, eco, pgn)!r}')
    known_positions.add(position)
    eco_position.append((position, eco, name, pgn, plys))
  print('sorting...')
  eco_position.sort(key=lambda x: (x[1], x[2]))
  return eco_position


def _JsonOverride(
    eco_data: list[tuple[str, str, str, str, list[tuple[str, int, str, int]]]]) -> Generator[
        str, None, None]:
  """Save data structure in JSON-readable format, which is easy in this case."""
  yield '[\n'
  last_idx: int = len(eco_data) - 1
  for i, (position, eco, name, pgn, plys) in enumerate(eco_data):
    ply_str: list[str] = []
    for san, encoded_ply, ply_hash, flags in plys:
      ply_str.append(f'["{san}",{encoded_ply},"{ply_hash}",{flags}]')
    yield f'["{position}", "{eco}", "{name}", "{pgn}", [{", ".join(ply_str)}]]{"" if i == last_idx else ","}\n'
  yield ']\n'


def Main() -> None:
  """Main ECOIngest."""
  # start
  print(f'{base.TERM_BLUE}{base.TERM_BOLD}***********************************************')
  print(f'**        {base.TERM_LIGHT_RED}Pawnalyze ECO Ingestion{base.TERM_BLUE}            **')
  print('**   balparda@gmail.com (Daniel Balparda)    **')
  print(f'***********************************************{base.TERM_END}')
  success_message: str = f'{base.TERM_WARNING}premature end? user paused?'
  try:
    # execute ECO ingestion
    print()
    basic_eco: dict[str, tuple[str, str]] = {}  # {pgn: (eco, name)}
    with base.Timer() as op_timer:
      print('Starting ECO ingestion...')
      for url in _ECO_URLS:
        print()
        print(f'Ingest: {url}')
        _IngestTSV(url, basic_eco)
        print()
      print(f'ECO ingestion ended, {len(basic_eco)} records loaded; convert and save...')
      eco_data: list[
          tuple[str, str, str, str, list[tuple[str, int, str, int]]]] = _ConvertData(basic_eco)
      with open(pawnlib.ECO_JSON_PATH, 'wt', encoding='utf-8') as json_obj:
        json_obj.writelines(_JsonOverride(eco_data))
      print(f'Saved to {pawnlib.ECO_JSON_PATH}')
    print()
    print(f'Executed in {base.TERM_GREEN}{op_timer.readable}{base.TERM_END}')
    print()
    success_message = f'{base.TERM_GREEN}success'
  except Exception as err:
    success_message = f'{base.TERM_FAIL}error: {err}'
    raise
  finally:
    print(f'{base.TERM_BLUE}{base.TERM_BOLD}THE END: {success_message}{base.TERM_END}')


if __name__ == '__main__':
  logging.basicConfig(level=logging.INFO, format=base.LOG_FORMAT)  # set this as default
  Main()
