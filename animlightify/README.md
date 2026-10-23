# Animlightify
With NewDark 1.29, a new variant of the engine (HWTL) was released featuring dynamic shadows and volumetric fog, among other modern lighting techniques. However, these new features only affect animlights and dynamic lights, so, to take full advantage, missions with brush lights and static lights must be converted to animlights and relit, which is what Animlightify will perform automatically. It will also detect whether brush lights and hack lights are near windows, since those that are will be processed differently.

## Prerequisites
You need Python 3.10+ installed.

## How does it work?
Animlightify takes a single argument, which is the mission file that you wish to process. When it finishes, it will output two files: `animlight.dml` and `animlight.cmd`. Via `animlight.dml`, objects with light properties will gain animlight properties and have their original light properties removed. New objects with animlight properties will be created for each brush light. `animlight.cmd` is responsible for removing all (now redundant) brush lights and automatically relighting the level. Inside Dromed, load the mission and type into the commandline box: `run <path-to-animlight.cmd>`. You must not put the path inside quotes, even if it contains spaces. Press `enter` and Dromed will do the real processing. When it finishes, save the mission to some other location (unless you want the changes to be permanent).

### Important
* For all cases, `gamesys.dml` must be in a directory specified in `mod_path`
inside `cam_mod.ini`. It doesn't necessarily need to reside in the same directory as the modified mission. I'd recommend adding the directory you cloned this repo to, to `mod_path`. Included with the HWTL variant is a mod (`MODS\hwtl`) that sets some HwtlLight parameters for certain abstract light objects. This should be added to `mod_path` as the 1st entry (highest priority).
    * For OMs, the modified mission must be in a directory specified in `mod_path` inside `cam_mod.ini`.
    * For FMs, I'm currently unsure what the proper course of action is, since the mod load order is different when an FM is loaded. Modifying `uber_mod_path` caused me tons of problems, so I'd recommend overwriting the FM. You can always reinstall the FM if you wish to revert it back to its unmodified form.

Okay, here's a visual example of how `mod_path` should look be laid out:
```
mod_path .\MODS\hwtl+<this-directory>+<modified-mission-directory>+<whatever-other-mods-you-have ...>
```
And, of course, the vars between the carets should be replaced with actual paths, so here's my actual `mod_path`:
```
mod_path .\MODS\hwtl+C:\prj\tagfile\animlightify+.\MODS\Thief2 Fixed HWTL+.\MODS\Thief2 Fixed+.\MODS\T2FMDML+.\patch_ext
```
Where `C:\prj\tagfile\animlightify` is where this repo is (which contains `gamesys.dml`) and `.\MODS\Thief2 Fixed HWTL` is where I saved the modified OMs.

### Window light detection (and its limitations)
Right, I guess I'll explain how this detection works. But first, I should justify its existence in the first place. Basically, there is a file included with this project called `gamesys.dml` that sets some default behavior for HTWL lights. All hack lights and (former) brush lights have their volumetric property set to 0, since they look extremely awkward just floating around in the air as spheres or cones. However, when they are placed near windows, the volumetric effect actually looks pleasant. Because of this, determining whether those lights are near a window becomes important. If a brush face's texture is derived from GlassTex, it's considered a window. There are two boundary checks: First, an outer box intersection test around the brush's origin, to eliminate lights that are too far away from the face in question. Second, an inner box intersection test around each GlassTex face, in which an intersecting light will be considered a window light, and thus have its volumetric effect applied in `animlightify.dml`.

As for limitations:
* If a light is near a GlassTex face which isn't rendered, the algorithm won't care and will consider it a window light anyway. This will cause the awkward floating volumetric spheres and cones, as previously described, but the vast majority of such instances should be eliminated.
* Only cube brush primitives are handled. It's possible to handle the other shapes, but I ran out of steam.
* Sometimes, textures featuring a window aren't descended from GlassTex. Lights near those textures won't be considered window lights.

## Caveats
This might fail if missions are pushing up against the object limit, since new objects will be created for every brush light.

## Bugs
Report these in the issue tracker, or submit a pull request if you wish to fix them yourself.
