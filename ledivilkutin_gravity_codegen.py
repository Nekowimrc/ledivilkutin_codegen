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
from dataclasses import dataclass, replace
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
        return f"s{self.coord.y:x}{self.coord.x:x}"


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
    delay_ms: int
    max_brightness: float = 1.0


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
    coords: List[Coordinate], config: Config, is_emptying: bool, rng: random.Random
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
    rng = random.Random()
    if config.seed != "NEW":
        rng.seed(config.seed)
    ordered_starts = sort_coordinates(starts, config, is_emptying=True, rng=rng)
    ordered_ends = sort_coordinates(ends, config, is_emptying=False, rng=rng)

    return list(zip(ordered_starts, ordered_ends))


def generate_dsl(
    config: Config,
    pattern: PatternGrid,
    frame_delay_ticks: int = 15,
    verbose: bool = False,
) -> str:
    """Generates the DSL string, optionally formatted with comments."""
    active_brightness = int(round(15.0 * config.max_brightness))
    starts, ends, static = extract_coordinate_buckets(pattern)
    pairs = create_gravity_mapping(starts, ends, config)

    commands: list[Command] = []

    if static or starts:
        commands.append(Effect(AnimationEffect.BRIGHTEN_TO_MAX, active_brightness))
        for coord in static:
            commands.append(SetLed(coord))
        for coord in starts:
            commands.append(SetLed(coord))

    commands.append(Wait(frame_delay_ticks))
    for start, end in pairs:
        commands.append(Effect(AnimationEffect.DIM_TO_ZERO, 0))
        commands.append(SetLed(start))

        commands.append(Effect(AnimationEffect.BRIGHTEN_TO_MAX, active_brightness))
        commands.append(SetLed(end))

        commands.append(Wait(frame_delay_ticks))

    if not verbose:
        # Standard mode: one continuous string
        dsl_body = "".join(cmd.to_dsl() for cmd in commands)
        return f'"{dsl_body}"\n'

    # Verbose mode: multi-line quoted strings with C-style comments[cite: 7]
    lines = []
    for cmd in commands:
        dsl_str = cmd.to_dsl()

        if isinstance(cmd, Effect):
            comment = f"Set {cmd.effect.name} brightness {cmd.brightness}"
        elif isinstance(cmd, SetLed):
            comment = f"Apply to LED at {cmd.coord}"
        elif isinstance(cmd, Wait):
            comment = f"Wait {cmd.ticks * 15}ms"
        else:
            comment = ""

        # Pad the string to align the comments cleanly
        lines.append(f'"{dsl_str}"{" " * (10 - len(dsl_str))} // {comment}')

    return "\n".join(lines) + "\n"


def parse_topleft_pair(string: str) -> Coordinate:
    """Parse the top-left coordinate into Coordinate

    >>> parse_topleft_pair("10")
    Coordinate(x=0, y=1)
    >>> parse_topleft_pair("(0, 1)")
    Coordinate(x=0, y=1)

    """
    generic_value_error = ValueError(
        "The top-left coordinate must be specified as first field, with hexpair 'YX' or as integer-tuple '(x,y)'"
    )
    if string.startswith("(") and string.endswith(")"):
        # Handle (x, y)
        parts = string[1:-1].split(",")  # '(foo bar, bar)' -> ["foo bar" " baz"]
        if len(parts) != 2:
            raise generic_value_error
        try:
            xval = int(parts[0].strip())
            yval = int(parts[1].strip())
            return Coordinate(xval, yval)

        except ValueError as verr:
            raise ValueError(
                f"The top-left corner tuple must be like '(2,4)'. Got {string}"
            ) from verr
    elif not len(string) == 2:
        raise generic_value_error
    else:
        xchar = string[1]
        ychar = string[0]

        try:
            xval = int(xchar, base=16)
            yval = int(ychar, base=16)
            return Coordinate(xval, yval)
        except ValueError as verr:
            raise ValueError(
                f"The top-left corner hex-values must be valid hex-characters. Got {string}"
            ) from verr


def parse_config_row(first_row: str) -> Config:
    """Parses the first row into a config.


    >>> parse_config_row("00")
    Config(top_left=Coordinate(x=0, y=0), animation_pattern='RANDOM', direction='DOWN', seed='NEW', delay_ms=2000, max_brightness=1.0)

    >>> parse_config_row("1f LTR UP SEED:42")
    Config(top_left=Coordinate(x=15, y=1), animation_pattern='LTR', direction='UP', seed=42, delay_ms=2000, max_brightness=1.0)

    >>> parse_config_row("a3 UP SEED:NEW RTL")
    Config(top_left=Coordinate(x=3, y=10), animation_pattern='RTL', direction='UP', seed='NEW', delay_ms=2000, max_brightness=1.0)

    >>> parse_config_row("1")
    Traceback (most recent call last):
        ...
    ValueError: The top-left coordinate must be specified as first field, with hexpair 'YX' or as integer-tuple '(x,y)'

    >>> parse_config_row("gh")
    Traceback (most recent call last):
        ...
    ValueError: The top-left corner hex-values must be valid hex-characters. Got gh

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
    max_brightness: float = 1.0
    seed = "NEW"
    delay_ms = 2000  # default is two seconds

    # check that the coordinate is valid
    maybe_coord = items[0]
    topleft = parse_topleft_pair(maybe_coord)

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

            case s if s.startswith("DELAY:"):
                parts = s.split(":")
                if len(parts) != 2:
                    raise ValueError(f"Expected DELAY:NUM, got {s}")
                try:
                    delay_ms = int(parts[1])
                except ValueError as verr:
                    raise ValueError(
                        f"Expected integer for delay, got {parts[1]}"
                    ) from verr
            case s if s.startswith("BRIGHTNESS"):
                parts = s.split(":")
                if len(parts) != 2:
                    raise ValueError(f"Expected BRIGHTNESS:FLOAT, got {s}")
                try:
                    max_brightness = parse_brightness_float(parts[1])
                except ValueError as verr:
                    raise ValueError(f"Expected float for brightness, got {parts[1]}")
                if not 0.0 <= max_brightness <= 1.0:
                    raise ValueError(
                        f"Brightness must be between 0.0 and 1.0. got {max_brightness}"
                    )

            case _:
                raise ValueError(f"Unknown option: {item}")

    return Config(
        top_left=topleft,
        animation_pattern=pattern,
        direction=direction,
        seed=seed,
        delay_ms=delay_ms,
        max_brightness=max_brightness,
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


def parser_seed_arg(val: str) -> int | Literal["NEW"]:
    if val.upper() == "NEW":
        return "NEW"
    try:
        return int(val)
    except ValueError as verr:
        raise argparse.ArgumentTypeError(
            f"Expected 'NEW' or integer for seed, got '{val}'"
        ) from verr


def parse_brightness_float(val: str) -> float:
    MIN = 0.067
    try:
        f = float(val)
    except ValueError as verr:
        raise argparse.ArgumentTypeError(f"'{val}' is not a valid float.") from verr
    if not MIN <= f <= 1.0:
        raise argparse.ArgumentTypeError(
            f"brightness {f} must be between 0.0 and {MIN}"
        )
    return f


def main():
    parser = argparse.ArgumentParser(
        description="Generate animation definition for Ledivilkutin from an input file."
    )
    parser.add_argument("filepath", type=Path, help="Path to the animation input file")
    parser.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        help="Print DSL in multiline format with comments",
    )
    parser.add_argument(
        "-b",
        "--brightness",
        type=parse_brightness_float,
        default=None,
        help="Maximum brightness muliplier from 0.0 to 1.0 (default 1.0)",
    )
    parser.add_argument(
        "-s",
        "--seed",
        type=parser_seed_arg,
        default=None,
        help="Override RNG seed (integer or 'NEW')",
    )
    parser.add_argument(
        "-d",
        "--delay",
        type=int,
        default=None,
        help="Override frame delay in milliseconds (e.g., 2000)",
    )
    args = parser.parse_args()

    try:
        # Parse the first line into config, rest of the lines into pattern
        config, pattern_grid = parse_input(args.filepath)

        # If command-line flags were used, they override the files config
        if args.brightness is not None:
            config = replace(config, max_brightness=args.brightness)
        if args.delay is not None:
            config = replace(config, delay_ms=args.delay)
        if args.seed is not None:
            config = replace(config, delay_ms=args.seed)

        # calculate the delay in ticks
        # TODO: this is here but similar logic for brightness
        #       is inside generate_dsl. Should do both in the same place I guess
        delayticks = int(config.delay_ms / TIME_UNIT)
        dsl_code = generate_dsl(config, pattern_grid, delayticks, args.verbose)
        if not args.verbose:
            print(f"// Successfully parsed {args.filepath}")
            print(f"// Config: {config}")
            print(
                f"// Grid: {len(pattern_grid.grid)}x{len(pattern_grid.grid[0])} parsed.\n//Code:\n"
            )
        print(dsl_code, end="")
        sys.exit(0)

    except FileNotFoundError:
        print(f"Error: File not found at '{args.filepath}'", file=sys.stderr)
        sys.exit(1)
    except ValueError as e:
        print(f"Parse Error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
