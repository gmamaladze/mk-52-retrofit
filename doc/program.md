## Programming MK 52

Pull this program using web interface into the programmable calculator:
```
ИП1 С/П ИП3 С/П ИП2 С/П ИП4 1   0    *
ИП5 /   ИП6 -   П7  ИП8 *   ИП3 +    П9
x^2 ^   ИП3 x^2 -   ИП7 /   2   /    ИП1
+   П1  ИП9 П3  ИП2 ИП4 ИП8 -   П2   |x|
2   -   x<0 00  ИП3 |x| 5   -   x>=0 54
6   6   6   С/П 7   7   7   С/П
```

This are registers used in a program, their meanings and initial values. 

Register|Variable|Initial values
--------|--------|-----
R1|height|100
R2|fuel|140
R3|velocity|0
R4|fuel supply|-
R5|mass|10
R6|planet gravity|9.8
R7|acceleration|0
R8|cycle duration|1
R9|TEMP|-


After the program is loaded into the programmable calculator we need to set
initial values of variables:
 
```
// Write initail values into registers 
100  X→П  1     // LET R1_height = 100
140  X→П  2     // LET R2_fuel = 140
  0  X→П  3     // LET R3_velocity = 0
 10  X→П  5     // LET R5_mass = 10
9,8  X→П  6     // LET R6_gravity = 9.8
  1  X→П  8     // LET R8_cycle_duration = 1
 ```

After that we need to run the program:
 ```
  В/0           // GOTO 0
  С/П           // RUN
 ```
 
 Time to time the program will stop it's execution and ask for input.
 To rerun the program from current position we use:
 ```
   С/П           // RUN
 ```
 
 The program translated into a pseudo code:
 ```
 00:    П→Х 1       // PRINT R1_height
 01:    с/п         // PAUSE (press с/п to resume)
 02:    П→Х 3       // R3_velocity    
 03:    с/п         // PAUSE (press с/п to resume)
 04:    П→Х 2       // PRINT R2_fuel
 05:    с/п         // PAUSER4_fuel_supply(press с/п to resume)
 05:    Х→П 4	    // INPUT R4_fuel_supply (type a number and press с/п to resume)
 06:    1
 07:    0
 08:    *
 09:    П→Х5
 10:    /
 11:    П→Х6
 12:    -
 13:    Х→П 7	    //LET R7_acceleration = (R4_fuel_supply*10 - R5_mass * R6_gravity) / R5_mass
 14:    П→Х 8
 15:    *
 16:    П→Х3
 17:    +
 18:    Х→П 9       //LET R9_temp = R3_velocity + R7_acceleration * R8_cycle_duration
 19:    Fx2
 20:    В|
 21:    П→Х 3
 22:    Fx^2
 23:    -
 24:    П→Х 7
 25:    /
 26:    2
 27:    /	        //LET distance=(R9_temp^2 - R3_velocity^2) / R7_acceleration / 2 (throws ЕГГОГ - division by zero)
 28:    П→Х 1
 29:    +
 30:    Х→П 1	    //LET R1_height=R1_height+distance
 31:    П→Х 9
 32:    Х→П 3	    //LET R3_velocity=R9_temp
 33:    П→Х 2
 34:    П→Х 4
 35:    П→Х 8
 36:    -
 37:    Х→П 2	    //LET R2_fuel = R2_fuel - R4_fuel_supply * R8_cycle_duration
 38:    K|x|
 39:    2
 40:    -
 41:    Fx>=0
 42:    46
 43:    БП
 44:    00
 45:    П→Х 3
 46:    К|x|
 47:    5
 48:    -
 49:    Fx>=0
 50:    56
 51:    6
 52:    6
 53:    6
 54:    c/п
 55:    7
 56:    7
 57:    7
 58:    с/п	        //IF ((ABS(R1_height)-2)<=0) AND ((ABS(R3_velocity)-2)<=0) THEN 
                    //  PRINT 777
                    //ELSE IF (R2_fuel<=0)
                    //  PRINT 666
                    //ELSE
                    //  GOTO 00
                    //ENDIF
 ```