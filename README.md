# Synthetic framing fixture

This repository contains a small, self-contained Python fixture for testing a
fictional length-prefixed JSON frame. Its format and limits are test assumptions,
not a production protocol.

The tests use Python's standard library. With Python 3.12, run:

```text
python -S -B -m unittest -v test_frame_fixture
```

These tests operate on complete in-memory buffers. Passing them does not prove
sender identity, authorization, persistence, operating-system IPC, or the
safety of any application that uses a real protocol.
