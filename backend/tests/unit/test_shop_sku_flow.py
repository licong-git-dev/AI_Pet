import json

import pytest
from fastapi import HTTPException

from app.api.shop import _merge_order_items, _resolve_product_sku, _update_product_sku_stock
from app.models.shop import Product


@pytest.fixture
def sku_product() -> Product:
    product = Product()
    product.id = 1
    product.price = 100
    product.stock = 10
    product.skus = json.dumps([
        {"id": 11, "price": 88, "stock": 3, "specs": {"颜色": "红", "尺寸": "M"}},
        {"id": 12, "price": 92, "stock": 5, "specs": {"颜色": "蓝", "尺寸": "L"}},
    ], ensure_ascii=False)
    return product


class Item:
    def __init__(self, product_id: int, quantity: int, sku_id: int | None, sku_info: str | None = None):
        self.product_id = product_id
        self.quantity = quantity
        self.sku_id = sku_id
        self.sku_info = sku_info


def test_resolve_product_sku_requires_sku_id_for_sku_products(sku_product: Product):
    with pytest.raises(HTTPException) as exc:
        _resolve_product_sku(sku_product, None)

    assert exc.value.status_code == 400
    assert '必须选择规格' in exc.value.detail


def test_resolve_product_sku_returns_variant_price_and_stock(sku_product: Product):
    result = _resolve_product_sku(sku_product, 11)

    assert result['sku_id'] == 11
    assert result['price'] == 88.0
    assert result['stock'] == 3
    assert '颜色:红' in result['sku_info']


def test_merge_order_items_merges_same_product_and_sku():
    merged = _merge_order_items([
        Item(1, 1, 11, '颜色:红 / 尺寸:M'),
        Item(1, 2, 11, '颜色:红 / 尺寸:M'),
        Item(1, 1, 12, '颜色:蓝 / 尺寸:L'),
    ])

    assert len(merged) == 2
    assert merged[0]['quantity'] == 3
    assert merged[0]['sku_id'] == 11
    assert merged[1]['quantity'] == 1
    assert merged[1]['sku_id'] == 12


def test_update_product_sku_stock_updates_product_and_variant_stock(sku_product: Product):
    _update_product_sku_stock(sku_product, 11, -2)

    updated_skus = json.loads(sku_product.skus)
    red_sku = next(sku for sku in updated_skus if sku['id'] == 11)

    assert sku_product.stock == 8
    assert red_sku['stock'] == 1


def test_update_product_sku_stock_restores_variant_stock_on_cancel(sku_product: Product):
    _update_product_sku_stock(sku_product, 11, -2)
    _update_product_sku_stock(sku_product, 11, 2)

    updated_skus = json.loads(sku_product.skus)
    red_sku = next(sku for sku in updated_skus if sku['id'] == 11)

    assert sku_product.stock == 10
    assert red_sku['stock'] == 3
