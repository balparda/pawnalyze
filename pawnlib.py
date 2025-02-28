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
from typing import Any, BinaryIO, Callable, Optional

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
  INSUFFICIENT_MATERIAL = enum.auto()  # neither side has sufficient winning material
  REPETITIONS_3 = enum.auto()  # one side can claim draw
  REPETITIONS_5 = enum.auto()  # since 2014-7-1 this game is automatically drawn
  # ATTENTION: checking for repetitions is costly for the chess library!
  MOVES_50 = enum.auto()       # one side can claim draw
  MOVES_75 = enum.auto()       # since 2014-7-1 this game is automatically drawn
  # <<== add new stuff to the end!


@dataclasses.dataclass
class GamePosition:
  """Game position."""
  plys: dict[int, Any]                   # the next found continuations {ply: GamePosition}
  flags: PositionFlag                    # the status of this position
  games: Optional[list[dict[str, str]]]  # list of PGN headers that end in this position


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
      (board.is_insufficient_material, PositionFlag.INSUFFICIENT_MATERIAL),
      (board.is_repetition, PositionFlag.REPETITIONS_3),
      (board.is_fivefold_repetition, PositionFlag.REPETITIONS_5),
      (board.is_fifty_moves, PositionFlag.MOVES_50),
      (board.is_seventyfive_moves, PositionFlag.MOVES_75),
  ]
  for method, flag in position_checks:
    if method():
      flags |= flag
  # add mandatory winning conditions
  if PositionFlag.CHECKMATE in flags and PositionFlag.BLACK_TO_MOVE in flags:
    flags |= PositionFlag.WHITE_WIN
  if PositionFlag.CHECKMATE in flags and PositionFlag.WHITE_TO_MOVE in flags:
    flags |= PositionFlag.BLACK_WIN
  # add mandatory draw positions
  if (PositionFlag.STALEMATE in flags or
      PositionFlag.INSUFFICIENT_MATERIAL in flags or
      PositionFlag.REPETITIONS_5 in flags or
      PositionFlag.MOVES_75 in flags):
    flags |= PositionFlag.DRAWN_GAME
    # check that it is not also a win position!
    if PositionFlag.BLACK_WIN in flags or PositionFlag.WHITE_WIN in flags:
      raise InvalidGameError(f'Position is both a WIN and a DRAW, ({flags!r}) at {san} with {board.fen()!r}')
  return flags


class PGNData:
  """A PGN Database for Pawnalyze."""

  def __init__(self) -> None:
    """Constructor."""
    # check data directory is there
    if not os.path.exists(_PGN_DATA_DIR):
      os.makedirs(_PGN_DATA_DIR)
      logging.info('Created empty data dir %r', _PGN_DATA_DIR)
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
    new_count: int = 0
    n_ply: int = -1
    board: chess.Board = game.board()
    try:
      # does this game contain errors?
      if game.errors:
        # game goes into errors list
        raise InvalidGameError(GAME_ERRORS(game))
      # game should be OK, so add to dict structure by going over the moves
      dict_pointer: dict[int, GamePosition] = self.db.positions
      position: Optional[GamePosition] = None
      new_flags = PositionFlag(0)
      game_headers: dict[str, str] = _GameMinimalHeaders(game)
      # test for non-standard chess games
      if board.chess960 or board.fen() != STANDARD_CHESS_FEN:
        raise NonStandardGameError()
      # test for games we don't know the result of
      game_result: str = game_headers.get('result', '?')
      if game_result not in {'1-0', '0-1', '1/2-1/2'}:
        raise InvalidGameError('Game has no recorded result')
      # go over the moves
      for n_ply, move in enumerate(game.mainline_moves()):
        # push the move to the board
        encoded_ply: int = EncodePly(move)
        san: str = board.san(move)
        if not board.is_legal(move):
          raise InvalidGameError(f'Invalid move at {san} with {board.fen()!r}')
        board.push(move)
        # add to dictionary, if needed
        if encoded_ply not in dict_pointer:
          # new entry, check if position is valid
          if (board_status := board.status()) or not board.is_valid():
            raise InvalidGameError(f'Invalid position ({board_status!r}) at {san} with {board.fen()!r}')
          # add the position
          new_count += 1
          new_flags = _CreatePositionFlags(board, san, new_flags)
          dict_pointer[encoded_ply] = GamePosition(plys={}, flags=new_flags, games=None)
          # check for unexpected game endings
          for end_flag, expected_result in [
              (PositionFlag.WHITE_WIN, '1-0'),
              (PositionFlag.BLACK_WIN, '0-1'),
              (PositionFlag.DRAWN_GAME, '1/2-1/2')]:
            if end_flag in new_flags and game_result != expected_result:
              raise InvalidGameError(
                  f'Game result {game_result} should be {expected_result} at {san} with {board.fen()!r}')
        # move the pointer
        position = dict_pointer[encoded_ply]
        dict_pointer = position.plys
      # game has ended
      if not position:
        # game had no moves, we will consider this an "error" game
        raise EmptyGameError()
      # we have a valid game, so we must add the game here
      if position.games is None:
        position.games = []
      position.games.append(game_headers)
      return (n_ply + 1, new_count)
    except EmptyGameError:
      self.db.empty_games.append(ErrorGame(pgn=original_pgn, error='Game has no moves'))
      return (0, 0)
    except NonStandardGameError:
      self.db.non_standard_games.append(ErrorGame(
          pgn=original_pgn,
          error=f'Non-standard chess{"960" if board.chess960 else ""} game: {board.fen()!r}'))
      return (0, 0)
    except InvalidGameError as err:
      error_game = ErrorGame(pgn=original_pgn, error=err.args[0])
      self.db.error_games.append(error_game)
      logging.warning(str(error_game))
      return (n_ply + 1, new_count)
