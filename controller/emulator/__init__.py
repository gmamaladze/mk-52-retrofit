# -*- coding: utf-8 -*-
from .machine import Машина

# Back-compat alias so existing call sites can keep using `Emulator`.
Emulator = Машина

__all__ = ["Машина", "Emulator"]
