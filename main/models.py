from django.db import models
from django.core.files.storage import FileSystemStorage
import numpy as np
from scipy.fftpack import dct
from django.core.files.storage import default_storage as fs
from PIL import Image
from django.utils import timezone

# Create your models here.
class CustomUser(models.Model):
    username = models.CharField(max_length=50, unique=True, verbose_name="Логин")
    password = models.CharField(max_length=50, verbose_name="Пароль")
    is_active = models.BooleanField(default=True, verbose_name="Активен")
    date_joined = models.DateTimeField(auto_now_add=True, verbose_name="Дата регистрации")

    def __str__(self):
        return self.username

    class Meta:
        verbose_name = "Пользователь"
        verbose_name_plural = "Пользователи"



fs = FileSystemStorage(location='media/images')


class TemporalImage(models.Model):
    class ImageStatus(models.TextChoices):
        DRAFT = 'DR', 'Черновик'
        PUBLISHED = 'PB', 'Опубликовано'
        ARCHIVED = 'AR', 'Архивные изображения'

    user = models.ForeignKey('CustomUser', on_delete=models.CASCADE,
                             verbose_name="Идентификатор пользователя")
    status = models.CharField(max_length=2, choices=[ (ImageStatus.DRAFT.value,
            ImageStatus.DRAFT.label),
            (ImageStatus.PUBLISHED.value, ImageStatus.PUBLISHED.label),
            (ImageStatus.ARCHIVED.value, ImageStatus.ARCHIVED.label)
        ], default=ImageStatus.DRAFT, verbose_name="Статус изображения")
    title = models.CharField(max_length=255,verbose_name="Название изображения")
    upload_time = models.DateTimeField(auto_now_add=True,verbose_name="Время загрузки")
    expiration_time = models.DateTimeField(null=True,blank=True,verbose_name="Истечение срока")
    perceptual_hash = models.CharField(max_length=64,verbose_name="Перцептивный хэш")
    image_path = models.CharField(max_length=512,verbose_name="Путь к изображению",
        null=True,blank=True)

    def save(self, *args, **kwargs):
        if self.status == self.ImageStatus.PUBLISHED:
            self.expiration_time = None
        elif self.status == self.ImageStatus.DRAFT and not self.expiration_time:
            self.expiration_time = timezone.now() + timezone.timedelta(days=30)

        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        """Удаление файла из хранилища при удалении объекта"""
        if self.image_path:
            # Получаем экземпляр хранилища
            storage = fs

            # Удаляем файл, если он существует
            if storage.exists(self.image_path):
                storage.delete(self.image_path)

        super().delete(*args, **kwargs)

    def _process_image(self, image_file):

            filename = f"{self.user.id}_{timezone.now().timestamp()}.webp"
            path = fs.save(filename, image_file)
            self.image_path = path

            with fs.open(path) as f:
                img = Image.open(f)
                img = img.convert('L').resize((32, 32))

                img_array = np.array(img, dtype=np.float32) / 255.0

                dct_2d = dct(dct(img_array, axis=0, norm='ortho'), axis=1, norm='ortho')

                dct_coefficients = dct_2d[:8, :8].flatten()

                dct_roi = dct_coefficients[1:]

                mean_value = np.mean(dct_roi)

                bits = dct_roi > mean_value

                hash_int = sum(bit << (62 - i) for i, bit in enumerate(bits))

                self.perceptual_hash = f"{hash_int:016x}"



    class Meta:
        verbose_name = "Темпоральное изображение"
        verbose_name_plural = "Темпоральные изображения"
        indexes = [
            models.Index(fields=['perceptual_hash']),
            models.Index(fields=['expiration_time']),
            models.Index(fields=['user', 'status']),
        ]
        db_table = "temporal_images"

    def __str__(self):
        return f"{self.title} ({self.image_path})"


