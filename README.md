# Animation Code generator for ledivilkutin DSL

Generate valid DSL for ledivilkutin based on an input file
## Input file specification

Input file specifies the animations coordinates, initial state and end-state.
This is turned into the animation code through *gravity*. LED's fall down from
their initial pattern to positions defined by the final pattern.

## Valid Patterns to animate

- number of LED's initially on equals the number of LED's active in the final
  pattern
  *This simplifies the animating process*

- the specified top-left coordinate `(N,M)` fullfills:
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
corners coordinates

Configuration options are written after the top-right coordinate, separated by
space. Following configuration options are supported, the option marked as
default is assumed if no other option is given:

- **random (default) | LTR | RTL :** the animation for each row. Random picks a
  random LED along the remaining ones. LTR empties each row left-to-right. RTL
  empties each row right-to-left
- **down (default)| up :** direction of "gravity." if set to "up", the starting
  position is emptied from lowest row to highest, and the final position is
  filled from the highest row to lowest.

- **seed:NUM | seed:NEW (assumed) :** Sets the RNG seed used for random pattern.
  If set to "NEW", a random pattern is generated each time.

### Pattern

The pattern consists of rows of characters, where each row represents a row of
LED's. LEDS of row are represented by `u`, `d`, `1` or `_`. There can be
arbitary whitespace between these characters, either space or tabs. newline
character separates the rows.

Every row must have equal width. So, even if no such LED's exist on some row,
they need to be "padded" in the pattern with `_`.

Example: Suppose your ledivilkutin has the following pattern of SMD LEDS, where
`_` represent an empty pad on the PCB, and `L` represents an SMD LED device:

_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ 
_ _ _ _ _ _ _ L L L _ _ _ _ _ _
_ _ _ _ _ _ _ _ L L _ _ _ _ _
_ _ _ _ _ _ _ L L L L _ _ _ _

The animation you want has a starting position (`L` represents a lit up LED):

_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ 
_ _ _ _ _ _ _ L L L _ _ _ _ _
_ _ _ _ _ _ _ _ L _ _ _ _ _ _
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _

And an end position like this:


_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ 
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ 
_ _ _ _ _ _ _ _ _ L _ _ _ _ _
_ _ _ _ _ _ _ _ L L L _ _ _ _

To represent it in the file, the middle row MUST include padding. However, we
don't need to draw the whole. However, we DO need to include some padding.

Counting the initial position, the left-most colum is 7. The highest LEDs are on
row 1 (first row is row 0). So by setting the first coordinate to (1, 7), we can
start drawing from the first L. We also only need to draw a pattern as wide as
our rightmost LED we want to set on. To match this, our first row must be:


u u u _ 

We need the fourth column, else we can't draw the last row of our pattern. The
full pattern we want is as follows:

u u u _ 
_ u d _
_ d d d


Similarly, the need for padding on the second and third row is illustrated. We
without them, it would be ambigious. That some of these LEDs are not installed
doesn't matter for the script we generate.




## Animation

This script only handles a very specific kind of animation: the initial pattern
shifting from the initial pattern (`u`) to the final pattern (`d`). The letterns
stand for up and down.
