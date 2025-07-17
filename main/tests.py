from django.test import TestCase
from django.utils import timezone
from .models import TemporalImage, CustomUser
from .views import calculate_phash, hamming_distance
from PIL import Image



class TemporalImageModelTest(TestCase):
    def test_draft_expiration(self):
        user = CustomUser.objects.create(username='test', password='test')
        draft = TemporalImage.objects.create(
            user=user,
            title="Draft Test",
            status=TemporalImage.ImageStatus.DRAFT
        )
        self.assertIsNotNone(draft.expiration_time)
        self.assertGreater(draft.expiration_time, timezone.now())



class PhashTest(TestCase):
    def test_phash_generation(self):
        test_image = Image.new('L', (32, 32), color=127)

        phash = calculate_phash(test_image)

        self.assertEqual(len(phash), 16)
        self.assertTrue(phash.isalnum())
        self.assertTrue(all(c in '0123456789abcdef' for c in phash))



class HammingDistanceTest(TestCase):
    def test_hamming_calculation(self):
        self.assertEqual(hamming_distance("1234567890abcdef", "1234567890abcdef"), 0)
        self.assertEqual(hamming_distance("a", "b"), 1)  # a=1010, b=1011 (4-й бит)
        self.assertEqual(hamming_distance("0000000000000000", "ffffffffffffffff"), 63)