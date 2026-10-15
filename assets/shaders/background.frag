#version 330 core
// Fondo basado en la ilustración del launcher: el reflejo de la luna en el arroyo (según
// fire_mask.png) ondula y centellea, y caen hojas de arce; el resto de la imagen queda estable.
uniform vec2 uResolution;
uniform float uTime;
uniform vec4 uImgRect;     // x, y, w, h de la imagen en píxeles de pantalla
uniform float uIntensity;  // fundido de entrada 0..1
uniform sampler2D uBg;
uniform sampler2D uMask;
out vec4 fragColor;

vec3 sampleBg(vec2 uv, float lod) { return textureLod(uBg, uv, lod).rgb; }

void main()
{
  // Coordenadas de pantalla con origen arriba-izquierda (como la imagen).
  vec2 px = vec2(gl_FragCoord.x, uResolution.y - gl_FragCoord.y);
  vec2 uv = (px - uImgRect.xy) / uImgRect.zw;
  float T = uTime;

  // Fuera de la imagen (ventanas más anchas que 3:2): reflejo desenfocado y oscuro.
  if (uv.x > 1.0 || uv.y > 1.0 || uv.x < 0.0 || uv.y < 0.0)
  {
    vec2 m = vec2(1.0 - fract(uv.x), clamp(uv.y, 0.0, 1.0));
    vec3 c = sampleBg(m, 5.0) * 0.35;
    fragColor = vec4(c * uIntensity, 1.0);
    return;
  }

  // Agua: ondulación horizontal suave y centelleo del reflejo.
  float water = texture(uMask, uv).r;
  float waterWide = clamp(textureLod(uMask, uv, 3.0).r * 2.5, 0.0, 1.0);
  vec2 q = uv * vec2(1536.0, 1024.0);
  float w1 = sin(q.y * 0.55 + T * 2.1 + noise(vec2(q.x * 0.05, T * 0.6)) * 4.0);
  vec2 disp = vec2(w1 * 1.6, 0.0) / vec2(1536.0, 1024.0);
  vec3 col = sampleBg(uv + disp * waterWide, 0.0);
  float glint = noise(vec2(q.x * 0.12 + T * 0.8, q.y * 0.3 - T * 1.1));
  col *= mix(1.0, 0.85 + 0.45 * smoothstep(0.55, 0.9, glint), water);

  // Hojas de arce que caen con un leve vaivén.
  vec3 leaves = vec3(0.0);
  float leafA = 0.0;
  for (int layer = 0; layer < 3; layer++)
  {
    float fl = float(layer);
    float scale = 5.0 + fl * 4.0;
    vec2 ep = vec2(uv.x * 1.5, uv.y) * scale;
    ep.y -= T * (0.10 + fl * 0.05) * scale * 0.35;
    ep.x += sin(uv.y * 6.0 + T * (0.7 + fl * 0.2) + fl * 2.1) * 0.35 - T * 0.05 * scale * 0.35;
    vec2 cell = floor(ep);
    vec2 f = fract(ep);
    vec2 rnd = hash22(cell + fl * 37.0);
    if (rnd.x > 0.07)
      continue;
    vec2 c = 0.25 + 0.5 * hash22(cell * 1.3 + 9.0);
    float ang = T * (0.8 + rnd.y * 1.5) + rnd.x * 30.0;
    vec2 d = f - c;
    d = mat2(cos(ang), -sin(ang), sin(ang), cos(ang)) * d;
    float size = 0.07 + 0.06 * rnd.y;
    // hoja: elipse con cinco lóbulos
    float a = atan(d.y, d.x);
    float r = length(d * vec2(1.0, 1.0 + 0.6 * sin(ang * 0.7)));
    float lobes = size * (0.75 + 0.25 * cos(a * 5.0));
    float m = smoothstep(lobes, lobes * 0.7, r) * (0.45 + fl * 0.15);
    leaves += vec3(0.62, 0.06 + 0.05 * rnd.y, 0.04) * m;
    leafA = max(leafA, m);
  }
  col = mix(col, leaves / max(leafA, 1e-3), leafA * 0.85);

  fragColor = vec4(col * uIntensity, 1.0);
}
