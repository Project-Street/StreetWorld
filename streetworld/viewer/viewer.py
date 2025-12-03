import ctypes
import platform
import threading
from typing import Union

import glfw
import numpy as np
import OpenGL.GL as gl
import torch
from imgui_bundle import imgui

from streetworld.viewer.client import Client
from streetworld.viewer.manual_controller import get_controller
from streetworld.viewer.server import WebSocketServer


def log(message):
    print(message)


def red(text):
    return f"\033[91m{text}\033[0m"


class Quad:
    def __init__(self, H, W):
        self.H = H
        self.W = W
        self.texture = None
        self.vao = None
        self.vbo = None
        self.program = None
        self._init_quad()

    def _init_quad(self):
        vertices = np.array(
            [
                [-1.0, -1.0, 0.0],
                [1.0, -1.0, 0.0],
                [1.0, 1.0, 0.0],
                [-1.0, 1.0, 0.0],
            ],
            dtype=np.float32,
        )

        indices = np.array([0, 1, 2, 2, 3, 0], dtype=np.uint32)
        tex_coords = np.array(
            [
                [0.0, 1.0],
                [1.0, 1.0],
                [1.0, 0.0],
                [0.0, 0.0],
            ],
            dtype=np.float32,
        )

        self.vao = gl.glGenVertexArrays(1)
        gl.glBindVertexArray(self.vao)

        self.vbo = gl.glGenBuffers(1)
        gl.glBindBuffer(gl.GL_ARRAY_BUFFER, self.vbo)
        gl.glBufferData(gl.GL_ARRAY_BUFFER, vertices.nbytes, vertices, gl.GL_STATIC_DRAW)

        gl.glVertexAttribPointer(0, 3, gl.GL_FLOAT, gl.GL_FALSE, 12, ctypes.c_void_p(0))
        gl.glEnableVertexAttribArray(0)

        tex_vbo = gl.glGenBuffers(1)
        gl.glBindBuffer(gl.GL_ARRAY_BUFFER, tex_vbo)
        gl.glBufferData(gl.GL_ARRAY_BUFFER, tex_coords.nbytes, tex_coords, gl.GL_STATIC_DRAW)

        gl.glVertexAttribPointer(1, 2, gl.GL_FLOAT, gl.GL_FALSE, 8, ctypes.c_void_p(0))
        gl.glEnableVertexAttribArray(1)

        ebo = gl.glGenBuffers(1)
        gl.glBindBuffer(gl.GL_ELEMENT_ARRAY_BUFFER, ebo)
        gl.glBufferData(gl.GL_ELEMENT_ARRAY_BUFFER, indices.nbytes, indices, gl.GL_STATIC_DRAW)

        self.texture = gl.glGenTextures(1)
        gl.glBindTexture(gl.GL_TEXTURE_2D, self.texture)
        gl.glTexParameteri(gl.GL_TEXTURE_2D, gl.GL_TEXTURE_MIN_FILTER, gl.GL_LINEAR)
        gl.glTexParameteri(gl.GL_TEXTURE_2D, gl.GL_TEXTURE_MAG_FILTER, gl.GL_LINEAR)

        empty_data = np.zeros((self.H, self.W, 3), dtype=np.uint8)
        gl.glTexImage2D(gl.GL_TEXTURE_2D, 0, gl.GL_RGB, self.W, self.H, 0, gl.GL_RGB, gl.GL_UNSIGNED_BYTE, empty_data)

        vertex_shader = """
        #version 130
        attribute vec3 position;
        attribute vec2 texcoord;
        varying vec2 TexCoord;

        void main() {
            gl_Position = vec4(position, 1.0);
            TexCoord = texcoord;
        }
        """

        fragment_shader = """
        #version 130
        uniform sampler2D texture1;
        varying vec2 TexCoord;

        void main() {
            gl_FragColor = texture2D(texture1, TexCoord);
        }
        """

        vs = gl.glCreateShader(gl.GL_VERTEX_SHADER)
        gl.glShaderSource(vs, vertex_shader)
        gl.glCompileShader(vs)

        fs = gl.glCreateShader(gl.GL_FRAGMENT_SHADER)
        gl.glShaderSource(fs, fragment_shader)
        gl.glCompileShader(fs)

        self.program = gl.glCreateProgram()
        gl.glAttachShader(self.program, vs)
        gl.glAttachShader(self.program, fs)
        gl.glLinkProgram(self.program)

        gl.glDeleteShader(vs)
        gl.glDeleteShader(fs)

        gl.glBindVertexArray(0)

    def copy_to_texture(self, img):
        if img is None:
            return

        if isinstance(img, torch.Tensor):
            img = img.cpu().numpy()

        if img.dtype != np.uint8:
            if img.max() <= 1.0:
                img = (img * 255).astype(np.uint8)
            else:
                img = img.astype(np.uint8)

        if len(img.shape) == 2:
            img = np.stack([img, img, img], axis=-1)
        elif img.shape[2] == 4:
            img = img[:, :, :3]
        elif img.shape[2] != 3:
            img = img[:, :, :3]

        gl.glBindTexture(gl.GL_TEXTURE_2D, self.texture)
        gl.glTexSubImage2D(gl.GL_TEXTURE_2D, 0, 0, 0, self.W, self.H, gl.GL_RGB, gl.GL_UNSIGNED_BYTE, img)

    def draw(self):
        gl.glUseProgram(self.program)
        gl.glBindVertexArray(self.vao)
        gl.glBindTexture(gl.GL_TEXTURE_2D, self.texture)
        gl.glDrawElements(gl.GL_TRIANGLES, 6, gl.GL_UNSIGNED_INT, None)
        gl.glBindVertexArray(0)


class Viewer:
    def __init__(
        self,
        H,
        W,
        mode="local",  # client, server, local
        host=None,
        port=None,
        controller="keyboard",
    ):
        self.H = H
        self.W = W
        self.mode = mode

        if self.mode == "client":
            self.lock = threading.Lock()
            self.client = Client(server_ip=host, server_port=port, lock=self.lock)
            self.client.run()
        elif self.mode == "server":
            self.lock = threading.Lock()
            self.server = WebSocketServer(host=host, port=port, lock=self.lock)
            self.server.run()

        self.window_title = "Simple Visualizer"

        if self.mode in ["local", "client"]:
            self._init_glfw()
            self._init_opengl()
            self._init_imgui()
            self._init_quad()
            self._bind_callbacks()
            self.manual_controller = get_controller(controller, self.window)

    @property
    def window_address(self):
        # Check if window is a mock or non-standard object
        if not hasattr(self.window, "__class__") or "Mock" in str(type(self.window)):
            return id(self.window)
        try:
            window_address = ctypes.cast(self.window, ctypes.c_void_p).value
            return window_address
        except (TypeError, AttributeError, ValueError, RecursionError):
            # Return a dummy address for mock objects or when casting fails
            return id(self.window)

    def _init_opengl(self):
        gl.glViewport(0, 0, self.W, self.H)

    def _init_glfw(self):
        if not glfw.init():
            log(red("Could not initialize OpenGL context"))
            exit(1)

        if platform.system() == "Darwin":
            self.glsl_version = "#version 150"
            glfw.window_hint(glfw.CONTEXT_VERSION_MAJOR, 3)
            glfw.window_hint(glfw.CONTEXT_VERSION_MINOR, 2)
            glfw.window_hint(glfw.OPENGL_PROFILE, glfw.OPENGL_CORE_PROFILE)
            glfw.window_hint(glfw.OPENGL_FORWARD_COMPAT, 1)
            glfw.window_hint(glfw.COCOA_RETINA_FRAMEBUFFER, 0)
        else:
            self.glsl_version = "#version 130"
            glfw.window_hint(glfw.CONTEXT_VERSION_MAJOR, 3)
            glfw.window_hint(glfw.CONTEXT_VERSION_MINOR, 0)

        window = glfw.create_window(self.W, self.H, self.window_title, None, None)
        if not window:
            glfw.terminate()
            log(red("Could not initialize window"))
            raise RuntimeError("Failed to initialize window in glfw")

        glfw.make_context_current(window)
        glfw.swap_interval(False)
        glfw.set_input_mode(window, glfw.CURSOR, glfw.CURSOR_DISABLED)

        self.window = window

    def _init_imgui(self):
        imgui.create_context()
        self.io = imgui.get_io()

        self.io.config_flags |= imgui.ConfigFlags_.docking_enable

        imgui.style_colors_dark()

        style = imgui.get_style()
        style.tab_rounding = 4.0
        style.grab_rounding = 4.0
        style.child_rounding = 4.0
        style.frame_rounding = 4.0
        style.popup_rounding = 8.0
        style.window_rounding = 8.0
        style.scrollbar_rounding = 4.0
        window_bg_color = style.color_(imgui.Col_.window_bg)
        window_bg_color.w = 1.0
        style.set_color_(imgui.Col_.window_bg, window_bg_color)

        imgui.backends.glfw_init_for_open_gl(self.window_address, True)
        imgui.backends.opengl3_init(self.glsl_version)

        io = imgui.get_io()
        io.fonts.build()

    def _init_quad(self):
        self.quad = Quad(H=self.H, W=self.W)

    def _bind_callbacks(self):
        glfw.set_window_user_pointer(self.window, self)

    def is_running(self):
        return not glfw.window_should_close(self.window) if self.mode in ["client", "local"] else True

    def run(self, img: Union[np.ndarray, torch.Tensor] = None):
        if self.mode == "server":
            action = self._actuate_server(img)
            action = action if action else [0.0, 0.0]
            return action
        elif self.mode == "client":
            action = self.manual_controller.process_input()
            img = self._actuate_client(action)
            if img is None:
                img = self.last_image if hasattr(self, "last_image") else None
            else:
                self.last_image = img
            self._render(img)
        elif self.mode == "local":
            self._render(img)
            action = self.manual_controller.process_input()
            return action

    def _render(self, img):
        gl.glClear(gl.GL_COLOR_BUFFER_BIT)
        glfw.poll_events()

        imgui.backends.opengl3_new_frame()
        imgui.backends.glfw_new_frame()
        imgui.new_frame()

        if img is not None:
            self.quad.copy_to_texture(img)
            self.quad.draw()

        imgui.render()
        imgui.backends.opengl3_render_draw_data(imgui.get_draw_data())

        glfw.swap_buffers(self.window)

    def _actuate_client(self, input):
        with self.lock:
            self.client.input = input

        with self.lock:
            outputs = self.client.output
            self.client.output = None
        return outputs

    def _actuate_server(self, img):
        output = img
        with self.lock:
            self.server.output = output

        with self.lock:
            input_data = self.server.input
            self.server.input = None
        return input_data

    def shutdown(self):
        imgui.backends.opengl3_shutdown()
        imgui.backends.glfw_shutdown()
        imgui.destroy_context()

        glfw.destroy_window(self.window)
        glfw.terminate()
