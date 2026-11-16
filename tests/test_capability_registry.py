import unittest
from capability_registry import capability_profile

class CapabilityRegistryTests(unittest.TestCase):
    def test_registry_only_advertises_real_animated_environments(self):
        profile = capability_profile()
        self.assertEqual(profile["environments"]["animated_backgrounds"],
                         ["beach", "ocean", "sea", "underwater"])
        self.assertIn("forest", profile["environments"]["base_plate_only"])

    def test_registry_exposes_actual_species_and_known_limits(self):
        profile = capability_profile()
        species = profile["characters"]["native_species"]
        self.assertIn("human", species)
        self.assertIn("bear", species)
        self.assertIn("rabbit", species)
        self.assertIn("path_points", profile["timeline"])
        self.assertIn("subject_tracking", profile["camera"])
        self.assertTrue(profile["limitations"])

if __name__ == "__main__":
    unittest.main()
