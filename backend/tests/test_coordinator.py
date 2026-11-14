
import unittest

from coordinator import (
    get_route_for_request,
    coordinator_node,
    route_coordinator,
)


class TestCoordinator(unittest.TestCase):

    def test_ocr_analysis_route(self):
        self.assertEqual(
            get_route_for_request("ocr_analysis"),
            "nutritional"
        )

    def test_comparison_route(self):
        self.assertEqual(
            get_route_for_request("comparison"),
            "comparison"
        )

    def test_qa_route(self):
        self.assertEqual(
            get_route_for_request("qa"),
            "nutritional"
        )

    def test_invalid_request_type(self):
        self.assertIsNone(
            get_route_for_request("invalid_type")
        )

    def test_route_coordinator_comparison(self):
        state = {"request_type": "comparison"}

        self.assertEqual(
            route_coordinator(state),
            "comparison"
        )

    def test_route_coordinator_invalid(self):
        state = {"request_type": "invalid_type"}

        self.assertEqual(
            route_coordinator(state),
            "invalid"
        )

    def test_invalid_request_generates_error(self):
        state = {
            "request_type": "invalid_type",
            "warnings": [],
            "verification_errors": [],
        }

        result = coordinator_node(state)

        self.assertEqual(result["classification_tone"], "ERRO")
        self.assertFalse(result["verification_passed"])
        self.assertTrue(result["warnings"])
        self.assertTrue(result["verification_errors"])


if __name__ == "__main__":
    unittest.main()
