#!/usr/bin/python3 -bb
#
# Copyright 2025 Daniel Balparda (balparda@gmail.com)
# GNU General Public License v3 (http://www.gnu.org/licenses/gpl-3.0.txt)
#
# pylint: disable=invalid-name,protected-access
"""pawningest.py unittest."""

import logging
# import pdb
import sys
import unittest
from unittest import mock

from baselib import base
from pawnalyze import pawningest

__author__ = 'balparda@gmail.com (Daniel Balparda)'
__version__ = (1, 0)


class TestPawnIngest(unittest.TestCase):
  """Tests for pawningest.py."""

  @mock.patch('pawnalyze.pawningest.pawnlib.PGNData')
  @mock.patch('pawnalyze.pawningest.pawnlib.PGNCache')
  def test_Main_URL(self, mock_PGNCache: mock.MagicMock, mock_PGNData: mock.MagicMock) -> None:
    """Provide -u <URL>."""
    mock_db = mock.MagicMock()
    mock_PGNData.return_value = mock_db
    mock_cache = mock.MagicMock()
    mock_PGNCache.return_value = mock_cache
    test_args: list[str] = [
        'pawningest.py',
        '-u', 'http://example.com/fake.pgn'
    ]
    with mock.patch.object(sys, 'argv', test_args):
      pawningest.Main()
    # DB created with readonly=False by default
    mock_PGNData.assert_called_once_with(readonly=False)
    # Cache is created because -i not given
    mock_PGNCache.assert_called_once()
    # Now check the side effect: _LoadFromURL calls db.CachedLoadFromURL
    # We won't patch _LoadFromURL, but we see that db must have called
    # something like db.CachedLoadFromURL('http://example.com/fake.pgn', mock_cache)
    # That code results in db.CachedLoadFromURL being used in a for-loop.
    mock_db.CachedLoadFromURL.assert_called_once_with('http://example.com/fake.pgn', mock_cache)
    mock_db.Close.assert_called_once()

  @mock.patch('pawnalyze.pawningest.pawnlib.PGNData')
  @mock.patch('pawnalyze.pawningest.pawnlib.PGNCache')
  def test_Main_File(self, mock_PGNCache: mock.MagicMock, mock_PGNData: mock.MagicMock) -> None:
    """Provide -f /some/file.pgn. We confirm it calls db.LoadFromDisk('/some/file.pgn')."""
    mock_db = mock.MagicMock()
    mock_PGNData.return_value = mock_db
    mock_cache = mock.MagicMock()
    mock_PGNCache.return_value = mock_cache
    test_args: list[str] = [
        'pawningest.py',
        '-f', '/tmp/my-games.pgn'
    ]
    with mock.patch.object(sys, 'argv', test_args):
      pawningest.Main()
    mock_PGNData.assert_called_once_with(readonly=False)
    mock_PGNCache.assert_called_once()
    # _LoadFromFile(...) calls db.LoadFromDisk('/tmp/my-games.pgn')
    # internally we do a for-loop over db.LoadFromDisk(...).
    mock_db.LoadFromDisk.assert_called_once_with('/tmp/my-games.pgn')
    mock_db.Close.assert_called_once()

  @mock.patch('pawnalyze.pawningest.os.walk')
  @mock.patch('pawnalyze.pawningest.pawnlib.PGNData')
  @mock.patch('pawnalyze.pawningest.pawnlib.PGNCache')
  def test_Main_Directory(
      self, mock_PGNCache: mock.MagicMock, mock_PGNData: mock.MagicMock,
      mock_walk: mock.MagicMock) -> None:
    '''
    Provide -d /some/dir => _LoadFromDirectory.
    That calls os.walk() plus db.LoadFromDisk(...) for each .pgn file.
    '''
    mock_db = mock.MagicMock()
    mock_PGNData.return_value = mock_db
    mock_cache = mock.MagicMock()
    mock_PGNCache.return_value = mock_cache
    # We'll mock out os.walk to simulate one .pgn plus a .txt that we skip
    mock_walk.return_value = [
        ('/some/dir', ['subdir'], ['file1.pgn', 'notes.txt']),
        ('/some/dir/subdir', [], ['subfile.pgn']),
    ]
    test_args: list[str] = [
        'pawningest.py',
        '-d', '/some/dir'
    ]
    with mock.patch.object(sys, 'argv', test_args):
      pawningest.Main()
    mock_PGNData.assert_called_once_with(readonly=False)
    mock_PGNCache.assert_called_once()
    mock_walk.assert_called_once_with('/some/dir')
    # Expect LoadFromDisk called for the .pgn files:
    # '/some/dir/file1.pgn' and '/some/dir/subdir/subfile.pgn'
    calls: list = [  # type:ignore
        mock.call('/some/dir/file1.pgn'),
        mock.call().__iter__(),  # pylint: disable=unnecessary-dunder-call
        mock.call('/some/dir/subdir/subfile.pgn'),
        mock.call().__iter__(),  # pylint: disable=unnecessary-dunder-call
    ]
    mock_db.LoadFromDisk.assert_has_calls(calls, any_order=False)
    # total 2 calls
    self.assertEqual(mock_db.LoadFromDisk.call_count, 2)
    mock_db.Close.assert_called_once()

  @mock.patch('pawnalyze.pawningest.pawnlib.PGNData')
  @mock.patch('pawnalyze.pawningest.pawnlib.PGNCache')
  def test_Main_Sources(self, mock_PGNCache: mock.MagicMock, mock_PGNData: mock.MagicMock) -> None:
    """Provide -s figshare.

    => _LoadFromSource => calls _LoadFromURL internally,
    which calls db.CachedLoadFromURL for each URL in _SOURCES dict.
    We'll see multiple calls to db.CachedLoadFromURL.
    """
    mock_db = mock.MagicMock()
    mock_PGNData.return_value = mock_db
    mock_cache = mock.MagicMock()
    mock_PGNCache.return_value = mock_cache
    test_args: list[str] = [
        'pawningest.py',
        '-s', 'figshare'
    ]
    with mock.patch.object(sys, 'argv', test_args):
      pawningest.Main()
    mock_PGNData.assert_called_once_with(readonly=False)
    mock_PGNCache.assert_called_once()
    # The 'figshare' entry is:
    # 'figshare': ('figshare.com','https://figshare.com/articles/...',['https://ndownloader.figstatic.com/files/6971717'])
    # => it calls _LoadFromURL(...) for each in the list
    # => which calls db.CachedLoadFromURL('https://ndownloader.figstatic.com/files/6971717', cache)
    mock_db.CachedLoadFromURL.assert_called_once_with(
        'https://ndownloader.figstatic.com/files/6971717', mock_cache)

    mock_db.Close.assert_called_once()

  def test_BadSource(self) -> None:
    """If user gave a source that isn't in _SOURCES => error out with ValueError."""
    test_args: list[str] = [
        'pawningest.py',
        '-s', 'foobar'
    ]
    with mock.patch.object(sys, 'argv', test_args):
      with self.assertRaisesRegex(ValueError, 'Invalid source in'):
        pawningest.Main()

  @mock.patch('pawnalyze.pawningest.pawnlib.PGNData')
  @mock.patch('pawnalyze.pawningest.pawnlib.PGNCache')
  def test_IgnoreCache(self, mock_PGNCache: mock.MagicMock, mock_PGNData: mock.MagicMock) -> None:
    """If user sets -i/--ignorecache, we skip creation of PGNCache."""
    mock_db = mock.MagicMock()
    mock_PGNData.return_value = mock_db
    test_args: list[str] = [
        'pawningest.py',
        '-s', 'figshare',
        '-i', '1'
    ]
    with mock.patch.object(sys, 'argv', test_args):
      pawningest.Main()
    # no cache created
    mock_PGNCache.assert_not_called()
    # but DB is created
    mock_PGNData.assert_called_once_with(readonly=False)
    mock_db.Close.assert_called_once()

  @mock.patch('pawnalyze.pawningest.pawnlib.PGNData')
  def test_ReadOnly(self, mock_PGNData: mock.MagicMock) -> None:
    """If user sets -r/--readonly, we create PGNData(readonly=True)."""
    mock_db = mock.MagicMock()
    mock_PGNData.return_value = mock_db
    test_args: list[str] = [
        'pawningest.py',
        '-s', 'figshare',
        '-r', '1'
    ]
    with mock.patch.object(sys, 'argv', test_args):
      pawningest.Main()
    mock_PGNData.assert_called_once_with(readonly=True)
    mock_db.Close.assert_called_once()


SUITE: unittest.TestSuite = unittest.TestLoader().loadTestsFromTestCase(TestPawnIngest)


if __name__ == '__main__':
  logging.basicConfig(level=logging.INFO, format=base.LOG_FORMAT)  # set this as default
  unittest.main()
