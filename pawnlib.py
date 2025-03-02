#!/usr/bin/python3 -O
#
# Copyright 2025 Daniel Balparda (balparda@gmail.com)
# GNU General Public License v3 (http://www.gnu.org/licenses/gpl-3.0.txt)
#
"""Pawnalyze base library of util methods and classes."""

import dataclasses
import enum
import hashlib
import logging
import os
import os.path
# import pdb
import sys
from typing import Any, BinaryIO, Callable, Generator, Optional

import chess
import chess.pgn

from baselib import base

__author__ = 'balparda@gmail.com (Daniel Balparda)'
__version__ = (1, 0)


# PGN cache directory
_PGN_CACHE_DIR: str = base.MODULE_PRIVATE_DIR(__file__, '.pawnalyze-cache')
_PGN_CACHE_FILE: str = os.path.join(_PGN_CACHE_DIR, 'cache.bin')

# PGN data directory
_PGN_DATA_DIR: str = base.MODULE_PRIVATE_DIR(__file__, '.pawnalyze-data')
_PGN_DATA_FILE: str = os.path.join(_PGN_DATA_DIR, 'pawnalyze-games-db.bin')

# useful
GAME_ERRORS: Callable[[chess.pgn.Game], str] = lambda g: ' ; '.join(e.args[0] for e in g.errors)
STANDARD_CHESS_FEN: str = 'rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1'


class Error(Exception):
  """Base pawnalyze exception."""


class InvalidGameError(Error):
  """Game is invalid exception."""


class EmptyGameError(InvalidGameError):
  """Game is invalid because it has no moves exception."""


class NonStandardGameError(InvalidGameError):
  """Game is invalid because is it not standard chess exception."""


@dataclasses.dataclass
class _Cache:
  """A cache mapping to be saved to disk."""
  files: dict[str, str]  # {URL(lowercase): file_path}


class PGNCache:
  """PGN cache."""

  def __init__(self) -> None:
    """Constructor."""
    # check cache directory is there
    if not os.path.exists(_PGN_CACHE_DIR):
      os.makedirs(_PGN_CACHE_DIR)
      logging.info('Created empty PGN cache dir %r', _PGN_CACHE_DIR)
    # load cache file, create if empty
    self._cache: _Cache = _Cache(files={})
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


@dataclasses.dataclass
class ErrorGame:
  """A game that failed checks."""
  pgn: str    # the whole PGN for the game
  error: str  # error given by chess module


class PositionFlag(enum.Flag):
  """States a position might be in."""
  # ATTENTION: DO NOT ADD TO BEGINNING OR MIDDLE OF LIST! ONLY ADD AT THE END or
  # you will corrupt the database!! DO NOT REORDER LIST!
  # the conditions below are mandatory (by the rules) and depend only on the board
  WHITE_TO_MOVE = enum.auto()  # white moves in this position
  BLACK_TO_MOVE = enum.auto()  # black moves in this position
  DRAWN_GAME = enum.auto()     # STALEMATE | INSUFFICIENT_MATERIAL | REPETITIONS_5 | MOVES_75
  GAME_CONTINUED_AFTER_MANDATORY_DRAW = enum.auto()  # position after game should have drawn
  WHITE_WIN = enum.auto()      # BLACK_TO_MOVE & CHECKMATE
  BLACK_WIN = enum.auto()      # WHITE_TO_MOVE & CHECKMATE
  # the checks below do not depend on the player's intentions (are mandatory)
  CHECK = enum.auto()      # is the current side to move in check
  CHECKMATE = enum.auto()  # is the current position checkmate
  STALEMATE = enum.auto()  # is the current position stalemate
  WHITE_INSUFFICIENT_MATERIAL = enum.auto()  # white does not have sufficient winning material
  BLACK_INSUFFICIENT_MATERIAL = enum.auto()  # black does not have sufficient winning material
  REPETITIONS_3 = enum.auto()  # one side can claim draw
  REPETITIONS_5 = enum.auto()  # since 2014-7-1 this game is automatically drawn
  # ATTENTION: checking for repetitions is costly for the chess library!
  MOVES_50 = enum.auto()       # one side can claim draw
  MOVES_75 = enum.auto()       # since 2014-7-1 this game is automatically drawn
  # <<== add new stuff to the end!
  # TODO: implement multithreaded workers that will, for each "node" (FEN) stockfish-eval the position
  IS_BEST_PLAY = enum.auto()          # is the best stockfish play
  WHITE_FORCED_MATE_20 = enum.auto()  # white has forced mate in <=20 plys
  BLACK_FORCED_MATE_20 = enum.auto()  # black has forced mate in <=20 plys


RESULTS_FLAG_MAP: dict[PositionFlag, str] = {
    PositionFlag.WHITE_WIN: '1-0',
    PositionFlag.BLACK_WIN: '0-1',
    PositionFlag.DRAWN_GAME: '1/2-1/2',
}
RESULTS_PGN_MAP: dict[str, PositionFlag] = {v: k for k, v in RESULTS_FLAG_MAP.items()}


@dataclasses.dataclass
class GamePosition:
  """Game position."""
  plys: dict[int, Any]                   # the next found continuations {ply: GamePosition}
  flags: PositionFlag                    # the status of this position
  games: Optional[list[dict[str, str]]]  # list of PGN headers that end in this position


_EMPTY_POSITION: GamePosition = GamePosition(plys={}, flags=PositionFlag(0), games=None)


@dataclasses.dataclass
class LoadedGames:
  """Loaded games structure to be saved to disk."""
  positions: dict[int, GamePosition]   # the initial plys as {ply: GamePosition}
  empty_games: list[ErrorGame]         # the games that have errors and cannot be used
  non_standard_games: list[ErrorGame]  # the games that have errors and cannot be used
  error_games: list[ErrorGame]         # the games that have errors and cannot be used


def _GameMinimalHeaders(game: chess.pgn.Game) -> dict[str, str]:
  """Return a dict with only parsed/relevant content."""
  headers: dict[str, str] = {}
  for k, v in game.headers.items():
    v = v.strip()
    if not v or v in {'?', '*', '????.??.??'}:
      continue  # skip any empty or default value
    headers[k.lower()] = v
  return headers


# convert a chess.Move into an integer we can use to index our dictionaries
EncodePly: Callable[[chess.Move], int] = lambda m: (
    m.from_square * 100 + m.to_square + (m.promotion * 1000000 if m.promotion else 0))


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
    tuple[int, str, int, chess.Board, PositionFlag], None, None]:
  """Iterates a game, returning useful information of moves and board.

  Args:
    game: The game

  Yields:
    (ply_counter, san_move, encoded_ply_move, board_obj, position_flags)

  Raises:
    NonStandardGameError: if non-traditional chess is detected
    InvalidGameError: if game object indicates errors or if illegal move/position is detected
  """
  board: chess.Board = game.board()
  flags: PositionFlag = PositionFlag(0)
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
    yield (n_ply + 1, san, EncodePly(move), board, _CreatePositionFlags(board, san, flags))


def _CreatePositionFlags(board: chess.Board, san: str, old_flags: PositionFlag) -> PositionFlag:
  """Creates position flags for a given position and also if game should mandatorily end."""
  # create as the move
  flags: PositionFlag = PositionFlag.WHITE_TO_MOVE if board.turn else PositionFlag.BLACK_TO_MOVE
  # add stuff from previous moves
  if PositionFlag.WHITE_WIN in old_flags or PositionFlag.BLACK_WIN in old_flags:
    raise InvalidGameError(f'Continued game after checkmate, ({old_flags!r}) at {san} with {board.fen()!r}')
  if (PositionFlag.DRAWN_GAME in old_flags or
      PositionFlag.GAME_CONTINUED_AFTER_MANDATORY_DRAW in old_flags):
    flags |= PositionFlag.GAME_CONTINUED_AFTER_MANDATORY_DRAW
  # add the "is_*()" method calls
  position_checks: list[tuple[Callable[[], bool], PositionFlag]] = [
      (board.is_check, PositionFlag.CHECK),
      (board.is_checkmate, PositionFlag.CHECKMATE),
      (board.is_stalemate, PositionFlag.STALEMATE),
      (board.is_repetition, PositionFlag.REPETITIONS_3),
      (board.is_fivefold_repetition, PositionFlag.REPETITIONS_5),
      (board.is_fifty_moves, PositionFlag.MOVES_50),
      (board.is_seventyfive_moves, PositionFlag.MOVES_75),
  ]
  for method, flag in position_checks:
    if method():
      flags |= flag
  # check material
  for color, material_flag in {
      chess.WHITE: PositionFlag.WHITE_INSUFFICIENT_MATERIAL,
      chess.BLACK: PositionFlag.BLACK_INSUFFICIENT_MATERIAL}.items():
    if board.has_insufficient_material(color):
      flags |= material_flag
  # add mandatory winning conditions
  if PositionFlag.CHECKMATE in flags and PositionFlag.BLACK_TO_MOVE in flags:
    flags |= PositionFlag.WHITE_WIN
  if PositionFlag.CHECKMATE in flags and PositionFlag.WHITE_TO_MOVE in flags:
    flags |= PositionFlag.BLACK_WIN
  # add mandatory draw positions
  if (PositionFlag.STALEMATE in flags or
      (PositionFlag.WHITE_INSUFFICIENT_MATERIAL in flags and
       PositionFlag.BLACK_INSUFFICIENT_MATERIAL in flags) or
      PositionFlag.REPETITIONS_5 in flags or
      PositionFlag.MOVES_75 in flags):
    flags |= PositionFlag.DRAWN_GAME
    # check that it is not also a win position!
    if PositionFlag.BLACK_WIN in flags or PositionFlag.WHITE_WIN in flags:
      raise InvalidGameError(
          f'Position is both a WIN and a DRAW, ({flags!r}) at {san} with {board.fen()!r}')
  return flags


def _FixGameResultHeaderOrRaise(
    original_pgn: str, game: chess.pgn.Game, headers: dict[str, str]) -> None:
  """Either fixes the 'result' header, or raises InvalidGameError."""
  if headers.get('result', '*') not in RESULTS_PGN_MAP:
    return  # all is already OK
  # go over the moves, unfortunately we have to pay the price of going over redundantly
  n_ply: int = 0
  flags: PositionFlag = PositionFlag(0)
  result_pgn: str
  for n_ply, _, _, _, flags in IterateGame(game):
    pass  # we just want to get to last recorded move
  if n_ply:
    for result_flag, result_pgn in RESULTS_FLAG_MAP.items():
      if result_flag in flags:
        # we found a game that had a very concrete ending result
        logging.info(
            'Adopting forced result: %s -> %s (%r)', headers.get('result', '*'),
            result_pgn, headers)
        headers['result'] = result_pgn
        return
  # as last resource we look into actual PGN to see if it has some recorded result at end
  result_pgn = original_pgn.split('\n')[-1].strip()
  if result_pgn and result_pgn in RESULTS_PGN_MAP:
    # found one
    logging.info(
        'Adopting PGN last-line result: %s -> %s (%r)', headers.get('result', '*'),
        result_pgn, headers)
    headers['result'] = result_pgn
    return
  # could not fix the problem, so we raise
  raise InvalidGameError('Game has no recorded result and no clear end')


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
    new_count: int = 0
    board: Optional[chess.Board] = None
    try:
      # prepare to add to dict structure by going over the moves
      dict_pointer: dict[int, GamePosition] = self.db.positions
      position: GamePosition = _EMPTY_POSITION
      game_headers: dict[str, str] = _GameMinimalHeaders(game)
      # test for games we don't know the result of
      _FixGameResultHeaderOrRaise(original_pgn, game, game_headers)
      # go over the moves
      for n_ply, san, encoded_ply, board, flags in IterateGame(game):
        # add to dictionary, if needed
        if encoded_ply not in dict_pointer:
          # add the position
          new_count += 1
          dict_pointer[encoded_ply] = GamePosition(plys={}, flags=flags, games=None)
          # check for unexpected game endings
          if ((PositionFlag.WHITE_WIN in flags or PositionFlag.BLACK_WIN in flags) and
              game_headers['result'] == '1/2-1/2'):
            raise InvalidGameError(
                f'Draw result 1/2-1/2 should be {flags} at {n_ply}/{san} with {board.fen()!r}')
        # move the pointer
        position = dict_pointer[encoded_ply]
        dict_pointer = position.plys
      # reached end of game
      if board is None:
        # game had no moves, we will consider this an "error" game
        raise EmptyGameError()
      # we have a valid game, so we must add the game here
      if position.games is None:
        position.games = []
      position.games.append(game_headers)  # TODO: we have to treat repeated games imported; bias to discard if deeper than N plys (40?)
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
