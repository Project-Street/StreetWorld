import unittest
from unittest.mock import MagicMock, patch

import numpy as np
import torch


class TestQuad(unittest.TestCase):
    """Test the Quad class"""

    def setUp(self):
        self.mock_gl = MagicMock()
        self.mock_ctypes = MagicMock()

    @patch("streetworld.viewer.viewer.gl")
    def test_quad_initialization(self, mock_gl):
        """Test Quad class initialization"""
        mock_gl.glGenVertexArrays.return_value = 1
        mock_gl.glGenBuffers.side_effect = [2, 3, 4]
        mock_gl.glGenTextures.return_value = 5
        mock_gl.glCreateShader.side_effect = [6, 7]
        mock_gl.glCreateProgram.return_value = 8

        from streetworld.viewer.viewer import Quad

        quad = Quad(H=480, W=640)

        self.assertEqual(quad.H, 480)
        self.assertEqual(quad.W, 640)
        self.assertIsNotNone(quad.vao)
        self.assertIsNotNone(quad.vbo)
        self.assertIsNotNone(quad.texture)
        self.assertIsNotNone(quad.program)

    @patch("streetworld.viewer.viewer.gl")
    def test_quad_copy_to_texture_numpy_uint8(self, mock_gl):
        """Test copy_to_texture with uint8 numpy array"""
        mock_gl.glGenVertexArrays.return_value = 1
        mock_gl.glGenBuffers.side_effect = [2, 3, 4]
        mock_gl.glGenTextures.return_value = 5
        mock_gl.glCreateShader.side_effect = [6, 7]
        mock_gl.glCreateProgram.return_value = 8

        from streetworld.viewer.viewer import Quad

        quad = Quad(H=480, W=640)

        img = np.random.randint(0, 256, (480, 640, 3), dtype=np.uint8)
        quad.copy_to_texture(img)

        mock_gl.glTexSubImage2D.assert_called()

    @patch("streetworld.viewer.viewer.gl")
    def test_quad_copy_to_texture_numpy_float32(self, mock_gl):
        """Test copy_to_texture with float32 numpy array (0-1 range)"""
        mock_gl.glGenVertexArrays.return_value = 1
        mock_gl.glGenBuffers.side_effect = [2, 3, 4]
        mock_gl.glGenTextures.return_value = 5
        mock_gl.glCreateShader.side_effect = [6, 7]
        mock_gl.glCreateProgram.return_value = 8

        from streetworld.viewer.viewer import Quad

        quad = Quad(H=480, W=640)

        img = np.random.rand(480, 640, 3).astype(np.float32)
        quad.copy_to_texture(img)

        mock_gl.glTexSubImage2D.assert_called()

    @patch("streetworld.viewer.viewer.gl")
    def test_quad_copy_to_texture_torch_tensor(self, mock_gl):
        """Test copy_to_texture with torch tensor"""
        mock_gl.glGenVertexArrays.return_value = 1
        mock_gl.glGenBuffers.side_effect = [2, 3, 4]
        mock_gl.glGenTextures.return_value = 5
        mock_gl.glCreateShader.side_effect = [6, 7]
        mock_gl.glCreateProgram.return_value = 8

        from streetworld.viewer.viewer import Quad

        quad = Quad(H=480, W=640)

        img = torch.randint(0, 256, (480, 640, 3), dtype=torch.uint8)
        quad.copy_to_texture(img)

        mock_gl.glTexSubImage2D.assert_called()

    @patch("streetworld.viewer.viewer.gl")
    def test_quad_copy_to_texture_grayscale(self, mock_gl):
        """Test copy_to_texture with grayscale image"""
        mock_gl.glGenVertexArrays.return_value = 1
        mock_gl.glGenBuffers.side_effect = [2, 3, 4]
        mock_gl.glGenTextures.return_value = 5
        mock_gl.glCreateShader.side_effect = [6, 7]
        mock_gl.glCreateProgram.return_value = 8

        from streetworld.viewer.viewer import Quad

        quad = Quad(H=480, W=640)

        img = np.random.randint(0, 256, (480, 640), dtype=np.uint8)
        quad.copy_to_texture(img)

        mock_gl.glTexSubImage2D.assert_called()

    @patch("streetworld.viewer.viewer.gl")
    def test_quad_copy_to_texture_rgba(self, mock_gl):
        """Test copy_to_texture with RGBA image (should convert to RGB)"""
        mock_gl.glGenVertexArrays.return_value = 1
        mock_gl.glGenBuffers.side_effect = [2, 3, 4]
        mock_gl.glGenTextures.return_value = 5
        mock_gl.glCreateShader.side_effect = [6, 7]
        mock_gl.glCreateProgram.return_value = 8

        from streetworld.viewer.viewer import Quad

        quad = Quad(H=480, W=640)

        img = np.random.randint(0, 256, (480, 640, 4), dtype=np.uint8)
        quad.copy_to_texture(img)

        mock_gl.glTexSubImage2D.assert_called()

    @patch("streetworld.viewer.viewer.gl")
    def test_quad_copy_to_texture_none(self, mock_gl):
        """Test copy_to_texture with None input"""
        mock_gl.glGenVertexArrays.return_value = 1
        mock_gl.glGenBuffers.side_effect = [2, 3, 4]
        mock_gl.glGenTextures.return_value = 5
        mock_gl.glCreateShader.side_effect = [6, 7]
        mock_gl.glCreateProgram.return_value = 8

        from streetworld.viewer.viewer import Quad

        quad = Quad(H=480, W=640)
        quad.copy_to_texture(None)

        mock_gl.glTexSubImage2D.assert_not_called()

    @patch("streetworld.viewer.viewer.gl")
    def test_quad_draw(self, mock_gl):
        """Test Quad draw method"""
        mock_gl.glGenVertexArrays.return_value = 1
        mock_gl.glGenBuffers.side_effect = [2, 3, 4]
        mock_gl.glGenTextures.return_value = 5
        mock_gl.glCreateShader.side_effect = [6, 7]
        mock_gl.glCreateProgram.return_value = 8

        from streetworld.viewer.viewer import Quad

        quad = Quad(H=480, W=640)
        quad.draw()

        mock_gl.glUseProgram.assert_called()
        mock_gl.glBindVertexArray.assert_called()
        mock_gl.glBindTexture.assert_called()
        mock_gl.glDrawElements.assert_called()


class TestViewer(unittest.TestCase):
    """Test the Viewer class"""

    @patch("streetworld.viewer.viewer.glfw")
    @patch("streetworld.viewer.viewer.gl")
    @patch("streetworld.viewer.viewer.imgui")
    @patch("streetworld.viewer.viewer.Client")
    @patch("streetworld.viewer.viewer.get_controller")
    def test_viewer_local_mode_initialization(self, mock_controller, mock_client, mock_imgui, mock_gl, mock_glfw):
        """Test Viewer initialization in local mode"""
        mock_glfw.init.return_value = True
        mock_glfw.create_window.return_value = MagicMock()
        mock_imgui.get_io.return_value = MagicMock()
        mock_imgui.get_style.return_value = MagicMock()
        mock_gl.glGenVertexArrays.return_value = 1
        mock_gl.glGenBuffers.side_effect = [2, 3, 4]
        mock_gl.glGenTextures.return_value = 5
        mock_gl.glCreateShader.side_effect = [6, 7]
        mock_gl.glCreateProgram.return_value = 8
        mock_controller.return_value = MagicMock()

        from streetworld.viewer.viewer import Viewer

        viewer = Viewer(H=480, W=640, mode="local")

        self.assertEqual(viewer.H, 480)
        self.assertEqual(viewer.W, 640)
        self.assertEqual(viewer.mode, "local")
        self.assertIsNotNone(viewer.window)
        self.assertIsNotNone(viewer.quad)

    @patch("streetworld.viewer.viewer.glfw")
    @patch("streetworld.viewer.viewer.gl")
    @patch("streetworld.viewer.viewer.imgui")
    @patch("streetworld.viewer.viewer.Client")
    @patch("streetworld.viewer.viewer.get_controller")
    def test_viewer_client_mode_initialization(self, mock_controller, mock_client, mock_imgui, mock_gl, mock_glfw):
        """Test Viewer initialization in client mode"""
        mock_glfw.init.return_value = True
        mock_glfw.create_window.return_value = MagicMock()
        mock_imgui.get_io.return_value = MagicMock()
        mock_imgui.get_style.return_value = MagicMock()
        mock_gl.glGenVertexArrays.return_value = 1
        mock_gl.glGenBuffers.side_effect = [2, 3, 4]
        mock_gl.glGenTextures.return_value = 5
        mock_gl.glCreateShader.side_effect = [6, 7]
        mock_gl.glCreateProgram.return_value = 8
        mock_client_instance = MagicMock()
        mock_client.return_value = mock_client_instance
        mock_controller.return_value = MagicMock()

        from streetworld.viewer.viewer import Viewer

        viewer = Viewer(H=480, W=640, mode="client", host="127.0.0.1", port=56789)

        self.assertEqual(viewer.mode, "client")
        mock_client.assert_called_once()
        mock_client_instance.run.assert_called_once()

    @patch("streetworld.viewer.viewer.glfw")
    @patch("streetworld.viewer.viewer.gl")
    @patch("streetworld.viewer.viewer.imgui")
    @patch("streetworld.viewer.viewer.WebSocketServer")
    def test_viewer_server_mode_initialization(self, mock_server, mock_imgui, mock_gl, mock_glfw):
        """Test Viewer initialization in server mode"""
        mock_server_instance = MagicMock()
        mock_server.return_value = mock_server_instance

        from streetworld.viewer.viewer import Viewer

        viewer = Viewer(H=480, W=640, mode="server", host="0.0.0.0", port=1024)

        self.assertEqual(viewer.mode, "server")
        mock_server.assert_called_once()
        mock_server_instance.run.assert_called_once()

    @patch("streetworld.viewer.viewer.glfw")
    @patch("streetworld.viewer.viewer.gl")
    @patch("streetworld.viewer.viewer.imgui")
    @patch("streetworld.viewer.viewer.Client")
    @patch("streetworld.viewer.viewer.get_controller")
    def test_viewer_is_running_local(self, mock_controller, mock_client, mock_imgui, mock_gl, mock_glfw):
        """Test is_running method in local mode"""
        mock_glfw.init.return_value = True
        mock_glfw.create_window.return_value = MagicMock()
        mock_glfw.window_should_close.return_value = False
        mock_imgui.get_io.return_value = MagicMock()
        mock_imgui.get_style.return_value = MagicMock()
        mock_gl.glGenVertexArrays.return_value = 1
        mock_gl.glGenBuffers.side_effect = [2, 3, 4]
        mock_gl.glGenTextures.return_value = 5
        mock_gl.glCreateShader.side_effect = [6, 7]
        mock_gl.glCreateProgram.return_value = 8
        mock_controller.return_value = MagicMock()

        from streetworld.viewer.viewer import Viewer

        viewer = Viewer(H=480, W=640, mode="local")
        result = viewer.is_running()

        self.assertTrue(result)

    @patch("streetworld.viewer.viewer.glfw")
    @patch("streetworld.viewer.viewer.gl")
    @patch("streetworld.viewer.viewer.imgui")
    @patch("streetworld.viewer.viewer.Client")
    @patch("streetworld.viewer.viewer.get_controller")
    def test_viewer_run_local_mode(self, mock_controller, mock_client, mock_imgui, mock_gl, mock_glfw):
        """Test run method in local mode"""
        mock_glfw.init.return_value = True
        mock_glfw.create_window.return_value = MagicMock()
        mock_imgui.get_io.return_value = MagicMock()
        mock_imgui.get_style.return_value = MagicMock()
        mock_gl.glGenVertexArrays.return_value = 1
        mock_gl.glGenBuffers.side_effect = [2, 3, 4]
        mock_gl.glGenTextures.return_value = 5
        mock_gl.glCreateShader.side_effect = [6, 7]
        mock_gl.glCreateProgram.return_value = 8

        mock_manual_controller = MagicMock()
        mock_manual_controller.process_input.return_value = [0.5, 0.3]
        mock_controller.return_value = mock_manual_controller

        from streetworld.viewer.viewer import Viewer

        viewer = Viewer(H=480, W=640, mode="local")

        img = np.random.randint(0, 256, (480, 640, 3), dtype=np.uint8)
        action = viewer.run(img)

        self.assertEqual(action, [0.5, 0.3])
        mock_manual_controller.process_input.assert_called()

    @patch("streetworld.viewer.viewer.glfw")
    @patch("streetworld.viewer.viewer.gl")
    @patch("streetworld.viewer.viewer.imgui")
    @patch("streetworld.viewer.viewer.WebSocketServer")
    def test_viewer_run_server_mode(self, mock_server, mock_imgui, mock_gl, mock_glfw):
        """Test run method in server mode"""
        mock_server_instance = MagicMock()
        mock_server_instance.input = None
        mock_server.return_value = mock_server_instance

        from streetworld.viewer.viewer import Viewer

        viewer = Viewer(H=480, W=640, mode="server")

        img = np.random.randint(0, 256, (480, 640, 3), dtype=np.uint8)
        action = viewer.run(img)

        self.assertEqual(action, [0.0, 0.0])
        self.assertIsNotNone(mock_server_instance.output)

    @patch("streetworld.viewer.viewer.glfw")
    @patch("streetworld.viewer.viewer.gl")
    @patch("streetworld.viewer.viewer.imgui")
    @patch("streetworld.viewer.viewer.Client")
    @patch("streetworld.viewer.viewer.get_controller")
    def test_viewer_shutdown(self, mock_controller, mock_client, mock_imgui, mock_gl, mock_glfw):
        """Test shutdown method"""
        mock_glfw.init.return_value = True
        mock_glfw.create_window.return_value = MagicMock()
        mock_imgui.get_io.return_value = MagicMock()
        mock_imgui.get_style.return_value = MagicMock()
        mock_gl.glGenVertexArrays.return_value = 1
        mock_gl.glGenBuffers.side_effect = [2, 3, 4]
        mock_gl.glGenTextures.return_value = 5
        mock_gl.glCreateShader.side_effect = [6, 7]
        mock_gl.glCreateProgram.return_value = 8
        mock_controller.return_value = MagicMock()

        from streetworld.viewer.viewer import Viewer

        viewer = Viewer(H=480, W=640, mode="local")
        viewer.shutdown()

        mock_imgui.backends.opengl3_shutdown.assert_called_once()
        mock_imgui.backends.glfw_shutdown.assert_called_once()
        mock_imgui.destroy_context.assert_called_once()
        mock_glfw.destroy_window.assert_called_once()
        mock_glfw.terminate.assert_called_once()

    @patch("streetworld.viewer.viewer.glfw")
    @patch("streetworld.viewer.viewer.gl")
    @patch("streetworld.viewer.viewer.imgui")
    @patch("streetworld.viewer.viewer.Client")
    @patch("streetworld.viewer.viewer.get_controller")
    def test_viewer_window_address_property(self, mock_controller, mock_client, mock_imgui, mock_gl, mock_glfw):
        """Test window_address property"""
        mock_window = MagicMock()
        mock_glfw.init.return_value = True
        mock_glfw.create_window.return_value = mock_window
        mock_imgui.get_io.return_value = MagicMock()
        mock_imgui.get_style.return_value = MagicMock()
        mock_gl.glGenVertexArrays.return_value = 1
        mock_gl.glGenBuffers.side_effect = [2, 3, 4]
        mock_gl.glGenTextures.return_value = 5
        mock_gl.glCreateShader.side_effect = [6, 7]
        mock_gl.glCreateProgram.return_value = 8
        mock_controller.return_value = MagicMock()

        from streetworld.viewer.viewer import Viewer

        viewer = Viewer(H=480, W=640, mode="local")
        address = viewer.window_address

        self.assertIsNotNone(address)
        self.assertIsInstance(address, int)


class TestDummyData(unittest.TestCase):
    """Test with various dummy data formats"""

    def generate_image_uint8(self, h=480, w=640):
        """Generate uint8 image"""
        return np.random.randint(0, 256, (h, w, 3), dtype=np.uint8)

    def generate_image_float32(self, h=480, w=640):
        """Generate float32 image (0-1 range)"""
        return np.random.rand(h, w, 3).astype(np.float32)

    def generate_image_float32_large(self, h=480, w=640):
        """Generate float32 image (0-255 range)"""
        return np.random.rand(h, w, 3).astype(np.float32) * 255.0

    def generate_image_grayscale(self, h=480, w=640):
        """Generate grayscale image"""
        return np.random.randint(0, 256, (h, w), dtype=np.uint8)

    def generate_image_rgba(self, h=480, w=640):
        """Generate RGBA image"""
        return np.random.randint(0, 256, (h, w, 4), dtype=np.uint8)

    def generate_torch_tensor_uint8(self, h=480, w=640):
        """Generate torch tensor (uint8)"""
        return torch.randint(0, 256, (h, w, 3), dtype=torch.uint8)

    def generate_torch_tensor_float32(self, h=480, w=640):
        """Generate torch tensor (float32 0-1)"""
        return torch.rand(h, w, 3)

    def generate_torch_tensor_float32_large(self, h=480, w=640):
        """Generate torch tensor (float32 0-255)"""
        return torch.rand(h, w, 3) * 255.0

    def test_image_formats(self):
        """Test various image formats"""
        formats = [
            ("uint8", self.generate_image_uint8()),
            ("float32 0-1", self.generate_image_float32()),
            ("float32 0-255", self.generate_image_float32_large()),
            ("grayscale", self.generate_image_grayscale()),
            ("rgba", self.generate_image_rgba()),
            ("torch uint8", self.generate_torch_tensor_uint8()),
            ("torch float32 0-1", self.generate_torch_tensor_float32()),
            ("torch float32 0-255", self.generate_torch_tensor_float32_large()),
        ]

        for name, img in formats:
            with self.subTest(format=name):
                if isinstance(img, torch.Tensor):
                    self.assertTrue(isinstance(img, torch.Tensor))
                else:
                    self.assertTrue(isinstance(img, np.ndarray))

    def test_different_resolutions(self):
        """Test different image resolutions"""
        resolutions = [
            (240, 320),
            (480, 640),
            (720, 1280),
            (1080, 1920),
        ]

        for h, w in resolutions:
            with self.subTest(resolution=f"{h}x{w}"):
                img = self.generate_image_uint8(h, w)
                self.assertEqual(img.shape, (h, w, 3))


class TestUtilityFunctions(unittest.TestCase):
    """Test utility functions"""

    def test_log_function(self):
        """Test log function"""
        from streetworld.viewer.viewer import log

        with patch("builtins.print") as mock_print:
            log("test message")
            mock_print.assert_called_once_with("test message")

    def test_red_function(self):
        """Test red text coloring function"""
        from streetworld.viewer.viewer import red

        colored_text = red("error")
        self.assertIn("\033[91m", colored_text)
        self.assertIn("\033[0m", colored_text)
        self.assertIn("error", colored_text)

    def test_red_function_output(self):
        """Test red function output format"""
        from streetworld.viewer.viewer import red

        result = red("test")
        expected = "\033[91mtest\033[0m"
        self.assertEqual(result, expected)


if __name__ == "__main__":
    unittest.main()
