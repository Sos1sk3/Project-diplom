import traceback

from django.core.files.storage import FileSystemStorage
from django.shortcuts import get_object_or_404
from django.shortcuts import render, redirect
from .models import CustomUser, fs
from django.core.exceptions import ValidationError
from functools import wraps
from scipy.fftpack import dct
from PIL import Image
import datetime
from django.contrib import messages
import time
import numpy as np
from scipy.fft import dct
from django.shortcuts import render
from django.utils import timezone
from .models import TemporalImage

def login_required(view_func):
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        if 'user_id' not in request.session:
            return redirect('login')
        try:
            # Проверяем существование пользователя
            CustomUser.objects.get(id=request.session['user_id'])
            return view_func(request, *args, **kwargs)
        except CustomUser.DoesNotExist:
            request.session.flush()
            return redirect('login')
    return wrapper

@login_required
def home(request):
    return render(request, 'main/home.html')

def login_view(request):
    if request.method == 'POST':
        username = request.POST.get('username')
        password = request.POST.get('password')

        try:
            user = CustomUser.objects.get(username=username)
            if user.password == password:

                request.session['user_id'] = user.id
                request.session['username'] = user.username
                return redirect('home')
            else:
                messages.error(request, 'Неверный пароль')
        except CustomUser.DoesNotExist:
            messages.error(request, 'Пользователь не найден')

        return redirect('login')

    return render(request, 'main/login.html')


def logout_view(request):
    # Очищаем сессию
    request.session.flush()
    return redirect('login')



def delete_image(request, image_id):
    image = get_object_or_404(TemporalImage, id=image_id)
    image.delete()
    return redirect('image_work')



@login_required
def down_image(request):
    if request.method == 'POST':
        try:
            user = CustomUser.objects.get(id=request.session['user_id'])
            title = request.POST['title']
            status = request.POST['status']
            image_file = request.FILES['image']
            expiration_days = int(request.POST.get('expiration_days', 30))

            if not all([title, status, image_file]):
                raise ValidationError("Все поля обязательны для заполнения")

            temporal_image = TemporalImage(
                user=user,
                title=title,
                status=status
            )
            if status == TemporalImage.ImageStatus.DRAFT:
                temporal_image.expiration_time = timezone.now() + timezone.timedelta(
                    days=expiration_days
                )
            temporal_image._process_image(image_file)
            temporal_image.save()
            messages.success(request, "Изображение успешно загружено!")
            return redirect('home')
        except Exception as e:
            messages.error(request, f"Ошибка: {str(e)}")

    return render(request, 'main/download_image.html')


@login_required
def check_all_images(request):

    published_images = TemporalImage.objects.filter(
        status=TemporalImage.ImageStatus.PUBLISHED
    ).order_by('-upload_time')  # Сортировка по дате загрузки

    return render(request, 'main/all_images.html', {
        'images': published_images,
        'media_prefix': '/media/images/'  # Добавляем префикс для медиа-файлов
    })



@login_required
def draft_images(request):
    try:

        user_id = request.session['user_id']
        user = CustomUser.objects.get(id=user_id)

        drafts = TemporalImage.objects.filter(
            user=user,
            status=TemporalImage.ImageStatus.DRAFT
        ).order_by('-upload_time')

        return render(request, 'main/draft_images.html', {
            'drafts': drafts,
            'media_prefix': '/media/images/',
            'now': timezone.now()
        })

    except KeyError:

        return redirect('login')
    except CustomUser.DoesNotExist:
        request.session.flush()
        return redirect('login')


def calculate_phash(image):

    img = image.convert('L').resize((32, 32))
    img_array = np.array(img, dtype=np.float32) / 255.0
    dct_matrix = dct(dct(img_array, axis=0, norm='ortho'), axis=1, norm='ortho')
    dct_coefficients = dct_matrix[:8, :8].flatten()
    dct_roi = dct_coefficients[1:]
    mean_value = np.mean(dct_roi)
    bits = dct_roi > mean_value
    hash_int = sum(bit << (62 - i) for i, bit in enumerate(bits))
    return f"{hash_int:016x}"


def hamming_distance(hash1, hash2):
    bin_str1 = bin(int(hash1, 16))[2:].zfill(64)
    bin_str2 = bin(int(hash2, 16))[2:].zfill(64)
    return sum(c1 != c2 for c1, c2 in zip(bin_str1[1:], bin_str2[1:]))


    return sum(c1 != c2 for c1, c2 in zip(bin_str1, bin_str2))

def process_image_for_dct(image_file):
    # Аналог вашего метода из models.py
    img = Image.open(image_file)
    img = img.convert('L').resize((32, 32))
    img_array = np.array(img, dtype=np.float32) / 255.0
    dct_2d = dct(dct(img_array, axis=0, norm='ortho'), axis=1, norm='ortho')
    return dct_2d[:8, :8].flatten()[1:]

@login_required
def image_search(request):
    context = {'media_prefix': '/media/images/'}

    if request.method == 'POST':
        try:
            start_time = timezone.now()


            if 'search_image' not in request.FILES:
                raise ValueError("Необходимо выбрать изображение для поиска")

            image_file = request.FILES['search_image']
            max_distance = int(request.POST.get('max_distance', 5))
            start_date = request.POST.get('start_date')
            end_date = request.POST.get('end_date')
            method = request.POST.get('method', 'pHash')


            filters = {'status': TemporalImage.ImageStatus.PUBLISHED}
            date_filters = {}
            if start_date:
                date_filters['upload_time__gte'] = datetime.datetime.strptime(start_date, '%Y-%m-%d').date()
            if end_date:
                date_filters['upload_time__lte'] = datetime.datetime.strptime(end_date, '%Y-%m-%d').date()

            results = []


            if method == 'pHash':

                with Image.open(image_file) as img:
                    query_hash = calculate_phash(img)

                for image in TemporalImage.objects.filter(**filters, **date_filters):
                    stored_hash = image.perceptual_hash
                    distance = hamming_distance(query_hash, stored_hash)
                    if distance <= max_distance:
                        results.append({
                            'title': image.title,
                            'path': image.image_path,
                            'distance': distance,
                            'upload_time': image.upload_time
                        })

            elif method == 'ED':

                query_dct = process_image_for_dct(image_file)

                for image in TemporalImage.objects.filter(**filters, **date_filters):
                    try:

                        with fs.open(image.image_path) as f:
                            img = Image.open(f)
                            img = img.convert('L').resize((32, 32))
                            img_array = np.array(img, dtype=np.float32) / 255.0
                            dct_2d = dct(dct(img_array, axis=0, norm='ortho'), axis=1, norm='ortho')
                            stored_dct = dct_2d[:8, :8].flatten()[1:]


                        distance = np.linalg.norm(query_dct - stored_dct)
                        if distance <= max_distance * 10:
                            results.append({
                                'title': image.title,
                                'path': image.image_path,
                                'distance': distance,
                                'upload_time': image.upload_time
                            })

                    except Exception as e:
                        print(f"Ошибка обработки {image.id}: {str(e)}")


            context['results'] = sorted(results, key=lambda x: x['distance'])
            context['search_time'] = (timezone.now() - start_time).total_seconds()
            context['search_performed'] = True
            context['method'] = method

        except Exception as e:
            messages.error(request, f"Ошибка: {str(e)}")

    return render(request, 'main/image_search.html', context)

@login_required
def image_work(request):
    user_id = request.session.get('user_id')
    user = CustomUser.objects.get(id=user_id)

    published_images = TemporalImage.objects.filter(
        user=user,
        status=TemporalImage.ImageStatus.PUBLISHED
    ).order_by('-upload_time')

    draft_images = TemporalImage.objects.filter(
        user=user,
        status=TemporalImage.ImageStatus.DRAFT
    ).order_by('-upload_time')

    return render(request, 'main/image_work.html', {
        'published_images': published_images,
        'draft_images': draft_images,
        'media_prefix': '/media/images/'
    })


@login_required
def test_images(request):
    results = {
        'total': 0,
        'success': 0,
        'errors': [],
        'total_time': 0.0,
        'avg_time': 0.0,
        'hash_times': [],
        'saved_paths': [],
        'processed_files': []  # Добавлен недостающий ключ
    }

    # Конфигурационные параметры
    MAX_FILES = 100
    MAX_FILE_SIZE = 10 * 1024 * 1024  # 10 MB
    ALLOWED_TYPES = ['image/jpeg', 'image/png', 'image/webp']

    if request.method == 'POST' and request.FILES:
        try:
            user = CustomUser.objects.get(id=request.session['user_id'])
        except (KeyError, CustomUser.DoesNotExist):
            messages.error(request, "Требуется авторизация")
            return redirect('login')

        files = request.FILES.getlist('images')

        # Валидация количества файлов
        if len(files) > MAX_FILES:
            messages.error(request, f"Максимальное количество файлов за раз: {MAX_FILES}")
            return redirect('test_images')

        results['total'] = len(files)
        total_start = time.time()
        storage = FileSystemStorage(location='media/images')

        for idx, file in enumerate(files):
            file_start_time = time.time()
            file_record = {
                'name': file.name,
                'size': f"{file.size / 1024 / 1024:.2f}MB",
                'status': 'error'
            }

            try:
                # Валидация типа и размера файла
                if file.content_type not in ALLOWED_TYPES:
                    raise ValueError(f"Недопустимый тип файла: {file.content_type}")

                if file.size > MAX_FILE_SIZE:
                    raise ValueError(f"Файл превышает максимальный размер {MAX_FILE_SIZE // 1024 // 1024}MB")

                # Генерация уникального имени файла
                timestamp = int(time.time() * 1000)
                filename = f"{user.id}_{timestamp}_{idx}.webp"

                # Сохранение файла на диск
                saved_path = storage.save(filename, file)
                full_path = storage.path(saved_path)

                # Обработка изображения
                with Image.open(full_path) as img:
                    # Конвертация в градации серого и изменение размера
                    img = img.convert('L').resize((32, 32))

                    # Преобразование в numpy array
                    img_array = np.array(img, dtype=np.float32) / 255.0

                    # Применение DCT
                    dct_2d = dct(dct(img_array, axis=0, norm='ortho'), axis=1, norm='ortho')

                    # Стандартный pHash алгоритм
                    dct_coefficients = dct_2d[:8, :8].flatten()
                    dct_roi = dct_coefficients[1:]  # Исключаем DC-компонент
                    mean = np.mean(dct_roi)
                    bits = dct_roi > mean

                    # Формирование хеша
                    hash_int = sum(bit << (63 - i) for i, bit in enumerate(bits.flatten()))
                    phash = f"{hash_int:016x}"

                # Создание записи в базе данных
                TemporalImage.objects.create(
                    user=user,
                    title=f"Test Image {idx}",
                    perceptual_hash=phash,
                    image_path=saved_path,  # Сохраняем относительный путь
                    status=TemporalImage.ImageStatus.DRAFT,
                    expiration_time=timezone.now() + timezone.timedelta(days=30)
                )
                # Обновление результатов
                processing_time = time.time() - file_start_time
                results['success'] += 1
                results['hash_times'].append(processing_time)
                results['total_time'] += processing_time
                results['saved_paths'].append(saved_path)
                file_record['status'] = 'success'
                file_record['phash'] = phash

            except Exception as e:
                error_msg = str(e)
                file_record['error'] = error_msg
                results['errors'].append({
                    'file': file.name,
                    'error': error_msg,
                    'trace': traceback.format_exc()[:500]
                })

                # Удаляем файл в случае ошибки
                if 'saved_path' in locals():
                    try:
                        storage.delete(saved_path)
                    except Exception as delete_error:
                        pass
            finally:
                results['processed_files'].append(file_record)

        # Расчет статистики
        if results['success'] > 0:
            results['avg_time'] = results['total_time'] / results['success']
            results['total_time'] = round(results['total_time'], 4)
            results['avg_time'] = round(results['avg_time'], 4)
            results['min_time'] = round(min(results['hash_times']), 4)
            results['max_time'] = round(max(results['hash_times']), 4)

    return render(request, 'main/test_images.html', {'results': results})


@login_required
def archive_image(request):
    user_id = request.session.get('user_id')
    user = CustomUser.objects.get(id=user_id)

    archived_images = TemporalImage.objects.filter(
        user=user,
        status=TemporalImage.ImageStatus.ARCHIVED
    ).order_by('-upload_time')

    if request.method == 'POST':
        image_id = request.POST.get('image_id')
        action = request.POST.get('action')

        try:
            image = TemporalImage.objects.get(id=image_id, user=user)

            if action == 'restore':
                try:
                    expiration_days = int(request.POST.get('expiration_days', 30))
                    if not (1 <= expiration_days <= 365):
                        raise ValueError
                except ValueError:
                    expiration_days = 30

                image.status = TemporalImage.ImageStatus.DRAFT
                image.expiration_time = timezone.now() + timezone.timedelta(days=expiration_days)
                image.save()
                messages.success(
                    request,
                    f"Изображение восстановлено в черновики на {expiration_days} дней"
                )

            elif action == 'delete':
                image.delete()
                messages.success(request, "Изображение удалено из архива")

        except TemporalImage.DoesNotExist:
            messages.error(request, "Изображение не найдено")

        return redirect('archive_image')

    return render(request, 'main/archive_image.html', {
        'archived_images': archived_images,
        'media_prefix': '/media/images/'
    })

def about(request):
    return render(request, 'main/about.html')