import unittest
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from memory_review import review_text


class MemoryReviewTests(unittest.TestCase):
    def test_rejects_reader_without_budget(self):
        source = "ImageReader reader = ImageReader.newInstance(w,h,PixelFormat.RGBA_8888,3);"
        self.assertEqual("FAIL", review_text(source)[0]["status"])

    def test_accepts_guarded_reader(self):
        source = """checkFrameBudget(w,h);
ImageReader reader = ImageReader.newInstance(w,h,PixelFormat.RGBA_8888,3);"""
        self.assertEqual("PASS", review_text(source)[0]["status"])

    def test_rejects_unguarded_resize_even_if_initial_reader_guarded(self):
        source = """checkFrameBudget(width,height);
ImageReader initial = ImageReader.newInstance(width,height,1,3);
void resize(int w,int h) {
ImageReader replacement = ImageReader.newInstance(w,h,1,3);
}"""
        self.assertEqual("FAIL", review_text(source)[0]["status"])

    def test_late_extract_guard_does_not_prevent_allocation(self):
        source = """ImageReader reader = ImageReader.newInstance(w,h,1,3);
void extract() { checkFrameBudget(w,h); }"""
        self.assertEqual("FAIL", review_text(source)[0]["status"])


    def test_guard_in_different_method_does_not_protect_resize(self):
        source = """void initiate() {
    checkFrameBudget(width,height);
    ImageReader first=ImageReader.newInstance(width,height,1,3);
}
void resize(int w,int h) {
    ImageReader second=ImageReader.newInstance(w,h,1,3);
}"""
        self.assertEqual("FAIL", review_text(source)[0]["status"])

    def test_separate_budget_checks_per_method_satisfy_lexical_gate(self):
        source = """void initiate() {
    checkFrameBudget(width,height);
    ImageReader first=ImageReader.newInstance(width,height,1,3);
}
void resize(int w,int h) {
    checkFrameBudget(w,h);
    ImageReader second=ImageReader.newInstance(w,h,1,3);
}"""
        self.assertEqual("PASS", review_text(source)[0]["status"])

    def test_budget_check_only_in_comment_does_not_pass(self):
        source = """void initiate() {
    // checkFrameBudget(width,height);
    ImageReader first=ImageReader.newInstance(width,height,1,3);
}"""
        self.assertEqual("FAIL", review_text(source)[0]["status"])


if __name__ == "__main__":
    unittest.main()
