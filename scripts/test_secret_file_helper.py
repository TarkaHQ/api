import contextlib
import importlib.util
import io
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

HELPERS = Path(__file__).resolve().parents[1] / 'examples/tarka-control-api/scripts'
sys.path.insert(0, str(HELPERS))
spec = importlib.util.spec_from_file_location('tarka_secret_upload', HELPERS / 'secrets.py')
helper = importlib.util.module_from_spec(spec)
spec.loader.exec_module(helper)


class SecretFileHelperTests(unittest.TestCase):
    def test_env_is_literal_and_json_rejects_duplicate_and_nested_values(self):
        self.assertEqual(helper.parse_values("TOKEN='$(touch /tmp/nope) ${HOME}'\nEMPTY="), {'TOKEN': '$(touch /tmp/nope) ${HOME}', 'EMPTY': ''})
        self.assertEqual(helper.parse_values('{"TOKEN":"abc"}'), {'TOKEN': 'abc'})
        for raw in ['{"TOKEN":"a","TOKEN":"b"}', '{"TOKEN":{"NESTED":"secret"}}', 'TOKEN="private-value', 'TOKEN=a\nTOKEN=b']:
            with self.assertRaises(ValueError) as error:
                helper.parse_values(raw)
            self.assertNotIn('private-value', str(error.exception))

    def test_helper_streams_values_and_prints_only_metadata(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'secrets.env'
            path.write_text('TOKEN=private-fixture-value')
            output = io.StringIO()
            with patch.dict(os.environ, {'TARKA_ACCESS_TOKEN': 'local-session'}), patch.object(helper, 'call', return_value={'status': 'ready', 'unexpected_secret': 'private-fixture-value'}) as call, contextlib.redirect_stdout(output):
                result = helper.main(['--org', '00000000-0000-0000-0000-000000000001', '--bundle', '00000000-0000-0000-0000-000000000002', '--file', str(path)])
            self.assertEqual(result, 0)
            self.assertEqual(call.call_args.args[-1], {'values': {'TOKEN': 'private-fixture-value'}})
            self.assertIn('secrets_bundle_id', output.getvalue())
            self.assertNotIn('private-fixture-value', output.getvalue())
            self.assertNotIn('local-session', output.getvalue())
