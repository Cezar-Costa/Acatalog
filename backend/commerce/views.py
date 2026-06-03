from django.contrib.auth import get_user_model
from django.conf import settings
from django.core.files.base import ContentFile
from django.db import models, transaction
from django.db.models import Count, Sum
from django.db.models.functions import TruncDate
from django.shortcuts import get_object_or_404, redirect, render
from rest_framework import mixins, status, viewsets
from rest_framework.decorators import action, api_view, permission_classes
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework_simplejwt.exceptions import TokenError
from rest_framework_simplejwt.tokens import RefreshToken

from .filters import ProductFilter
from .models import (
    Address, Brand, Cart, CartItem, Category, Coupon, Inventory, Order,
    Product, ProductImage, Promotion, Review, Wishlist,
)
from .permissions import IsAdminRole
from .serializers import (
    AddressSerializer, AdminProductSerializer, BrandSerializer, CartItemSerializer,
    CartSerializer, CategorySerializer, CheckoutSerializer, CouponSerializer,
    GoogleLoginSerializer, LoginSerializer, OrderSerializer, ProductDetailSerializer,
    ProductImageImportByUrlSerializer, ProductImageSerializer, ProductListSerializer, PromotionSerializer,
    RegisterSerializer, ReviewSerializer, UserSerializer, WishlistSerializer,
)
from ipaddress import ip_address
from pathlib import Path
from urllib.parse import urlparse
import socket
import uuid
import urllib.request as urlrequest

User = get_user_model()


@api_view(['GET'])
@permission_classes([AllowAny])
def health(request):
    return Response({'status': 'ok'})


def format_brl(value):
    amount = float(value or 0)
    formatted = f'{amount:,.2f}'.replace(',', 'X').replace('.', ',').replace('X', '.')
    return f'R$ {formatted}'


def dashboard_admin_user(request):
    token = request.COOKIES.get('refresh_token')
    if not token:
        return None
    try:
        refresh = RefreshToken(token)
        user_id = refresh.get('user_id')
    except TokenError:
        return None
    if not user_id:
        return None
    user = User.objects.filter(id=user_id).first()
    if not user or not user.is_active or not user.is_admin_role:
        return None
    return user


def admin_dashboard(request):
    admin_user = dashboard_admin_user(request)
    if not admin_user:
        return redirect('/admin/login?next=/dashboard/')

    orders = Order.objects.select_related('user').all()
    paid_orders = orders.exclude(status=Order.Status.CANCELED)
    total_sales = paid_orders.aggregate(total=Sum('total'))['total'] or 0
    total_orders = paid_orders.count()
    average_ticket = total_sales / total_orders if total_orders else 0
    low_stock_count = Inventory.objects.filter(quantity__lte=models.F('low_stock_threshold')).count()

    sales_chart = list(
        paid_orders.annotate(day=TruncDate('created_at'))
        .values('day')
        .annotate(sales=Sum('total'), orders=Count('id'))
        .order_by('day')
    )[-7:]
    chart_max = max((float(item['sales'] or 0) for item in sales_chart), default=1)
    for item in sales_chart:
        value = float(item['sales'] or 0)
        item['label'] = item.pop('day').strftime('%d/%m')
        item['sales_display'] = format_brl(value)
        item['height'] = max(round((value / chart_max) * 180), 12) if chart_max else 12

    recent_orders = []
    for order in orders.order_by('-created_at')[:6]:
        recent_orders.append({
            'id': order.id,
            'status': order.get_status_display(),
            'total': format_brl(order.total),
            'customer': order.user.get_full_name() or order.user.username or order.user.email,
            'date': order.created_at.strftime('%d/%m/%Y'),
        })

    best_sellers = []
    products = Product.objects.select_related('brand', 'category', 'inventory').order_by('-sold_count')[:6]
    for index, product in enumerate(products, start=1):
        best_sellers.append({
            'position': index,
            'name': product.name,
            'brand': product.brand.name,
            'category': product.category.name,
            'price': format_brl(product.current_price),
            'sold_count': product.sold_count,
            'stock': product.inventory.available if hasattr(product, 'inventory') else 0,
        })

    low_stock_products = []
    low_stock_qs = Inventory.objects.select_related('product', 'product__brand').filter(
        quantity__lte=models.F('low_stock_threshold')
    )[:5]
    for item in low_stock_qs:
        low_stock_products.append({
            'name': item.product.name,
            'brand': item.product.brand.name,
            'available': item.available,
            'threshold': item.low_stock_threshold,
        })

    status_summary = list(
        orders.values('status')
        .annotate(total=Count('id'))
        .order_by('status')
    )
    status_labels = dict(Order.Status.choices)
    for item in status_summary:
        item['label'] = status_labels.get(item['status'], item['status'])

    context = {
        'metrics': [
            {'label': 'Faturamento total', 'value': format_brl(total_sales), 'note': 'Pedidos nao cancelados'},
            {'label': 'Pedidos', 'value': total_orders, 'note': 'Historico operacional'},
            {'label': 'Ticket medio', 'value': format_brl(average_ticket), 'note': 'Media por pedido pago'},
            {'label': 'Alerta de estoque', 'value': low_stock_count, 'note': 'Produtos no limite'},
        ],
        'sales_chart': sales_chart,
        'recent_orders': recent_orders,
        'best_sellers': best_sellers,
        'low_stock_products': low_stock_products,
        'status_summary': status_summary,
        'totals': {
            'products': Product.objects.count(),
            'categories': Category.objects.count(),
            'customers': User.objects.filter(role=User.Role.CUSTOMER).count(),
            'promotions': Promotion.objects.filter(is_active=True).count(),
        },
        'admin_user': admin_user,
    }
    return render(request, 'commerce/python_dashboard.html', context)


def python_dashboard(request):
    return redirect('/dashboard/')


def token_response(user, response_status=status.HTTP_200_OK):
    refresh = RefreshToken.for_user(user)
    response = Response(
        {
            'access': str(refresh.access_token),
            'user': UserSerializer(user).data,
        },
        status=response_status,
    )
    response.set_cookie(
        'refresh_token',
        str(refresh),
        httponly=True,
        secure=settings.REFRESH_COOKIE_SECURE,
        samesite=settings.REFRESH_COOKIE_SAMESITE,
        max_age=7 * 24 * 60 * 60,
    )
    return response


@api_view(['POST'])
@permission_classes([AllowAny])
def register(request):
    serializer = RegisterSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    user = serializer.save()
    return token_response(user, status.HTTP_201_CREATED)


@api_view(['POST'])
@permission_classes([AllowAny])
def customer_login(request):
    serializer = LoginSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    user = serializer.validated_data['user']
    if user.is_admin_role:
        return Response({'detail': 'Use o login administrativo.'}, status=status.HTTP_403_FORBIDDEN)
    Cart.objects.get_or_create(user=user)
    return token_response(user)


@api_view(['POST'])
@permission_classes([AllowAny])
def admin_login(request):
    serializer = LoginSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    user = serializer.validated_data['user']
    if not user.is_admin_role:
        return Response({'detail': 'Acesso administrativo negado.'}, status=status.HTTP_403_FORBIDDEN)
    return token_response(user)


@api_view(['POST'])
@permission_classes([AllowAny])
def google_login(request):
    serializer = GoogleLoginSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    return token_response(serializer.validated_data['user'])


@api_view(['POST'])
@permission_classes([AllowAny])
def refresh_access(request):
    token = request.COOKIES.get('refresh_token')
    if not token:
        return Response({'detail': 'Refresh token ausente.'}, status=status.HTTP_401_UNAUTHORIZED)
    try:
        refresh = RefreshToken(token)
    except TokenError:
        return Response({'detail': 'Refresh token invalido.'}, status=status.HTTP_401_UNAUTHORIZED)
    return Response({'access': str(refresh.access_token)})


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def logout(request):
    response = Response({'detail': 'Logout realizado.'})
    response.delete_cookie('refresh_token')
    return response


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def me(request):
    return Response(UserSerializer(request.user).data)


class CategoryViewSet(viewsets.ModelViewSet):
    queryset = Category.objects.all()
    serializer_class = CategorySerializer

    def get_permissions(self):
        if self.action in ['list', 'retrieve', 'home']:
            return [AllowAny()]
        return [IsAdminRole()]


class BrandViewSet(viewsets.ModelViewSet):
    queryset = Brand.objects.all()
    serializer_class = BrandSerializer

    def get_permissions(self):
        if self.action in ['list', 'retrieve', 'home']:
            return [AllowAny()]
        return [IsAdminRole()]


class ProductViewSet(viewsets.ModelViewSet):
    queryset = Product.objects.select_related('category', 'brand', 'inventory').prefetch_related('images')
    filterset_class = ProductFilter
    search_fields = ['name', 'brand__name', 'sku', 'description', 'specifications']
    ordering_fields = ['price', 'created_at', 'sold_count', 'average_rating']
    lookup_field = 'slug'

    def get_queryset(self):
        qs = super().get_queryset()
        if not (self.request.user.is_authenticated and self.request.user.is_admin_role):
            qs = qs.filter(is_active=True)
        return qs

    def get_serializer_class(self):
        if self.request.user.is_authenticated and self.request.user.is_admin_role and self.action != 'retrieve':
            return AdminProductSerializer
        if self.action == 'retrieve':
            return ProductDetailSerializer
        return ProductListSerializer

    def get_permissions(self):
        if self.action in ['list', 'retrieve', 'home']:
            return [AllowAny()]
        return [IsAdminRole()]

    @action(detail=False, methods=['get'], permission_classes=[AllowAny])
    def home(self, request):
        qs = self.get_queryset()
        data = {
            'featured': ProductListSerializer(qs.filter(is_featured=True)[:8], many=True, context={'request': request}).data,
            'promotions': ProductListSerializer(qs.filter(promotional_price__isnull=False)[:8], many=True, context={'request': request}).data,
            'new': ProductListSerializer(qs.filter(is_new=True)[:8], many=True, context={'request': request}).data,
            'best_sellers': ProductListSerializer(qs.order_by('-sold_count')[:8], many=True, context={'request': request}).data,
        }
        return Response(data)


class ProductImageViewSet(viewsets.ModelViewSet):
    queryset = ProductImage.objects.select_related('product')
    serializer_class = ProductImageSerializer
    permission_classes = [IsAdminRole]

    @staticmethod
    def _host_is_private(hostname):
        if not hostname:
            return True
        if hostname in {'localhost'}:
            return True
        try:
            infos = socket.getaddrinfo(hostname, None)
        except socket.gaierror:
            return True
        for info in infos:
            address = info[4][0]
            ip = ip_address(address)
            if (
                ip.is_private
                or ip.is_loopback
                or ip.is_link_local
                or ip.is_multicast
                or ip.is_reserved
                or ip.is_unspecified
            ):
                return True
        return False

    @action(detail=False, methods=['post'], url_path='import-by-url')
    def import_by_url(self, request):
        serializer = ProductImageImportByUrlSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        validated = serializer.validated_data

        product = validated['product']
        urls = validated['urls']
        alt_text = validated.get('alt_text', '')
        set_first_as_primary = validated.get('set_first_as_primary', False)

        max_images = 6
        max_bytes = 5 * 1024 * 1024
        allowed_types = {'image/jpeg': '.jpg', 'image/png': '.png', 'image/webp': '.webp'}
        timeout = 10
        current_count = product.images.count()
        available_slots = max(max_images - current_count, 0)
        start_sort = validated.get('start_sort_order')
        if start_sort is None:
            last = product.images.order_by('-sort_order').first()
            start_sort = (last.sort_order + 1) if last else 0

        created = []
        errors = []
        first_primary_set = False

        if available_slots == 0:
            return Response(
                {'created': [], 'errors': [{'url': '', 'reason': f'Limite de {max_images} imagens ja atingido para este produto.'}]},
                status=status.HTTP_400_BAD_REQUEST,
            )

        for index, raw_url in enumerate(urls):
            url = raw_url.strip()
            if not url:
                errors.append({'url': raw_url, 'reason': 'URL vazia.'})
                continue
            if len(created) >= available_slots:
                errors.append({'url': url, 'reason': f'Limite de {max_images} imagens por produto atingido.'})
                continue

            parsed = urlparse(url)
            if parsed.scheme not in {'http', 'https'}:
                errors.append({'url': url, 'reason': 'URL deve usar http ou https.'})
                continue
            if self._host_is_private(parsed.hostname):
                errors.append({'url': url, 'reason': 'Origem bloqueada por politica de seguranca.'})
                continue

            try:
                req = urlrequest.Request(url, headers={'User-Agent': 'AcatalogBot/1.0'})
                with urlrequest.urlopen(req, timeout=timeout) as response:
                    content_type_header = (response.headers.get('Content-Type') or '').split(';')[0].strip().lower()
                    if content_type_header not in allowed_types:
                        errors.append({'url': url, 'reason': 'Tipo de arquivo nao suportado (use JPG, PNG ou WEBP).'})
                        continue
                    content_length = response.headers.get('Content-Length')
                    if content_length and int(content_length) > max_bytes:
                        errors.append({'url': url, 'reason': 'Imagem excede 5MB.'})
                        continue

                    chunks = []
                    total = 0
                    while True:
                        chunk = response.read(64 * 1024)
                        if not chunk:
                            break
                        total += len(chunk)
                        if total > max_bytes:
                            chunks = []
                            break
                        chunks.append(chunk)

                    if not chunks:
                        errors.append({'url': url, 'reason': 'Imagem excede 5MB.'})
                        continue

                    image_bytes = b''.join(chunks)
                    ext = allowed_types[content_type_header]
                    parsed_ext = Path(parsed.path).suffix.lower()
                    filename_ext = parsed_ext if parsed_ext in {'.jpg', '.jpeg', '.png', '.webp'} else ext
                    filename = f'product-import-{uuid.uuid4().hex}{filename_ext}'

                    is_primary = bool(set_first_as_primary and not first_primary_set)
                    if is_primary:
                        product.images.filter(is_primary=True).update(is_primary=False)
                        first_primary_set = True

                    image_obj = ProductImage(
                        product=product,
                        alt_text=alt_text or product.name,
                        is_primary=is_primary,
                        sort_order=start_sort + index,
                    )
                    image_obj.image.save(filename, ContentFile(image_bytes), save=True)
                    created.append(image_obj)
            except Exception:
                errors.append({'url': url, 'reason': 'Falha ao baixar imagem desse link.'})

        return Response(
            {
                'created': ProductImageSerializer(created, many=True, context={'request': request}).data,
                'errors': errors,
            },
            status=status.HTTP_200_OK,
        )


class AddressViewSet(viewsets.ModelViewSet):
    serializer_class = AddressSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return Address.objects.filter(user=self.request.user)

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)


class CartViewSet(viewsets.GenericViewSet):
    permission_classes = [IsAuthenticated]

    def get_cart(self):
        cart, _ = Cart.objects.get_or_create(user=self.request.user)
        return cart

    @action(detail=False, methods=['get'])
    def current(self, request):
        return Response(CartSerializer(self.get_cart(), context={'request': request}).data)

    @action(detail=False, methods=['post'])
    @transaction.atomic
    def add(self, request):
        cart = self.get_cart()
        serializer = CartItemSerializer(data=request.data, context={'request': request})
        serializer.is_valid(raise_exception=True)
        product = serializer.validated_data['product']
        quantity = serializer.validated_data.get('quantity', 1)
        inventory = Inventory.objects.select_for_update().filter(product=product).first()
        current_quantity = CartItem.objects.filter(cart=cart, product=product).first()
        requested_total = quantity + (current_quantity.quantity if current_quantity else 0)
        if not inventory or inventory.available < requested_total:
            return Response({'detail': 'Estoque insuficiente.'}, status=status.HTTP_400_BAD_REQUEST)
        item, created = CartItem.objects.get_or_create(cart=cart, product=product, defaults={'quantity': quantity})
        if not created:
            item.quantity += quantity
            item.save(update_fields=['quantity'])
        return Response(CartSerializer(cart, context={'request': request}).data)

    @action(detail=False, methods=['patch', 'delete'], url_path='items/(?P<item_id>[^/.]+)')
    @transaction.atomic
    def item(self, request, item_id=None):
        cart = self.get_cart()
        item = get_object_or_404(CartItem, id=item_id, cart=cart)
        if request.method == 'DELETE':
            item.delete()
            return Response(CartSerializer(cart, context={'request': request}).data)
        try:
            quantity = max(int(request.data.get('quantity', 1)), 1)
        except (TypeError, ValueError):
            return Response({'detail': 'Quantidade invalida.'}, status=status.HTTP_400_BAD_REQUEST)
        inventory = Inventory.objects.select_for_update().filter(product=item.product).first()
        if not inventory or inventory.available < quantity:
            return Response({'detail': 'Estoque insuficiente.'}, status=status.HTTP_400_BAD_REQUEST)
        item.quantity = quantity
        item.save(update_fields=['quantity'])
        return Response(CartSerializer(item.cart, context={'request': request}).data)

    @action(detail=False, methods=['post'])
    def coupon(self, request):
        cart = self.get_cart()
        code = request.data.get('code', '').strip().upper()
        coupon = Coupon.objects.filter(code__iexact=code).first()
        if not coupon or not coupon.is_valid():
            return Response({'detail': 'Cupom invalido ou expirado.'}, status=status.HTTP_400_BAD_REQUEST)
        cart.coupon = coupon
        cart.save(update_fields=['coupon'])
        return Response(CartSerializer(cart, context={'request': request}).data)


class OrderViewSet(viewsets.ModelViewSet):
    serializer_class = OrderSerializer
    permission_classes = [IsAuthenticated]
    filterset_fields = ['status']
    ordering_fields = ['created_at', 'total']

    def get_queryset(self):
        qs = Order.objects.prefetch_related('items').select_related('user', 'address')
        if self.request.user.is_admin_role:
            return qs
        return qs.filter(user=self.request.user)

    def get_permissions(self):
        if self.action in ['update', 'partial_update', 'destroy']:
            return [IsAdminRole()]
        return [IsAuthenticated()]

    @action(detail=False, methods=['post'])
    def checkout(self, request):
        serializer = CheckoutSerializer(data=request.data, context={'request': request})
        serializer.is_valid(raise_exception=True)
        order = serializer.save()
        return Response(OrderSerializer(order, context={'request': request}).data, status=status.HTTP_201_CREATED)


class WishlistViewSet(viewsets.ModelViewSet):
    serializer_class = WishlistSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return Wishlist.objects.filter(user=self.request.user).select_related('product')

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)


class ReviewViewSet(viewsets.ModelViewSet):
    serializer_class = ReviewSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        product = self.request.query_params.get('product')
        qs = Review.objects.select_related('user', 'product')
        return qs.filter(product_id=product) if product else qs

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)


class CouponViewSet(viewsets.ModelViewSet):
    queryset = Coupon.objects.all()
    serializer_class = CouponSerializer
    permission_classes = [IsAdminRole]


class PromotionViewSet(viewsets.ModelViewSet):
    queryset = Promotion.objects.prefetch_related('products')
    serializer_class = PromotionSerializer
    permission_classes = [IsAdminRole]


class CustomerViewSet(mixins.ListModelMixin, mixins.RetrieveModelMixin, viewsets.GenericViewSet):
    queryset = User.objects.filter(role=User.Role.CUSTOMER).prefetch_related('addresses', 'orders')
    serializer_class = UserSerializer
    permission_classes = [IsAdminRole]


@api_view(['GET'])
@permission_classes([IsAdminRole])
def dashboard_metrics(request):
    orders = Order.objects.all()
    paid_orders = orders.exclude(status=Order.Status.CANCELED)
    total_sales = paid_orders.aggregate(total=Sum('total'))['total'] or 0
    total_orders = paid_orders.count()
    average_ticket = total_sales / total_orders if total_orders else 0
    low_stock = Inventory.objects.filter(quantity__lte=models.F('low_stock_threshold')).count()
    recent_orders = OrderSerializer(orders.order_by('-created_at')[:6], many=True, context={'request': request}).data
    best_sellers = ProductListSerializer(Product.objects.order_by('-sold_count')[:6], many=True, context={'request': request}).data
    sales_chart = list(
        paid_orders.annotate(day=TruncDate('created_at'))
        .values('day')
        .annotate(sales=Sum('total'), orders=models.Count('id'))
        .order_by('day')
    )
    for item in sales_chart:
        item['label'] = item.pop('day').strftime('%d/%m')
    return Response({
        'total_sales': total_sales,
        'total_orders': total_orders,
        'average_ticket': average_ticket,
        'low_stock': low_stock,
        'recent_orders': recent_orders,
        'best_sellers': best_sellers,
        'sales_chart': sales_chart,
    })
