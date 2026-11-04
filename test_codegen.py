#!/usr/bin/env python3

import pytest
import random
from ledivilkutin_gravity_codegen import (
    Coordinate,
    Config,
    LedState,
    SetLed,
    PatternGrid,
    parse_config_row,
    parse_led_row,
    parse_input,
    extract_coordinate_buckets,
    sort_coordinates,
)


def test_set_led_yx_order():
    """Check that generated code now follows the yx notation"""
    assert SetLed(Coordinate(x=5, y=0)).to_dsl() == "s05"


def test_parse_config_row_defaults():
    config = parse_config_row("00")
    assert config.top_left == Coordinate(0, 0)
    assert config.animation_pattern == "RANDOM"
    assert config.direction == "DOWN"
    assert config.seed == "NEW"


def test_parse_config_row_options():
    config = parse_config_row("1f LTR UP SEED:42")
    assert config.top_left == Coordinate(15, 1)
    assert config.animation_pattern == "LTR"
    assert config.direction == "UP"
    assert config.seed == 42


def test_parse_config_row_invalid_coord_length():
    with pytest.raises(ValueError, match="two characters"):
        parse_config_row("1")


def test_parse_config_row_invalid_hex():
    with pytest.raises(ValueError, match="valid hex-characters"):
        parse_config_row("gh")


def test_parse_config_row_invalid_seed():
    with pytest.raises(ValueError, match="Expected 'NEW' or integer"):
        parse_config_row("00 SEED:hello")


def test_parse_config_row_unknown_option():
    with pytest.raises(ValueError, match="Unknown option"):
        parse_config_row("00 BOGUS")


def test_parse_led_row_valid():
    assert parse_led_row("_ _ u d 1") == [
        LedState.EMPTY,
        LedState.EMPTY,
        LedState.UP,
        LedState.DOWN,
        LedState.STATIC_ON,
    ]


def test_parse_led_row_invalid():
    with pytest.raises(ValueError, match="Unexpected character"):
        parse_led_row("_ x u")


def test_extract_coordinate_buckets_valid():
    grid = PatternGrid(
        top_left=Coordinate(0, 0),
        grid=[
            [LedState.UP, LedState.EMPTY, LedState.STATIC_ON],
            [LedState.EMPTY, LedState.DOWN, LedState.EMPTY],
        ],
    )
    starts, ends, static = extract_coordinate_buckets(grid)
    assert starts == [Coordinate(0, 0)]
    assert ends == [Coordinate(1, 1)]
    assert static == [Coordinate(2, 0)]


def test_extract_coordinate_buckets_mismatch():
    grid = PatternGrid(
        top_left=Coordinate(0, 0), grid=[[LedState.UP, LedState.UP, LedState.DOWN]]
    )
    with pytest.raises(ValueError, match="LED count mismatch"):
        extract_coordinate_buckets(grid)


def test_sort_coordinates_ltr_down():
    coords = [Coordinate(2, 1), Coordinate(0, 1), Coordinate(1, 0), Coordinate(0, 0)]
    config = Config(Coordinate(0, 0), "LTR", "DOWN", "NEW", delay_ms=2000)
    rng = random.Random()
    rng.seed(4)
    # Emptying (reverse Y = False for DOWN) -> Top to bottom, LTR
    emptying_sorted = sort_coordinates(coords, config, is_emptying=True, rng=rng)
    assert emptying_sorted == [
        Coordinate(0, 0),
        Coordinate(1, 0),
        Coordinate(0, 1),
        Coordinate(2, 1),
    ]

    # Filling (reverse Y = True for DOWN) -> Bottom to top, LTR
    filling_sorted = sort_coordinates(coords, config, is_emptying=False, rng=rng)
    assert filling_sorted == [
        Coordinate(0, 1),
        Coordinate(2, 1),
        Coordinate(0, 0),
        Coordinate(1, 0),
    ]


def test_sort_coordinates_rtl_up():
    coords = [Coordinate(2, 1), Coordinate(0, 1), Coordinate(1, 0), Coordinate(0, 0)]
    config = Config(Coordinate(0, 0), "RTL", "UP", "NEW", delay_ms=2000)
    rng = random.Random()
    rng.seed(4)

    # Emptying (reverse Y = True for UP) -> Bottom to top, RTL
    emptying_sorted = sort_coordinates(coords, config, is_emptying=True, rng=rng)
    assert emptying_sorted == [
        Coordinate(2, 1),
        Coordinate(0, 1),
        Coordinate(1, 0),
        Coordinate(0, 0),
    ]


def test_full_parsing_and_buckets(tmp_path):
    test_file = tmp_path / "test_pattern.txt"
    test_file.write_text("00 LTR DOWN SEED:NEW\n" "u 1 _\n" "_ d _\n")

    config, grid = parse_input(test_file)
    starts, ends, static = extract_coordinate_buckets(grid)

    assert config.direction == "DOWN"
    assert len(starts) == 1
    assert len(ends) == 1
    assert len(static) == 1
    assert starts[0] == Coordinate(0, 0)  # 'u'
    assert static[0] == Coordinate(1, 0)  # '1'
    assert ends[0] == Coordinate(1, 1)  # 'd'
