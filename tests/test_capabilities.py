"""Offline regression tests for the optional integration registry."""
from __future__ import annotations

import unittest
from ppigfinder.infrastructure.capabilities import CapabilityStatus, collect_capabilities


class CapabilityRegistryTests(unittest.TestCase):
    def inspect(self, executables=(), modules=()):
        return {
            item.identifier: item
            for item in collect_capabilities(
                which=lambda cmd: f"/fake/{cmd}" if cmd in executables else None,
                module_probe=lambda module: module in modules,
            )
        }

    def test_core_and_server_export_work_offline(self):
        items = self.inspect()
        self.assertEqual(items["genome_io"].status, CapabilityStatus.AVAILABLE)
        self.assertEqual(items["afserver_export"].status, CapabilityStatus.AVAILABLE)
        self.assertIn("manual_submission", items["afserver_export"].operations)
        self.assertEqual(items["af3_input"].status, CapabilityStatus.AVAILABLE)
        self.assertEqual(items["af3_local"].status, CapabilityStatus.NOT_CONFIGURED)

    def test_detection_never_claims_validated_execution(self):
        items = self.inspect(executables=("af3", "blastp", "hmmsearch"), modules=("pyrodigal",))
        for key in ("af3_local", "blast", "hmmer", "pyrodigal"):
            self.assertEqual(items[key].status, CapabilityStatus.DETECTED)

    def test_unimplemented_remote_workflows_are_explicit(self):
        items = self.inspect(executables=("af3", "sbatch", "ssh"), modules=("paramiko",))
        self.assertEqual(items["ssh_transport"].status, CapabilityStatus.NOT_IMPLEMENTED)
        self.assertEqual(items["remote_scheduler"].status, CapabilityStatus.NOT_IMPLEMENTED)
        self.assertEqual(items["boltz2_runner"].status, CapabilityStatus.NOT_IMPLEMENTED)
        self.assertEqual(items["foldcp_runner"].status, CapabilityStatus.NOT_IMPLEMENTED)
        self.assertEqual(items["scheduler_script"].status, CapabilityStatus.NOT_CONFIGURED)

    def test_unique_identifiers_and_json_safe_values(self):
        items = collect_capabilities(which=lambda _: None, module_probe=lambda _: False)
        self.assertEqual(len(items), len({item.identifier for item in items}))
        import json
        json.dumps([item.as_dict() for item in items])


if __name__ == "__main__":
    unittest.main()
