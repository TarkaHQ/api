"""The generated contract preserves price consent and explicit placement."""
import json
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]

class BillingQuoteContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.doc = json.loads((ROOT / 'openapi/tarka-control-v1.swagger.json').read_text())

    def test_quote_and_acceptance_are_org_scoped(self):
        for path, method in [('/compute-quotes', 'post'), ('/usage-policy', 'get'), ('/usage-policy/accept', 'post')]:
            op = self.doc['paths']['/control/v1/orgs/{org_id}' + path][method]
            org = next(p for p in op['parameters'] if p['name'] == 'org_id')
            self.assertTrue(org['required'])
        quote = self.doc['definitions']['v1ComputeQuote']['properties']
        for field in ['currency', 'pricing_version', 'maximum_reservation_microcents', 'expires_at', 'max_network_bytes', 'fx_numerator', 'fx_denominator']:
            self.assertIn(field, quote)

    def test_create_accepts_quote_without_breaking_legacy_eu(self):
        for name in ['ProvisioningServiceCreateAgentHostBody', 'ProvisioningServiceCreateJobBody', 'SandboxServiceCreateSandboxBody']:
            definition = self.doc['definitions'][name]
            self.assertIn('accepted_quote_id', definition['properties'])
            self.assertNotIn('accepted_quote_id', definition.get('required', []))

    def test_agent_disk_and_startup_consent_are_explicit(self):
        quote = self.doc['definitions']['v1ComputeQuote']['properties']
        for field in ['persistent_storage_bytes', 'persistent_storage_gib_month_microcents', 'persistent_storage_period_seconds', 'startup_reservation_microcents', 'network_allowance_period_seconds']:
            self.assertIn(field, quote)
        body = self.doc['definitions']['ProvisioningServiceCreateAgentHostBody']
        self.assertIn('max_network_bytes', body['properties'])
        self.assertNotIn('max_network_bytes', body.get('required', []))

    def test_omitted_location_has_no_implicit_cost_increase(self):
        for name in ['ProvisioningServiceCreateJobBody', 'SandboxServiceCreateSandboxBody']:
            location = self.doc['definitions'][name]['properties']['location']
            self.assertIn('eu-1', location.get('description', '') + location.get('title', ''))
        policy = self.doc['definitions']['v1UsagePolicy']['properties']
        self.assertIn('charging_ready', policy)
        self.assertIn('accepted_at', policy)

if __name__ == '__main__':
    unittest.main()
