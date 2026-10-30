from pathlib import Path
import unittest
from strict_json import load_json_object
ROOT = Path(__file__).resolve().parents[1]
class SourceBuildContract(unittest.TestCase):
    def test_org_scoped_routes_and_no_credential_exchange_inputs(self):
        contract = load_json_object(ROOT / 'openapi/tarka-control-v1.swagger.json')
        paths = [p for p in contract['paths'] if '/source/' in p]
        self.assertGreaterEqual(len(paths), 10)
        self.assertTrue(all(p.startswith('/control/v1/orgs/{org_id}/source/') for p in paths))
        for name, definition in contract['definitions'].items():
            if 'Source' in name:
                self.assertFalse({'access_token', 'refresh_token', 'client_secret', 'private_key', 'password'} & definition.get('properties', {}).keys(), name)
    def test_no_customer_build_credentials_or_privileged_options(self):
        definitions = load_json_object(ROOT / 'openapi/tarka-control-v1.swagger.json')['definitions']
        self.assertEqual(set(definitions['v1SourceBuildService']['properties']), {'name', 'context', 'dockerfile'})
        self.assertEqual(definitions['v1SourceBuildConfig']['properties']['services']['maxItems'], 8)
        self.assertIn('allowance_consumed', definitions['v1SourceBuild']['properties'])
        self.assertNotIn('cost_microcents', definitions['v1SourceBuild']['properties'])
        self.assertIn('next_sequence', definitions['v1GetSourceBuildLogsResponse']['properties'])
if __name__ == '__main__': unittest.main()
