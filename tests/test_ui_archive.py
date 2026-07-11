from zipfile import ZipFile

import apps.problem_bridge_wizard as ui


def test_download_archive_is_refreshed_and_does_not_include_itself(tmp_path):
    out = tmp_path / "run"
    out.mkdir()
    (out / "first.txt").write_text("first", encoding="utf-8")

    archive = ui._make_archive(out)
    (out / "second.txt").write_text("second", encoding="utf-8")
    refreshed = ui._make_archive(out)

    assert archive == refreshed
    assert archive.parent == out.parent
    with ZipFile(refreshed) as package:
        names = package.namelist()
    assert names == ["first.txt", "second.txt"]
    assert all(not name.endswith(".zip") for name in names)
