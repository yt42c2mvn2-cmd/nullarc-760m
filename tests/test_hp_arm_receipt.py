"""Exercise the operator helper against the actual binary atomic-write contract."""
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'tools'),str(ROOT/'install'),str(ROOT/'tools/phxctl')]
import hp_arm_persistence as handoff

class ReceiptTests(unittest.TestCase):
    def test_verified_authorization_receipt_exports_bytes_and_private_permissions(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'result.json'
            report={'persistent_authorized':True,'nvram_verified':True,'note':'GPU ✓'}
            with patch.object(handoff.os,'chown') as owner:
                handoff.publish_receipt(path,report,501,20)
            self.assertEqual(json.loads(path.read_bytes()),report)
            self.assertEqual(path.stat().st_mode&0o777,0o600)
            owner.assert_called_once_with(path,501,20)
            self.assertEqual(list(Path(tmp).iterdir()),[path])
if __name__=='__main__':unittest.main()
