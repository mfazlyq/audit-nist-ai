import unittest

from audit_utils import parse_nist_findings


class ParseNistFindingsTests(unittest.TestCase):
    def test_parses_valid_finding(self):
        response = (
            "GOVERN | GV.OC-01 | Asset ownership is not clearly documented | "
            "Assign accountable owners and review the inventory quarterly."
        )
        self.assertEqual(
            parse_nist_findings(response),
            [[
                "GOVERN",
                "GV.OC-01",
                "Asset ownership is not clearly documented",
                "Assign accountable owners and review the inventory quarterly.",
            ]],
        )

    def test_ignores_header_and_invalid_control_ids(self):
        response = "\n".join([
            "PILAR | ID_KONTROL | Situasi | Saran",
            "PROTECT | PR.DS-XX | Missing control suffix | This should be ignored.",
            "UNKNOWN | GV.OC-01 | Invalid pillar | This should be ignored.",
            "DETECT | NOT-A-NIST-ID | Invalid control | This should be ignored.",
        ])
        self.assertEqual(parse_nist_findings(response), [])

    def test_normalizes_case_and_whitespace(self):
        response = (
            "Fungsi protect | pr.ds - 01 | Data classification is inconsistent | "
            "Define and communicate a consistent classification policy."
        )
        self.assertEqual(parse_nist_findings(response)[0][:2], ["PROTECT", "PR.DS-01"])

    def test_stops_at_requested_limit(self):
        rows = [
            f"RECOVER | RC.RP-{index:02d} | Situation {index} | Recommendation {index}"
            for index in range(1, 5)
        ]
        self.assertEqual(len(parse_nist_findings("\n".join(rows), limit=2)), 2)

    def test_rejects_non_string_input(self):
        with self.assertRaises(TypeError):
            parse_nist_findings(None)


if __name__ == "__main__":
    unittest.main()
