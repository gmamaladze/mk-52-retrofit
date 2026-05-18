# Program library

YAML programs in `programs/` are numbered (`NN-id.yaml`). The number is what
the Pi controller uses for "load from ROM" via the A↑ key.

| № | id | Title | Notes |
|----|----|----|----|
| 01 | moon-landing | Прилунение | Lunar landing simulation (input registers Р1–Р8 first) |
| 02 | newton-sqrt  | Корень по Ньютону | Newton's-method sqrt, one iteration per С/П |
| 03 | fibonacci    | Числа Фибоначчи | Fibonacci sequence, one term per С/П |
| 04 | counter      | Счётчик | Increment on each С/П (starts at 0) |
| 05 | squares      | Квадраты натуральных чисел | 1, 4, 9, 16, … |
| 06 | factorial    | Факториал | Input n ≥ 1, get n! |
| 07 | dice         | Игральная кость | Random 1…6 per С/П |
| 08 | gcd          | НОД | Euclid's algorithm — input a В↑ b, get gcd |
| 09 | power        | Целая степень | Input x В↑ n, get xⁿ |
| 10 | sum-n        | Сумма 1…n | Input n, get 1 + 2 + … + n |

## Loading on the Pi (A↑ key, "ROM" workflow)

The original МК-52's A↑ key reads a program off a ROM cartridge by number.
The controller mirrors that:

1. Type the program number on the keypad (one or two digits).
2. Press **A↑**.
3. The LCD shows `LOAD NN <title>` while keystroke-entry writes the program
   into program memory, then `OK NN STEPS`.
4. Type any inputs the program needs, then press **В/О**, **С/П** to run.

Behaviors:
- A↑ with an empty digit buffer → "ENTER NUMBER".
- Unknown number → "NO PROG NN".
- The digit buffer is reset by any non-digit key, so you can't accidentally
  load from old digits.

## Loading on the desktop (web UI)

Pick from the dropdown in the lower panel and click *Load to MK-52*. The
server uses the same keystroke-entry path under the hood (`controller/emulator/keystroke_loader.py`).

## Adding a new program

1. Create `programs/NN-shortname.yaml` with this schema:

   ```yaml
   id: shortname
   title: Short title
   description: One-line description
   author: Your name
   instructions: |
     Multi-line usage notes.
   code: |
     0 П1 ИП1 С/П
     1 + П1 БП 02
   ```

2. The web UI auto-discovers it on next page load.
3. For Pi A↑ loading, the NN prefix becomes the program number.

The token vocabulary the keystroke loader understands is in
`controller/emulator/keystroke_loader.py` (`_SINGLE`, `_F_PREFIX`,
`_K_PREFIX`). Address-byte tokens like `02`, `14`, `54` are auto-recognized
as two-digit BCD addresses (the chip combines them into one byte).
