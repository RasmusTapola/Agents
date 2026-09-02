import unittest

from workflow_core.adapters import SimulatedERPAdapter
from workflow_core.contracts import work_order_from_result


class WorkflowContractTests(unittest.TestCase):
    def test_work_order_preserves_crm_ids(self):
        order = work_order_from_result({
            "email_id": "mail-1",
            "work_order": {"organization_name": "Example Oy", "customer_id": "acct-1", "site_id": "site-1"},
        })
        self.assertEqual(order.customer_id, "acct-1")
        self.assertEqual(order.site_id, "site-1")
        self.assertEqual(order.workflow_id, "email:mail-1")

    def test_simulated_adapter_is_idempotency_lookup_boundary(self):
        records = [{"external_id": "email:mail-1", "work_order_id": "SIM-1"}]
        adapter = SimulatedERPAdapter(lambda payload: payload, records)
        self.assertEqual(adapter.health_check()["status"], "ok")
        self.assertEqual(adapter.find_by_external_id("email:mail-1")["work_order_id"], "SIM-1")
        self.assertIsNone(adapter.find_by_external_id("email:missing"))


if __name__ == "__main__":
    unittest.main()
