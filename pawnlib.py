#!/usr/bin/python3 -O
#
# Copyright 2025 Daniel Balparda (balparda@gmail.com)
# GNU General Public License v3 (http://www.gnu.org/licenses/gpl-3.0.txt)
#
"""Pawnalyze base library of util methods and classes."""

import dataclasses
import enum
import hashlib
import json
import logging
import os
import os.path
# import pdb
import sqlite3
import sys
from typing import Any, BinaryIO, Callable, Generator, Optional

import chess
import chess.engine
import chess.pgn
import chess.polyglot

from baselib import base
from pawnalyze import pawnzobrist

__author__ = 'balparda@gmail.com (Daniel Balparda)'
__version__ = (1, 0)


# PGN cache directory
_PGN_CACHE_DIR: str = base.MODULE_PRIVATE_DIR(__file__, '.pawnalyze-cache')
_PGN_CACHE_FILE: str = os.path.join(_PGN_CACHE_DIR, 'cache.bin')

# PGN data directory
_PGN_DATA_DIR: str = base.MODULE_PRIVATE_DIR(__file__, '.pawnalyze-data')
_PGN_DATA_FILE: str = os.path.join(_PGN_DATA_DIR, 'pawnalyze-games-db2.bin')
_PGN_SQL_FILE: str = os.path.join(_PGN_DATA_DIR, 'pawnalyze-games.db')

# useful
GAME_ERRORS: Callable[[chess.pgn.Game], str] = lambda g: ' ; '.join(e.args[0] for e in g.errors)
STANDARD_CHESS_FEN: str = 'rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1'
_EMPTY_HEADER_VALUES: set[str] = {
    '?', '??', '???', '????',
    'x', 'xx', 'xxx', 'xxxx',
    '-', '--', '---', '----',
    '*', '**', '***', '****',
    '#', '##', '###', '####',
    '.', '..', '...', '....',
    '????.??.??', 'xxxx.xx.xx', '####.##.##',
    '????.??', 'xxxx.xx', '####.##',
    'n/a', 'unknown', 'none', 'no',
    'no date', 'no name', 'no event',
}

# make player names "Balparda, Daniel" -> "daniel balparda"
_NormalizeNames: Callable[[str], str] = lambda n: (
    ' '.join(n.lower().split(', ', 1)[::-1]) if ', ' in n else n.lower())

# convert a chess.Move into an integer we can use to index our dictionaries
EncodePly: Callable[[chess.Move], int] = lambda m: (
    m.from_square * 100 + m.to_square + (m.promotion * 1000000 if m.promotion else 0))


class Error(Exception):
  """Base pawnalyze exception."""


class InvalidGameError(Error):
  """Game is invalid exception."""


class EmptyGameError(InvalidGameError):
  """Game is invalid because it has no moves exception."""


class NonStandardGameError(InvalidGameError):
  """Game is invalid because is it not standard chess exception."""


class ErrorGameCategory(enum.Flag):
  """Game error categories in DB."""
  # ATTENTION: DO NOT ADD TO BEGINNING OR MIDDLE OF LIST! ONLY ADD AT THE END or
  # you will corrupt the database!! DO NOT REORDER LIST!
  # Was using enum.auto() but hardcoded values to help avoid data corruption.
  EMPTY_GAME = 1 << 0          # game with no moves
  NON_STANDARD_CHESS = 1 << 1  # chess960 or handicap or incomplete game or any non-standard
  LIBRARY_ERROR = 1 << 2       # error reported by loading library
  INVALID_POSITION = 1 << 3    # invalid position found
  INVALID_MOVE = 1 << 4        # invalid move found
  ENDING_ERROR = 1 << 5        # game ending has some problem


class PositionFlag(enum.Flag):
  """States a position might be in. Must be position (Zobrist) agnostic."""
  # ATTENTION: DO NOT ADD TO BEGINNING OR MIDDLE OF LIST! ONLY ADD AT THE END or
  # you will corrupt the database!! DO NOT REORDER LIST!
  # Was using enum.auto() but hardcoded values to help avoid data corruption.
  # The conditions below are mandatory (by the rules) and depend only on the
  # Zobrist hash, which encodes: [BOARD, TURN, CASTLING RIGHTS, EN PASSANT SQUARES]
  WHITE_TO_MOVE = 1 << 0  # white moves in this position
  BLACK_TO_MOVE = 1 << 1  # black moves in this position
  CHECK = 1 << 2      # is the current side to move in check
  CHECKMATE = 1 << 3  # is the current position checkmate
  STALEMATE = 1 << 4  # is the current position stalemate
  WHITE_INSUFFICIENT_MATERIAL = 1 << 5   # white does not have sufficient winning material
  BLACK_INSUFFICIENT_MATERIAL = 1 << 6  # black does not have sufficient winning material
  # <<== add new stuff to the end!


class ExtraInsightPositionFlag(enum.Flag):
  """States a position might be in that are not necessarily Zobrist Agnostic."""
  # ATTENTION: DO NOT ADD TO BEGINNING OR MIDDLE OF LIST! ONLY ADD AT THE END or
  # you will corrupt the database!! DO NOT REORDER LIST!
  # ATTENTION: checking for repetitions is costly for the chess library!
  # repeated game position counters
  REPETITIONS_3 = 1 << 10  # one side can claim draw (3x repetition rule)
  REPETITIONS_5 = 1 << 11  # since 2014-7-1 this game is automatically drawn (5x repetition rule)
  # halfmoves that have elapsed without a capture or pawn move counters
  MOVES_50 = 1 << 12       # one side can claim draw (50 moves rule)
  MOVES_75 = 1 << 13       # since 2014-7-1 this game is automatically drawn (75 moves rule)
  GAME_CONTINUED_AFTER_MANDATORY_DRAW = 1 << 14  # position *after* game should have drawn
  # <<== add new stuff to the end!


@dataclasses.dataclass
class EngineResult:
  """Analysis engine result."""
  ply: int             # the best found continuation
  score: int           # if present (not mate): the score in centi-pawns
  mate: Optional[int]  # if present: > 0 => side to move is mating in 'mate' moves; < 0 => opponent is mating in abs(mate) moves


@dataclasses.dataclass
class GamePosition:
  """Game position."""
  plys: dict[int, Any]                   # the next found continuations {ply: GamePosition}
  flags: PositionFlag                    # the status of this position
  engine: Optional[EngineResult]         # if given, the result of the engine computation
  games: Optional[list[dict[str, str]]]  # list of PGN headers that end in this position


@dataclasses.dataclass
class ErrorGame:
  """A game that failed checks."""
  pgn: str    # the whole PGN for the game
  error: str  # error given by chess module


@dataclasses.dataclass
class LoadedGames:
  """Loaded games structure to be saved to disk."""
  positions: dict[int, GamePosition]   # the initial plys as {ply: GamePosition}
  empty_games: list[ErrorGame]         # the games that have errors and cannot be used
  non_standard_games: list[ErrorGame]  # the games that have errors and cannot be used
  error_games: list[ErrorGame]         # the games that have errors and cannot be used


# PositionFlag helpers, only depend on the Zobrist hash
WHITE_WIN: Callable[[PositionFlag], bool] = lambda f: (
    PositionFlag.CHECKMATE in f and PositionFlag.BLACK_TO_MOVE in f)
BLACK_WIN: Callable[[PositionFlag], bool] = lambda f: (
    PositionFlag.CHECKMATE in f and PositionFlag.WHITE_TO_MOVE in f)
DRAWN_GAME: Callable[[PositionFlag], bool] = lambda f: (
    PositionFlag.STALEMATE in f or (PositionFlag.WHITE_INSUFFICIENT_MATERIAL in f and
                                    PositionFlag.BLACK_INSUFFICIENT_MATERIAL in f))

# ExtraInsightPositionFlag helpers, depend on game history and not only on Zobrist hash
DRAWN_GAME_EXTRA: Callable[[PositionFlag, ExtraInsightPositionFlag], bool] = lambda p, e: (
    DRAWN_GAME(p) or
    ExtraInsightPositionFlag.REPETITIONS_5 in e or ExtraInsightPositionFlag.MOVES_75 in e)
CAN_CLAIM_DRAW: Callable[[ExtraInsightPositionFlag], bool] = lambda f: (
    ExtraInsightPositionFlag.REPETITIONS_3 in f or ExtraInsightPositionFlag.MOVES_50 in f)

# game results PGN code, and the checking helper
_WHITE_WIN_PGN: str = '1-0'
_BLACK_WIN_PGN: str = '0-1'
_DRAW_PGN: str = '1/2-1/2'
_RESULTS_PGN: dict[str, Callable[[PositionFlag], bool]] = {
    _WHITE_WIN_PGN: WHITE_WIN,
    _BLACK_WIN_PGN: BLACK_WIN,
    _DRAW_PGN: DRAWN_GAME,
}


class PGNCache:
  """PGN cache."""

  @dataclasses.dataclass
  class _Cache:
    """A cache mapping to be saved to disk."""
    files: dict[str, str]  # {URL(lowercase): file_path}

  def __init__(self) -> None:
    """Constructor."""
    # check cache directory is there
    if not os.path.exists(_PGN_CACHE_DIR):
      os.makedirs(_PGN_CACHE_DIR)
      logging.info('Created empty PGN cache dir %r', _PGN_CACHE_DIR)
    # load cache file, create if empty
    self._cache: PGNCache._Cache = PGNCache._Cache(files={})
    if os.path.exists(_PGN_CACHE_FILE):
      self._cache = base.BinDeSerialize(file_path=_PGN_CACHE_FILE)
      logging.info('Loaded cache from %r with %d entries', _PGN_CACHE_FILE, len(self._cache.files))
    else:
      logging.info('No cache file to load yet')

  def GetCachedPath(self, url: str) -> Optional[str]:
    """Returns path for cached file, if found in cache. If not returns None."""
    file_path: Optional[str] = self._cache.files.get(url.lower(), None)
    if file_path:
      logging.info('Cache hit for %r -> %r', url, file_path)
    return file_path

  def AddCachedFile(self, file_url: str, file_obj: BinaryIO) -> str:
    """Adds open file_obj into cache as being downloaded from file_url. Saves cache."""
    file_obj.seek(0)
    hex_hash: str = hashlib.sha256(file_obj.read()).hexdigest().lower()
    file_obj.seek(0)
    file_path: str = os.path.join(_PGN_CACHE_DIR, f'{hex_hash}.pgn')
    with open(file_path, 'wb') as cached_obj:
      cached_obj.write(file_obj.read())
    self._cache.files[file_url.lower()] = file_path
    base.BinSerialize(self._cache, _PGN_CACHE_FILE)
    logging.info('Added URL %r to cache (%r)', file_url, file_path)
    return file_path


def _GameMinimalHeaders(game: chess.pgn.Game) -> dict[str, str]:
  """Return a dict with only parsed/relevant content."""
  headers: dict[str, str] = {}
  date_ending: Callable[[str], bool] = lambda y: any(
      y.endswith(x) for x in ('.??', '.xx', '.XX', '.**', '.##'))
  for k, v in game.headers.items():
    v: str = v.strip()
    v = v[:-3] if date_ending(v) else v
    v = v[:-3] if date_ending(v) else v  # second time to take care of '1992.??.??'
    if not v or v.lower() in _EMPTY_HEADER_VALUES:
      continue  # skip any empty or default value
    headers[k.lower()] = v
  return headers


def DecodePly(ply: int) -> chess.Move:
  """Convert integer from dictionaries (ply) to a chess move."""
  promotion: Optional[int] = None
  if ply > 10000:
    promotion = ply // 1000000
    ply -= promotion * 1000000
    if promotion not in {chess.KNIGHT, chess.BISHOP, chess.ROOK, chess.QUEEN}:
      raise ValueError(f'Invalid promotion: {promotion}')
  from_square: int = ply // 100
  ply -= from_square * 100
  if not 0 <= from_square < 64 or not 0 <= ply < 64:
    raise ValueError(f'Invalid coordinates: {from_square} / {ply}')
  return chess.Move(from_square, ply, promotion=promotion)


def IterateGame(game: chess.pgn.Game) -> Generator[
    tuple[int, str, int, tuple[pawnzobrist.Zobrist, pawnzobrist.Zobrist],
          chess.Board, PositionFlag, ExtraInsightPositionFlag], None, None]:
  """Iterates a game, returning useful information of moves and board.

  Args:
    game: The game

  Yields:
    (ply_counter,
     san_move,
     encoded_ply_move, (zobrist_previous, zobrist_current),
     board_obj, position_flags, extra_flags)

  Raises:
    NonStandardGameError: if non-traditional chess is detected
    InvalidGameError: if game object indicates errors or if illegal move/position is detected
  """
  board: chess.Board = game.board()
  hasher: Callable[[chess.Board], int] = pawnzobrist.Zobrist.MakeHasher()
  zobrist_previous: int = hasher(board)
  flags: PositionFlag = PositionFlag(0)
  extras: ExtraInsightPositionFlag = ExtraInsightPositionFlag(0)
  # does this game contain errors?
  if game.errors:
    # game goes into errors list
    raise InvalidGameError(GAME_ERRORS(game))
  # test for non-standard chess games
  if board.chess960 or board.fen() != STANDARD_CHESS_FEN:
    raise NonStandardGameError()
  # go over the moves
  for n_ply, move in enumerate(game.mainline_moves()):
    # push the move to the board
    san: str = board.san(move)
    if not board.is_legal(move):
      raise InvalidGameError(f'Invalid move at {san} with {board.fen()!r}')
    board.push(move)
    # check if position is valid
    if (board_status := board.status()) or not board.is_valid():
      raise InvalidGameError(f'Invalid position ({board_status!r}) at {san} with {board.fen()!r}')
    # yield useful move/position info
    zobrist_current: int = hasher(board)
    flags, extras = _CreatePositionFlags(board, san, flags, extras)
    yield (n_ply + 1, san, EncodePly(move),
           (pawnzobrist.Zobrist(zobrist_previous), pawnzobrist.Zobrist(zobrist_current)),
           board, flags, extras)
    zobrist_previous = zobrist_current


def _CreatePositionFlags(
    board: chess.Board,
    san: str,
    old_flags: PositionFlag,
    old_extra: ExtraInsightPositionFlag) -> tuple[PositionFlag, ExtraInsightPositionFlag]:
  """Creates position flags for a given position and also if game should mandatorily end."""
  # create as the move
  flags: PositionFlag = PositionFlag.WHITE_TO_MOVE if board.turn else PositionFlag.BLACK_TO_MOVE
  extra = ExtraInsightPositionFlag(0)
  # add stuff from previous moves
  if PositionFlag.CHECKMATE in old_flags:
    raise InvalidGameError(
        f'Continued game after checkmate, {old_flags!r} / {old_extra!r} at '
        f'{san} with {board.fen()!r}')
  if (ExtraInsightPositionFlag.GAME_CONTINUED_AFTER_MANDATORY_DRAW in old_extra or
      DRAWN_GAME_EXTRA(old_flags, old_extra)):
    extra |= ExtraInsightPositionFlag.GAME_CONTINUED_AFTER_MANDATORY_DRAW
  # add the "is_*()" method calls
  position_checks: list[tuple[Callable[[], bool], PositionFlag]] = [
      (board.is_check, PositionFlag.CHECK),
      (board.is_checkmate, PositionFlag.CHECKMATE),
      (board.is_stalemate, PositionFlag.STALEMATE),
  ]
  for method, flag in position_checks:
    if method():
      flags |= flag
  extra_checks: list[tuple[Callable[[], bool], ExtraInsightPositionFlag]] = [
      (board.is_repetition, ExtraInsightPositionFlag.REPETITIONS_3),
      (board.is_fivefold_repetition, ExtraInsightPositionFlag.REPETITIONS_5),
      (board.is_fifty_moves, ExtraInsightPositionFlag.MOVES_50),
      (board.is_seventyfive_moves, ExtraInsightPositionFlag.MOVES_75),
  ]
  for method, flag in extra_checks:
    if method():
      extra |= flag
  # check material
  for color, material_flag in {
      chess.WHITE: PositionFlag.WHITE_INSUFFICIENT_MATERIAL,
      chess.BLACK: PositionFlag.BLACK_INSUFFICIENT_MATERIAL}.items():
    if board.has_insufficient_material(color):
      flags |= material_flag
    # check that it is not also a win position!
    if PositionFlag.CHECKMATE in flags:
      raise InvalidGameError(
          f'Position is both a WIN and a DRAW, ({flags!r}) at {san} with {board.fen()!r}')
  return (flags, extra)


def _FixGameResultHeaderOrRaise(
    original_pgn: str, game: chess.pgn.Game, headers: dict[str, str]) -> None:
  """Either fixes the 'result' header, or raises InvalidGameError."""
  if headers.get('result', '*') in _RESULTS_PGN:
    return  # all is already OK
  # go over the moves, unfortunately we have to pay the price of going over redundantly
  n_ply: int = 0
  flags: PositionFlag = PositionFlag(0)
  extras: ExtraInsightPositionFlag = ExtraInsightPositionFlag(0)
  result_pgn: str
  for n_ply, _, _, _, _, flags, extras in IterateGame(game):
    pass  # we just want to get to last recorded move
  if n_ply:
    for result_pgn, result_flag in _RESULTS_PGN.items():
      if result_flag(flags) or result_pgn == _DRAW_PGN and DRAWN_GAME_EXTRA(flags, extras):
        # we found a game that had a very concrete ending result
        logging.info(
            'Adopting forced result: %s -> %s (%r)', headers.get('result', '*'),
            result_pgn, headers)
        headers['result'] = result_pgn
        return
  # as last resource we look into actual PGN to see if it has some recorded result at end
  result_pgn = original_pgn.split('\n')[-1].strip()
  if result_pgn and result_pgn in _RESULTS_PGN:
    # found one
    logging.info(
        'Adopting PGN last-line result: %s -> %s (%r)', headers.get('result', '*'),
        result_pgn, headers)
    headers['result'] = result_pgn
    return
  # could not fix the problem, so we raise
  raise InvalidGameError('Game has no recorded result and no clear end')


_PLY_LAX_COMPARISON_DEPTH: int = 40  # i.e., if game is beyond 20th move and is much less likely to repeat


def _HeaderCompare(
    ha: dict[str, str], hb: dict[str, str], ply_depth: int) -> tuple[
        bool, Optional[dict[str, str]]]:
  """Compare 2 dict headers, ha and hb. If equal also return a new merged header dict.

  Args:
    ha: Header dict A
    hb: Header dict B

  Returns:
    (is_equal, merged_header) ; merged_header will only be present if is_equal is True
                                and is a new object (not header A nor header B)
  """
  # TODO: rewrite... this is bad
  # first just shallow compare
  if ha == hb:
    return (True, ha.copy())  # shallow copy should work for now
  # first look at 'result': if it is different then games are not the same most probably
  result_a: str = ha.get('result', '*')
  result_b: str = hb.get('result', '*')
  if result_a not in _RESULTS_PGN or result_b not in _RESULTS_PGN:
    raise ValueError(f'Invalid result/game {ha!r} / {hb!r}')
  if result_a != result_b:
    return (False, None)
  # we should have the same 'result'...
  # look at 'date': if it is different and significant, then not the same most probably
  date_a: str = ha.get('date', '?')
  date_b: str = hb.get('date', '?')
  if date_a != date_b:
    return (False, None)
  # we should have the same 'date'/'result' but date might not be significant...
  if ply_depth > _PLY_LAX_COMPARISON_DEPTH and (len(date_a) > 4 or len(date_b) > 4):
    # HEURISTIC: dates can be determinative at high ply counts
    return (True, _HeaderMerge(ha, hb))
  # look at names
  white_a: str = _NormalizeNames(ha.get('white', '?'))
  white_b: str = _NormalizeNames(hb.get('white', '?'))
  black_a: str = _NormalizeNames(ha.get('black', '?'))
  black_b: str = _NormalizeNames(hb.get('black', '?'))
  if white_a != white_b or black_a != black_b:
    return (False, None)
  # we should have the same 'date'/'result'/'white'/'black' but date/names might not be significant...
  # HEURISTIC: can we suppose they are the same now?
  return (True, _HeaderMerge(ha, hb))


def _HeaderMerge(ha: dict[str, str], hb: dict[str, str]) -> dict[str, str]:
  """Merge 2 headers avoiding losses."""
  # TODO: rewrite... this is bad
  # start with ha
  hm: dict[str, str] = ha.copy()
  # carefully copy hb into it:
  for k, v in hb.items():
    if k in hm:
      # key already exists: append if different, leave if equal
      orig_v: str = hm[k]
      if k in {'white', 'black'} and _NormalizeNames(v) == _NormalizeNames(orig_v):
        continue
      if v != orig_v:
        hm[k] = f'{orig_v} | {v}'
    else:
      # new key: add
      hm[k] = v
  return hm


class PGNData:
  """A PGN Database for Pawnalyze."""

  _RECURSION_LIMIT = 10000  # default is usually 1000: sys.getrecursionlimit()

  def __init__(self) -> None:
    """Constructor."""
    # check data directory is there
    if not os.path.exists(_PGN_DATA_DIR):
      os.makedirs(_PGN_DATA_DIR)
      logging.info('Created empty data dir %r', _PGN_DATA_DIR)
    # increase recursion limit so pickle will work with larger structures
    if (old_recursion := sys.getrecursionlimit()) < PGNData._RECURSION_LIMIT:
      logging.info(
          'Changing recursion limit from %d to %d', old_recursion, PGNData._RECURSION_LIMIT)
      sys.setrecursionlimit(PGNData._RECURSION_LIMIT)
    # load data file, create if empty
    self.db: LoadedGames = LoadedGames(
        positions={}, empty_games=[], non_standard_games=[], error_games=[])
    if os.path.exists(_PGN_DATA_FILE):
      self.db = base.BinDeSerialize(file_path=_PGN_DATA_FILE)
      logging.info('Loaded data from %r', _PGN_DATA_FILE)
    else:
      logging.info('No data file to load yet')

  def Save(self) -> None:
    """Save DB file."""
    base.BinSerialize(self.db, _PGN_DATA_FILE)
    logging.info('Saved data file %r', _PGN_DATA_FILE)

  def LoadGame(self, original_pgn: str, game: chess.pgn.Game) -> tuple[int, int]:
    """Loads game into database. Returns (plys, new_positions)."""
    n_ply: int = 0
    n_ply_checkmate: tuple[int, str] = (0, '')
    new_count: int = 0
    board: Optional[chess.Board] = None
    flags: PositionFlag = PositionFlag(0)
    try:
      # prepare to add to dict structure by going over the moves
      dict_pointer: dict[int, GamePosition] = self.db.positions
      position: GamePosition = GamePosition(plys={}, flags=PositionFlag(0), engine=None, games=None)
      game_headers: dict[str, str] = _GameMinimalHeaders(game)
      # test for games we don't know the result of
      _FixGameResultHeaderOrRaise(original_pgn, game, game_headers)
      # go over the moves
      for n_ply, san, encoded_ply, (z_previous, z_current), board, flags, _ in IterateGame(game):
        # add to dictionary, if needed
        if encoded_ply not in dict_pointer:
          # add the position
          new_count += 1
          dict_pointer[encoded_ply] = GamePosition(plys={}, flags=flags, engine=None, games=None)
          # check for unexpected game endings
          if (PositionFlag.CHECKMATE in flags and game_headers['result'] == _DRAW_PGN):
            n_ply_checkmate = (n_ply, san)  # we save this to check later is this is the last move...
        # move the pointer
        position = dict_pointer[encoded_ply]
        dict_pointer = position.plys
      # reached end of game
      if board is None:
        # game had no moves, we will consider this an "error" game
        raise EmptyGameError()
      # check for case of games marked draw that are actually checkmate
      if n_ply_checkmate[0]:
        if n_ply > n_ply_checkmate[0]:
          # in this case the game continued *after* checkmate, so we raise
          raise InvalidGameError(
              f'Draw result 1/2-1/2 should be checkmate at {n_ply_checkmate[0]}/{n_ply_checkmate[1]}')
        # if we got here: game is checkmated but marked as draw in error
        game_headers['result'] = _WHITE_WIN_PGN if WHITE_WIN(flags) else _BLACK_WIN_PGN
        logging.warning('Fixing game ending draw->%s for %r', game_headers['result'], game_headers)
      # we have a valid game, so we must add the game here
      if position.games is None:
        position.games = []
      for i, g in enumerate(position.games):
        g_equal: bool
        g_merge: Optional[dict[str, str]]
        g_equal, g_merge = _HeaderCompare(game_headers, g, n_ply)
        if g_equal and game_headers != g:
          logging.info('Merge: \n%r + \n%r = \n%r', g, game_headers, g_merge)
          position.games.pop(i)
          position.games.append(g_merge if g_merge else {})
          break
      else:
        position.games.append(game_headers)
      return (n_ply, new_count)
    except EmptyGameError:
      # empty game, no moves
      self.db.empty_games.append(ErrorGame(pgn=original_pgn, error='Game has no moves'))
      return (0, 0)
    except NonStandardGameError:
      # some kind of non-standard chess game
      self.db.non_standard_games.append(ErrorGame(
          pgn=original_pgn,
          error=f'Non-standard chess{"960" if board and board.chess960 else ""} '
                f'game: {board.fen() if board else "?"!r}'))
      return (0, 0)
    except InvalidGameError as err:
      # all other parsing errors
      error_game = ErrorGame(pgn=original_pgn, error=err.args[0])
      self.db.error_games.append(error_game)
      logging.warning(str(error_game))
      return (n_ply, new_count)

  # TODO: add a method for trimming the tree of nodes without games

  # TODO: add a method for duplicate game in a node detection


class PGNDataSQLite:
  """A PGN Database for Pawnalyze using SQLite."""

  _POSITIONS_SCHEMA = """
    CREATE TABLE IF NOT EXISTS positions (
        position_hash INTEGER PRIMARY KEY,  -- 128 bit Zobrist
        flags INTEGER NOT NULL,             -- PositionFlag integer
        extras TEXT NOT NULL,               -- ExtraInsightPositionFlag ','-separated hex set
        game_headers TEXT                   -- JSON array of game headers or NULL
    );
    """

  _MOVES_SCHEMA = """
    CREATE TABLE IF NOT EXISTS moves (
        from_position_hash INTEGER NOT NULL,  -- 128 bit Zobrist
        ply INTEGER NOT NULL,                 -- encoded ply for move
        to_position_hash INTEGER NOT NULL,    -- 128 bit Zobrist
        PRIMARY KEY(from_position_hash, ply)
    );
    """

  _ERROR_GAMES_SCHEMA = """
    CREATE TABLE IF NOT EXISTS error_games (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        category INTEGER NOT NULL,  -- ErrorGameCategory integer
        pgn TEXT NOT NULL,
        error TEXT NOT NULL
    );
    """

  def __init__(self) -> None:
    """Open or create the SQLite DB."""
    # check data directory is there
    if not os.path.exists(_PGN_DATA_DIR):
      os.makedirs(_PGN_DATA_DIR)
      logging.info('Created empty data dir %r', _PGN_DATA_DIR)
    # open DB, create if empty
    exists_db: bool = os.path.exists(_PGN_SQL_FILE)
    self._conn: sqlite3.Connection = sqlite3.connect(_PGN_SQL_FILE)
    self._conn.execute('PRAGMA foreign_keys = ON;')  # allow foreign keys to be used
    if exists_db:
      logging.info('Opening SQLite DB in %r', _PGN_SQL_FILE)
    else:
      logging.info('Creating new SQLite DB in %r', _PGN_SQL_FILE)
      self._EnsureSchema()

  def Close(self) -> None:
    """Close the database connection."""
    self._conn.close()

  def _EnsureSchema(self) -> None:
    """Create tables if they do not exist."""
    self._conn.execute(PGNDataSQLite._POSITIONS_SCHEMA)
    self._conn.execute(PGNDataSQLite._MOVES_SCHEMA)
    self._conn.execute(PGNDataSQLite._ERROR_GAMES_SCHEMA)
    self._conn.commit()

  def DropAllTables(self) -> None:
    """Drop all tables from the database (destructive operation)."""
    cursor: sqlite3.Cursor = self._conn.cursor()
    cursor.execute('DROP TABLE IF EXISTS error_games;')
    cursor.execute('DROP TABLE IF EXISTS moves;')
    cursor.execute('DROP TABLE IF EXISTS positions;')
    self._conn.commit()
    logging.warning('Dropped all database tables')

  def DeleteDBFile(self) -> None:
    """Closes connection and deletes the entire DB file from disk."""
    self._conn.close()
    if os.path.exists(_PGN_SQL_FILE):
      os.remove(_PGN_SQL_FILE)
      logging.warning('Deleted database file %r', _PGN_SQL_FILE)

  def WipeData(self) -> None:
    """Delete data."""
    self.DropAllTables()
    self.DeleteDBFile()

  def InsertPosition(
      self, position_hash: pawnzobrist.Zobrist,
      flags: PositionFlag, extras: ExtraInsightPositionFlag,
      game_headers: Optional[list[dict[str, str]]]) -> None:
    """Insert a position, or update if existing by adding game headers."""
    cur: sqlite3.Cursor = self._conn.cursor()
    # check if position_hash exists
    cur.execute(
        'SELECT flags, extras, game_headers FROM positions WHERE position_hash = ?;',
        (position_hash.z,))
    row = cur.fetchone()
    if row:
      # we already have this position, so we check if flags are consistent and add headers, if any
      existing_flags, existing_extras, existing_json = row
      if existing_flags != flags:
        raise ValueError(
            f'Conflicting flags for position {position_hash}: '
            f'{existing_flags} (old) versus {flags} (new)')
      # add extra flags
      existing_extras = set(existing_extras.split(','))
      existing_extras.add(hex(extras.value))
      # look at headers, if needed
      if game_headers:
        # merge any new game headers
        existing_headers = [] if existing_json is None else json.loads(existing_json)
        updated_headers: str = json.dumps(existing_headers.extend(game_headers))
      else:
        updated_headers = existing_json
      # save
      cur.execute("""
          UPDATE positions
          SET flags = ?, extras = ?, game_headers = ?
          WHERE position_hash = ?
      """, (flags, ','.join(sorted(existing_extras)), updated_headers, position_hash.z))
    else:
      # brand new entry
      headers_json: Optional[str] = json.dumps(game_headers) if game_headers else None
      cur.execute("""
          INSERT INTO positions (position_hash, flags, extras, game_headers)
          VALUES (?, ?, ?, ?)
      """, (position_hash.z, flags.value, hex(extras.value), headers_json))
    self._conn.commit()

  def GetPosition(
      self, position_hash: pawnzobrist.Zobrist) -> tuple[
          Optional[PositionFlag], Optional[set[ExtraInsightPositionFlag]],
          Optional[list[dict[str, str]]]]:
    """Retrieve the PositionFlag for the given hash. Returns None if not found."""
    cursor: sqlite3.Cursor = self._conn.cursor()
    cursor.execute(
        'SELECT flags, extras, game_headers FROM positions WHERE position_hash = ?;', (position_hash.z,))
    row = cursor.fetchone()
    if row is None:
      return (None, None, None)
    flag = PositionFlag(row[0])
    extras: set[ExtraInsightPositionFlag] = set(
        ExtraInsightPositionFlag(int(e, 16)) for e in row[1].split(','))
    if row[2] is None:
      return (flag, extras, None)
    headers: Optional[list[dict[str, str]]] = json.loads(existing_json)
    return (flag, extras, headers if headers else None)

  def InsertMove(
      self, from_hash: pawnzobrist.Zobrist, ply: int, to_hash: pawnzobrist.Zobrist) -> None:
    """Insert an edge from `from_hash` with move `ply` leading to `to_hash`."""
    cursor: sqlite3.Cursor = self._conn.cursor()
    cursor.execute("""
        INSERT OR IGNORE INTO moves(from_position_hash, ply, to_position_hash)
        VALUES(?, ?, ?)
    """, (from_hash.z, ply, to_hash.z))
    self._conn.commit()

  def GetMoves(
      self, position_hash: pawnzobrist.Zobrist) -> list[tuple[int, pawnzobrist.Zobrist]]:
    """Return a list of (ply, to_position_hash) for the given from_position_hash."""
    cursor: sqlite3.Cursor = self._conn.cursor()
    cursor.execute("""
        SELECT ply, to_position_hash
        FROM position_moves
        WHERE from_position_hash = ?;
    """, (position_hash.z,))
    return [(ply, pawnzobrist.Zobrist(z)) for ply, z in cursor.fetchall()]

  def InsertErrorGame(self, category: ErrorGameCategory, pgn: str, error: str) -> None:
    """Insert an error game entry."""
    cursor: sqlite3.Cursor = self._conn.cursor()
    cursor.execute("""
        INSERT INTO error_games(category, pgn, error)
        VALUES (?, ?, ?)
    """, (category, pgn, error))
    self._conn.commit()

  def GetErrorGames(self) -> list[tuple[int, ErrorGameCategory, str, str]]:
    """Return a list of all (id, category, pgn, error)."""
    cursor: sqlite3.Cursor = self._conn.cursor()
    cursor.execute('SELECT id, category, pgn, error FROM error_games;')
    return [(i, ErrorGameCategory(c), p, e) for i, c, p, e in cursor.fetchall()]


# TODO: implement multithreaded workers that will, for each "node" (FEN) stockfish-eval the position
def FindBestMove(
    fen: str, depth: int = 20, engine_path: str = 'stockfish') -> tuple[chess.Move, int, int]:
  """Finds the best move for a position (FEN) up to a depth.

  Args:
    fen: FEN string to use
    depth: (default 20) ply depth to search
    engine_path: (default 'stockfish') the engine path to invoke

  Returns:
    (best_move, score, mate_in_n), where best_move is a chess.Move, score is in centi-pawns,
        and mate_in_n can be:
          0 = no forced mate found
          +N (positive) = side to move mates in N
          -N (negative) = opponent side mates in abs(N)
  """
  # open Stockfish in UCI mode
  with chess.engine.SimpleEngine.popen_uci(engine_path) as engine:
    # ask for an analysis from engine
    info: chess.List[chess.engine.InfoDict] = engine.analyse(
        chess.Board(fen),
        limit=chess.engine.Limit(depth=depth),
        info=chess.engine.INFO_ALL,  # to get full data
        multipv=1  # We only want the single best line
    )
    # check the result is as expected; best move is first move of best line
    if len(info) != 1 or not info[0].get('pv', None) or not info[0].get('score', None):
      raise RuntimeError(f'No principal variation or score returned by engine for FEN: {fen!r}')
    best_move: chess.Move = info[0]['pv'][0]  # type:ignore
    # check if the engine sees a forced mate from the current position
    mate_in: int = 0
    relative_score: chess.engine.Score = info[0]['score'].relative  # type:ignore
    if relative_score.is_mate() and (n_mate := relative_score.mate()):
      # mate_in > 0 => side to move is mating in n_mate moves
      # mate_in < 0 => the opponent is mating in abs(n_mate) moves
      mate_in = n_mate
    score: Optional[int] = relative_score.score()
    return (best_move, 0 if score is None else score, mate_in)
