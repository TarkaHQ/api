import copy
import unittest

from validate_openapi import IAM_OAUTH_PATH, load, validate_iam_oauth


class CustomerOAuthContractTests(unittest.TestCase):
    def test_contract(self):
        validate_iam_oauth(load(IAM_OAUTH_PATH))

    def test_no_credential_or_authority_onboarding(self):
        original = load(IAM_OAUTH_PATH)
        for name in ("client_secret", "agent_id", "allowed_audiences"):
            document = copy.deepcopy(original)
            schema = document["components"]["schemas"]["PublicClientRegistration"]
            schema["not"]["anyOf"] = [item for item in schema["not"]["anyOf"] if item["required"] != [name]]
            with self.assertRaises(ValueError):
                validate_iam_oauth(document)

    def test_pkce_resource_and_issuer_cannot_weaken(self):
        original = load(IAM_OAUTH_PATH)
        for field in ("code_challenge_method", "resource"):
            document = copy.deepcopy(original)
            params = document["paths"]["/oauth2/auth"]["get"]["parameters"]
            param = next(item for item in params if item["name"] == field)
            if field == "resource":
                param["required"] = False
            else:
                param["schema"]["enum"].append("plain")
            with self.assertRaises(ValueError):
                validate_iam_oauth(document)
