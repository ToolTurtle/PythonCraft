Put mod files (*.py) here and PythonCraft loads them when it starts.
A mod file is a normal pycraft program without the runplot line:

    import pycraft as pc
    m = pc.mod('mine')
    m.addblock('snad', 'snad.png', like='sand')     # snad.png sits next to this file

See docs/README_mods.md and examples/mod_example/.
