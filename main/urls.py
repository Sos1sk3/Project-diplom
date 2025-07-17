from django.contrib import admin
from django.urls import path
from . import views
from .views import check_all_images, draft_images, image_search, image_work, archive_image, about
from django.conf import settings
from django.conf.urls.static import static

urlpatterns = [
    path('', views.home, name='home'),
    path('login/', views.login_view, name='login'),
    path('download_image',views.down_image,name='download_image'),
    path('all_images',check_all_images,name='all_images'),
    path('draft_images',draft_images, name='draft_images'),
    path('image_search',image_search, name='image_search'),
    path('image_work', image_work, name='image_work'),
    path('test_images',views.test_images,name='test_images'),
    path('delete/<int:image_id>/', views.delete_image, name='delete_image'),
    path('archive_image',archive_image,name='archive_image'),
    path('about',about,name='about')
] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)