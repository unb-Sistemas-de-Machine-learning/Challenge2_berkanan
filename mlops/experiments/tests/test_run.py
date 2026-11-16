import csv
import json
import tempfile
import threading
import unittest
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

from benchmark import run, testset


class FakeAPI(BaseHTTPRequestHandler):
    received: list[dict] = []

    def do_POST(self):
        body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        FakeAPI.received.append(body)
        text = "Não há evidência suficiente." if body["text"].startswith("Fora") else "Resposta."
        data = json.dumps({"llm_explanation": text, "matched_sources": [{"source": "guia.pdf"}]}).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(data)

    def log_message(self, *args):
        pass


class TestRun(unittest.TestCase):
    def setUp(self):
        self.server = HTTPServer(("127.0.0.1", 0), FakeAPI)
        threading.Thread(target=self.server.serve_forever, daemon=True).start()
        self.tmp = Path(tempfile.mkdtemp())
        header = ",".join(f'"{c}"' for c in testset.COLUMNS)
        (self.tmp / "t.csv").write_text(
            header + "\nA1,Guia,Pergunta?,R,Guia,,Acerto,Não\n"
            "D1,Comparação,Compare?,R,IN 75,,Acerto,Não\n"
            "G1,Fora,Fora do escopo?,,,Recusar,Recusa,Não\n",
            encoding="utf-8",
        )
        FakeAPI.received = []

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()

    def test_run_writes_outputs(self):
        args = run.parse_args([
            "--testset", str(self.tmp / "t.csv"), "--configs", "A", "B", "--reps", "2",
            "--api", f"http://127.0.0.1:{self.server.server_port}", "--out", str(self.tmp / "out"),
            "--experiment-id", "x",
        ])
        out = run.run(args)

        self.assertEqual(len(FakeAPI.received), 2 * 2 * 3)
        self.assertEqual(FakeAPI.received[0]["enable_verifier"], False)
        self.assertEqual({r["request_type"] for r in FakeAPI.received}, {"qa", "comparison"})

        with (out / "correcao.csv").open(encoding="utf-8-sig") as f:
            rows = list(csv.DictReader(f))
        self.assertEqual(len(rows), 12)
        g = [r for r in rows if r["question_id"] == "G1"]
        self.assertTrue(all(r["refused"] == "1" for r in g))
        self.assertTrue(all(r["correct"] == "" for r in rows))

        meta = json.loads((out / "run.json").read_text(encoding="utf-8"))
        self.assertEqual(meta["n_errors"], 0)
        self.assertIn("official", meta)
        self.assertEqual(len((out / "respostas.jsonl").read_text(encoding="utf-8").splitlines()), 12)

    def test_unreachable_api_is_recorded_as_error(self):
        args = run.parse_args([
            "--testset", str(self.tmp / "t.csv"), "--configs", "A", "--reps", "1",
            "--api", "http://127.0.0.1:1", "--out", str(self.tmp / "out"), "--experiment-id", "y",
            "--timeout", "2",
        ])
        out = run.run(args)
        meta = json.loads((out / "run.json").read_text(encoding="utf-8"))
        self.assertEqual(meta["n_errors"], 3)


if __name__ == "__main__":
    unittest.main()
