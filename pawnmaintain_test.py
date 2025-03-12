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

  @mock.patch('pawnalyze.pawnmaintain.pawnlib.PGNData')
  def test_NormalFlow(self, mock_PGNData: mock.MagicMock) -> None:
    """Test normal flow with valid arguments.

    The script should:
        1) Create PGNData(readonly=False)
        2) Call DeduplicateGames
        3) Call PrintDatabaseCheck
        4) Close the DB
    """
    # Mock out the PGNData constructor returns a MagicMock object
    mock_db_instance = mock.MagicMock()
    mock_db_instance.DeduplicateGames.return_value = ['pos1', 'pos2']
    # We can let PrintDatabaseCheck() return a list of lines. We'll mock it to yield lines.
    mock_db_instance.PrintDatabaseCheck.return_value = ['DB line 1', 'DB line 2']
    mock_PGNData.return_value = mock_db_instance
    test_args: list[str] = [
        'pawnmaintain.py',
        '-s', '40',
        '-l', '60'
    ]
    with mock.patch.object(sys, 'argv', test_args):
      pawnmaintain.Main()
    # Check that PGNData was constructed with read-only = False
    mock_PGNData.assert_called_once_with(readonly=False)
    # The script calls .DeduplicateGames(soft_limit=40, hard_limit=60)
    mock_db_instance.DeduplicateGames.assert_called_once_with(40, 60)
    # Then .PrintDatabaseCheck()
    mock_db_instance.PrintDatabaseCheck.assert_called_once()
    # Then .Close()
    mock_db_instance.Close.assert_called_once()

  def test_InvalidThresholds(self) -> None:
    """Test that invalid thresholds raise ValueError: i.e. --softlimit < 40 or --hardlimit < 60."""
    test_args: list[str] = [
        'pawnmaintain.py',
        '-s', '39',  # invalid
        '-l', '60'
    ]
    with mock.patch.object(sys, 'argv', test_args):
      with self.assertRaisesRegex(ValueError, 'Minimum soft limit is 40'):
        pawnmaintain.Main()
    test_args2: list[str] = [
        'pawnmaintain.py',
        '-s', '40',
        '-l', '59'  # invalid
    ]
    with mock.patch.object(sys, 'argv', test_args2):
      with self.assertRaisesRegex(ValueError, 'minimum hard limit is 60'):
        pawnmaintain.Main()

  @mock.patch('pawnalyze.pawnmaintain.pawnlib.PGNData')
  def test_ReadOnly(self, mock_PGNData: mock.MagicMock) -> None:
    """Confirm that if -r/--readonly is set, we pass readonly=True to PGNData."""
    mock_db_instance = mock.MagicMock()
    mock_PGNData.return_value = mock_db_instance
    test_args: list[str] = [
        'pawnmaintain.py',
        '-s', '40',
        '-l', '60',
        '-r', '1'
    ]
    with mock.patch.object(sys, 'argv', test_args):
      pawnmaintain.Main()
    mock_PGNData.assert_called_once_with(readonly=True)
    mock_db_instance.DeduplicateGames.assert_called_once_with(40, 60)
    mock_db_instance.PrintDatabaseCheck.assert_called_once()
    mock_db_instance.Close.assert_called_once()

  @mock.patch('pawnalyze.pawnmaintain.pawnlib.PGNData')
  def test_ExceptionFlow(self, mock_PGNData: mock.MagicMock) -> None:
    """If there's an exception, see if it re-raises but still prints 'THE END: error: ...'."""
    mock_db_instance = mock.MagicMock()
    mock_db_instance.DeduplicateGames.side_effect = RuntimeError('fake de-dupe error')
    mock_PGNData.return_value = mock_db_instance
    test_args: list[str] = [
        'pawnmaintain.py',
        '-s', '40',
        '-l', '60'
    ]
    with mock.patch.object(sys, 'argv', test_args):
      with self.assertRaisesRegex(RuntimeError, 'fake de-dupe error'):
        pawnmaintain.Main()
    # The DB should be closed even if there's an error
    mock_db_instance.Close.assert_called_once()


SUITE: unittest.TestSuite = unittest.TestLoader().loadTestsFromTestCase(TestPawnMaintain)


if __name__ == '__main__':
  logging.basicConfig(level=logging.INFO, format=base.LOG_FORMAT)  # set this as default
  unittest.main()
