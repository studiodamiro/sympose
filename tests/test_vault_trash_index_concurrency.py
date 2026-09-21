"""Concurrency regression test for vault_trash_index.py — record_clash's
load-mutate-save cycle must be atomic, or two clashes recorded at the same
time can lose one entry (see CODE_QUALITY_STANDARDS.md §7)."""

import os
import threading

from sympose.vault_trash_index import load_index, record_clash


def test_concurrent_record_clash_calls_dont_lose_entries(tmp_path):
    troot = str(tmp_path)
    os.makedirs(troot, exist_ok=True)
    n = 20
    barrier = threading.Barrier(n)

    def record(i: int) -> None:
        barrier.wait()  # maximize actual overlap between threads
        record_clash(troot, f"trash-{i}.md", f"original-{i}.md")

    threads = [threading.Thread(target=record, args=(i,)) for i in range(n)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    index = load_index(troot)
    assert len(index) == n
    for i in range(n):
        assert index[f"trash-{i}.md"] == f"original-{i}.md"
