#version 330

uniform sampler2D shadow_map;
uniform vec3 light_direction;

in vec3 world_normal;
in vec4 base_color;
in vec4 shadow_position;

out vec4 fragment_color;

void main() {
    vec3 normal = normalize(world_normal);
    vec3 light = normalize(light_direction);
    float diffuse = max(dot(normal, light), 0.0);
    vec3 shadow_coord = shadow_position.xyz / shadow_position.w * 0.5 + 0.5;
    float shadow = 0.0;

    if (
        shadow_coord.x >= 0.0 && shadow_coord.x <= 1.0 &&
        shadow_coord.y >= 0.0 && shadow_coord.y <= 1.0 &&
        shadow_coord.z >= 0.0 && shadow_coord.z <= 1.0
    ) {
        float bias = max(0.003 * (1.0 - dot(normal, light)), 0.0005);
        vec2 texel = 1.0 / vec2(textureSize(shadow_map, 0));
        for (int x = -1; x <= 1; ++x) {
            for (int y = -1; y <= 1; ++y) {
                float closest = texture(shadow_map, shadow_coord.xy + vec2(x, y) * texel).r;
                shadow += shadow_coord.z - bias > closest ? 1.0 : 0.0;
            }
        }
        shadow /= 9.0;
    }

    vec3 illumination = vec3(0.3) + vec3(0.85, 0.78, 0.68) * diffuse * (1.0 - shadow);
    fragment_color = vec4(base_color.rgb * illumination, base_color.a);
}
