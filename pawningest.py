#!/usr/bin/python3 -O
#
# Copyright 2025 Daniel Balparda (balparda@gmail.com)
# GNU General Public License v3 (http://www.gnu.org/licenses/gpl-3.0.txt)
#
"""Pawnalyze ingest PGNs.

pawningest.py

This module ingests PGN files (from a URL, local file, or directory) into the
Pawnalyze SQLite database. It can also print games without saving them if run
in read-only mode.

Typical usage:
  ./pawningest.py -u "https://ndownloader.figstatic.com/files/6971717"
    - Downloads the PGN file from the given URL (zipped or 7z),
      parses it, and loads it into the Pawnalyze DB.

  ./pawningest.py -f /path/to/local/games.pgn
    - Reads a local .pgn file and loads it into the DB.

  ./pawningest.py -d /path/to/pgnfiles/
    - Recursively reads all .pgn files in the directory
      and ingests them.

Optional arguments:
  -r/--readonly : If set to True, parse and print but do not save to the DB.
  -i/--ignorecache : If True, do not check or store the PGN cache; always re-download.
  -s/--sources : Named source keys, pulling from a dictionary of known URLs.
  -u/--url : A direct download link for PGN data.
  -f/--file : A single local PGN file.
  -d/--dir : A directory containing multiple PGN files.
"""

import argparse
import logging
import os
import os.path
# import pdb
from typing import Optional

from baselib import base
from pawnalyze import pawnlib

__author__ = 'balparda@gmail.com (Daniel Balparda)'
__version__ = (1, 0)


def _LoadFromURL(url: str, cache: Optional[pawnlib.PGNCache], db: pawnlib.PGNData) -> int:
  """Load a source from URL."""
  game_count: int = 0
  for game_count, _, _, _, _ in db.CachedLoadFromURL(url, cache):
    pass
  return game_count


def _LoadFromFile(file_path: str, db: pawnlib.PGNData) -> int:
  """Load a source from a file."""
  game_count: int = 0
  for game_count, _, _, _, _ in db.LoadFromDisk(file_path):
    pass
  return game_count


def _LoadFromSource(source: str, cache: Optional[pawnlib.PGNCache], db: pawnlib.PGNData) -> int:
  """Load a source from URL."""
  source = source.strip().lower()
  if source not in _SOURCES:
    raise ValueError(f'Invalid source {source!r}')
  domain, human_url, download_urls = _SOURCES[source]
  logging.info('Reading from source %s: %s (%s)', source, domain, human_url)
  game_count: int = 0
  if not db:
    raise NotImplementedError()
  for url in download_urls:
    game_count += _LoadFromURL(url, cache, db)
  return game_count


def _LoadFromDirectory(dir_path: str, db: pawnlib.PGNData) -> int:
  """Load files from directory."""
  game_count: int = 0
  for dirpath, _, filenames in os.walk(dir_path):
    logging.info('Reading files from %r', dirpath)
    for file_name in sorted(filenames):
      file_path: str = os.path.join(dirpath, file_name)
      if file_path.endswith('.pgn'):
        game_count += _LoadFromFile(file_path, db)
  return game_count


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
      '-f', '--file', type=str, default='',
      help='local file to load from (default: empty); if given, overrides -s/--sources flag')
  parser.add_argument(
      '-d', '--dir', type=str, default='',
      help='local dir to load from (default: empty); if given, overrides -s/--sources flag')
  parser.add_argument(
      '-r', '--readonly', type=bool, default=False,
      help='If "True" will not save database (default: False)')
  parser.add_argument(
      '-i', '--ignorecache', type=bool, default=False,
      help='If "True" will not use cache, will re-download files (default: False)')
  args: argparse.Namespace = parser.parse_args()
  url: str = args.url.strip()
  local_file_path: str = args.file.strip()
  local_dir_path: str = args.dir.strip()
  sources: list[str] = ([s.strip() for s in args.sources] if isinstance(args.sources, list) else  # type:ignore
                        [args.sources.strip()])
  if not sources and not url and not local_file_path and not local_dir_path:
    raise ValueError('must have -s/--sources or -u/--url or -f/--file or -d/--dir to load from')
  if any(s.strip().lower() not in _SOURCES for s in sources):
    raise ValueError(f'Invalid source in {sources}, valid are {_VALID_SOURCES}')
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
    database: pawnlib.PGNData = pawnlib.PGNData(readonly=db_readonly)
    try:
      # execute the source reads
      print()
      with base.Timer() as op_timer:
        if url:
          _LoadFromURL(url, pgn_cache, database)
        elif local_file_path:
          _LoadFromFile(local_file_path, database)
        elif local_dir_path:
          _LoadFromDirectory(local_dir_path, database)
        elif sources:
          for source in sorted(sources):
            _LoadFromSource(source, pgn_cache, database)
        else:
          raise NotImplementedError('No sources found')
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


# sources we can handle should be "registered" here!
_SOURCES: dict[str, tuple[str, str, list[str]]] = {  # name: (domain, human_url, list[download_url])
    # 'lumbrasgigabase': (
    #     'lumbrasgigabase.com',
    #     'https://lumbrasgigabase.com/',
    #     [
    #         'blob:https://mega.nz/834c3f58-1bf8-4e5c-8bac-2e59c30b5ca7',

    #         'https://lumbrasgigabase.com/download/lumbras-giga-base-pgn-2023-2/?wpdmdl=8752&amp;refresh=67bf14f94fce91740575993',
    #         'https://lumbrasgigabase.com/download/lumbras-giga-base-pgn-2023/?wpdmdl=8068&amp;refresh=67bf14f950eac1740575993',
    #         'https://lumbrasgigabase.com/download/lumbras-giga-base-pgn-2022/?wpdmdl=8069&amp;refresh=67bf14f951d761740575993',
    #         'https://lumbrasgigabase.com/download/lumbras-giga-base-pgn-2021/?wpdmdl=8070&amp;refresh=67bf14f9529681740575993',
    #         'https://lumbrasgigabase.com/download/lumbras-giga-base-pgn-2020/?wpdmdl=8071&amp;refresh=67bf14f95351b1740575993',
    #         'https://lumbrasgigabase.com/download/lumbras-giga-base-pgn-2015-to-2019/?wpdmdl=8072&amp;refresh=67bf14f9540b71740575993',
    #         'https://lumbrasgigabase.com/download/lumbras-giga-base-pgn-2005-to-2009/?wpdmdl=8074&amp;refresh=67bf14f954bf31740575993',
    #         'https://lumbrasgigabase.com/download/lumbras-giga-base-pgn-2000-to-2004/?wpdmdl=8075&amp;refresh=67bf14f9557e91740575993',
    #         'https://lumbrasgigabase.com/download/lumbras-giga-base-pgn-1990-to-1999/?wpdmdl=8076&amp;refresh=67bf14f9565111740575993',
    #         'https://lumbrasgigabase.com/download/lumbras-giga-base-pgn-2010-to-2014/?wpdmdl=8073&amp;refresh=67bf14f9570a41740575993',
    #         'https://lumbrasgigabase.com/download/lumbras-giga-base-pgn-1970-to-1989/?wpdmdl=8077&amp;refresh=67bf160c614521740576268',
    #         'https://lumbrasgigabase.com/download/lumbras-giga-base-pgn-1950-to-1969/?wpdmdl=8078&amp;refresh=67bf160c62c4e1740576268',
    #         'https://lumbrasgigabase.com/download/lumbras-giga-base-pgn-1900-to-1949/?wpdmdl=8081&amp;refresh=67bf160c63fe71740576268',
    #         'https://lumbrasgigabase.com/download/lumbras-giga-base-pgn-until-1899/?wpdmdl=8079&amp;refresh=67bf160c653251740576268',
    #         'https://lumbrasgigabase.com/download/lumbras-giga-base-pgn-with-no-date/?wpdmdl=8080&amp;refresh=67bf160c666221740576268',
    #     ]),
    'figshare': (
        'figshare.com',
        'https://figshare.com/articles/dataset/Chess_Database/4276523',
        [
            'https://ndownloader.figstatic.com/files/6971717',
        ]
    ),
}
_VALID_SOURCES: str = ','.join(str(i) for i in _SOURCES)


if __name__ == '__main__':
  logging.basicConfig(level=logging.INFO, format=base.LOG_FORMAT)  # set this as default
  Main()
