#!/usr/bin/python3 -bb
#
# Copyright 2025 Daniel Balparda (balparda@gmail.com)
# GNU General Public License v3 (http://www.gnu.org/licenses/gpl-3.0.txt)
#
# pylint: disable=invalid-name,protected-access
"""pawnenginemoves.py unittest."""

import logging
# import pdb
import unittest
# from unittest import mock

from baselib import base

__author__ = 'balparda@gmail.com (Daniel Balparda)'
__version__ = (1, 0)


class TestPawnEngineMoves(unittest.TestCase):
  """Tests for pawnenginemoves.py."""

  def test_YYY(self) -> None:
    """Test."""


SUITE: unittest.TestSuite = unittest.TestLoader().loadTestsFromTestCase(TestPawnEngineMoves)


if __name__ == '__main__':
  logging.basicConfig(level=logging.INFO, format=base.LOG_FORMAT)  # set this as default
  unittest.main()
