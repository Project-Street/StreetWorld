from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from queue import Queue
from threading import Thread
from typing import Any, Dict, Mapping

import gymnasium as gym
import numpy as np
from panda3d.core import (
    ColorWriteAttrib,
    Geom,
    GeomNode,
    GeomTriangles,
    GeomVertexData,
    GeomVertexFormat,
    GeomVertexWriter,
    GraphicsOutput,
    LMatrix4,
    LVecBase3f,
    OrthographicLens,
    PerspectiveLens,
    RenderState,
    SamplerState,
    Shader,
    ShaderAttrib,
    Texture,
    Vec4,
    loadPrcFileData,
)
from scipy.spatial.transform import Rotation

from streetworld.objects.terrain.ground import GroundPlane
from streetworld.objects.terrain.mesh_terrain import MeshTerrain
from streetworld.obs.observation_base import BaseObservation
from streetworld.type import MetaDriveType


_NEAR_CLIP = 0.1
_FAR_CLIP = 1000.0
_SHADOW_MAP_SIZE = 1024
_SHADOW_RANGE = 120.0
_SHADOW_DISTANCE = 120.0
_SUN_DIRECTION = np.asarray([-0.45, -0.65, 1.0], dtype=np.float32)
_SUN_DIRECTION /= np.linalg.norm(_SUN_DIRECTION)

_SKY_COLOR = (0.58, 0.70, 0.76, 1.0)
_GROUND_COLOR = (0.31, 0.39, 0.37, 1.0)
_VEHICLE_COLOR = (0.18, 0.38, 0.68, 1.0)
_PEDESTRIAN_COLOR = (0.78, 0.28, 0.24, 1.0)
_CYCLIST_COLOR = (0.88, 0.58, 0.14, 1.0)
_SHADER_DIR = Path(__file__).with_name("shaders")


@dataclass
class _CameraConfig:
    height: int
    width: int
    focal: float
    offset: np.ndarray
    panda_camera_to_ego: np.ndarray
    texture: Any = None
    buffer: Any = None
    camera: Any = None


def _numpy_to_panda_matrix(matrix: np.ndarray) -> LMatrix4:
    return LMatrix4(*np.asarray(matrix).T.ravel())


def _vec3(value: Any, label: str) -> np.ndarray:
    vector = np.asarray(value, dtype=np.float32)
    if vector.shape != (3,) or not np.isfinite(vector).all():
        raise ValueError(f"{label} must contain three finite values")
    return vector


def _parse_camera_configs(config: Mapping[str, Any]) -> Dict[str, _CameraConfig]:
    cameras = config.get("cameras")
    if not isinstance(cameras, Mapping) or not cameras:
        raise ValueError(
            "CollisionBodyObservation requires a non-empty cameras mapping"
        )

    ego_to_cv_base = np.asarray(
        [[0.0, -1.0, 0.0], [0.0, 0.0, -1.0], [1.0, 0.0, 0.0]],
        dtype=np.float32,
    )
    cv_from_panda = np.asarray(
        [
            [1.0, 0.0, 0.0, 0.0],
            [0.0, 0.0, -1.0, 0.0],
            [0.0, 1.0, 0.0, 0.0],
            [0.0, 0.0, 0.0, 1.0],
        ],
        dtype=np.float32,
    )

    parsed: Dict[str, _CameraConfig] = {}
    required = ("H", "W", "focal", "offset", "hpr")
    for raw_name, raw_camera in cameras.items():
        name = str(raw_name)
        if not name:
            raise ValueError("Collision body camera names must not be empty")
        if not isinstance(raw_camera, Mapping):
            raise TypeError(f"Collision body camera {name} config must be a mapping")
        missing = [key for key in required if key not in raw_camera]
        if missing:
            raise ValueError(
                f"Collision body camera {name} missing required params: {missing}"
            )

        raw_height = raw_camera["H"]
        raw_width = raw_camera["W"]
        if (
            isinstance(raw_height, bool)
            or not isinstance(raw_height, (int, np.integer))
            or isinstance(raw_width, bool)
            or not isinstance(raw_width, (int, np.integer))
        ):
            raise TypeError(f"Collision body camera {name} H and W must be integers")
        height = int(raw_height)
        width = int(raw_width)
        focal = float(raw_camera["focal"])
        if height <= 0 or width <= 0:
            raise ValueError(f"Collision body camera {name} H and W must be positive")
        if not np.isfinite(focal) or focal <= 0.0:
            raise ValueError(
                f"Collision body camera {name} focal must be positive and finite"
            )

        offset = _vec3(raw_camera["offset"], f"Collision body camera {name} offset")
        hpr = _vec3(raw_camera["hpr"], f"Collision body camera {name} hpr")
        camera_to_ego = Rotation.from_euler("ZYX", np.deg2rad(hpr)).as_matrix()
        cv_camera_to_ego = np.eye(4, dtype=np.float32)
        cv_camera_to_ego[:3, :3] = camera_to_ego @ ego_to_cv_base.T
        cv_camera_to_ego[:3, 3] = offset

        parsed[name] = _CameraConfig(
            height=height,
            width=width,
            focal=focal,
            offset=offset,
            panda_camera_to_ego=np.asarray(
                cv_camera_to_ego @ cv_from_panda, dtype=np.float32
            ),
        )
    return parsed


def _copy_camera_configs(cameras: Mapping[str, _CameraConfig]) -> Dict[str, _CameraConfig]:
    return {
        name: _CameraConfig(
            height=camera.height,
            width=camera.width,
            focal=camera.focal,
            offset=camera.offset.copy(),
            panda_camera_to_ego=camera.panda_camera_to_ego.copy(),
        )
        for name, camera in cameras.items()
    }


def _snapshot_ground(ground: Any) -> dict[str, Any]:
    if isinstance(ground, GroundPlane):
        shape = ground.body.get_shape(0)
        normal = np.asarray(shape.get_plane_normal(), dtype=np.float32)
        normal_length = float(np.linalg.norm(normal))
        if normal_length == 0.0:
            raise ValueError("GroundPlane normal must have non-zero length")
        return {
            "kind": "plane",
            "normal": normal / normal_length,
            "constant": float(shape.get_plane_constant()),
        }
    if isinstance(ground, MeshTerrain):
        return {
            "kind": "mesh",
            "vertices": ground.vertices,
            "faces": ground.faces,
            "normals": ground.vertex_normals,
        }
    raise TypeError(f"Unsupported collision body ground type: {type(ground).__name__}")


class _CollisionBodySceneRenderer:
    def __init__(self, cameras: Mapping[str, _CameraConfig]):
        loadPrcFileData(
            "collision-body-observation",
            "window-type offscreen\n"
            "load-display p3headlessgl\n"
            "audio-library-name null\n"
            "gl-version 3 3\n"
            "framebuffer-multisample 0\n"
            "multisamples 0\n",
        )
        from direct.showbase.ShowBase import ShowBase

        self.base = ShowBase(windowType="offscreen")
        self.render_root = self.base.render
        self.base.camNode.set_active(False)
        self._ground_node = None
        self._ground_plane = None
        self._object_nodes: Dict[str, Any] = {}
        self._ego_node = None

        main_shader = self._load_shader(
            "collision_body.vert.glsl", "collision_body.frag.glsl"
        )
        depth_shader = self._load_shader(
            "collision_body_depth.vert.glsl", "collision_body_depth.frag.glsl"
        )
        self.render_root.set_shader(main_shader)
        self.render_root.set_shader_input(
            "light_direction", LVecBase3f(*_SUN_DIRECTION)
        )

        self._setup_shadow_buffer(depth_shader)
        self.cameras = dict(cameras)
        for name, camera in self.cameras.items():
            self._setup_camera(name, camera)

    @staticmethod
    def _load_shader(vertex_name: str, fragment_name: str) -> Shader:
        vertex_path = _SHADER_DIR / vertex_name
        fragment_path = _SHADER_DIR / fragment_name
        return Shader.make(
            Shader.SL_GLSL,
            vertex=vertex_path.read_text(encoding="utf-8"),
            fragment=fragment_path.read_text(encoding="utf-8"),
        )

    def _setup_shadow_buffer(self, depth_shader: Shader) -> None:
        self._shadow_texture = Texture("collision-body-shadow-map")
        self._shadow_texture.set_format(Texture.F_depth_component32)
        self._shadow_texture.set_minfilter(SamplerState.FT_nearest)
        self._shadow_texture.set_magfilter(SamplerState.FT_nearest)
        self._shadow_texture.set_wrap_u(SamplerState.WM_clamp)
        self._shadow_texture.set_wrap_v(SamplerState.WM_clamp)

        self._shadow_buffer = self.base.win.make_texture_buffer(
            "collision-body-shadow-buffer", _SHADOW_MAP_SIZE, _SHADOW_MAP_SIZE
        )
        self._shadow_buffer.clear_render_textures()
        self._shadow_buffer.add_render_texture(
            self._shadow_texture,
            GraphicsOutput.RTM_bind_or_copy,
            GraphicsOutput.RTP_depth,
        )
        self._shadow_buffer.set_clear_depth(1.0)
        self._shadow_buffer.set_clear_depth_active(True)
        self._shadow_buffer.set_sort(-100)
        self._shadow_buffer.set_active(False)

        self._shadow_lens = OrthographicLens()
        self._shadow_lens.set_film_size(_SHADOW_RANGE, _SHADOW_RANGE)
        self._shadow_lens.set_near_far(1.0, _SHADOW_DISTANCE * 2.0)
        self._shadow_camera = self.base.make_camera(
            self._shadow_buffer,
            lens=self._shadow_lens,
            scene=self.render_root,
        )
        self._shadow_camera.node().set_initial_state(
            RenderState.make(
                ShaderAttrib.make(depth_shader),
                ColorWriteAttrib.make(ColorWriteAttrib.C_off),
            )
        )
        self.render_root.set_shader_input("shadow_map", self._shadow_texture)

    def _setup_camera(self, name: str, camera: _CameraConfig) -> None:
        camera.texture = Texture(f"collision-body-{name}")
        camera.buffer = self.base.win.make_texture_buffer(
            f"collision-body-buffer-{name}",
            camera.width,
            camera.height,
            camera.texture,
            True,
        )
        camera.buffer.set_clear_color(Vec4(*_SKY_COLOR))
        camera.buffer.set_clear_color_active(True)
        camera.buffer.set_clear_depth(1.0)
        camera.buffer.set_clear_depth_active(True)
        camera.buffer.set_active(False)

        lens = PerspectiveLens()
        lens.set_film_size(camera.width, camera.height)
        lens.set_focal_length(camera.focal)
        lens.set_near_far(_NEAR_CLIP, _FAR_CLIP)
        camera.camera = self.base.make_camera(
            camera.buffer, lens=lens, scene=self.render_root
        )

    def set_ground(self, ground: Mapping[str, Any]) -> None:
        if self._ground_node is not None:
            self._ground_node.remove_node()
        self._ground_node = None
        self._ground_plane = None

        if ground["kind"] == "plane":
            normal = ground["normal"]
            self._ground_plane = (normal, ground["constant"])
            node = self._make_box_node(
                width=_FAR_CLIP * 2.0,
                depth=_FAR_CLIP * 2.0,
                height=0.02,
                color=_GROUND_COLOR,
                name="collision-body-ground-plane",
                center=(0.0, 0.0, -0.01),
            )
            self._ground_node = self.render_root.attach_new_node(node)
            reference = (
                np.asarray([0.0, 0.0, 1.0], dtype=np.float32)
                if abs(float(normal[2])) < 0.9
                else np.asarray([1.0, 0.0, 0.0], dtype=np.float32)
            )
            tangent = np.cross(reference, normal)
            tangent /= np.linalg.norm(tangent)
            bitangent = np.cross(normal, tangent)
            ground_transform = np.eye(4, dtype=np.float32)
            ground_transform[:3, :3] = np.column_stack((tangent, bitangent, normal))
            self._ground_node.set_mat(_numpy_to_panda_matrix(ground_transform))
            return

        if ground["kind"] == "mesh":
            self._ground_node = self.render_root.attach_new_node(
                self._make_triangle_node(
                    ground["vertices"],
                    ground["faces"],
                    ground["normals"],
                    _GROUND_COLOR,
                    "collision-body-ground-mesh",
                )
            )
            return

        raise ValueError(f"Unsupported collision body ground kind: {ground['kind']}")

    @staticmethod
    def _make_triangle_node(
        vertices: np.ndarray,
        faces: np.ndarray,
        normals: np.ndarray,
        color: tuple[float, float, float, float],
        name: str,
    ) -> GeomNode:
        vertex_data = GeomVertexData(
            name, GeomVertexFormat.get_v3n3c4(), Geom.UH_static
        )
        vertex_data.set_num_rows(len(vertices))
        vertex_writer = GeomVertexWriter(vertex_data, "vertex")
        normal_writer = GeomVertexWriter(vertex_data, "normal")
        color_writer = GeomVertexWriter(vertex_data, "color")
        for vertex, normal in zip(vertices, normals):
            vertex_writer.add_data3f(*vertex)
            normal_writer.add_data3f(*normal)
            color_writer.add_data4f(*color)

        triangles = GeomTriangles(Geom.UH_static)
        for a, b, c in faces:
            triangles.add_vertices(int(a), int(b), int(c))
        triangles.close_primitive()

        geom = Geom(vertex_data)
        geom.add_primitive(triangles)
        node = GeomNode(name)
        node.add_geom(geom)
        return node

    @classmethod
    def _make_box_node(
        cls,
        width: float,
        depth: float,
        height: float,
        color: tuple[float, float, float, float],
        name: str,
        center: tuple[float, float, float] = (0.0, 0.0, 0.0),
    ) -> GeomNode:
        half_width, half_depth, half_height = np.asarray(
            (width, depth, height), dtype=np.float32
        ) * 0.5
        vertices = np.asarray(
            (
                (-half_width, -half_depth, -half_height),
                (half_width, -half_depth, -half_height),
                (half_width, half_depth, -half_height),
                (-half_width, half_depth, -half_height),
                (-half_width, -half_depth, half_height),
                (half_width, -half_depth, half_height),
                (half_width, half_depth, half_height),
                (-half_width, half_depth, half_height),
            ),
            dtype=np.float32,
        ) + np.asarray(center, dtype=np.float32)
        faces = (
            ((0, 4, 7, 3), (-1.0, 0.0, 0.0)),
            ((1, 2, 6, 5), (1.0, 0.0, 0.0)),
            ((0, 1, 5, 4), (0.0, -1.0, 0.0)),
            ((3, 7, 6, 2), (0.0, 1.0, 0.0)),
            ((0, 3, 2, 1), (0.0, 0.0, -1.0)),
            ((4, 5, 6, 7), (0.0, 0.0, 1.0)),
        )
        face_vertices = np.concatenate(
            [vertices[list(indices)] for indices, _ in faces]
        )
        normals = np.repeat(
            np.asarray([normal for _, normal in faces], dtype=np.float32), 4, axis=0
        )
        triangles = np.asarray(
            [
                (base, base + 1, base + 2)
                for base in range(0, len(face_vertices), 4)
            ]
            + [
                (base, base + 2, base + 3)
                for base in range(0, len(face_vertices), 4)
            ],
            dtype=np.int32,
        )
        return cls._make_triangle_node(face_vertices, triangles, normals, color, name)

    def _sync_objects(self, objects: Mapping[str, Mapping[str, Any]], ego_object_id: str) -> None:
        active_ids = set(objects)
        for object_id in set(self._object_nodes) - active_ids:
            self._object_nodes.pop(object_id).remove_node()

        self._ego_node = None
        for object_id, state in objects.items():
            size = np.asarray(state["size"], dtype=np.float32)
            transform = np.asarray(state["transform"], dtype=np.float32)
            if size.shape != (3,) or not np.isfinite(size).all() or np.any(size <= 0.0):
                raise ValueError(f"Object {object_id} has invalid size: {size}")
            if transform.shape != (4, 4) or not np.isfinite(transform).all():
                raise ValueError(
                    f"Object {object_id} has invalid transform: shape={transform.shape}"
                )

            color = state["color"]
            if object_id not in self._object_nodes:
                node = self._make_box_node(
                    width=float(size[0]),
                    depth=float(size[1]),
                    height=float(size[2]),
                    color=color,
                    name=f"collision-body-{object_id}",
                )
                self._object_nodes[object_id] = self.render_root.attach_new_node(node)

            object_node = self._object_nodes[object_id]
            object_node.set_mat(_numpy_to_panda_matrix(transform))
            if object_id == ego_object_id:
                self._ego_node = object_node

        if self._ego_node is None:
            raise RuntimeError(
                "Collision body observation collector did not include the ego controller"
            )

    def render(
        self,
        ego_transform: np.ndarray,
        objects: Mapping[str, Mapping[str, Any]],
        ego_object_id: str,
        show_ego: Mapping[str, bool],
    ) -> Dict[str, np.ndarray]:
        self._sync_objects(objects, ego_object_id)
        ego_transform = np.asarray(ego_transform, dtype=np.float32)
        ego_position = ego_transform[:3, 3]
        self._update_shadow_camera(ego_position)

        images: Dict[str, np.ndarray] = {}
        for name, camera in self.cameras.items():
            camera_to_world = ego_transform @ camera.panda_camera_to_ego
            camera.camera.set_mat(_numpy_to_panda_matrix(camera_to_world))
            if show_ego[name]:
                self._ego_node.show()
            else:
                self._ego_node.hide()
            self._position_ground_plane(camera_to_world[:3, 3])

            self._shadow_buffer.set_active(True)
            self.base.graphicsEngine.render_frame()
            self._shadow_buffer.set_active(False)

            camera.buffer.set_active(True)
            self.base.graphicsEngine.render_frame()
            camera.buffer.set_active(False)

            image = np.frombuffer(
                camera.texture.get_ram_image_as("RGB"), dtype=np.uint8
            )
            expected_size = camera.height * camera.width * 3
            if image.size != expected_size:
                raise RuntimeError(
                    f"Collision body camera {name} returned {image.size} bytes, expected {expected_size}"
                )
            image = image.reshape(camera.height, camera.width, 3)
            images[name] = np.ascontiguousarray(np.flipud(image))

        self._ego_node.show()
        return images

    def _update_shadow_camera(self, target: np.ndarray) -> None:
        light_position = target + _SUN_DIRECTION * _SHADOW_DISTANCE
        self._shadow_camera.set_pos(*light_position)
        self._shadow_camera.look_at(*target)
        world_to_light = self.render_root.get_transform(self._shadow_camera).get_mat()
        shadow_mvp = world_to_light * self._shadow_lens.get_projection_mat()
        self.render_root.set_shader_input("shadow_mvp", shadow_mvp)

    def _position_ground_plane(self, camera_position: np.ndarray) -> None:
        if self._ground_plane is None:
            return
        normal, constant = self._ground_plane
        projected = camera_position + normal * (
            constant - float(normal @ camera_position)
        )
        self._ground_node.set_pos(*projected)

    def destroy(self) -> None:
        for camera in self.cameras.values():
            camera.camera.remove_node()
            camera.buffer.clear_render_textures()
            self.base.graphicsEngine.remove_window(camera.buffer)
        self.cameras.clear()
        self._shadow_camera.remove_node()
        self._shadow_buffer.clear_render_textures()
        self.base.graphicsEngine.remove_window(self._shadow_buffer)
        self.render_root.clear_shader()
        self.base.destroy()
        self.base = None


class _CollisionBodyRenderThread:
    def __init__(self, cameras: Mapping[str, _CameraConfig]) -> None:
        self._requests = Queue()
        self._ready = Queue(maxsize=1)
        self._thread = Thread(
            target=self._run,
            args=(_copy_camera_configs(cameras),),
            name="CollisionBodyRenderer",
            daemon=True,
        )
        self._thread.start()
        result = self._ready.get()
        if isinstance(result, BaseException):
            self._thread.join()
            raise result

    def set_ground(self, ground: Mapping[str, Any]) -> None:
        self._request("set_ground", ground)

    def render(
        self,
        ego_transform: np.ndarray,
        objects: Mapping[str, Mapping[str, Any]],
        ego_object_id: str,
        show_ego: Mapping[str, bool],
    ) -> Dict[str, np.ndarray]:
        return self._request("render", ego_transform, objects, ego_object_id, show_ego)

    def close(self) -> None:
        self._request("close")
        self._thread.join()

    def _request(self, operation: str, *args: Any) -> Any:
        response = Queue(maxsize=1)
        self._requests.put((operation, args, response))
        result = response.get()
        if isinstance(result, BaseException):
            raise result
        return result

    def _run(self, cameras: Mapping[str, _CameraConfig]) -> None:
        try:
            renderer = _CollisionBodySceneRenderer(cameras)
        except BaseException as error:
            self._ready.put(error)
            return
        self._ready.put(None)

        try:
            while True:
                operation, args, response = self._requests.get()
                try:
                    if operation == "set_ground":
                        result = renderer.set_ground(*args)
                    elif operation == "render":
                        result = renderer.render(*args)
                    elif operation == "close":
                        result = None
                    else:
                        raise ValueError(f"Unknown collision body render operation: {operation}")
                except BaseException as error:
                    response.put(error)
                else:
                    response.put(result)
                if operation == "close":
                    return
        finally:
            renderer.destroy()


class CollisionBodyObservation(BaseObservation):
    """
    Render MetaDrive collision bodies from ego-relative pinhole cameras.

    Each camera config contains H, W, focal, offset, and hpr. The offset uses
    ego axes (+X forward, +Y left, +Z up); hpr follows GaussianObservation.
    """

    def __init__(self, config: Mapping[str, Any]):
        super().__init__(config)
        self.cameras = _parse_camera_configs(config)
        self.controller = None
        self.collector = None
        self._renderer = None
        self._show_ego: Dict[str, bool] = {}

    def reset(self, controller: Any, collector: Any, ground: Any, **kwargs) -> None:
        self.controller = controller
        self.collector = collector
        if self._renderer is None:
            self._renderer = _CollisionBodyRenderThread(self.cameras)
        self._renderer.set_ground(_snapshot_ground(ground))

        half_size = (
            np.asarray(
                [controller.LENGTH, controller.WIDTH, controller.HEIGHT],
                dtype=np.float32,
            )
            * 0.5
        )
        self._show_ego = {
            name: not bool(np.all(np.abs(camera.offset) <= half_size))
            for name, camera in self.cameras.items()
        }

    @property
    def observation_space(self) -> gym.spaces.Dict:
        return gym.spaces.Dict(
            {
                name: gym.spaces.Box(
                    0,
                    255,
                    shape=(camera.height, camera.width, 3),
                    dtype=np.uint8,
                )
                for name, camera in self.cameras.items()
            }
        )

    def observe(self) -> Dict[str, np.ndarray]:
        if self._renderer is None or self.controller is None or self.collector is None:
            raise RuntimeError(
                "CollisionBodyObservation.observe() called before reset()"
            )
        objects = self.collector()
        scene_objects = {}
        ego_object_id = None
        for object_id, state in objects.items():
            scene_object = state["controller"]
            scene_objects[object_id] = {
                "size": state["size"],
                "transform": state["transform"],
                "color": self.__object_color(scene_object),
            }
            if scene_object is self.controller:
                ego_object_id = object_id
        if ego_object_id is None:
            raise RuntimeError("Collision body observation collector did not include the ego controller")
        return self._renderer.render(
            ego_transform=self.controller.transform,
            objects=scene_objects,
            ego_object_id=ego_object_id,
            show_ego=self._show_ego,
        )

    @staticmethod
    def __object_color(scene_object: Any) -> tuple[float, float, float, float]:
        object_type = scene_object.metadrive_type
        if MetaDriveType.is_vehicle(object_type):
            color = _VEHICLE_COLOR
        elif object_type == MetaDriveType.PEDESTRIAN:
            color = _PEDESTRIAN_COLOR
        elif object_type == MetaDriveType.CYCLIST:
            color = _CYCLIST_COLOR
        else:
            raise ValueError(f"Unsupported collision body object type: {object_type}")
        if scene_object.body.isStatic():
            return tuple((channel + 1.0) * 0.5 for channel in color[:3]) + (color[3],)
        return color

    def destroy(self) -> None:
        if self._renderer is not None:
            self._renderer.close()
        self._renderer = None
        self.controller = None
        self.collector = None
        self._show_ego = {}
        super().destroy()
