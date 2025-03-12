#!/usr/bin/python3 -O
#
# Copyright 2025 Daniel Balparda (balparda@gmail.com)
# GNU General Public License v3 (http://www.gnu.org/licenses/gpl-3.0.txt)
#
"""Pawnalyze base library of util methods and classes."""

import dataclasses
import enum
import hashlib
import io
import json
import logging
import multiprocessing
import multiprocessing.queues
import multiprocessing.managers
import os
import os.path
# import pdb
import queue
import sqlite3
import tempfile
import time
from typing import Any, BinaryIO, Callable, Generator, IO, Optional, TypedDict
import urllib.request
import zipfile

import chess
import chess.engine
import chess.pgn
import chess.polyglot
import py7zr
import tqdm

from baselib import base
from pawnalyze import pawnzobrist

__author__ = 'balparda@gmail.com (Daniel Balparda)'
__version__ = (1, 0)


# PGN cache directory
_PGN_CACHE_DIR: str = base.MODULE_PRIVATE_DIR(__file__, '.pawnalyze-cache')

# PGN data directory
_PGN_DATA_DIR: str = base.MODULE_PRIVATE_DIR(__file__, '.pawnalyze-data')
_PGN_SQL_FILE: str = os.path.join(_PGN_DATA_DIR, 'pawnalyze-games.db')

# tactical constants
DEFAULT_ENGINE = 'stockfish'
ELO_CATEGORY_TO_PLY: dict[str, int] = {  # ply depth search for STOCKFISH VERSION 17+
    'club': 4,    # club player
    'expert': 8,
    'master': 12,
    'im': 14,     # international master
    'gm': 16,     # grandmaster
    'world': 18,  # world champion
    'super': 20,  # super-human
}

# useful
GAME_ERRORS: Callable[[chess.pgn.Game], str] = lambda g: ' ; '.join(e.args[0] for e in g.errors)
STANDARD_CHESS_FEN: str = 'rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1'
STARTING_POSITION_HASH: pawnzobrist.Zobrist = pawnzobrist.ZobristFromBoard(chess.pgn.Game().board())
_PRINT_EVERY_N = 10000
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
_WORKER_SENTINEL_MESSAGE: str = '-'

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


class PositionEval(TypedDict):
  """Chess engine evaluation of a position.

  For `mate`:
      0 = no forced mate found (look at `score`)
      +N (positive) = side to move mates in N plys
      -N (negative) = opponent side mates in abs(N) plys

  For `score`:
      0 = mate found (look at `mate`)
      +N (positive) = side to move is ahead by N / 100 pawns
      -N (negative) = opponent side is ahead by abs(N) / 100 pawns
  """
  depth: int  # depth of this evaluation
  best: int   # best found move; encoded
  mate: int   # 0 no mate; !=0 position has mate-in-N (==abs(mate)); >0 side to move; <0 opponent
  score: int  # score, only if mate==0, in centi-pawns
  # AVOID adding stuff here; if you do, change EncodeEval() & DecodeEval() and MIGRATE THE DB!!


# convert a PositionEval into a string of 4 ','-separated hex ints
EncodeEval: Callable[[PositionEval], str] = lambda e: ','.join(
    f'{e[k]:x}' for k in ('depth', 'best', 'mate', 'score'))


def DecodeEval(evaluation: str) -> PositionEval:
  """Decode position evaluation from ','-separated hex into a PositionEval."""
  depth, best, mate, score = evaluation.split(',')
  return PositionEval(
      depth=int(depth, 16), best=int(best, 16), mate=int(mate, 16), score=int(score, 16))


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


def CountFileLines(file_path: str) -> int:
  """Reads a file just to count the lines. Only worth it if processing file is tough."""
  with open(file_path, 'rt', encoding='utf-8', errors='ignore') as file_in:
    count: int = 0
    for count, _ in enumerate(file_in):
      pass
  return count


def _SplitLargePGN(file_path: str) -> Generator[tuple[list[str], int], None, None]:
  """A very rough splitting of a huge PGN into individual games."""
  game_lines: list[str] = []
  saw_game: bool = False
  # we open first to just count the lines
  with base.Timer() as count_timer:
    logging.info('Counting file lines...')
    total_lines: int = CountFileLines(file_path)
  logging.info(
      'File with %s lines (read in %s)', base.HumanizedDecimal(total_lines), count_timer.readable)
  # we open a second time to actually read
  with open(file_path, 'rt', encoding='utf-8', errors='replace') as file_in:
    count: int = 0
    line: str = ''
    for count, line in tqdm.tqdm(  # type: ignore
        enumerate(file_in), total=total_lines,
        mininterval=1.0, miniters=100, unit='ln', smoothing=0.6, colour='green'):
      # strip the line and skip if empty
      pgn_line: str = line.strip()  # type: ignore
      if not pgn_line:
        continue
      # we have a content line
      if pgn_line.startswith('['):  # type: ignore
        # we have a header line
        if game_lines and saw_game:
          # we have a header+game in the lines, so we output it and restart
          yield (game_lines, count)
          game_lines, saw_game = [], False
      else:
        saw_game = True
      # add this line to the buffer
      game_lines.append(pgn_line)  # type: ignore
    # if file didn't end with an empty line, you may have a last game to process:
    if game_lines:
      yield (game_lines, count)
    logging.info('Finished parsing %d lines of PGN', count + 1)  # type: ignore


def _GamesFromLargePGN(file_path: str) -> Generator[tuple[str, chess.pgn.Game, int], None, None]:
  """Get individual PGN games and parse them."""
  for game_lines, n_line in _SplitLargePGN(file_path):
    pgn: str = '\n'.join(game_lines)
    pgn_io = io.StringIO(pgn)
    game: chess.pgn.Game = chess.pgn.read_game(pgn_io)  # type:ignore
    if not game:
      raise ValueError(f'No game found in game lines: {game_lines!r}')
    # we are strict on purpose: we don't want any PGN with more than one game in it
    other_game: chess.pgn.Game = chess.pgn.read_game(pgn_io)  # type:ignore
    if other_game:
      raise ValueError(f'Game lines have more than one game: {game_lines!r}')
    yield (pgn, game, n_line)


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


def _IsDuplicateGame(
    plys_a: list[int], headers_a: dict[str, str],
    plys_b: list[int], headers_b: dict[str, str],
    soft_ply_threshold: int, hard_ply_threshold: int) -> bool:
  """Decide if game A and game B are duplicates. Returns True if we consider them duplicates.

  Args:
    plys_a: plys for first game
    headers_a: headers for first game
    plys_b: plys for second game
    headers_b: headers for second game
    soft_ply_threshold: games with >= ply depth than this are easier to declare duplicates
    hard_ply_threshold: games with >= ply depth than this are always considered duplicates

  Returns:
    True if duplicates, False otherwise
  """
  # 1. Duplicates are not just per position: the whole game has to be identical
  if plys_a != plys_b:
    return False  # we are strict: no difference in plies allowed
  # 2. Apply the "hard" threshold: above this number of plies, the games have to be the same
  if len(plys_a) >= hard_ply_threshold:
    return True  # no game can be considered not a duplicate past the hard_ply_threshold!
  # 3. If the length of plys is large, we treat them as duplicates if they share same end pos.
  #    Actually they do share the same end pos if they're in game_hashes for the same position,
  #    but let's confirm we do not have error categories or short games.
  if len(plys_a) >= soft_ply_threshold:
    # soft compare player names, e.g. "John Doe" vs "Doe, John A"
    w_a: str = _NormalizePlayer(headers_a.get('white', ''))
    w_b: str = _NormalizePlayer(headers_b.get('white', ''))
    if w_a != w_b:
      return False
    b_a: str = _NormalizePlayer(headers_a.get('black', ''))
    b_b: str = _NormalizePlayer(headers_b.get('black', ''))
    if b_a != b_b:
      return False
    # if we get here, we consider them duplicates
    return True
  # 4. If both games are short, we treat them as unique unless they have identical date + players
  #    or other strong match. This is up to your preference.
  date_a: str = headers_a.get('date', '')
  date_b: str = headers_b.get('date', '')
  if date_a and date_a == date_b:
    # check players again, but be more strict or less strict
    w_a = _NormalizePlayer(headers_a.get('white', ''))
    w_b = _NormalizePlayer(headers_b.get('white', ''))
    b_a = _NormalizePlayer(headers_a.get('black', ''))
    b_b = _NormalizePlayer(headers_b.get('black', ''))
    if w_a == w_b and b_a == b_b:
      return True
  # otherwise not duplicates
  return False


def _NormalizePlayer(name: str) -> str:
  """Soft compare approach for player name, ignoring punctuation and
  reversing 'lastname, firstname' forms, etc."""
  # all lowercase, remove commas & dots, trim multiple spaces
  name = name.lower().replace('.', '').strip()
  # for now just unify to a single spaced string; try to reorder if there's a comma
  return ' '.join(name.split(', ')[::-1])


def _MergeGameHeaders(headers_a: dict[str, str], headers_b: dict[str, str]) -> dict[str, str]:
  """Unify (new object) 2 headers, adding if no conflict, else merge with '|' delimiter."""
  merged: dict[str, str] = dict(headers_a)
  for k, v in headers_b.items():
    if not v or k == 'issues':
      continue
    if k not in merged:
      merged[k] = v
    else:
      if (original := merged[k]).lower() != v.lower():
        # if they differ, combine them with a pipe
        if k == 'result':
          # mark result as unknown?
          merged['result'] = '*'
        else:
          merged[k] = f'{merged[k]} | {v}'
        merged.setdefault('issues', set()).add(f'{k}: {original!r}/{v!r}')  # type: ignore
  return merged


def FindBestMove(
    fen: str, /,
    depth: int = ELO_CATEGORY_TO_PLY['super'],
    engine_path: str = DEFAULT_ENGINE,
    engine_obj: Optional[chess.engine.SimpleEngine] = None) -> Optional[
        tuple[chess.Move, PositionEval]]:
  """Finds the best move for a position (FEN) up to a depth.

  Args:
    fen: FEN string to use
    depth: (default 20 = ELO_CATEGORY_TO_PLY['super']) ply depth to search
    engine_path: (default DEFAULT_ENGINE) the engine path to invoke
    engine_obj: (default None) a open chess.engine.SimpleEngine; if given skips creation/engine_path

  Returns:
    (best_move, PositionEval), where best_move is a chess.Move and see PositionEval for details
  """
  if depth < 4:
    raise ValueError('Chess engine depth must be 5 or larger')
  # take care of checkmate case
  board = chess.Board(fen)
  if board.is_checkmate() or board.is_stalemate():
    return None
  # ask for an analysis from engine
  engine_info: chess.List[chess.engine.InfoDict]
  if engine_obj:
    # call engine: INFO_ALL is to get full data; multipv=1 means only the single best line
    engine_info = engine_obj.analyse(
        board, limit=chess.engine.Limit(depth=depth), info=chess.engine.INFO_ALL, multipv=1)
  else:
    # open Stockfish/engine in UCI mode
    with chess.engine.SimpleEngine.popen_uci(engine_path) as engine:
      engine_info = engine.analyse(
          board, limit=chess.engine.Limit(depth=depth), info=chess.engine.INFO_ALL, multipv=1)
  # check the result is as expected; best move is first move of best line
  if (len(engine_info) != 1 or
      not engine_info[0].get('pv', None) or
      not engine_info[0].get('score', None)):
    raise RuntimeError(f'No principal variation or score returned by engine for FEN: {fen!r}')
  best_move: chess.Move = engine_info[0]['pv'][0]  # type:ignore
  # check if the engine sees a forced mate from the current position
  mate_in: int = 0
  relative_score: chess.engine.Score = engine_info[0]['score'].relative  # type:ignore
  if relative_score.is_mate() and (n_mate := relative_score.mate()):
    # mate_in > 0 => side to move is mating in n_mate moves
    # mate_in < 0 => the opponent is mating in abs(n_mate) moves
    mate_in = n_mate
  score: Optional[int] = relative_score.score()
  return (best_move, PositionEval(
      depth=depth, best=EncodePly(best_move), mate=mate_in, score=0 if score is None else score))


def _WorkerProcessEvalTask(
    worker_n: int, db_readonly: bool, tasks: multiprocessing.queues.Queue,  # type:ignore
    depth: int, engine_path: str, timeout: float, log_dir: str, db_file: str,
    tasks_done: multiprocessing.managers.DictProxy) -> None:  # type:ignore
  """Worker function that runs in a separate process or thread to evaluate chess positions."""
  if not tasks or not engine_path or not log_dir or not os.path.isdir(log_dir):
    raise ValueError('Empty parameters!')
  if depth < ELO_CATEGORY_TO_PLY['club']:
    raise ValueError(f'ply depth should be at least {ELO_CATEGORY_TO_PLY["club"]}')
  # local connection: each thread must have it own
  fen: str
  task: set[str]
  p_hash: str = ''
  p_eval: Optional[tuple[chess.Move, PositionEval]]
  db = PGNData(db_path=db_file, readonly=db_readonly)
  try:
    # only once: open Stockfish/engine in UCI mode, also append to a log file
    with (chess.engine.SimpleEngine.popen_uci(engine_path) as engine,
          open(os.path.join(log_dir, f'worker-{worker_n:02}.logs'),
               'at', encoding='utf-8') as file_obj):
      # main loop: pick up a task and execute it
      file_obj.write(f'\n\nStarting worker thread #{worker_n} @ {base.STR_TIME()}\n\n')
      file_obj.flush()
      while True:
        try:
          task = tasks.get(timeout=timeout)  # type:ignore
          for p_hash in task:                # type:ignore
            if p_hash == _WORKER_SENTINEL_MESSAGE:  # sentinel to stop
              file_obj.write(f'Worker #{worker_n} received sentinel, exiting.\n\n')
              break
            # we have a task: evaluate and save
            position: pawnzobrist.Zobrist = pawnzobrist.ZobristFromHash(p_hash)  # type:ignore
            with base.Timer() as fen_timer:
              fen = db.PositionHashToFEN(position)[0]
            with base.Timer() as engine_timer:
              p_eval = FindBestMove(fen, depth=depth, engine_obj=engine)
            if p_eval:
              db.UpdatePositionEvaluation(position, p_eval[1])
              file_obj.write(
                  f'{p_hash} ({fen} @{fen_timer.readable}) => '
                  f'{p_eval[1]!r} @{engine_timer.readable}\n')
            else:
              file_obj.write(
                  f'{p_hash} ({fen} @{fen_timer.readable}) => None\n')
            tasks_done[worker_n] = tasks_done[worker_n] + 1  # this is only OK because each thread has its own
        except queue.Empty:
          file_obj.write(
              f'Worker #{worker_n} timed out, no tasks available. Exiting. @ {base.STR_TIME()}\n\n')
          break
        except Exception as err:
          file_obj.write(f'Worker #{worker_n} exception @ {base.STR_TIME()}: {err}\n\n')
          raise  # we really don't want to eat this exception up, so we allow the thread to crash
        finally:
          file_obj.flush()
        # check for sentinel
        if p_hash == _WORKER_SENTINEL_MESSAGE:  # sentinel to stop
          break
  finally:
    db.Close()


def RunEvalWorkers(
    num_workers: int, db_readonly: bool, tasks: list[str], timeout: float,
    depth: int, engine_path: str, log_dir: str, db_file: str) -> None:
  """Spawns multiple worker processes to process list of (fen_string, position_hash) tasks.

  Each worker calls WorkerProcessEvalTask(...) in a new process.

  Args:
    num_workers: number of worker threads
    db_readonly: is the DB readonly?
    tasks: list of position hashes to look at
    timeout: seconds until worker timeout
    depth: ply depth to search
    engine_path: the engine path to invoke
    log_dir: the (existing!) path to save log files to
    db_file: the (existing!) file path to the DB to use
  """
  # get number of tasks: unfortunately Queue() can't handle more than ~10000 items
  # so we have to feed them to the queue either individually or in groups
  local: bool = num_workers == 1
  n_tasks: int = len(tasks)
  set_tasks: list[set[str]] = []
  tasks_per_queue_item: int = (n_tasks // 10000) + 1
  eval_queue: multiprocessing.queues.Queue = multiprocessing.Queue()  # type:ignore
  for i in range(0, n_tasks, tasks_per_queue_item):
    new_task: set[str] = set()
    for j in range(tasks_per_queue_item):
      if i + j < n_tasks:
        new_task.add(tasks[i + j])
    eval_queue.put(new_task)  # type:ignore
    set_tasks.append(new_task)
  if local:
    eval_queue.put({_WORKER_SENTINEL_MESSAGE})  # type:ignore
  logging.info('Enqueued %d positions (%d tasks) for engine evaluation', n_tasks, len(set_tasks))
  # create worker processes
  processes: list[multiprocessing.Process] = []
  with multiprocessing.Manager() as manager:
    tasks_done: multiprocessing.managers.DictProxy = manager.dict()  # {worker: count_done}  # type:ignore
    logging.info('Spawning %d engine eval workers with depth %d', num_workers, depth)
    for i in range(num_workers):
      tasks_done[i] = 0
      process_args: tuple[int, bool, multiprocessing.queues.Queue,                            # type:ignore
                          int, str, float, str, str, multiprocessing.managers.DictProxy] = (  # type:ignore
                              i, db_readonly, eval_queue,
                              depth, engine_path, timeout, log_dir, db_file, tasks_done)
      if local:
        _WorkerProcessEvalTask(*process_args)
      else:
        worker_thread = multiprocessing.Process(target=_WorkerProcessEvalTask, args=process_args)  # type:ignore
        processes.append(worker_thread)
    for thread in processes:
      thread.start()
    # monitor queue size
    progress_bar: tqdm.tqdm = tqdm.tqdm(
        total=len(tasks), mininterval=1.0, miniters=1, unit='ev', smoothing=0.4, colour='green')
    last_done: int = 0
    try:
      while not local and (n_tasks - last_done) > num_workers:
        queue_done: int = sum(tasks_done.values())  # type:ignore
        progress_bar.update(queue_done - last_done)
        last_done = queue_done
        time.sleep(1)
    finally:
      progress_bar.close()
    # wait for them to finish or do something else
    for p in processes:
      p.join(timeout)
      if p.is_alive():
        # force the sentinel so they can exit
        eval_queue.put({_WORKER_SENTINEL_MESSAGE})  # type:ignore
    # re-join them
    for p in processes:
      p.join(timeout)
    logging.info('All engine eval workers done')


def _UnzipZipFile(in_file: IO[bytes], out_file: IO[Any]) -> None:
  """Unzips `in_file` to `out_file`. Raises BadZipFile if error."""
  logging.info('Unzipping file as ZIP')
  with zipfile.ZipFile(in_file, 'r') as zip_ref:
    # for simplicity, assume there's only one PGN inside.
    pgn_file_name: str = zip_ref.namelist()[0]
    with zip_ref.open(pgn_file_name) as pgn_file:
      out_file.write(pgn_file.read())


def _UnzipSevenZFile(in_file: str, out_file: IO[Any]) -> None:
  logging.info('Unzipping file as 7z')
  with py7zr.SevenZipFile(in_file, mode='r') as svz_ref:
    files: Optional[dict[str, IO[Any]]] = svz_ref.read()
    if files:
      if len(files) > 1:
        raise NotImplementedError('7z file had more than one file')
      for _, file_obj in files.items():
        out_file.write(file_obj.read())
        break


def ZipFileInMemory(original_path: str) -> bytes:
  """Read disk file and compress it into a ZIP file (with only one file in it) in memory."""
  # read binary data from the original file
  with open(original_path, 'rb') as f:
    file_data: bytes = f.read()
  zip_buffer = io.BytesIO()
  # create a ZIP archive in memory
  with zipfile.ZipFile(zip_buffer, mode='w', compression=zipfile.ZIP_DEFLATED) as zf:
    # The second argument is how it will appear inside the ZIP
    zf.writestr('single_file.bin', file_data)
  # get the raw bytes of the zip file
  return zip_buffer.getvalue()


class PGNCache:
  """PGN cache."""

  @dataclasses.dataclass
  class _Cache:
    """A cache mapping to be saved to disk."""
    files: dict[str, str]  # {URL(lowercase): file_path}

  def __init__(self, cache_dir: str = _PGN_CACHE_DIR, cache_filename: str = 'cache.bin') -> None:
    """Constructor."""
    self._cache_dir: str = cache_dir.strip()
    if not self._cache_dir:
      raise ValueError('Empty cache dir')
    self._cache_file: str = os.path.join(self._cache_dir, cache_filename)
    # check cache directory is there
    if not os.path.exists(self._cache_dir):
      os.makedirs(self._cache_dir)
      logging.info('Created empty PGN cache dir %r', self._cache_dir)
    # load cache file, create if empty
    self._cache: PGNCache._Cache = PGNCache._Cache(files={})
    if os.path.exists(self._cache_file):
      self._cache = base.BinDeSerialize(file_path=self._cache_file)
      logging.info('Loaded cache from %r with %d entries', self._cache_file, len(self._cache.files))
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
    file_path: str = os.path.join(self._cache_dir, f'{hex_hash}.pgn')
    with open(file_path, 'wb') as cached_obj:
      cached_obj.write(file_obj.read())
    self._cache.files[file_url.lower()] = file_path
    base.BinSerialize(self._cache, self._cache_file)
    logging.info('Added URL %r to cache (%r)', file_url, file_path)
    return file_path


class PGNData:
  """A PGN Database for Pawnalyze using SQLite."""

  _TABLE_ORDER: list[str] = [
      'positions', 'games', 'duplicate_games', 'moves',
      'idx_games_positions_hash', 'idx_duplicates_hash', 'idx_destination_hash']

  _TABLES: dict[str, str] = {

      'positions': """
          CREATE TABLE IF NOT EXISTS positions (
              position_hash TEXT PRIMARY KEY CHECK (length(position_hash) = 32),  -- 128 bit Zobrist hex
              flags INTEGER NOT NULL,  -- PositionFlag integer
              extras TEXT NOT NULL,    -- ExtraInsightPositionFlag ','-separated hex set
              engine TEXT,             -- ','-separated hex tuple with PositionEval(depth,move,mate,score)
              game_hashes TEXT         -- ','-separated hex set of game_hash that ended here, if any
          );
      """,

      'games': """
          CREATE TABLE IF NOT EXISTS games (
              game_hash TEXT PRIMARY KEY      CHECK (length(game_hash)         = 64),  -- 256 bit SHA-256 hex
              end_position_hash TEXT NOT NULL CHECK (length(end_position_hash) = 32),  -- 128 bit Zobrist hex
              game_plys TEXT NOT NULL,          -- list of encoded plys as ','-separated hex list; '-' for error games
              game_headers TEXT NOT NULL,       -- JSON dict with game headers
              error_category INTEGER NOT NULL,  -- if error game: ErrorGameCategory integer (0 == no error)
              error_pgn TEXT,                   -- if error game: original PGN
              error_message TEXT,               -- if error game: some sort of error description
              FOREIGN KEY(end_position_hash) REFERENCES positions(position_hash) ON DELETE RESTRICT
          );
      """,

      'idx_games_positions_hash': 'CREATE INDEX IF NOT EXISTS idx_games_positions_hash ON games(end_position_hash);',

      'duplicate_games': """
          CREATE TABLE IF NOT EXISTS duplicate_games (
              game_hash TEXT PRIMARY KEY CHECK (length(game_hash)    = 64),  -- 256 bit SHA-256 hex
              duplicate_of TEXT NOT NULL CHECK (length(duplicate_of) = 64),  -- 256 bit SHA-256 hex
              game_headers TEXT NOT NULL,       -- JSON dict with game headers
              FOREIGN KEY(duplicate_of) REFERENCES games(game_hash) ON DELETE RESTRICT
          );
      """,

      'idx_duplicates_hash': 'CREATE INDEX IF NOT EXISTS idx_duplicates_hash ON duplicate_games(duplicate_of);',

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

  def __init__(self, db_path: str = _PGN_SQL_FILE, readonly: bool = False) -> None:
    """Open or create the SQLite DB.

    Args:
      readonly: (default: False) if True DB will not save data
    """
    self.db_path: str = db_path.strip()
    if not self.db_path:
      raise ValueError('Empty DB path')
    self.db_dir: str = os.path.split(self.db_path)[0]
    if not self.db_dir:
      raise ValueError(f'Empty DB dir for {self.db_path}')
    self._readonly: bool = bool(readonly)
    # check data directory is there
    if not os.path.exists(self.db_dir):
      if self._readonly:
        raise ValueError('No data path and READONLY do not mix')
      os.makedirs(self.db_dir)
      logging.info('Created empty data dir %r', self.db_dir)
    # open DB, create if empty
    exists_db: bool = os.path.exists(self.db_path)
    # self._conn: sqlite3.Connection = sqlite3.connect(
    #     f'file:{self._db_path}{"?mode=ro" if self._readonly else ""}', uri=True)
    self._conn: sqlite3.Connection = sqlite3.connect(self.db_path)
    self._conn.execute('PRAGMA foreign_keys = ON;')  # allow foreign keys to be used
    self._known_hashes: Optional[set[str]] = None    # lazy hashes cache
    if exists_db:
      logging.info(
          'Opening %sSQLite DB in %r', 'READONLY ' if self._readonly else '', self.db_path)
    else:
      if self._readonly:
        raise ValueError('Empty database and READONLY do not mix')
      logging.info('Creating new SQLite DB in %r', self.db_path)
      self._EnsureSchema()
      logging.info('Adding standard chess base position...')
      with self._conn:
        self._InsertPosition(
            STARTING_POSITION_HASH,
            PositionFlag(PositionFlag.WHITE_TO_MOVE), ExtraInsightPositionFlag(0))

  @property
  def is_readonly(self) -> bool:
    """Is the DB readonly?"""
    return self._readonly

  def Close(self) -> None:
    """Close the database connection."""
    self._conn.close()

  def _EnsureSchema(self) -> None:
    """Create tables if they do not exist."""
    if self._readonly:
      return
    if (names := set(PGNData._TABLE_ORDER)) != (tables := set(PGNData._TABLES.keys())):
      raise ValueError(
          f'_TABLE_ORDER should be the same keys in _TABLES: {sorted(names)} versus {sorted(tables)}')
    with self._conn:
      for name in PGNData._TABLE_ORDER:
        logging.info('Creating table %r', name)
        self._conn.execute(PGNData._TABLES[name])

  def DropAllTables(self) -> None:
    """Drop all tables from the database (destructive operation)."""
    if self._readonly:
      return
    with self._conn:
      for name in PGNData._TABLE_ORDER[::-1]:
        logging.info('Deleting table %r', name)
        self._conn.execute(f'DROP TABLE IF EXISTS {name};')
    logging.warning('Dropped all database tables')

  def DeleteDBFile(self) -> None:
    """Closes connection and deletes the entire DB file from disk."""
    if self._readonly:
      return
    self._conn.close()
    if os.path.exists(self.db_path):
      os.remove(self.db_path)
      logging.warning('Deleted database file %r', self.db_path)

  def WipeData(self) -> None:
    """Delete all data and data file."""
    if self._readonly:
      return
    self.DropAllTables()
    self.DeleteDBFile()

  def IsHashInDB(self, game_hash: str) -> bool:
    """Checks if a `game_hash` was in the DB at the beginning of a run."""
    # lazy load of cache
    if self._known_hashes is None:
      self._known_hashes = self.GetAllKnownHashes()
      logging.info('Loaded %d games already parsed into DB...', len(self._known_hashes))
    # lookup
    return game_hash in self._known_hashes

  # POSITIONS TABLE ################################################################################

  def _InsertPosition(
      self, position_hash: pawnzobrist.Zobrist, flags: PositionFlag,
      extras: ExtraInsightPositionFlag, game_hash: Optional[str] = None) -> bool:
    """Insert a position, or update if existing by adding one game. Returns True on new position."""
    # check if position_hash exists
    cursor: sqlite3.Cursor = self._conn.execute(
        'SELECT flags, extras, game_hashes FROM positions WHERE position_hash = ?;',
        (str(position_hash),))
    row: Optional[tuple[int, str, Optional[str]]] = cursor.fetchone()  # primary key == position_hash
    if not row:
      # brand new entry, guaranteed to have only one ExtraInsightPositionFlag & one hash
      if not self._readonly:
        self._conn.execute(
            'INSERT INTO positions (position_hash, flags, extras, game_hashes) VALUES (?, ?, ?, ?)',
            (str(position_hash), flags.value, f'{extras.value:x}', game_hash if game_hash else None))
      return True
    # we already have this position, so we check if flags are consistent and add headers, if any
    if row[0] != flags.value:
      raise ValueError(
          f'Conflicting flags for position {position_hash}: {row[0]} (old) versus {flags} (new)')
    # add extra flags
    row_changed = False
    existing_extras_set: set[str] = set(row[1].split(','))
    if (new_extra := f'{extras.value:x}') not in existing_extras_set:
      existing_extras_set.add(new_extra)
      row_changed = True
    # add extra hashes, if needed
    existing_hashes_set: set[str] = set(row[2].split(',')) if row[2] else set()
    if game_hash:
      if game_hash not in existing_hashes_set:
        existing_hashes_set.add(game_hash)
        row_changed = True
    # save, if needed
    if row_changed and not self._readonly:
      self._conn.execute(
          'UPDATE positions SET extras = ?, game_hashes = ? WHERE position_hash = ?',
          (','.join(sorted(existing_extras_set)),
           ','.join(sorted(existing_hashes_set)), str(position_hash)))
    return False

  def GetPosition(
      self, position_hash: pawnzobrist.Zobrist) -> Optional[
          tuple[PositionFlag, set[ExtraInsightPositionFlag], Optional[PositionEval], set[str]]]:
    """Retrieve the PositionFlag for the given hash. Returns None if not found."""
    cursor: sqlite3.Cursor = self._conn.execute(
        'SELECT flags, extras, engine, game_hashes FROM positions WHERE position_hash = ?;',
        (str(position_hash),))
    row: Optional[tuple[int, str, Optional[str], Optional[str]]] = cursor.fetchone()  # primary key == position_hash
    if row is None:
      return None
    flag = PositionFlag(row[0])
    extras: set[ExtraInsightPositionFlag] = set(
        ExtraInsightPositionFlag(int(e, 16)) for e in row[1].split(','))
    return (flag, extras,
            None if row[2] is None else DecodeEval(row[2]),
            set() if row[3] is None else set(row[3].split(',')))

  def GetPositions(
      self, has_eval: bool, has_game: bool, limit: int = 0) -> Generator[
          tuple[pawnzobrist.Zobrist, PositionFlag, set[ExtraInsightPositionFlag],
                Optional[PositionEval], set[str]], None, None]:
    """Yields `positions` that `has_eval` and `has_game` up to `limit`."""
    cursor: sqlite3.Cursor = self._conn.execute(
        'SELECT position_hash, flags, extras, engine, game_hashes FROM positions WHERE '
        f'engine IS {"NOT " if has_eval else ""}NULL and '
        f'game_hashes IS {"NOT " if has_game else ""}NULL'
        f'{f" LIMIT {limit}" if limit else ""};')
    for p, f, e, s, h in cursor:  # stream results...
      yield (pawnzobrist.ZobristFromHash(p), PositionFlag(f),
             set(ExtraInsightPositionFlag(int(x, 16)) for x in e.split(',')),
             None if s is None else DecodeEval(s),
             set() if h is None else set(h.split(',')))

  def GetPositionsWithGamesOrNot(self) -> tuple[set[str], set[str]]:
    """Return a set{position_hash} for positions with games and set{position_hash} without games."""
    positions_with_games: set[str] = set()
    positions_without_games: set[str] = set()
    cursor: sqlite3.Cursor = self._conn.execute('SELECT position_hash, game_hashes FROM positions')
    for position_hash, game_hashes in cursor:  # stream cursor
      if game_hashes:
        positions_with_games.add(position_hash)
      else:
        positions_without_games.add(position_hash)
    return (positions_with_games, positions_without_games)

  def UpdatePositionEvaluation(
      self, position_hash: pawnzobrist.Zobrist, evaluation: PositionEval) -> None:
    """Update a position setting its engine evaluation. Position must exist previously."""
    if not self._readonly:
      with self._conn:
        self._conn.execute(
            'UPDATE positions SET engine = ? WHERE position_hash = ?',
            (EncodeEval(evaluation), str(position_hash)))

  # GAMES TABLE ####################################################################################

  def _InsertParsedGame(
      self, game_hash: str, end_position_hash: pawnzobrist.Zobrist, game_plys: list[int],
      game_headers: dict[str, str]) -> None:
    """Insert a "successful" game in `game_hash` with `position_hash`, `game_plys`, and `game_headers`."""
    if not self._readonly:
      self._conn.execute("""
          INSERT INTO games(game_hash, end_position_hash, game_plys, game_headers, error_category)
          VALUES(?, ?, ?, ?, ?)
      """, (game_hash, str(end_position_hash), ','.join(f'{p:x}' for p in game_plys),
            json.dumps(game_headers), 0))

  def _InsertErrorGame(
      self, game_hash: str, game_headers: dict[str, str],
      error_category: ErrorGameCategory, error_pgn: str, error_message: str) -> None:
    """Insert an error game entry."""
    if not self._readonly:
      self._conn.execute("""
          INSERT INTO games(game_hash, end_position_hash, game_plys, game_headers,
                            error_category, error_pgn, error_message)
          VALUES(?, ?, ?, ?, ?, ?, ?)
      """, (game_hash, str(STARTING_POSITION_HASH), '-', json.dumps(game_headers),
            error_category.value, error_pgn, error_message))

  def GetGame(self, game_hash: str) -> Optional[
      tuple[pawnzobrist.Zobrist, list[int], dict[str, str],
            ErrorGameCategory, Optional[str], Optional[str]]]:
    """Return game (zobrist, plys, header, err_car, err_pgn, err_message) for game_hash; None if not found."""
    cursor: sqlite3.Cursor = self._conn.execute("""
        SELECT end_position_hash, game_plys, game_headers, error_category, error_pgn, error_message
        FROM games
        WHERE game_hash = ?;
    """, (game_hash,))
    row: Optional[tuple[str, str, str, ErrorGameCategory,
                        Optional[str], Optional[str]]] = cursor.fetchone()  # primary key == game_hash
    if not row:
      return None
    return (pawnzobrist.Zobrist(int(row[0], 16)),
            [] if row[1] == '-' else [int(p, 16) for p in row[1].split(',')],
            json.loads(row[2]), ErrorGameCategory(row[3]), row[4], row[5])

  def SimpleGetHeader(self, game_hash: str) -> dict[str, str]:
    """Get a single header for a single `game_hash`. Raises if not found."""
    row: Optional[tuple[str]] = self._conn.execute(
        'SELECT game_headers FROM games WHERE game_hash = ?', (game_hash,)).fetchone()
    if not row:
      raise ValueError(f'Game not found {game_hash}')
    headers: dict[str, str] = json.loads(row[0])
    return headers

  def GetAllGames(self) -> Generator[
      tuple[str, pawnzobrist.Zobrist, list[int], dict[str, str],
            ErrorGameCategory, Optional[str], Optional[str]], None, None]:
    """Yields all games as (hash, zobrist, plys, header, err_car, err_pgn, err_message)."""
    cursor: sqlite3.Cursor = self._conn.execute("""
        SELECT game_hash, end_position_hash, game_plys, game_headers, error_category, error_pgn, error_message
        FROM games;
    """)
    for h, p, i, d, c, s, m in cursor:  # stream results...
      yield (h, pawnzobrist.Zobrist(int(p, 16)),
             [] if i == '-' else [int(k, 16) for k in i.split(',')],
             json.loads(d), ErrorGameCategory(c), s, m)

  def GetAllGameHashes(self) -> set[str]:
    """Gets all game hashes."""
    cursor: sqlite3.Cursor = self._conn.execute('SELECT game_hash FROM games;')
    return {h[0] for h in cursor}  # stream into set

  def GetAllOKAndErrorGames(self) -> tuple[dict[str, str], set[str]]:
    """"Gets all OK games as a dict {game_hash: end_position} and all error as set {game_hash}."""
    ok_games: dict[str, str] = {}  # {game_hash: end_position}
    error_games: set[str] = set()  # {game_hash}
    cursor: sqlite3.Cursor = self._conn.execute(
        'SELECT game_hash, end_position_hash, error_category FROM games')
    for game_hash, end_position_hash, error_category in cursor:  # stream cursor
      if error_category:
        error_games.add(game_hash)
      else:
        ok_games[game_hash] = end_position_hash
    return (ok_games, error_games)

  # DUPLICATE_GAMES TABLE ##########################################################################

  def _InsertDuplicateGame(
      self, game_hash: str, duplicate_of: str, game_headers: dict[str, str]) -> None:
    """Insert a "duplicate" game in `game_hash` pointing to `duplicate_of` hash. Removes original.

    We remove the row from the original table because:
      1. we know the game has the exact same plies, so the end_position is also the same
      2. we do not duplicate error games, so none of the error fields are needed
      3. because of the above only the hash and header will have the meaningful differences,
         and we copy the headers here first
    """
    if self._readonly:
      logging.info('new duplicate_games(%s, %s, %r)', game_hash, duplicate_of, game_headers)
      logging.info('delete games(%s)', game_hash)
    else:
      self._conn.execute(
          'INSERT OR IGNORE INTO duplicate_games(game_hash, duplicate_of, game_headers) VALUES(?, ?, ?)',
          (game_hash, duplicate_of, json.dumps(game_headers)))
      self._conn.execute('DELETE FROM games WHERE game_hash = ?', (game_hash,))

  def GetDuplicateGame(self, game_hash: str) -> Optional[tuple[str, dict[str, str]]]:
    """Return duplicate for `game_hash` as hash into `games` table; None if not found."""
    cursor: sqlite3.Cursor = self._conn.execute(
        'SELECT duplicate_of, game_headers FROM duplicate_games WHERE game_hash = ?;', (game_hash,))
    row: Optional[tuple[str, str]] = cursor.fetchone()  # primary key == game_hash
    return None if not row else (row[0], json.loads(row[1]))

  def GetDuplicatesOf(self, duplicate_of: str) -> set[str]:
    """Return a set of duplicates `game_hash` for the given actual `game_hash`."""
    cursor: sqlite3.Cursor = self._conn.execute(
        'SELECT game_hash FROM duplicate_games WHERE duplicate_of = ?;', (duplicate_of,))
    return {g[0] for g in cursor.fetchall()}  # non-stream

  def FindTopPrimary(self, game_hash: str) -> str:
    """Follow 'duplicate_of' references to find top-most `game_hash`. If none, return game_hash."""
    while True:
      row: Optional[tuple[str]] = self._conn.execute(
          'SELECT duplicate_of FROM duplicate_games WHERE game_hash = ?', (game_hash,)).fetchone()
      if not row:
        return game_hash  # no further chain, return previous result (or original game_hash)
      # move to next link in the chain
      game_hash = row[0]

  def GetAllDuplicateHashes(self) -> set[str]:
    """Gets all duplicate game hashes."""
    cursor: sqlite3.Cursor = self._conn.execute('SELECT game_hash FROM duplicate_games;')
    return {h[0] for h in cursor}  # stream into set

  def GetDuplicatesDict(self) -> dict[str, str]:
    """Return all duplicates as a dict {game_hash: duplicate_of}."""
    return dict(self._conn.execute('SELECT game_hash, duplicate_of FROM duplicate_games'))  # stream cursor

  def GetAllKnownHashes(self) -> set[str]:
    """Gets all game hashes in DB, all from table `games` and all from `duplicate_games`."""
    all_hashes: set[str] = self.GetAllGameHashes()
    all_hashes.update(self.GetAllDuplicateHashes())
    return all_hashes

  def MergedHeaders(self, game_hash: str) -> dict[str, str]:
    """Returns merged header for main games.game_hash plus all duplicates."""
    # get headers for the main game
    master_header: dict[str, str] = self.SimpleGetHeader(game_hash)
    # find duplicates
    cursor: sqlite3.Cursor = self._conn.execute(
        'SELECT game_headers FROM duplicate_games WHERE duplicate_of = ?', (game_hash,))
    duplicates: list[tuple[str]] = cursor.fetchall()
    # merge headers from each duplicate
    for (dup_game_header,) in duplicates:
      master_header = _MergeGameHeaders(master_header, json.loads(dup_game_header))
    # all merged
    return master_header

  # MOVES TABLE ####################################################################################

  def _InsertMove(
      self, from_hash: pawnzobrist.Zobrist, ply: int, to_hash: pawnzobrist.Zobrist) -> None:
    """Insert an edge from `from_hash` with move `ply` leading to `to_hash`."""
    if not self._readonly:
      self._conn.execute(
          'INSERT OR IGNORE INTO moves(from_position_hash, ply, to_position_hash) VALUES(?, ?, ?)',
          (str(from_hash), ply, str(to_hash)))

  def GetMoves(
      self, position_hash: pawnzobrist.Zobrist) -> list[tuple[int, pawnzobrist.Zobrist]]:
    """Return a list of (ply, to_position_hash) for the given from_position_hash."""
    cursor: sqlite3.Cursor = self._conn.execute("""
        SELECT ply, to_position_hash
        FROM moves
        WHERE from_position_hash = ?;
    """, (str(position_hash),))
    return [(ply, pawnzobrist.Zobrist(int(z, 16))) for ply, z in cursor.fetchall()]  # non-stream

  ##################################################################################################

  def GetPositionsWithMultipleBranches(
      self, filter_engine_done: bool = False) -> dict[int, dict[str, dict[int, str]]]:
    """Find `moves` with >1 ply in them as {len_plys, {from_position_hash: {ply: to_position_hash}}}."""
    with self._conn:
      if filter_engine_done:
        cursor: sqlite3.Cursor = self._conn.execute("""
            SELECT m.from_position_hash, m.ply, m.to_position_hash
            FROM moves AS m
            JOIN positions AS p ON p.position_hash = m.from_position_hash
            WHERE p.engine IS NULL
              AND m.from_position_hash IN (
                SELECT from_position_hash
                FROM moves
                GROUP BY from_position_hash
                HAVING COUNT(*) > 1
              )
        """)
      else:
        cursor: sqlite3.Cursor = self._conn.execute("""
            SELECT from_position_hash, ply, to_position_hash
            FROM moves
            WHERE from_position_hash IN (
              SELECT from_position_hash
              FROM moves
              GROUP BY from_position_hash
              HAVING COUNT(*) > 1
            )
        """)
    # first gather from_position_hash -> {ply: to_position_hash}
    node_map: dict[str, dict[int, str]] = {}
    for f_h, ply, t_h in cursor:  # stream cursor
      plys: dict[int, str] = node_map.setdefault(f_h, {})
      plys[ply] = t_h
    # group them by the count of distinct plies
    result: dict[int, dict[str, dict[int, str]]] = {}
    for f_h, plys in node_map.items():
      branch_count: int = len(plys)  # how many different plies from this position
      if not plys or branch_count < 2:
        raise ValueError('Query should never return a row with only one ply')
      result.setdefault(branch_count, {})[f_h] = plys
    return result

  def PositionHashToFEN(
      self, position_zob: pawnzobrist.Zobrist) -> tuple[str, chess.Board, list[int]]:
    """Reconstruct a FEN string for the given `position_hash`. Returns None if no path to root."""
    # if this is already the starting position, return the standard FEN directly
    start_hash = str(STARTING_POSITION_HASH)
    board = chess.Board(STANDARD_CHESS_FEN)
    position_hash = str(position_zob)
    if position_hash == start_hash:
      return (STANDARD_CHESS_FEN, board, [])
    # trace backwards through `moves` until we reach STARTING_POSITION_HASH
    reverse_moves: list[int] = []  # moves in backward order from the target up to the start
    current_hash: str = position_hash
    visited: set[str] = set()
    while current_hash != start_hash:
      if current_hash in visited:
        raise RuntimeError(f'Detected cycle or repeated position: {position_hash}/{current_hash}')
      visited.add(current_hash)
      # find a row in `moves` where `to_position_hash == current_hash`
      row: Optional[tuple[str, int]] = self._conn.execute(
          'SELECT from_position_hash, ply FROM moves WHERE to_position_hash = ? LIMIT 1',
          (current_hash,)).fetchone()
      if not row:
        raise RuntimeError(f'No parent found: {position_hash}/{current_hash}')
      from_hash, ply_int = row
      reverse_moves.append(ply_int)
      current_hash = from_hash
    # apply those moves forward from a fresh board
    actual_moves: list[int] = reverse_moves[::-1]
    for ply_int in actual_moves:
      move: chess.Move = DecodePly(ply_int)
      if not board.is_legal(move):
        raise RuntimeError(f'Illegal move reconstructing {position_hash}: {move}, {board.fen()}')
      board.push(move)
    # the resulting board should match the `position_hash`, so check!
    board_hash: pawnzobrist.Zobrist = pawnzobrist.ZobristFromBoard(board)
    if position_hash != str(board_hash):
      raise RuntimeError(f'Position mismatch {position_hash}: {str(board_hash)}, {board.fen()}')
    return (board.fen(), board, actual_moves)

  def LoadGame(self, original_pgn: str, game: chess.pgn.Game) -> tuple[str, int, int]:
    """Loads game into database. Returns (game_hash, plys, new_positions)."""
    # get game_hash and check if we already know this exact game PGN
    game_hash: str = base.BytesHexHash(original_pgn.encode(encoding='utf-8', errors='replace'))
    # first check in hashes cache
    if self.IsHashInDB(game_hash):
      return (game_hash, 0, 0)  # found in cache
    # we don't have this game, so prepare to parse it
    n_ply: int = 0
    encoded_plys: list[int] = []
    new_count: int = 0
    board: Optional[chess.Board] = None
    z_current: pawnzobrist.Zobrist = STARTING_POSITION_HASH
    game_headers: dict[str, str] = _GameMinimalHeaders(game)
    try:
      with self._conn:  # make all game operations inside one transaction
        n_ply_checkmate: tuple[int, str] = (0, '')
        flags: PositionFlag = PositionFlag(PositionFlag.WHITE_TO_MOVE)
        extras: ExtraInsightPositionFlag = ExtraInsightPositionFlag(0)
        # hashes cache was loaded at startup, so we still have to re-check before we process/insert
        if (done_game := self.GetGame(game_hash)):
          # we already did this game; nothing to do
          return (game_hash, len(done_game[1]), 0)
        # test for games we don't know the result of
        _FixGameResultHeaderOrRaise(original_pgn, game, game_headers)
        # go over the moves
        for n_ply, san, encoded_ply, (z_previous, z_current), board, flags, extras in IterateGame(game):
          # insert position and move
          encoded_plys.append(encoded_ply)
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
        self._InsertParsedGame(game_hash, z_current, encoded_plys, game_headers)
        return (game_hash, n_ply, new_count)
    except InvalidGameError as err:
      # some sort of error in game, insert as error game
      with self._conn:
        self._InsertErrorGame(game_hash, game_headers, err.category, original_pgn, err.args[0])
      # log if error not exactly empty|non-standard (these are plentiful and not interesting to see)
      if err.category not in {ErrorGameCategory.EMPTY_GAME, ErrorGameCategory.NON_STANDARD_CHESS}:
        logging.warning('%s\n%r', str(err), original_pgn)
      return (game_hash, 0, 0)

  def DeduplicateGames(
      self, soft_ply_threshold: int,
      hard_ply_threshold: int) -> list[tuple[str, str, dict[str, str]]]:
    """Deduplicate games.

    Finds positions in `positions` table that have multiple game_hashes and attempts
    to identify duplicates among those games. Duplicates are recorded in `duplicate_games`.

    Args:
      soft_ply_threshold: games with >= ply depth than this are easier to declare duplicates
      hard_ply_threshold: games with >= ply depth than this are always considered duplicates

    Returns:
      A list of position_hash strings that had merges done.
    """
    # Step 1: Find `positions` that have multiple game_hashes
    cursor: sqlite3.Cursor = self._conn.execute("""
        SELECT position_hash, game_hashes
        FROM positions
        WHERE game_hashes IS NOT NULL
          AND game_hashes LIKE '%,%'
    """)
    starting_position: str = str(STARTING_POSITION_HASH)
    rows: list[tuple[str, str]] = cursor.fetchall()
    # we'll need to skip game_hashes already in duplicate_games:
    known_duplicates: set[str] = self.GetAllDuplicateHashes()
    merges_done: list[tuple[str, str, dict[str, str]]] = []  # the return with info on merges we'll do
    # go over the games that have ending positions with more than one hash
    for position_hash, g_hashes_str in rows:
      if position_hash == starting_position:
        continue  # skip root position
      # parse game_hashes by comma
      all_gs: list[str] = [h for h in g_hashes_str.split(',') if h not in known_duplicates]
      if len(all_gs) < 2:
        continue  # after skipping known duplicates, might not have actual multiples
      # Step 2: fetch `games` for each and compare them to find which are duplicates among them
      # we'll store groups of duplicates and produce a unified header for each group
      potential_games: list[tuple[str, list[int], dict[str, str]]] = []
      for gh in all_gs:
        g_info: Optional[tuple[pawnzobrist.Zobrist, list[int], dict[str, str], ErrorGameCategory,
                               Optional[str], Optional[str]]] = self.GetGame(gh)
        if not g_info:
          raise ValueError(f'Game {gh!r} not found!')
        _, plys_list, game_headers, err_cat, _, _ = g_info
        if err_cat.value:
          continue  # error games do not come into consideration
        potential_games.append((gh, plys_list, game_headers))
      # Step 2b: form groups of duplicates
      visited: set[str] = set()
      duplicates_found: list[set[str]] = []  # [(set_of_hashes, merged_header)]
      for i in range(len(potential_games)):  # pylint: disable=consider-using-enumerate
        gh_a, plys_a, head_a = potential_games[i]
        if gh_a in visited:
          continue
        visited.add(gh_a)
        # We'll keep "duplicates" for gh_a in one group
        group: set[str] = {gh_a}
        for j in range(i + 1, len(potential_games)):
          gh_b, plys_b, head_b = potential_games[j]
          if gh_b in visited:
            continue
          # Step 2b: decide if these two are duplicates
          if _IsDuplicateGame(
              plys_a, head_a, plys_b, head_b, soft_ply_threshold, hard_ply_threshold):
            visited.add(gh_b)
            group.add(gh_b)
        if len(group) > 1:
          duplicates_found.append(group)
      # Step 3: store duplicates
      for group in duplicates_found:
        # pick a stable primary, e.g. lexicographically smallest
        sorted_list: list[str] = sorted(group)
        primary_hash: str = sorted_list[0]
        with self._conn:
          # unify the chain if 'primary_hash' itself is a duplicate of something else
          top_primary: str = self.FindTopPrimary(primary_hash)
          # now link every other hash in the group to top_primary
          for dgh in group:
            if dgh == top_primary:
              continue
            # read game from DB
            d_game: Optional[tuple[pawnzobrist.Zobrist, list[int], dict[str, str], ErrorGameCategory,
                                   Optional[str], Optional[str]]] = self.GetGame(dgh)
            if d_game is None:
              raise ValueError(f'Duplicate game {dgh!r} not found!')
            # record in duplicate_games
            self._InsertDuplicateGame(dgh, top_primary, d_game[2])
            merges_done.append((dgh, top_primary, d_game[2]))
            known_duplicates.add(dgh)
    # end
    return merges_done

  def CachedLoadFromURL(self, url: str, cache: Optional[PGNCache]) -> Generator[
      tuple[int, str, int, str, chess.pgn.Game], None, None]:
    """Load a source from URL into DB, cached, yields (n, hash, plys, pgn, game)."""
    pgn_path: Optional[str] = cache.GetCachedPath(url) if cache else None
    with tempfile.NamedTemporaryFile() as out_file:
      if pgn_path is None:
        # we don't have the PGN yet: open the URL, download file
        logging.info('Downloading URL %r', url)
        with urllib.request.urlopen(url) as response, tempfile.NamedTemporaryFile() as raw_file:
          raw_file.write(response.read())
          raw_file.seek(0)
          # open the temporary file as a ZIP archive
          try:
            _UnzipZipFile(raw_file, out_file)
          except zipfile.BadZipFile as err:
            if 'not a zip' not in str(err):
              raise
            # try to unzip as 7z
            _UnzipSevenZFile(raw_file.name, out_file)
        # now we have a file name, so keep it
        pgn_path = out_file.name
        if cache:
          cache.AddCachedFile(url, out_file)  # type:ignore
      # we have the PGN as a file in "pgn_path" for sure here
      for game_count, game_hash, plys, pgn, game in self.LoadFromDisk(pgn_path):
        yield (game_count, game_hash, plys, pgn, game)

  def LoadFromDisk(self, file_path: str) -> Generator[
      tuple[int, str, int, str, chess.pgn.Game], None, None]:
    """Load a source from local file, yields (n, hash, plys, pgn, game)."""
    game_count: int = 0
    ply_count: int = 0
    last_ply: int = 0
    node_count: int = 0
    actual_game_count: int = 0
    actual_loaded_count: int = 0
    processing_start: float = time.time()
    last_time: float = 0.0
    logging.info('Downloading local file %r', file_path)
    for game_count, (pgn, game, n_line) in enumerate(_GamesFromLargePGN(file_path)):
      # we are building the DB
      game_hash: str
      plys: int
      nodes: int
      game_hash, plys, nodes = self.LoadGame(pgn, game)
      actual_game_count += 1 if nodes else 0
      ply_count += plys
      actual_loaded_count += plys if nodes else 0  # assume 0 nodes means we already have that block
      node_count += nodes
      if not game_count % _PRINT_EVERY_N and game_count:  # by games loaded
        # here we log by game count (not line), sporadically, to complement the line info
        now: float = time.time()
        total_time: float = now - processing_start
        delta: float = now - last_time
        logging.info(
            'Loaded %d lines, %d games (%d plys, %d nodes, %0.1f%%) '
            '%0.1f games/s %0.1f plys/s = %s per M-games',
            n_line, game_count, ply_count, node_count,
            (100.0 * (actual_loaded_count - node_count) / actual_loaded_count) if actual_loaded_count else 0,
            _PRINT_EVERY_N / delta, (actual_loaded_count - last_ply) / delta,
            base.HumanizedSeconds(1000000.0 * total_time / actual_game_count) if actual_game_count else '?')
        last_time = now
        last_ply = actual_loaded_count
      yield (game_count, game_hash, plys, pgn, game)

  def PrintDatabaseCheck(self) -> Generator[str, None, None]:
    """
    Does a complete check of the database, prints stats and any errors.

    Steps:
      (1) read all games, sorting them into ok_games vs error_games
      (2) get all duplicate games
      (3) gather positions that do/don't have games
      (4) traverse the moves tree from the root to find unreachable or invalid leaf positions
    """
    # (1) read all games from `games`
    yield 'Reading all games...'
    ok_games, error_games = self.GetAllOKAndErrorGames()
    yield f'{len(ok_games)} ok games and {len(error_games)} error games in database'
    yield ''
    # (2) get all duplicates from `duplicate_games`, do some basic checks
    yield 'Reading all duplicate games...'
    dup_map: dict[str, str] = self.GetDuplicatesDict()
    dup_keys: set[str] = set(dup_map.keys())
    dup_ok_repeats: set[str] = dup_keys.intersection(ok_games.keys())
    dup_err_repeats: set[str] = dup_keys.intersection(error_games)
    yield f'{len(dup_map)} duplicate games'
    if dup_ok_repeats:
      yield (f'==> Found {len(dup_ok_repeats)} keys both in OK `games` and `duplicate_games`: '
             f'{dup_ok_repeats!r}')
    if dup_err_repeats:
      yield (f'==> Found {len(dup_err_repeats)} keys both in error `games` and `duplicate_games`: '
             f'{dup_err_repeats!r}')
    yield ''
    # (3) gather positions that do/don't have games
    yield 'Reading all positions games...'
    positions_with_games, positions_without_games = self.GetPositionsWithGamesOrNot()
    n_all_positions: int = len(positions_with_games) + len(positions_without_games)
    yield (f'{n_all_positions} total positions, '
           f'{len(positions_with_games)} with game endings, '
           f'{len(positions_without_games)} en-passant (no game ended here)')
    yield ''
    # (4) BFS/DFS from STARTING_POSITION_HASH to find reachable positions
    # we'll consider the move graph from positions -> moves -> positions
    yield 'Visiting all positions...'
    visited_positions: set[str] = set()
    to_visit: set[str] = {str(STARTING_POSITION_HASH)}
    leaf_with_no_games: set[str] = set()
    progress_bar: tqdm.tqdm = tqdm.tqdm(
        total=n_all_positions, mininterval=1.0, miniters=100,
        unit='pos', smoothing=0.4, colour='green')
    while to_visit:
      current: str = to_visit.pop()
      if current in visited_positions:
        continue
      visited_positions.add(current)
      # get next moves
      rows: list[tuple[int, str]] = self._conn.execute(
          'SELECT ply, to_position_hash FROM moves WHERE from_position_hash = ?',
          (current,)).fetchall()
      progress_bar.update(1)
      for _, to_hash in rows:
        if to_hash not in visited_positions:
          to_visit.add(to_hash)
      if not rows:
        # this is a (end-)leaf node, so it should have a game...
        if current not in positions_with_games:
          leaf_with_no_games.add(current)
    progress_bar.close()
    # now we know which positions are reachable from the standard start
    unreachable_positions: set[str] = (
        positions_with_games.union(positions_without_games) - visited_positions)
    if unreachable_positions:
      yield (f'==> Found {len(unreachable_positions)} unreachable positions: '
             f'{unreachable_positions!r}')
    if leaf_with_no_games:
      yield (f'==> Found {len(leaf_with_no_games)} leaf positions with no games: '
             f'{leaf_with_no_games!r}')
    yield ''
