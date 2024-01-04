import bpy
import os
import sys
import zipfile
import struct
import ctypes
import json
import mathutils
import pathlib
import time

def to_signed_32(value):
    if value & 0x80000000:
        return value - 0x100000000
    return value

def to_unsigned_32(value):
    return value & 0xFFFFFFFF

class HitmanAbsolution:
    def __init__(self):
        self.dir = os.path.abspath(os.path.dirname(__file__))
        if not os.environ['PATH'].startswith(self.dir):
            os.environ['PATH'] = self.dir + os.pathsep + os.environ['PATH']
        self.hmaexport = ctypes.CDLL(os.path.abspath(os.path.join(os.path.dirname(__file__), "AbsolutionSceneExporter.dll")), winmode=0)
        self.hmaexport.LoadData.argtypes = (ctypes.c_uint32, ctypes.c_char_p, ctypes.c_char_p, ctypes.c_char_p)
        self.hmaexport.LoadData.restype = None
        self.hmaexport.ExportModel.argtypes = (ctypes.c_uint64, ctypes.c_char_p)
        self.hmaexport.ExportModel.restype = None
        self.hmaexport.GetMaterialJson.argtypes = (ctypes.c_uint64,)
        self.hmaexport.GetMaterialJson.restype = ctypes.c_char_p
        self.hmaexport.GetSceneJson.argtypes = ()
        self.hmaexport.GetSceneJson.restype = ctypes.c_char_p
        self.scene_json = ""
        self.output_folder_path = ""
        self.root_node = None

    def load_data(self, context, selected_scene_index, runtime_folder_path, output_folder_path):
        assets_folder_path = os.path.dirname(__file__).encode()
        self.output_folder_path = output_folder_path

        if self.output_folder_path == "":
            self.output_folder_path = self.dir

        self.hmaexport.LoadData(selected_scene_index, runtime_folder_path, assets_folder_path, output_folder_path.encode())

        json_string = self.hmaexport.GetSceneJson()
        self.scene_json = json.loads(json_string)

        for model in self.scene_json["Scene"]:
            if "Meshes" in model:
                item = context.scene.custom.add()
                item.name = model["Parent"] + " / " + model["Name"] + " (" + str(model["PRIMRuntimeResourceID"]) + ")"
                item.index = model["Index"]
                item.prim_file_name = model["PRIMFileName"]

                prim_runtime_resource_id = model["PRIMRuntimeResourceID"]
                item.prim_id_high = to_signed_32((prim_runtime_resource_id >> 32) & 0xFFFFFFFF)
                item.prim_id_low = to_signed_32(prim_runtime_resource_id & 0xFFFFFFFF)

                context.scene.custom_index = item.index

    def import_model_in_blender(self, context, prim_runtime_resource_id, model, name, parent, prim_file_name):
        self.hmaexport.ExportModel(prim_runtime_resource_id, self.output_folder_path.encode())

        filepath = os.path.join(self.output_folder_path, "Models", f"{prim_file_name}_{prim_runtime_resource_id}.obj")

        bpy.ops.wm.obj_import(
            filepath=filepath,
            forward_axis='Z',
            up_axis='Y'
        )

        if len(context.selected_objects) > 0:
            context.view_layer.objects.active = context.selected_objects[0]
            obj = context.object
            obj.name = name
            if parent != None:
                if parent in bpy.data.objects:
                    obj.parent = bpy.data.objects[parent]
                    obj.matrix_parent_inverse = obj.parent.matrix_world.inverted()
            obj.matrix_local = self.get_matrix(model["Index"])
            if self.root_node == None:
                self.root_node = obj
            for slot in obj.material_slots:
                if ".0" in slot.material.name:
                    old_material = slot.material
                    slot.material = bpy.data.materials[slot.material.name[:slot.material.name.find(".")]]
                    bpy.data.materials.remove(old_material, do_unlink=True)
            # bpy.ops.mesh.separate(type='MATERIAL')
            if obj != None:
                for mesh in model["Meshes"]:
                    json_string = self.hmaexport.GetMaterialJson(mesh["MATIRuntimeResourceID"])
                    mat_json = json.loads(json_string)
                    material = mat_json["Instance"][0]["Binder"][0]["Render State"][0]
                    #if "Blend Enabled" in material and "Blend Mode" in material and "Alpha Reference" in material and "Culling Mode" in material:
                        #if material["Blend Enabled"] == 1 and (
                                #material["Alpha Reference"] != 254 or material["Opacity"] != 1.0 or (
                                #material["Blend Mode"] != "TRANS" and material["Alpha Reference"] == 254) or material[
                                    #"Culling Mode"] == "TwoSided"):
                            #for slot in obj.material_slots:
                                #if slot.material.use_nodes:
                                    #for n in slot.material.node_tree.nodes:
                                        #if n.type == "BSDF_PRINCIPLED" and "Base Color" in n.inputs:
                                            #for l in n.inputs["Base Color"].links:
                                                #if l.from_node.type == "TEX_IMAGE":
                                                    #if material["Blend Mode"] == "TRANS" and material["Opacity"] == 1.0:
                                                    #    slot.material.blend_method = 'CLIP'
                                                    #else:
                                                    #    slot.material.blend_method = 'BLEND'
                                                    #if material["Opacity"] == 1.0:
                                                    #    slot.material.node_tree.links.new(l.from_node.outputs['Alpha'],
                                                    #                                      n.inputs['Alpha'])
                                                    #else:
                                                    #    n.inputs['Alpha'].default_value = material["Opacity"]
            return obj
        else:
            return None

    def import_models(self, context, index, parent):
        self.update_progress()
        model = self.scene_json["Scene"][index]
        name = str(model["Index"]) + " - " + model["Name"]
        if len(name) > 63:
            name = name[:63]
        exclude_model = False
        is_model = False

        if "Meshes" in model:
            is_model = True

        if is_model and not exclude_model:
            obj = self.import_model_in_blender(context, model["PRIMRuntimeResourceID"], model, name, parent, model["PRIMFileName"])
        else:
            obj = bpy.data.objects.new(name, None)
            context.collection.objects.link(obj)
            if parent != None:
                if parent in bpy.data.objects:
                    obj.parent = bpy.data.objects[parent]
                    obj.matrix_parent_inverse = obj.parent.matrix_world.inverted()
                    obj.matrix_local = self.get_matrix(model["Index"])
            obj.matrix_local = self.get_matrix(model["Index"])
            if self.root_node == None:
                self.root_node = obj

        if "Children" in model:
            for child in model["Children"]:
                self.import_models(context, child["Index"], name)

    def import_map(self, context):
        from bpy.ops import _BPyOpsSubModOp
        view_layer_update = _BPyOpsSubModOp._view_layer_update

        def dummy_view_layer_update(context):
            pass

        try:
            _BPyOpsSubModOp._view_layer_update = dummy_view_layer_update
            time_start = time.time()
            self.root_node = None
            root_index = -1

            for model in self.scene_json["Scene"]:
                if model["Parent"] == None:
                    root_index = model["Index"]
                    break

            if root_index != -1:
                self.progress = 0
                self.progress_step = int(len(self.scene_json["Scene"]) / 100)
                bpy.context.window_manager.progress_begin(0, 100)
                
                self.import_models(context, root_index, None)
                self.root_node.matrix_local = (
                    (-0.01, 0.0, 0.0, 0.0),
                    (0.0, 0.0, 0.01, 0.0),
                    (0.0, -0.01, 0.0, 0.0),
                    (0.0, 0.0, 0.0, 1.0)
                )
                bpy.context.window_manager.progress_end()
                print("Loaded Map in " + str(time.time() - time_start) + " seconds")
            else:
                print("Error: The root scene node for the map could not be found.")
        finally:
            _BPyOpsSubModOp._view_layer_update = view_layer_update

    def get_matrix(self, index):
        return (
            (
                self.scene_json["Scene"][index]["Transform"]["Rot"]["XAxis"]["x"],
                self.scene_json["Scene"][index]["Transform"]["Rot"]["XAxis"]["y"],
                self.scene_json["Scene"][index]["Transform"]["Rot"]["XAxis"]["z"],
                0.0
            ),
            (
                self.scene_json["Scene"][index]["Transform"]["Rot"]["YAxis"]["x"],
                self.scene_json["Scene"][index]["Transform"]["Rot"]["YAxis"]["y"],
                self.scene_json["Scene"][index]["Transform"]["Rot"]["YAxis"]["z"],
                0.0
            ),
            (
                self.scene_json["Scene"][index]["Transform"]["Rot"]["ZAxis"]["x"],
                self.scene_json["Scene"][index]["Transform"]["Rot"]["ZAxis"]["y"],
                self.scene_json["Scene"][index]["Transform"]["Rot"]["ZAxis"]["z"],
                0.0
            ),
            (
                self.scene_json["Scene"][index]["Transform"]["Trans"]["x"],
                self.scene_json["Scene"][index]["Transform"]["Trans"]["y"],
                self.scene_json["Scene"][index]["Transform"]["Trans"]["z"],
                1.0
            )
        )

    def update_progress(self):
        self.progress += 1

        if self.progress % self.progress_step == 0:
            bpy.context.window_manager.progress_update(self.progress / self.progress_step)
