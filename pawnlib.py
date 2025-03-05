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
from typing import BinaryIO, Callable, Generator, Optional

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
_PGN_SQL_FILE: str = os.path.join(_PGN_DATA_DIR, 'pawnalyze-games.db')

# useful
GAME_ERRORS: Callable[[chess.pgn.Game], str] = lambda g: ' ; '.join(e.args[0] for e in g.errors)
STANDARD_CHESS_FEN: str = 'rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1'
STARTING_POSITION_HASH: pawnzobrist.Zobrist = pawnzobrist.ZobristFromBoard(chess.pgn.Game().board())
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

# make player names "Doe, John" -> "john doe"
_NormalizeNames: Callable[[str], str] = lambda n: (
    ' '.join(n.lower().split(', ', 1)[::-1]) if ', ' in n else n.lower())


class Error(Exception):
  """Base pawnalyze exception."""


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


class InvalidGameError(Error):
  """Game is invalid exception."""

  def __init__(self, message: str, category: ErrorGameCategory) -> None:
    super().__init__(message)
    self.category: ErrorGameCategory = category


class EmptyGameError(InvalidGameError):
  """Game is invalid because it has no moves exception."""

  def __init__(self, message: str = 'Game has no moves') -> None:
    super().__init__(message, ErrorGameCategory.EMPTY_GAME)


class NonStandardGameError(InvalidGameError):
  """Game is invalid because it is not standard chess exception."""

  def __init__(self, message: str = 'Game is non-standard chess') -> None:
    super().__init__(message, ErrorGameCategory.NON_STANDARD_CHESS)


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

# at what ply depth should we be more lax with game comparisons?
_PLY_LAX_COMPARISON_DEPTH: int = 40  # i.e., if game is beyond 20th move and is much less likely to repeat


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
  flags: PositionFlag = PositionFlag(PositionFlag.WHITE_TO_MOVE)
  extras: ExtraInsightPositionFlag = ExtraInsightPositionFlag(0)
  # does this game contain errors?
  if game.errors:
    # game goes into errors list
    raise InvalidGameError(GAME_ERRORS(game), ErrorGameCategory.LIBRARY_ERROR)
  # test for non-standard chess games
  if board.chess960 or board.fen() != STANDARD_CHESS_FEN:
    raise NonStandardGameError(
        f'Non-standard chess game{" (chess960)" if board.chess960 else ""}: {board.fen()}')
  # go over the moves
  for n_ply, move in enumerate(game.mainline_moves()):
    # push the move to the board
    san: str = board.san(move)
    if not board.is_legal(move):
      raise InvalidGameError(
          f'Invalid move at {san} with {board.fen()!r}', ErrorGameCategory.INVALID_MOVE)
    board.push(move)
    # check if position is valid
    if (board_status := board.status()) or not board.is_valid():
      raise InvalidGameError(
          f'Invalid position ({board_status!r}) at {san} with {board.fen()!r}',
          ErrorGameCategory.INVALID_POSITION)
    # yield useful move/position info
    zobrist_current: int = hasher(board)
    flags, extras = _CreatePositionFlags(board, san, flags, extras)
    yield (n_ply + 1, san, EncodePly(move),
           (pawnzobrist.Zobrist(zobrist_previous), pawnzobrist.Zobrist(zobrist_current)),
           board, flags, extras)
    zobrist_previous = zobrist_current


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
        f'{san} with {board.fen()!r}', ErrorGameCategory.ENDING_ERROR)
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
  return (flags, extra)


def _FixGameResultHeaderOrRaise(
    original_pgn: str, game: chess.pgn.Game, headers: dict[str, str]) -> None:
  """Either fixes the 'result' header, or raises InvalidGameError."""
  if headers.get('result', '*') in _RESULTS_PGN:
    return  # all is already OK
  # go over the moves, unfortunately we have to pay the price of going over redundantly
  n_ply: int = 0
  flags: PositionFlag = PositionFlag(PositionFlag.WHITE_TO_MOVE)
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
  raise InvalidGameError('Game has no recorded result and no clear end', ErrorGameCategory.ENDING_ERROR)


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


class PGNData:
  """A PGN Database for Pawnalyze using SQLite."""

  _TABLE_ORDER: list[str] = [
      'positions', 'games', 'moves', 'idx_games_positions_hash', 'idx_destination_hash']

  _TABLES: dict[str, str] = {

      'positions': """
          CREATE TABLE IF NOT EXISTS positions (
              position_hash TEXT PRIMARY KEY CHECK (length(position_hash) = 32),  -- 128 bit Zobrist hex
              flags INTEGER NOT NULL,  -- PositionFlag integer
              extras TEXT NOT NULL,    -- ExtraInsightPositionFlag ','-separated hex set
              game_hashes TEXT         -- ','-separated hex set of game_hash that ended here, if any
          );
      """,

      'games': """
          CREATE TABLE IF NOT EXISTS games (
              game_hash TEXT PRIMARY KEY      CHECK (length(game_hash)         = 64),  -- 256 bit SHA-256 hex
              end_position_hash TEXT NOT NULL CHECK (length(end_position_hash) = 32),  -- 128 bit Zobrist hex
              game_plys INTEGER NOT NULL,       -- number of plys if success in parsing, 0 for error games
              game_headers TEXT NOT NULL,       -- JSON dict with game headers
              error_category INTEGER NOT NULL,  -- if error game: ErrorGameCategory integer (0 == no error)
              error_pgn TEXT,                   -- if error game: original PGN
              error_message TEXT,               -- if error game: some sort of error description
              FOREIGN KEY(end_position_hash) REFERENCES positions(position_hash) ON DELETE RESTRICT
          );
      """,

      'idx_games_positions_hash': 'CREATE INDEX IF NOT EXISTS idx_games_positions_hash ON games(end_position_hash);',

      'moves': """
          CREATE TABLE IF NOT EXISTS moves (
              from_position_hash TEXT NOT NULL CHECK (length(from_position_hash) = 32),  -- 128 bit Zobrist hex
              ply INTEGER NOT NULL,                                                      -- encoded ply for move
              to_position_hash TEXT NOT NULL   CHECK (length(to_position_hash)   = 32),  -- 128 bit Zobrist hex
              PRIMARY KEY(from_position_hash, ply),
              FOREIGN KEY(from_position_hash) REFERENCES positions(position_hash) ON DELETE RESTRICT,
              FOREIGN KEY(to_position_hash) REFERENCES positions(position_hash) ON DELETE RESTRICT
          );
      """,

      'idx_destination_hash': 'CREATE INDEX IF NOT EXISTS idx_destination_hash ON moves(to_position_hash);',

  }

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
      logging.info('Adding standard chess base position...')
      with self._conn:
        self._InsertPosition(
            STARTING_POSITION_HASH,
            PositionFlag(PositionFlag.WHITE_TO_MOVE), ExtraInsightPositionFlag(0))

  def Close(self) -> None:
    """Close the database connection."""
    self._conn.close()

  def _EnsureSchema(self) -> None:
    """Create tables if they do not exist."""
    if (names := set(PGNData._TABLE_ORDER)) != (tables := set(PGNData._TABLES.keys())):
      raise ValueError(
          f'_TABLE_ORDER should be the same keys in _TABLES: {sorted(names)} versus {sorted(tables)}')
    with self._conn:
      for name in PGNData._TABLE_ORDER:
        logging.info('Creating table %r', name)
        self._conn.execute(PGNData._TABLES[name])

  def DropAllTables(self) -> None:
    """Drop all tables from the database (destructive operation)."""
    with self._conn:
      for name in PGNData._TABLE_ORDER[::-1]:
        logging.info('Deleting table %r', name)
        self._conn.execute(f'DROP TABLE IF EXISTS {name};')
    logging.warning('Dropped all database tables')

  def DeleteDBFile(self) -> None:
    """Closes connection and deletes the entire DB file from disk."""
    self._conn.close()
    if os.path.exists(_PGN_SQL_FILE):
      os.remove(_PGN_SQL_FILE)
      logging.warning('Deleted database file %r', _PGN_SQL_FILE)

  def WipeData(self) -> None:
    """Delete all data and data file."""
    self.DropAllTables()
    self.DeleteDBFile()

  def _InsertPosition(
      self, position_hash: pawnzobrist.Zobrist, flags: PositionFlag,
      extras: ExtraInsightPositionFlag, game_hash: Optional[str] = None) -> bool:
    """Insert a position, or update if existing by adding one game. Returns True on new position."""
    # check if position_hash exists
    cursor: sqlite3.Cursor = self._conn.execute(
        'SELECT flags, extras, game_hashes FROM positions WHERE position_hash = ?;',
        (str(position_hash),))
    row: Optional[tuple[int, str, Optional[str]]] = cursor.fetchone()
    if not row:
      # brand new entry, guaranteed to have only one ExtraInsightPositionFlag & one hash
      self._conn.execute("""
          INSERT INTO positions (position_hash, flags, extras, game_hashes)
          VALUES (?, ?, ?, ?)
      """, (str(position_hash), flags.value, hex(extras.value)[2:],
            game_hash if game_hash else None))
      return True
    # we already have this position, so we check if flags are consistent and add headers, if any
    if row[0] != flags.value:
      raise ValueError(
          f'Conflicting flags for position {position_hash}: {row[0]} (old) versus {flags} (new)')
    # add extra flags
    row_changed = False
    existing_extras_set: set[str] = set(row[1].split(','))
    if (new_extra := hex(extras.value)[2:]) not in existing_extras_set:
      existing_extras_set.add(new_extra)
      row_changed = True
    # add extra hashes, if needed
    existing_hashes_set: set[str] = set(row[2].split(',')) if row[2] else set()
    if game_hash:
      if game_hash not in existing_hashes_set:
        existing_hashes_set.add(game_hash)
        row_changed = True
    # save, if needed
    if row_changed:
      self._conn.execute("""
          UPDATE positions
          SET extras = ?, game_hashes = ?
          WHERE position_hash = ?
      """, (','.join(sorted(existing_extras_set)), ','.join(sorted(existing_hashes_set)),
            str(position_hash)))
    return False

  def _GetPosition(
      self, position_hash: pawnzobrist.Zobrist) -> Optional[
          tuple[PositionFlag, set[ExtraInsightPositionFlag], set[str]]]:
    """Retrieve the PositionFlag for the given hash. Returns None if not found."""
    cursor: sqlite3.Cursor = self._conn.execute(
        'SELECT flags, extras, game_hashes FROM positions WHERE position_hash = ?;',
        (str(position_hash),))
    row: Optional[tuple[int, str, Optional[str]]] = cursor.fetchone()
    if row is None:
      return None
    flag = PositionFlag(row[0])
    extras: set[ExtraInsightPositionFlag] = set(
        ExtraInsightPositionFlag(int(e, 16)) for e in row[1].split(','))
    return (flag, extras, set() if row[2] is None else set(row[2].split(',')))

  def _InsertParsedGame(
      self, game_hash: str, end_position_hash: pawnzobrist.Zobrist, game_plys: int,
      game_headers: dict[str, str]) -> None:
    """Insert a "successful" game in `game_hash` with `position_hash`, `game_plys`, and `game_headers`."""
    self._conn.execute("""
        INSERT OR IGNORE INTO games(game_hash, end_position_hash, game_plys, game_headers, error_category)
        VALUES(?, ?, ?, ?, ?)
    """, (game_hash, str(end_position_hash), game_plys, json.dumps(game_headers), 0))

  def _InsertErrorGame(
      self, game_hash: str, game_headers: dict[str, str],
      error_category: ErrorGameCategory, error_pgn: str, error_message: str) -> None:
    """Insert an error game entry."""
    self._conn.execute("""
        INSERT OR IGNORE INTO games(game_hash, end_position_hash, game_plys, game_headers,
                                    error_category, error_pgn, error_message)
        VALUES(?, ?, ?, ?, ?, ?, ?)
    """, (game_hash, str(STARTING_POSITION_HASH), 0, json.dumps(game_headers),
          error_category.value, error_pgn, error_message))

  def _GetGame(self, game_hash: str) -> Optional[
      tuple[pawnzobrist.Zobrist, int, dict[str, str],
            ErrorGameCategory, Optional[str], Optional[str]]]:
    """Return game (zobrist, plys, header, err_car, err_pgn, err_message) for game_hash; None if not found."""
    cursor: sqlite3.Cursor = self._conn.execute("""
        SELECT end_position_hash, game_plys, game_headers, error_category, error_pgn, error_message
        FROM games
        WHERE game_hash = ?;
    """, (game_hash,))
    row: Optional[tuple[str, int, str, ErrorGameCategory,
                        Optional[str], Optional[str]]] = cursor.fetchone()
    if not row:
      return None
    return (pawnzobrist.Zobrist(int(row[0], 16)), row[1], json.loads(row[2]),
            ErrorGameCategory(row[3]), row[4], row[5])

  def _GetAllGames(self) -> Generator[
      tuple[str, pawnzobrist.Zobrist, int, dict[str, str],
            ErrorGameCategory, Optional[str], Optional[str]], None, None]:
    """Yields all games as (hash, zobrist, plys, header, err_car, err_pgn, err_message)."""
    cursor: sqlite3.Cursor = self._conn.execute(
        'SELECT game_hash, end_position_hash, game_plys, game_headers, '
        'error_category, error_pgn, error_message FROM games;')
    for h, p, i, d, c, s, m in cursor.fetchall():
      yield (h, pawnzobrist.Zobrist(int(p, 16)), i, json.loads(d), ErrorGameCategory(c), s, m)

  def _InsertMove(
      self, from_hash: pawnzobrist.Zobrist, ply: int, to_hash: pawnzobrist.Zobrist) -> None:
    """Insert an edge from `from_hash` with move `ply` leading to `to_hash`."""
    self._conn.execute("""
        INSERT OR IGNORE INTO moves(from_position_hash, ply, to_position_hash)
        VALUES(?, ?, ?)
    """, (str(from_hash), ply, str(to_hash)))

  def _GetMoves(
      self, position_hash: pawnzobrist.Zobrist) -> list[tuple[int, pawnzobrist.Zobrist]]:
    """Return a list of (ply, to_position_hash) for the given from_position_hash."""
    cursor: sqlite3.Cursor = self._conn.execute("""
        SELECT ply, to_position_hash
        FROM moves
        WHERE from_position_hash = ?;
    """, (str(position_hash),))
    return [(ply, pawnzobrist.Zobrist(int(z, 16))) for ply, z in cursor.fetchall()]

  def LoadGame(self, original_pgn: str, game: chess.pgn.Game) -> tuple[int, int]:
    """Loads game into database. Returns (plys, new_positions)."""
    # get game_hash and check if we already know this exact game PGN
    game_hash: str = base.BytesHexHash(original_pgn.encode(encoding='utf-8', errors='replace'))
    if (done_game := self._GetGame(game_hash)):
      # we already did this game; nothing to do
      return (done_game[1], 0)
    # we don't have this game, so prepare to parse it
    n_ply: int = 0
    new_count: int = 0
    board: Optional[chess.Board] = None
    z_current: pawnzobrist.Zobrist = STARTING_POSITION_HASH
    game_headers: dict[str, str] = _GameMinimalHeaders(game)
    try:
      with self._conn:  # make all game operations inside one transaction
        n_ply_checkmate: tuple[int, str] = (0, '')
        flags: PositionFlag = PositionFlag(PositionFlag.WHITE_TO_MOVE)
        extras: ExtraInsightPositionFlag = ExtraInsightPositionFlag(0)
        # test for games we don't know the result of
        _FixGameResultHeaderOrRaise(original_pgn, game, game_headers)
        # go over the moves
        for n_ply, san, encoded_ply, (z_previous, z_current), board, flags, extras in IterateGame(game):
          # insert position and move
          new_count += int(self._InsertPosition(z_current, flags, extras))
          self._InsertMove(z_previous, encoded_ply, z_current)
          # check for unexpected game endings
          if (PositionFlag.CHECKMATE in flags and game_headers['result'] == _DRAW_PGN):
            n_ply_checkmate = (n_ply, san)  # we save this to check later is this is the last move...
        # reached end of game
        if board is None:
          # game had no moves, we will consider this an "error" game
          raise EmptyGameError()
        # check for case of games marked draw that are actually checkmate
        if n_ply_checkmate[0]:
          if n_ply > n_ply_checkmate[0]:
            # in this case the game continued *after* checkmate, so we raise
            raise InvalidGameError(
                f'Draw result 1/2-1/2 should be checkmate at {n_ply_checkmate[0]}/{n_ply_checkmate[1]}',
                ErrorGameCategory.ENDING_ERROR)
          # if we got here: game is checkmated but marked as draw in error
          game_headers['result'] = _WHITE_WIN_PGN if WHITE_WIN(flags) else _BLACK_WIN_PGN
          logging.warning('Fixing game ending draw->%s for %r', game_headers['result'], game_headers)
        # we have a valid game, so we must add the game here
        self._InsertPosition(z_current, flags, extras, game_hash=game_hash)
        self._InsertParsedGame(game_hash, z_current, n_ply, game_headers)
        return (n_ply, new_count)
    except InvalidGameError as err:
      # some sort of error in game, insert as error game
      with self._conn:
        self._InsertErrorGame(game_hash, game_headers, err.category, original_pgn, err.args[0])
      # log if error not exactly empty|non-standard (these are plentiful and not interesting to see)
      if err.category not in {ErrorGameCategory.EMPTY_GAME, ErrorGameCategory.NON_STANDARD_CHESS}:
        logging.warning('%s\n%r', str(err), original_pgn)
      return (0, 0)

  # TODO: add a method for trimming the tree of nodes without games

  # TODO: add a method for duplicate game in a node detection


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
