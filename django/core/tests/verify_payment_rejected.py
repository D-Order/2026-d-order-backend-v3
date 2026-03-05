"""결제거절 테스트 결과 검증 스크립트"""
import django, os, sys

current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.join(current_dir, "..")
sys.path.append(project_root)
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'project.settings')
django.setup()

from cart.models import Cart
from order.models import Order

cart = Cart.objects.get(pk=1)
print(f"Cart id=1 상태: {cart.status}")
print(f"Cart.Status.ACTIVE = {Cart.Status.ACTIVE}")
print(f"일치 여부: {cart.status == Cart.Status.ACTIVE}")

order_exists = Order.objects.filter(cart_id=1).exists()
print(f"Order 생성 여부: {order_exists}")

print()
if cart.status == Cart.Status.ACTIVE and not order_exists:
    print("✅ 결제거절 테스트 성공!")
    print("   - Cart.status: pending_payment → active 복구 완료")
    print("   - Order: 생성되지 않음 (정상)")
else:
    print("❌ 테스트 실패!")
    if cart.status != Cart.Status.ACTIVE:
        print(f"   Cart.status가 active가 아님: {cart.status}")
    if order_exists:
        print("   Order가 생성되었음 (비정상)")
