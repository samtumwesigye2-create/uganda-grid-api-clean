import unittest

from address_confidence import evaluate_address_application


STATE={
    "state_code":"KMP",
    "state_name":"Kampala Metropolitan State",
    "grid_prefix":"KLA",
    "postal_prefix":"20",
}
POSTAL={"zip_code":"20401","region":"KLA","name":"Test Zone"}


class HybridAddressConfidenceTests(unittest.TestCase):
    def test_high_confidence_low_density_auto_approves(self):
        result=evaluate_address_application(
            0.31062,32.58056,[],STATE,POSTAL,gps_accuracy_m=4.0,is_special=False
        )
        self.assertTrue(result["auto_approve"])
        self.assertEqual(result["decision"],"auto_approve")
        self.assertGreaterEqual(result["score"],90)

    def test_duplicate_risk_requires_review(self):
        addresses=[{"latitude":0.31062,"longitude":32.58056,"grid_id":"KLA-000001"}]
        result=evaluate_address_application(
            0.31062,32.58056,addresses,STATE,POSTAL,gps_accuracy_m=3.0,is_special=False
        )
        self.assertFalse(result["auto_approve"])
        self.assertEqual(result["decision"],"manual_review")
        self.assertIn("possible_existing_address_duplicate",result["reasons"])

    def test_dense_environment_requires_review(self):
        # Four known addresses within roughly 60 m of the application.
        addresses=[
            {"latitude":0.31070,"longitude":32.58056},
            {"latitude":0.31080,"longitude":32.58056},
            {"latitude":0.31062,"longitude":32.58075},
            {"latitude":0.31062,"longitude":32.58090},
        ]
        result=evaluate_address_application(
            0.31062,32.58056,addresses,STATE,POSTAL,gps_accuracy_m=4.0,is_special=False
        )
        self.assertFalse(result["auto_approve"])
        self.assertIn("dense_address_environment",result["reasons"])

    def test_special_location_always_requires_review(self):
        result=evaluate_address_application(
            0.31062,32.58056,[],STATE,POSTAL,gps_accuracy_m=2.0,is_special=True
        )
        self.assertFalse(result["auto_approve"])
        self.assertEqual(result["score"],0)
        self.assertIn("protected_or_special_location",result["reasons"])

    def test_missing_gps_accuracy_does_not_auto_approve(self):
        result=evaluate_address_application(
            0.31062,32.58056,[],STATE,POSTAL,gps_accuracy_m=None,is_special=False
        )
        self.assertFalse(result["auto_approve"])
        self.assertIn("gps_accuracy_not_reported",result["reasons"])

    def test_ambiguous_boundary_requires_review(self):
        state=dict(STATE)
        state["ambiguous"]=True
        result=evaluate_address_application(
            0.31062,32.58056,[],state,POSTAL,gps_accuracy_m=2.0,is_special=False
        )
        self.assertFalse(result["auto_approve"])
        self.assertEqual(result["score"],0)
        self.assertIn("state_boundary_ambiguous",result["reasons"])


if __name__ == "__main__":
    unittest.main()
