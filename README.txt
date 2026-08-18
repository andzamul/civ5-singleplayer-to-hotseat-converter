CIVILIZATION V SINGLEPLAYER -> HOTSEAT CONVERTER

WHAT IT DOES
------------
1. Double-click Civ5HotseatConverter.exe.
2. Pick a .Civ5Save.
3. Check every civilization that should be human-controlled.
4. Click "Convert to Hotseat".
5. A new file ending in _HOTSEAT.Civ5Save is created beside the original.
6. Load that new file in:
   Civilization V -> Multiplayer -> Hot Seat -> Load Game

BUILDING THE EXE
----------------
Put these two files in the same folder:
  Civ5HotseatConverter.py
  BUILD_EXE.bat

Then double-click BUILD_EXE.bat.

The finished Windows executable will be:
  dist\Civ5HotseatConverter.exe

IMPORTANT
---------
The converter always makes a COPY and does not overwrite the original save.

This utility is based on the conversion behavior we verified against:
- a genuine Civ V 1-human/1-AI Hotseat save
- a genuine Civ V 2-human Hotseat save
- the Fall of Rome scenario
- GMR's open-source CivSaveLib game-type logic

The crucial conversion writes BOTH Civ V game-type fields to Hotseat.
Changing only the visible header byte can make a file appear to be Hotseat
while Civ V still behaves internally as a single-player/network-style game.
