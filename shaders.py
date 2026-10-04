"""The shaders that draw blocks and creatures. Written in GLSL 1.20 so they also compile on macOS.

Light works like Minecraft: every block face has a SKY light (sunlight, fades at night) and a
BLOCK light (torches and glowing blocks, always on). The brighter of the two decides how bright
the face is. Faces also get a fixed shade by direction: tops brightest, undersides darkest.

Values the game sets for the whole scene each frame (see sky.py):
    daylight    0 at night to 1 at noon
    fog_color   the color of the sky, which far-away land fades into
    fog_range   fog starts at x and hides everything at y"""
from ursina import Vec2
from ursina.shader import Shader

_FOG_AND_LIGHT = '''
uniform vec4 fog_color;
uniform vec2 fog_range;
uniform float daylight;
uniform float ambient;
float brightness(float sky, float block) {
    float level = max(sky * daylight, block);
    return ambient + (1.0 - ambient) * pow(clamp(level, 0.0, 1.0), 1.4);
}
vec3 with_fog(vec3 color, float distance_to_camera) {
    float clear = clamp((fog_range.y - distance_to_camera) / (fog_range.y - fog_range.x), 0.0, 1.0);
    return mix(fog_color.rgb, color, clear);
}
'''

_FACE_SHADE = '''
float face_shade(vec3 normal) {
    if (normal.y > 0.5) return 1.0;           // top faces are brightest
    if (normal.y < -0.5) return 0.5;          // undersides darkest
    if (abs(normal.x) > 0.5) return 0.8;
    return 0.65;
}
'''

# Blocks: the light of each face is baked into the vertex color (red = sky light, green = block light)
block_shader = Shader(
    name='block_shader', language=Shader.GLSL,
    vertex='''#version 120
uniform mat4 p3d_ModelViewProjectionMatrix;
uniform mat4 p3d_ModelViewMatrix;
attribute vec4 p3d_Vertex;
attribute vec3 p3d_Normal;
attribute vec4 p3d_Color;
attribute vec2 p3d_MultiTexCoord0;
varying vec2 uvs;
varying vec3 normal;
varying vec2 light;
varying float distance_to_camera;
void main() {
    gl_Position = p3d_ModelViewProjectionMatrix * p3d_Vertex;
    distance_to_camera = length((p3d_ModelViewMatrix * p3d_Vertex).xyz);
    uvs = p3d_MultiTexCoord0;
    normal = p3d_Normal;
    light = p3d_Color.rg;
}
''',
    fragment='''#version 120
uniform sampler2D p3d_Texture0;
uniform vec4 p3d_ColorScale;
varying vec2 uvs;
varying vec3 normal;
varying vec2 light;
varying float distance_to_camera;
''' + _FOG_AND_LIGHT + _FACE_SHADE + '''
void main() {
    vec4 tex = texture2D(p3d_Texture0, uvs);
    if (tex.a < 0.5) discard;   // see-through parts, like leaves
    vec4 lit = vec4(tex.rgb * face_shade(normal) * brightness(light.r, light.g), 1.0) * p3d_ColorScale;
    gl_FragColor = vec4(with_fog(lit.rgb, distance_to_camera), lit.a);
}
''',
    default_input={},
)

# Creatures, items and crumbs: one light value for the whole object (set per object as `entity_light`)
entity_shader = Shader(
    name='entity_shader', language=Shader.GLSL,
    vertex='''#version 120
uniform mat4 p3d_ModelViewProjectionMatrix;
uniform mat4 p3d_ModelViewMatrix;
attribute vec4 p3d_Vertex;
attribute vec3 p3d_Normal;
attribute vec2 p3d_MultiTexCoord0;
varying vec2 uvs;
varying vec3 normal;
varying float distance_to_camera;
void main() {
    gl_Position = p3d_ModelViewProjectionMatrix * p3d_Vertex;
    distance_to_camera = length((p3d_ModelViewMatrix * p3d_Vertex).xyz);
    uvs = p3d_MultiTexCoord0;
    normal = p3d_Normal;
}
''',
    fragment='''#version 120
uniform sampler2D p3d_Texture0;
uniform vec4 p3d_ColorScale;
uniform vec2 entity_light;       // x = sky light, y = block light (each 0 to 1)
varying vec2 uvs;
varying vec3 normal;
varying float distance_to_camera;
''' + _FOG_AND_LIGHT + _FACE_SHADE + '''
void main() {
    vec4 tex = texture2D(p3d_Texture0, uvs);
    if (tex.a < 0.5) discard;
    vec4 lit = vec4(tex.rgb * face_shade(normal) * brightness(entity_light.x, entity_light.y), 1.0) * p3d_ColorScale;
    gl_FragColor = vec4(with_fog(lit.rgb, distance_to_camera), lit.a);
}
''',
    default_input={'entity_light': Vec2(1, 0)},
)
