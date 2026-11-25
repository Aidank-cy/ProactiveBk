"""Deterministic reconstruction of the original mock mall's coupon arithmetic."""
from itertools import product

SKU_GROUPS = {
    "A": (("bsk_strr_a1", 13300), ("bsk_strr_a2", 9400), ("bsk_strr_a3", 8300)),
    "B": (("bsk_strr_b1", 16200), ("bsk_strr_b2", 11300)),
    "C": (("bsk_strr_c1", 8000), ("bsk_strr_c2", 5000), ("bsk_strr_c3", 4300)),
}
COUPONS = (("FULL209_strr", 21900, 3000), ("FULL249_strr", 25400, 5500))


def enumerate_carts():
    """Each discount uses the original subtotal; percentage floors to cents."""
    plans = []
    for selected in product(*SKU_GROUPS.values()):
        subtotal = sum(price for _, price in selected)
        used = [name for name, threshold, _ in COUPONS if subtotal >= threshold]
        flat = sum(amount for _, threshold, amount in COUPONS if subtotal >= threshold)
        percent = subtotal // 10 if subtotal >= 10000 else 0
        if percent:
            used.append("PCT10_strr")
        plans.append({"sku_ids": [sku for sku, _ in selected], "subtotal_minor": subtotal,
                      "coupon_codes": used, "discount_minor": flat + percent,
                      "total_minor": max(0, subtotal - flat - percent)})
    return sorted(plans, key=lambda p: (p["total_minor"], p["sku_ids"]))


def audit():
    plans = enumerate_carts()
    assert len(plans) == 18
    return {"rule": "All coupon thresholds and percentage discount use the original subtotal; discounts add; percentage floors to cents; total floors at zero.",
            "source": "VibeLifeBench/servers/ecommerce_mock/src/ecommerce_mock/services/coupon_service.py and cart_service.py",
            "combination_count": len(plans), "best": plans[0], "all_combinations": plans}
