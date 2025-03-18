#!/usr/bin/python3 -bb
#
# Copyright 2025 Daniel Balparda (balparda@gmail.com)
# GNU General Public License v3 (http://www.gnu.org/licenses/gpl-3.0.txt)
#
# pylint: disable=invalid-name,protected-access
"""pawnalyzer.py unittest."""

import logging
# import pdb
# import sys
import unittest
# from unittest import mock

from baselib import base
# from pawnalyze import pawnenginemoves

__author__ = 'balparda@gmail.com (Daniel Balparda)'
__version__ = (1, 0)


class TestPawnalyzer(unittest.TestCase):
  """Tests for pawnalyzer.py."""


SUITE: unittest.TestSuite = unittest.TestLoader().loadTestsFromTestCase(TestPawnalyzer)


if __name__ == '__main__':
  logging.basicConfig(level=logging.INFO, format=base.LOG_FORMAT)  # set this as default
  unittest.main()
