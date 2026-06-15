# Screenshot Skill

## Description
Captures screen content using Pillow ImageGrab and returns PNG bytes or saves to file.

## Parameters
- region (tuple, optional): Tuple (left, top, right, bottom) for region capture. If not specified, captures full screen.
- path (str, required): File path to save screenshot (for save method)

## Output
- capture(): Returns PNG bytes
- save(): Returns path where screenshot was saved

## Dependencies
- Pillow>=10.0.0

## Hardware
Requires display (not headless). Raises SkillExecutionError if display unavailable.

## Tags
screenshot, screen-capture, image, desktop
