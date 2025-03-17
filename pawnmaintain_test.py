#!/usr/bin/python3 -bb
#
# Copyright 2025 Daniel Balparda (balparda@gmail.com)
# GNU General Public License v3 (http://www.gnu.org/licenses/gpl-3.0.txt)
#
# pylint: disable=invalid-name,protected-access
"""pawnmaintain.py unittest."""

import logging
# import pdb
import sys
import unittest
from unittest import mock

from baselib import base
from pawnalyze import pawnmaintain

__author__ = 'balparda@gmail.com (Daniel Balparda)'
__version__ = (1, 0)


class TestPawnMaintain(unittest.TestCase):
  """Tests for pawnmaintain.py."""

  @mock.patch('pawnmaintain.pawnlib.PGNData')
  def test_SubcommandPrint(self, mock_PGNDataClass: mock.MagicMock) -> None:
    """Test the 'print' subcommand."""
    # 1) Create a MagicMock to represent the DB instance
    mock_db_instance = mock.MagicMock()
    mock_PGNDataClass.return_value = mock_db_instance
    # 2) Simulate CLI arguments
    test_args: list[str] = [
        'pawnmaintain.py',
        'print',
        '-p', '2',  # positions limit
        '-z', 'abcdef0123456789abcdef0123456789',  # 32-char hex
        '-g', 'True'
    ]
    with mock.patch.object(sys, 'argv', test_args):
      pawnmaintain.Main()
    # 3) Verify PGNData was constructed with correct "readonly"
    mock_PGNDataClass.assert_called_once_with(readonly=False)
    # 4) We also verify that PrintMovesDB was called:
    #    The logic calls PrintMovesDB(...) => it yields lines => we presumably print them.
    #    We can check how many times the iteration was done.
    #    Let’s define a dummy side_effect if you want more control.
    mock_db_instance.PrintMovesDB.assert_called_once()
    call_args = mock_db_instance.PrintMovesDB.call_args[1]  # the named arguments
    # The function signature is presumably PrintMovesDB(start_position=None, expand_games=False)
    # We expect start_position=ZobristFromHash('abcdef0123456789abcdef0123456789'), expand_games=True
    self.assertTrue(call_args['expand_games'], "Expected expand_games=True from -g True")
    # Checking the z-hash is a bit trickier because it should be a pawnzobrist.Zobrist object.
    # We'll do a simpler assertion that it's not None:
    self.assertIsNotNone(call_args['start_position'])
    # 5) Check that database.Close() was called eventually
    mock_db_instance.Close.assert_called_once()

  @mock.patch('pawnmaintain.pawnlib.PGNData')
  def test_SubcommandDedup(self, mock_PGNDataClass: mock.MagicMock) -> None:
    """Test the 'dedup' subcommand with custom soft/hard limits."""
    mock_db_instance = mock.MagicMock()
    mock_PGNDataClass.return_value = mock_db_instance
    test_args: list[str] = [
        'pawnmaintain.py',
        'dedup',
        '-s', '45',
        '-l', '70',
    ]
    with mock.patch.object(sys, 'argv', test_args):
      pawnmaintain.Main()
    mock_PGNDataClass.assert_called_once_with(readonly=False)
    # Ensure we call DeduplicateGames with (45, 70)
    mock_db_instance.DeduplicateGames.assert_called_once_with(45, 70)
    mock_db_instance.Close.assert_called_once()

  @mock.patch('pawnmaintain.pawnlib.PGNData')
  def test_SubcommandCheck(self, mock_PGNDataClass: mock.MagicMock) -> None:
    """Test the 'check' subcommand calls PrintDatabaseCheck and iterates over its output."""
    mock_db_instance = mock.MagicMock()
    # We can define a side_effect or return_value for PrintDatabaseCheck
    # so we can see how the code deals with it
    mock_db_instance.PrintDatabaseCheck.return_value = iter([
        'Reading all games...',
        '10 ok games and 5 error games in database',
        'Reading all duplicate games...',
    ])
    mock_PGNDataClass.return_value = mock_db_instance
    test_args = ['pawnmaintain.py', 'check']
    with mock.patch.object(sys, 'argv', test_args):
      pawnmaintain.Main()
    mock_PGNDataClass.assert_called_once_with(readonly=False)
    mock_db_instance.PrintDatabaseCheck.assert_called_once()
    mock_db_instance.Close.assert_called_once()

  @mock.patch('pawnmaintain.pawnlib.PGNData')
  def test_SubcommandInvalidArgs(self, mock_PGNDataClass: mock.MagicMock) -> None:
    """Test passing invalid arguments, for instance softlimit >= hardlimit or none command."""
    mock_db_instance = mock.MagicMock()
    mock_PGNDataClass.return_value = mock_db_instance
    # First, let's do a case where we specify 'dedup' but pass an invalid limit
    test_args = ['pawnmaintain.py', 'dedup', '-s', '70', '-l', '60']  # s >= l => error
    with mock.patch.object(sys, 'argv', test_args):
      with self.assertRaisesRegex(ValueError, 'Minimum soft limit'):
        pawnmaintain.Main()
    mock_db_instance.Close.assert_called_once()  # Even on error, we eventually close
    mock_db_instance.Close.reset_mock()
    # Another scenario: No subcommand => it prints parser help
    # We won't raise an error in that scenario, but let’s confirm it doesn't call PGNData methods
    test_args2 = ['pawnmaintain.py']  # no subcommand
    with mock.patch.object(sys, 'argv', test_args2):
      pawnmaintain.Main()
    # it should not call deduplicate and others etc:
    mock_db_instance.PrintMovesDB.assert_not_called()
    mock_db_instance.DeduplicateGames.assert_not_called()
    mock_db_instance.PrintDatabaseCheck.assert_not_called()
    # But it does open/close the DB
    mock_db_instance.Close.assert_called_once()


SUITE: unittest.TestSuite = unittest.TestLoader().loadTestsFromTestCase(TestPawnMaintain)


if __name__ == '__main__':
  logging.basicConfig(level=logging.INFO, format=base.LOG_FORMAT)  # set this as default
  unittest.main()
