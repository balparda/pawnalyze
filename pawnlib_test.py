#!/usr/bin/python3 -bb
#
# Copyright 2025 Daniel Balparda (balparda@gmail.com)
# GNU General Public License v3 (http://www.gnu.org/licenses/gpl-3.0.txt)
#
# pylint: disable=invalid-name,protected-access
"""pawnlib.py unittest."""

import logging
import os.path
# import pdb
import shutil
import tempfile
import unittest
from unittest import mock

import chess

from baselib import base
from pawnalyze import pawnlib
from pawnalyze import pawnenginemoves
from pawnalyze import pawnzobrist

__author__ = 'balparda@gmail.com (Daniel Balparda)'
__version__ = (1, 0)


_TEST_PGN_PATH: str = os.path.join(os.path.dirname(__file__), 'test-pgn/')
_TEST_PGN_1: str = os.path.join(_TEST_PGN_PATH, 'test-file-1.pgn')


class TestPawnLib(unittest.TestCase):
  """Tests for pawnlib.py."""

  @mock.patch('pawnlib.urllib.request.urlopen')
  def setUp(self, mock_open: mock.MagicMock) -> None:  # pylint: disable=arguments-differ
    # Create a temporary directory for DB, create DB in this temp directory
    self.maxDiff = None  # no limit to diff output
    self.test_dir: str = tempfile.mkdtemp(prefix='pawn_lib_test_')
    try:
      self.db_dir: str = os.path.join(self.test_dir, 'db-dir')
      self.test_db_path: str = os.path.join(self.db_dir, 'pawnalyze-test.db')
      self.log_file: str = os.path.join(self.db_dir, 'worker-00.logs')
      self.db = pawnlib.PGNData(db_path=self.test_db_path, readonly=False)
      self.cache_dir: str = os.path.join(self.test_dir, 'cache-dir')
      self.cache = pawnlib.PGNCache(cache_dir=self.cache_dir)
      mock_open.return_value.__enter__.return_value.read.return_value = pawnlib.ZipFileInMemory(_TEST_PGN_1)
      games: dict[str, int] = {}  # {hame_hash: n_plys}
      for _, game_hash, plys, _, _ in self.db.CachedLoadFromURL('http://source.url.for.test/', self.cache):
        games[game_hash] = plys
      mock_open.assert_called_once_with('http://source.url.for.test/')
      self.assertDictEqual(games, _GAMES_LOADED)
      self.assertListEqual(self.db.DeduplicateGames(20, 40), _DUPLICATES_FOUND)
      with mock.patch('pawnlib.time.time') as mock_time:
        mock_time.return_value = 123456789
        pawnenginemoves.AddEvaluationsOfPositionsToDB(
            self.db, 1, pawnlib.ELO_CATEGORY_TO_PLY['club'], 1000, 'stockfish', True)
        pawnenginemoves.AddEvaluationsOfRepeatPositionsToDB(
            self.db, 1, pawnlib.ELO_CATEGORY_TO_PLY['club'], 1000, 'stockfish')
      self.assertTrue(os.path.exists(self.log_file))
      with open(self.log_file, 'rt', encoding='utf-8') as log_obj:
        log_lines: list[str] = list(log_obj)
      self.assertEqual(''.join(log_lines), _THREAD_LOGS)
    except Exception:
      shutil.rmtree(self.test_dir)
      print(f'Cleaned temp dir {self.test_dir}')
      raise

  def tearDown(self) -> None:
    # close DB and remove temp directory
    self.db.WipeData()
    print('Wiped DB')
    if os.path.exists(self.test_dir):
      try:
        shutil.rmtree(self.test_dir)
        print(f'Cleaned temp dir {self.test_dir}')
      except OSError as err:
        print(f'Could not remove temp dir {self.test_dir}: {err}')

  def test_PositionEval(self) -> None:
    """Test."""
    engine = pawnlib.PositionEval(depth=4, best=816, mate=-1, score=79)
    self.assertEqual(pawnlib.EncodeEval(engine), '4,330,-1,4f')
    self.assertDictEqual(pawnlib.DecodeEval('4,330,-1,4f'), engine)
    self.assertEqual(pawnlib.DecodePly(816).uci(), 'a2a3')
    self.assertEqual(pawnlib.EncodePly(chess.Move(chess.A2, chess.A3)), 816)
    self.assertEqual(
        pawnlib.EncodePly(chess.Move(chess.A2, chess.A3, promotion=chess.QUEEN)), 5000816)

  def test_DBReads(self) -> None:
    """Test."""
    self.maxDiff = None  # no limit to diff output
    self.assertEqual(
        self.db.GetPosition(pawnzobrist.STARTING_POSITION_HASH),
        (pawnlib.PositionFlag(1), {pawnlib.ExtraInsightPositionFlag(0)},
         {'best': 1228, 'depth': 4, 'mate': 0, 'score': 33}, set()))
    self.assertIsNone(self.db.GetPosition(pawnzobrist.Zobrist(123)))
    self.assertEqual(len(list(self.db.GetAllGames())), 11)
    self.assertEqual(
        self.db.GetDuplicateGame('79da399d406bf1e492109403a3d34eda93620cfe3fc013b1b9b0562c27e2a268'),
        _DUPLICATES_FOUND[1][1:])
    self.assertSetEqual(
        self.db.GetDuplicatesOf('418073579eabddec4b5a9c740b59f00b24842b6cbf2921f569ce7100b37d01b1'),
        {'79da399d406bf1e492109403a3d34eda93620cfe3fc013b1b9b0562c27e2a268'})
    self.assertDictEqual(
        self.db.MergedHeaders('418073579eabddec4b5a9c740b59f00b24842b6cbf2921f569ce7100b37d01b1'),
        _MERGED_HEADER)
    self.assertListEqual(
        [(i, str(j)) for i, j in self.db.GetMoves(pawnzobrist.STARTING_POSITION_HASH)],
        [(917, '7504991f9af1fa6d6c0862176b8fbd51'),
         (1127, '4e76061f723e19eab31025ada516d321')])

  def test_PrintDatabaseCheck(self) -> None:
    """Test."""
    self.assertListEqual(list(self.db.PrintDatabaseCheck()), _DB_CHECK_OUTPUT)


_GAMES_LOADED: dict[str, int] = {
    # {hame_hash: n_plys} for every game in the test file
    '23b041ff638186b6c969577a8c59772c1c1435de24b644a45a15b58faaa8dda3': 0,
    '418073579eabddec4b5a9c740b59f00b24842b6cbf2921f569ce7100b37d01b1': 94,
    '50caf9c441022cd5a876bff4479bf165a2b3a90b0df755a2309ea479a97e25a5': 0,
    '574e26d3c87508cd3ec98a1fcc05b1815431e738efc6944c0f1274190b524a0b': 4,
    '8b9eceb7b6800c43caacc5d577fb626011605485301265d1466bc812ef5dd81e': 0,
    'a6ec2fc46ebe2bbf78407803ead96de277b94368fb332fabe8df9caa84c3bac7': 4,
    '79da399d406bf1e492109403a3d34eda93620cfe3fc013b1b9b0562c27e2a268': 94,
    'cef4c3abfea7d4beed86942a335eb1c72c5db5deb9a30762e025e6182927af27': 75,
    'd2e70b8aa5283c95601827c6b5a6d3badac3a7080ade26fe681cc4614ca0942d': 43,
    'd7aefc371ec6cfc6b7e9afbbb0e0d1e5f78d1332a526dd3fbeed9511116501be': 4,
    'da6966ed026112e63143ee0f617e6292ecaa57b5ae05eff6f093e7ed48610e41': 83,
    'ee87c754866ef9c3d4b331ada12f0e741d1924cd91204196b84d223fb7b87008': 0,
    'f3444b58a7656fcab9f94c2f8155c867abbf2535dc171d453e7a9d1eabe9be60': 4
}

_DUPLICATES_FOUND: list[tuple[str, str, dict[str, str]]] = [
    (
        'f3444b58a7656fcab9f94c2f8155c867abbf2535dc171d453e7a9d1eabe9be60',
        '574e26d3c87508cd3ec98a1fcc05b1815431e738efc6944c0f1274190b524a0b',
        {
            'black': 'Bbb Ccc',
            'date': '2010.06.23',
            'event': 'basic',
            'result': '1/2-1/2',
            'white': 'Aaa',
        },
    ),
    (
        '79da399d406bf1e492109403a3d34eda93620cfe3fc013b1b9b0562c27e2a268',
        '418073579eabddec4b5a9c740b59f00b24842b6cbf2921f569ce7100b37d01b1',
        {
            'black': 'other',
            'blackelo': '2725',
            'date': '2021.06.24',
            'eco': 'D97',
            'event': 'Fujitsu Siemens Giants - duplicate',
            'eventdate': '2000.06.22',
            'result': '0-1',
            'round': '7',
            'site': 'Frankfurt',
            'white': 'another',
            'whiteelo': '2851',
        },
    ),
]

_MERGED_HEADER: dict[str, str] = {
    'black': 'Leko, Peter | other',
    'blackelo': '2725',
    'date': '2000.06.24 | 2021.06.24',
    'eco': 'D97',
    'event': 'Fujitsu Siemens Giants | Fujitsu Siemens Giants - duplicate',
    'eventdate': '2000.06.22',
    'issues': {  # type: ignore
        "black: 'Leko, Peter'/'other'",
        "date: '2000.06.24'/'2021.06.24'",
        "event: 'Fujitsu Siemens Giants'/'Fujitsu Siemens Giants - duplicate'",
        "white: 'Kasparov, Garry'/'another'",
    },
    'result': '0-1',
    'round': '7',
    'site': 'Frankfurt',
    'white': 'Kasparov, Garry | another',
    'whiteelo': '2851',
}

_DB_CHECK_OUTPUT: list[str] = [
    'Reading all games...',
    '7 ok games and 4 error games in database',
    '',
    'Reading all duplicate games...',
    '2 duplicate games',
    '',
    'Reading all positions games...',
    '294 total positions, 5 with game endings, 289 en-passant (no game ended here)',
    '',
    'Visiting all positions...',
    '',
]

_THREAD_LOGS: str = """

Starting worker thread #0 @ 1973/Nov/29-21:33:09-UTC

f8da2a698ef19a7c05871ed2045f7f57 (8/8/p5R1/7k/6Qp/1B1P4/P6K/8 b - - 2 42 @0 secs) => None
2d83f8797c048132b55f995992b8452a (rnbqkbnr/p1pp1ppp/1p2p3/8/2PP4/8/PP2PPPP/RNBQKBNR w KQkq - 0 3 @0 secs) => {'depth': 4, 'best': 816, 'mate': 0, 'score': 79} @0 secs
d570901e9a9c20a053f9055dafc06232 (3b4/p6p/1p2k1p1/1P2Pp2/PB3P2/5K1P/8/8 b - - 0 38 @0 secs) => {'depth': 4, 'best': 4638, 'mate': 0, 'score': 8} @0 secs
8c3bdda626e109fee32e88ed1aec1dbb (8/8/3knK2/p2p4/5r2/1P1B4/P2R4/8 w - - 6 48 @0 secs) => {'depth': 4, 'best': 1937, 'mate': 0, 'score': -132} @0 secs
31c2be39c829ed1333a06ba59ba042c5 (n1Q1kb1r/3npppp/8/3qP3/5P2/8/1P3P1P/2B1K2R b Kk - 1 22 @0 secs) => None
Worker #0 received sentinel, exiting.



Starting worker thread #0 @ 1973/Nov/29-21:33:09-UTC

4e76061f723e19eab31025ada516d321 (rnbqkbnr/pppppppp/8/8/3P4/8/PPP1PPPP/RNBQKBNR b KQkq - 0 1 @0 secs) => {'depth': 4, 'best': 5135, 'mate': 0, 'score': -21} @0 secs
3a653200920c4adb562ceff24c6af691 (rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1 @0 secs) => {'depth': 4, 'best': 1228, 'mate': 0, 'score': 33} @0 secs
Worker #0 received sentinel, exiting.

"""


SUITE: unittest.TestSuite = unittest.TestLoader().loadTestsFromTestCase(TestPawnLib)


if __name__ == '__main__':
  logging.basicConfig(level=logging.INFO, format=base.LOG_FORMAT)  # set this as default
  unittest.main()
