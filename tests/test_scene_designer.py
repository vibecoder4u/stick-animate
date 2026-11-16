import unittest

from scene_designer import design_story, split_beats


class SceneDesignerTests(unittest.TestCase):
    def test_splits_story_into_multiple_timed_shots(self):
        script = design_story(
            "The train left the platform. A locked service gate opened. "
            "He ran into the tunnel. A shadow waited at the exit.",
            24, "Night Train",
        )
        self.assertEqual(len(script["scenes"]), 4)
        self.assertEqual(script["scenes"][0]["environment"], "platform")
        self.assertEqual(script["scenes"][1]["environment"], "service_gate")
        self.assertEqual(script["scenes"][2]["environment"], "tunnel")
        self.assertEqual(script["scenes"][3]["environment"], "exit")
        self.assertEqual(script["scenes"][-1]["end"], 24)

    def test_shot_types_and_camera_compositions_vary(self):
        script = design_story(
            "He entered the hallway. He heard a whisper. He looked back. "
            "He ran toward the street. A shadow appeared.",
            30,
        )
        shots = [s["shot_design"]["shot_type"] for s in script["scenes"]]
        self.assertGreater(len(set(shots)), 1)
        self.assertGreater(len({s["camera"]["pan"] for s in script["scenes"]}), 1)

    def test_duration_and_empty_text_are_validated(self):
        with self.assertRaises(ValueError):
            design_story("   ", 10)
        with self.assertRaises(ValueError):
            design_story("A story.", 0)


    def test_human_protagonist_stays_visible_across_environment_beats(self):
        plan = design_story(
            "At midnight the train left the station. A gate opened by itself. "
            "He heard a clang in the tunnel. He ran toward the exit.", 24
        )
        actors = [scene.get("actor") for scene in plan["scenes"]]
        self.assertTrue(all(actor for actor in actors))
        self.assertTrue(all(actor["species"] == "human" for actor in actors))
        self.assertEqual(len({actor["character_id"] for actor in actors}), 1)

    def test_free_planner_assigns_species_specific_actors(self):
        plan = design_story(
            "A dog runs through the forest. A bird flies above the river. "
            "A dinosaur roars beside the cave.", 30, "Wild Night"
        )
        species = [scene.get("actor", {}).get("species") for scene in plan["scenes"]]
        self.assertIn("dog", species)
        self.assertIn("bird", species)
        self.assertIn("dinosaur", species)


    def test_flood_story_builds_persistent_multi_species_cast(self):
        story = ("The peaceful jungle surrounds a wide river. Elephant Ella, a young deer, "
                 "a fox, a rabbit, a monkey, a colourful bird, a bear and a turtle gather. "
                 "Heavy rain falls and the river rises. The monkey climbs a tree while the bird scouts. "
                 "The bear and elephant pull a fallen tree into place. The fox guides the rabbit and deer. "
                 "The elephant catches the deer when it slips. All the animals reach safety.")
        plan = design_story(story, title="The Great Flood")
        species = {item["species"] for item in plan["design_metadata"]["cast"]}
        self.assertTrue({"elephant", "deer", "fox", "rabbit", "monkey", "bird", "bear", "turtle"}.issubset(species))
        self.assertEqual(len(plan["scenes"][1].get("actors", [])), 8)
        self.assertTrue(all(scene.get("actors") for scene in plan["scenes"]))

    def test_searching_does_not_trigger_beach_environment(self):
        from scene_designer import _environment
        self.assertEqual(_environment("The fox is searching beside the riverbank.", None), "river")


if __name__ == "__main__":
    unittest.main()
