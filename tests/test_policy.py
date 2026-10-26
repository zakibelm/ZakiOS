import unittest

from zakios import policy
from zakios.classify import COMPONENT_TYPES


class PolicyTests(unittest.TestCase):
    def test_behavior_types_are_never_decided_by_score(self):
        for ctype in policy.BEHAVIOR_TYPES:
            for score in (0.0, 0.39, 0.5, 0.99, 1.0):
                self.assertEqual(policy.status_for(ctype, score, True), policy.STATUS_BEHAVIOR)

    def test_thresholds(self):
        self.assertEqual(policy.status_for("agent", 0.60, True), policy.STATUS_EQUIVALENCE)
        self.assertEqual(policy.status_for("agent", 0.59, True), policy.STATUS_PARTIAL)
        self.assertEqual(policy.status_for("agent", 0.40, True), policy.STATUS_PARTIAL)
        self.assertEqual(policy.status_for("agent", 0.39, True), policy.STATUS_NOVELTY)

    def test_low_score_is_not_proof_of_novelty(self):
        self.assertIn("ne prouve pas", policy.PROPOSALS[policy.STATUS_NOVELTY])

    def test_no_text_means_insufficient_metadata(self):
        self.assertEqual(policy.status_for("skill", 0.0, False), policy.STATUS_INSUFFICIENT)

    def test_no_affirmative_proposal_anywhere(self):
        for text in policy.PROPOSALS.values():
            self.assertNotIn("adopter", text.lower())
        self.assertEqual(set(policy.PROPOSALS), set(policy.STATUSES))

    def test_every_type_has_a_family(self):
        for ctype in COMPONENT_TYPES:
            self.assertTrue(policy.family_of(ctype))


if __name__ == "__main__":
    unittest.main()
