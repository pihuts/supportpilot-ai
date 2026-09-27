"""Offline smoke test for an exported n8n workflow. Run: python smoke_test.py"""
import json
import subprocess
import unittest
from pathlib import Path


ROOT = Path(__file__).parent
DOC = json.loads(next(p for p in ROOT.glob("*.json") if p.name not in ("Failure Alert.json", "fixtures.json")).read_text(encoding="utf-8"))
NODES = {n["name"]: n for n in DOC["nodes"]}
FIXTURE = json.loads((ROOT / "fixtures.json").read_text(encoding="utf-8"))


def run_code(name, payload, env=None, node_data=None):
    code = NODES[name]["parameters"]["jsCode"]
    runner = r"""const vm=require('vm');
const a=JSON.parse(process.argv[1]);
const ctx={
  $input:{first:()=>({json:a.payload,binary:a.binary}),all:()=>[{json:a.payload}]},
  $:name=>({first:()=>({json:a.nodeData?.[name]||{}}),item:{json:a.nodeData?.[name]||{}},all:()=>[{json:a.nodeData?.[name]||{}}]}),
  $env:a.env||{},$json:a.payload,$execution:{id:'smoke-123'},
  console:{log:()=>{}},Date,Intl,Number,String,JSON,Array,Error,URL};
try { const out=vm.runInNewContext('(()=>{'+a.code+'})()',ctx);
  process.stdout.write(JSON.stringify({ok:true,out})); }
catch(e) { process.stdout.write(JSON.stringify({ok:false,error:e.message})); }"""
    process = subprocess.run(["node", "-e", runner, json.dumps({"code": code, "payload": payload, "env": env or {},
                                                                 "nodeData": node_data or {}, "binary": payload.get("_binary")})],
                             text=True, capture_output=True, timeout=10, check=True)
    return json.loads(process.stdout)


class WorkflowSmoke(unittest.TestCase):
    def test_graph_and_javascript(self):
        self.assertEqual(len(NODES), len(DOC["nodes"]))
        for source, ports in DOC["connections"].items():
            self.assertIn(source, NODES)
            for branches in ports.values():
                for edges in branches:
                    for edge in edges:
                        self.assertIn(edge["node"], NODES)
        for n in DOC["nodes"]:
            if n["type"].endswith(".code"):
                subprocess.run(["node", "--check", "-"], input=n["parameters"]["jsCode"], text=True,
                               capture_output=True, timeout=10, check=True)
        alert = json.loads((ROOT / "Failure Alert.json").read_text(encoding="utf-8"))
        self.assertEqual(alert["nodes"][0]["type"], "n8n-nodes-base.errorTrigger")
        subprocess.run(["node", "--check", "-"], input=alert["nodes"][1]["parameters"]["jsCode"], text=True,
                       capture_output=True, timeout=10, check=True)
        for n in DOC["nodes"]:
            if n["type"].endswith(".webhook"):
                self.assertEqual(n["parameters"].get("authentication"), "headerAuth")

    def test_preflight_modes(self):
        self.assertEqual(run_code("Preflight", {}, {})["out"][0]["json"]["status"], "disabled")
        prefix = {"ledgerlens-ai": "LEDGERLENS", "outreachengine-ai": "OUTREACH", "supportpilot-ai": "SUPPORT",
                  "actionflow-ai": "ACTIONFLOW", "careercompass-ai": "CAREER"}[ROOT.name]
        self.assertEqual(run_code("Preflight", {}, {prefix + "_ENABLED": "true"})["out"][0]["json"]["status"], "dry_run")
        self.assertIn("Missing configuration", run_code("Preflight", {}, {prefix + "_ENABLED": "true", prefix + "_DRY_RUN": "false"})["error"])
        self.assertEqual(DOC["settings"]["timezone"], "Asia/Manila")
        self.assertGreater(DOC["settings"]["executionTimeout"], 0)

    def test_input_edges(self):
        if "Validate Input" not in NODES:
            return
        self.assertTrue(run_code("Validate Input", FIXTURE["empty"])["out"][0]["json"]["invalid"])
        if ROOT.name == "supportpilot-ai":
            valid = FIXTURE["valid"]
            self.assertEqual(run_code("Validate Input", valid)["out"][0]["json"]["ticketId"], "TKT-ticket_123")
            columns = NODES["Log Ticket to Google Sheets"]["parameters"]["columns"]["value"]
            self.assertIn("Escalation pending", columns["Status"])
            self.assertEqual(columns["Escalated"], "={{ false }}")
            sent = NODES["Mark escalation sent"]["parameters"]["columns"]["value"]
            self.assertEqual(sent["Status"], "=Escalated")
            self.assertEqual(sent["Escalated"], "={{ true }}")
            self.assertEqual(DOC["connections"]["Audit notify support team"]["main"][0][0]["node"], "Restore ticket after email")
            self.assertEqual(DOC["connections"]["Restore ticket after email"]["main"][0][0]["node"], "Mark escalation sent")
        else:
            valid = FIXTURE["valid"]
            self.assertEqual(run_code("Validate Input", valid)["out"][0]["json"]["meetingId"], "MTG-meeting_123")

    def test_replay_and_network_failure(self):
        existing = [n for n in DOC["nodes"] if n["name"].startswith("Find existing ")]
        for lookup in existing:
            self.assertTrue(lookup.get("alwaysOutputData"))
            key = lookup["parameters"]["filtersUI"]["values"][0]["lookupColumn"]
            check = NODES["New " + lookup["parameters"]["sheetName"]["value"].lower() + "?"]
            self.assertIn("!$json['" + key + "']", check["parameters"]["conditions"]["conditions"][0]["leftValue"])
        if ROOT.name == "outreachengine-ai":
            private = run_code("Prepare Lead", FIXTURE["private_lead"])
            self.assertTrue(private["out"]["json"]["skip"])
            down = run_code("Clean Site Text", FIXTURE["network_down"], node_data={"Prepare Lead": FIXTURE["valid"]})
            self.assertFalse(down["out"]["json"]["siteUsable"])
        if ROOT.name == "careercompass-ai":
            cleaned = run_code("Clean Job Text", FIXTURE["valid"])
            self.assertIn("Manila", cleaned["out"][0]["json"]["cleaned_text"])

    def test_network_and_write_guards(self):
        for n in DOC["nodes"]:
            if n["type"].endswith(".httpRequest"):
                self.assertGreater(n["parameters"]["options"]["timeout"], 0)
                self.assertTrue(n["retryOnFail"])
            if n["type"].endswith(".googleSheets") and n["parameters"].get("operation") == "appendOrUpdate":
                self.assertTrue(n["parameters"]["columns"]["matchingColumns"])


if __name__ == "__main__":
    unittest.main()
