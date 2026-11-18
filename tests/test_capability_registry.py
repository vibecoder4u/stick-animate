import unittest
from capability_registry import capability_profile

class CapabilityRegistryTests(unittest.TestCase):
    def test_environment_capabilities_are_honest(self):
        profile = capability_profile()
        self.assertEqual(profile["environments"]["animated_backgrounds"],
                         ["beach", "ocean", "sea", "underwater"])
        self.assertIn("forest", profile["environments"]["base_plate_only"])

    def test_renderer_features_are_exposed(self):
        profile = capability_profile()
        self.assertIn("bear", profile["characters"]["native_species"])
        self.assertIn("dinosaur", profile["characters"]["native_species"])
        self.assertIn("path_points", profile["timeline"])
        self.assertIn("subject_tracking", profile["camera"])
        self.assertEqual(len(profile["characters"]["approved_human_cast"]), 8)
        self.assertIn("manual_user_approval", profile["characters"]["special_character_policy"])
        self.assertIn("brain", profile["stickers"])
        self.assertTrue(profile["limitations"])

if __name__ == "__main__":
    unittest.main()
