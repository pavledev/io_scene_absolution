bl_info = {
    "name": "Hitman Absolution Tools",
    "description": "Tools for Hitman Absolution",
    "version": (1, 0, 0),
    "blender": (3, 3, 0),
    "doc_url": "",
    "tracker_url": "",
    "category": "Import-Export",
}

import bpy
import json
from . import hmaexport

hma = hmaexport.HitmanAbsolution()


class Preferences(bpy.types.AddonPreferences):
    bl_idname = __name__
    
    runtime_folder_path: bpy.props.StringProperty(
        name="Runtime Folder Path",
        subtype='DIR_PATH'
    )

    output_folder_path: bpy.props.StringProperty(
        name="Output Folder Path",
        subtype='DIR_PATH',
        default="",
        description="Output folder path for exported Hitman Absolution models"
    )

    def draw(self, context):
        layout = self.layout
        layout.prop(self, "runtime_folder_path")
        layout.prop(self, "output_folder_path")


class CUSTOM_UL_Items(bpy.types.UIList):
    def draw_item(self, context, layout, data, item, icon, active_data, active_propname, index):
        self.use_filter_show = True
        split = layout.row()
        custom_icon = "COLOR"
        split.prop(item, "name", emboss=False, text="")

    def invoke(self, context, event):
        pass


class CUSTOM_PT_HitmanAbsolutionPanel(bpy.types.Panel):
    bl_idname = 'CUSTOM_PT_HitmanAbsolutionPanel'
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = 'Hitman Absolution'
    bl_label = 'Hitman Absolution'

    def draw(self, context):
        layout = self.layout
        scene = bpy.context.scene
        
        row = layout.row(align=True)
        row.prop(scene, "custom_dropdown_property")

        rows = 10
        row = layout.row()
        row.template_list("CUSTOM_UL_Items", "", scene, "custom", scene, "custom_index", rows=rows)

        row = layout.row()
        row = layout.row(align=True)
        row.operator("custom.load_model")
        row = layout.row(align=True)
        row.operator("custom.load_map")        
        layout.label(text="General Options:")
        row = layout.row(align=True)
        row.prop(context.preferences.addons[__name__].preferences, "runtime_folder_path")
        row = layout.row(align=True)
        row.prop(context.preferences.addons[__name__].preferences, "output_folder_path")


class ImportSettings(bpy.types.PropertyGroup):
    include_volume_boxes: bpy.props.BoolProperty(
        name="Include nodes with volume boxes",
        description="",
        default=True
    )

    include_volume_spheres: bpy.props.BoolProperty(
        name="Include nodes with volume spheres",
        description="",
        default=True
    )

    include_visibility: bpy.props.BoolProperty(
        name="Hide nodes with m_bVisible == false",
        description="",
        default=False
    )


class CUSTOM_PT_HitmanAbsolutionImportOptions(bpy.types.Panel):
    bl_idname = 'CUSTOM_PT_HitmanAbsolutionImportOptions'
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_label = 'Map Import Options'
    bl_parent_id = 'CUSTOM_PT_HitmanAbsolutionPanel'
    bl_options = {'DEFAULT_CLOSED'}

    def draw(self, context):
        layout = self.layout
        layout.use_property_split = False
        layout.use_property_decorate = False

        row = layout.row(align=True)
        row.prop(context.scene.import_settings, "include_volume_boxes")
        row = layout.row(align=True)
        row.prop(context.scene.import_settings, "include_volume_spheres")
        row = layout.row(align=True)
        row.prop(context.scene.import_settings, "include_visibility")


class CUSTOM_ModelData(bpy.types.PropertyGroup):
    index: bpy.props.IntProperty()
    prim_id_high: bpy.props.IntProperty()
    prim_id_low: bpy.props.IntProperty()
    prim_file_name: bpy.props.StringProperty()


def get_selected_scene_index(enum_value, enum_items):
    for index, item in enumerate(enum_items):
        if item.identifier == enum_value:
            return index
    return -1


def on_dropdown_value_change(self, context):
    scene = bpy.context.scene
    enum_value = scene.custom_dropdown_property
    enum_items = bpy.types.Scene.bl_rna.properties["custom_dropdown_property"].enum_items
    selected_scene_index = get_selected_scene_index(enum_value, enum_items) - 1

    runtime_folder_path = context.preferences.addons[__name__].preferences.runtime_folder_path.encode()
    output_folder_path = context.preferences.addons[__name__].preferences.output_folder_path

    hma.load_data(context, selected_scene_index, runtime_folder_path, output_folder_path)


class CUSTOM_OT_LoadModel(bpy.types.Operator):
    bl_idname = "custom.load_model"
    bl_label = "Load Model"
    bl_description = "Load Hitman Absolution Model"
    bl_options = {'INTERNAL'}

    def execute(self, context):
        try:
            item = context.scene.custom[context.scene.custom_index]
        except IndexError:
            return{'FINISHED'}

        prim_runtime_resource_id = (hmaexport.to_unsigned_32(item.prim_id_high) << 32) | hmaexport.to_unsigned_32(item.prim_id_low)
        output_folder_path = context.preferences.addons[__name__].preferences.output_folder_path

        obj = hma.import_model_in_blender(context, prim_runtime_resource_id, hma.scene_json["Scene"][item.index], item.name, None, item.prim_file_name)
        obj.matrix_local = (
            (1.0, 0.0, 0.0, 0.0),
            (0.0, 1.0, 0.0, 0.0),
            (0.0, 0.0, 1.0, 0.0),
            (0.0, 0.0, 0.0, 1.0)
        )

        return{'FINISHED'}


class CUSTOM_OT_LoadMap(bpy.types.Operator):
    bl_idname = "custom.load_map"
    bl_label = "Load Map"
    bl_description = "Load Hitman Absolution Map"
    bl_options = {'INTERNAL'}

    def execute(self, context):
        hma.import_map(context)

        return{'FINISHED'}


classes = (
    Preferences,
    ImportSettings,
    CUSTOM_UL_Items,
    CUSTOM_PT_HitmanAbsolutionPanel,
    CUSTOM_PT_HitmanAbsolutionImportOptions,
    CUSTOM_ModelData,
    CUSTOM_OT_LoadModel,
    CUSTOM_OT_LoadMap,
)


def register():
    from bpy.utils import register_class
    for cls in classes:
        register_class(cls)

    scenes = [
        ("None", "None", ""),
        ("l01", "A Personal Contract", ""),
        ("l01b", "The King of Chinatown", ""),
        ("l02b", "Terminus", ""),
        ("l02c", "Run For Your Life", ""),
        ("l02d", "Hunter and Hunted", ""),
        ("l03", "Rosewood", ""),
        ("l04b", "Welcome to Hope", ""),
        ("l04c", "Birdies Gift", ""),
        ("l04d", "Shaving Lenny", ""),
        ("l04e", "End of the Road", ""),
        ("l05a", "Dexter Industries", ""),
        ("l05b", "Death Factory", ""),
        ("l05c", "Fight Night", ""),
        ("l06a", "Attack of the Saints", ""),
        ("l06d", "Skurkys Law", ""),
        ("l07a", "Operation Sledgehammer", ""),
        ("l08a", "One of a Kind", ""),
        ("l08b", "Blackwater Park", ""),
        ("l09", "Countdown", ""),
        ("l10", "Absolution", ""),
    ]

    bpy.types.Scene.custom = bpy.props.CollectionProperty(type=CUSTOM_ModelData)
    bpy.types.Scene.custom_index = bpy.props.IntProperty()
    bpy.types.Scene.import_settings = bpy.props.PointerProperty(type=ImportSettings)
    bpy.types.Scene.custom_dropdown_property = bpy.props.EnumProperty(
        items=scenes,
        update=on_dropdown_value_change,
        name="Scene",
        description="Select scene to import",
    )


def unregister():
    from bpy.utils import unregister_class
    for cls in reversed(classes):
        unregister_class(cls)

    del bpy.types.Scene.custom
    del bpy.types.Scene.custom_index
    del bpy.types.Scene.import_settings
    del bpy.types.Scene.custom_dropdown_property


if __name__ == "__main__":
    register()
    