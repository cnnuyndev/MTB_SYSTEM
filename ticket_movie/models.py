from django.db import models
from django.contrib.auth.models import AbstractUser, BaseUserManager
from django.utils.translation import gettext_lazy as _
from django.core.exceptions import ValidationError
from django.contrib.auth.password_validation import validate_password
from django.core.validators import MinValueValidator


class UserManager(BaseUserManager):
    def create_user(self, email, password=None, **extra_fields):
        """
        Tạo regular user với email và password
        """
        if not email:
            raise ValueError('Email là bắt buộc cho regular user')

        email = self.normalize_email(email)
        user = self.model(email=email, **extra_fields)

        if password:
            user.set_password(password)
        user.save(using=self._db)
        return user

    def create_social_user(self, provider, social_id, email=None, **extra_fields):
        """
        Tạo social user với provider và social_id
        """
        if not provider or not social_id:
            raise ValueError(
                'Provider và Social ID là bắt buộc cho social user')

        # Tạo username duy nhất từ social info
        username = f"{provider}_{social_id}"
        email = self.normalize_email(email) if email else None

        # Kiểm tra xem username đã tồn tại chưa
        if self.model.objects.filter(username=username).exists():
            raise ValueError('Username đã tồn tại cho social user này')

        user = self.model(
            username=username,
            email=email,
            provider=provider,
            social_id=social_id,
            **extra_fields
        )
        user.set_unusable_password()  # Social user không dùng password
        user.save(using=self._db)
        return user

    def create_superuser(self, email, password, **extra_fields):
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)
        extra_fields.setdefault('role', User.Role.ADMIN)

        if extra_fields.get('is_staff') is not True:
            raise ValueError('Superuser must have is_staff=True.')
        if extra_fields.get('is_superuser') is not True:
            raise ValueError('Superuser must have is_superuser=True.')

        return self.create_user(email, password, **extra_fields)


class User(AbstractUser):
    # Điều chỉnh username field để phù hợp với cả regular và social user
    username = models.CharField(
        _('username'),
        max_length=150,
        unique=True,
        null=True,
        blank=True,
        help_text=_('Chỉ dùng cho social auth. 150 ký tự trở xuống.'),
    )

    # Email là chính (bắt buộc với regular user)
    email = models.EmailField(
        _('email address'),
        unique=True,
        null=True,  # Cho phép null cho social user
        blank=True,
        error_messages={
            'unique': _("Email đã được sử dụng."),
        }
    )

    # Cho phép password null cho social user
    password = models.CharField(
        _('password'),
        max_length=128,
        null=True,
        blank=True
    )

    # Thông tin cá nhân
    full_name = models.CharField(_('full name'), max_length=100, blank=True)
    phone = models.CharField(_('phone number'), max_length=20, blank=True)

    groups = models.ManyToManyField(
        'auth.Group',
        verbose_name=_('groups'),
        blank=True,
        help_text=_(
            'The groups this user belongs to. A user will get all permissions '
            'granted to each of their groups.'
        ),
        related_name="ticket_movie_user_groups",
        related_query_name="ticket_movie_user",
    )
    user_permissions = models.ManyToManyField(
        'auth.Permission',
        verbose_name=_('user permissions'),
        blank=True,
        help_text=_('Specific permissions for this user.'),
        related_name="ticket_movie_user_permissions",
        related_query_name="ticket_movie_user",
    )

    # Phân quyền
    class Role(models.TextChoices):
        CUSTOMER = 'customer', _('Customer')
        STAFF = 'staff', _('Staff')
        ADMIN = 'admin', _('Admin')

    role = models.CharField(
        _('role'),
        max_length=20,
        choices=Role.choices,
        default=Role.CUSTOMER
    )

    # Social auth fields
    provider = models.CharField(max_length=50, blank=True, null=True)
    social_id = models.CharField(max_length=200, blank=True, null=True)
    avatar = models.URLField(blank=True, null=True)

    # Sử dụng email làm USERNAME_FIELD
    USERNAME_FIELD = 'email'
    # Thêm các trường bắt buộc khi tạo superuser
    REQUIRED_FIELDS = ['full_name']

    objects = UserManager()

    class Meta:
        db_table = 'users'
        verbose_name = _('user')
        verbose_name_plural = _('users')

    def __str__(self):
        return self.email or f"{self.provider}:{self.social_id}"

    def clean(self):
        super().clean()
        # Kiểm tra xem user có email hoặc là social user không
        if not self.email and not (self.provider and self.social_id):
            raise ValidationError(
                'User must have either email or social credentials')

    def save(self, *args, **kwargs):
        # Validate password nếu có thay đổi và là regular user
        if not self.is_social_user and self.password and not self.check_password(self.password):
            try:
                validate_password(self.password)
            except ValidationError as e:
                raise ValidationError({'password': e.messages})

        self.clean()
        super().save(*args, **kwargs)

    @property
    def is_social_user(self):
        """Kiểm tra có phải là social user không"""
        return bool(self.provider and self.social_id)

    @property
    def is_staff_member(self):
        """Kiểm tra user có phải là staff hoặc admin không"""
        return self.role in [self.Role.STAFF, self.Role.ADMIN] or self.is_staff

    @property
    def is_admin(self):
        """Kiểm tra user có phải là admin không"""
        return self.role == self.Role.ADMIN or self.is_superuser

    def get_username(self):
        """Lấy username để hiển thị (dùng cho social user)"""
        return self.username if self.is_social_user else self.email

    @property
    def get_user_id(self):
        return self.id


class City(models.Model):
    name = models.CharField(max_length=100, null=False, blank=False)
    country = models.CharField(max_length=50, default='Vietnam')

    class Meta:
        db_table = 'cities'
        verbose_name_plural = 'cities'

    def __str__(self):
        return f"{self.name}, {self.country}"


class Cinema(models.Model):
    city = models.ForeignKey(City, on_delete=models.CASCADE, null=False)
    name = models.CharField(max_length=100, null=False, blank=False)
    address = models.TextField(null=False, blank=False)
    phone = models.CharField(max_length=20, blank=True)
    opening_hours = models.CharField(max_length=100, blank=True)

    class Meta:
        db_table = 'cinemas'
        indexes = [
            models.Index(fields=['city'], name='idx_cinema_city'),
        ]

    def __str__(self):
        return f"{self.name} ({self.city.name})"


class Movie(models.Model):
    class Status(models.TextChoices):
        COMING = 'coming', _('Coming Soon')
        SHOWING = 'showing', _('Now Showing')
        ENDED = 'ended', _('Ended')

    title = models.CharField(max_length=100, null=False, blank=False)
    description = models.TextField(blank=True)
    duration = models.IntegerField(
        null=False, validators=[MinValueValidator(1)])
    release_date = models.DateField(null=False)
    genre = models.CharField(max_length=100, blank=True)
    director = models.CharField(max_length=100, blank=True)
    movie_cast = models.TextField(blank=True)
    poster_url = models.URLField(max_length=255, blank=True)
    trailer_url = models.URLField(max_length=255, blank=True)
    rating = models.DecimalField(
        max_digits=3, decimal_places=1, null=True, blank=True)
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.COMING
    )

    class Meta:
        db_table = 'movies'
        indexes = [
            models.Index(fields=['status'], name='idx_movie_status'),
        ]

    def __str__(self):
        return self.title


class Screen(models.Model):
    class ScreenType(models.TextChoices):
        TWO_D = '2D', _('2D')
        THREE_D = '3D', _('3D')
        IMAX = 'IMAX', _('IMAX')
        FOUR_DX = '4DX', _('4DX')

    cinema = models.ForeignKey(Cinema, on_delete=models.CASCADE, null=False)
    name = models.CharField(max_length=50, null=False, blank=False)
    type = models.CharField(
        max_length=20,
        choices=ScreenType.choices,
        default=ScreenType.TWO_D
    )
    capacity = models.IntegerField(
        null=False, validators=[MinValueValidator(1)])

    class Meta:
        db_table = 'screens'
        indexes = [
            models.Index(fields=['cinema'], name='idx_screen_cinema'),
        ]

    def __str__(self):
        return f"{self.name} ({self.type}) - {self.cinema.name}"


class Seat(models.Model):
    class SeatType(models.TextChoices):
        STANDARD = 'standard', _('Standard')
        VIP = 'vip', _('VIP')
        COUPLE = 'couple', _('Couple')

    screen = models.ForeignKey(Screen, on_delete=models.CASCADE, null=False)
    row = models.CharField(max_length=1, null=False, blank=False)
    number = models.IntegerField(null=False)
    type = models.CharField(
        max_length=20,
        choices=SeatType.choices,
        default=SeatType.STANDARD
    )
    is_active = models.BooleanField(default=True)

    class Meta:
        db_table = 'seats'
        indexes = [
            models.Index(fields=['screen'], name='idx_seat_screen'),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=['screen', 'row', 'number'],
                name='unique_seat'
            )
        ]

    def __str__(self):
        return f"{self.row}{self.number} ({self.type})"


class Showtime(models.Model):
    class ShowStatus(models.TextChoices):
        SCHEDULED = 'scheduled', _('Scheduled')
        CANCELLED = 'cancelled', _('Cancelled')
        COMPLETED = 'completed', _('Completed')

    movie = models.ForeignKey(Movie, on_delete=models.CASCADE, null=False)
    screen = models.ForeignKey(Screen, on_delete=models.CASCADE, null=False)
    start_time = models.DateTimeField(null=False)
    end_time = models.DateTimeField(null=False)
    base_price = models.DecimalField(
        max_digits=10, decimal_places=2, null=False)
    available_seats = models.IntegerField(null=False)
    status = models.CharField(
        max_length=20,
        choices=ShowStatus.choices,
        default=ShowStatus.SCHEDULED
    )

    class Meta:
        db_table = 'showtimes'
        indexes = [
            models.Index(fields=['movie'], name='idx_showtime_movie'),
            models.Index(fields=['screen'], name='idx_showtime_screen'),
        ]
        constraints = [
            models.CheckConstraint(
                check=models.Q(end_time__gt=models.F('start_time')),
                name='valid_showtime'
            )
        ]

    def __str__(self):
        return f"{self.movie.title} at {self.start_time}"


class Booking(models.Model):
    class BookingStatus(models.TextChoices):
        PENDING = 'pending', _('Pending')
        CONFIRMED = 'confirmed', _('Confirmed')
        CANCELLED = 'cancelled', _('Cancelled')
        EXPIRED = 'expired', _('Expired')

    user = models.ForeignKey(User, on_delete=models.CASCADE, null=False)
    showtime = models.ForeignKey(
        Showtime, on_delete=models.CASCADE, null=False)
    booking_code = models.CharField(max_length=20, unique=True, null=False)
    total_amount = models.DecimalField(
        max_digits=10, decimal_places=2, null=False)
    booking_time = models.DateTimeField(auto_now_add=True)
    status = models.CharField(
        max_length=20,
        choices=BookingStatus.choices,
        default=BookingStatus.PENDING
    )

    class Meta:
        db_table = 'bookings'
        indexes = [
            models.Index(fields=['user'], name='idx_booking_user'),
            models.Index(fields=['showtime'], name='idx_booking_showtime'),
        ]

    def __str__(self):
        return f"Booking #{self.booking_code}"


class BookingSeat(models.Model):
    booking = models.ForeignKey(Booking, on_delete=models.CASCADE, null=False)
    seat = models.ForeignKey(Seat, on_delete=models.CASCADE, null=False)
    price = models.DecimalField(max_digits=10, decimal_places=2, null=False)

    class Meta:
        db_table = 'booking_seats'

    def __str__(self):
        return f"{self.seat} in {self.booking}"


class Payment(models.Model):
    class PaymentMethod(models.TextChoices):
        CASH = 'cash', _('Cash')
        CREDIT_CARD = 'credit_card', _('Credit Card')
        MOMO = 'momo', _('MoMo')
        ZALOPAY = 'zalopay', _('ZaloPay')
        VNPAY = 'vnpay', _('VNPay')

    class PaymentStatus(models.TextChoices):
        PENDING = 'pending', _('Pending')
        SUCCESS = 'success', _('Success')
        FAILED = 'failed', _('Failed')
        REFUNDED = 'refunded', _('Refunded')

    booking = models.ForeignKey(Booking, on_delete=models.CASCADE, null=False)
    amount = models.DecimalField(max_digits=10, decimal_places=2, null=False)
    method = models.CharField(
        max_length=20,
        choices=PaymentMethod.choices,
        null=True,
        blank=True
    )
    transaction_id = models.CharField(max_length=100, blank=True)
    status = models.CharField(
        max_length=20,
        choices=PaymentStatus.choices,
        default=PaymentStatus.PENDING
    )
    payment_time = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'payments'
        indexes = [
            models.Index(fields=['booking'], name='idx_payment_booking'),
        ]

    def __str__(self):
        return f"Payment for {self.booking}"


class Promotion(models.Model):
    class DiscountType(models.TextChoices):
        PERCENTAGE = 'percentage', _('Percentage')
        FIXED = 'fixed', _('Fixed Amount')

    code = models.CharField(max_length=20, unique=True, null=False)
    name = models.CharField(max_length=100, null=False)
    description = models.TextField(blank=True)
    discount_type = models.CharField(
        max_length=20,
        choices=DiscountType.choices,
        null=False
    )
    discount_value = models.DecimalField(
        max_digits=10, decimal_places=2, null=False)
    min_order_value = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True
    )
    start_date = models.DateTimeField(null=False)
    end_date = models.DateTimeField(null=False)
    max_uses = models.IntegerField(null=True, blank=True)
    current_uses = models.IntegerField(default=0)
    is_active = models.BooleanField(default=True)

    class Meta:
        db_table = 'promotions'

    def __str__(self):
        return f"{self.name} ({self.code})"


class AppliedPromotion(models.Model):
    booking = models.ForeignKey(Booking, on_delete=models.CASCADE, null=False)
    promotion = models.ForeignKey(
        Promotion, on_delete=models.CASCADE, null=False)
    discount_amount = models.DecimalField(
        max_digits=10, decimal_places=2, null=False)

    class Meta:
        db_table = 'applied_promotions'

    def __str__(self):
        return f"{self.promotion} applied to {self.booking}"
