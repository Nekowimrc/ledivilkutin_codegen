#!/usr/bin/env python3

"""Generate animation definition for Ledivilkutin, as part of Rakentelutyö: Ledivilkutin,
 using the DSL internal to the TUNI course ITC-010 Johdanto tekniikan opintoihin.

author: joonas.pastila@tuni.fi
license: MIT"""

from typing import (
    List,
    Literal,
    Protocol,
    Optional,
    Tuple,
    assert_never,
)
from dataclasses import dataclass
from enum import Enum, StrEnum
import argparse
from pathlib import Path
import sys
import random
from itertools import groupby

TIME_UNIT = 15  # ms -- approximation given in docs of the DSL


class AnimationEffect(Enum):
    NOANIM = 0
    DIM_TO_ZERO = 1
    BRIGHTEN_TO_MAX = 3
    DIM_LIGHT_DIM = 5
    LIGH_DIM_LIGHT = 7


class Command(Protocol):
    def to_dsl(self) -> str:
        """Render the command to its C-string representation."""
        ...


@dataclass(frozen=True)
class Coordinate:
    x: int
    y: int

    def __str__(self):
        return f"({self.x},{self.y})"

    def __post_init__(self):
        if not (0 <= self.x <= 15 and 0 <= self.y <= 15):
            raise ValueError(f"Coordinate {self} outside 0-f bounds.")
        return


class LedState(StrEnum):
    UP = "u"
    DOWN = "d"
    STATIC_ON = "1"
    EMPTY = "_"


@dataclass(frozen=True)
class Effect(Command):
    effect: AnimationEffect
    brightness: int

    def __post_init__(self):
        if not 0 <= self.brightness <= 15:
            raise ValueError(f"Brightness {self.brightness} out of bounds (0-15)")
        return

    def to_dsl(self) -> str:
        return f"e{self.effect.value:x}{self.brightness:x}"


@dataclass(frozen=True)
class SetLed(Command):
    coord: Coordinate

    def to_dsl(self) -> str:
        return f"s{self.coord.x:x}{self.coord.y:x}"


@dataclass(frozen=True)
class AllLeds(Command):
    def to_dsl(self) -> str:
        return "a"


@dataclass(frozen=True)
class Wait(Command):
    ticks: int  # 1 tick = TIME_UNIT_MS

    def __post_init__(self):
        if not 0 <= self.ticks <= 0xFFFF:
            raise ValueError(
                f"Wait ticks {self.ticks} outside the allowed 16-bit hex range."
            )
        return

    def to_dsl(self) -> str:
        return f"w{self.ticks:04x}"


type LedRow = list[LedState]


@dataclass(frozen=True)
class PatternGrid:
    top_left: Coordinate
    grid: list[LedRow]

    def get_absolute_coordinate(self, row: int, col: int) -> Coordinate:
        """Translates a relative grid position to absolute matrix coordinate."""

        return Coordinate(x=self.top_left.x + col, y=self.top_left.y + row)


@dataclass(frozen=True)
class Config:
    top_left: Coordinate
    animation_pattern: Optional[Literal["RANDOM", "LTR", "RTL"]]
    direction: Optional[Literal["UP", "DOWN"]]
    seed: Optional[int | Literal["NEW"]]


def extract_coordinate_buckets(
    pattern: PatternGrid,
) -> Tuple[List[Coordinate], List[Coordinate], List[Coordinate]]:
    """Extracts starting and ending coordinates from the pattern grid."""
    starts: list[Coordinate] = []
    ends: list[Coordinate] = []
    static_on: list[Coordinate] = []

    for r, row in enumerate(pattern.grid):
        for c, state in enumerate(row):
            coord = pattern.get_absolute_coordinate(r, c)
            match state:
                case LedState.UP:
                    starts.append(coord)
                case LedState.DOWN:
                    ends.append(coord)
                case LedState.STATIC_ON:
                    static_on.append(coord)
                case LedState.EMPTY:
                    continue
                case _:
                    assert_never(state)

    # Validate that the number of active LEDs remains constant[cite: 1]
    if len(starts) != len(ends):
        raise ValueError(
            f"LED count mismatch: {len(starts)} initial vs {len(ends)} final."
        )

    return starts, ends, static_on


def sort_coordinates(
    coords: List[Coordinate], config: Config, is_emptying: bool
) -> List[Coordinate]:
    """Sorts coordinates based on direction and row-level animation patterns."""

    # If UP: starting position is emptied from lowest row to highest (max Y to min Y)
    # and final position is filled from highest row to lowest (min Y to max Y)[cite: 1].
    # If DOWN: the inverse applies.
    if config.direction == "UP":
        reverse_y = True if is_emptying else False
    else:
        reverse_y = False if is_emptying else True

    # Sort vertically first
    sorted_coords = sorted(coords, key=lambda c: c.y, reverse=reverse_y)
    final_order = []

    # Initialize RNG once if a specific seed is defined[cite: 1]
    rng = random.Random()
    if config.seed != "NEW":
        rng.seed(config.seed)

    # Group by Y and apply horizontal sorting (LTR/RTL/RANDOM)[cite: 1]
    for _, group in groupby(sorted_coords, key=lambda c: c.y):
        row_coords = list(group)

        if config.animation_pattern == "LTR":
            row_coords.sort(key=lambda c: c.x)
        elif config.animation_pattern == "RTL":
            row_coords.sort(key=lambda c: c.x, reverse=True)
        elif config.animation_pattern == "RANDOM":
            rng.shuffle(row_coords)

        final_order.extend(row_coords)

    return final_order


def create_gravity_mapping(
    starts: List[Coordinate], ends: List[Coordinate], config: Config
) -> List[Tuple[Coordinate, Coordinate]]:
    """Applies sorting policies and pairs initial states with final states."""
    ordered_starts = sort_coordinates(starts, config, is_emptying=True)
    ordered_ends = sort_coordinates(ends, config, is_emptying=False)

    return list(zip(ordered_starts, ordered_ends))


def parse_config_row(first_row: str) -> Config:
    """Parses the first row into a config.


    >>> parse_config_row("00")
    Config(top_left=Coordinate(x=0, y=0), animation_pattern='RANDOM', direction='DOWN', seed='NEW')

    >>> parse_config_row("1f LTR UP SEED:42")
    Config(top_left=Coordinate(x=1, y=15), animation_pattern='LTR', direction='UP', seed=42)

    >>> parse_config_row("a3 UP SEED:NEW RTL")
    Config(top_left=Coordinate(x=10, y=3), animation_pattern='RTL', direction='UP', seed='NEW')

    >>> parse_config_row("1")
    Traceback (most recent call last):
        ...
    ValueError: the top-left coordinate must be specified as first field, with two characters

    >>> parse_config_row("gh")
    Traceback (most recent call last):
        ...
    ValueError: The top-left corner must be defined with valid hex-characters. Got gh

    >>> parse_config_row("00 SEED:hello")
    Traceback (most recent call last):
        ...
    ValueError: Expected 'NEW' or integer, got hello

    >>> parse_config_row("00 BOGUS")
    Traceback (most recent call last):
        ...
    ValueError: Unknown option: BOGUS
    """
    items: list[str] = first_row.strip().split()
    topleft: Coordinate
    pattern: Literal["RANDOM", "LTR", "RTL"] = "RANDOM"
    direction: Literal["UP", "DOWN"] = "DOWN"
    seed = "NEW"

    # check that the coordinate is valid
    maybe_coord = items[0]
    if not len(maybe_coord) == 2:
        raise ValueError(
            "the top-left coordinate must be specified as first field, with two characters"
        )
    xchar = maybe_coord[0]
    ychar = maybe_coord[1]

    try:
        xval = int(xchar, base=16)
        yval = int(ychar, base=16)
        topleft = Coordinate(xval, yval)
    except ValueError as verr:
        raise ValueError(
            f"The top-left corner must be defined with valid hex-characters. Got {maybe_coord}"
        ) from verr

        # Loop over the others
    for item in items[1:]:
        match item.upper():
            case "RANDOM" | "LTR" | "RTL" as p:
                pattern = p
            case "UP" | "DOWN" as d:
                direction = d
            case s if s.startswith("SEED:"):
                parts = item.split(":")
                if len(parts) != 2:
                    raise ValueError(
                        f"Expected seed definition to have form SEED:rest.{s} doesn't have exactly two parts."
                    )
                seedval = parts[1]

                if seedval.upper() == "NEW":
                    continue  # that is the default
                else:
                    try:
                        seed = int(seedval)
                    except ValueError as verr:
                        raise ValueError(
                            f"Expected 'NEW' or integer, got {seedval}"
                        ) from verr

            case _:
                raise ValueError(f"Unknown option: {item}")

    return Config(
        top_left=topleft, animation_pattern=pattern, direction=direction, seed=seed
    )


def parse_led_row(row: str) -> LedRow:
    """Parse line into a list of LedStates.

    >>> parse_led_row("_ _ u")
    [<LedState.EMPTY: '_'>, <LedState.EMPTY: '_'>, <LedState.UP: 'u'>]
    >>> parse_led_row("_ _ d")
    [<LedState.EMPTY: '_'>, <LedState.EMPTY: '_'>, <LedState.DOWN: 'd'>]
    >>> parse_led_row("_ _ 1")
    [<LedState.EMPTY: '_'>, <LedState.EMPTY: '_'>, <LedState.STATIC_ON: '1'>]
    """

    states: list[LedState] = []

    for char in row:
        if char.isspace():
            continue
        try:
            states.append(LedState(char.lower()))
        except ValueError:
            raise ValueError(
                f"Unexpected character: {char}, expected '_', 'U', 'D' or '1'"
            )
    return states


def parse_input(filepath: Path | str) -> Tuple[Config, PatternGrid]:
    """Reads the input file and returns the parsed Config and PatternGrid."""
    with open(filepath, "r", encoding="utf-8") as f:
        lines = f.readlines()

    if not lines:
        raise ValueError(f"Input file '{filepath}' is empty.")

    # Configuration is always the first row[cite: 1]
    config = parse_config_row(lines[0])

    grid: list[list[LedState]] = []
    expected_width = -1

    # Pattern starts from the first non-empty row below the first[cite: 1]
    for line in lines[1:]:
        if not line.strip():
            continue  # Skip empty rows

        row_states = parse_led_row(line)
        if not row_states:
            continue

        if expected_width == -1:
            expected_width = len(row_states)
        elif len(row_states) != expected_width:
            # Enforce the requirement that every row has equal width[cite: 1]
            raise ValueError(
                f"Row width mismatch: expected {expected_width} columns, got {len(row_states)}."
            )

        grid.append(row_states)

    if not grid:
        raise ValueError("No pattern found in the input file.")

    return config, PatternGrid(top_left=config.top_left, grid=grid)


def main():
    parser = argparse.ArgumentParser(
        description="Generate animation definition for Ledivilkutin from an input file."
    )
    parser.add_argument("filepath", type=Path, help="Path to the animation input file")
    args = parser.parse_args()

    try:
        config, pattern_grid = parse_input(args.filepath)
        print(f"Successfully parsed {args.filepath}")
        print(f"Config: {config}")
        print(f"Grid: {len(pattern_grid.grid)}x{len(pattern_grid.grid[0])} parsed.")

        # Generator logic to output the C-header would go here

    except FileNotFoundError:
        print(f"Error: File not found at '{args.filepath}'", file=sys.stderr)
        sys.exit(1)
    except ValueError as e:
        print(f"Parse Error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
