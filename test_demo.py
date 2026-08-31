import unittest

from demo import build_customer360, normalize_order_id


class Customer360DemoTests(unittest.TestCase):
    def test_rejects_ambiguous_order_id(self):
        with self.assertRaises(ValueError):
            normalize_order_id("ORDER-1")

    def test_exact_order_evidence_links_and_aggregates(self):
        payload = {
            "taobao_orders": [
                {"main_order_id": "1001", "taobao_nickname": "tb_a", "paid_at": "2026-01-01", "amount_cents": 1000, "sku_ids": ["SKU-A"]},
                {"main_order_id": "1002", "taobao_nickname": "tb_a", "paid_at": "2026-02-01", "amount_cents": 2000, "sku_ids": ["SKU-A", "SKU-B"]},
            ],
            "crm_orders": [
                {"main_order_id": "1001", "wechat_id": "wx_a", "wechat_nickname": "微信A", "group_nickname": "群A"}
            ],
        }
        result = build_customer360(payload)
        profile = result["profiles"][0]
        self.assertEqual(profile["identity_status"], "linked")
        self.assertEqual(profile["total_spend_cents"], 3000)
        self.assertEqual(profile["purchase_count"], 2)
        self.assertEqual(profile["favorite_skus"], ["SKU-A", "SKU-B"])

    def test_conflicting_identity_is_isolated(self):
        payload = {
            "taobao_orders": [{"main_order_id": "2001", "taobao_nickname": "tb_b", "paid_at": "2026-01-01", "amount_cents": 1000, "sku_ids": []}],
            "crm_orders": [
                {"main_order_id": "2001", "wechat_id": "wx_1"},
                {"main_order_id": "2001", "wechat_id": "wx_2"},
            ],
        }
        result = build_customer360(payload)
        self.assertEqual(result["profiles"][0]["identity_status"], "conflict")
        self.assertEqual(result["profiles"][0]["wechat_ids"], [])
        self.assertEqual(len(result["conflicts"]), 1)


if __name__ == "__main__":
    unittest.main()
