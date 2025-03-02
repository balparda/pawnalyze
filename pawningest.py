#!/usr/bin/python3 -O
#
# Copyright 2025 Daniel Balparda (balparda@gmail.com)
# GNU General Public License v3 (http://www.gnu.org/licenses/gpl-3.0.txt)
#
"""Pawnalyze ingest PGNs.

Typical examples:

./pawningest.py -u "https://ndownloader.figstatic.com/files/6971717"
(read the URL and ingest these games --- expects a zipped file)

./pawningest.py -u "https://ndownloader.figstatic.com/files/6971717" -r 1
(print all the games in the URL but don't add them to the DB)
"""

import argparse
import io
import logging
# import pdb
import tempfile
import time
from typing import Generator, Optional
import urllib.request
import zipfile

import chess
import chess.pgn

from baselib import base
from pawnalyze import pawnlib

__author__ = 'balparda@gmail.com (Daniel Balparda)'
__version__ = (1, 0)


# sources we can handle should be "registered" here!
_SOURCES: dict[str, tuple[str, str, list[str]]] = {  # name: (domain, human_url, list[download_url])
    'lumbrasgigabase': (
        'lumbrasgigabase.com',
        'https://lumbrasgigabase.com/',
        [
            'https://lumbrasgigabase.com/download/lumbras-giga-base-pgn-2023-2/?wpdmdl=8752&amp;refresh=67bf14f94fce91740575993',
            'https://lumbrasgigabase.com/download/lumbras-giga-base-pgn-2023/?wpdmdl=8068&amp;refresh=67bf14f950eac1740575993',
            'https://lumbrasgigabase.com/download/lumbras-giga-base-pgn-2022/?wpdmdl=8069&amp;refresh=67bf14f951d761740575993',
            'https://lumbrasgigabase.com/download/lumbras-giga-base-pgn-2021/?wpdmdl=8070&amp;refresh=67bf14f9529681740575993',
            'https://lumbrasgigabase.com/download/lumbras-giga-base-pgn-2020/?wpdmdl=8071&amp;refresh=67bf14f95351b1740575993',
            'https://lumbrasgigabase.com/download/lumbras-giga-base-pgn-2015-to-2019/?wpdmdl=8072&amp;refresh=67bf14f9540b71740575993',
            'https://lumbrasgigabase.com/download/lumbras-giga-base-pgn-2005-to-2009/?wpdmdl=8074&amp;refresh=67bf14f954bf31740575993',
            'https://lumbrasgigabase.com/download/lumbras-giga-base-pgn-2000-to-2004/?wpdmdl=8075&amp;refresh=67bf14f9557e91740575993',
            'https://lumbrasgigabase.com/download/lumbras-giga-base-pgn-1990-to-1999/?wpdmdl=8076&amp;refresh=67bf14f9565111740575993',
            'https://lumbrasgigabase.com/download/lumbras-giga-base-pgn-2010-to-2014/?wpdmdl=8073&amp;refresh=67bf14f9570a41740575993',
            'https://lumbrasgigabase.com/download/lumbras-giga-base-pgn-1970-to-1989/?wpdmdl=8077&amp;refresh=67bf160c614521740576268',
            'https://lumbrasgigabase.com/download/lumbras-giga-base-pgn-1950-to-1969/?wpdmdl=8078&amp;refresh=67bf160c62c4e1740576268',
            'https://lumbrasgigabase.com/download/lumbras-giga-base-pgn-1900-to-1949/?wpdmdl=8081&amp;refresh=67bf160c63fe71740576268',
            'https://lumbrasgigabase.com/download/lumbras-giga-base-pgn-until-1899/?wpdmdl=8079&amp;refresh=67bf160c653251740576268',
            'https://lumbrasgigabase.com/download/lumbras-giga-base-pgn-with-no-date/?wpdmdl=8080&amp;refresh=67bf160c666221740576268',
        ]),
    'figshare': (
        'figshare.com',
        'https://figshare.com/articles/dataset/Chess_Database/4276523',
        [
            'https://ndownloader.figstatic.com/files/6971717',  # all
            'https://ndownloader.figstatic.com/files/6971729',  # filtered
        ]
    ),
}
_VALID_SOURCES: str = ','.join(str(i) for i in _SOURCES)


def Main() -> None:
  """Main PawnIngest."""
  # parse the input arguments, do some basic checks
  parser: argparse.ArgumentParser = argparse.ArgumentParser()
  parser.add_argument(
      '-s', '--sources', type=str, nargs='+', default=_VALID_SOURCES,
      help=f'Sources to use (default is "all", which are: "{_VALID_SOURCES})"')
  parser.add_argument(
      '-u', '--url', type=str, default='',
      help='URL to load from (default: empty); if given, overrides -s/--sources flag')
  parser.add_argument(
      '-l', '--maxload', type=int, default=0,
      help='Maximum number of games to read from source; 0==infinite (default: 0, i.e., infinite)')
  parser.add_argument(
      '-r', '--readonly', type=bool, default=False,
      help='If "True" will not save database, will only print (default: False)')
  parser.add_argument(
      '-m', '--maxprint', type=int, default=100,
      help='Maximum number of games to print for -r/--readonly mode; 0==infinite (default: 100)')
  parser.add_argument(
      '-i', '--ignorecache', type=bool, default=False,
      help='If "True" will not use cache, will re-download files (default: False)')
  args: argparse.Namespace = parser.parse_args()
  url: str = args.url.strip()
  sources: list[str] = [s.strip() for s in args.sources]
  if not sources and not url:
    raise ValueError('we must have either -s/--sources or -u/--url to load from')
  maxload: int = args.maxload if args.maxload >= 0 else 0
  maxprint: int = args.maxprint if args.maxprint >= 0 else 0
  db_readonly = bool(args.readonly)
  ignore_cache = bool(args.ignorecache)
  # start
  print(f'{base.TERM_BLUE}{base.TERM_BOLD}***********************************************')
  print(f'**         {base.TERM_LIGHT_RED}Pawnalyze ingest PGNs{base.TERM_BLUE}             **')
  print('**   balparda@gmail.com (Daniel Balparda)    **')
  print(f'***********************************************{base.TERM_END}')
  success_message: str = f'{base.TERM_WARNING}premature end? user paused?'
  try:
    # creates objects
    pgn_cache: Optional[pawnlib.PGNCache] = None if ignore_cache else pawnlib.PGNCache()
    database: Optional[pawnlib.PGNData] = None if db_readonly else pawnlib.PGNData()
    # execute the source reads
    print()
    with base.Timer() as op_timer:
      if url:
        _LoadFromURL(url, pgn_cache, database, maxload, maxprint)
        if database:
          database.Save()
      elif sources:
        raise NotImplementedError()
      else:
        raise NotImplementedError('No sources found')
    print()
    print(f'Executed in {base.TERM_GREEN}{base.HumanizedSeconds(op_timer.delta)}{base.TERM_END}')
    print()
    success_message = f'{base.TERM_GREEN}success'
  except Exception as err:
    success_message = f'{base.TERM_FAIL}error: {err}'
    raise
  finally:
    print(f'{base.TERM_BLUE}{base.TERM_BOLD}THE END: {success_message}{base.TERM_END}')


def _GamesFromLargePGN(file_path: str) -> Generator[tuple[str, chess.pgn.Game], None, None]:
  """Get individual PGN games and parse them."""
  for game_lines in _SplitLargePGN(file_path):
    pgn: str = '\n'.join(game_lines)
    pgn_io = io.StringIO(pgn)
    game: chess.pgn.Game = chess.pgn.read_game(pgn_io)  # type:ignore
    if not game:
      raise ValueError(f'No game found in game lines: {game_lines!r}')
    other_game: chess.pgn.Game = chess.pgn.read_game(pgn_io)  # type:ignore
    if other_game:
      raise ValueError(f'Game lines have more than one game: {game_lines!r}')
    yield (pgn, game)


def _SplitLargePGN(file_path: str) -> Generator[list[str], None, None]:
  """A very rough splitting of a huge PGN into individual games."""
  game_lines: list[str] = []
  saw_game: bool = False
  with open(file_path, 'rt', encoding='utf-8', errors='replace') as file_in:
    count = 0
    for count, line in enumerate(file_in):
      # strip the line and skip if empty
      pgn_line: str = line.strip()
      if not pgn_line:
        continue
      # we have a content line
      if pgn_line.startswith('['):
        # we have a header line
        if game_lines and saw_game:
          # we have a header+game in the lines, so we output it and restart
          yield game_lines
          game_lines, saw_game = [], False
      else:
        saw_game = True
      # add this line to the buffer
      game_lines.append(pgn_line)
    # if file didn't end with an empty line, you may have a last game to process:
    if game_lines:
      yield game_lines
    logging.info('Finished parsing %d lines of PGN', count + 1)


def _LoadFromURL(
    url: str,
    cache: Optional[pawnlib.PGNCache],
    db: Optional[pawnlib.PGNData],
    maxload: int,
    maxprint: int) -> int:
  """Load a source from URL."""
  pgn_path: Optional[str] = cache.GetCachedPath(url) if cache else None
  game_count: int = 0
  ply_count: int = 0
  node_count: int = 0
  with tempfile.NamedTemporaryFile() as out_file:
    if pgn_path is None:
      # we don't have the PGN yet: open the URL, download file
      logging.info('Downloading URL %r', url)
      with urllib.request.urlopen(url) as response, tempfile.NamedTemporaryFile() as raw_file:
        raw_file.write(response.read())
        raw_file.seek(0)
        # open the temporary file as a ZIP archive
        logging.info('Unzipping file')
        with zipfile.ZipFile(raw_file, 'r') as zip_ref:
          # for simplicity, assume there's only one PGN inside.
          pgn_file_name: str = zip_ref.namelist()[0]
          with zip_ref.open(pgn_file_name) as pgn_file:
            out_file.write(pgn_file.read())
      # now we have a file name, so keep it
      pgn_path = out_file.name
      if cache:
        cache.AddCachedFile(url, out_file)  # type:ignore
    # we have the PGN as a file in "pgn_path" for sure here
    processing_start: float = time.time()
    for game_count, (pgn, game) in enumerate(_GamesFromLargePGN(pgn_path)):
      if maxload > 0 and game_count >= maxload:
        logging.info('Stopping loading games because reached limit of %d games', maxload)
        break
      if db:
        # we are building the DB
        plys: int
        nodes: int
        plys, nodes = db.LoadGame(pgn, game)
        ply_count += plys
        node_count += nodes
        if not game_count % 10000 and game_count:
          delta: float = time.time() - processing_start
          logging.info(
              'Loaded %d games (%d plys, %d nodes, %0.1f%%) in %s '
              '(%0.1f games/s average = %s per million games)',
              game_count, ply_count, node_count, 100.0 * (ply_count - node_count) / ply_count,
              base.HumanizedSeconds(delta), game_count / delta,
              base.HumanizedSeconds(1000000.0 * delta / game_count))
      else:
        # we are printing the games
        if maxprint > 0 and game_count >= maxprint:
          logging.info('Stopping printing games because reached limit of %d games', maxprint)
          break
        print('*' * 80)
        print(f'Game # {game_count + 1}')
        print()
        print(pgn)
        if game.errors:
          print()
          print(f'  ==>> ERROR: {pawnlib.GAME_ERRORS(game)!r}')
        print()
  return game_count


if __name__ == '__main__':
  logging.basicConfig(level=logging.INFO, format=base.LOG_FORMAT)  # set this as default
  Main()
