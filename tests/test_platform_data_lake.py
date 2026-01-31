from src.platform.data_lake import DataLake


def test_data_lake_register(tmp_path):
    data_path = tmp_path / "sample.txt"
    data_path.write_text("ok", encoding="utf-8")

    lake = DataLake(base_dir=str(tmp_path / "lake"))
    entry = lake.register(kind="dataset", name="sample", path=str(data_path))

    assert lake.get(entry.entry_id) is not None
    entries = lake.list(kind="dataset")
    assert len(entries) == 1
    assert entries[0].path == str(data_path)
