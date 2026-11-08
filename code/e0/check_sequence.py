#!/usr/bin/env python3
"""Run on qs-dut as root; compare full BPF predictions packet by packet.

No attachment or wire traffic. Uses system libbpf BPF_PROG_TEST_RUN with repeat=1,
one CPU, fresh maps for each variant, and PCAP-relative timestamps supplied through
a test-only map in place of bpf_ktime_get_ns(). Never use this for performance.
usage: sudo python3 check_sequence.py SOURCE VARIANTS TRACE.pcap OUTPUT_DIR
"""
import argparse
import ctypes as ct
from contextlib import closing
import hashlib
import json
import os
from pathlib import Path
import runpy

from bcc import BPF
from scapy.utils import RawPcapReader


class TestRun(ct.Structure):
    _fields_ = [("sz", ct.c_size_t), ("data_in", ct.c_void_p),
                ("data_out", ct.c_void_p), ("data_size_in", ct.c_uint32),
                ("data_size_out", ct.c_uint32), ("ctx_in", ct.c_void_p),
                ("ctx_out", ct.c_void_p), ("ctx_size_in", ct.c_uint32),
                ("ctx_size_out", ct.c_uint32), ("retval", ct.c_uint32),
                ("repeat", ct.c_int), ("duration", ct.c_uint32),
                ("flags", ct.c_uint32), ("cpu", ct.c_uint32),
                ("batch_size", ct.c_uint32)]


def replace_once(text, old, new):
    assert text.count(old) == 1, (old, text.count(old))
    return text.replace(old, new)


def load_model(path, model, count, variant):
    ns = runpy.run_path(str(path))
    text = ns["bpf_text"]
    audit = """
struct audit_input_t { u64 timestamp; u32 ordinal; };
struct audit_output_t { u32 prediction; u32 hits; };
BPF_ARRAY(audit_input, struct audit_input_t, 1);
BPF_ARRAY(audit_output, struct audit_output_t, AUDIT_COUNT);
static __always_inline u64 audit_time(void) {
  int zero = 0;
  struct audit_input_t *p = audit_input.lookup(&zero);
  return p ? p->timestamp : 0;
}
static __always_inline void audit_record(u32 prediction) {
  int zero = 0;
  struct audit_input_t *p = audit_input.lookup(&zero);
  if (!p) return;
  u32 ordinal = p->ordinal;
  struct audit_output_t *o = audit_output.lookup(&ordinal);
  if (o) { o->prediction = prediction; o->hits++; }
}
""".replace("AUDIT_COUNT", str(count))
    text = replace_once(text, "BPF_HASH(dropcnt, int, u32);", audit + "BPF_HASH(dropcnt, int, u32);")
    text = replace_once(text, "ts = bpf_ktime_get_ns();", "ts = audit_time();")
    if model == "nn":
        # Instrument faithful code directly; all variants receive the same hook.
        final = 'XDP_PASS' if variant in ('faithful', 'hist') else 'FINAL_ACTION'
        text = replace_once(text, '  // return XDP_DROP;\n  return ' +
                            final +
                            ';\n}\nint nn_xdp_drop_packet',
                            '  audit_record(argmax_over_cols);\n  return ' +
                            final +
                            ';\n}\nint nn_xdp_drop_packet')
        params = json.loads((path.parent / "mlp_params.json").read_text())
        for key in ("layer_1_s_w_inv", "layer_2_s_w_inv", "layer_3_s_w_inv",
                    "layer_1_weight", "layer_2_weight", "layer_3_weight", "data_min", "data_scale"):
            text = text.replace(key.upper(), str(len(params[key])))
    else:
        text = replace_once(text, "          bool is_anomaly = (bool)(*current_value);",
                            "          audit_record((u32)*current_value);\n"
                            "          bool is_anomaly = (bool)(*current_value);")
        params = {key: json.loads((path.parent / "runs" / key).read_text())
                  for key in ("childrenLeft", "childrenRight", "feature", "threshold", "value")}
        for key, token in (("childrenLeft", "CHILDREN_LEFT"), ("childrenRight", "CHILDREN_RIGHT"),
                           ("feature", "FEATURE"), ("threshold", "THRESHOLD"), ("value", "VALUE")):
            text = text.replace(f"DT_{token}_SIZE", str(len(params[key])))
        text = text.replace("DT_MAX_TREE_DEPTH", "20")
    b = BPF(text=text, cflags=["-w", "-DFINAL_ACTION=" +
                              ("XDP_DROP" if variant in ("clean_drop", "abl_w", "abl_io", "abl_w_io") else "XDP_PASS")])
    # Populate parameters before any packet can execute.
    for key, values in params.items():
        if model == "nn":
            ns["map_bpf_table"](b[key], values, 'int64_t' if key.startswith('data_') else 'int')
        else:
            ns["map_bpf_table"](b[key], values)
    if variant in ("abl_w", "abl_w_io"):
        for n in (1, 2, 3):
            table = b[f"layer_{n}_wv"]
            value = table.Leaf()
            for i, weight in enumerate(params[f"layer_{n}_weight"]):
                assert -128 <= weight <= 127
                value.w[i] = weight & 255
            table[ct.c_int(0)] = value
    entry = b.load_func(f"{model}_xdp_drop_packet", BPF.XDP)
    if model == "nn":
        # Keep handles alive along with the owning BPF instance.
        for i, name in enumerate(("nn1", "nn2")):
            b["jmp_table"][ct.c_int(i)] = ct.c_int(b.load_func(name, BPF.XDP).fd)
    return b, entry


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for arg in ("source", "variants", "trace", "output"):
        parser.add_argument(arg, type=Path)
    args = parser.parse_args()
    os.sched_setaffinity(0, {min(os.sched_getaffinity(0))})
    packets = []
    with closing(RawPcapReader(str(args.trace))) as reader:
        assert reader.linktype == 1, "Ethernet PCAP required"
        factor = 1 if reader.nano else 1000
        for raw, meta in reader:
            packets.append((raw, meta.sec * 10**9 + meta.usec * factor))
    assert packets
    base_time = packets[0][1]
    times = [ts - base_time + 10**9 for _, ts in packets]
    assert all(a <= b for a, b in zip(times, times[1:])), "PCAP timestamps must be monotonic"
    lib = ct.CDLL("libbpf.so.1", use_errno=True)
    lib.bpf_prog_test_run_opts.argtypes = [ct.c_int, ct.POINTER(TestRun)]
    lib.bpf_prog_test_run_opts.restype = ct.c_int
    args.output.mkdir(parents=True, exist_ok=True)
    summary = {"trace_sha256": hashlib.sha256(args.trace.read_bytes()).hexdigest(),
               "packets": len(packets), "clock": "PCAP-relative nanoseconds + 1 second",
               "cpu": min(os.sched_getaffinity(0)), "runs": []}
    for model in ("dt", "nn"):
        variants = ["faithful", "hist", "clean_pass", "clean_drop"]
        if model == "nn":
            variants += ["abl_w", "abl_io", "abl_w_io"]
        reference = None
        for variant in variants:
            root = args.source if variant == "faithful" else args.variants / variant
            path = root / f"{model}-filter" / f"{model}_filter_xdp.py"
            b, entry = load_model(path, model, len(packets), variant)
            actions = {}
            for ordinal, ((raw, _), timestamp) in enumerate(zip(packets, times)):
                control = b["audit_input"].Leaf()
                control.timestamp, control.ordinal = timestamp, ordinal
                b["audit_input"][ct.c_int(0)] = control
                buf = ct.create_string_buffer(raw)
                opts = TestRun(sz=ct.sizeof(TestRun), data_in=ct.addressof(buf),
                               data_size_in=len(raw), repeat=1)
                rc = lib.bpf_prog_test_run_opts(entry.fd, ct.byref(opts))
                if rc:
                    raise OSError(ct.get_errno(), f"test_run rc={rc} packet={ordinal}")
                actions[str(opts.retval)] = actions.get(str(opts.retval), 0) + 1
            results = [b["audit_output"][ct.c_int(i)] for i in range(len(packets))]
            predictions = [v.prediction for v in results]
            missing = sum(v.hits == 0 for v in results)
            duplicate = sum(v.hits > 1 for v in results)
            if reference is None:
                reference = predictions
            mismatches = [i for i, (a, c) in enumerate(zip(reference, predictions)) if a != c]
            csv = "ordinal,class,hits\n" + "".join(
                f"{i},{v.prediction},{v.hits}\n" for i, v in enumerate(results))
            (args.output / f"{model}_{variant}.csv").write_text(csv)
            row = {"model": model, "variant": variant, "missing": missing,
                   "duplicate": duplicate, "mismatches": len(mismatches),
                   "first_mismatches": mismatches[:20], "actions": actions,
                   "class_counts": {str(c): predictions.count(c) for c in sorted(set(predictions))},
                   "prediction_sha256": hashlib.sha256(bytes(predictions)).hexdigest()}
            summary["runs"].append(row)
            print(json.dumps(row), flush=True)
            b.cleanup()
    (args.output / "summary.json").write_text(json.dumps(summary, indent=2) + "\n")
    assert all(not (r["missing"] or r["duplicate"] or r["mismatches"]) for r in summary["runs"])


if __name__ == "__main__":
    main()
