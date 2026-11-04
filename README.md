# Animation Code generator for ledivilkutin DSL

Generate valid DSL for ledivilkutin based on an input file
## Usage

Generate the code as a single string:

``` shell
ledivilkutin_gravity_codegen.py <pattern-file>
```

Generate commented code:
``` shell
ledivilkutin_gravity_codegen.py -v <pattern-file>
```

See help (for possible undocumented flags):

``` shell
ledivilkutin_gravity_codegen.py -h
```

Pattern file defines the initial and final position of LEDs. The example
file [[file:example_pattern.txt]] shows the valid pattern.

## Input file specification

Input file specifies the animations coordinates, initial state and end-state.
This is turned into the animation code through *gravity*. LED's fall down from
their initial pattern to positions defined by the final pattern.

## Valid Patterns to animate

- number of LED's initially on equals the number of LED's active in the final
  pattern
  *This simplifies the animating process*

- the specified top-left coordinate `NM` fullfills:
   + **N:** in range 0-f
   + **M:** in range 0-f
  *The coordinates are used for building the indexes of LEDs*

- Every row of the pattern has equal width

- Every LED in every row is either notated by `u`, `d`, `1` or `_`.

## Input file syntax

The input file consists of two sections:
+ **configuration (first row):** names the top-right LED of the pattern (can be
  inactive)
+ **pattern (starting from first non-empty row below first):** defines all LED's
  in the animations rectangular area: their initial and final position, or that
  they are blanks. 

### Configuration

At the beginning of the configuration row the top-left corner of the pattern is
defined. This is done with two characters, in 0-f.

To start the pattern from the actual top-left-most LED on the PCB, set this to
`00`. Else, define a rectangle around the pattern you want, and use its top-left
corners coordinates. To define second LED of third row as the corner, use `32`.

Configuration options are written after the top-right coordinate, separated by
space. Following configuration options are supported, the option marked as
default is assumed if no other option is given:

- **RANDOM (default) | LTR | RTL :** the animation for each row. Random picks a
  random LED along the remaining ones. LTR empties each row left-to-right. RTL
  empties each row right-to-left
- **DOWN (default)| UP :** direction of "gravity." if set to "up", the starting
  position is emptied from lowest row to highest, and the final position is
  filled from the highest row to lowest.

- **SEED:NUM | seed:NEW (assumed) :** Sets the RNG seed used for random pattern.
  If set to "NEW", a random pattern is generated each time.
- **DELAY:NUM (default: 2000):** Sets the (approximate) wait time between each
  animation frame in milliseconds. For example: `DELAY:500` applies a
  half-second pause between each falling LED. This gets rounded down to 13ms
  ticks. The 13ms delay is an approximation in DSL documentation, so all time
  estimates in output/input are subject to inaccuracy.

### Pattern

- `u`**(Up / Start):** Lit during initialization. Falls down to an available `d`
  position during animation sequence.
- `d` **(Down / End):** Unlit during initialization. The final resting
  destination for a falling `u` LED.
- `1` **(Static On):** Lit during initialization and remains permanently on.
  Unaffected by gravity.
- `_` **(Empty / Static Off):** Unlit and ignored by the animation. **required
  as padding to maintain equal row widths.**


## Animation
This script generates a gravity-based transition from an initial pattern to a
final pattern.

### Initialization
Before the animation begins, the script turns on all u and 1 LEDs
to maximum brightness to display the full starting state (e.g., a full upper
glass of an hourglass). A full frame delay is applied immediately after setup so
the initial state is clearly visible.

### The Gravity Effect
The script moves exactly one LED per step. During each step,
a single u LED dims to zero while its paired d LED brightens to maximum.

### Timing
The frame delay dictates the wait time between every single falling "grain." If
a 2.0-second delay is configured, the initial pattern holds for 2.0 seconds, and
then exactly one LED moves every 2.0 seconds until the u pattern has completely
shifted into the d pattern.
