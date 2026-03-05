"""기존 세트메뉴 OrderItem에 자식 OrderItem(구성품) 추가 스크립트"""
import os, sys, django

current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.join(current_dir, "../..")
sys.path.insert(0, project_root)
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'project.settings')
django.setup()

from order.models import OrderItem
from menu.models import SetMenuItem

# 세트메뉴인데 자식이 없는 OrderItem 조회
parent_items = (
    OrderItem.objects
    .filter(setmenu__isnull=False, parent__isnull=True)
    .exclude(children__isnull=False)
    .select_related("setmenu", "order")
)

created = 0
for parent in parent_items:
    components = SetMenuItem.objects.filter(
        set_menu_id=parent.setmenu_id
    ).select_related("menu")

    if not components.exists():
        print(f"⚠️  세트메뉴 구성품 없음: setmenu_id={parent.setmenu_id}")
        continue

    for comp in components:
        child = OrderItem.objects.create(
            order=parent.order,
            menu=comp.menu,
            setmenu=None,
            parent=parent,
            quantity=parent.quantity * comp.quantity,
            fixed_price=0,
            status=parent.status,  # 부모와 같은 상태로 초기화
        )
        created += 1
        print(f"  ✅ 자식 생성: parent={parent.pk} → child={child.pk} "
              f"menu={comp.menu.name} qty={child.quantity} status={child.status}")

print()
print(f"총 {created}개 자식 OrderItem 생성 완료!")
print(f"전체 OrderItem 수: {OrderItem.objects.count()}")
