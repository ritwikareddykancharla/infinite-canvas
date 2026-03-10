/**
 * WebGL transition engine for seamless genre crossfades.
 * Uses a dissolve shader that blends between video textures.
 */

const VERTEX_SHADER = `
  attribute vec2 a_position;
  attribute vec2 a_texCoord;
  varying vec2 v_texCoord;
  void main() {
    gl_Position = vec4(a_position, 0.0, 1.0);
    v_texCoord = a_texCoord;
  }
`;

const FRAGMENT_SHADER = `
  precision mediump float;
  uniform sampler2D u_from;
  uniform sampler2D u_to;
  uniform float u_progress;
  uniform int u_transitionType;
  varying vec2 v_texCoord;

  // Crossfade
  vec4 crossfade(vec4 from, vec4 to, float p) {
    return mix(from, to, p);
  }

  // Directional wipe
  vec4 wipe(vec4 from, vec4 to, float p, vec2 uv) {
    return uv.x < p ? to : from;
  }

  // Glitch dissolve
  vec4 glitch(vec4 from, vec4 to, float p, vec2 uv) {
    float noise = fract(sin(dot(uv, vec2(12.9898, 78.233)) + p) * 43758.5453);
    return noise < p ? to : from;
  }

  // Radial reveal
  vec4 radial(vec4 from, vec4 to, float p, vec2 uv) {
    vec2 center = vec2(0.5, 0.5);
    float dist = distance(uv, center);
    return dist < p * 0.707 ? to : from;
  }

  void main() {
    vec4 fromColor = texture2D(u_from, v_texCoord);
    vec4 toColor = texture2D(u_to, v_texCoord);

    if (u_transitionType == 0) {
      gl_FragColor = crossfade(fromColor, toColor, u_progress);
    } else if (u_transitionType == 1) {
      gl_FragColor = wipe(fromColor, toColor, u_progress, v_texCoord);
    } else if (u_transitionType == 2) {
      gl_FragColor = glitch(fromColor, toColor, u_progress, v_texCoord);
    } else {
      gl_FragColor = radial(fromColor, toColor, u_progress, v_texCoord);
    }
  }
`;

// Transition type per genre switch
const GENRE_TRANSITIONS = {
  'noir->romcom': 0,
  'romcom->noir': 0,
  'noir->horror': 2,
  'horror->noir': 2,
  'noir->scifi': 3,
  'scifi->noir': 3,
  'romcom->horror': 2,
  'horror->romcom': 0,
  'romcom->scifi': 1,
  'scifi->romcom': 1,
  'horror->scifi': 3,
  'scifi->horror': 2,
};

export class WebGLTransitionEngine {
  constructor(canvas) {
    this.canvas = canvas;
    this.gl = canvas.getContext('webgl') || canvas.getContext('experimental-webgl');
    this.program = null;
    this.fromTexture = null;
    this.toTexture = null;
    this.animFrame = null;
    this._init();
  }

  _init() {
    const gl = this.gl;
    if (!gl) return;

    const vs = this._compileShader(gl.VERTEX_SHADER, VERTEX_SHADER);
    const fs = this._compileShader(gl.FRAGMENT_SHADER, FRAGMENT_SHADER);
    this.program = this._linkProgram(vs, fs);

    // Full-screen quad
    const positions = new Float32Array([-1, -1, 1, -1, -1, 1, 1, 1]);
    const texCoords = new Float32Array([0, 1, 1, 1, 0, 0, 1, 0]);

    const posBuf = gl.createBuffer();
    gl.bindBuffer(gl.ARRAY_BUFFER, posBuf);
    gl.bufferData(gl.ARRAY_BUFFER, positions, gl.STATIC_DRAW);
    const posLoc = gl.getAttribLocation(this.program, 'a_position');
    gl.enableVertexAttribArray(posLoc);
    gl.vertexAttribPointer(posLoc, 2, gl.FLOAT, false, 0, 0);

    const texBuf = gl.createBuffer();
    gl.bindBuffer(gl.ARRAY_BUFFER, texBuf);
    gl.bufferData(gl.ARRAY_BUFFER, texCoords, gl.STATIC_DRAW);
    const texLoc = gl.getAttribLocation(this.program, 'a_texCoord');
    gl.enableVertexAttribArray(texLoc);
    gl.vertexAttribPointer(texLoc, 2, gl.FLOAT, false, 0, 0);

    gl.useProgram(this.program);
    gl.uniform1i(gl.getUniformLocation(this.program, 'u_from'), 0);
    gl.uniform1i(gl.getUniformLocation(this.program, 'u_to'), 1);
  }

  _compileShader(type, source) {
    const gl = this.gl;
    const shader = gl.createShader(type);
    gl.shaderSource(shader, source);
    gl.compileShader(shader);
    return shader;
  }

  _linkProgram(vs, fs) {
    const gl = this.gl;
    const program = gl.createProgram();
    gl.attachShader(program, vs);
    gl.attachShader(program, fs);
    gl.linkProgram(program);
    return program;
  }

  uploadVideoTexture(unit, videoElement) {
    const gl = this.gl;
    const texture = gl.createTexture();
    gl.activeTexture(unit === 0 ? gl.TEXTURE0 : gl.TEXTURE1);
    gl.bindTexture(gl.TEXTURE_2D, texture);
    gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_WRAP_S, gl.CLAMP_TO_EDGE);
    gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_WRAP_T, gl.CLAMP_TO_EDGE);
    gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_MIN_FILTER, gl.LINEAR);
    gl.texImage2D(gl.TEXTURE_2D, 0, gl.RGBA, gl.RGBA, gl.UNSIGNED_BYTE, videoElement);
    return texture;
  }

  transition(fromVideo, toVideo, fromGenre, toGenre, durationMs = 800) {
    if (!this.gl) return Promise.resolve();
    if (this.animFrame) cancelAnimationFrame(this.animFrame);

    const key = `${fromGenre}->${toGenre}`;
    const transitionType = GENRE_TRANSITIONS[key] ?? 0;
    const gl = this.gl;
    const startTime = performance.now();

    return new Promise((resolve) => {
      const animate = (now) => {
        const elapsed = now - startTime;
        const progress = Math.min(elapsed / durationMs, 1);

        this.uploadVideoTexture(0, fromVideo);
        this.uploadVideoTexture(1, toVideo);

        gl.useProgram(this.program);
        gl.uniform1f(gl.getUniformLocation(this.program, 'u_progress'), progress);
        gl.uniform1i(gl.getUniformLocation(this.program, 'u_transitionType'), transitionType);
        gl.drawArrays(gl.TRIANGLE_STRIP, 0, 4);

        if (progress < 1) {
          this.animFrame = requestAnimationFrame(animate);
        } else {
          resolve();
        }
      };
      this.animFrame = requestAnimationFrame(animate);
    });
  }

  drawFrame(videoElement) {
    if (!this.gl) return;
    const gl = this.gl;
    this.uploadVideoTexture(0, videoElement);
    this.uploadVideoTexture(1, videoElement);
    gl.useProgram(this.program);
    gl.uniform1f(gl.getUniformLocation(this.program, 'u_progress'), 1.0);
    gl.uniform1i(gl.getUniformLocation(this.program, 'u_transitionType'), 0);
    gl.drawArrays(gl.TRIANGLE_STRIP, 0, 4);
  }

  destroy() {
    if (this.animFrame) cancelAnimationFrame(this.animFrame);
  }
}
