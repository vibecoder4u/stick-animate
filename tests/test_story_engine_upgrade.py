import unittest
from PIL import Image, ImageChops
from transition_engine import crossfade, smoothstep
import stick_animate

class StoryEngineUpgradeTests(unittest.TestCase):
    def test_crossfade_endpoints_and_midpoint(self):
        a=Image.new('RGB',(64,64),(0,0,0)); b=Image.new('RGB',(64,64),(255,255,255))
        self.assertEqual(crossfade(b,a,0).getpixel((0,0)),(0,0,0))
        self.assertEqual(crossfade(b,a,1).getpixel((0,0)),(255,255,255))
        self.assertTrue(0 < crossfade(b,a,.5).getpixel((0,0))[0] < 255)
    def test_easing_is_monotonic_and_bounded(self):
        vals=[smoothstep(i/10) for i in range(11)]
        self.assertEqual(vals[0],0); self.assertEqual(vals[-1],1)
        self.assertEqual(vals,sorted(vals))
    def test_story_backgrounds_are_distinct_and_full_size(self):
        for kind in ('bedroom','classroom','office','park'):
            im=stick_animate.gradient_background(kind)
            self.assertEqual(im.size,(1280,720))
        self.assertNotEqual(stick_animate.gradient_background('bedroom').getpixel((100,100)),stick_animate.gradient_background('classroom').getpixel((100,100)))
if __name__=='__main__': unittest.main()
