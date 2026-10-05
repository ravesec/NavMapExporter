HOW TO USE:
Launch a singleplayer or multiplayer lobby by yourself, get in a jet and open your NAV map. Wait a few seconds to make sure the map is loaded properly.
Note that while the mod is capturing tiles, your in-game frames will drop. You can tell when it is finished either by seeing that your FPS is restored, or by checking the player.log file. You can increase your FPS by increasing `wait_frames` inside the config file, but this will make the capture take longer.
Also note: This has not been tested on PTB and may not work as expected. Version tested: v1.12.6f1

CONTROLS:
Edit the config file in "C:\Users\User\AppData\LocalLow\Boundless Dynamics, LLC\VTOLVR\NavMapExports\exporter-config.txt" to your liking.
The config file is reloaded on capture. F9 detects the full map; columns/rows apply to Shift+F9 only
Make sure your game is focused, then;
F7: Cycle through active NAV displays. Shouldn't be necessary to do this unless multiple NAV displays are open.
F8: Capture one tile around the NAV focus.
F9: Detect map bounds and capture the entire map.
Shift+F9: Capture a grid around the NAV focus.
F10: Cancel the current capture. Tiles that are already captured will be kept.

OUTPUTS:
%USERPROFILE%\AppData\LocalLow\Boundless Dynamics, LLC\VTOLVR\NavMapExports

How to Stitch:
Stitching script requires Python and Pillow. Once you have python, you can install pillow in powershell with:

`py -m pip install Pillow`

Drag a folder from %USERPROFILE%\AppData\LocalLow\Boundless Dynamics, LLC\VTOLVR\NavMapExports over stitch_map.bat. Once the script finishes, you can find the stitched.png inside the NavMapExports folder that you dragged over the batch script.


