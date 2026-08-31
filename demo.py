from __future__ import annotations

import json
import sys
from collections import Counter, defaultdict
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any


def normalize_order_id(value: Any) -> str:
    text = str(value).strip()
    if not text or not text.isdigit():
        raise ValueError(f"invalid order id: {value!r}")
    return text


class DisjointSet:
    def __init__(self) -> None:
        self.parent: dict[str, str] = {}

    def find(self, item: str) -> str:
        self.parent.setdefault(item, item)
        if self.parent[item] != item:
            self.parent[item] = self.find(self.parent[item])
        return self.parent[item]

    def union(self, left: str, right: str) -> None:
        left_root, right_root = self.find(left), self.find(right)
        if left_root != right_root:
            self.parent[max(left_root, right_root)] = min(left_root, right_root)


@dataclass(frozen=True)
class CustomerProfile:
    customer_id: str
    taobao_nicknames: list[str]
    wechat_ids: list[str]
    wechat_nicknames: list[str]
    group_nicknames: list[str]
    total_spend_cents: int
    average_order_value_cents: int
    purchase_count: int
    last_order_at: str
    favorite_skus: list[str]
    identity_status: str


def build_customer360(payload: dict[str, Any]) -> dict[str, Any]:
    taobao_orders = payload.get("taobao_orders", [])
    crm_orders = payload.get("crm_orders", [])
    crm_by_order: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in crm_orders:
        crm_by_order[normalize_order_id(row["main_order_id"])].append(row)

    dsu = DisjointSet()
    conflicts: list[dict[str, Any]] = []
    conflicted_tb: set[str] = set()

    for order in taobao_orders:
        order_id = normalize_order_id(order["main_order_id"])
        tb_node = f"tb:{order['taobao_nickname']}"
        dsu.find(tb_node)
        candidates = {str(row["wechat_id"]) for row in crm_by_order.get(order_id, [])}
        if len(candidates) == 1:
            dsu.union(tb_node, f"wx:{next(iter(candidates))}")
        elif len(candidates) > 1:
            conflicted_tb.add(tb_node)
            conflicts.append({"main_order_id": order_id, "candidate_wechat_ids": sorted(candidates)})

    orders_by_root: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for order in taobao_orders:
        tb_node = f"tb:{order['taobao_nickname']}"
        orders_by_root[dsu.find(tb_node)].append(order)

    identities_by_root: dict[str, dict[str, set[str]]] = defaultdict(lambda: defaultdict(set))
    for node in list(dsu.parent):
        root = dsu.find(node)
        kind, value = node.split(":", 1)
        identities_by_root[root][kind].add(value)

    crm_by_wechat: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in crm_orders:
        crm_by_wechat[str(row["wechat_id"])].append(row)

    profiles: list[CustomerProfile] = []
    for index, root in enumerate(sorted(orders_by_root), start=1):
        orders = orders_by_root[root]
        tb_names = sorted(identities_by_root[root].get("tb", set()))
        wx_ids = sorted(identities_by_root[root].get("wx", set()))
        related_crm = [row for wx_id in wx_ids for row in crm_by_wechat.get(wx_id, [])]
        amounts = [int(order["amount_cents"]) for order in orders]
        sku_counts = Counter(sku for order in orders for sku in order.get("sku_ids", []))
        favorite_skus = [sku for sku, _ in sorted(sku_counts.items(), key=lambda item: (-item[1], item[0]))[:3]]
        has_conflict = any(f"tb:{name}" in conflicted_tb for name in tb_names)
        status = "conflict" if has_conflict else ("linked" if wx_ids else "taobao_only")
        profiles.append(
            CustomerProfile(
                customer_id=f"CUST-DEMO-{index:03d}",
                taobao_nicknames=tb_names,
                wechat_ids=wx_ids,
                wechat_nicknames=sorted({str(row.get("wechat_nickname", "")) for row in related_crm if row.get("wechat_nickname")}),
                group_nicknames=sorted({str(row.get("group_nickname", "")) for row in related_crm if row.get("group_nickname")}),
                total_spend_cents=sum(amounts),
                average_order_value_cents=round(sum(amounts) / len(amounts)),
                purchase_count=len(orders),
                last_order_at=max(str(order["paid_at"]) for order in orders),
                favorite_skus=favorite_skus,
                identity_status=status,
            )
        )

    return {"profiles": [asdict(profile) for profile in profiles], "conflicts": conflicts}


def main() -> None:
    source = Path(sys.argv[1] if len(sys.argv) > 1 else "sample_data.json")
    print(json.dumps(build_customer360(json.loads(source.read_text(encoding="utf-8"))), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
