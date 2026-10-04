#version 330

uniform mat4 p3d_ModelViewProjectionMatrix;
uniform mat4 p3d_ModelMatrix;
uniform mat4 shadow_mvp;
uniform vec4 p3d_ColorScale;

in vec4 p3d_Vertex;
in vec3 p3d_Normal;
in vec4 p3d_Color;

out vec3 world_normal;
out vec4 base_color;
out vec4 shadow_position;

void main() {
    vec4 world_position = p3d_ModelMatrix * p3d_Vertex;
    world_normal = normalize(transpose(inverse(mat3(p3d_ModelMatrix))) * p3d_Normal);
    base_color = p3d_Color * p3d_ColorScale;
    shadow_position = shadow_mvp * world_position;
    gl_Position = p3d_ModelViewProjectionMatrix * p3d_Vertex;
}
