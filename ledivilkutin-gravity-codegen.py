#!/usr/bin/env python3

"""Generate animation definition for Ledivilkutin, as part of Rakentelutyö: Ledivilkutin,
 using the DSL internal to the TUNI course ITC-010 Johdanto tekniikan opintoihin.

author: joonas.pastila@tuni.fi
license: MIT"""

from typing import NamedTuple, LiteralString, Union, Literal, Protocol
from dataclasses import dataclass
from enum import Enum, StrEnum

type Animation_Effect_t = Literal[
    "NOANIM" "DIM_TO_ZERO" "BRIGHTEN_TO_MAX" "DIM_LIGHT_DIM" "LIGHT_DIM_LIGHT"
]

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
    x: int
    y: int

    def __post_init__(self):
        if not (0 <= self.x <= 15 and 0 <= self.y <= 15):
            raise ValueError(
                f"Coordinates ({self.x}{self.y}) outside the 16x16 matrix."
            )
        return

    def to_dsl(self) -> str:
        return f"s{self.x:01x}{self.y:01x}"


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
