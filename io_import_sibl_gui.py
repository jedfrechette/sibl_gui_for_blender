# ***** BEGIN GPL LICENSE BLOCK *****
#
#
# This program is free software; you can redistribute it and/or
# modify it under the terms of the GNU General Public License
# as published by the Free Software Foundation; either version 2
# of the License, or (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.    See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software Foundation,
# Inc., 51 Franklin Street, Fifth Floor, Boston, MA 02110-1301, USA.
#
# ***** END GPL LICENCE BLOCK *****

bl_info = {"name": "sIBL_GUI for Blender",
           "description": "Import image-based lighting setup from sIBL GUI.",
           "author": "Jed Frechette <jedfrechette@gmail.com>",
           "version": (0, 1),
           "blender": (2, 68, 0),
           "location": "File > Import",
           "wiki_url": "TODO: Add to wiki",
           "tracker_url": "TODO: Add to tracker",
           "category": "Import-Export"}

# Standard library imports
import sys
from imp import reload
from ipaddress import ip_address
from os import path
from shutil import which
from socketserver import BaseRequestHandler, ThreadingMixIn, TCPServer
from subprocess import Popen
from threading import Thread

# Blender imports
import bpy
from bpy_extras.io_utils import ImportHelper
from bpy.props import IntProperty, StringProperty
from bpy.types import AddonPreferences, Operator, Panel

def get_host(self):
    """Return hostname string."""
    if 'hostname' in self.keys():
        host = self['hostname']
    else:
        host = 'localhost'
    return host

def set_host(self, value):
    """Set hostname to a valid ip address or 'localhost'."""
    if value != 'localhost':
        try:
            ip_address(value)
        except ValueError:
            value = 'localhost'
    self['hostname'] = value

def get_sibl_gui(self):
    """Return full path to sIBL GUI or empty sting."""
    if 'sibl_gui_path' in self.keys():
        gui_path = self['sibl_gui_path']
    else:
        gui_path = ''

    if not gui_path:
        found_path = which('sIBL_GUI')
        if found_path:
            gui_path = found_path
    return gui_path

def set_sibl_gui(self, value):
    """Return full path to sIBL GUI or empty string."""
    if not path.isfile(value):
        value = ''
    self['sibl_gui_path'] = value

class TCPHandler(BaseRequestHandler):
    """Handle TCP  communication with sIBL GUI client."""
    def handle(self):
        self.data = self.request.recv(1024).strip()
        bpy.ops.import_sibl_gui.script_import(filepath=self.data.decode('utf-8'))

class StartTCPServer(Operator):
    """Start sIBL GUI TCP server"""
    bl_idname = "import_sibl_gui.start_server"
    bl_label = "Start Server"

    def execute(self, context):
        if not bpy.sibl_gui_server:
            try:
                host = context.user_preferences.addons[__name__].preferences.hostname
                port = context.user_preferences.addons[__name__].preferences.port
                bpy.sibl_gui_server = ServerSIBLGUI((host, port), TCPHandler)
            except OSError as error:
                if error.errno == 98:
                    self.report({'ERROR'}, "Address already in use")
                    return {'CANCELLED'}
            server_thread = Thread(target=bpy.sibl_gui_server.serve_forever)
            server_thread.daemon = True
            server_thread.start()

        return {'FINISHED'}

class StopTCPServer(Operator):
    """Stop sIBL GUI TCP server"""
    bl_idname = "import_sibl_gui.stop_server"
    bl_label = "Stop Server"

    def execute(self, context):
        if bpy.sibl_gui_server:
            bpy.sibl_gui_server.shutdown()
            bpy.sibl_gui_server = None
        return {'FINISHED'}

class ServerSIBLGUI(ThreadingMixIn, TCPServer):
    """TCP server for connecting to sIBL GUI."""
    allow_reuse_address = True

class LaunchSIBLGUI(Operator):
    """Launch sIBL GUI application"""
    bl_idname = "import_sibl_gui.lauch_sibl_gui"
    bl_label = "Launch sIBL GUI"

    def execute(self, context):
        app = context.user_preferences.addons[__name__].preferences.sibl_gui_path
        if app:
            Popen([app])
            self.report({'INFO'}, "Launching sIBL GUI, please wait a moment.")
        else:
            self.report({'ERROR'}, "Executable not found.\n" \
                                   "Specify the path to sIBL GUI in the Addon preferences.")
            return{'CANCELLED'}
        return {'FINISHED'}

class PreferencesSIBLGUI(AddonPreferences):
    """sIBL GUI addon preferences."""
    bl_idname = __name__

    hostname = StringProperty(name="Host", get=get_host, set=set_host,
                              description="sIBL GUI command host name")
    port = IntProperty(name="Port", default=2048,
                       description="sIBL GUI command port")
    sibl_gui_path = StringProperty(name="sIBL GUI Location",
                                   description="Path to sIBL GUI executable",
                                   get=get_sibl_gui,
                                   set=set_sibl_gui,
                                   subtype="FILE_PATH")

    def draw(self, context):
        layout = self.layout
        layout.prop(self, "hostname")
        layout.prop(self, "port")
        layout.prop(self, "sibl_gui_path")

class PanelSIBLGUI(Panel):
    """Panel in the scene context for connecting to sIBL GUI."""
    bl_idname = "IMPORT_SIBL_GUI_server"
    bl_label = "sIBL GUI"
    bl_space_type = 'PROPERTIES'
    bl_region_type = 'WINDOW'
    bl_context = "scene"
    bl_options = {'DEFAULT_CLOSED'}

    def draw(self, context):
        layout = self.layout
        row = layout.row()
        row.operator("import_sibl_gui.lauch_sibl_gui")
        row = layout.row()
        if bpy.sibl_gui_server:
            address, port = bpy.sibl_gui_server.server_address
            row.label(text="TCP Server Running")
            row = layout.row()
            row.label(text="Address: %s" % address)
            row = layout.row()
            row.label(text="Port: %s" % port)
        else:
            row.label(text="TCP Server Not Running")
        row = layout.row()
#        row.prop(bpy.ops.import_sibl_guil.start_server, "port")
        row.operator("import_sibl_gui.start_server")
        row.operator("import_sibl_gui.stop_server")

class ImportSIBLGUI(Operator, ImportHelper):
    """Import image-based lighting setup from sIBL GUI loader script."""
    bl_idname = "import_sibl_gui.script_import"
    bl_label = "Load sIBL GUI script (.py)"
    bl_options = {'REGISTER', 'UNDO'}

    # ImportHelper mixin class uses this
    filename_ext = ".py"

    filter_glob = StringProperty(default="*.py", options={'HIDDEN'})

    def execute(self, context):
        script_dir = path.dirname(self.filepath)
        if script_dir not in sys.path:
            sys.path.append(script_dir)
        import sIBL_Blender_Cycles_Import as sibl_gui
        if 'setup_sibl' in dir(bpy.ops.import_sibl_gui):
            bpy.utils.unregister_class(sibl_gui.SetupSIBL)

        reload(sibl_gui)
        bpy.utils.register_class(sibl_gui.SetupSIBL)

        bpy.ops.import_sibl_gui.setup_sibl()

        return {'FINISHED'}

def menu_func_import(self, context):
    self.layout.operator(ImportSIBLGUI.bl_idname,
                         text=ImportSIBLGUI.bl_label)

def register():
    bpy.sibl_gui_server = None

    bpy.utils.register_module(__name__)
    bpy.types.INFO_MT_file_import.append(menu_func_import)

def unregister():
    bpy.sibl_gui_server.shutdown()
    del(bpy.sibl_gui_server)

    bpy.utils.unregister_module(__name__)
    bpy.types.INFO_MT_file_import.remove(menu_func_import)

if __name__ == "__main__":
    register()
