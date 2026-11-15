import tempfile
import unittest
import wave
from pathlib import Path
from audio_director import plan_scene_audio, render_audio, validate_audio_cues

class SceneAudioTests(unittest.TestCase):
    def test_door_sound_is_not_footsteps(self):
        script={'duration':4,'scenes':[{'start':0,'end':2,'environment':'corridor','door_open':0},{'start':2,'end':4,'environment':'corridor','door_open':0.8,'actor':{'keyframes':[{'t':0,'x':100,'pose':'idle'},{'t':1,'x':100,'pose':'idle'}]}}]}
        self.assertEqual([c['event'] for c in plan_scene_audio(script)],['door_open'])
    def test_footsteps_need_walk_and_movement(self):
        script={'duration':3,'scenes':[{'start':0,'end':3,'environment':'corridor','actor':{'keyframes':[{'t':0,'x':100,'pose':'walk'},{'t':1,'x':300,'pose':'walk'}]}}]}
        self.assertIn('footsteps',[c['event'] for c in plan_scene_audio(script)])
    def test_rain_and_birds_need_matching_visual_evidence(self):
        script={'duration':4,'scenes':[{'start':0,'end':2,'environment':'rainroom'},{'start':2,'end':4,'environment':'forest','actors':[{'species':'bird'}]}]}
        self.assertEqual([c['event'] for c in plan_scene_audio(script)],['rain','bird_wings'])
    def test_every_cue_requires_evidence_and_valid_timing(self):
        with self.assertRaises(ValueError): validate_audio_cues([{'event':'footsteps','start':0,'duration':1}],2)
        with self.assertRaises(ValueError): validate_audio_cues([{'event':'rain','start':1,'duration':3,'evidence':'rain'}],2)
    def test_fear_and_explicit_metal_impact_add_distinct_effects(self):
        script={"duration":4,"scenes":[
            {"start":0,"end":2,"environment":"corridor","actor":{"expression":"fear","keyframes":[{"t":0,"x":100,"pose":"fear"},{"t":1,"x":100,"pose":"fear"}]}},
            {"start":2,"end":4,"environment":"corridor","visual_events":[{"type":"metal_clang","at":0.5,"evidence":"gate hits stop"}]}
        ]}
        self.assertEqual([c["event"] for c in plan_scene_audio(script)],["heartbeat","metal_clang"])

    def test_narration_does_not_create_sfx(self):
        script={"duration":2,"scenes":[{"start":0,"end":2,"environment":"corridor",
            "narration":"A loud metal clang and footsteps echoed in the rain."}]}
        self.assertEqual(plan_scene_audio(script), [])

    def test_audio_is_stereo_pcm(self):
        script={'duration':1,'scenes':[{'start':0,'end':1,'environment':'rainroom'}]}
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'mix.wav'; cues=render_audio(script,path)
            self.assertEqual(cues[0]['event'],'rain')
            with wave.open(str(path),'rb') as wav:
                self.assertEqual(wav.getnchannels(),2); self.assertEqual(wav.getframerate(),22050); self.assertEqual(wav.getnframes(),22050)

if __name__=='__main__': unittest.main()
