// Микросхемы ИР2 (RAM shift register) and ИК13 (calculator chip).
// Ported from controller/emulator/chips.py.

package mk52

// J table indexed by мт >> 2 (микротакт shifted right by 2) — 42 entries.
var J = [42]int{
	0, 1, 2, 3, 4, 5,
	3, 4, 5, 3, 4, 5,
	3, 4, 5, 3, 4, 5,
	3, 4, 5, 3, 4, 5,
	6, 7, 8, 0, 1, 2,
	3, 4, 5, 6, 7, 8,
	0, 1, 2, 3, 4, 5,
}

// ИР2 — RAM shift register, 252 4-bit cells.
type ИР2 struct {
	M         [252]uint8
	вход      uint8
	выход     uint8
	микротакт int
}

// ИР2.Такт reads M[мт] to выход, stores вход at M[мт], advances мт.
func (chip *ИР2) Такт() {
	мт := chip.микротакт
	chip.выход = chip.M[мт]
	chip.M[мт] = chip.вход
	мт++
	if мт > 251 {
		мт = 0
	}
	chip.микротакт = мт
}

// ИК13 — calculator chip with microcode-driven execution.
type ИК13 struct {
	ПЗУ_микрокоманд    []uint32
	ПЗУ_синхропрограмм []uint32
	ПЗУ_команд         []uint32

	M  [42]uint8
	R  [42]uint8
	ST [42]uint8

	S, S1 uint8
	L, T  uint8
	П     uint8

	микротакт    int
	микрокоманда uint32

	вход  uint8
	выход uint8

	АМК, АСП uint32
	АК       uint32
	МОД      uint32

	индик_зпт [14]bool

	клав_x  int
	клав_y  int
	запятая int

	обн_индик bool
}

// ИК13.Такт runs one chip clock tick. ~150 lines of bit manipulation
// faithful to the original microcode interpreter.
func (chip *ИК13) Такт() {
	мт := chip.микротакт
	АК := chip.АК
	S := chip.S
	S1 := chip.S1
	L := chip.L
	T := chip.T
	АСП := chip.АСП
	АМК := chip.АМК
	МОД := chip.МОД
	запятая := chip.запятая
	обн_индик := chip.обн_индик
	R := &chip.R
	M := &chip.M
	ST := &chip.ST
	индик_зпт := &chip.индик_зпт
	ПЗУ_команд := chip.ПЗУ_команд
	ПЗУ_синхропрограмм := chip.ПЗУ_синхропрограмм
	ПЗУ_микрокоманд := chip.ПЗУ_микрокоманд
	клав_x := chip.клав_x
	клав_y := chip.клав_y

	сигнал_I := мт >> 2
	сигнал_D := мт / 12

	if мт == 0 {
		АК = uint32(R[36]) + 16*uint32(R[39])
		if (ПЗУ_команд[АК] & 0xfc0000) == 0 {
			T = 0
		}
	}
	команда := ПЗУ_команд[АК]
	k := мт / 36
	switch {
	case k < 3:
		АСП = команда & 0xff
	case k == 3:
		АСП = (команда >> 8) & 0xff
	case k == 4:
		АСП = (команда >> 16) & 0xff
		if АСП > 0x1f {
			if мт == 144 {
				R[37] = uint8(АСП & 0xf)
				R[40] = uint8(АСП >> 4)
			}
			АСП = 0x5f
		}
	}
	МОД = (команда >> 24) & 0xff
	АМК = ПЗУ_синхропрограмм[АСП*9+uint32(J[сигнал_I])] & 0x3f
	if АМК > 59 {
		АМК = (АМК - 60) * 2
		if L == 0 {
			АМК++
		}
		АМК += 60
	}
	мк := ПЗУ_микрокоманд[АМК]

	var альфа, бета, гамма uint8

	top2 := (мк >> 24) & 3
	if top2 >= 2 {
		if (мт/12) != клав_x-1 && клав_y > 0 {
			S1 |= uint8(клав_y)
		}
	}

	if мк&1 != 0 {
		альфа |= R[сигнал_I]
	}
	if мк&2 != 0 {
		альфа |= M[сигнал_I]
	}
	if мк&4 != 0 {
		альфа |= ST[сигнал_I]
	}
	if мк&8 != 0 {
		альфа |= (^R[сигнал_I]) & 0xf
	}
	if мк&16 != 0 && L == 0 {
		альфа |= 0xa
	}
	if мк&32 != 0 {
		альфа |= S
	}
	if мк&64 != 0 {
		альфа |= 4
	}

	мк7 := мк >> 7
	if мк7&16 != 0 {
		бета |= 1
	}
	if мк7&8 != 0 {
		бета |= 6
	}
	if мк7&4 != 0 {
		бета |= S1
	}
	if мк7&2 != 0 {
		бета |= (^S) & 0xf
	}
	if мк7&1 != 0 {
		бета |= S
	}

	if команда&0xfc0000 != 0 {
		if клав_y == 0 {
			T = 0
		}
	} else {
		обн_индик = true
		if (мт/12) == клав_x-1 && клав_y > 0 {
			S1 = uint8(клав_y)
			T = 1
		}
		if сигнал_D >= 0 && сигнал_D < 12 && L > 0 {
			запятая = сигнал_D
		}
		индик_зпт[сигнал_D] = L > 0
	}

	мк12 := мк >> 12
	if мк12&4 != 0 {
		гамма = (^T) & 1
	}
	if мк12&2 != 0 {
		гамма |= (^L) & 1
	}
	if мк12&1 != 0 {
		гамма |= L & 1
	}

	сумма := uint16(альфа) + uint16(бета) + uint16(гамма)
	сигма := uint8(сумма & 0xf)
	П := uint8(сумма >> 4)

	if МОД == 0 || сигнал_I >= 36 {
		sw := (мк >> 15) & 7
		if sw != 0 {
			switch sw {
			case 1:
				R[сигнал_I] = R[(сигнал_I+3)%42]
			case 2:
				R[сигнал_I] = сигма
			case 3:
				R[сигнал_I] = S
			case 4:
				R[сигнал_I] = R[сигнал_I] | S | сигма
			case 5:
				R[сигнал_I] = S | сигма
			case 6:
				R[сигнал_I] = R[сигнал_I] | S
			case 7:
				R[сигнал_I] = R[сигнал_I] | сигма
			}
		}
		if (мк>>18)&1 != 0 {
			R[(сигнал_I+41)%42] = сигма
		}
		if (мк>>19)&1 != 0 {
			R[(сигнал_I+40)%42] = сигма
		}
	}

	if (мк>>21)&1 != 0 {
		L = П & 1
	}
	if (мк>>20)&1 != 0 {
		M[сигнал_I] = S
	}

	sw := (мк >> 22) & 3
	switch sw {
	case 1:
		S = S1
	case 2:
		S = сигма
	case 3:
		S = S1 | сигма
	}

	// (мк >> 24) & 3 — same value as `top2` above.
	switch top2 {
	case 1:
		S1 = сигма
	case 3:
		S1 = S1 | сигма
		// case 2 is a no-op
	}

	sw = (мк >> 26) & 3
	if sw == 1 {
		j1 := (сигнал_I + 1) % 42
		j2 := (сигнал_I + 2) % 42
		ST[j2] = ST[j1]
		ST[j1] = ST[сигнал_I]
		ST[сигнал_I] = сигма
	} else if sw == 2 {
		j1 := (сигнал_I + 1) % 42
		j2 := (сигнал_I + 2) % 42
		x := ST[сигнал_I]
		ST[сигнал_I] = ST[j1]
		ST[j1] = ST[j2]
		ST[j2] = x
	} else if sw == 3 {
		j1 := (сигнал_I + 1) % 42
		j2 := (сигнал_I + 2) % 42
		x := ST[сигнал_I]
		y := ST[j1]
		z := ST[j2]
		ST[сигнал_I] = сигма | y
		ST[j1] = x | z
		ST[j2] = y | x
	}

	chip.выход = M[сигнал_I] & 0xf
	M[сигнал_I] = chip.вход
	мт += 4
	if мт > 167 {
		мт = 0
	}

	// Write back local state.
	chip.микротакт = мт
	chip.АК = АК
	chip.S = S
	chip.S1 = S1
	chip.L = L
	chip.T = T
	chip.П = П
	chip.АСП = АСП
	chip.АМК = АМК
	chip.МОД = МОД
	chip.микрокоманда = мк
	chip.запятая = запятая
	chip.обн_индик = обн_индик
}
