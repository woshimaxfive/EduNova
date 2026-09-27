import hashlib
import json

from scripts.assemble_desktop_payload import relocate_long_notices


def test_long_notices_keep_bytes_and_provenance(tmp_path):
    relative = "runtime/python/Lib/site-packages/example.dist-info/licenses/" + "nested/" * 20 + "LICENSE"
    source = tmp_path / relative
    source.parent.mkdir(parents=True)
    source.write_text("原样保留的许可证\n", encoding="utf-8")
    raw = source.read_bytes()
    short = tmp_path / "runtime/python/Lib/site-packages/example.dist-info/licenses/LICENSE"
    short.write_text("short notice", encoding="utf-8")
    result = relocate_long_notices(tmp_path)
    assert len(result) == 1
    assert result[0]["originalPath"] == relative
    assert result[0]["sha256"] == hashlib.sha256(raw).hexdigest()
    assert (tmp_path / result[0]["installedPath"]).read_bytes() == raw
    assert not source.exists()
    assert short.is_file()
    assert len(result[0]["installedPath"]) < 100
    assert relocate_long_notices(tmp_path) == result
    assert json.loads((tmp_path / "notices/relocated-license-paths.json").read_text(encoding="utf-8")) == result
