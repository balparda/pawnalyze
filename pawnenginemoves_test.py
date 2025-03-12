#!/usr/bin/python3 -bb
#
# Copyright 2025 Daniel Balparda (balparda@gmail.com)
# GNU General Public License v3 (http://www.gnu.org/licenses/gpl-3.0.txt)
#
# pylint: disable=invalid-name,protected-access
"""pawnenginemoves.py unittest."""

import logging
# import pdb
import sys
import unittest
from unittest import mock

from baselib import base
from pawnalyze import pawnenginemoves

__author__ = 'balparda@gmail.com (Daniel Balparda)'
__version__ = (1, 0)


class TestPawnEngineMoves(unittest.TestCase):
  """Tests for pawnenginemoves.py."""

  @mock.patch('pawnalyze.pawnenginemoves.AddEvaluationsOfRepeatPositionsToDB')
  @mock.patch('pawnalyze.pawnenginemoves.AddEvaluationsOfPositionsToDB')
  @mock.patch('pawnalyze.pawnenginemoves.pawnlib.PGNData')
  def test_NormalFlow(
      self,
      mock_PGNData: mock.MagicMock,
      mock_AddEvalPositions: mock.MagicMock,
      mock_AddEvalRepeats: mock.MagicMock) -> None:
    """Test normal flow with valid arguments. Check calls."""
    # Mock out the PGNData constructor returns a MagicMock object
    mock_db_instance = mock.MagicMock()
    mock_PGNData.return_value = mock_db_instance
    # We call Main() -> this should parse args and call in sequence
    test_args: list[str] = [
        'pawnenginemoves.py',
        '-n', '4',
        '-d', '12',
        '-e', 'my_stockfish',
        '-t', '500',
    ]
    with mock.patch.object(sys, 'argv', test_args):
      pawnenginemoves.Main()
    # Check that PGNData was constructed with read-only = False
    mock_PGNData.assert_called_once_with(readonly=False)
    self.assertEqual(mock_AddEvalPositions.call_count, 2)
    self.assertEqual(mock_AddEvalRepeats.call_count, 1)
    # The first call (final_node=True):
    mock_AddEvalPositions.assert_any_call(
        mock_db_instance, 4, 12, 500, 'my_stockfish', True)
    # The second call (final_node=False):
    mock_AddEvalPositions.assert_any_call(
        mock_db_instance, 4, 12, 500, 'my_stockfish', False)
    # The call to AddEvaluationsOfRepeatPositionsToDB
    mock_AddEvalRepeats.assert_called_once_with(
        mock_db_instance, 4, 12, 500, 'my_stockfish')
    # The DB close call after finishing
    mock_db_instance.Close.assert_called_once()

  def test_InvalidNumThreads(self) -> None:
    """Test that an invalid -n argument triggers a ValueError."""
    test_args: list[str] = [
        'pawnenginemoves.py',
        '-n', '0',  # invalid
        '-d', '12',
        '-e', 'stockfish'
    ]
    with mock.patch.object(sys, 'argv', test_args):
      with self.assertRaisesRegex(ValueError, 'threads'):
        pawnenginemoves.Main()

  def test_InvalidDepth(self) -> None:
    """Test that an invalid -d argument triggers a ValueError."""
    test_args: list[str] = [
        'pawnenginemoves.py',
        '-n', '4',
        '-d', '999',  # invalid, above _MAX_DEPTH
        '-e', 'stockfish'
    ]
    with mock.patch.object(sys, 'argv', test_args):
      with self.assertRaisesRegex(ValueError, 'ply depth'):
        pawnenginemoves.Main()

  def test_NoEngine(self):
    """Test that an empty engine command triggers a ValueError."""
    test_args: list[str] = [
        'pawnenginemoves.py',
        '-n', '4',
        '-d', '12',
        '-e', ''
    ]
    with mock.patch.object(sys, 'argv', test_args):
      with self.assertRaisesRegex(ValueError, 'engine command'):
        pawnenginemoves.Main()

  def test_InvalidTasks(self) -> None:
    """Test that out-of-range -t argument triggers a ValueError."""
    test_args: list[str] = [
        'pawnenginemoves.py',
        '-n', '4',
        '-d', '12',
        '-e', 'stockfish',
        '-t', '9'  # below 10
    ]
    with mock.patch.object(sys, 'argv', test_args):
      with self.assertRaisesRegex(ValueError, 'number of tasks'):
        pawnenginemoves.Main()


SUITE: unittest.TestSuite = unittest.TestLoader().loadTestsFromTestCase(TestPawnEngineMoves)


if __name__ == '__main__':
  logging.basicConfig(level=logging.INFO, format=base.LOG_FORMAT)  # set this as default
  unittest.main()
