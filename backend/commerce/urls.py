from django.urls import include, path
from rest_framework.routers import DefaultRouter

from . import views

router = DefaultRouter()
router.register('categories', views.CategoryViewSet, basename='category')
router.register('brands', views.BrandViewSet, basename='brand')
router.register('products', views.ProductViewSet, basename='product')
router.register('product-images', views.ProductImageViewSet, basename='product-image')
router.register('addresses', views.AddressViewSet, basename='address')
router.register('cart', views.CartViewSet, basename='cart')
router.register('orders', views.OrderViewSet, basename='order')
router.register('wishlist', views.WishlistViewSet, basename='wishlist')
router.register('reviews', views.ReviewViewSet, basename='review')
router.register('coupons', views.CouponViewSet, basename='coupon')
router.register('promotions', views.PromotionViewSet, basename='promotion')
router.register('customers', views.CustomerViewSet, basename='customer')

urlpatterns = [
    path('health/', views.health),
    path('', include(router.urls)),
    path('auth/register/', views.register),
    path('auth/login/', views.customer_login),
    path('auth/admin-login/', views.admin_login),
    path('auth/google/', views.google_login),
    path('auth/refresh/', views.refresh_access),
    path('auth/logout/', views.logout),
    path('auth/me/', views.me),
    path('dashboard/metrics/', views.dashboard_metrics),
]
