"""Read physical Arrow schemas from already-extracted bounded samples; no network or data download."""

import argparse
import collections
import hashlib
import json
from pathlib import Path
import sys

p = argparse.ArgumentParser()
p.add_argument("audit", type=Path)
a = p.parse_args()
sys.path.insert(0, str(a.audit / "python"))
import pyarrow
import pyarrow.parquet as pq

results = []
for path in sorted((a.audit / "hf").rglob("*.parquet")):
    item = dict(path=str(path.relative_to(a.audit)), bytes=path.stat().st_size)
    try:
        receipt = json.loads((path.parent / "archive-members.json").read_text())
        members = [row for row in receipt["members"] if Path(row["name"]).name == path.name]
        assert len(members) == 1 and members[0]["size"] == path.stat().st_size
        item.update(archive=receipt["archive"], member=members[0]["name"])
        parquet = pq.ParquetFile(path)
        schema = parquet.schema_arrow
        metadata = schema.metadata or {}
        hf = json.loads(metadata.get(b"huggingface", b"{}"))
        declared = hf.get("info", {}).get("features")
        item.update(
            status="readable",
            sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
            rows=parquet.metadata.num_rows,
            row_groups=parquet.metadata.num_row_groups,
            columns=schema.names,
            types={field.name: str(field.type) for field in schema},
            matches_hf_declared_columns=set(declared) == set(schema.names) if declared else None,
        )
    except Exception as error:
        item.update(status="unreadable", error=repr(error))
    results.append(item)
report = dict(
    scope="Physical Parquet/Arrow schemas from bounded archive samples already present on this server; not every published archive or episode.",
    pyarrow_version=pyarrow.__version__,
    status_counts=dict(collections.Counter(row["status"] for row in results)),
    column_sets=[
        list(names)
        for names in sorted({tuple(r["columns"]) for r in results if r["status"] == "readable"})
    ],
    files=results,
)
(a.audit / "hf/physical-parquet-schemas.json").write_text(json.dumps(report, indent=2))
print(json.dumps({key: value for key, value in report.items() if key != "files"}, indent=2))
