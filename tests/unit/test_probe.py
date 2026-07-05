from clipforge.probe import build_probe_argv, probe_device_compute, select_encoder


def test_nvenc_advertised_but_fails_lands_on_qsv():
    # Mirrors THIS box: nvenc/amf advertised but fail; only qsv/libx264 encode.
    def probe(enc):
        return enc in {"h264_qsv", "libx264"}

    got = select_encoder(["h264_nvenc", "h264_videotoolbox", "h264_qsv", "h264_amf"], probe)
    assert got == "h264_qsv"


def test_all_hardware_fail_falls_back_to_libx264():
    def probe(enc):
        return enc == "libx264"

    got = select_encoder(["h264_nvenc", "h264_videotoolbox", "h264_qsv", "h264_amf", "libx264"], probe)
    assert got == "libx264"


def test_first_success_wins_order():
    calls = []

    def probe(enc):
        calls.append(enc)
        return True  # first candidate succeeds

    got = select_encoder(["h264_nvenc", "h264_qsv"], probe)
    assert got == "h264_nvenc"
    assert calls == ["h264_nvenc"]  # stops at first success


def test_nothing_matches_defaults_libx264():
    got = select_encoder(["h264_qsv"], lambda e: False)
    assert got == "libx264"


def test_probe_argv_mirrors_real_graph():
    argv = build_probe_argv("h264_qsv", 1080, 1920)
    assert "-c:v" in argv and "h264_qsv" in argv
    # must scale + convert to nv12 so a passing probe implies a passing encode
    assert "scale=1080:1920,format=nv12" in " ".join(argv)
    assert argv[-2:] == ["null", "-"]


def test_device_probe_explicit_cpu():
    assert probe_device_compute("cpu", "auto") == ("cpu", "int8")


def test_device_probe_explicit_cuda_auto_compute():
    assert probe_device_compute("cuda", "auto") == ("cuda", "float16")


def test_device_probe_explicit_overrides():
    assert probe_device_compute("cpu", "float32") == ("cpu", "float32")


def test_device_probe_auto_falls_back_cpu(monkeypatch):
    # Simulate ctranslate2 reporting no CUDA device.
    import clipforge.probe as probe_mod

    class FakeCT2:
        @staticmethod
        def get_cuda_device_count():
            return 0

    monkeypatch.setitem(__import__("sys").modules, "ctranslate2", FakeCT2)
    assert probe_device_compute("auto", "auto") == ("cpu", "int8")
