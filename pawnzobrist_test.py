#!/usr/bin/python3 -bb
#
# Copyright 2025 Daniel Balparda (balparda@gmail.com)
# GNU General Public License v3 (http://www.gnu.org/licenses/gpl-3.0.txt)
#
# pylint: disable=invalid-name,protected-access
"""pawnzobrist.py unittest."""

import logging
# import pdb
import unittest

import chess
import chess.pgn

from baselib import base
from pawnalyze import pawnzobrist

__author__ = 'balparda@gmail.com (Daniel Balparda)'
__version__ = (1, 0)


class TestPawnZobrist(unittest.TestCase):
  """Tests for pawnzobrist.py."""

  def test_ZobristGenerateTable(self) -> None:
    """Test."""
    # this will make sure our table doesn't get corrupted by mistake
    self.assertTupleEqual(pawnzobrist.ZobristGenerateTable(),
                          ('fda2af8637b3b483e5467b71c28acf5b', 'b031bba5698b25a5424b5e4d029093ba'))

  def test_ZobristHash(self) -> None:
    """Test."""
    # here, too, we are pinning this version o Zobrist to the random table generated in the module
    base_str: str = '3a653200920c4adb562ceff24c6af691'  # starting board position
    base_hash: pawnzobrist.Zobrist = pawnzobrist.ZobristFromBoard(chess.pgn.Game().board())
    self.assertEqual(str(base_hash), base_str)
    self.assertEqual(repr(base_hash), 'Zobrist("3a653200920c4adb562ceff24c6af691")')
    another_base: pawnzobrist.Zobrist = pawnzobrist.ZobristFromHash(base_str)
    self.assertTrue(base_hash == another_base)
    self.assertTrue(base_hash == int(base_str, 16))
    self.assertTrue(base_hash == str(another_base))
    _ = {base_hash}
    self.assertEqual(
        str(pawnzobrist.ZobristFromFEN('4r2k/2R3p1/3P1pKp/p6P/P5P1/8/5P2/8 w - - 5 44')),
        'ce1e8b345ac1a8796d3c511a186b4e34')
    self.assertTrue(base_hash != 'ce1e8b345ac1a8796d3c511a186b4e34')
    self.assertTrue(base_hash != set())
    with self.assertRaisesRegex(ValueError, 'must be initialized with int'):
      pawnzobrist.Zobrist('ce1e8b345ac1a8796d3c511a186b4e34')  # type: ignore


SUITE: unittest.TestSuite = unittest.TestLoader().loadTestsFromTestCase(TestPawnZobrist)


if __name__ == '__main__':
  logging.basicConfig(level=logging.INFO, format=base.LOG_FORMAT)  # set this as default
  unittest.main()
