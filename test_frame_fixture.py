"""Contract-inspired negative cases against a deliberately fictional fixture."""

import json
import unittest

from frame_fixture import MAX_FIXTURE_PAYLOAD, Rejected, decode_fixture


def wrap(payload):
    return len(payload).to_bytes(4, "big") + payload


def example(**changes):
    value = {"version": 1, "kind": "event", "run": "run-a", "role": "node",
             "sequence": 1, "request": "request-a", "payload": {"n": 1}}
    value.update(changes)
    return wrap(json.dumps(value, ensure_ascii=False, separators=(",", ":")).encode("utf-8"))


class FrameFixtureTests(unittest.TestCase):
    def test_valid_fixture_and_non_ascii_payload(self):
        data = decode_fixture(example(payload={"message": "合成"}))
        self.assertEqual(data["payload"], {"message": "合成"})

    def test_every_prefix_truncation_rejected(self):
        frame = example()
        for size in range(len(frame)):
            with self.subTest(size=size), self.assertRaises(Rejected):
                decode_fixture(frame[:size])

    def test_zero_and_oversize_lengths_rejected_before_parsing(self):
        for size in (0, MAX_FIXTURE_PAYLOAD + 1, 2**32 - 1):
            with self.subTest(size=size), self.assertRaises(Rejected):
                decode_fixture(size.to_bytes(4, "big"))

    def test_trailing_bytes_and_two_frames_rejected(self):
        frame = example()
        for trailing in (b" ", b"\x00", frame):
            with self.subTest(trailing=trailing[:4]), self.assertRaises(Rejected):
                decode_fixture(frame + trailing)

    def test_duplicate_top_level_key_even_equal(self):
        body = b'{"version":1,"version":1,"kind":"event","run":"r","role":"x","sequence":1,"request":"q","payload":{}}'
        with self.assertRaises(Rejected):
            decode_fixture(wrap(body))

    def test_duplicate_key_nested_in_object_inside_array(self):
        body = b'{"version":1,"kind":"event","run":"r","role":"x","sequence":1,"request":"q","payload":{"a":[{"x":1,"x":2}]}}'
        with self.assertRaises(Rejected):
            decode_fixture(wrap(body))

    def test_escaped_duplicate_key_is_rejected(self):
        body = b'{"version":1,"kind":"event","run":"r","role":"x","sequence":1,"request":"q","payload":{"a":1,"\\u0061":2}}'
        with self.assertRaises(Rejected):
            decode_fixture(wrap(body))

    def test_invalid_utf8_and_json_rejected(self):
        for body in (b'\xff', b'{} trailing', b'{', b'\xef\xbb\xbf{}'):
            with self.subTest(body=body), self.assertRaises(Rejected):
                decode_fixture(wrap(body))

    def test_nonfinite_constants_rejected_even_nested(self):
        for constant in (b'NaN', b'Infinity', b'-Infinity'):
            body = b'{"version":1,"kind":"event","run":"r","role":"x","sequence":1,"request":"q","payload":{"v":' + constant + b'}}'
            with self.subTest(constant=constant), self.assertRaises(Rejected):
                decode_fixture(wrap(body))

    def test_float_overflow_rejected_and_finite_fraction_accepted(self):
        self.assertEqual(decode_fixture(example(payload={"v": 1.25}))["payload"]["v"], 1.25)
        for value in (b'1e999', b'-1e999'):
            body = b'{"version":1,"kind":"event","run":"r","role":"x","sequence":1,"request":"q","payload":{"v":' + value + b'}}'
            with self.subTest(value=value), self.assertRaises(Rejected):
                decode_fixture(wrap(body))

    def test_lone_surrogates_rejected_in_keys_and_values(self):
        for payload in (b'{"\\ud800":1}', b'{"x":"\\udfff"}'):
            body = b'{"version":1,"kind":"event","run":"r","role":"x","sequence":1,"request":"q","payload":' + payload + b'}'
            with self.subTest(payload=payload), self.assertRaises(Rejected):
                decode_fixture(wrap(body))

    def test_missing_and_unknown_fields(self):
        base = {"version": 1, "kind": "event", "run": "r", "role": "x", "sequence": 1, "request": "q", "payload": {}}
        for name in base:
            value = dict(base)
            del value[name]
            with self.subTest(missing=name), self.assertRaises(Rejected):
                decode_fixture(wrap(json.dumps(value).encode()))
        with self.assertRaises(Rejected):
            decode_fixture(example(extra=True))

    def test_invalid_version_sequence_types_and_ranges(self):
        for changes in ({"version": True}, {"version": 2}, {"sequence": True},
                        {"sequence": 0}, {"sequence": 4097}, {"sequence": 1.0}):
            with self.subTest(changes=changes), self.assertRaises(Rejected):
                decode_fixture(example(**changes))

    def test_invalid_identifiers_kind_and_payload(self):
        for changes in ({"kind": "other"}, {"run": ""}, {"role": "a b"},
                        {"request": "a" * 65}, {"run": "中文"}, {"payload": []}):
            with self.subTest(changes=changes), self.assertRaises(Rejected):
                decode_fixture(example(**changes))

    def test_incorrect_input_types(self):
        for value in (None, "abcd", bytearray(example())):
            with self.subTest(value=type(value)), self.assertRaises(Rejected):
                decode_fixture(value)

    def test_length_limit_boundary(self):
        raw = example(payload={"x": ""})[4:]
        exact = example(payload={"x": "a" * (MAX_FIXTURE_PAYLOAD - len(raw))})
        self.assertEqual(len(exact) - 4, MAX_FIXTURE_PAYLOAD)
        self.assertEqual(len(decode_fixture(exact)["payload"]["x"]), MAX_FIXTURE_PAYLOAD - len(raw))
        with self.assertRaises(Rejected):
            decode_fixture(example(payload={"x": "a" * (MAX_FIXTURE_PAYLOAD - len(raw) + 1)}))


if __name__ == "__main__":
    unittest.main()
