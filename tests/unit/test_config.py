import argparse

import pytest

from clipforge.config import Config


def test_defaults():
    c = Config()
    assert c.precise_cuts is True
    assert c.download_grouping == "ranged"
    assert c.reframe_mode == "crop"
    assert c.whisper_model == "small.en"
    assert c.caption_preset == "shorts_bold"
    assert c.max_concurrency == 3
    assert c.target_width == 1080 and c.target_height == 1920


def test_encoder_order_appends_libx264_last_once():
    c = Config(encoder_candidates=["h264_nvenc", "h264_qsv"])
    order = c.encoder_order()
    assert order[-1] == "libx264"
    assert order.count("libx264") == 1


def test_encoder_order_libx264_in_candidates_not_duplicated():
    c = Config(encoder_candidates=["libx264", "h264_qsv"])
    order = c.encoder_order()
    assert order.count("libx264") == 1
    assert order[-1] == "libx264"


def test_unknown_model_rejected():
    with pytest.raises(ValueError):
        Config(whisper_model="ginormous")


def test_concurrency_must_be_positive():
    with pytest.raises(ValueError):
        Config(max_concurrency=0)


def test_from_cli_args_only_overrides_set_flags():
    ns = argparse.Namespace(
        reframe_mode="blur_pad",
        whisper_model=None,  # unset -> must NOT clobber default
        precise_cuts=None,
        unrelated_key="ignored",
    )
    c = Config.from_cli_args(ns)
    assert c.reframe_mode == "blur_pad"
    assert c.whisper_model == "small.en"  # default preserved
    assert c.precise_cuts is True


def test_from_cli_args_bool_false_honored():
    ns = argparse.Namespace(precise_cuts=False)
    c = Config.from_cli_args(ns)
    assert c.precise_cuts is False
