package mk52

import "testing"

func TestРазобратьКоманду(t *testing.T) {
	cases := []struct {
		in   string
		want byte
	}{
		{"0", 0x00}, {"1", 0x01}, {"9", 0x09},
		{"+", 0x10}, {"-", 0x11}, {"*", 0x12}, {"/", 0x13},
		{"↔", 0x14}, {"^", 0x0E}, {"В↑", 0x0E},
		{"С/П", 0x50}, {"БП", 0x51}, {"В/О", 0x52},
		{"x^2", 0x22}, {"√", 0x21}, {"π", 0x20},
		{"x<0", 0x5C}, {"x=0", 0x5E}, {"x#0", 0x57}, {"x>=0", 0x59},
		{"П0", 0x40}, {"П1", 0x41}, {"П9", 0x49},
		{"ИП0", 0x60}, {"ИП5", 0x65}, {"ИП9", 0x69},
		{"|x|", 0x31}, {"[x]", 0x34}, {"СЧ", 0x3B},
		// Address-byte fallback (hex parse)
		{"02", 0x02}, {"54", 0x54},
	}
	for _, c := range cases {
		got, err := РазобратьКоманду(c.in)
		if err != nil {
			t.Errorf("%q: unexpected error %v", c.in, err)
			continue
		}
		if got != c.want {
			t.Errorf("%q: got 0x%02X, want 0x%02X", c.in, got, c.want)
		}
	}
}

func TestАдресКоманды(t *testing.T) {
	cases := []struct {
		номер, перм   int
		wantChip, wantAddr int
	}{
		// Step 0 across all 3 permutations
		{0, 0, 1, 83}, {0, 1, 1, 167}, {0, 2, 1, 251},
		// Step 28 perm 1 == step 0 perm 0 (collision case noted in machine.py)
		{28, 1, 1, 83},
	}
	for _, c := range cases {
		chip, addr := АдресКоманды(c.номер, c.перм)
		if chip != c.wantChip || addr != c.wantAddr {
			t.Errorf("step %d perm %d: got (%d, %d), want (%d, %d)",
				c.номер, c.перм, chip, addr, c.wantChip, c.wantAddr)
		}
	}
}
