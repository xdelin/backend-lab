"""同一组用例同时驱动两版 LRU 实现，保证行为等价。"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from lru import LRUCacheLinked, LRUCacheOrdered


def _drive(cls):
    c = cls(2)
    assert c.get("a") == -1, "空缓存 get 应返回 -1"

    c.put("a", 1)
    c.put("b", 2)
    assert c.get("a") == 1, "命中 a"
    c.put("c", 3)  # 容量满，淘汰最旧的 b（a 刚被访问过）
    assert c.get("b") == -1, "b 应已被淘汰"
    assert c.get("a") == 1 and c.get("c") == 3

    c.put("a", 9)  # 已存在 key 更新值，不新增条目
    assert c.get("a") == 9

    c.put("d", 4)  # 淘汰 c
    assert c.get("c") == -1 and c.get("a") == 9 and c.get("d") == 4


def test_ordered_version():
    _drive(LRUCacheOrdered)


def test_linked_version():
    _drive(LRUCacheLinked)


def test_capacity_one():
    for cls in (LRUCacheOrdered, LRUCacheLinked):
        c = cls(1)
        c.put("x", 1)
        assert c.get("x") == 1
        c.put("y", 2)
        assert c.get("x") == -1 and c.get("y") == 2, "容量 1 应淘汰旧 key"


def test_access_refreshes_recency():
    for cls in (LRUCacheOrdered, LRUCacheLinked):
        c = cls(3)
        for k in "abc":
            c.put(k, k)
        c.get("a")  # a 变为最新
        c.get("b")
        c.put("d", "d")  # 淘汰最旧的 c
        assert c.get("c") == -1
        assert c.get("a") == "a" and c.get("b") == "b" and c.get("d") == "d"


def test_invalid_capacity():
    for cls in (LRUCacheOrdered, LRUCacheLinked):
        try:
            cls(0)
        except ValueError:
            pass
        else:
            raise AssertionError("capacity=0 应拒绝")
