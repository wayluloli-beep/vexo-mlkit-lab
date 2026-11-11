import unittest
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from memory_review import review_text

BOUNDED_DIMS = """
public final class CaptureDimensions {
    private static final int MAX_DIMENSION=4096;
    private static final long MAX_PIXELS=6_000_000L;
    public static int[] fit(int width,int height) {
        if(width<=0||height<=0) throw new IllegalArgumentException();
        long pixels=(long)width*height;
        double scale=Math.min(1.0,
            Math.min(MAX_DIMENSION/(double)Math.max(width,height),
                     Math.sqrt(MAX_PIXELS/(double)pixels)));
        int w=Math.max(1,(int)Math.floor(width*scale));
        int h=Math.max(1,(int)Math.floor(height*scale));
        return new int[]{w,h};
    }
}
"""


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


    def test_pr24_bounded_fit_feeds_both_reader_allocations(self):
        source = """void initiate() {
    int[] fitted=CaptureDimensions.fit(requestedWidth,requestedHeight);
    width=fitted[0];height=fitted[1];
    imageReader=ImageReader.newInstance(width,height,PixelFormat.RGBA_8888,3);
}
void resize(int w,int h) {
    int[] fitted=CaptureDimensions.fit(w,h);
    w=fitted[0];h=fitted[1];
    ImageReader replacement=ImageReader.newInstance(w,h,PixelFormat.RGBA_8888,3);
}"""
        self.assertEqual("PASS", review_text(source, BOUNDED_DIMS)[0]["status"])

    def test_fit_called_but_output_not_used_fails(self):
        source = """void initiate() {
    int[] fitted=CaptureDimensions.fit(requestedWidth,requestedHeight);
    imageReader=ImageReader.newInstance(requestedWidth,requestedHeight,1,3);
}"""
        self.assertEqual("FAIL", review_text(source, BOUNDED_DIMS)[0]["status"])

    def test_fit_in_other_method_does_not_protect_resize(self):
        source = """void initiate() {
    int[] fitted=CaptureDimensions.fit(w,h);
    w=fitted[0];h=fitted[1];
    reader=ImageReader.newInstance(w,h,1,3);
}
void resize(int w,int h) {
    replacement=ImageReader.newInstance(w,h,1,3);
}"""
        self.assertEqual("FAIL", review_text(source, BOUNDED_DIMS)[0]["status"])

    def test_fit_helper_without_actual_limits_fails(self):
        fake = """public class CaptureDimensions {
    public static int[] fit(int width,int height) {
       int w=width,h=height; return new int[]{w,h};
    }
}"""
        source = """void resize(int w,int h) {
    int[] fitted=CaptureDimensions.fit(w,h);
    w=fitted[0];h=fitted[1];
    replacement=ImageReader.newInstance(w,h,1,3);
}"""
        self.assertEqual("FAIL", review_text(source, fake)[0]["status"])

    def test_fit_without_helper_source_does_not_pass(self):
        source = """void resize(int w,int h) {
    int[] fitted=CaptureDimensions.fit(w,h);
    w=fitted[0];h=fitted[1];
    replacement=ImageReader.newInstance(w,h,1,3);
}"""
        self.assertEqual("FAIL", review_text(source)[0]["status"])

    def test_fit_indices_swapped_are_rejected(self):
        source = """void resize(int w,int h) {
    int[] fitted=CaptureDimensions.fit(w,h);
    w=fitted[1];h=fitted[0];
    replacement=ImageReader.newInstance(w,h,1,3);
}"""
        self.assertEqual("FAIL", review_text(source, BOUNDED_DIMS)[0]["status"])



if __name__ == "__main__":
    unittest.main()
