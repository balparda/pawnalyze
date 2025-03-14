#!/usr/bin/python3 -bb
#
# Copyright 2025 Daniel Balparda (balparda@gmail.com)
# GNU General Public License v3 (http://www.gnu.org/licenses/gpl-3.0.txt)
#
# pylint: disable=invalid-name,protected-access
"""pawnmaintain.py unittest."""

import io
import logging
# import pdb
import unittest
from unittest import mock

from baselib import base
from pawnalyze import ecoingest

__author__ = 'balparda@gmail.com (Daniel Balparda)'
__version__ = (1, 0)


class TestECOIngest(unittest.TestCase):
  """Tests for ecoingest.py."""

  def setUp(self) -> None:
    # minimal valid TSV lines for each of the five URLs
    self.tsv_contents: list[bytes] = [
        b"eco\tname\t pgn\nA00\tAnderssen Opening\t1. a3\nA01\tNimzovich-Larsen Attack\t1. b3\n",
        b"eco\tname\t pgn\nB00\tOther Opening\t1. h3\nB01\tTest Variation\t1. e4\n",
        b"eco\tname\t pgn\nC00\tFrench Defense\t1. e4 e6\nC01\tAnother Variation\t1. e4 e6 2. d4 d5\n",
        b"eco\tname\t pgn\nD00\tQueen's Pawn\t1. d4 d5\nD01\tTorre Attack\t1. d4 Nf6 2. Nf3 e6\n",
        b"eco\tname\t pgn\nE00\tCatalan Opening\t1. d4 Nf6 2. c4 e6 3. g3\nE01\tAnother Catalan\t1. d4 Nf6 2. c4 e6 3. g3 d5\n",
    ]

  @mock.patch('ecoingest.urllib.request.urlopen')
  @mock.patch('builtins.open', new_callable=mock.mock_open)
  def test_main(self, mock_file_open: mock.MagicMock, mock_url_open: mock.MagicMock) -> None:
    """Test."""
    self.maxDiff = None
    mock_url_open.side_effect = [io.BytesIO(content) for content in self.tsv_contents]
    ecoingest.Main()
    mock_file_open.assert_called_once()
    handle = mock_file_open.return_value
    written_text: str = ''.join(k for k in handle.writelines.call_args_list[0].args[0])
    self.assertEqual(written_text, _ECO_FILE)


_ECO_FILE: str = """\
[
["09e41bd5282ebaaf9f7a3e7c866e5382", "A00", "Anderssen Opening", "1. a3", [["a3",816,"09e41bd5282ebaaf9f7a3e7c866e5382",2]]],
["7504991f9af1fa6d6c0862176b8fbd51", "A01", "Nimzovich-Larsen Attack", "1. b3", [["b3",917,"7504991f9af1fa6d6c0862176b8fbd51",2]]],
["ba6df00a165a684bc0044c671e50ed52", "B00", "Other Opening", "1. h3", [["h3",1523,"ba6df00a165a684bc0044c671e50ed52",2]]],
["26fa396cc6f30847ac0eb2f3ba3997ce", "B01", "Test Variation", "1. e4", [["e4",1228,"26fa396cc6f30847ac0eb2f3ba3997ce",2]]],
["41632add6b250700df39e622411109ec", "C00", "French Defense", "1. e4 e6", [["e4",1228,"26fa396cc6f30847ac0eb2f3ba3997ce",2], ["e6",5244,"41632add6b250700df39e622411109ec",1]]],
["3a26f37bdf417fce5702b8abc378596f", "C01", "Another Variation", "1. e4 e6 2. d4 d5", [["e4",1228,"26fa396cc6f30847ac0eb2f3ba3997ce",2], ["e6",5244,"41632add6b250700df39e622411109ec",1], ["d4",1127,"35701ec28b1754313a052c7da86d2c5c",2], ["d5",5135,"3a26f37bdf417fce5702b8abc378596f",1]]],
["4120eba626683215de17b17bce03a612", "D00", "Queen's Pawn", "1. d4 d5", [["d4",1127,"4e76061f723e19eab31025ada516d321",2], ["d5",5135,"4120eba626683215de17b17bce03a612",1]]],
["5cf200a8e1d944c65aa85170ceec4bc4", "D01", "Torre Attack", "1. d4 Nf6 2. Nf3 e6", [["d4",1127,"4e76061f723e19eab31025ada516d321",2], ["Nf6",6245,"1a5492d26859a8750581110af23c31f7",1], ["Nf3",621,"3b6b13194c0f4b81299f05a135c4d5e6",2], ["e6",5244,"5cf200a8e1d944c65aa85170ceec4bc4",1]]],
["2ede555898bc45024e0de17fa01c6a92", "E00", "Catalan Opening", "1. d4 Nf6 2. c4 e6 3. g3", [["d4",1127,"4e76061f723e19eab31025ada516d321",2], ["Nf6",6245,"1a5492d26859a8750581110af23c31f7",1], ["c4",1026,"2247c21ca94cf400a0ff36b1a64c9331",2], ["e6",5244,"45ded1ad049afb47d3c862605d640d13",1], ["g3",1422,"2ede555898bc45024e0de17fa01c6a92",2]]],
["2188b8e1ccea6efd230a75a9cb091fa1", "E01", "Another Catalan", "1. d4 Nf6 2. c4 e6 3. g3 d5", [["d4",1127,"4e76061f723e19eab31025ada516d321",2], ["Nf6",6245,"1a5492d26859a8750581110af23c31f7",1], ["c4",1026,"2247c21ca94cf400a0ff36b1a64c9331",2], ["e6",5244,"45ded1ad049afb47d3c862605d640d13",1], ["g3",1422,"2ede555898bc45024e0de17fa01c6a92",2], ["d5",5135,"2188b8e1ccea6efd230a75a9cb091fa1",1]]]
]
"""


SUITE: unittest.TestSuite = unittest.TestLoader().loadTestsFromTestCase(TestECOIngest)


if __name__ == '__main__':
  logging.basicConfig(level=logging.INFO, format=base.LOG_FORMAT)  # set this as default
  unittest.main()
