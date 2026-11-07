import copy
import unittest

from validate_openapi import RUNTIME_PATH, load, validate_runtime


class RuntimeContractTests(unittest.TestCase):
    def test_contract(self):
        validate_runtime(load(RUNTIME_PATH))

    def test_identity_selection_and_credential_disclosure_rejected(self):
        original = load(RUNTIME_PATH)
        for name, key in (("StartRun", "subject_id"), ("RenewRun", "permissions"),
                          ("RunDescription", "credential"), ("ClaimMessage", "actor_id"),
                          ("ReplyMessage", "recipient")):
            document = copy.deepcopy(original)
            document["components"]["schemas"][name]["properties"][key] = {"type": "string"}
            with self.assertRaises(ValueError):
                validate_runtime(document)

    def test_authentication_cannot_be_disabled(self):
        document = load(RUNTIME_PATH)
        next(iter(document["paths"].values()))["post"]["security"] = []
        with self.assertRaises(ValueError):
            validate_runtime(document)
