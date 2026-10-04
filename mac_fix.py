"""macOS fix: Ursina's shaders need '#version 130/140', which macOS's OpenGL
doesn't support in its default mode. On macOS we switch them off and let
Panda3D use its built-in (fixed-function) rendering instead.

Call fix_shaders() once, right after importing ursina and before Ursina().
Use make_sky() instead of Sky().
"""
import sys

ON_MAC = sys.platform == 'darwin'


TEXT_VERTEX = '''#version 120
uniform mat4 p3d_ModelViewProjectionMatrix;
attribute vec4 p3d_Vertex;
attribute vec2 p3d_MultiTexCoord0;
attribute vec4 p3d_Color;
varying vec2 uvs;
varying vec4 vertex_color;
void main() {
    gl_Position = p3d_ModelViewProjectionMatrix * p3d_Vertex;
    uvs = p3d_MultiTexCoord0;
    vertex_color = p3d_Color;
}
'''

TEXT_FRAGMENT = '''#version 120
uniform sampler2D p3d_Texture0;
uniform vec4 p3d_ColorScale;
varying vec2 uvs;
varying vec4 vertex_color;
void main() {
    vec4 c = vertex_color * p3d_ColorScale;
    gl_FragColor = vec4(c.rgb, c.a * texture2D(p3d_Texture0, uvs).a);
}
'''


PLAIN_VERTEX = '''#version 120
uniform mat4 p3d_ModelViewProjectionMatrix;
uniform vec2 texture_scale;
uniform vec2 texture_offset;
attribute vec4 p3d_Vertex;
attribute vec2 p3d_MultiTexCoord0;
attribute vec4 p3d_Color;
varying vec2 uvs;
varying vec4 vertex_color;
void main() {
    gl_Position = p3d_ModelViewProjectionMatrix * p3d_Vertex;
    uvs = p3d_MultiTexCoord0 * texture_scale + texture_offset;
    vertex_color = p3d_Color;
}
'''

PLAIN_FRAGMENT = '''#version 120
uniform sampler2D p3d_Texture0;
uniform vec4 p3d_ColorScale;
varying vec2 uvs;
varying vec4 vertex_color;
void main() {
    gl_FragColor = texture2D(p3d_Texture0, uvs) * p3d_ColorScale * vertex_color;
}
'''


def fix_shaders():
    if not ON_MAC:
        return
    from ursina import Entity, Vec2
    from ursina.shader import Shader
    # Everything gets a plain shader that macOS can compile (Ursina's own
    # 'unlit_shader' needs GLSL 1.30, which macOS doesn't offer here).
    Entity.default_shader = Shader(
        name='mac_plain_shader', language=Shader.GLSL,
        vertex=PLAIN_VERTEX, fragment=PLAIN_FRAGMENT,
        default_input={'texture_scale': Vec2(1, 1), 'texture_offset': Vec2(0, 0)},
    )

    # Text always uses a shader, so give it a simple one macOS can compile.
    text_module = sys.modules['ursina.text']
    text_module.text_shader = Shader(
        name='mac_text_shader', language=Shader.GLSL,
        vertex=TEXT_VERTEX, fragment=TEXT_FRAGMENT, default_input={},
    )


def make_sky():
    """Sky() hard-codes a shader that fails on macOS; there we use the plain
    window background color instead (set in main.py)."""
    if ON_MAC:
        return None
    from ursina import Sky
    return Sky()


def clear_leftover_shaders():
    """Call right after Ursina(): a few built-in entities still got a shader."""
    if not ON_MAC:
        return
    import gc
    from ursina import Entity
    for obj in gc.get_objects():
        if isinstance(obj, Entity) and obj.shader is not None and obj.shader.name == 'unlit_shader':
            obj.shader = Entity.default_shader


def fix_ui_scale():
    """Call every frame (from update()). On some setups Ursina leaves the UI
    camera at the wrong size, which makes the crosshair and text huge."""
    from ursina import camera, window
    wanted = (camera._ui_size * .5 * window.aspect_ratio, camera._ui_size * .5)
    film = camera.ui_lens.get_film_size()
    if abs(film[0] - wanted[0]) > 1e-3 or abs(film[1] - wanted[1]) > 1e-3:
        camera.ui_lens.set_film_size(*wanted)
