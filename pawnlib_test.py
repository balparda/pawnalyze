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
        [(i, str(j)) for i, _, j in self.db.GetChildMoves(pawnzobrist.STARTING_POSITION_HASH)],
        [(917, '7504991f9af1fa6d6c0862176b8fbd51'),
         (1127, '4e76061f723e19eab31025ada516d321')])

  def test_PrintMovesDB(self) -> None:
    """Test."""
    self.maxDiff = None  # no limit to diff output
    db_str: str = '\n'.join(i for _, i in self.db.PrintMovesDB())
    self.assertEqual(db_str, _DB_STR)
    db_str = '\n'.join(i for _, i in self.db.PrintMovesDB(
        start_position=pawnzobrist.ZobristFromHash('27d97b250cb8541d2a50d9464f9cea0e'),
        expand_games=False))
    self.assertEqual(db_str, _DB_STR_MINOR)

  def test_PrintDatabaseCheck(self) -> None:
    """Test."""
    self.assertListEqual(list(self.db.PrintDatabaseCheck()), _DB_CHECK_OUTPUT)

  def test_ECO(self) -> None:
    """Test."""
    self.maxDiff = None  # no limit to diff output
    eco = pawnlib.ECO()
    self.assertIsNone(eco.Get(pawnzobrist.ZobristFromHash('31c2be39c829ed1333a06ba59ba042c5')))
    b3: pawnzobrist.Zobrist = pawnzobrist.ZobristFromHash('7504991f9af1fa6d6c0862176b8fbd51')
    self.assertEqual(
        eco.Get(b3),
        pawnlib.ECOEntry('A01', 'Nimzo-Larsen Attack', '1. b3',
                         [pawnlib.ECOMove('b3', 917, b3, pawnlib.PositionFlag(2))]))
    self.assertGreater(len(eco._db), 3500)  # ECO DB is known to have >3500 entries # type:ignore


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

f8da2a698ef19a7c05871ed2045f7f57 (8/8/p5R1/7k/6Qp/1B1P4/P6K/8 b - - 2 42) → None
2d83f8797c048132b55f995992b8452a (rnbqkbnr/p1pp1ppp/1p2p3/8/2PP4/8/PP2PPPP/RNBQKBNR w KQkq - 0 3) → 4/a3/0.79 @0 secs
d570901e9a9c20a053f9055dafc06232 (3b4/p6p/1p2k1p1/1P2Pp2/PB3P2/5K1P/8/8 b - - 0 38) → 4/g5/0.08 @0 secs
8c3bdda626e109fee32e88ed1aec1dbb (8/8/3knK2/p2p4/5r2/1P1B4/P2R4/8 w - - 6 48) → 4/Bf5/-1.3 @0 secs
31c2be39c829ed1333a06ba59ba042c5 (n1Q1kb1r/3npppp/8/3qP3/5P2/8/1P3P1P/2B1K2R b Kk - 1 22) → None
Worker #0 received sentinel, exiting.



Starting worker thread #0 @ 1973/Nov/29-21:33:09-UTC

4e76061f723e19eab31025ada516d321 (rnbqkbnr/pppppppp/8/8/3P4/8/PPP1PPPP/RNBQKBNR b KQkq - 0 1) → 4/d5/-0.21 @0 secs
3a653200920c4adb562ceff24c6af691 (rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1) → 4/e4/0.33 @0 secs
Worker #0 received sentinel, exiting.

"""

_DB_STR: str = """\
3a653200920c4adb562ceff24c6af691: * → b3,d4 WHITE_TO_MOVE [] 4/e4/0.33
7504991f9af1fa6d6c0862176b8fbd51: b3 (A01/Nimzo-Larsen Attack) → c5 BLACK_TO_MOVE [] *
2df4b95dc52e6b0f4c2376731ee92e06: b3,c5 (A01/Nimzo-Larsen Attack: English Variation) → Bb2 WHITE_TO_MOVE [] *
7bcb7531ea97c1062d20ce69d194b320: b3,c5,Bb2 → Nc6 BLACK_TO_MOVE [] *
76606e23bacd0ad5e840def37d4d4b61: b3,c5,Bb2,Nc6 → g3 WHITE_TO_MOVE [] *
1d60ead626ebb49075855dec80352ce0: b3,c5,Bb2,Nc6,g3 → d6 BLACK_TO_MOVE [] *
1348e3166951cf54014059e70720df83: b3,c5,Bb2,Nc6,g3,d6 → Bg2 WHITE_TO_MOVE [] *
b39439565a7b53c5b4bc68d20208ca64: b3,c5,Bb2,Nc6,g3,d6,Bg2 → Nf6 BLACK_TO_MOVE [] *
e7b6ad9b401ce25a022d5c75552228b2: b3,c5,Bb2,Nc6,g3,d6,Bg2,Nf6 → c4 WHITE_TO_MOVE [] *
dfa5fd558109be2fa7537bce01528a74: b3,c5,Bb2,Nc6,g3,d6,Bg2,Nf6,c4 → a6 BLACK_TO_MOVE [] *
767d60349397944c1c524654eff9a928: b3,c5,Bb2,Nc6,g3,d6,Bg2,Nf6,c4,a6 → Nc3 WHITE_TO_MOVE [] *
f2e6e9ab4500425f62932198bd40353b: b3,c5,Bb2,Nc6,g3,d6,Bg2,Nf6,c4,a6,Nc3 → e5 BLACK_TO_MOVE [] *
6bfbbd54ca049461ca144ef4298f417c: b3,c5,Bb2,Nc6,g3,d6,Bg2,Nf6,c4,a6,Nc3,e5 → d3 WHITE_TO_MOVE [] *
d258350cfc6f2d49e508cbc01f7c2159: b3,c5,Bb2,Nc6,g3,d6,Bg2,Nf6,c4,a6,Nc3,e5,d3 → Nd4 BLACK_TO_MOVE [] *
00cf44a4893ce02dbe373135cd833d0f: b3,c5,Bb2,Nc6,g3,d6,Bg2,Nf6,c4,a6,Nc3,e5,d3,Nd4 → e3 WHITE_TO_MOVE [] *
b757dcb30cc49a36c26eaf6db6b0b42b: b3,c5,Bb2,Nc6,g3,d6,Bg2,Nf6,c4,a6,Nc3,e5,d3,Nd4,e3 → Bg4 BLACK_TO_MOVE [] *
5be433ab19fa1270a3ea11097630a41d: b3,c5,Bb2,Nc6,g3,d6,Bg2,Nf6,c4,a6,Nc3,e5,d3,Nd4,e3,Bg4 → Qd2 WHITE_TO_MOVE [] *
1fc8caf0f92f19a6c2d5cd4c0bbcb62d: b3,c5,Bb2,Nc6,g3,d6,Bg2,Nf6,c4,a6,Nc3,e5,d3,Nd4,e3,Bg4,Qd2 → Nf5 BLACK_TO_MOVE [] *
566e15a9fd7829c64b2fc25094ac147f: b3,c5,Bb2,Nc6,g3,d6,Bg2,Nf6,c4,a6,Nc3,e5,d3,Nd4,e3,Bg4,Qd2,Nf5 → Nge2 WHITE_TO_MOVE [] *
0d78f380cdacf3e1dbe16c4e4df636e4: b3,c5,Bb2,Nc6,g3,d6,Bg2,Nf6,c4,a6,Nc3,e5,d3,Nd4,e3,Bg4,Qd2,Nf5,Nge2 → Bxe2 BLACK_TO_MOVE [] *
9e24890bdbe026419950e79180bd2dbf: b3,c5,Bb2,Nc6,g3,d6,Bg2,Nf6,c4,a6,Nc3,e5,d3,Nd4,e3,Bg4,Qd2,Nf5,Nge2,Bxe2 → Qxe2 WHITE_TO_MOVE [] *
a7f89e1f0ddb5a7951b6299ecffbb7aa: b3,c5,Bb2,Nc6,g3,d6,Bg2,Nf6,c4,a6,Nc3,e5,d3,Nd4,e3,Bg4,Qd2,Nf5,Nge2,Bxe2,Qxe2 → g6 BLACK_TO_MOVE [] *
7d2e5e6fb17ea145a4fabc299e44c022: b3,c5,Bb2,Nc6,g3,d6,Bg2,Nf6,c4,a6,Nc3,e5,d3,Nd4,e3,Bg4,Qd2,Nf5,Nge2,Bxe2,Qxe2,g6 → Bxb7 WHITE_TO_MOVE [] *
e40c5294d085077ef730eba2e675b10d: b3,c5,Bb2,Nc6,g3,d6,Bg2,Nf6,c4,a6,Nc3,e5,d3,Nd4,e3,Bg4,Qd2,Nf5,Nge2,Bxe2,Qxe2,g6,Bxb7 → Rb8 BLACK_TO_MOVE [] *
724b7cdad9196231b72063f7bd602667: b3,c5,Bb2,Nc6,g3,d6,Bg2,Nf6,c4,a6,Nc3,e5,d3,Nd4,e3,Bg4,Qd2,Nf5,Nge2,Bxe2,Qxe2,g6,Bxb7,Rb8 → Bc6+ WHITE_TO_MOVE [] *
7bb76c5b1248eff3fffa6870c2303a24: b3,c5,Bb2,Nc6,g3,d6,Bg2,Nf6,c4,a6,Nc3,e5,d3,Nd4,e3,Bg4,Qd2,Nf5,Nge2,Bxe2,Qxe2,g6,Bxb7,Rb8,Bc6+ → Nd7 CHECK|BLACK_TO_MOVE [] *
656d82721911542def6f2ce482c1af3a: b3,c5,Bb2,Nc6,g3,d6,Bg2,Nf6,c4,a6,Nc3,e5,d3,Nd4,e3,Bg4,Qd2,Nf5,Nge2,Bxe2,Qxe2,g6,Bxb7,Rb8,Bc6+,Nd7 → O-O WHITE_TO_MOVE [] *
2754b11aa71fc9434400a41f86ce811b: b3,c5,Bb2,Nc6,g3,d6,Bg2,Nf6,c4,a6,Nc3,e5,d3,Nd4,e3,Bg4,Qd2,Nf5,Nge2,Bxe2,Qxe2,g6,Bxb7,Rb8,Bc6+,Nd7,O-O → Bg7 BLACK_TO_MOVE [] *
5fc966e81b651128c491640ac15824ec: b3,c5,Bb2,Nc6,g3,d6,Bg2,Nf6,c4,a6,Nc3,e5,d3,Nd4,e3,Bg4,Qd2,Nf5,Nge2,Bxe2,Qxe2,g6,Bxb7,Rb8,Bc6+,Nd7,O-O,Bg7 → Bg2 WHITE_TO_MOVE [] *
942e9a7cf5bed8dc59e474c37149325d: b3,c5,Bb2,Nc6,g3,d6,Bg2,Nf6,c4,a6,Nc3,e5,d3,Nd4,e3,Bg4,Qd2,Nf5,Nge2,Bxe2,Qxe2,g6,Bxb7,Rb8,Bc6+,Nd7,O-O,Bg7,Bg2 → O-O BLACK_TO_MOVE [] *
68a6300080231970141517711e76d60f: b3,c5,Bb2,Nc6,g3,d6,Bg2,Nf6,c4,a6,Nc3,e5,d3,Nd4,e3,Bg4,Qd2,Nf5,Nge2,Bxe2,Qxe2,g6,Bxb7,Rb8,Bc6+,Nd7,O-O,Bg7,Bg2,O-O → Nd5 WHITE_TO_MOVE [] *
f27fbe5fe4c246178d62a3965af552bf: b3,c5,Bb2,Nc6,g3,d6,Bg2,Nf6,c4,a6,Nc3,e5,d3,Nd4,e3,Bg4,Qd2,Nf5,Nge2,Bxe2,Qxe2,g6,Bxb7,Rb8,Bc6+,Nd7,O-O,Bg7,Bg2,O-O,Nd5 → Nb6 BLACK_TO_MOVE [] *
2f4f80f95d8c7d000d3fe91dd4aef5a8: b3,c5,Bb2,Nc6,g3,d6,Bg2,Nf6,c4,a6,Nc3,e5,d3,Nd4,e3,Bg4,Qd2,Nf5,Nge2,Bxe2,Qxe2,g6,Bxb7,Rb8,Bc6+,Nd7,O-O,Bg7,Bg2,O-O,Nd5,Nb6 → Nxb6 WHITE_TO_MOVE [] *
aefc615f08a9897bdf2d5987fa6f0b3a: b3,c5,Bb2,Nc6,g3,d6,Bg2,Nf6,c4,a6,Nc3,e5,d3,Nd4,e3,Bg4,Qd2,Nf5,Nge2,Bxe2,Qxe2,g6,Bxb7,Rb8,Bc6+,Nd7,O-O,Bg7,Bg2,O-O,Nd5,Nb6,Nxb6 → Rxb6 BLACK_TO_MOVE [] *
3c9f6d90b905c2b172cc0fbfc5c18aeb: b3,c5,Bb2,Nc6,g3,d6,Bg2,Nf6,c4,a6,Nc3,e5,d3,Nd4,e3,Bg4,Qd2,Nf5,Nge2,Bxe2,Qxe2,g6,Bxb7,Rb8,Bc6+,Nd7,O-O,Bg7,Bg2,O-O,Nd5,Nb6,Nxb6,Rxb6 → Bh3 WHITE_TO_MOVE [] *
4f2f7c548f5749e2d06be0832c606fd6: b3,c5,Bb2,Nc6,g3,d6,Bg2,Nf6,c4,a6,Nc3,e5,d3,Nd4,e3,Bg4,Qd2,Nf5,Nge2,Bxe2,Qxe2,g6,Bxb7,Rb8,Bc6+,Nd7,O-O,Bg7,Bg2,O-O,Nd5,Nb6,Nxb6,Rxb6,Bh3 → Qf6 BLACK_TO_MOVE [] *
2fafe9ad0eb888bdc350961852f25100: b3,c5,Bb2,Nc6,g3,d6,Bg2,Nf6,c4,a6,Nc3,e5,d3,Nd4,e3,Bg4,Qd2,Nf5,Nge2,Bxe2,Qxe2,g6,Bxb7,Rb8,Bc6+,Nd7,O-O,Bg7,Bg2,O-O,Nd5,Nb6,Nxb6,Rxb6,Bh3,Qf6 → f4 WHITE_TO_MOVE [] *
5283c93d5cd736696f086929eb55bc4a: b3,c5,Bb2,Nc6,g3,d6,Bg2,Nf6,c4,a6,Nc3,e5,d3,Nd4,e3,Bg4,Qd2,Nf5,Nge2,Bxe2,Qxe2,g6,Bxb7,Rb8,Bc6+,Nd7,O-O,Bg7,Bg2,O-O,Nd5,Nb6,Nxb6,Rxb6,Bh3,Qf6,f4 → Rb4 BLACK_TO_MOVE [] *
b257d971a799fdf0afb878ccc69cc475: b3,c5,Bb2,Nc6,g3,d6,Bg2,Nf6,c4,a6,Nc3,e5,d3,Nd4,e3,Bg4,Qd2,Nf5,Nge2,Bxe2,Qxe2,g6,Bxb7,Rb8,Bc6+,Nd7,O-O,Bg7,Bg2,O-O,Nd5,Nb6,Nxb6,Rxb6,Bh3,Qf6,f4,Rb4 → fxe5 WHITE_TO_MOVE [] *
29e626b1116e5d980ac12a1846fc6b65: b3,c5,Bb2,Nc6,g3,d6,Bg2,Nf6,c4,a6,Nc3,e5,d3,Nd4,e3,Bg4,Qd2,Nf5,Nge2,Bxe2,Qxe2,g6,Bxb7,Rb8,Bc6+,Nd7,O-O,Bg7,Bg2,O-O,Nd5,Nb6,Nxb6,Rxb6,Bh3,Qf6,f4,Rb4,fxe5 → dxe5 BLACK_TO_MOVE [] *
06eb60a3718919db39f2e39b1dcc60bb: b3,c5,Bb2,Nc6,g3,d6,Bg2,Nf6,c4,a6,Nc3,e5,d3,Nd4,e3,Bg4,Qd2,Nf5,Nge2,Bxe2,Qxe2,g6,Bxb7,Rb8,Bc6+,Nd7,O-O,Bg7,Bg2,O-O,Nd5,Nb6,Nxb6,Rxb6,Bh3,Qf6,f4,Rb4,fxe5,dxe5 → e4 WHITE_TO_MOVE [] *
504e5c5e973d95df5acf5bb35226479b: b3,c5,Bb2,Nc6,g3,d6,Bg2,Nf6,c4,a6,Nc3,e5,d3,Nd4,e3,Bg4,Qd2,Nf5,Nge2,Bxe2,Qxe2,g6,Bxb7,Rb8,Bc6+,Nd7,O-O,Bg7,Bg2,O-O,Nd5,Nb6,Nxb6,Rxb6,Bh3,Qf6,f4,Rb4,fxe5,dxe5,e4 → Qe7 BLACK_TO_MOVE [] *
652e92168cc24a69d2e9cafad1c5e129: b3,c5,Bb2,Nc6,g3,d6,Bg2,Nf6,c4,a6,Nc3,e5,d3,Nd4,e3,Bg4,Qd2,Nf5,Nge2,Bxe2,Qxe2,g6,Bxb7,Rb8,Bc6+,Nd7,O-O,Bg7,Bg2,O-O,Nd5,Nb6,Nxb6,Rxb6,Bh3,Qf6,f4,Rb4,fxe5,dxe5,e4,Qe7 → exf5 WHITE_TO_MOVE [] *
ece31f67d15949cdca5dc63e45ea5194: b3,c5,Bb2,Nc6,g3,d6,Bg2,Nf6,c4,a6,Nc3,e5,d3,Nd4,e3,Bg4,Qd2,Nf5,Nge2,Bxe2,Qxe2,g6,Bxb7,Rb8,Bc6+,Nd7,O-O,Bg7,Bg2,O-O,Nd5,Nb6,Nxb6,Rxb6,Bh3,Qf6,f4,Rb4,fxe5,dxe5,e4,Qe7,exf5 → Kh8 BLACK_TO_MOVE [] *
3c5991e3607a9a9d99b297304644b886: b3,c5,Bb2,Nc6,g3,d6,Bg2,Nf6,c4,a6,Nc3,e5,d3,Nd4,e3,Bg4,Qd2,Nf5,Nge2,Bxe2,Qxe2,g6,Bxb7,Rb8,Bc6+,Nd7,O-O,Bg7,Bg2,O-O,Nd5,Nb6,Nxb6,Rxb6,Bh3,Qf6,f4,Rb4,fxe5,dxe5,e4,Qe7,exf5,Kh8 → Rae1 WHITE_TO_MOVE [] *
34db8cbf211a33c36c72f5cf5e9b8813: b3,c5,Bb2,Nc6,g3,d6,Bg2,Nf6,c4,a6,Nc3,e5,d3,Nd4,e3,Bg4,Qd2,Nf5,Nge2,Bxe2,Qxe2,g6,Bxb7,Rb8,Bc6+,Nd7,O-O,Bg7,Bg2,O-O,Nd5,Nb6,Nxb6,Rxb6,Bh3,Qf6,f4,Rb4,fxe5,dxe5,e4,Qe7,exf5,Kh8,Rae1 → Rbb8 BLACK_TO_MOVE [] *
0a6cd6952cb77511accae76efb84c210: b3,c5,Bb2,Nc6,g3,d6,Bg2,Nf6,c4,a6,Nc3,e5,d3,Nd4,e3,Bg4,Qd2,Nf5,Nge2,Bxe2,Qxe2,g6,Bxb7,Rb8,Bc6+,Nd7,O-O,Bg7,Bg2,O-O,Nd5,Nb6,Nxb6,Rxb6,Bh3,Qf6,f4,Rb4,fxe5,dxe5,e4,Qe7,exf5,Kh8,Rae1,Rbb8 → f6 WHITE_TO_MOVE [] *
db3282e95e57a622ba37d06eebece9eb: b3,c5,Bb2,Nc6,g3,d6,Bg2,Nf6,c4,a6,Nc3,e5,d3,Nd4,e3,Bg4,Qd2,Nf5,Nge2,Bxe2,Qxe2,g6,Bxb7,Rb8,Bc6+,Nd7,O-O,Bg7,Bg2,O-O,Nd5,Nb6,Nxb6,Rxb6,Bh3,Qf6,f4,Rb4,fxe5,dxe5,e4,Qe7,exf5,Kh8,Rae1,Rbb8,f6 → Bxf6 BLACK_TO_MOVE [] *
bcb96e5a489b32868cb7fc9a7a2be707: b3,c5,Bb2,Nc6,g3,d6,Bg2,Nf6,c4,a6,Nc3,e5,d3,Nd4,e3,Bg4,Qd2,Nf5,Nge2,Bxe2,Qxe2,g6,Bxb7,Rb8,Bc6+,Nd7,O-O,Bg7,Bg2,O-O,Nd5,Nb6,Nxb6,Rxb6,Bh3,Qf6,f4,Rb4,fxe5,dxe5,e4,Qe7,exf5,Kh8,Rae1,Rbb8,f6,Bxf6 → Rxf6 WHITE_TO_MOVE [] *
5f6b39d21bf6f70866a4c8662969ca20: b3,c5,Bb2,Nc6,g3,d6,Bg2,Nf6,c4,a6,Nc3,e5,d3,Nd4,e3,Bg4,Qd2,Nf5,Nge2,Bxe2,Qxe2,g6,Bxb7,Rb8,Bc6+,Nd7,O-O,Bg7,Bg2,O-O,Nd5,Nb6,Nxb6,Rxb6,Bh3,Qf6,f4,Rb4,fxe5,dxe5,e4,Qe7,exf5,Kh8,Rae1,Rbb8,f6,Bxf6,Rxf6 → Qxf6 BLACK_TO_MOVE [] *
795f061d1daa84bef884801e545d5331: b3,c5,Bb2,Nc6,g3,d6,Bg2,Nf6,c4,a6,Nc3,e5,d3,Nd4,e3,Bg4,Qd2,Nf5,Nge2,Bxe2,Qxe2,g6,Bxb7,Rb8,Bc6+,Nd7,O-O,Bg7,Bg2,O-O,Nd5,Nb6,Nxb6,Rxb6,Bh3,Qf6,f4,Rb4,fxe5,dxe5,e4,Qe7,exf5,Kh8,Rae1,Rbb8,f6,Bxf6,Rxf6,Qxf6 → Bxe5 WHITE_TO_MOVE [] *
d9092859287f436597d1c84bc417156a: b3,c5,Bb2,Nc6,g3,d6,Bg2,Nf6,c4,a6,Nc3,e5,d3,Nd4,e3,Bg4,Qd2,Nf5,Nge2,Bxe2,Qxe2,g6,Bxb7,Rb8,Bc6+,Nd7,O-O,Bg7,Bg2,O-O,Nd5,Nb6,Nxb6,Rxb6,Bh3,Qf6,f4,Rb4,fxe5,dxe5,e4,Qe7,exf5,Kh8,Rae1,Rbb8,f6,Bxf6,Rxf6,Qxf6,Bxe5 → Qxe5 BLACK_TO_MOVE [] *
69f8410eb33297193f2d066f3694e9c9: b3,c5,Bb2,Nc6,g3,d6,Bg2,Nf6,c4,a6,Nc3,e5,d3,Nd4,e3,Bg4,Qd2,Nf5,Nge2,Bxe2,Qxe2,g6,Bxb7,Rb8,Bc6+,Nd7,O-O,Bg7,Bg2,O-O,Nd5,Nb6,Nxb6,Rxb6,Bh3,Qf6,f4,Rb4,fxe5,dxe5,e4,Qe7,exf5,Kh8,Rae1,Rbb8,f6,Bxf6,Rxf6,Qxf6,Bxe5,Qxe5 → Qxe5+ WHITE_TO_MOVE [] *
0ef3f502cf03502ac00c6bc246fe6c93: b3,c5,Bb2,Nc6,g3,d6,Bg2,Nf6,c4,a6,Nc3,e5,d3,Nd4,e3,Bg4,Qd2,Nf5,Nge2,Bxe2,Qxe2,g6,Bxb7,Rb8,Bc6+,Nd7,O-O,Bg7,Bg2,O-O,Nd5,Nb6,Nxb6,Rxb6,Bh3,Qf6,f4,Rb4,fxe5,dxe5,e4,Qe7,exf5,Kh8,Rae1,Rbb8,f6,Bxf6,Rxf6,Qxf6,Bxe5,Qxe5,Qxe5+ → Kg8 CHECK|BLACK_TO_MOVE [] *
de497b867e20837a93e33acc45508581: b3,c5,Bb2,Nc6,g3,d6,Bg2,Nf6,c4,a6,Nc3,e5,d3,Nd4,e3,Bg4,Qd2,Nf5,Nge2,Bxe2,Qxe2,g6,Bxb7,Rb8,Bc6+,Nd7,O-O,Bg7,Bg2,O-O,Nd5,Nb6,Nxb6,Rxb6,Bh3,Qf6,f4,Rb4,fxe5,dxe5,e4,Qe7,exf5,Kh8,Rae1,Rbb8,f6,Bxf6,Rxf6,Qxf6,Bxe5,Qxe5,Qxe5+,Kg8 → Bg2 WHITE_TO_MOVE [] *
adf96a42487208293144d5f0acf160bc: b3,c5,Bb2,Nc6,g3,d6,Bg2,Nf6,c4,a6,Nc3,e5,d3,Nd4,e3,Bg4,Qd2,Nf5,Nge2,Bxe2,Qxe2,g6,Bxb7,Rb8,Bc6+,Nd7,O-O,Bg7,Bg2,O-O,Nd5,Nb6,Nxb6,Rxb6,Bh3,Qf6,f4,Rb4,fxe5,dxe5,e4,Qe7,exf5,Kh8,Rae1,Rbb8,f6,Bxf6,Rxf6,Qxf6,Bxe5,Qxe5,Qxe5+,Kg8,Bg2 → Rbe8 BLACK_TO_MOVE [] *
7e123e8a70d897b8683dd54031f783c5: b3,c5,Bb2,Nc6,g3,d6,Bg2,Nf6,c4,a6,Nc3,e5,d3,Nd4,e3,Bg4,Qd2,Nf5,Nge2,Bxe2,Qxe2,g6,Bxb7,Rb8,Bc6+,Nd7,O-O,Bg7,Bg2,O-O,Nd5,Nb6,Nxb6,Rxb6,Bh3,Qf6,f4,Rb4,fxe5,dxe5,e4,Qe7,exf5,Kh8,Rae1,Rbb8,f6,Bxf6,Rxf6,Qxf6,Bxe5,Qxe5,Qxe5+,Kg8,Bg2,Rbe8 → Qxe8 WHITE_TO_MOVE [] *
13e0eb584ef2aaa4e35336d4de3dbd9f: b3,c5,Bb2,Nc6,g3,d6,Bg2,Nf6,c4,a6,Nc3,e5,d3,Nd4,e3,Bg4,Qd2,Nf5,Nge2,Bxe2,Qxe2,g6,Bxb7,Rb8,Bc6+,Nd7,O-O,Bg7,Bg2,O-O,Nd5,Nb6,Nxb6,Rxb6,Bh3,Qf6,f4,Rb4,fxe5,dxe5,e4,Qe7,exf5,Kh8,Rae1,Rbb8,f6,Bxf6,Rxf6,Qxf6,Bxe5,Qxe5,Qxe5+,Kg8,Bg2,Rbe8,Qxe8 → Rxe8 BLACK_TO_MOVE [] *
12510e7d067808715ef92d4f0a6412d7: b3,c5,Bb2,Nc6,g3,d6,Bg2,Nf6,c4,a6,Nc3,e5,d3,Nd4,e3,Bg4,Qd2,Nf5,Nge2,Bxe2,Qxe2,g6,Bxb7,Rb8,Bc6+,Nd7,O-O,Bg7,Bg2,O-O,Nd5,Nb6,Nxb6,Rxb6,Bh3,Qf6,f4,Rb4,fxe5,dxe5,e4,Qe7,exf5,Kh8,Rae1,Rbb8,f6,Bxf6,Rxf6,Qxf6,Bxe5,Qxe5,Qxe5+,Kg8,Bg2,Rbe8,Qxe8,Rxe8 → Rxe8+ WHITE_TO_MOVE [] *
8137d3336591eceb56e7233d3253e1bd: b3,c5,Bb2,Nc6,g3,d6,Bg2,Nf6,c4,a6,Nc3,e5,d3,Nd4,e3,Bg4,Qd2,Nf5,Nge2,Bxe2,Qxe2,g6,Bxb7,Rb8,Bc6+,Nd7,O-O,Bg7,Bg2,O-O,Nd5,Nb6,Nxb6,Rxb6,Bh3,Qf6,f4,Rb4,fxe5,dxe5,e4,Qe7,exf5,Kh8,Rae1,Rbb8,f6,Bxf6,Rxf6,Qxf6,Bxe5,Qxe5,Qxe5+,Kg8,Bg2,Rbe8,Qxe8,Rxe8,Rxe8+ → Kg7 CHECK|BLACK_TO_MOVE [] *
02472586e1d2ad4313ea6996c44c4bfe: b3,c5,Bb2,Nc6,g3,d6,Bg2,Nf6,c4,a6,Nc3,e5,d3,Nd4,e3,Bg4,Qd2,Nf5,Nge2,Bxe2,Qxe2,g6,Bxb7,Rb8,Bc6+,Nd7,O-O,Bg7,Bg2,O-O,Nd5,Nb6,Nxb6,Rxb6,Bh3,Qf6,f4,Rb4,fxe5,dxe5,e4,Qe7,exf5,Kh8,Rae1,Rbb8,f6,Bxf6,Rxf6,Qxf6,Bxe5,Qxe5,Qxe5+,Kg8,Bg2,Rbe8,Qxe8,Rxe8,Rxe8+,Kg7 → Bd5 WHITE_TO_MOVE [] *
7369a1082485ef24fcf7daff1e05f754: b3,c5,Bb2,Nc6,g3,d6,Bg2,Nf6,c4,a6,Nc3,e5,d3,Nd4,e3,Bg4,Qd2,Nf5,Nge2,Bxe2,Qxe2,g6,Bxb7,Rb8,Bc6+,Nd7,O-O,Bg7,Bg2,O-O,Nd5,Nb6,Nxb6,Rxb6,Bh3,Qf6,f4,Rb4,fxe5,dxe5,e4,Qe7,exf5,Kh8,Rae1,Rbb8,f6,Bxf6,Rxf6,Qxf6,Bxe5,Qxe5,Qxe5+,Kg8,Bg2,Rbe8,Qxe8,Rxe8,Rxe8+,Kg7,Bd5 → h5 BLACK_TO_MOVE [] *
d31f98237ef0fe87eda07804f658babe: b3,c5,Bb2,Nc6,g3,d6,Bg2,Nf6,c4,a6,Nc3,e5,d3,Nd4,e3,Bg4,Qd2,Nf5,Nge2,Bxe2,Qxe2,g6,Bxb7,Rb8,Bc6+,Nd7,O-O,Bg7,Bg2,O-O,Nd5,Nb6,Nxb6,Rxb6,Bh3,Qf6,f4,Rb4,fxe5,dxe5,e4,Qe7,exf5,Kh8,Rae1,Rbb8,f6,Bxf6,Rxf6,Qxf6,Bxe5,Qxe5,Qxe5+,Kg8,Bg2,Rbe8,Qxe8,Rxe8,Rxe8+,Kg7,Bd5,h5 → b4 WHITE_TO_MOVE [] *
20c6b7aa461cc0a7430102890b3f9e25: b3,c5,Bb2,Nc6,g3,d6,Bg2,Nf6,c4,a6,Nc3,e5,d3,Nd4,e3,Bg4,Qd2,Nf5,Nge2,Bxe2,Qxe2,g6,Bxb7,Rb8,Bc6+,Nd7,O-O,Bg7,Bg2,O-O,Nd5,Nb6,Nxb6,Rxb6,Bh3,Qf6,f4,Rb4,fxe5,dxe5,e4,Qe7,exf5,Kh8,Rae1,Rbb8,f6,Bxf6,Rxf6,Qxf6,Bxe5,Qxe5,Qxe5+,Kg8,Bg2,Rbe8,Qxe8,Rxe8,Rxe8+,Kg7,Bd5,h5,b4 → cxb4 BLACK_TO_MOVE [] *
43ca4c3b5036b1ce52951f2e0f5b69ad: b3,c5,Bb2,Nc6,g3,d6,Bg2,Nf6,c4,a6,Nc3,e5,d3,Nd4,e3,Bg4,Qd2,Nf5,Nge2,Bxe2,Qxe2,g6,Bxb7,Rb8,Bc6+,Nd7,O-O,Bg7,Bg2,O-O,Nd5,Nb6,Nxb6,Rxb6,Bh3,Qf6,f4,Rb4,fxe5,dxe5,e4,Qe7,exf5,Kh8,Rae1,Rbb8,f6,Bxf6,Rxf6,Qxf6,Bxe5,Qxe5,Qxe5+,Kg8,Bg2,Rbe8,Qxe8,Rxe8,Rxe8+,Kg7,Bd5,h5,b4,cxb4 → c5 WHITE_TO_MOVE [] *
9b5b89dca3029da8d9ce7d8a25e03b20: b3,c5,Bb2,Nc6,g3,d6,Bg2,Nf6,c4,a6,Nc3,e5,d3,Nd4,e3,Bg4,Qd2,Nf5,Nge2,Bxe2,Qxe2,g6,Bxb7,Rb8,Bc6+,Nd7,O-O,Bg7,Bg2,O-O,Nd5,Nb6,Nxb6,Rxb6,Bh3,Qf6,f4,Rb4,fxe5,dxe5,e4,Qe7,exf5,Kh8,Rae1,Rbb8,f6,Bxf6,Rxf6,Qxf6,Bxe5,Qxe5,Qxe5+,Kg8,Bg2,Rbe8,Qxe8,Rxe8,Rxe8+,Kg7,Bd5,h5,b4,cxb4,c5 → b3 BLACK_TO_MOVE [] *
74a2eeac74d79c039e4fce973f972f09: b3,c5,Bb2,Nc6,g3,d6,Bg2,Nf6,c4,a6,Nc3,e5,d3,Nd4,e3,Bg4,Qd2,Nf5,Nge2,Bxe2,Qxe2,g6,Bxb7,Rb8,Bc6+,Nd7,O-O,Bg7,Bg2,O-O,Nd5,Nb6,Nxb6,Rxb6,Bh3,Qf6,f4,Rb4,fxe5,dxe5,e4,Qe7,exf5,Kh8,Rae1,Rbb8,f6,Bxf6,Rxf6,Qxf6,Bxe5,Qxe5,Qxe5+,Kg8,Bg2,Rbe8,Qxe8,Rxe8,Rxe8+,Kg7,Bd5,h5,b4,cxb4,c5,b3 → Bxb3 WHITE_TO_MOVE [] *
37cf43d64c5c5283b18a5f0201e5ee00: b3,c5,Bb2,Nc6,g3,d6,Bg2,Nf6,c4,a6,Nc3,e5,d3,Nd4,e3,Bg4,Qd2,Nf5,Nge2,Bxe2,Qxe2,g6,Bxb7,Rb8,Bc6+,Nd7,O-O,Bg7,Bg2,O-O,Nd5,Nb6,Nxb6,Rxb6,Bh3,Qf6,f4,Rb4,fxe5,dxe5,e4,Qe7,exf5,Kh8,Rae1,Rbb8,f6,Bxf6,Rxf6,Qxf6,Bxe5,Qxe5,Qxe5+,Kg8,Bg2,Rbe8,Qxe8,Rxe8,Rxe8+,Kg7,Bd5,h5,b4,cxb4,c5,b3,Bxb3 → f5 BLACK_TO_MOVE [] *
e69160fe6dbf88160657513bea41a3ec: b3,c5,Bb2,Nc6,g3,d6,Bg2,Nf6,c4,a6,Nc3,e5,d3,Nd4,e3,Bg4,Qd2,Nf5,Nge2,Bxe2,Qxe2,g6,Bxb7,Rb8,Bc6+,Nd7,O-O,Bg7,Bg2,O-O,Nd5,Nb6,Nxb6,Rxb6,Bh3,Qf6,f4,Rb4,fxe5,dxe5,e4,Qe7,exf5,Kh8,Rae1,Rbb8,f6,Bxf6,Rxf6,Qxf6,Bxe5,Qxe5,Qxe5+,Kg8,Bg2,Rbe8,Qxe8,Rxe8,Rxe8+,Kg7,Bd5,h5,b4,cxb4,c5,b3,Bxb3,f5 → c6 WHITE_TO_MOVE [] *
0e45c344c51f52d0c25b99969814861a: b3,c5,Bb2,Nc6,g3,d6,Bg2,Nf6,c4,a6,Nc3,e5,d3,Nd4,e3,Bg4,Qd2,Nf5,Nge2,Bxe2,Qxe2,g6,Bxb7,Rb8,Bc6+,Nd7,O-O,Bg7,Bg2,O-O,Nd5,Nb6,Nxb6,Rxb6,Bh3,Qf6,f4,Rb4,fxe5,dxe5,e4,Qe7,exf5,Kh8,Rae1,Rbb8,f6,Bxf6,Rxf6,Qxf6,Bxe5,Qxe5,Qxe5+,Kg8,Bg2,Rbe8,Qxe8,Rxe8,Rxe8+,Kg7,Bd5,h5,b4,cxb4,c5,b3,Bxb3,f5,c6 → f4 BLACK_TO_MOVE [] *
53f905258367ec42a4bc52a0acd8ae24: b3,c5,Bb2,Nc6,g3,d6,Bg2,Nf6,c4,a6,Nc3,e5,d3,Nd4,e3,Bg4,Qd2,Nf5,Nge2,Bxe2,Qxe2,g6,Bxb7,Rb8,Bc6+,Nd7,O-O,Bg7,Bg2,O-O,Nd5,Nb6,Nxb6,Rxb6,Bh3,Qf6,f4,Rb4,fxe5,dxe5,e4,Qe7,exf5,Kh8,Rae1,Rbb8,f6,Bxf6,Rxf6,Qxf6,Bxe5,Qxe5,Qxe5+,Kg8,Bg2,Rbe8,Qxe8,Rxe8,Rxe8+,Kg7,Bd5,h5,b4,cxb4,c5,b3,Bxb3,f5,c6,f4 → c7 WHITE_TO_MOVE [] *
35f2b68632045953ad3e20fbc511cc5f: b3,c5,Bb2,Nc6,g3,d6,Bg2,Nf6,c4,a6,Nc3,e5,d3,Nd4,e3,Bg4,Qd2,Nf5,Nge2,Bxe2,Qxe2,g6,Bxb7,Rb8,Bc6+,Nd7,O-O,Bg7,Bg2,O-O,Nd5,Nb6,Nxb6,Rxb6,Bh3,Qf6,f4,Rb4,fxe5,dxe5,e4,Qe7,exf5,Kh8,Rae1,Rbb8,f6,Bxf6,Rxf6,Qxf6,Bxe5,Qxe5,Qxe5+,Kg8,Bg2,Rbe8,Qxe8,Rxe8,Rxe8+,Kg7,Bd5,h5,b4,cxb4,c5,b3,Bxb3,f5,c6,f4,c7 → fxg3 BLACK_TO_MOVE [] *
88f2928f7094faed2ef44f98191e0d9a: b3,c5,Bb2,Nc6,g3,d6,Bg2,Nf6,c4,a6,Nc3,e5,d3,Nd4,e3,Bg4,Qd2,Nf5,Nge2,Bxe2,Qxe2,g6,Bxb7,Rb8,Bc6+,Nd7,O-O,Bg7,Bg2,O-O,Nd5,Nb6,Nxb6,Rxb6,Bh3,Qf6,f4,Rb4,fxe5,dxe5,e4,Qe7,exf5,Kh8,Rae1,Rbb8,f6,Bxf6,Rxf6,Qxf6,Bxe5,Qxe5,Qxe5+,Kg8,Bg2,Rbe8,Qxe8,Rxe8,Rxe8+,Kg7,Bd5,h5,b4,cxb4,c5,b3,Bxb3,f5,c6,f4,c7,fxg3 → c8=Q WHITE_TO_MOVE [] *
5c4fd6dc315deda5108d7b90f1107b41: b3,c5,Bb2,Nc6,g3,d6,Bg2,Nf6,c4,a6,Nc3,e5,d3,Nd4,e3,Bg4,Qd2,Nf5,Nge2,Bxe2,Qxe2,g6,Bxb7,Rb8,Bc6+,Nd7,O-O,Bg7,Bg2,O-O,Nd5,Nb6,Nxb6,Rxb6,Bh3,Qf6,f4,Rb4,fxe5,dxe5,e4,Qe7,exf5,Kh8,Rae1,Rbb8,f6,Bxf6,Rxf6,Qxf6,Bxe5,Qxe5,Qxe5+,Kg8,Bg2,Rbe8,Qxe8,Rxe8,Rxe8+,Kg7,Bd5,h5,b4,cxb4,c5,b3,Bxb3,f5,c6,f4,c7,fxg3,c8=Q → gxh2+ BLACK_TO_MOVE [] *
637f9c695352fbf7f3d8f965c432586b: b3,c5,Bb2,Nc6,g3,d6,Bg2,Nf6,c4,a6,Nc3,e5,d3,Nd4,e3,Bg4,Qd2,Nf5,Nge2,Bxe2,Qxe2,g6,Bxb7,Rb8,Bc6+,Nd7,O-O,Bg7,Bg2,O-O,Nd5,Nb6,Nxb6,Rxb6,Bh3,Qf6,f4,Rb4,fxe5,dxe5,e4,Qe7,exf5,Kh8,Rae1,Rbb8,f6,Bxf6,Rxf6,Qxf6,Bxe5,Qxe5,Qxe5+,Kg8,Bg2,Rbe8,Qxe8,Rxe8,Rxe8+,Kg7,Bd5,h5,b4,cxb4,c5,b3,Bxb3,f5,c6,f4,c7,fxg3,c8=Q,gxh2+ → Kxh2 CHECK|WHITE_TO_MOVE [] *
0593ed2abfcad5a9a4a2a71da6e09685: b3,c5,Bb2,Nc6,g3,d6,Bg2,Nf6,c4,a6,Nc3,e5,d3,Nd4,e3,Bg4,Qd2,Nf5,Nge2,Bxe2,Qxe2,g6,Bxb7,Rb8,Bc6+,Nd7,O-O,Bg7,Bg2,O-O,Nd5,Nb6,Nxb6,Rxb6,Bh3,Qf6,f4,Rb4,fxe5,dxe5,e4,Qe7,exf5,Kh8,Rae1,Rbb8,f6,Bxf6,Rxf6,Qxf6,Bxe5,Qxe5,Qxe5+,Kg8,Bg2,Rbe8,Qxe8,Rxe8,Rxe8+,Kg7,Bd5,h5,b4,cxb4,c5,b3,Bxb3,f5,c6,f4,c7,fxg3,c8=Q,gxh2+,Kxh2 → h4 BLACK_TO_MOVE [] *
5d2e035efd39a5479deec78f5b666e99: b3,c5,Bb2,Nc6,g3,d6,Bg2,Nf6,c4,a6,Nc3,e5,d3,Nd4,e3,Bg4,Qd2,Nf5,Nge2,Bxe2,Qxe2,g6,Bxb7,Rb8,Bc6+,Nd7,O-O,Bg7,Bg2,O-O,Nd5,Nb6,Nxb6,Rxb6,Bh3,Qf6,f4,Rb4,fxe5,dxe5,e4,Qe7,exf5,Kh8,Rae1,Rbb8,f6,Bxf6,Rxf6,Qxf6,Bxe5,Qxe5,Qxe5+,Kg8,Bg2,Rbe8,Qxe8,Rxe8,Rxe8+,Kg7,Bd5,h5,b4,cxb4,c5,b3,Bxb3,f5,c6,f4,c7,fxg3,c8=Q,gxh2+,Kxh2,h4 → Qe6 WHITE_TO_MOVE [] *
d0f277065e46fadb20a74841167cafec: b3,c5,Bb2,Nc6,g3,d6,Bg2,Nf6,c4,a6,Nc3,e5,d3,Nd4,e3,Bg4,Qd2,Nf5,Nge2,Bxe2,Qxe2,g6,Bxb7,Rb8,Bc6+,Nd7,O-O,Bg7,Bg2,O-O,Nd5,Nb6,Nxb6,Rxb6,Bh3,Qf6,f4,Rb4,fxe5,dxe5,e4,Qe7,exf5,Kh8,Rae1,Rbb8,f6,Bxf6,Rxf6,Qxf6,Bxe5,Qxe5,Qxe5+,Kg8,Bg2,Rbe8,Qxe8,Rxe8,Rxe8+,Kg7,Bd5,h5,b4,cxb4,c5,b3,Bxb3,f5,c6,f4,c7,fxg3,c8=Q,gxh2+,Kxh2,h4,Qe6 → Kh6 BLACK_TO_MOVE [] *
119119ba0ac4741a9b4a8c72f43402f5: b3,c5,Bb2,Nc6,g3,d6,Bg2,Nf6,c4,a6,Nc3,e5,d3,Nd4,e3,Bg4,Qd2,Nf5,Nge2,Bxe2,Qxe2,g6,Bxb7,Rb8,Bc6+,Nd7,O-O,Bg7,Bg2,O-O,Nd5,Nb6,Nxb6,Rxb6,Bh3,Qf6,f4,Rb4,fxe5,dxe5,e4,Qe7,exf5,Kh8,Rae1,Rbb8,f6,Bxf6,Rxf6,Qxf6,Bxe5,Qxe5,Qxe5+,Kg8,Bg2,Rbe8,Qxe8,Rxe8,Rxe8+,Kg7,Bd5,h5,b4,cxb4,c5,b3,Bxb3,f5,c6,f4,c7,fxg3,c8=Q,gxh2+,Kxh2,h4,Qe6,Kh6 → Rg8 WHITE_TO_MOVE [] *
74341649e0e69ac1689ad1837a7089ad: b3,c5,Bb2,Nc6,g3,d6,Bg2,Nf6,c4,a6,Nc3,e5,d3,Nd4,e3,Bg4,Qd2,Nf5,Nge2,Bxe2,Qxe2,g6,Bxb7,Rb8,Bc6+,Nd7,O-O,Bg7,Bg2,O-O,Nd5,Nb6,Nxb6,Rxb6,Bh3,Qf6,f4,Rb4,fxe5,dxe5,e4,Qe7,exf5,Kh8,Rae1,Rbb8,f6,Bxf6,Rxf6,Qxf6,Bxe5,Qxe5,Qxe5+,Kg8,Bg2,Rbe8,Qxe8,Rxe8,Rxe8+,Kg7,Bd5,h5,b4,cxb4,c5,b3,Bxb3,f5,c6,f4,c7,fxg3,c8=Q,gxh2+,Kxh2,h4,Qe6,Kh6,Rg8 → Kg5 BLACK_TO_MOVE [] *
bfbb80b5bebe786fa5d8ccdd4c49c8eb: b3,c5,Bb2,Nc6,g3,d6,Bg2,Nf6,c4,a6,Nc3,e5,d3,Nd4,e3,Bg4,Qd2,Nf5,Nge2,Bxe2,Qxe2,g6,Bxb7,Rb8,Bc6+,Nd7,O-O,Bg7,Bg2,O-O,Nd5,Nb6,Nxb6,Rxb6,Bh3,Qf6,f4,Rb4,fxe5,dxe5,e4,Qe7,exf5,Kh8,Rae1,Rbb8,f6,Bxf6,Rxf6,Qxf6,Bxe5,Qxe5,Qxe5+,Kg8,Bg2,Rbe8,Qxe8,Rxe8,Rxe8+,Kg7,Bd5,h5,b4,cxb4,c5,b3,Bxb3,f5,c6,f4,c7,fxg3,c8=Q,gxh2+,Kxh2,h4,Qe6,Kh6,Rg8,Kg5 → Rxg6+ WHITE_TO_MOVE [] *
fa0cc4e92afd54233ead094caf7e6e74: b3,c5,Bb2,Nc6,g3,d6,Bg2,Nf6,c4,a6,Nc3,e5,d3,Nd4,e3,Bg4,Qd2,Nf5,Nge2,Bxe2,Qxe2,g6,Bxb7,Rb8,Bc6+,Nd7,O-O,Bg7,Bg2,O-O,Nd5,Nb6,Nxb6,Rxb6,Bh3,Qf6,f4,Rb4,fxe5,dxe5,e4,Qe7,exf5,Kh8,Rae1,Rbb8,f6,Bxf6,Rxf6,Qxf6,Bxe5,Qxe5,Qxe5+,Kg8,Bg2,Rbe8,Qxe8,Rxe8,Rxe8+,Kg7,Bd5,h5,b4,cxb4,c5,b3,Bxb3,f5,c6,f4,c7,fxg3,c8=Q,gxh2+,Kxh2,h4,Qe6,Kh6,Rg8,Kg5,Rxg6+ → Kh5 CHECK|BLACK_TO_MOVE [] *
f03ccae9aa7071ff55adfcde2c12a530: b3,c5,Bb2,Nc6,g3,d6,Bg2,Nf6,c4,a6,Nc3,e5,d3,Nd4,e3,Bg4,Qd2,Nf5,Nge2,Bxe2,Qxe2,g6,Bxb7,Rb8,Bc6+,Nd7,O-O,Bg7,Bg2,O-O,Nd5,Nb6,Nxb6,Rxb6,Bh3,Qf6,f4,Rb4,fxe5,dxe5,e4,Qe7,exf5,Kh8,Rae1,Rbb8,f6,Bxf6,Rxf6,Qxf6,Bxe5,Qxe5,Qxe5+,Kg8,Bg2,Rbe8,Qxe8,Rxe8,Rxe8+,Kg7,Bd5,h5,b4,cxb4,c5,b3,Bxb3,f5,c6,f4,c7,fxg3,c8=Q,gxh2+,Kxh2,h4,Qe6,Kh6,Rg8,Kg5,Rxg6+,Kh5 → Qg4# WHITE_TO_MOVE [] *
f8da2a698ef19a7c05871ed2045f7f57: b3,c5,Bb2,Nc6,g3,d6,Bg2,Nf6,c4,a6,Nc3,e5,d3,Nd4,e3,Bg4,Qd2,Nf5,Nge2,Bxe2,Qxe2,g6,Bxb7,Rb8,Bc6+,Nd7,O-O,Bg7,Bg2,O-O,Nd5,Nb6,Nxb6,Rxb6,Bh3,Qf6,f4,Rb4,fxe5,dxe5,e4,Qe7,exf5,Kh8,Rae1,Rbb8,f6,Bxf6,Rxf6,Qxf6,Bxe5,Qxe5,Qxe5+,Kg8,Bg2,Rbe8,Qxe8,Rxe8,Rxe8+,Kg7,Bd5,h5,b4,cxb4,c5,b3,Bxb3,f5,c6,f4,c7,fxg3,c8=Q,gxh2+,Kxh2,h4,Qe6,Kh6,Rg8,Kg5,Rxg6+,Kh5,Qg4# → * CHECKMATE|CHECK|BLACK_TO_MOVE [] 4/*/*
    da6966ed026112e63143ee0f617e6292ecaa57b5ae05eff6f093e7ed48610e41: {'event': 'WSCC Sting simul', 'site': 'New York', 'date': '2000.06.29', 'white': 'Kasparov, Garry', 'black': 'Botti, Chris', 'result': '1-0', 'whiteelo': '2851', 'eco': 'A01', 'eventdate': '2000.06.29'}
4e76061f723e19eab31025ada516d321: d4 (A40/Queen's Pawn Game) → Nf6,d5,e6 BLACK_TO_MOVE [] 4/d5/-0.21
1a5492d26859a8750581110af23c31f7: d4,Nf6 (A45/Indian Defense) → Nf3 WHITE_TO_MOVE [] *
3b6b13194c0f4b81299f05a135c4d5e6: d4,Nf6,Nf3 (A46/Indian Defense: Knights Variation) → g6 BLACK_TO_MOVE [] *
e1bdd369f0aab0bddcd39016647ba26e: d4,Nf6,Nf3,g6 (A48/East Indian Defense) → c4 WHITE_TO_MOVE [] *
d9ae83a731bfecc879adb7ad300b00a8: d4,Nf6,Nf3,g6,c4 (E60/King's Indian Defense: Normal Variation, King's Knight Variation) → Bg7 BLACK_TO_MOVE [] *
a13354558dc534a3f93c77b8779da55f: d4,Nf6,Nf3,g6,c4,Bg7 → Nc3 WHITE_TO_MOVE [] *
25a8ddca5b52e2b087fd10742524394c: d4,Nf6,Nf3,g6,c4,Bg7,Nc3 → d5 BLACK_TO_MOVE [] *
2afe30730f04c94feafa84a24e314c7f: d4,Nf6,Nf3,g6,c4,Bg7,Nc3,d5 (D90/Grünfeld Defense: Three Knights Variation) → Qb3 WHITE_TO_MOVE [] *
9af3afa0c04eefd148d9632b35fe9efd: d4,Nf6,Nf3,g6,c4,Bg7,Nc3,d5,Qb3 (D96/Grünfeld Defense: Russian Variation) → dxc4 BLACK_TO_MOVE [] *
b4c645867ce21cc7066e0c4ceca4bb62: d4,Nf6,Nf3,g6,c4,Bg7,Nc3,d5,Qb3,dxc4 → Qxc4 WHITE_TO_MOVE [] *
7bab54672426c1c7f01eba9462087038: d4,Nf6,Nf3,g6,c4,Bg7,Nc3,d5,Qb3,dxc4,Qxc4 → O-O BLACK_TO_MOVE [] *
811eb4a9c4c9b411f0519c11261be10d: d4,Nf6,Nf3,g6,c4,Bg7,Nc3,d5,Qb3,dxc4,Qxc4,O-O → e4 WHITE_TO_MOVE [] *
9d81bfc59036f68d0a73c110d0488052: d4,Nf6,Nf3,g6,c4,Bg7,Nc3,d5,Qb3,dxc4,Qxc4,O-O,e4 (D97/Grünfeld Defense: Russian Variation) → a6 BLACK_TO_MOVE [] *
345922a482a8dceeb172fc8a3ee3a30e: d4,Nf6,Nf3,g6,c4,Bg7,Nc3,d5,Qb3,dxc4,Qxc4,O-O,e4,a6 (D97/Grünfeld Defense: Russian Variation, Hungarian Variation) → Qb3 WHITE_TO_MOVE [] *
81f627fe8b6273323885f71a72bdff5f: d4,Nf6,Nf3,g6,c4,Bg7,Nc3,d5,Qb3,dxc4,Qxc4,O-O,e4,a6,Qb3 → c5 BLACK_TO_MOVE [] *
d90607bcd4bde25018aee37e07db6c08: d4,Nf6,Nf3,g6,c4,Bg7,Nc3,d5,Qb3,dxc4,Qxc4,O-O,e4,a6,Qb3,c5 → dxc5 WHITE_TO_MOVE [] *
f691dba25b6c1f0af40fd1c01413c6bf: d4,Nf6,Nf3,g6,c4,Bg7,Nc3,d5,Qb3,dxc4,Qxc4,O-O,e4,a6,Qb3,c5,dxc5 → Qa5 BLACK_TO_MOVE [] *
57270d9f6acd3294decff356dd12afac: d4,Nf6,Nf3,g6,c4,Bg7,Nc3,d5,Qb3,dxc4,Qxc4,O-O,e4,a6,Qb3,c5,dxc5,Qa5 → Qb6 WHITE_TO_MOVE [] *
8135ddae6b9f5a6840de45747668fcb1: d4,Nf6,Nf3,g6,c4,Bg7,Nc3,d5,Qb3,dxc4,Qxc4,O-O,e4,a6,Qb3,c5,dxc5,Qa5,Qb6 → Qxb6 BLACK_TO_MOVE [] *
88f64252e68778fbe693601d643cf00c: d4,Nf6,Nf3,g6,c4,Bg7,Nc3,d5,Qb3,dxc4,Qxc4,O-O,e4,a6,Qb3,c5,dxc5,Qa5,Qb6,Qxb6 → cxb6 WHITE_TO_MOVE [] *
4ac35424eeb2f7954760ecb7217fbcb0: d4,Nf6,Nf3,g6,c4,Bg7,Nc3,d5,Qb3,dxc4,Qxc4,O-O,e4,a6,Qb3,c5,dxc5,Qa5,Qb6,Qxb6,cxb6 → Nbd7 BLACK_TO_MOVE [] *
ff4f38d12350c395adecd15d3f992d81: d4,Nf6,Nf3,g6,c4,Bg7,Nc3,d5,Qb3,dxc4,Qxc4,O-O,e4,a6,Qb3,c5,dxc5,Qa5,Qb6,Qxb6,cxb6,Nbd7 → Be2 WHITE_TO_MOVE [] *
52f91ff17195fc2c5ceb81c1c8671848: d4,Nf6,Nf3,g6,c4,Bg7,Nc3,d5,Qb3,dxc4,Qxc4,O-O,e4,a6,Qb3,c5,dxc5,Qa5,Qb6,Qxb6,cxb6,Nbd7,Be2 → Nxb6 BLACK_TO_MOVE [] *
7d7fe321cfba40c4ae5c97b246176d8a: d4,Nf6,Nf3,g6,c4,Bg7,Nc3,d5,Qb3,dxc4,Qxc4,O-O,e4,a6,Qb3,c5,dxc5,Qa5,Qb6,Qxb6,cxb6,Nbd7,Be2,Nxb6 → Be3 WHITE_TO_MOVE [] *
a5e40ce719da44d0dfdc8b481621bd34: d4,Nf6,Nf3,g6,c4,Bg7,Nc3,d5,Qb3,dxc4,Qxc4,O-O,e4,a6,Qb3,c5,dxc5,Qa5,Qb6,Qxb6,cxb6,Nbd7,Be2,Nxb6,Be3 → Nbd7 BLACK_TO_MOVE [] *
78d43241a0947fc75f81c1c3987a1a23: d4,Nf6,Nf3,g6,c4,Bg7,Nc3,d5,Qb3,dxc4,Qxc4,O-O,e4,a6,Qb3,c5,dxc5,Qa5,Qb6,Qxb6,cxb6,Nbd7,Be2,Nxb6,Be3,Nbd7 → Nd4 WHITE_TO_MOVE [] *
6809bb13a8f2e5978070331e5080e333: d4,Nf6,Nf3,g6,c4,Bg7,Nc3,d5,Qb3,dxc4,Qxc4,O-O,e4,a6,Qb3,c5,dxc5,Qa5,Qb6,Qxb6,cxb6,Nbd7,Be2,Nxb6,Be3,Nbd7,Nd4 → Nc5 BLACK_TO_MOVE [] *
7f9122942ef0cb7ed15bc17606ccb234: d4,Nf6,Nf3,g6,c4,Bg7,Nc3,d5,Qb3,dxc4,Qxc4,O-O,e4,a6,Qb3,c5,dxc5,Qa5,Qb6,Qxb6,cxb6,Nbd7,Be2,Nxb6,Be3,Nbd7,Nd4,Nc5 → f3 WHITE_TO_MOVE [] *
f68126734b8e07e38e0c30d59d2023a7: d4,Nf6,Nf3,g6,c4,Bg7,Nc3,d5,Qb3,dxc4,Qxc4,O-O,e4,a6,Qb3,c5,dxc5,Qa5,Qb6,Qxb6,cxb6,Nbd7,Be2,Nxb6,Be3,Nbd7,Nd4,Nc5,f3 → e5 BLACK_TO_MOVE [] *
6f9c728cc48ad1dd268b5fb909ef57e0: d4,Nf6,Nf3,g6,c4,Bg7,Nc3,d5,Qb3,dxc4,Qxc4,O-O,e4,a6,Qb3,c5,dxc5,Qa5,Qb6,Qxb6,cxb6,Nbd7,Be2,Nxb6,Be3,Nbd7,Nd4,Nc5,f3,e5 → Nc6 WHITE_TO_MOVE [] *
396794335c388482a9da02ad7eaf2ef6: d4,Nf6,Nf3,g6,c4,Bg7,Nc3,d5,Qb3,dxc4,Qxc4,O-O,e4,a6,Qb3,c5,dxc5,Qa5,Qb6,Qxb6,cxb6,Nbd7,Be2,Nxb6,Be3,Nbd7,Nd4,Nc5,f3,e5,Nc6 → bxc6 BLACK_TO_MOVE [] *
de4e98c68c2690538f47f8745ec77535: d4,Nf6,Nf3,g6,c4,Bg7,Nc3,d5,Qb3,dxc4,Qxc4,O-O,e4,a6,Qb3,c5,dxc5,Qa5,Qb6,Qxb6,cxb6,Nbd7,Be2,Nxb6,Be3,Nbd7,Nd4,Nc5,f3,e5,Nc6,bxc6 → Bxc5 WHITE_TO_MOVE [] *
31fd71cd2010baee8c8fab00c6bf1488: d4,Nf6,Nf3,g6,c4,Bg7,Nc3,d5,Qb3,dxc4,Qxc4,O-O,e4,a6,Qb3,c5,dxc5,Qa5,Qb6,Qxb6,cxb6,Nbd7,Be2,Nxb6,Be3,Nbd7,Nd4,Nc5,f3,e5,Nc6,bxc6,Bxc5 → Rd8 BLACK_TO_MOVE [] *
3ccfa76981d9a68105ffd6073b78f093: d4,Nf6,Nf3,g6,c4,Bg7,Nc3,d5,Qb3,dxc4,Qxc4,O-O,e4,a6,Qb3,c5,dxc5,Qa5,Qb6,Qxb6,cxb6,Nbd7,Be2,Nxb6,Be3,Nbd7,Nd4,Nc5,f3,e5,Nc6,bxc6,Bxc5,Rd8 → Kf2 WHITE_TO_MOVE [] *
7955847eda925b7b9aefbb4ebdc534dd: d4,Nf6,Nf3,g6,c4,Bg7,Nc3,d5,Qb3,dxc4,Qxc4,O-O,e4,a6,Qb3,c5,dxc5,Qa5,Qb6,Qxb6,cxb6,Nbd7,Be2,Nxb6,Be3,Nbd7,Nd4,Nc5,f3,e5,Nc6,bxc6,Bxc5,Rd8,Kf2 → Be6 BLACK_TO_MOVE [] *
8479e0028d1e22ccbc6e2422b79fce7b: d4,Nf6,Nf3,g6,c4,Bg7,Nc3,d5,Qb3,dxc4,Qxc4,O-O,e4,a6,Qb3,c5,dxc5,Qa5,Qb6,Qxb6,cxb6,Nbd7,Be2,Nxb6,Be3,Nbd7,Nd4,Nc5,f3,e5,Nc6,bxc6,Bxc5,Rd8,Kf2,Be6 → Rhd1 WHITE_TO_MOVE [] *
4d7144567dccc0a16e64b5425bfc04ad: d4,Nf6,Nf3,g6,c4,Bg7,Nc3,d5,Qb3,dxc4,Qxc4,O-O,e4,a6,Qb3,c5,dxc5,Qa5,Qb6,Qxb6,cxb6,Nbd7,Be2,Nxb6,Be3,Nbd7,Nd4,Nc5,f3,e5,Nc6,bxc6,Bxc5,Rd8,Kf2,Be6,Rhd1 → Nd7 BLACK_TO_MOVE [] *
53abaa7f76957b7f7ef1f1d61b0d91b3: d4,Nf6,Nf3,g6,c4,Bg7,Nc3,d5,Qb3,dxc4,Qxc4,O-O,e4,a6,Qb3,c5,dxc5,Qa5,Qb6,Qxb6,cxb6,Nbd7,Be2,Nxb6,Be3,Nbd7,Nd4,Nc5,f3,e5,Nc6,bxc6,Bxc5,Rd8,Kf2,Be6,Rhd1,Nd7 → Be3 WHITE_TO_MOVE [] *
6e4b152bd7bb255d45d8757a033d3a12: d4,Nf6,Nf3,g6,c4,Bg7,Nc3,d5,Qb3,dxc4,Qxc4,O-O,e4,a6,Qb3,c5,dxc5,Qa5,Qb6,Qxb6,cxb6,Nbd7,Be2,Nxb6,Be3,Nbd7,Nd4,Nc5,f3,e5,Nc6,bxc6,Bxc5,Rd8,Kf2,Be6,Rhd1,Nd7,Be3 → Bf8 BLACK_TO_MOVE [] *
16d6c2d96bc1fd36c549b56f44ab9fe5: d4,Nf6,Nf3,g6,c4,Bg7,Nc3,d5,Qb3,dxc4,Qxc4,O-O,e4,a6,Qb3,c5,dxc5,Qa5,Qb6,Qxb6,cxb6,Nbd7,Be2,Nxb6,Be3,Nbd7,Nd4,Nc5,f3,e5,Nc6,bxc6,Bxc5,Rd8,Kf2,Be6,Rhd1,Nd7,Be3,Bf8 → Rd2 WHITE_TO_MOVE [] *
3b5c3804f2345f31d3625cdb04b5cdb0: d4,Nf6,Nf3,g6,c4,Bg7,Nc3,d5,Qb3,dxc4,Qxc4,O-O,e4,a6,Qb3,c5,dxc5,Qa5,Qb6,Qxb6,cxb6,Nbd7,Be2,Nxb6,Be3,Nbd7,Nd4,Nc5,f3,e5,Nc6,bxc6,Bxc5,Rd8,Kf2,Be6,Rhd1,Nd7,Be3,Bf8,Rd2 → f5 BLACK_TO_MOVE [] *
ea021b2cd3d785a464bf52e2ef11805c: d4,Nf6,Nf3,g6,c4,Bg7,Nc3,d5,Qb3,dxc4,Qxc4,O-O,e4,a6,Qb3,c5,dxc5,Qa5,Qb6,Qxb6,cxb6,Nbd7,Be2,Nxb6,Be3,Nbd7,Nd4,Nc5,f3,e5,Nc6,bxc6,Bxc5,Rd8,Kf2,Be6,Rhd1,Nd7,Be3,Bf8,Rd2,f5 → Rad1 WHITE_TO_MOVE [] *
f212eea976e779743e029f3fde057b70: d4,Nf6,Nf3,g6,c4,Bg7,Nc3,d5,Qb3,dxc4,Qxc4,O-O,e4,a6,Qb3,c5,dxc5,Qa5,Qb6,Qxb6,cxb6,Nbd7,Be2,Nxb6,Be3,Nbd7,Nd4,Nc5,f3,e5,Nc6,bxc6,Bxc5,Rd8,Kf2,Be6,Rhd1,Nd7,Be3,Bf8,Rd2,f5,Rad1 → Be7 BLACK_TO_MOVE [] *
83ef33e8d3ac3e3ed086cd480a168bd9: d4,Nf6,Nf3,g6,c4,Bg7,Nc3,d5,Qb3,dxc4,Qxc4,O-O,e4,a6,Qb3,c5,dxc5,Qa5,Qb6,Qxb6,cxb6,Nbd7,Be2,Nxb6,Be3,Nbd7,Nd4,Nc5,f3,e5,Nc6,bxc6,Bxc5,Rd8,Kf2,Be6,Rhd1,Nd7,Be3,Bf8,Rd2,f5,Rad1,Be7 → g3 WHITE_TO_MOVE [] *
e8efb71d4f8a807b4d434e57f76eec58: d4,Nf6,Nf3,g6,c4,Bg7,Nc3,d5,Qb3,dxc4,Qxc4,O-O,e4,a6,Qb3,c5,dxc5,Qa5,Qb6,Qxb6,cxb6,Nbd7,Be2,Nxb6,Be3,Nbd7,Nd4,Nc5,f3,e5,Nc6,bxc6,Bxc5,Rd8,Kf2,Be6,Rhd1,Nd7,Be3,Bf8,Rd2,f5,Rad1,Be7,g3 → Kf7 BLACK_TO_MOVE [] *
8a0bb1f3e09c5237c2108a5261693d8e: d4,Nf6,Nf3,g6,c4,Bg7,Nc3,d5,Qb3,dxc4,Qxc4,O-O,e4,a6,Qb3,c5,dxc5,Qa5,Qb6,Qxb6,cxb6,Nbd7,Be2,Nxb6,Be3,Nbd7,Nd4,Nc5,f3,e5,Nc6,bxc6,Bxc5,Rd8,Kf2,Be6,Rhd1,Nd7,Be3,Bf8,Rd2,f5,Rad1,Be7,g3,Kf7 → b3 WHITE_TO_MOVE [] *
c56a1aece861e281f83407b7468c764e: d4,Nf6,Nf3,g6,c4,Bg7,Nc3,d5,Qb3,dxc4,Qxc4,O-O,e4,a6,Qb3,c5,dxc5,Qa5,Qb6,Qxb6,cxb6,Nbd7,Be2,Nxb6,Be3,Nbd7,Nd4,Nc5,f3,e5,Nc6,bxc6,Bxc5,Rd8,Kf2,Be6,Rhd1,Nd7,Be3,Bf8,Rd2,f5,Rad1,Be7,g3,Kf7,b3 → a5 BLACK_TO_MOVE [] *
2273523e61f4604e54e8018e67f2271e: d4,Nf6,Nf3,g6,c4,Bg7,Nc3,d5,Qb3,dxc4,Qxc4,O-O,e4,a6,Qb3,c5,dxc5,Qa5,Qb6,Qxb6,cxb6,Nbd7,Be2,Nxb6,Be3,Nbd7,Nd4,Nc5,f3,e5,Nc6,bxc6,Bxc5,Rd8,Kf2,Be6,Rhd1,Nd7,Be3,Bf8,Rd2,f5,Rad1,Be7,g3,Kf7,b3,a5 → Rc2 WHITE_TO_MOVE [] *
5b8c36d21e4718f583f4edd3a6227c08: d4,Nf6,Nf3,g6,c4,Bg7,Nc3,d5,Qb3,dxc4,Qxc4,O-O,e4,a6,Qb3,c5,dxc5,Qa5,Qb6,Qxb6,cxb6,Nbd7,Be2,Nxb6,Be3,Nbd7,Nd4,Nc5,f3,e5,Nc6,bxc6,Bxc5,Rd8,Kf2,Be6,Rhd1,Nd7,Be3,Bf8,Rd2,f5,Rad1,Be7,g3,Kf7,b3,a5,Rc2 → Nf6 BLACK_TO_MOVE [] *
4556d8fb151ea32b9361a947e6d3e916: d4,Nf6,Nf3,g6,c4,Bg7,Nc3,d5,Qb3,dxc4,Qxc4,O-O,e4,a6,Qb3,c5,dxc5,Qa5,Qb6,Qxb6,cxb6,Nbd7,Be2,Nxb6,Be3,Nbd7,Nd4,Nc5,f3,e5,Nc6,bxc6,Bxc5,Rd8,Kf2,Be6,Rhd1,Nd7,Be3,Bf8,Rd2,f5,Rad1,Be7,g3,Kf7,b3,a5,Rc2,Nf6 → Rxd8 WHITE_TO_MOVE [] *
0969687b535beec506c44bfd1f114607: d4,Nf6,Nf3,g6,c4,Bg7,Nc3,d5,Qb3,dxc4,Qxc4,O-O,e4,a6,Qb3,c5,dxc5,Qa5,Qb6,Qxb6,cxb6,Nbd7,Be2,Nxb6,Be3,Nbd7,Nd4,Nc5,f3,e5,Nc6,bxc6,Bxc5,Rd8,Kf2,Be6,Rhd1,Nd7,Be3,Bf8,Rd2,f5,Rad1,Be7,g3,Kf7,b3,a5,Rc2,Nf6,Rxd8 → Rxd8 BLACK_TO_MOVE [] *
a3fdb0ca48da9dffafc2a3f296b05a7e: d4,Nf6,Nf3,g6,c4,Bg7,Nc3,d5,Qb3,dxc4,Qxc4,O-O,e4,a6,Qb3,c5,dxc5,Qa5,Qb6,Qxb6,cxb6,Nbd7,Be2,Nxb6,Be3,Nbd7,Nd4,Nc5,f3,e5,Nc6,bxc6,Bxc5,Rd8,Kf2,Be6,Rhd1,Nd7,Be3,Bf8,Rd2,f5,Rad1,Be7,g3,Kf7,b3,a5,Rc2,Nf6,Rxd8,Rxd8 → exf5 WHITE_TO_MOVE [] *
29fb380f480312dae36ec1ab749bc1ea: d4,Nf6,Nf3,g6,c4,Bg7,Nc3,d5,Qb3,dxc4,Qxc4,O-O,e4,a6,Qb3,c5,dxc5,Qa5,Qb6,Qxb6,cxb6,Nbd7,Be2,Nxb6,Be3,Nbd7,Nd4,Nc5,f3,e5,Nc6,bxc6,Bxc5,Rd8,Kf2,Be6,Rhd1,Nd7,Be3,Bf8,Rd2,f5,Rad1,Be7,g3,Kf7,b3,a5,Rc2,Nf6,Rxd8,Rxd8,exf5 → gxf5 BLACK_TO_MOVE [] *
d6245ca4213cdee6c4625b8738698aae: d4,Nf6,Nf3,g6,c4,Bg7,Nc3,d5,Qb3,dxc4,Qxc4,O-O,e4,a6,Qb3,c5,dxc5,Qa5,Qb6,Qxb6,cxb6,Nbd7,Be2,Nxb6,Be3,Nbd7,Nd4,Nc5,f3,e5,Nc6,bxc6,Bxc5,Rd8,Kf2,Be6,Rhd1,Nd7,Be3,Bf8,Rd2,f5,Rad1,Be7,g3,Kf7,b3,a5,Rc2,Nf6,Rxd8,Rxd8,exf5,gxf5 → Na4 WHITE_TO_MOVE [] *
7b649481ad492911f9b8034605b2fe09: d4,Nf6,Nf3,g6,c4,Bg7,Nc3,d5,Qb3,dxc4,Qxc4,O-O,e4,a6,Qb3,c5,dxc5,Qa5,Qb6,Qxb6,cxb6,Nbd7,Be2,Nxb6,Be3,Nbd7,Nd4,Nc5,f3,e5,Nc6,bxc6,Bxc5,Rd8,Kf2,Be6,Rhd1,Nd7,Be3,Bf8,Rd2,f5,Rad1,Be7,g3,Kf7,b3,a5,Rc2,Nf6,Rxd8,Rxd8,exf5,gxf5,Na4 → Bd5 BLACK_TO_MOVE [] *
fcd6b0b678f415ed2896a0e1e9757d4b: d4,Nf6,Nf3,g6,c4,Bg7,Nc3,d5,Qb3,dxc4,Qxc4,O-O,e4,a6,Qb3,c5,dxc5,Qa5,Qb6,Qxb6,cxb6,Nbd7,Be2,Nxb6,Be3,Nbd7,Nd4,Nc5,f3,e5,Nc6,bxc6,Bxc5,Rd8,Kf2,Be6,Rhd1,Nd7,Be3,Bf8,Rd2,f5,Rad1,Be7,g3,Kf7,b3,a5,Rc2,Nf6,Rxd8,Rxd8,exf5,gxf5,Na4,Bd5 → Bb6 WHITE_TO_MOVE [] *
90d6933c1272a3faa4772db5a183131d: d4,Nf6,Nf3,g6,c4,Bg7,Nc3,d5,Qb3,dxc4,Qxc4,O-O,e4,a6,Qb3,c5,dxc5,Qa5,Qb6,Qxb6,cxb6,Nbd7,Be2,Nxb6,Be3,Nbd7,Nd4,Nc5,f3,e5,Nc6,bxc6,Bxc5,Rd8,Kf2,Be6,Rhd1,Nd7,Be3,Bf8,Rd2,f5,Rad1,Be7,g3,Kf7,b3,a5,Rc2,Nf6,Rxd8,Rxd8,exf5,gxf5,Na4,Bd5,Bb6 → Ra8 BLACK_TO_MOVE [] *
3aa38c6af2fe86f9397f3b059d71fb83: d4,Nf6,Nf3,g6,c4,Bg7,Nc3,d5,Qb3,dxc4,Qxc4,O-O,e4,a6,Qb3,c5,dxc5,Qa5,Qb6,Qxb6,cxb6,Nbd7,Be2,Nxb6,Be3,Nbd7,Nd4,Nc5,f3,e5,Nc6,bxc6,Bxc5,Rd8,Kf2,Be6,Rhd1,Nd7,Be3,Bf8,Rd2,f5,Rad1,Be7,g3,Kf7,b3,a5,Rc2,Nf6,Rxd8,Rxd8,exf5,gxf5,Na4,Bd5,Bb6,Ra8 → Bc5 WHITE_TO_MOVE [] *
96e1bf320ee5da4f6bf1498c0f3df12f: d4,Nf6,Nf3,g6,c4,Bg7,Nc3,d5,Qb3,dxc4,Qxc4,O-O,e4,a6,Qb3,c5,dxc5,Qa5,Qb6,Qxb6,cxb6,Nbd7,Be2,Nxb6,Be3,Nbd7,Nd4,Nc5,f3,e5,Nc6,bxc6,Bxc5,Rd8,Kf2,Be6,Rhd1,Nd7,Be3,Bf8,Rd2,f5,Rad1,Be7,g3,Kf7,b3,a5,Rc2,Nf6,Rxd8,Rxd8,exf5,gxf5,Na4,Bd5,Bb6,Ra8,Bc5 → Nd7 BLACK_TO_MOVE [] *
883b511b05bc61917b640d184fcc6431: d4,Nf6,Nf3,g6,c4,Bg7,Nc3,d5,Qb3,dxc4,Qxc4,O-O,e4,a6,Qb3,c5,dxc5,Qa5,Qb6,Qxb6,cxb6,Nbd7,Be2,Nxb6,Be3,Nbd7,Nd4,Nc5,f3,e5,Nc6,bxc6,Bxc5,Rd8,Kf2,Be6,Rhd1,Nd7,Be3,Bf8,Rd2,f5,Rad1,Be7,g3,Kf7,b3,a5,Rc2,Nf6,Rxd8,Rxd8,exf5,gxf5,Na4,Bd5,Bb6,Ra8,Bc5,Nd7 → Bxe7 WHITE_TO_MOVE [] *
0d15bb885938fa069a454117df4d94c3: d4,Nf6,Nf3,g6,c4,Bg7,Nc3,d5,Qb3,dxc4,Qxc4,O-O,e4,a6,Qb3,c5,dxc5,Qa5,Qb6,Qxb6,cxb6,Nbd7,Be2,Nxb6,Be3,Nbd7,Nd4,Nc5,f3,e5,Nc6,bxc6,Bxc5,Rd8,Kf2,Be6,Rhd1,Nd7,Be3,Bf8,Rd2,f5,Rad1,Be7,g3,Kf7,b3,a5,Rc2,Nf6,Rxd8,Rxd8,exf5,gxf5,Na4,Bd5,Bb6,Ra8,Bc5,Nd7,Bxe7 → Kxe7 BLACK_TO_MOVE [] *
b7f02fdeee4018dc707a6ff04a80687b: d4,Nf6,Nf3,g6,c4,Bg7,Nc3,d5,Qb3,dxc4,Qxc4,O-O,e4,a6,Qb3,c5,dxc5,Qa5,Qb6,Qxb6,cxb6,Nbd7,Be2,Nxb6,Be3,Nbd7,Nd4,Nc5,f3,e5,Nc6,bxc6,Bxc5,Rd8,Kf2,Be6,Rhd1,Nd7,Be3,Bf8,Rd2,f5,Rad1,Be7,g3,Kf7,b3,a5,Rc2,Nf6,Rxd8,Rxd8,exf5,gxf5,Na4,Bd5,Bb6,Ra8,Bc5,Nd7,Bxe7,Kxe7 → Ke3 WHITE_TO_MOVE [] *
c0786078499deb0a25012b6e7780cda4: d4,Nf6,Nf3,g6,c4,Bg7,Nc3,d5,Qb3,dxc4,Qxc4,O-O,e4,a6,Qb3,c5,dxc5,Qa5,Qb6,Qxb6,cxb6,Nbd7,Be2,Nxb6,Be3,Nbd7,Nd4,Nc5,f3,e5,Nc6,bxc6,Bxc5,Rd8,Kf2,Be6,Rhd1,Nd7,Be3,Bf8,Rd2,f5,Rad1,Be7,g3,Kf7,b3,a5,Rc2,Nf6,Rxd8,Rxd8,exf5,gxf5,Na4,Bd5,Bb6,Ra8,Bc5,Nd7,Bxe7,Kxe7,Ke3 → Kd6 BLACK_TO_MOVE [] *
6ff3756fa004f34de2b0fe49fc9ff2ce: d4,Nf6,Nf3,g6,c4,Bg7,Nc3,d5,Qb3,dxc4,Qxc4,O-O,e4,a6,Qb3,c5,dxc5,Qa5,Qb6,Qxb6,cxb6,Nbd7,Be2,Nxb6,Be3,Nbd7,Nd4,Nc5,f3,e5,Nc6,bxc6,Bxc5,Rd8,Kf2,Be6,Rhd1,Nd7,Be3,Bf8,Rd2,f5,Rad1,Be7,g3,Kf7,b3,a5,Rc2,Nf6,Rxd8,Rxd8,exf5,gxf5,Na4,Bd5,Bb6,Ra8,Bc5,Nd7,Bxe7,Kxe7,Ke3,Kd6 → Bd3 WHITE_TO_MOVE [] *
d673f0598cd1946b82243856a7732e13: d4,Nf6,Nf3,g6,c4,Bg7,Nc3,d5,Qb3,dxc4,Qxc4,O-O,e4,a6,Qb3,c5,dxc5,Qa5,Qb6,Qxb6,cxb6,Nbd7,Be2,Nxb6,Be3,Nbd7,Nd4,Nc5,f3,e5,Nc6,bxc6,Bxc5,Rd8,Kf2,Be6,Rhd1,Nd7,Be3,Bf8,Rd2,f5,Rad1,Be7,g3,Kf7,b3,a5,Rc2,Nf6,Rxd8,Rxd8,exf5,gxf5,Na4,Bd5,Bb6,Ra8,Bc5,Nd7,Bxe7,Kxe7,Ke3,Kd6,Bd3 → f4+ BLACK_TO_MOVE [] *
8bcf3638caa92af9e4c3f36093bf062d: d4,Nf6,Nf3,g6,c4,Bg7,Nc3,d5,Qb3,dxc4,Qxc4,O-O,e4,a6,Qb3,c5,dxc5,Qa5,Qb6,Qxb6,cxb6,Nbd7,Be2,Nxb6,Be3,Nbd7,Nd4,Nc5,f3,e5,Nc6,bxc6,Bxc5,Rd8,Kf2,Be6,Rhd1,Nd7,Be3,Bf8,Rd2,f5,Rad1,Be7,g3,Kf7,b3,a5,Rc2,Nf6,Rxd8,Rxd8,exf5,gxf5,Na4,Bd5,Bb6,Ra8,Bc5,Nd7,Bxe7,Kxe7,Ke3,Kd6,Bd3,f4+ → gxf4 CHECK|WHITE_TO_MOVE [] *
4a452a31e1854ff2cce307529e241d94: d4,Nf6,Nf3,g6,c4,Bg7,Nc3,d5,Qb3,dxc4,Qxc4,O-O,e4,a6,Qb3,c5,dxc5,Qa5,Qb6,Qxb6,cxb6,Nbd7,Be2,Nxb6,Be3,Nbd7,Nd4,Nc5,f3,e5,Nc6,bxc6,Bxc5,Rd8,Kf2,Be6,Rhd1,Nd7,Be3,Bf8,Rd2,f5,Rad1,Be7,g3,Kf7,b3,a5,Rc2,Nf6,Rxd8,Rxd8,exf5,gxf5,Na4,Bd5,Bb6,Ra8,Bc5,Nd7,Bxe7,Kxe7,Ke3,Kd6,Bd3,f4+,gxf4 → exf4+ BLACK_TO_MOVE [] *
4413dbc6a82ded22f17c664c7ea448c2: d4,Nf6,Nf3,g6,c4,Bg7,Nc3,d5,Qb3,dxc4,Qxc4,O-O,e4,a6,Qb3,c5,dxc5,Qa5,Qb6,Qxb6,cxb6,Nbd7,Be2,Nxb6,Be3,Nbd7,Nd4,Nc5,f3,e5,Nc6,bxc6,Bxc5,Rd8,Kf2,Be6,Rhd1,Nd7,Be3,Bf8,Rd2,f5,Rad1,Be7,g3,Kf7,b3,a5,Rc2,Nf6,Rxd8,Rxd8,exf5,gxf5,Na4,Bd5,Bb6,Ra8,Bc5,Nd7,Bxe7,Kxe7,Ke3,Kd6,Bd3,f4+,gxf4,exf4+ → Kxf4 CHECK|WHITE_TO_MOVE [] *
9c5e8a80ceece31f8b970184f40f2703: d4,Nf6,Nf3,g6,c4,Bg7,Nc3,d5,Qb3,dxc4,Qxc4,O-O,e4,a6,Qb3,c5,dxc5,Qa5,Qb6,Qxb6,cxb6,Nbd7,Be2,Nxb6,Be3,Nbd7,Nd4,Nc5,f3,e5,Nc6,bxc6,Bxc5,Rd8,Kf2,Be6,Rhd1,Nd7,Be3,Bf8,Rd2,f5,Rad1,Be7,g3,Kf7,b3,a5,Rc2,Nf6,Rxd8,Rxd8,exf5,gxf5,Na4,Bd5,Bb6,Ra8,Bc5,Nd7,Bxe7,Kxe7,Ke3,Kd6,Bd3,f4+,gxf4,exf4+,Kxf4 → Rf8+ BLACK_TO_MOVE [] *
c6bbecf4b81a6ef07aa91142f7b0e4dd: d4,Nf6,Nf3,g6,c4,Bg7,Nc3,d5,Qb3,dxc4,Qxc4,O-O,e4,a6,Qb3,c5,dxc5,Qa5,Qb6,Qxb6,cxb6,Nbd7,Be2,Nxb6,Be3,Nbd7,Nd4,Nc5,f3,e5,Nc6,bxc6,Bxc5,Rd8,Kf2,Be6,Rhd1,Nd7,Be3,Bf8,Rd2,f5,Rad1,Be7,g3,Kf7,b3,a5,Rc2,Nf6,Rxd8,Rxd8,exf5,gxf5,Na4,Bd5,Bb6,Ra8,Bc5,Nd7,Bxe7,Kxe7,Ke3,Kd6,Bd3,f4+,gxf4,exf4+,Kxf4,Rf8+ → Kg5 CHECK|WHITE_TO_MOVE [] *
ba6de3dcfcc9458db1813aec4af6c1e7: d4,Nf6,Nf3,g6,c4,Bg7,Nc3,d5,Qb3,dxc4,Qxc4,O-O,e4,a6,Qb3,c5,dxc5,Qa5,Qb6,Qxb6,cxb6,Nbd7,Be2,Nxb6,Be3,Nbd7,Nd4,Nc5,f3,e5,Nc6,bxc6,Bxc5,Rd8,Kf2,Be6,Rhd1,Nd7,Be3,Bf8,Rd2,f5,Rad1,Be7,g3,Kf7,b3,a5,Rc2,Nf6,Rxd8,Rxd8,exf5,gxf5,Na4,Bd5,Bb6,Ra8,Bc5,Nd7,Bxe7,Kxe7,Ke3,Kd6,Bd3,f4+,gxf4,exf4+,Kxf4,Rf8+,Kg5 → Ne5 BLACK_TO_MOVE [] *
f9eaa8a8a454a32ac03f838aaeb05ecf: d4,Nf6,Nf3,g6,c4,Bg7,Nc3,d5,Qb3,dxc4,Qxc4,O-O,e4,a6,Qb3,c5,dxc5,Qa5,Qb6,Qxb6,cxb6,Nbd7,Be2,Nxb6,Be3,Nbd7,Nd4,Nc5,f3,e5,Nc6,bxc6,Bxc5,Rd8,Kf2,Be6,Rhd1,Nd7,Be3,Bf8,Rd2,f5,Rad1,Be7,g3,Kf7,b3,a5,Rc2,Nf6,Rxd8,Rxd8,exf5,gxf5,Na4,Bd5,Bb6,Ra8,Bc5,Nd7,Bxe7,Kxe7,Ke3,Kd6,Bd3,f4+,gxf4,exf4+,Kxf4,Rf8+,Kg5,Ne5 → Bxh7 WHITE_TO_MOVE [] *
3b9afafcccb79ed5f6a5f9193f13be26: d4,Nf6,Nf3,g6,c4,Bg7,Nc3,d5,Qb3,dxc4,Qxc4,O-O,e4,a6,Qb3,c5,dxc5,Qa5,Qb6,Qxb6,cxb6,Nbd7,Be2,Nxb6,Be3,Nbd7,Nd4,Nc5,f3,e5,Nc6,bxc6,Bxc5,Rd8,Kf2,Be6,Rhd1,Nd7,Be3,Bf8,Rd2,f5,Rad1,Be7,g3,Kf7,b3,a5,Rc2,Nf6,Rxd8,Rxd8,exf5,gxf5,Na4,Bd5,Bb6,Ra8,Bc5,Nd7,Bxe7,Kxe7,Ke3,Kd6,Bd3,f4+,gxf4,exf4+,Kxf4,Rf8+,Kg5,Ne5,Bxh7 → Nxf3+ BLACK_TO_MOVE [] *
0e632977fd513f76a902594ccdf3b0c0: d4,Nf6,Nf3,g6,c4,Bg7,Nc3,d5,Qb3,dxc4,Qxc4,O-O,e4,a6,Qb3,c5,dxc5,Qa5,Qb6,Qxb6,cxb6,Nbd7,Be2,Nxb6,Be3,Nbd7,Nd4,Nc5,f3,e5,Nc6,bxc6,Bxc5,Rd8,Kf2,Be6,Rhd1,Nd7,Be3,Bf8,Rd2,f5,Rad1,Be7,g3,Kf7,b3,a5,Rc2,Nf6,Rxd8,Rxd8,exf5,gxf5,Na4,Bd5,Bb6,Ra8,Bc5,Nd7,Bxe7,Kxe7,Ke3,Kd6,Bd3,f4+,gxf4,exf4+,Kxf4,Rf8+,Kg5,Ne5,Bxh7,Nxf3+ → Kh6 CHECK|WHITE_TO_MOVE [] *
3c1ddd167db7a621b47f4c166b0fe8d7: d4,Nf6,Nf3,g6,c4,Bg7,Nc3,d5,Qb3,dxc4,Qxc4,O-O,e4,a6,Qb3,c5,dxc5,Qa5,Qb6,Qxb6,cxb6,Nbd7,Be2,Nxb6,Be3,Nbd7,Nd4,Nc5,f3,e5,Nc6,bxc6,Bxc5,Rd8,Kf2,Be6,Rhd1,Nd7,Be3,Bf8,Rd2,f5,Rad1,Be7,g3,Kf7,b3,a5,Rc2,Nf6,Rxd8,Rxd8,exf5,gxf5,Na4,Bd5,Bb6,Ra8,Bc5,Nd7,Bxe7,Kxe7,Ke3,Kd6,Bd3,f4+,gxf4,exf4+,Kxf4,Rf8+,Kg5,Ne5,Bxh7,Nxf3+,Kh6 → Rf4 BLACK_TO_MOVE [] *
06abfba6cf2842e93afd998208c8545e: d4,Nf6,Nf3,g6,c4,Bg7,Nc3,d5,Qb3,dxc4,Qxc4,O-O,e4,a6,Qb3,c5,dxc5,Qa5,Qb6,Qxb6,cxb6,Nbd7,Be2,Nxb6,Be3,Nbd7,Nd4,Nc5,f3,e5,Nc6,bxc6,Bxc5,Rd8,Kf2,Be6,Rhd1,Nd7,Be3,Bf8,Rd2,f5,Rad1,Be7,g3,Kf7,b3,a5,Rc2,Nf6,Rxd8,Rxd8,exf5,gxf5,Na4,Bd5,Bb6,Ra8,Bc5,Nd7,Bxe7,Kxe7,Ke3,Kd6,Bd3,f4+,gxf4,exf4+,Kxf4,Rf8+,Kg5,Ne5,Bxh7,Nxf3+,Kh6,Rf4 → Re2 WHITE_TO_MOVE [] *
a105a4be99e4416f4f3e0b5609d67ba0: d4,Nf6,Nf3,g6,c4,Bg7,Nc3,d5,Qb3,dxc4,Qxc4,O-O,e4,a6,Qb3,c5,dxc5,Qa5,Qb6,Qxb6,cxb6,Nbd7,Be2,Nxb6,Be3,Nbd7,Nd4,Nc5,f3,e5,Nc6,bxc6,Bxc5,Rd8,Kf2,Be6,Rhd1,Nd7,Be3,Bf8,Rd2,f5,Rad1,Be7,g3,Kf7,b3,a5,Rc2,Nf6,Rxd8,Rxd8,exf5,gxf5,Na4,Bd5,Bb6,Ra8,Bc5,Nd7,Bxe7,Kxe7,Ke3,Kd6,Bd3,f4+,gxf4,exf4+,Kxf4,Rf8+,Kg5,Ne5,Bxh7,Nxf3+,Kh6,Rf4,Re2 → Rh4+ BLACK_TO_MOVE [] *
3c085a6443d4a472f7267febe15db4c8: d4,Nf6,Nf3,g6,c4,Bg7,Nc3,d5,Qb3,dxc4,Qxc4,O-O,e4,a6,Qb3,c5,dxc5,Qa5,Qb6,Qxb6,cxb6,Nbd7,Be2,Nxb6,Be3,Nbd7,Nd4,Nc5,f3,e5,Nc6,bxc6,Bxc5,Rd8,Kf2,Be6,Rhd1,Nd7,Be3,Bf8,Rd2,f5,Rad1,Be7,g3,Kf7,b3,a5,Rc2,Nf6,Rxd8,Rxd8,exf5,gxf5,Na4,Bd5,Bb6,Ra8,Bc5,Nd7,Bxe7,Kxe7,Ke3,Kd6,Bd3,f4+,gxf4,exf4+,Kxf4,Rf8+,Kg5,Ne5,Bxh7,Nxf3+,Kh6,Rf4,Re2,Rh4+ → Kg7 CHECK|WHITE_TO_MOVE [] *
2ab150343e14b506d36457929380577e: d4,Nf6,Nf3,g6,c4,Bg7,Nc3,d5,Qb3,dxc4,Qxc4,O-O,e4,a6,Qb3,c5,dxc5,Qa5,Qb6,Qxb6,cxb6,Nbd7,Be2,Nxb6,Be3,Nbd7,Nd4,Nc5,f3,e5,Nc6,bxc6,Bxc5,Rd8,Kf2,Be6,Rhd1,Nd7,Be3,Bf8,Rd2,f5,Rad1,Be7,g3,Kf7,b3,a5,Rc2,Nf6,Rxd8,Rxd8,exf5,gxf5,Na4,Bd5,Bb6,Ra8,Bc5,Nd7,Bxe7,Kxe7,Ke3,Kd6,Bd3,f4+,gxf4,exf4+,Kxf4,Rf8+,Kg5,Ne5,Bxh7,Nxf3+,Kh6,Rf4,Re2,Rh4+,Kg7 → Nxh2 BLACK_TO_MOVE [] *
5666c567fec9921dc32ac7d07b448bee: d4,Nf6,Nf3,g6,c4,Bg7,Nc3,d5,Qb3,dxc4,Qxc4,O-O,e4,a6,Qb3,c5,dxc5,Qa5,Qb6,Qxb6,cxb6,Nbd7,Be2,Nxb6,Be3,Nbd7,Nd4,Nc5,f3,e5,Nc6,bxc6,Bxc5,Rd8,Kf2,Be6,Rhd1,Nd7,Be3,Bf8,Rd2,f5,Rad1,Be7,g3,Kf7,b3,a5,Rc2,Nf6,Rxd8,Rxd8,exf5,gxf5,Na4,Bd5,Bb6,Ra8,Bc5,Nd7,Bxe7,Kxe7,Ke3,Kd6,Bd3,f4+,gxf4,exf4+,Kxf4,Rf8+,Kg5,Ne5,Bxh7,Nxf3+,Kh6,Rf4,Re2,Rh4+,Kg7,Nxh2 → Nc3 WHITE_TO_MOVE [] *
fb260d4272bc65eafef09f11469fff49: d4,Nf6,Nf3,g6,c4,Bg7,Nc3,d5,Qb3,dxc4,Qxc4,O-O,e4,a6,Qb3,c5,dxc5,Qa5,Qb6,Qxb6,cxb6,Nbd7,Be2,Nxb6,Be3,Nbd7,Nd4,Nc5,f3,e5,Nc6,bxc6,Bxc5,Rd8,Kf2,Be6,Rhd1,Nd7,Be3,Bf8,Rd2,f5,Rad1,Be7,g3,Kf7,b3,a5,Rc2,Nf6,Rxd8,Rxd8,exf5,gxf5,Na4,Bd5,Bb6,Ra8,Bc5,Nd7,Bxe7,Kxe7,Ke3,Kd6,Bd3,f4+,gxf4,exf4+,Kxf4,Rf8+,Kg5,Ne5,Bxh7,Nxf3+,Kh6,Rf4,Re2,Rh4+,Kg7,Nxh2,Nc3 → Nf3 BLACK_TO_MOVE [] *
f09659da87c463d5a0414951e34640ee: d4,Nf6,Nf3,g6,c4,Bg7,Nc3,d5,Qb3,dxc4,Qxc4,O-O,e4,a6,Qb3,c5,dxc5,Qa5,Qb6,Qxb6,cxb6,Nbd7,Be2,Nxb6,Be3,Nbd7,Nd4,Nc5,f3,e5,Nc6,bxc6,Bxc5,Rd8,Kf2,Be6,Rhd1,Nd7,Be3,Bf8,Rd2,f5,Rad1,Be7,g3,Kf7,b3,a5,Rc2,Nf6,Rxd8,Rxd8,exf5,gxf5,Na4,Bd5,Bb6,Ra8,Bc5,Nd7,Bxe7,Kxe7,Ke3,Kd6,Bd3,f4+,gxf4,exf4+,Kxf4,Rf8+,Kg5,Ne5,Bxh7,Nxf3+,Kh6,Rf4,Re2,Rh4+,Kg7,Nxh2,Nc3,Nf3 → Ne4+ WHITE_TO_MOVE [] *
0de70a376f108a052e4d1b585e72a670: d4,Nf6,Nf3,g6,c4,Bg7,Nc3,d5,Qb3,dxc4,Qxc4,O-O,e4,a6,Qb3,c5,dxc5,Qa5,Qb6,Qxb6,cxb6,Nbd7,Be2,Nxb6,Be3,Nbd7,Nd4,Nc5,f3,e5,Nc6,bxc6,Bxc5,Rd8,Kf2,Be6,Rhd1,Nd7,Be3,Bf8,Rd2,f5,Rad1,Be7,g3,Kf7,b3,a5,Rc2,Nf6,Rxd8,Rxd8,exf5,gxf5,Na4,Bd5,Bb6,Ra8,Bc5,Nd7,Bxe7,Kxe7,Ke3,Kd6,Bd3,f4+,gxf4,exf4+,Kxf4,Rf8+,Kg5,Ne5,Bxh7,Nxf3+,Kh6,Rf4,Re2,Rh4+,Kg7,Nxh2,Nc3,Nf3,Ne4+ → Kc7 CHECK|BLACK_TO_MOVE [] *
ac93633b8208e924a7ebbbaac50d94a6: d4,Nf6,Nf3,g6,c4,Bg7,Nc3,d5,Qb3,dxc4,Qxc4,O-O,e4,a6,Qb3,c5,dxc5,Qa5,Qb6,Qxb6,cxb6,Nbd7,Be2,Nxb6,Be3,Nbd7,Nd4,Nc5,f3,e5,Nc6,bxc6,Bxc5,Rd8,Kf2,Be6,Rhd1,Nd7,Be3,Bf8,Rd2,f5,Rad1,Be7,g3,Kf7,b3,a5,Rc2,Nf6,Rxd8,Rxd8,exf5,gxf5,Na4,Bd5,Bb6,Ra8,Bc5,Nd7,Bxe7,Kxe7,Ke3,Kd6,Bd3,f4+,gxf4,exf4+,Kxf4,Rf8+,Kg5,Ne5,Bxh7,Nxf3+,Kh6,Rf4,Re2,Rh4+,Kg7,Nxh2,Nc3,Nf3,Ne4+,Kc7 → Nf6 WHITE_TO_MOVE [] *
fa1e05e6128d5b759fda6667b22fd3b0: d4,Nf6,Nf3,g6,c4,Bg7,Nc3,d5,Qb3,dxc4,Qxc4,O-O,e4,a6,Qb3,c5,dxc5,Qa5,Qb6,Qxb6,cxb6,Nbd7,Be2,Nxb6,Be3,Nbd7,Nd4,Nc5,f3,e5,Nc6,bxc6,Bxc5,Rd8,Kf2,Be6,Rhd1,Nd7,Be3,Bf8,Rd2,f5,Rad1,Be7,g3,Kf7,b3,a5,Rc2,Nf6,Rxd8,Rxd8,exf5,gxf5,Na4,Bd5,Bb6,Ra8,Bc5,Nd7,Bxe7,Kxe7,Ke3,Kd6,Bd3,f4+,gxf4,exf4+,Kxf4,Rf8+,Kg5,Ne5,Bxh7,Nxf3+,Kh6,Rf4,Re2,Rh4+,Kg7,Nxh2,Nc3,Nf3,Ne4+,Kc7,Nf6 → Nd4 BLACK_TO_MOVE [] *
8dd4f6f5dcf63407e710dab41646192e: d4,Nf6,Nf3,g6,c4,Bg7,Nc3,d5,Qb3,dxc4,Qxc4,O-O,e4,a6,Qb3,c5,dxc5,Qa5,Qb6,Qxb6,cxb6,Nbd7,Be2,Nxb6,Be3,Nbd7,Nd4,Nc5,f3,e5,Nc6,bxc6,Bxc5,Rd8,Kf2,Be6,Rhd1,Nd7,Be3,Bf8,Rd2,f5,Rad1,Be7,g3,Kf7,b3,a5,Rc2,Nf6,Rxd8,Rxd8,exf5,gxf5,Na4,Bd5,Bb6,Ra8,Bc5,Nd7,Bxe7,Kxe7,Ke3,Kd6,Bd3,f4+,gxf4,exf4+,Kxf4,Rf8+,Kg5,Ne5,Bxh7,Nxf3+,Kh6,Rf4,Re2,Rh4+,Kg7,Nxh2,Nc3,Nf3,Ne4+,Kc7,Nf6,Nd4 → Nxd5+ WHITE_TO_MOVE [] *
1db4a4e0a0410345ece8169e592113ed: d4,Nf6,Nf3,g6,c4,Bg7,Nc3,d5,Qb3,dxc4,Qxc4,O-O,e4,a6,Qb3,c5,dxc5,Qa5,Qb6,Qxb6,cxb6,Nbd7,Be2,Nxb6,Be3,Nbd7,Nd4,Nc5,f3,e5,Nc6,bxc6,Bxc5,Rd8,Kf2,Be6,Rhd1,Nd7,Be3,Bf8,Rd2,f5,Rad1,Be7,g3,Kf7,b3,a5,Rc2,Nf6,Rxd8,Rxd8,exf5,gxf5,Na4,Bd5,Bb6,Ra8,Bc5,Nd7,Bxe7,Kxe7,Ke3,Kd6,Bd3,f4+,gxf4,exf4+,Kxf4,Rf8+,Kg5,Ne5,Bxh7,Nxf3+,Kh6,Rf4,Re2,Rh4+,Kg7,Nxh2,Nc3,Nf3,Ne4+,Kc7,Nf6,Nd4,Nxd5+ → cxd5 CHECK|BLACK_TO_MOVE [] *
7d0750f94d4ac9ee81eb989cb2eb95e2: d4,Nf6,Nf3,g6,c4,Bg7,Nc3,d5,Qb3,dxc4,Qxc4,O-O,e4,a6,Qb3,c5,dxc5,Qa5,Qb6,Qxb6,cxb6,Nbd7,Be2,Nxb6,Be3,Nbd7,Nd4,Nc5,f3,e5,Nc6,bxc6,Bxc5,Rd8,Kf2,Be6,Rhd1,Nd7,Be3,Bf8,Rd2,f5,Rad1,Be7,g3,Kf7,b3,a5,Rc2,Nf6,Rxd8,Rxd8,exf5,gxf5,Na4,Bd5,Bb6,Ra8,Bc5,Nd7,Bxe7,Kxe7,Ke3,Kd6,Bd3,f4+,gxf4,exf4+,Kxf4,Rf8+,Kg5,Ne5,Bxh7,Nxf3+,Kh6,Rf4,Re2,Rh4+,Kg7,Nxh2,Nc3,Nf3,Ne4+,Kc7,Nf6,Nd4,Nxd5+,cxd5 → Rd2 WHITE_TO_MOVE [] *
5ef4c48b53860650c6729d64b0af2e51: d4,Nf6,Nf3,g6,c4,Bg7,Nc3,d5,Qb3,dxc4,Qxc4,O-O,e4,a6,Qb3,c5,dxc5,Qa5,Qb6,Qxb6,cxb6,Nbd7,Be2,Nxb6,Be3,Nbd7,Nd4,Nc5,f3,e5,Nc6,bxc6,Bxc5,Rd8,Kf2,Be6,Rhd1,Nd7,Be3,Bf8,Rd2,f5,Rad1,Be7,g3,Kf7,b3,a5,Rc2,Nf6,Rxd8,Rxd8,exf5,gxf5,Na4,Bd5,Bb6,Ra8,Bc5,Nd7,Bxe7,Kxe7,Ke3,Kd6,Bd3,f4+,gxf4,exf4+,Kxf4,Rf8+,Kg5,Ne5,Bxh7,Nxf3+,Kh6,Rf4,Re2,Rh4+,Kg7,Nxh2,Nc3,Nf3,Ne4+,Kc7,Nf6,Nd4,Nxd5+,cxd5,Rd2 → Kd6 BLACK_TO_MOVE [] *
ff80ad87be9e65714fd43d962bd01c87: d4,Nf6,Nf3,g6,c4,Bg7,Nc3,d5,Qb3,dxc4,Qxc4,O-O,e4,a6,Qb3,c5,dxc5,Qa5,Qb6,Qxb6,cxb6,Nbd7,Be2,Nxb6,Be3,Nbd7,Nd4,Nc5,f3,e5,Nc6,bxc6,Bxc5,Rd8,Kf2,Be6,Rhd1,Nd7,Be3,Bf8,Rd2,f5,Rad1,Be7,g3,Kf7,b3,a5,Rc2,Nf6,Rxd8,Rxd8,exf5,gxf5,Na4,Bd5,Bb6,Ra8,Bc5,Nd7,Bxe7,Kxe7,Ke3,Kd6,Bd3,f4+,gxf4,exf4+,Kxf4,Rf8+,Kg5,Ne5,Bxh7,Nxf3+,Kh6,Rf4,Re2,Rh4+,Kg7,Nxh2,Nc3,Nf3,Ne4+,Kc7,Nf6,Nd4,Nxd5+,cxd5,Rd2,Kd6 → Bd3 WHITE_TO_MOVE [] *
86c96291cf7d41a7a1b5a5469bacbdd4: d4,Nf6,Nf3,g6,c4,Bg7,Nc3,d5,Qb3,dxc4,Qxc4,O-O,e4,a6,Qb3,c5,dxc5,Qa5,Qb6,Qxb6,cxb6,Nbd7,Be2,Nxb6,Be3,Nbd7,Nd4,Nc5,f3,e5,Nc6,bxc6,Bxc5,Rd8,Kf2,Be6,Rhd1,Nd7,Be3,Bf8,Rd2,f5,Rad1,Be7,g3,Kf7,b3,a5,Rc2,Nf6,Rxd8,Rxd8,exf5,gxf5,Na4,Bd5,Bb6,Ra8,Bc5,Nd7,Bxe7,Kxe7,Ke3,Kd6,Bd3,f4+,gxf4,exf4+,Kxf4,Rf8+,Kg5,Ne5,Bxh7,Nxf3+,Kh6,Rf4,Re2,Rh4+,Kg7,Nxh2,Nc3,Nf3,Ne4+,Kc7,Nf6,Nd4,Nxd5+,cxd5,Rd2,Kd6,Bd3 → Ne6+ BLACK_TO_MOVE [] *
402f0ff5e62234c38e3111ce2d4ec75c: d4,Nf6,Nf3,g6,c4,Bg7,Nc3,d5,Qb3,dxc4,Qxc4,O-O,e4,a6,Qb3,c5,dxc5,Qa5,Qb6,Qxb6,cxb6,Nbd7,Be2,Nxb6,Be3,Nbd7,Nd4,Nc5,f3,e5,Nc6,bxc6,Bxc5,Rd8,Kf2,Be6,Rhd1,Nd7,Be3,Bf8,Rd2,f5,Rad1,Be7,g3,Kf7,b3,a5,Rc2,Nf6,Rxd8,Rxd8,exf5,gxf5,Na4,Bd5,Bb6,Ra8,Bc5,Nd7,Bxe7,Kxe7,Ke3,Kd6,Bd3,f4+,gxf4,exf4+,Kxf4,Rf8+,Kg5,Ne5,Bxh7,Nxf3+,Kh6,Rf4,Re2,Rh4+,Kg7,Nxh2,Nc3,Nf3,Ne4+,Kc7,Nf6,Nd4,Nxd5+,cxd5,Rd2,Kd6,Bd3,Ne6+ → Kf6 CHECK|WHITE_TO_MOVE [] *
1136237cfcd1ece35b36fc50f267d2d3: d4,Nf6,Nf3,g6,c4,Bg7,Nc3,d5,Qb3,dxc4,Qxc4,O-O,e4,a6,Qb3,c5,dxc5,Qa5,Qb6,Qxb6,cxb6,Nbd7,Be2,Nxb6,Be3,Nbd7,Nd4,Nc5,f3,e5,Nc6,bxc6,Bxc5,Rd8,Kf2,Be6,Rhd1,Nd7,Be3,Bf8,Rd2,f5,Rad1,Be7,g3,Kf7,b3,a5,Rc2,Nf6,Rxd8,Rxd8,exf5,gxf5,Na4,Bd5,Bb6,Ra8,Bc5,Nd7,Bxe7,Kxe7,Ke3,Kd6,Bd3,f4+,gxf4,exf4+,Kxf4,Rf8+,Kg5,Ne5,Bxh7,Nxf3+,Kh6,Rf4,Re2,Rh4+,Kg7,Nxh2,Nc3,Nf3,Ne4+,Kc7,Nf6,Nd4,Nxd5+,cxd5,Rd2,Kd6,Bd3,Ne6+,Kf6 → Rf4+ BLACK_TO_MOVE [] *
8c3bdda626e109fee32e88ed1aec1dbb: d4,Nf6,Nf3,g6,c4,Bg7,Nc3,d5,Qb3,dxc4,Qxc4,O-O,e4,a6,Qb3,c5,dxc5,Qa5,Qb6,Qxb6,cxb6,Nbd7,Be2,Nxb6,Be3,Nbd7,Nd4,Nc5,f3,e5,Nc6,bxc6,Bxc5,Rd8,Kf2,Be6,Rhd1,Nd7,Be3,Bf8,Rd2,f5,Rad1,Be7,g3,Kf7,b3,a5,Rc2,Nf6,Rxd8,Rxd8,exf5,gxf5,Na4,Bd5,Bb6,Ra8,Bc5,Nd7,Bxe7,Kxe7,Ke3,Kd6,Bd3,f4+,gxf4,exf4+,Kxf4,Rf8+,Kg5,Ne5,Bxh7,Nxf3+,Kh6,Rf4,Re2,Rh4+,Kg7,Nxh2,Nc3,Nf3,Ne4+,Kc7,Nf6,Nd4,Nxd5+,cxd5,Rd2,Kd6,Bd3,Ne6+,Kf6,Rf4+ → * CHECK|WHITE_TO_MOVE [] 4/Bf5/-1.3
    418073579eabddec4b5a9c740b59f00b24842b6cbf2921f569ce7100b37d01b1: {'event': 'Fujitsu Siemens Giants', 'site': 'Frankfurt', 'date': '2000.06.24', 'round': '7', 'white': 'Kasparov, Garry', 'black': 'Leko, Peter', 'result': '0-1', 'whiteelo': '2851', 'blackelo': '2725', 'eco': 'D97', 'eventdate': '2000.06.22'}
4120eba626683215de17b17bce03a612: d4,d5 (D00/Queen's Pawn Game) → c4 WHITE_TO_MOVE [] *
7933bb68e77d6e607b6996c09a7304d4: d4,d5,c4 (D06/Queen's Gambit) → Nc6 BLACK_TO_MOVE [] *
7498a07ab727a5b3be09865a36aafc95: d4,d5,c4,Nc6 (D07/Queen's Gambit Declined: Chigorin Defense) → Nf3 WHITE_TO_MOVE [] *
55a721b193714647921792f1f1521884: d4,d5,c4,Nc6,Nf3 → Bg4 BLACK_TO_MOVE [] *
b914cea9864fce01f3932c9531d208b2: d4,d5,c4,Nc6,Nf3,Bg4 (D07/Queen's Gambit Declined: Chigorin Defense, Main Line) → Nc3 WHITE_TO_MOVE [] *
3d8f473650d818128d524b59636b94a1: d4,d5,c4,Nc6,Nf3,Bg4,Nc3 → Nf6 BLACK_TO_MOVE [] *
69add3fb4abfa98d3bc37ffe34417677: d4,d5,c4,Nc6,Nf3,Bg4,Nc3,Nf6 → cxd5 WHITE_TO_MOVE [] *
82964517f7f86b0793c616d16d908548: d4,d5,c4,Nc6,Nf3,Bg4,Nc3,Nf6,cxd5 → Bxf3 BLACK_TO_MOVE [] *
879985aa9880511dd3a601e23a07cd2e: d4,d5,c4,Nc6,Nf3,Bg4,Nc3,Nf6,cxd5,Bxf3 → gxf3 WHITE_TO_MOVE [] *
36d55f4f80ff2a609419283df651abad: d4,d5,c4,Nc6,Nf3,Bg4,Nc3,Nf6,cxd5,Bxf3,gxf3 → Nxd5 BLACK_TO_MOVE [] *
0a64459751fee3e6fc66c99d41595d5f: d4,d5,c4,Nc6,Nf3,Bg4,Nc3,Nf6,cxd5,Bxf3,gxf3,Nxd5 → e4 WHITE_TO_MOVE [] *
16fb4efb0501a17a0644949cb70a3c00: d4,d5,c4,Nc6,Nf3,Bg4,Nc3,Nf6,cxd5,Bxf3,gxf3,Nxd5,e4 → Nb6 BLACK_TO_MOVE [] *
566cecdd36f2ab7567c6c0238cd1b950: d4,d5,c4,Nc6,Nf3,Bg4,Nc3,Nf6,cxd5,Bxf3,gxf3,Nxd5,e4,Nb6 → d5 WHITE_TO_MOVE [] *
7e73fb197ed36962fceffe78fa419b40: d4,d5,c4,Nc6,Nf3,Bg4,Nc3,Nf6,cxd5,Bxf3,gxf3,Nxd5,e4,Nb6,d5 → Ne5 BLACK_TO_MOVE [] *
85d3c78abbf67016a2bd6a6eac386d18: d4,d5,c4,Nc6,Nf3,Bg4,Nc3,Nf6,cxd5,Bxf3,gxf3,Nxd5,e4,Nb6,d5,Ne5 → f4 WHITE_TO_MOVE [] *
8c4d4c7bbb54b6dcb4f41f8d4cf9de9a: d4,d5,c4,Nc6,Nf3,Bg4,Nc3,Nf6,cxd5,Bxf3,gxf3,Nxd5,e4,Nb6,d5,Ne5,f4 → Ned7 BLACK_TO_MOVE [] *
cfca070fe3c9507bc54aa6eba8bf41b2: d4,d5,c4,Nc6,Nf3,Bg4,Nc3,Nf6,cxd5,Bxf3,gxf3,Nxd5,e4,Nb6,d5,Ne5,f4,Ned7 → a4 WHITE_TO_MOVE [] *
cb3f5ed7876d9f2067386c33b43ff385: d4,d5,c4,Nc6,Nf3,Bg4,Nc3,Nf6,cxd5,Bxf3,gxf3,Nxd5,e4,Nb6,d5,Ne5,f4,Ned7,a4 → c6 BLACK_TO_MOVE [] *
efb4ebaaabb7f2500dec00973fcd71e0: d4,d5,c4,Nc6,Nf3,Bg4,Nc3,Nf6,cxd5,Bxf3,gxf3,Nxd5,e4,Nb6,d5,Ne5,f4,Ned7,a4,c6 → a5 WHITE_TO_MOVE [] *
b0fb10cda725f10b965f7c8a9c24d175: d4,d5,c4,Nc6,Nf3,Bg4,Nc3,Nf6,cxd5,Bxf3,gxf3,Nxd5,e4,Nb6,d5,Ne5,f4,Ned7,a4,c6,a5 → Nc8 BLACK_TO_MOVE [] *
00262153dd8f1fded75d3f45d4e911cc: d4,d5,c4,Nc6,Nf3,Bg4,Nc3,Nf6,cxd5,Bxf3,gxf3,Nxd5,e4,Nb6,d5,Ne5,f4,Ned7,a4,c6,a5,Nc8 → a6 WHITE_TO_MOVE [] *
9a90fe5136106dc0649dda19efe84b01: d4,d5,c4,Nc6,Nf3,Bg4,Nc3,Nf6,cxd5,Bxf3,gxf3,Nxd5,e4,Nb6,d5,Ne5,f4,Ned7,a4,c6,a5,Nc8,a6 → Qc7 BLACK_TO_MOVE [] *
a3044bf666d03e4d9a4f254b830eeec5: d4,d5,c4,Nc6,Nf3,Bg4,Nc3,Nf6,cxd5,Bxf3,gxf3,Nxd5,e4,Nb6,d5,Ne5,f4,Ned7,a4,c6,a5,Nc8,a6,Qc7 → axb7 WHITE_TO_MOVE [] *
13ed1b2b471c78ada456a11e35243e70: d4,d5,c4,Nc6,Nf3,Bg4,Nc3,Nf6,cxd5,Bxf3,gxf3,Nxd5,e4,Nb6,d5,Ne5,f4,Ned7,a4,c6,a5,Nc8,a6,Qc7,axb7 → Qxb7 BLACK_TO_MOVE [] *
6ec9c5a0ff8c03bafc0fdd297d40a21e: d4,d5,c4,Nc6,Nf3,Bg4,Nc3,Nf6,cxd5,Bxf3,gxf3,Nxd5,e4,Nb6,d5,Ne5,f4,Ned7,a4,c6,a5,Nc8,a6,Qc7,axb7,Qxb7 → Ba6 WHITE_TO_MOVE [] *
baf410aeb7daeda3688bd8435f52f550: d4,d5,c4,Nc6,Nf3,Bg4,Nc3,Nf6,cxd5,Bxf3,gxf3,Nxd5,e4,Nb6,d5,Ne5,f4,Ned7,a4,c6,a5,Nc8,a6,Qc7,axb7,Qxb7,Ba6 → Qc7 BLACK_TO_MOVE [] *
b45ecfce61cdf1d03ec959fcf4093a4f: d4,d5,c4,Nc6,Nf3,Bg4,Nc3,Nf6,cxd5,Bxf3,gxf3,Nxd5,e4,Nb6,d5,Ne5,f4,Ned7,a4,c6,a5,Nc8,a6,Qc7,axb7,Qxb7,Ba6,Qc7 → Qa4 WHITE_TO_MOVE [] *
0511babccca6e4a801d7bf11361b7f96: d4,d5,c4,Nc6,Nf3,Bg4,Nc3,Nf6,cxd5,Bxf3,gxf3,Nxd5,e4,Nb6,d5,Ne5,f4,Ned7,a4,c6,a5,Nc8,a6,Qc7,axb7,Qxb7,Ba6,Qc7,Qa4 → cxd5 BLACK_TO_MOVE [] *
0f2670a551763ed8638d00ce5e4ec941: d4,d5,c4,Nc6,Nf3,Bg4,Nc3,Nf6,cxd5,Bxf3,gxf3,Nxd5,e4,Nb6,d5,Ne5,f4,Ned7,a4,c6,a5,Nc8,a6,Qc7,axb7,Qxb7,Ba6,Qc7,Qa4,cxd5 → Nxd5 WHITE_TO_MOVE [] *
bf05ea858091bd27a47dc354ddd93dc0: d4,d5,c4,Nc6,Nf3,Bg4,Nc3,Nf6,cxd5,Bxf3,gxf3,Nxd5,e4,Nb6,d5,Ne5,f4,Ned7,a4,c6,a5,Nc8,a6,Qc7,axb7,Qxb7,Ba6,Qc7,Qa4,cxd5,Nxd5 → Qd6 BLACK_TO_MOVE [] *
849b4810d6a9542c386dbb8b4b84283a: d4,d5,c4,Nc6,Nf3,Bg4,Nc3,Nf6,cxd5,Bxf3,gxf3,Nxd5,e4,Nb6,d5,Ne5,f4,Ned7,a4,c6,a5,Nc8,a6,Qc7,axb7,Qxb7,Ba6,Qc7,Qa4,cxd5,Nxd5,Qd6 → Bb7 WHITE_TO_MOVE [] *
cfc304cdbfecd61129fcefeb6175af3a: d4,d5,c4,Nc6,Nf3,Bg4,Nc3,Nf6,cxd5,Bxf3,gxf3,Nxd5,e4,Nb6,d5,Ne5,f4,Ned7,a4,c6,a5,Nc8,a6,Qc7,axb7,Qxb7,Ba6,Qc7,Qa4,cxd5,Nxd5,Qd6,Bb7 → Rb8 BLACK_TO_MOVE [] *
59842a83b670b35e69ec67be3a603850: d4,d5,c4,Nc6,Nf3,Bg4,Nc3,Nf6,cxd5,Bxf3,gxf3,Nxd5,e4,Nb6,d5,Ne5,f4,Ned7,a4,c6,a5,Nc8,a6,Qc7,axb7,Qxb7,Ba6,Qc7,Qa4,cxd5,Nxd5,Qd6,Bb7,Rb8 → e5 WHITE_TO_MOVE [] *
b095efec4f7ee27eccf5257d43495c77: d4,d5,c4,Nc6,Nf3,Bg4,Nc3,Nf6,cxd5,Bxf3,gxf3,Nxd5,e4,Nb6,d5,Ne5,f4,Ned7,a4,c6,a5,Nc8,a6,Qc7,axb7,Qxb7,Ba6,Qc7,Qa4,cxd5,Nxd5,Qd6,Bb7,Rb8,e5 → Nb6 BLACK_TO_MOVE [] *
0048de7235d40cab8df766b20b849cce: d4,d5,c4,Nc6,Nf3,Bg4,Nc3,Nf6,cxd5,Bxf3,gxf3,Nxd5,e4,Nb6,d5,Ne5,f4,Ned7,a4,c6,a5,Nc8,a6,Qc7,axb7,Qxb7,Ba6,Qc7,Qa4,cxd5,Nxd5,Qd6,Bb7,Rb8,e5,Nb6 → Qxa7 WHITE_TO_MOVE [] *
4e85e0eb9bfcb31e8bab6550001b1e35: d4,d5,c4,Nc6,Nf3,Bg4,Nc3,Nf6,cxd5,Bxf3,gxf3,Nxd5,e4,Nb6,d5,Ne5,f4,Ned7,a4,c6,a5,Nc8,a6,Qc7,axb7,Qxb7,Ba6,Qc7,Qa4,cxd5,Nxd5,Qd6,Bb7,Rb8,e5,Nb6,Qxa7 → Rxb7 BLACK_TO_MOVE [] *
2c82dc052a9aab3e6814294d7da1d3af: d4,d5,c4,Nc6,Nf3,Bg4,Nc3,Nf6,cxd5,Bxf3,gxf3,Nxd5,e4,Nb6,d5,Ne5,f4,Ned7,a4,c6,a5,Nc8,a6,Qc7,axb7,Qxb7,Ba6,Qc7,Qa4,cxd5,Nxd5,Qd6,Bb7,Rb8,e5,Nb6,Qxa7,Rxb7 → Qxb7 WHITE_TO_MOVE [] *
fe3fb35bbb308617137f00e4d797a49e: d4,d5,c4,Nc6,Nf3,Bg4,Nc3,Nf6,cxd5,Bxf3,gxf3,Nxd5,e4,Nb6,d5,Ne5,f4,Ned7,a4,c6,a5,Nc8,a6,Qc7,axb7,Qxb7,Ba6,Qc7,Qa4,cxd5,Nxd5,Qd6,Bb7,Rb8,e5,Nb6,Qxa7,Rxb7,Qxb7 → Qxd5 BLACK_TO_MOVE [] *
252ed75839a4e16b070607a93f307df5: d4,d5,c4,Nc6,Nf3,Bg4,Nc3,Nf6,cxd5,Bxf3,gxf3,Nxd5,e4,Nb6,d5,Ne5,f4,Ned7,a4,c6,a5,Nc8,a6,Qc7,axb7,Qxb7,Ba6,Qc7,Qa4,cxd5,Nxd5,Qd6,Bb7,Rb8,e5,Nb6,Qxa7,Rxb7,Qxb7,Qxd5 → Ra8+ WHITE_TO_MOVE [] *
9b34fbf8404bd61067c273c086700b10: d4,d5,c4,Nc6,Nf3,Bg4,Nc3,Nf6,cxd5,Bxf3,gxf3,Nxd5,e4,Nb6,d5,Ne5,f4,Ned7,a4,c6,a5,Nc8,a6,Qc7,axb7,Qxb7,Ba6,Qc7,Qa4,cxd5,Nxd5,Qd6,Bb7,Rb8,e5,Nb6,Qxa7,Rxb7,Qxb7,Qxd5,Ra8+ → Nxa8 CHECK|BLACK_TO_MOVE [] *
d96807d158418c745f49a3df067392d3: d4,d5,c4,Nc6,Nf3,Bg4,Nc3,Nf6,cxd5,Bxf3,gxf3,Nxd5,e4,Nb6,d5,Ne5,f4,Ned7,a4,c6,a5,Nc8,a6,Qc7,axb7,Qxb7,Ba6,Qc7,Qa4,cxd5,Nxd5,Qd6,Bb7,Rb8,e5,Nb6,Qxa7,Rxb7,Qxb7,Qxd5,Ra8+,Nxa8 → Qc8# WHITE_TO_MOVE [] *
31c2be39c829ed1333a06ba59ba042c5: d4,d5,c4,Nc6,Nf3,Bg4,Nc3,Nf6,cxd5,Bxf3,gxf3,Nxd5,e4,Nb6,d5,Ne5,f4,Ned7,a4,c6,a5,Nc8,a6,Qc7,axb7,Qxb7,Ba6,Qc7,Qa4,cxd5,Nxd5,Qd6,Bb7,Rb8,e5,Nb6,Qxa7,Rxb7,Qxb7,Qxd5,Ra8+,Nxa8,Qc8# → * CHECKMATE|CHECK|BLACK_TO_MOVE [] 4/*/*
    d2e70b8aa5283c95601827c6b5a6d3badac3a7080ade26fe681cc4614ca0942d: {'event': 'Bayern-chI Bank Hofmann 1st - wrong result', 'site': 'Bad Wiessee', 'date': '1997.11.15', 'round': '1', 'white': 'Khalifman, Alexander', 'black': 'Kaftan, Thorsten', 'result': '1-0', 'whiteelo': '2655', 'eco': 'D07', 'eventdate': '1997.11.15'}
29ef15aedfe816adc027717c5e3e4d03: d4,e6 (A40/Horwitz Defense) → c4 WHITE_TO_MOVE [] *
11fc45601efd4ad8655956c70a4eefc5: d4,e6,c4 → b6 BLACK_TO_MOVE [] *
2d83f8797c048132b55f995992b8452a: d4,e6,c4,b6 (A40/English Defense) → a3 WHITE_TO_MOVE [] 4/a3/0.79
    574e26d3c87508cd3ec98a1fcc05b1815431e738efc6944c0f1274190b524a0b: {'event': 'basic-dup', 'date': '2010.06.23', 'white': 'Aaa', 'black': 'CCC, Bbb', 'result': '1/2-1/2'}
    a6ec2fc46ebe2bbf78407803ead96de277b94368fb332fabe8df9caa84c3bac7: {'event': 'basic', 'date': '2010.06.25', 'white': 'Aaa', 'black': 'Bbb Ccc', 'result': '1/2-1/2'}
    d7aefc371ec6cfc6b7e9afbbb0e0d1e5f78d1332a526dd3fbeed9511116501be: {'event': 'basic-nondup', 'date': '2010.06.24', 'white': 'Ddd', 'black': 'Bbb Ccc', 'result': '1/2-1/2'}
1e02d1acc62671467c0948d758bce039: d4,e6,c4,b6,a3 → Bb7 BLACK_TO_MOVE [] *
f35296432b2297ccf18de0ec8b54c057: d4,e6,c4,b6,a3,Bb7 → Nc3 WHITE_TO_MOVE [] *
77c91fdcfdb541df8f4c8720d9ed5c44: d4,e6,c4,b6,a3,Bb7,Nc3 → f5 BLACK_TO_MOVE [] *
a6973cf4dc569b4a38918919324911a8: d4,e6,c4,b6,a3,Bb7,Nc3,f5 → d5 WHITE_TO_MOVE [] *
8e882b309477595da3b8b74244d933b8: d4,e6,c4,b6,a3,Bb7,Nc3,f5,d5 → Nf6 BLACK_TO_MOVE [] *
daaabffd8e10e8c2152983e513f3d16e: d4,e6,c4,b6,a3,Bb7,Nc3,f5,d5,Nf6 → g3 WHITE_TO_MOVE [] *
b1aa3b081236568788ec00faee8bb6ef: d4,e6,c4,b6,a3,Bb7,Nc3,f5,d5,Nf6,g3 → Na6 BLACK_TO_MOVE [] *
4265798efb171bd83fafd4c0fc9aff25: d4,e6,c4,b6,a3,Bb7,Nc3,f5,d5,Nf6,g3,Na6 → Bg2 WHITE_TO_MOVE [] *
e2b9a3cec83d87498a53e5f5f9b2eac2: d4,e6,c4,b6,a3,Bb7,Nc3,f5,d5,Nf6,g3,Na6,Bg2 → Nc5 BLACK_TO_MOVE [] *
b362143a6afcd0ff86b7fe4da309633e: d4,e6,c4,b6,a3,Bb7,Nc3,f5,d5,Nf6,g3,Na6,Bg2,Nc5 → Nh3 WHITE_TO_MOVE [] *
9256fa762036d27864ca24cbdc8ad494: d4,e6,c4,b6,a3,Bb7,Nc3,f5,d5,Nf6,g3,Na6,Bg2,Nc5,Nh3 → Bd6 BLACK_TO_MOVE [] *
b8c891bf62f03ab6b09c93b2965d7298: d4,e6,c4,b6,a3,Bb7,Nc3,f5,d5,Nf6,g3,Na6,Bg2,Nc5,Nh3,Bd6 → O-O WHITE_TO_MOVE [] *
faf1a2d7dcfea7d81bf31b4992525cb9: d4,e6,c4,b6,a3,Bb7,Nc3,f5,d5,Nf6,g3,Na6,Bg2,Nc5,Nh3,Bd6,O-O → Be5 BLACK_TO_MOVE [] *
c0c483d429c723ff71412cb48cde5f3c: d4,e6,c4,b6,a3,Bb7,Nc3,f5,d5,Nf6,g3,Na6,Bg2,Nc5,Nh3,Bd6,O-O,Be5 → Qc2 WHITE_TO_MOVE [] *
834bc26d14611bfa9a10129d96e6f4c2: d4,e6,c4,b6,a3,Bb7,Nc3,f5,d5,Nf6,g3,Na6,Bg2,Nc5,Nh3,Bd6,O-O,Be5,Qc2 → O-O BLACK_TO_MOVE [] *
79fe22a3f48e6e2c9a5f3418d2f565f7: d4,e6,c4,b6,a3,Bb7,Nc3,f5,d5,Nf6,g3,Na6,Bg2,Nc5,Nh3,Bd6,O-O,Be5,Qc2,O-O → Rd1 WHITE_TO_MOVE [] *
a3801ba231d3693c0e8475565375db15: d4,e6,c4,b6,a3,Bb7,Nc3,f5,d5,Nf6,g3,Na6,Bg2,Nc5,Nh3,Bd6,O-O,Be5,Qc2,O-O,Rd1 → Qe7 BLACK_TO_MOVE [] *
0bc2ef959c70c35670dfe9f56c8e8c2a: d4,e6,c4,b6,a3,Bb7,Nc3,f5,d5,Nf6,g3,Na6,Bg2,Nc5,Nh3,Bd6,O-O,Be5,Qc2,O-O,Rd1,Qe7 → Be3 WHITE_TO_MOVE [] *
d35900534a10c742015ff50f3cb85c94: d4,e6,c4,b6,a3,Bb7,Nc3,f5,d5,Nf6,g3,Na6,Bg2,Nc5,Nh3,Bd6,O-O,Be5,Qc2,O-O,Rd1,Qe7,Be3 → Rab8 BLACK_TO_MOVE [] *
432364afd6fe16770cf1386d4c81be99: d4,e6,c4,b6,a3,Bb7,Nc3,f5,d5,Nf6,g3,Na6,Bg2,Nc5,Nh3,Bd6,O-O,Be5,Qc2,O-O,Rd1,Qe7,Be3,Rab8 → Rac1 WHITE_TO_MOVE [] *
ca514f9b7863962edf1f41b7e517d342: d4,e6,c4,b6,a3,Bb7,Nc3,f5,d5,Nf6,g3,Na6,Bg2,Nc5,Nh3,Bd6,O-O,Be5,Qc2,O-O,Rd1,Qe7,Be3,Rab8,Rac1 → Nce4 BLACK_TO_MOVE [] *
93bd390dbc70004e61964a9030edde45: d4,e6,c4,b6,a3,Bb7,Nc3,f5,d5,Nf6,g3,Na6,Bg2,Nc5,Nh3,Bd6,O-O,Be5,Qc2,O-O,Rd1,Qe7,Be3,Rab8,Rac1,Nce4 → Nxe4 WHITE_TO_MOVE [] *
18d1e5afaa1cbfe28cb4bf171ae1309b: d4,e6,c4,b6,a3,Bb7,Nc3,f5,d5,Nf6,g3,Na6,Bg2,Nc5,Nh3,Bd6,O-O,Be5,Qc2,O-O,Rd1,Qe7,Be3,Rab8,Rac1,Nce4,Nxe4 → Nxe4 BLACK_TO_MOVE [] *
fa9f6f544f5f5999f2946effe1f7ead8: d4,e6,c4,b6,a3,Bb7,Nc3,f5,d5,Nf6,g3,Na6,Bg2,Nc5,Nh3,Bd6,O-O,Be5,Qc2,O-O,Rd1,Qe7,Be3,Rab8,Rac1,Nce4,Nxe4,Nxe4 → Nf4 WHITE_TO_MOVE [] *
68bf4655f1b5391fa43cd21f953283fa: d4,e6,c4,b6,a3,Bb7,Nc3,f5,d5,Nf6,g3,Na6,Bg2,Nc5,Nh3,Bd6,O-O,Be5,Qc2,O-O,Rd1,Qe7,Be3,Rab8,Rac1,Nce4,Nxe4,Nxe4,Nf4 → c5 BLACK_TO_MOVE [] *
fe3c48ca685daabfcdbd5e327139c882: d4,e6,c4,b6,a3,Bb7,Nc3,f5,d5,Nf6,g3,Na6,Bg2,Nc5,Nh3,Bd6,O-O,Be5,Qc2,O-O,Rd1,Qe7,Be3,Rab8,Rac1,Nce4,Nxe4,Nxe4,Nf4,c5 → dxc6 WHITE_TO_MOVE [] *
df130e77c13a4df637930233f759bdfc: d4,e6,c4,b6,a3,Bb7,Nc3,f5,d5,Nf6,g3,Na6,Bg2,Nc5,Nh3,Bd6,O-O,Be5,Qc2,O-O,Rd1,Qe7,Be3,Rab8,Rac1,Nce4,Nxe4,Nxe4,Nf4,c5,dxc6 → Bxc6 BLACK_TO_MOVE [] *
8858d9e20a50a465969ea13d75149035: d4,e6,c4,b6,a3,Bb7,Nc3,f5,d5,Nf6,g3,Na6,Bg2,Nc5,Nh3,Bd6,O-O,Be5,Qc2,O-O,Rd1,Qe7,Be3,Rab8,Rac1,Nce4,Nxe4,Nxe4,Nf4,c5,dxc6,Bxc6 → Nd3 WHITE_TO_MOVE [] *
f7736f876cdc09ffdff125c2e6d708c4: d4,e6,c4,b6,a3,Bb7,Nc3,f5,d5,Nf6,g3,Na6,Bg2,Nc5,Nh3,Bd6,O-O,Be5,Qc2,O-O,Rd1,Qe7,Be3,Rab8,Rac1,Nce4,Nxe4,Nxe4,Nf4,c5,dxc6,Bxc6,Nd3 → Bf6 BLACK_TO_MOVE [] *
7f7e600a74362c46330bddb07911cf3d: d4,e6,c4,b6,a3,Bb7,Nc3,f5,d5,Nf6,g3,Na6,Bg2,Nc5,Nh3,Bd6,O-O,Be5,Qc2,O-O,Rd1,Qe7,Be3,Rab8,Rac1,Nce4,Nxe4,Nxe4,Nf4,c5,dxc6,Bxc6,Nd3,Bf6 → f3 WHITE_TO_MOVE [] *
f66e64ed1148e0db6c5c2c13e2fd5eae: d4,e6,c4,b6,a3,Bb7,Nc3,f5,d5,Nf6,g3,Na6,Bg2,Nc5,Nh3,Bd6,O-O,Be5,Qc2,O-O,Rd1,Qe7,Be3,Rab8,Rac1,Nce4,Nxe4,Nxe4,Nf4,c5,dxc6,Bxc6,Nd3,Bf6,f3 → Nc5 BLACK_TO_MOVE [] *
af82127bd55b76bbd2d52734370753a9: d4,e6,c4,b6,a3,Bb7,Nc3,f5,d5,Nf6,g3,Na6,Bg2,Nc5,Nh3,Bd6,O-O,Be5,Qc2,O-O,Rd1,Qe7,Be3,Rab8,Rac1,Nce4,Nxe4,Nxe4,Nf4,c5,dxc6,Bxc6,Nd3,Bf6,f3,Nc5 → b4 WHITE_TO_MOVE [] *
ee98396bd2f94caea316ab2d2f0ff3a9: d4,e6,c4,b6,a3,Bb7,Nc3,f5,d5,Nf6,g3,Na6,Bg2,Nc5,Nh3,Bd6,O-O,Be5,Qc2,O-O,Rd1,Qe7,Be3,Rab8,Rac1,Nce4,Nxe4,Nxe4,Nf4,c5,dxc6,Bxc6,Nd3,Bf6,f3,Nc5,b4 → Nxd3 BLACK_TO_MOVE [] *
012c438b1bf8ce786a95a527ec4014e1: d4,e6,c4,b6,a3,Bb7,Nc3,f5,d5,Nf6,g3,Na6,Bg2,Nc5,Nh3,Bd6,O-O,Be5,Qc2,O-O,Rd1,Qe7,Be3,Rab8,Rac1,Nce4,Nxe4,Nxe4,Nf4,c5,dxc6,Bxc6,Nd3,Bf6,f3,Nc5,b4,Nxd3 → Rxd3 WHITE_TO_MOVE [] *
864b19ea72f37f31809e63b02dbb5259: d4,e6,c4,b6,a3,Bb7,Nc3,f5,d5,Nf6,g3,Na6,Bg2,Nc5,Nh3,Bd6,O-O,Be5,Qc2,O-O,Rd1,Qe7,Be3,Rab8,Rac1,Nce4,Nxe4,Nxe4,Nf4,c5,dxc6,Bxc6,Nd3,Bf6,f3,Nc5,b4,Nxd3,Rxd3 → d5 BLACK_TO_MOVE [] *
891df45326a554ceed99f76646ae276a: d4,e6,c4,b6,a3,Bb7,Nc3,f5,d5,Nf6,g3,Na6,Bg2,Nc5,Nh3,Bd6,O-O,Be5,Qc2,O-O,Rd1,Qe7,Be3,Rab8,Rac1,Nce4,Nxe4,Nxe4,Nf4,c5,dxc6,Bxc6,Nd3,Bf6,f3,Nc5,b4,Nxd3,Rxd3,d5 → f4 WHITE_TO_MOVE [] *
80837fa226079204fbd08285a66f94e8: d4,e6,c4,b6,a3,Bb7,Nc3,f5,d5,Nf6,g3,Na6,Bg2,Nc5,Nh3,Bd6,O-O,Be5,Qc2,O-O,Rd1,Qe7,Be3,Rab8,Rac1,Nce4,Nxe4,Nxe4,Nf4,c5,dxc6,Bxc6,Nd3,Bf6,f3,Nc5,b4,Nxd3,Rxd3,d5,f4 → dxc4 BLACK_TO_MOVE [] *
aeb695849aab6112b567ede27f35b177: d4,e6,c4,b6,a3,Bb7,Nc3,f5,d5,Nf6,g3,Na6,Bg2,Nc5,Nh3,Bd6,O-O,Be5,Qc2,O-O,Rd1,Qe7,Be3,Rab8,Rac1,Nce4,Nxe4,Nxe4,Nf4,c5,dxc6,Bxc6,Nd3,Bf6,f3,Nc5,b4,Nxd3,Rxd3,d5,f4,dxc4 → Qxc4 WHITE_TO_MOVE [] *
92595a0f3083a2890a65829a906e0351: d4,e6,c4,b6,a3,Bb7,Nc3,f5,d5,Nf6,g3,Na6,Bg2,Nc5,Nh3,Bd6,O-O,Be5,Qc2,O-O,Rd1,Qe7,Be3,Rab8,Rac1,Nce4,Nxe4,Nxe4,Nf4,c5,dxc6,Bxc6,Nd3,Bf6,f3,Nc5,b4,Nxd3,Rxd3,d5,f4,dxc4,Qxc4 → Bxg2 BLACK_TO_MOVE [] *
c0b091fb342f947f274c392231892757: d4,e6,c4,b6,a3,Bb7,Nc3,f5,d5,Nf6,g3,Na6,Bg2,Nc5,Nh3,Bd6,O-O,Be5,Qc2,O-O,Rd1,Qe7,Be3,Rab8,Rac1,Nce4,Nxe4,Nxe4,Nf4,c5,dxc6,Bxc6,Nd3,Bf6,f3,Nc5,b4,Nxd3,Rxd3,d5,f4,dxc4,Qxc4,Bxg2 → Kxg2 WHITE_TO_MOVE [] *
c62f277203b45a6053cda2aee5e7b5f5: d4,e6,c4,b6,a3,Bb7,Nc3,f5,d5,Nf6,g3,Na6,Bg2,Nc5,Nh3,Bd6,O-O,Be5,Qc2,O-O,Rd1,Qe7,Be3,Rab8,Rac1,Nce4,Nxe4,Nxe4,Nf4,c5,dxc6,Bxc6,Nd3,Bf6,f3,Nc5,b4,Nxd3,Rxd3,d5,f4,dxc4,Qxc4,Bxg2,Kxg2 → Rf7 BLACK_TO_MOVE [] *
61845ab2f591fd01475e720ad1fec8e6: d4,e6,c4,b6,a3,Bb7,Nc3,f5,d5,Nf6,g3,Na6,Bg2,Nc5,Nh3,Bd6,O-O,Be5,Qc2,O-O,Rd1,Qe7,Be3,Rab8,Rac1,Nce4,Nxe4,Nxe4,Nf4,c5,dxc6,Bxc6,Nd3,Bf6,f3,Nc5,b4,Nxd3,Rxd3,d5,f4,dxc4,Qxc4,Bxg2,Kxg2,Rf7 → b5 WHITE_TO_MOVE [] *
f4db08200b2db4704f061c2d44e693f0: d4,e6,c4,b6,a3,Bb7,Nc3,f5,d5,Nf6,g3,Na6,Bg2,Nc5,Nh3,Bd6,O-O,Be5,Qc2,O-O,Rd1,Qe7,Be3,Rab8,Rac1,Nce4,Nxe4,Nxe4,Nf4,c5,dxc6,Bxc6,Nd3,Bf6,f3,Nc5,b4,Nxd3,Rxd3,d5,f4,dxc4,Qxc4,Bxg2,Kxg2,Rf7,b5 → Re8 BLACK_TO_MOVE [] *
27305ce833872be1167f1c9dd9e07089: d4,e6,c4,b6,a3,Bb7,Nc3,f5,d5,Nf6,g3,Na6,Bg2,Nc5,Nh3,Bd6,O-O,Be5,Qc2,O-O,Rd1,Qe7,Be3,Rab8,Rac1,Nce4,Nxe4,Nxe4,Nf4,c5,dxc6,Bxc6,Nd3,Bf6,f3,Nc5,b4,Nxd3,Rxd3,d5,f4,dxc4,Qxc4,Bxg2,Kxg2,Rf7,b5,Re8 → Rcd1 WHITE_TO_MOVE [] *
4bf02ddf0f99e3eb7a6ad3eb83e82925: d4,e6,c4,b6,a3,Bb7,Nc3,f5,d5,Nf6,g3,Na6,Bg2,Nc5,Nh3,Bd6,O-O,Be5,Qc2,O-O,Rd1,Qe7,Be3,Rab8,Rac1,Nce4,Nxe4,Nxe4,Nf4,c5,dxc6,Bxc6,Nd3,Bf6,f3,Nc5,b4,Nxd3,Rxd3,d5,f4,dxc4,Qxc4,Bxg2,Kxg2,Rf7,b5,Re8,Rcd1 → e5 BLACK_TO_MOVE [] *
48d6c5171af88e11449c93272e850c1b: d4,e6,c4,b6,a3,Bb7,Nc3,f5,d5,Nf6,g3,Na6,Bg2,Nc5,Nh3,Bd6,O-O,Be5,Qc2,O-O,Rd1,Qe7,Be3,Rab8,Rac1,Nce4,Nxe4,Nxe4,Nf4,c5,dxc6,Bxc6,Nd3,Bf6,f3,Nc5,b4,Nxd3,Rxd3,d5,f4,dxc4,Qxc4,Bxg2,Kxg2,Rf7,b5,Re8,Rcd1,e5 → Rd7 WHITE_TO_MOVE [] *
472b38226cdb5ca45860dad664f76f92: d4,e6,c4,b6,a3,Bb7,Nc3,f5,d5,Nf6,g3,Na6,Bg2,Nc5,Nh3,Bd6,O-O,Be5,Qc2,O-O,Rd1,Qe7,Be3,Rab8,Rac1,Nce4,Nxe4,Nxe4,Nf4,c5,dxc6,Bxc6,Nd3,Bf6,f3,Nc5,b4,Nxd3,Rxd3,d5,f4,dxc4,Qxc4,Bxg2,Kxg2,Rf7,b5,Re8,Rcd1,e5,Rd7 → Qe6 BLACK_TO_MOVE [] *
6aba6cf4605102986cdf420b895efeee: d4,e6,c4,b6,a3,Bb7,Nc3,f5,d5,Nf6,g3,Na6,Bg2,Nc5,Nh3,Bd6,O-O,Be5,Qc2,O-O,Rd1,Qe7,Be3,Rab8,Rac1,Nce4,Nxe4,Nxe4,Nf4,c5,dxc6,Bxc6,Nd3,Bf6,f3,Nc5,b4,Nxd3,Rxd3,d5,f4,dxc4,Qxc4,Bxg2,Kxg2,Rf7,b5,Re8,Rcd1,e5,Rd7,Qe6 → Qxe6 WHITE_TO_MOVE [] *
c39ca4ad8178117120f72d5a9c9d3c05: d4,e6,c4,b6,a3,Bb7,Nc3,f5,d5,Nf6,g3,Na6,Bg2,Nc5,Nh3,Bd6,O-O,Be5,Qc2,O-O,Rd1,Qe7,Be3,Rab8,Rac1,Nce4,Nxe4,Nxe4,Nf4,c5,dxc6,Bxc6,Nd3,Bf6,f3,Nc5,b4,Nxd3,Rxd3,d5,f4,dxc4,Qxc4,Bxg2,Kxg2,Rf7,b5,Re8,Rcd1,e5,Rd7,Qe6,Qxe6 → Rxe6 BLACK_TO_MOVE [] *
f6ee11a55eef0188480851b8450d992c: d4,e6,c4,b6,a3,Bb7,Nc3,f5,d5,Nf6,g3,Na6,Bg2,Nc5,Nh3,Bd6,O-O,Be5,Qc2,O-O,Rd1,Qe7,Be3,Rab8,Rac1,Nce4,Nxe4,Nxe4,Nf4,c5,dxc6,Bxc6,Nd3,Bf6,f3,Nc5,b4,Nxd3,Rxd3,d5,f4,dxc4,Qxc4,Bxg2,Kxg2,Rf7,b5,Re8,Rcd1,e5,Rd7,Qe6,Qxe6,Rxe6 → Kf3 WHITE_TO_MOVE [] *
ccc94063a752c345ecfd8c2ed108e144: d4,e6,c4,b6,a3,Bb7,Nc3,f5,d5,Nf6,g3,Na6,Bg2,Nc5,Nh3,Bd6,O-O,Be5,Qc2,O-O,Rd1,Qe7,Be3,Rab8,Rac1,Nce4,Nxe4,Nxe4,Nf4,c5,dxc6,Bxc6,Nd3,Bf6,f3,Nc5,b4,Nxd3,Rxd3,d5,f4,dxc4,Qxc4,Bxg2,Kxg2,Rf7,b5,Re8,Rcd1,e5,Rd7,Qe6,Qxe6,Rxe6,Kf3 → exf4 BLACK_TO_MOVE [] *
c29fb194eefa6195d162ed303188b412: d4,e6,c4,b6,a3,Bb7,Nc3,f5,d5,Nf6,g3,Na6,Bg2,Nc5,Nh3,Bd6,O-O,Be5,Qc2,O-O,Rd1,Qe7,Be3,Rab8,Rac1,Nce4,Nxe4,Nxe4,Nf4,c5,dxc6,Bxc6,Nd3,Bf6,f3,Nc5,b4,Nxd3,Rxd3,d5,f4,dxc4,Qxc4,Bxg2,Kxg2,Rf7,b5,Re8,Rcd1,e5,Rd7,Qe6,Qxe6,Rxe6,Kf3,exf4 → gxf4 WHITE_TO_MOVE [] *
0315ad9dc5d6049ef94219023c13afab: d4,e6,c4,b6,a3,Bb7,Nc3,f5,d5,Nf6,g3,Na6,Bg2,Nc5,Nh3,Bd6,O-O,Be5,Qc2,O-O,Rd1,Qe7,Be3,Rab8,Rac1,Nce4,Nxe4,Nxe4,Nf4,c5,dxc6,Bxc6,Nd3,Bf6,f3,Nc5,b4,Nxd3,Rxd3,d5,f4,dxc4,Qxc4,Bxg2,Kxg2,Rf7,b5,Re8,Rcd1,e5,Rd7,Qe6,Qxe6,Rxe6,Kf3,exf4,gxf4 → Rxd7 BLACK_TO_MOVE [] *
7ad63bd2cb051b098bd3350913e9929b: d4,e6,c4,b6,a3,Bb7,Nc3,f5,d5,Nf6,g3,Na6,Bg2,Nc5,Nh3,Bd6,O-O,Be5,Qc2,O-O,Rd1,Qe7,Be3,Rab8,Rac1,Nce4,Nxe4,Nxe4,Nf4,c5,dxc6,Bxc6,Nd3,Bf6,f3,Nc5,b4,Nxd3,Rxd3,d5,f4,dxc4,Qxc4,Bxg2,Kxg2,Rf7,b5,Re8,Rcd1,e5,Rd7,Qe6,Qxe6,Rxe6,Kf3,exf4,gxf4,Rxd7 → Rxd7 WHITE_TO_MOVE [] *
18f0de1818c110c4204cd3d57bd6a20e: d4,e6,c4,b6,a3,Bb7,Nc3,f5,d5,Nf6,g3,Na6,Bg2,Nc5,Nh3,Bd6,O-O,Be5,Qc2,O-O,Rd1,Qe7,Be3,Rab8,Rac1,Nce4,Nxe4,Nxe4,Nf4,c5,dxc6,Bxc6,Nd3,Bf6,f3,Nc5,b4,Nxd3,Rxd3,d5,f4,dxc4,Qxc4,Bxg2,Kxg2,Rf7,b5,Re8,Rcd1,e5,Rd7,Qe6,Qxe6,Rxe6,Kf3,exf4,gxf4,Rxd7,Rxd7 → Re7 BLACK_TO_MOVE [] *
acc68bb2e29be1e8d94d4095fc571a0f: d4,e6,c4,b6,a3,Bb7,Nc3,f5,d5,Nf6,g3,Na6,Bg2,Nc5,Nh3,Bd6,O-O,Be5,Qc2,O-O,Rd1,Qe7,Be3,Rab8,Rac1,Nce4,Nxe4,Nxe4,Nf4,c5,dxc6,Bxc6,Nd3,Bf6,f3,Nc5,b4,Nxd3,Rxd3,d5,f4,dxc4,Qxc4,Bxg2,Kxg2,Rf7,b5,Re8,Rcd1,e5,Rd7,Qe6,Qxe6,Rxe6,Kf3,exf4,gxf4,Rxd7,Rxd7,Re7 → Rxe7 WHITE_TO_MOVE [] *
fa641223810ca2f7170f125511235628: d4,e6,c4,b6,a3,Bb7,Nc3,f5,d5,Nf6,g3,Na6,Bg2,Nc5,Nh3,Bd6,O-O,Be5,Qc2,O-O,Rd1,Qe7,Be3,Rab8,Rac1,Nce4,Nxe4,Nxe4,Nf4,c5,dxc6,Bxc6,Nd3,Bf6,f3,Nc5,b4,Nxd3,Rxd3,d5,f4,dxc4,Qxc4,Bxg2,Kxg2,Rf7,b5,Re8,Rcd1,e5,Rd7,Qe6,Qxe6,Rxe6,Kf3,exf4,gxf4,Rxd7,Rxd7,Re7,Rxe7 → Bxe7 BLACK_TO_MOVE [] *
2d8beaed752eedc1b58e4ee63a72cab1: d4,e6,c4,b6,a3,Bb7,Nc3,f5,d5,Nf6,g3,Na6,Bg2,Nc5,Nh3,Bd6,O-O,Be5,Qc2,O-O,Rd1,Qe7,Be3,Rab8,Rac1,Nce4,Nxe4,Nxe4,Nf4,c5,dxc6,Bxc6,Nd3,Bf6,f3,Nc5,b4,Nxd3,Rxd3,d5,f4,dxc4,Qxc4,Bxg2,Kxg2,Rf7,b5,Re8,Rcd1,e5,Rd7,Qe6,Qxe6,Rxe6,Kf3,exf4,gxf4,Rxd7,Rxd7,Re7,Rxe7,Bxe7 → a4 WHITE_TO_MOVE [] *
e75d35669c1b666d3bec2ec12e7c12ce: d4,e6,c4,b6,a3,Bb7,Nc3,f5,d5,Nf6,g3,Na6,Bg2,Nc5,Nh3,Bd6,O-O,Be5,Qc2,O-O,Rd1,Qe7,Be3,Rab8,Rac1,Nce4,Nxe4,Nxe4,Nf4,c5,dxc6,Bxc6,Nd3,Bf6,f3,Nc5,b4,Nxd3,Rxd3,d5,f4,dxc4,Qxc4,Bxg2,Kxg2,Rf7,b5,Re8,Rcd1,e5,Rd7,Qe6,Qxe6,Rxe6,Kf3,exf4,gxf4,Rxd7,Rxd7,Re7,Rxe7,Bxe7,a4 → Kf7 BLACK_TO_MOVE [] *
85b93388330db421b4bfeac4b87bc318: d4,e6,c4,b6,a3,Bb7,Nc3,f5,d5,Nf6,g3,Na6,Bg2,Nc5,Nh3,Bd6,O-O,Be5,Qc2,O-O,Rd1,Qe7,Be3,Rab8,Rac1,Nce4,Nxe4,Nxe4,Nf4,c5,dxc6,Bxc6,Nd3,Bf6,f3,Nc5,b4,Nxd3,Rxd3,d5,f4,dxc4,Qxc4,Bxg2,Kxg2,Rf7,b5,Re8,Rcd1,e5,Rd7,Qe6,Qxe6,Rxe6,Kf3,exf4,gxf4,Rxd7,Rxd7,Re7,Rxe7,Bxe7,a4,Kf7 → Bd4 WHITE_TO_MOVE [] *
740bf908907b158820c4b88ae48204ab: d4,e6,c4,b6,a3,Bb7,Nc3,f5,d5,Nf6,g3,Na6,Bg2,Nc5,Nh3,Bd6,O-O,Be5,Qc2,O-O,Rd1,Qe7,Be3,Rab8,Rac1,Nce4,Nxe4,Nxe4,Nf4,c5,dxc6,Bxc6,Nd3,Bf6,f3,Nc5,b4,Nxd3,Rxd3,d5,f4,dxc4,Qxc4,Bxg2,Kxg2,Rf7,b5,Re8,Rcd1,e5,Rd7,Qe6,Qxe6,Rxe6,Kf3,exf4,gxf4,Rxd7,Rxd7,Re7,Rxe7,Bxe7,a4,Kf7,Bd4 → Bd6 BLACK_TO_MOVE [] *
d2cae00640450e8fff5026f5b8cc9d55: d4,e6,c4,b6,a3,Bb7,Nc3,f5,d5,Nf6,g3,Na6,Bg2,Nc5,Nh3,Bd6,O-O,Be5,Qc2,O-O,Rd1,Qe7,Be3,Rab8,Rac1,Nce4,Nxe4,Nxe4,Nf4,c5,dxc6,Bxc6,Nd3,Bf6,f3,Nc5,b4,Nxd3,Rxd3,d5,f4,dxc4,Qxc4,Bxg2,Kxg2,Rf7,b5,Re8,Rcd1,e5,Rd7,Qe6,Qxe6,Rxe6,Kf3,exf4,gxf4,Rxd7,Rxd7,Re7,Rxe7,Bxe7,a4,Kf7,Bd4,Bd6 → e4 WHITE_TO_MOVE [] *
ce55eb6a14ba4c1305727bf44e9ffc0a: d4,e6,c4,b6,a3,Bb7,Nc3,f5,d5,Nf6,g3,Na6,Bg2,Nc5,Nh3,Bd6,O-O,Be5,Qc2,O-O,Rd1,Qe7,Be3,Rab8,Rac1,Nce4,Nxe4,Nxe4,Nf4,c5,dxc6,Bxc6,Nd3,Bf6,f3,Nc5,b4,Nxd3,Rxd3,d5,f4,dxc4,Qxc4,Bxg2,Kxg2,Rf7,b5,Re8,Rcd1,e5,Rd7,Qe6,Qxe6,Rxe6,Kf3,exf4,gxf4,Rxd7,Rxd7,Re7,Rxe7,Bxe7,a4,Kf7,Bd4,Bd6,e4 → g6 BLACK_TO_MOVE [] *
14832b1aa81fb72ff03eee431f208b82: d4,e6,c4,b6,a3,Bb7,Nc3,f5,d5,Nf6,g3,Na6,Bg2,Nc5,Nh3,Bd6,O-O,Be5,Qc2,O-O,Rd1,Qe7,Be3,Rab8,Rac1,Nce4,Nxe4,Nxe4,Nf4,c5,dxc6,Bxc6,Nd3,Bf6,f3,Nc5,b4,Nxd3,Rxd3,d5,f4,dxc4,Qxc4,Bxg2,Kxg2,Rf7,b5,Re8,Rcd1,e5,Rd7,Qe6,Qxe6,Rxe6,Kf3,exf4,gxf4,Rxd7,Rxd7,Re7,Rxe7,Bxe7,a4,Kf7,Bd4,Bd6,e4,g6 → h3 WHITE_TO_MOVE [] *
948be9102c4995bf66164dd64d1a9041: d4,e6,c4,b6,a3,Bb7,Nc3,f5,d5,Nf6,g3,Na6,Bg2,Nc5,Nh3,Bd6,O-O,Be5,Qc2,O-O,Rd1,Qe7,Be3,Rab8,Rac1,Nce4,Nxe4,Nxe4,Nf4,c5,dxc6,Bxc6,Nd3,Bf6,f3,Nc5,b4,Nxd3,Rxd3,d5,f4,dxc4,Qxc4,Bxg2,Kxg2,Rf7,b5,Re8,Rcd1,e5,Rd7,Qe6,Qxe6,Rxe6,Kf3,exf4,gxf4,Rxd7,Rxd7,Re7,Rxe7,Bxe7,a4,Kf7,Bd4,Bd6,e4,g6,h3 → Ke6 BLACK_TO_MOVE [] *
c4431c64b855591d44acd93e33505c9d: d4,e6,c4,b6,a3,Bb7,Nc3,f5,d5,Nf6,g3,Na6,Bg2,Nc5,Nh3,Bd6,O-O,Be5,Qc2,O-O,Rd1,Qe7,Be3,Rab8,Rac1,Nce4,Nxe4,Nxe4,Nf4,c5,dxc6,Bxc6,Nd3,Bf6,f3,Nc5,b4,Nxd3,Rxd3,d5,f4,dxc4,Qxc4,Bxg2,Kxg2,Rf7,b5,Re8,Rcd1,e5,Rd7,Qe6,Qxe6,Rxe6,Kf3,exf4,gxf4,Rxd7,Rxd7,Re7,Rxe7,Bxe7,a4,Kf7,Bd4,Bd6,e4,g6,h3,Ke6 → Bc3 WHITE_TO_MOVE [] *
68f264a5b285ba18fa5e33cbf4d69b32: d4,e6,c4,b6,a3,Bb7,Nc3,f5,d5,Nf6,g3,Na6,Bg2,Nc5,Nh3,Bd6,O-O,Be5,Qc2,O-O,Rd1,Qe7,Be3,Rab8,Rac1,Nce4,Nxe4,Nxe4,Nf4,c5,dxc6,Bxc6,Nd3,Bf6,f3,Nc5,b4,Nxd3,Rxd3,d5,f4,dxc4,Qxc4,Bxg2,Kxg2,Rf7,b5,Re8,Rcd1,e5,Rd7,Qe6,Qxe6,Rxe6,Kf3,exf4,gxf4,Rxd7,Rxd7,Re7,Rxe7,Bxe7,a4,Kf7,Bd4,Bd6,e4,g6,h3,Ke6,Bc3 → Bc7 BLACK_TO_MOVE [] *
17ef9e98a060676780416f83514ff80f: d4,e6,c4,b6,a3,Bb7,Nc3,f5,d5,Nf6,g3,Na6,Bg2,Nc5,Nh3,Bd6,O-O,Be5,Qc2,O-O,Rd1,Qe7,Be3,Rab8,Rac1,Nce4,Nxe4,Nxe4,Nf4,c5,dxc6,Bxc6,Nd3,Bf6,f3,Nc5,b4,Nxd3,Rxd3,d5,f4,dxc4,Qxc4,Bxg2,Kxg2,Rf7,b5,Re8,Rcd1,e5,Rd7,Qe6,Qxe6,Rxe6,Kf3,exf4,gxf4,Rxd7,Rxd7,Re7,Rxe7,Bxe7,a4,Kf7,Bd4,Bd6,e4,g6,h3,Ke6,Bc3,Bc7 → Bb4 WHITE_TO_MOVE [] *
27d97b250cb8541d2a50d9464f9cea0e: d4,e6,c4,b6,a3,Bb7,Nc3,f5,d5,Nf6,g3,Na6,Bg2,Nc5,Nh3,Bd6,O-O,Be5,Qc2,O-O,Rd1,Qe7,Be3,Rab8,Rac1,Nce4,Nxe4,Nxe4,Nf4,c5,dxc6,Bxc6,Nd3,Bf6,f3,Nc5,b4,Nxd3,Rxd3,d5,f4,dxc4,Qxc4,Bxg2,Kxg2,Rf7,b5,Re8,Rcd1,e5,Rd7,Qe6,Qxe6,Rxe6,Kf3,exf4,gxf4,Rxd7,Rxd7,Re7,Rxe7,Bxe7,a4,Kf7,Bd4,Bd6,e4,g6,h3,Ke6,Bc3,Bc7,Bb4 → Bd8 BLACK_TO_MOVE [] *
3c61557163927180f6e0479ed6e90615: d4,e6,c4,b6,a3,Bb7,Nc3,f5,d5,Nf6,g3,Na6,Bg2,Nc5,Nh3,Bd6,O-O,Be5,Qc2,O-O,Rd1,Qe7,Be3,Rab8,Rac1,Nce4,Nxe4,Nxe4,Nf4,c5,dxc6,Bxc6,Nd3,Bf6,f3,Nc5,b4,Nxd3,Rxd3,d5,f4,dxc4,Qxc4,Bxg2,Kxg2,Rf7,b5,Re8,Rcd1,e5,Rd7,Qe6,Qxe6,Rxe6,Kf3,exf4,gxf4,Rxd7,Rxd7,Re7,Rxe7,Bxe7,a4,Kf7,Bd4,Bd6,e4,g6,h3,Ke6,Bc3,Bc7,Bb4,Bd8 → e5 WHITE_TO_MOVE [] *
d570901e9a9c20a053f9055dafc06232: d4,e6,c4,b6,a3,Bb7,Nc3,f5,d5,Nf6,g3,Na6,Bg2,Nc5,Nh3,Bd6,O-O,Be5,Qc2,O-O,Rd1,Qe7,Be3,Rab8,Rac1,Nce4,Nxe4,Nxe4,Nf4,c5,dxc6,Bxc6,Nd3,Bf6,f3,Nc5,b4,Nxd3,Rxd3,d5,f4,dxc4,Qxc4,Bxg2,Kxg2,Rf7,b5,Re8,Rcd1,e5,Rd7,Qe6,Qxe6,Rxe6,Kf3,exf4,gxf4,Rxd7,Rxd7,Re7,Rxe7,Bxe7,a4,Kf7,Bd4,Bd6,e4,g6,h3,Ke6,Bc3,Bc7,Bb4,Bd8,e5 → * BLACK_TO_MOVE [] 4/g5/0.08
    cef4c3abfea7d4beed86942a335eb1c72c5db5deb9a30762e025e6182927af27: {'event': 'Fujitsu Siemens Giants', 'site': 'Frankfurt', 'date': '2000.06.23', 'round': '5', 'white': 'Kasparov, Garry', 'black': 'Morozevich, Alexander', 'result': '1/2-1/2', 'whiteelo': '2851', 'blackelo': '2748', 'eco': 'A40', 'eventdate': '2000.06.22'}\
"""

_DB_STR_MINOR: str = """\
27d97b250cb8541d2a50d9464f9cea0e: d4,e6,c4,b6,a3,Bb7,Nc3,f5,d5,Nf6,g3,Na6,Bg2,Nc5,Nh3,Bd6,O-O,Be5,Qc2,O-O,Rd1,Qe7,Be3,Rab8,Rac1,Nce4,Nxe4,Nxe4,Nf4,c5,dxc6,Bxc6,Nd3,Bf6,f3,Nc5,b4,Nxd3,Rxd3,d5,f4,dxc4,Qxc4,Bxg2,Kxg2,Rf7,b5,Re8,Rcd1,e5,Rd7,Qe6,Qxe6,Rxe6,Kf3,exf4,gxf4,Rxd7,Rxd7,Re7,Rxe7,Bxe7,a4,Kf7,Bd4,Bd6,e4,g6,h3,Ke6,Bc3,Bc7,Bb4 → Bd8 BLACK_TO_MOVE [] *
3c61557163927180f6e0479ed6e90615: d4,e6,c4,b6,a3,Bb7,Nc3,f5,d5,Nf6,g3,Na6,Bg2,Nc5,Nh3,Bd6,O-O,Be5,Qc2,O-O,Rd1,Qe7,Be3,Rab8,Rac1,Nce4,Nxe4,Nxe4,Nf4,c5,dxc6,Bxc6,Nd3,Bf6,f3,Nc5,b4,Nxd3,Rxd3,d5,f4,dxc4,Qxc4,Bxg2,Kxg2,Rf7,b5,Re8,Rcd1,e5,Rd7,Qe6,Qxe6,Rxe6,Kf3,exf4,gxf4,Rxd7,Rxd7,Re7,Rxe7,Bxe7,a4,Kf7,Bd4,Bd6,e4,g6,h3,Ke6,Bc3,Bc7,Bb4,Bd8 → e5 WHITE_TO_MOVE [] *
d570901e9a9c20a053f9055dafc06232: d4,e6,c4,b6,a3,Bb7,Nc3,f5,d5,Nf6,g3,Na6,Bg2,Nc5,Nh3,Bd6,O-O,Be5,Qc2,O-O,Rd1,Qe7,Be3,Rab8,Rac1,Nce4,Nxe4,Nxe4,Nf4,c5,dxc6,Bxc6,Nd3,Bf6,f3,Nc5,b4,Nxd3,Rxd3,d5,f4,dxc4,Qxc4,Bxg2,Kxg2,Rf7,b5,Re8,Rcd1,e5,Rd7,Qe6,Qxe6,Rxe6,Kf3,exf4,gxf4,Rxd7,Rxd7,Re7,Rxe7,Bxe7,a4,Kf7,Bd4,Bd6,e4,g6,h3,Ke6,Bc3,Bc7,Bb4,Bd8,e5 → * BLACK_TO_MOVE [] 4/g5/0.08\
"""


SUITE: unittest.TestSuite = unittest.TestLoader().loadTestsFromTestCase(TestPawnLib)


if __name__ == '__main__':
  logging.basicConfig(level=logging.INFO, format=base.LOG_FORMAT)  # set this as default
  unittest.main()
