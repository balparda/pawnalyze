#!/usr/bin/python3 -bb
#
# Copyright 2025 Daniel Balparda (balparda@gmail.com)
# GNU General Public License v3 (http://www.gnu.org/licenses/gpl-3.0.txt)
#
"""Run all the tests so we can have easy global coverage."""

import logging
import types

from baselib import base
from pawnalyze import pawnlib_test
from pawnalyze import pawningest_test

__author__ = 'balparda@gmail.com (Daniel Balparda)'
__version__ = (1, 0)


_TEST_MODULES_TO_RUN: list[types.ModuleType] = [
    pawnlib_test,
    pawningest_test,
]


@base.Timed('pawnalyze tests')  # type:ignore
def Main() -> None:
  """Run all of the tests."""
  logging.info('*' * 80)
  for module in _TEST_MODULES_TO_RUN:
    logging.info('Running tests: %s.py', module.__name__)
    module.SUITE.debug()
    logging.info('OK')
    logging.info('*' * 80)
  logging.info('               ======>>>>  ALL MODULES PASSED OK  <<<<======')
  logging.info('*' * 80)


if __name__ == "__main__":
  logging.basicConfig(level=logging.INFO, format=base.LOG_FORMAT)
  Main()  # type:ignore
