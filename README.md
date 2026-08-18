# Civilization V Singleplayer → Hotseat Converter

Convert existing **Sid Meier's Civilization V singleplayer and scenario saves into true Hotseat games**, with the ability to choose exactly which civilizations are controlled by human players.

This makes it possible to play scenarios such as **Fall of Rome** and **1066: Year of Viking Destiny** in Hotseat even though Civilization V does not normally provide a way to configure those scenarios as Hotseat games.

## Features

* Convert an existing `.Civ5Save` from Singleplayer to Hotseat.
* Automatically detects the civilizations present in the save.
* Select any combination of civilizations as human players using checkboxes.
* Unselected civilizations remain AI-controlled.
* Supports more than two human players.
* Preserves the existing scenario state, including:

  * cities
  * units
  * diplomacy
  * map
  * scenario rules
  * starting positions
* Creates a new save instead of modifying the original.
* Can output directly to the Civilization V Hotseat save directory.

## Tested

Successfully tested with:

* **Fall of Rome**

  * Western Rome and Eastern Rome as two human players.
* **1066: Year of Viking Destiny**

  * All four civilizations simultaneously configured as human players.

Additional scenarios and ordinary singleplayer saves may also work, but have not all been individually tested.

## How to Use

1. Launch `Civ5HotseatConverter.exe`.

2. Select the `.Civ5Save` you want to convert.

3. A list of civilizations contained in the save will appear.

4. Check every civilization you want controlled by a human.

5. Click **Convert to Hotseat**.

6. The converted save will be created as:

   `OriginalSaveName_HOTSEAT.Civ5Save`

7. Open Civilization V.

8. Go to:

   **Multiplayer → Hot Seat → Load Game**

9. Load the converted save.

Civilization V should now perform normal sequential Hotseat handoffs between the civilizations selected as human players.

## Save Location

The converter can save directly to the current Windows user's Civilization V Hotseat directory:

`Documents\My Games\Sid Meier's Civilization 5\Saves\hotseat`

For example:

`C:\Users\YourName\Documents\My Games\Sid Meier's Civilization 5\Saves\hotseat`

## Building From Source

Requirements:

* Python 3
* PyInstaller

Install PyInstaller:

```bat
python -m pip install pyinstaller
```

Build the executable:

```bat
python -m PyInstaller --onefile --noconsole --name Civ5HotseatConverter Civ5HotseatConverter.py
```

The finished executable will appear in:

```text
dist\Civ5HotseatConverter.exe
```

A provided `BUILD_EXE.bat` can perform this automatically.

## How It Works

Civilization V stores multiplayer information in several places inside a `.Civ5Save`.

Simply changing the obvious game-type byte is **not enough**. Doing so can make the save appear in the Hotseat menu while Civilization V still internally behaves as though it were a Singleplayer or network-style game.

The converter updates the relevant save structures, including:

* the visible game-type field
* Civilization V's additional internal game-type field
* player Human/AI status data
* duplicated player-status structures
* Hotseat player names
* local-player participation information
* other player metadata required for proper Hotseat handoff

The critical discovery was that Civilization V stores its game type in **more than one location**. Converting both is necessary for genuine local Hotseat behavior.

## Development

The converter was developed by comparing:

* genuine Singleplayer scenario saves
* genuine one-human/one-AI Hotseat saves
* genuine multi-human Hotseat saves
* saves captured immediately before different players' turns

These files were compared at the binary level to determine which structures Civilization V changes when creating a legitimate Hotseat game.

A major breakthrough came from examining the open-source save manipulation code originally used by **Giant Multiplayer Robot**, which revealed Civilization V's second internal game-type field.

## Credits

This project benefited greatly from previous Civilization V save-format reverse engineering and open-source work, particularly:

* **Giant Multiplayer Robot / CivSaveLib**
* **civ5-save-parser**
* **js-civ5save**
* the Civilization V modding and reverse-engineering communities
* **CivFanatics**

Without their previous work documenting portions of the `.Civ5Save` format, this utility would have been considerably more difficult to create.

## Important Notes

Always keep your original save.

The converter creates a separate Hotseat copy, but Civilization V's save format is complex and not fully documented. Some unusual mods, total conversions, custom DLLs, or heavily modified scenarios may use structures that have not been tested.

If a converted save behaves incorrectly, retain the original and report:

* the scenario or mod being used
* number of civilizations
* which civilizations were selected as human
* what happened when the converted save was loaded

## Why This Exists

Civilization V includes many excellent scenarios that were designed primarily for Singleplayer and do not expose normal Hotseat setup controls.

However, the game engine itself is capable of running those scenarios with multiple human players.

This utility bridges that gap.

**Load scenario. Pick civilizations. Convert. Play Hotseat.**
