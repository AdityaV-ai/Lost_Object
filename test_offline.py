"""Offline regression tests requiring no Flask server."""
import sys, unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parent
for name in ('fusion_module','location_module','text_module'):
    sys.path.insert(0,str(ROOT/'modules'/name))
from fusion_ranking import calculate_final_score
from location_similarity import calculate_distance, calculate_location_similarity
from text_similarity import compute_text_similarity
class OfflineTests(unittest.TestCase):
    def test_missing_image(self):
        self.assertAlmostEqual(calculate_final_score(None,.8,.6), (0.2*.8+0.1*.6)/.3)
    def test_no_signals(self):
        self.assertIsNone(calculate_final_score(None,None,None))
    def test_invalid_score(self):
        with self.assertRaises(ValueError): calculate_final_score(1.1,None,None)
    def test_location(self):
        self.assertAlmostEqual(calculate_distance(0,0,0,0),0)
        self.assertAlmostEqual(calculate_location_similarity(0),1)
    def test_text_only(self):
        score=compute_text_similarity('L1','F1',None,None,'blue water bottle','blue water bottle')
        self.assertGreater(score,.5)
if __name__=='__main__': unittest.main(verbosity=2)
