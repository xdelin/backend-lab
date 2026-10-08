"""LRU 缓存的两版实现。

面试常见两问：
1. 「写一个 LRU」——先用版本 A（OrderedDict），说明 move_to_end / popitem(last=False)
   与淘汰语义的对应关系；
2. 「不许用内置结构」——写版本 B（HashMap + 双向链表），要点是：
   - HashMap 负责 O(1) 定位节点，双向链表负责 O(1) 摘除与头插；
     单向链表摘除需要找前驱（O(n)），所以必须双向；
   - 头尾哨兵节点消掉「链表空 / 只有一个节点」的边界分支。

两版 API 完全一致，test_lru.py 用同一组用例同时驱动两个实现，保证行为等价。
"""

from __future__ import annotations

from collections import OrderedDict
from typing import Any


class LRUCacheOrdered:
    """版本 A：OrderedDict 实现（迭代顺序即访问顺序，最新端在尾部）。"""

    def __init__(self, capacity: int) -> None:
        if capacity <= 0:
            raise ValueError("capacity must be positive")
        self.capacity = capacity
        self._od: OrderedDict[Any, Any] = OrderedDict()

    def get(self, key: Any) -> Any:
        if key not in self._od:
            return -1
        self._od.move_to_end(key)  # 命中 → 移到最新端
        return self._od[key]

    def put(self, key: Any, value: Any) -> None:
        if key in self._od:
            self._od.move_to_end(key)
        self._od[key] = value
        if len(self._od) > self.capacity:
            self._od.popitem(last=False)  # 淘汰最旧端


class _Node:
    __slots__ = ("key", "value", "prev", "next")

    def __init__(self, key: Any = None, value: Any = None) -> None:
        self.key = key
        self.value = value
        self.prev: _Node | None = None
        self.next: _Node | None = None


class LRUCacheLinked:
    """版本 B：HashMap + 双向链表（带头尾哨兵，摘除/头插均 O(1)）。"""

    def __init__(self, capacity: int) -> None:
        if capacity <= 0:
            raise ValueError("capacity must be positive")
        self.capacity = capacity
        self._map: dict[Any, _Node] = {}
        self._head: _Node = _Node()  # 哨兵：head.next 是最新端
        self._tail: _Node = _Node()  # 哨兵：tail.prev 是最旧端
        self._head.next = self._tail
        self._tail.prev = self._head

    def _unlink(self, node: _Node) -> None:
        node.prev.next = node.next
        node.next.prev = node.prev

    def _push_front(self, node: _Node) -> None:
        first = self._head.next
        node.prev, node.next = self._head, first
        self._head.next = node
        first.prev = node

    def get(self, key: Any) -> Any:
        node = self._map.get(key)
        if node is None:
            return -1
        self._unlink(node)
        self._push_front(node)  # 命中提到最新端
        return node.value

    def put(self, key: Any, value: Any) -> None:
        node = self._map.get(key)
        if node is not None:
            node.value = value
            self._unlink(node)
            self._push_front(node)
            return
        if len(self._map) >= self.capacity:
            lru = self._tail.prev
            self._unlink(lru)
            del self._map[lru.key]  # type: ignore[arg-type]
        node = _Node(key, value)
        self._map[key] = node
        self._push_front(node)
