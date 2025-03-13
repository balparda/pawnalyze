#!/bin/bash
#
# Copyright 2025 Daniel Balparda (balparda@gmail.com)
# GNU General Public License v3
#
# https://coverage.readthedocs.io/
#

coverage run --omit=*_test.py,*_tests.py,*/dist-packages/*,*/site-packages/*,*/baselib/* run_all_tests.py
coverage report -m
coverage html
