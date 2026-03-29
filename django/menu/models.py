from django.db import models
from django.core.validators import MinValueValidator
from booth.models import Booth


class Menu(models.Model):
    """단일 메뉴"""
    
    class Category(models.TextChoices):
        MENU = 'MENU', '메뉴'
        DRINK = 'DRINK', '음료'
        FEE = 'FEE', '이용료'
    
    booth = models.ForeignKey(
        Booth,
        on_delete=models.CASCADE,
        related_name='menus'
    )
    name = models.CharField(max_length=20)
    category = models.CharField(
        max_length=20,
        choices=Category.choices,
        default=Category.MENU
    )
    description = models.CharField(max_length=30, blank=True, null=True)
    price = models.DecimalField(
        max_digits=10,
        decimal_places=0,
        validators=[MinValueValidator(0)]
    )
    stock = models.IntegerField(
        default=0,
        validators=[MinValueValidator(0)]
    )
    image = models.ImageField(upload_to='menu_images/', blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'menu'
        ordering = ['category', 'name']

    def __str__(self):
        return f"[{self.booth.name}] {self.name}"


class SetMenu(models.Model):
    """세트 메뉴"""
    
    class Category(models.TextChoices):
        SET = 'SET', '세트'
    
    booth = models.ForeignKey(
        Booth,
        on_delete=models.CASCADE,
        related_name='set_menus'
    )
    name = models.CharField(max_length=20)
    category = models.CharField(
        max_length=20,
        choices=Category.choices,
        default=Category.SET
    )
    description = models.CharField(max_length=30, blank=True, null=True)
    price = models.IntegerField(validators=[MinValueValidator(0)])
    image = models.ImageField(upload_to='setmenu_images/', blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'set_menu'
        ordering = ['category', 'name']

    def __str__(self):
        return f"[{self.booth.name}] {self.name} (세트)"


class SetMenuItem(models.Model):
    """세트 메뉴 구성 항목 (SetMenu <-> Menu 연결)"""
    set_menu = models.ForeignKey(
        SetMenu,
        on_delete=models.CASCADE,
        related_name='items'
    )
    menu = models.ForeignKey(
        Menu,
        on_delete=models.CASCADE,
        related_name='set_menu_items'
    )
    quantity = models.IntegerField(default=1)

    class Meta:
        db_table = 'set_menu_item'
        unique_together = ['set_menu', 'menu']

    def __str__(self):
        return f"{self.set_menu.name} - {self.menu.name} x{self.quantity}"
