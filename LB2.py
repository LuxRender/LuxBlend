#!BPY
"""Registration info for Blender menus:
Name: 'LuxBlend CVS Exporter - 2nd Generation'
Blender: 248
Group: 'Render'
Tooltip: 'Export/Render to LuxRender CVS scene format (.lxs)'
"""
#===============================================================================
#
# ***** BEGIN GPL LICENSE BLOCK *****
#
#------------------------------------------------------------------------------ 
# LuxBlend CVS exporter
#------------------------------------------------------------------------------ 
#
# LuxBlend Authors:
# radiance, zuegs, ideasman42, luxblender
#
# LB2 constructed From LuxBlend by:
# dougal2
#
# This program is free software; you can redistribute it and/or
# modify it under the terms of the GNU General Public License
# as published by the Free Software Foundation; either version 2
# of the License, or (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software Foundation,
# Inc., 59 Temple Place - Suite 330, Boston, MA  02111-1307, USA.
#
# ***** END GPL LICENCE BLOCK *****
#
#===============================================================================

#===============================================================================
# IMPORT FROM PYTHON AND BLENDER
#===============================================================================

import math, os, sys as osys, types, subprocess, types
import Blender


#===============================================================================
# Lux Class
#===============================================================================
class Lux:
    '''Lux Export Class'''
    
    # Material stuff ?
    dummyMat        = 2394723948
    clayMat         = None
    MatSaved        = False
    
    # lists
    meshlist        = None
    matnames        = None
    
    # filenames
    geom_filename   = None
    geom_pfilename  = None
    mat_filename    = None
    mat_pfilename   = None
    vol_filename    = None
    vol_pfilename   = None
    
    # enabled features ('instances')
    i_gui           = False
    i_lrmdb         = False
    
    # current scene
    scene           = None
    
    # dictionary that will hold all preview images
    previewCache    = {}
    
    # Event IDs
    class Events:
        LuxGui           = 99
        SavePreset       = 98
        DeletePreset     = 97
        SaveMaterial     = 96
        LoadMaterial     = 95
        DeleteMaterial   = 94
        # what heppened to 93 ?
        ConvertMaterial  = 92
        SaveMaterial2    = 91
        LoadMaterial2    = 90

    # Property lists
    usedproperties = {} # global variable to collect used properties for storing presets
    usedpropertiesfilterobj = None # assign a object to only collect the properties that are assigned to this object
    
    @staticmethod
    def exportMaterial(mat):
        '''Export Material Section'''
        str = "# Material '%s'\n" % mat.name
        return str + Lux.Material(mat) + "\n"
    
    @staticmethod
    def exportMaterialGeomTag(mat):
        return "%s\n"%(Lux.Property(mat, "link", "").get())
    
    @staticmethod
    def save_lux(filename, unindexedname):
        '''EXPORT'''
        
        export_total_steps = 12.0
        
        print("Lux Render Export started...\n")
        time1 = Blender.sys.time()
        Lux.scene = Blender.Scene.GetCurrent()
    
        filepath = os.path.dirname(filename)
        filebase = os.path.splitext(os.path.basename(filename))[0]
    
        Lux.geom_filename  = os.path.join(filepath, filebase + "-geom.lxo")
        Lux.geom_pfilename = filebase + "-geom.lxo"
    
        Lux.mat_filename  = os.path.join(filepath, filebase + "-mat.lxm")
        Lux.mat_pfilename = filebase + "-mat.lxm"
        
        Lux.vol_filename  = os.path.join(filepath, filebase + "-vol.lxv")
        Lux.vol_pfilename = filebase + "-vol.lxv"
    
        ### Zuegs: initialization for export class
        export = Lux.Export(Lux.scene)
    
        # check if a light is present
        envtype = Lux.Property(Lux.scene, "env.type", "infinite").get()
        if envtype == "sunsky":
            sun = None
            for obj in Lux.scene.objects:
                if (obj.getType() == "Lamp") and ((obj.Layers & Lux.scene.Layers) > 0):
                    if obj.getData(mesh=1).getType() == 1: # sun object # data
                        sun = obj
        if not(export.analyseScene()) and not(envtype == "infinite") and not((envtype == "sunsky") and (sun != None)):
            print("ERROR: No light source found")
            Blender.Draw.PupMenu("ERROR: No light source found%t|OK%x1")
            return False
    
        if Lux.i_gui: Blender.Window.DrawProgressBar(0.0/export_total_steps,'Setting up Scene file')
        if Lux.Property(Lux.scene, "lxs", "true").get()=="true":
            ##### Determine/open files
            print("Exporting scene to '" + filename + "'...\n")
            file = open(filename, 'w')
    
            ##### Write Header ######
            file.write("# Lux Render CVS Scene File\n")
            file.write("# Exported by LuxBlend Blender Exporter\n")
            file.write("\n")
        
            ##### Write camera ######
            camObj = Lux.scene.getCurrentCamera()
    
            if Lux.i_gui: Blender.Window.DrawProgressBar(1.0/export_total_steps,'Exporting Camera')
            if camObj:
                print "processing Camera..."
                cam = camObj.data
                cammblur = Lux.Property(cam, "cammblur", "true")
                usemblur = Lux.Property(cam, "usemblur", "false")
    
                matrix = camObj.getMatrix()
    
                motion = None
                if(cammblur.get() == "true" and usemblur.get() == "true"):
                    # motion blur
                    frame = Blender.Get('curframe')
                    Blender.Set('curframe', frame+1)
                    m1 = 1.0*matrix # multiply by 1.0 to get a copy of original matrix (will be frame-independant) 
                    Blender.Set('curframe', frame)
                    if m1 != matrix:
                        # Motion detected, write endtransform
                        print "  motion blur"
                        motion = m1
                        pos = m1[3]
                        forwards = -m1[2]
                        target = pos + forwards
                        up = m1[1]
                        file.write("TransformBegin\n")
                        file.write("   LookAt %f %f %f \n       %f %f %f \n       %f %f %f\n" % ( pos[0], pos[1], pos[2], target[0], target[1], target[2], up[0], up[1], up[2] ))
                        file.write("   CoordinateSystem \"CameraEndTransform\"\n")
                        file.write("TransformEnd\n\n")
    
                # Write original lookat transform
                pos = matrix[3]
                forwards = -matrix[2]
                target = pos + forwards
                up = matrix[1]
                file.write("LookAt %f %f %f \n       %f %f %f \n       %f %f %f\n\n" % ( pos[0], pos[1], pos[2], target[0], target[1], target[2], up[0], up[1], up[2] ))
                file.write(Lux.Camera(camObj.data, Lux.scene.getRenderingContext()))
                if motion:
                    file.write("\n   \"string endtransform\" [\"CameraEndTransform\"]")
                file.write("\n")
            file.write("\n")
        
            if Lux.i_gui: Blender.Window.DrawProgressBar(2.0/export_total_steps,'Exporting Film Settings')
            ##### Write film ######
            file.write(Lux.SceneElements.Film())
            file.write("\n")
    
            if Lux.i_gui: Blender.Window.DrawProgressBar(3.0/export_total_steps,'Exporting Pixel Filter')
            ##### Write Pixel Filter ######
            file.write(Lux.SceneElements.PixelFilter(Lux.scene))
            file.write("\n")
        
            if Lux.i_gui: Blender.Window.DrawProgressBar(4.0/export_total_steps,'Exporting Sampler')
            ##### Write Sampler ######
            file.write(Lux.SceneElements.Sampler(Lux.scene))
            file.write("\n")
        
            if Lux.i_gui: Blender.Window.DrawProgressBar(5.0/export_total_steps,'Exporting Surface Integrator')
            ##### Write Surface Integrator ######
            file.write(Lux.SceneElements.SurfaceIntegrator(Lux.scene))
            file.write("\n")
            
            if Lux.i_gui: Blender.Window.DrawProgressBar(6.0/export_total_steps,'Exporting Volume Integrator')
            ##### Write Volume Integrator ######
            file.write(Lux.SceneElements.VolumeIntegrator(Lux.scene))
            file.write("\n")
            
            if Lux.i_gui: Blender.Window.DrawProgressBar(7.0/export_total_steps,'Exporting Accelerator')
            ##### Write Acceleration ######
            file.write(Lux.SceneElements.Accelerator(Lux.scene))
            file.write("\n")    
        
            ########## BEGIN World
            file.write("\n")
            file.write("WorldBegin\n")
            file.write("\n")
    
            ########## World scale
            scale = Lux.Property(Lux.scene, "global.scale", 1.0).get()
            if scale != 1.0:
                # TODO: not working yet !!!
                # TODO: propabily scale needs to be applyed on camera coords too 
                file.write("Transform [%s 0.0 0.0 0.0  0.0 %s 0.0 0.0  0.0 0.0 %s 0.0  0.0 0.0 0 1.0]\n"%(scale, scale, scale))
                file.write("\n")
            
            if Lux.i_gui: Blender.Window.DrawProgressBar(8.0/export_total_steps,'Exporting Environment')
            ##### Write World Background, Sunsky or Env map ######
            env = Lux.SceneElements.Environment(Lux.scene)
            if env != "":
                file.write("AttributeBegin\n")
                file.write(env)
                export.Portals(file)
                file.write("AttributeEnd\n")
                file.write("\n")    
    
            # Note - radiance - this is a work in progress
            #flash = Lux.ExperimentalFlashBlock(camObj)
            #if flash != "":
            #    file.write("# Camera flash lamp\n")
            #    file.write("AttributeBegin\n")
            #    #file.write("CoordSysTransform \"camera\"\n")
            #    file.write(flash)
            #    file.write("AttributeEnd\n\n")
    
            #### Write material & geometry file includes in scene file
            file.write("Include \"%s\"\n\n" %(Lux.mat_pfilename))
            file.write("Include \"%s\"\n\n" %(Lux.geom_pfilename))
            file.write("Include \"%s\"\n\n" %(Lux.vol_pfilename))
            
            #### Write End Tag
            file.write("WorldEnd\n\n")
            file.close()
            
        if Lux.Property(Lux.scene, "lxm", "true").get()=="true":
            if Lux.i_gui: Blender.Window.DrawProgressBar(9.0/export_total_steps,'Exporting Materials')
            ##### Write Material file #####
            print("Exporting materials to '" + Lux.mat_filename + "'...\n")
            mat_file = open(Lux.mat_filename, 'w')
            mat_file.write("")
            export.Materials(mat_file)
            mat_file.write("")
            mat_file.close()
        
        if Lux.Property(Lux.scene, "lxo", "true").get()=="true":
            if Lux.i_gui: Blender.Window.DrawProgressBar(10.0/export_total_steps,'Exporting Geometry')
            ##### Write Geometry file #####
            print("Exporting geometry to '" + Lux.geom_filename + "'...\n")
            geom_file = open(Lux.geom_filename, 'w')
            Lux.meshlist = []
            geom_file.write("")
            export.Lights(geom_file)
            export.Meshes(geom_file)
            export.Objects(geom_file)
            geom_file.write("")
            geom_file.close()
    
        if Lux.Property(Lux.scene, "lxv", "true").get()=="true":
            if Lux.i_gui: Blender.Window.DrawProgressBar(11.0/export_total_steps,'Exporting Volumes')
            ##### Write Volume file #####
            print("Exporting volumes to '" + Lux.vol_filename + "'...\n")
            vol_file = open(Lux.vol_filename, 'w')
            Lux.meshlist = []
            vol_file.write("")
            export.Volumes(vol_file)
            vol_file.write("")
            vol_file.close()
        
        if Lux.i_gui: Blender.Window.DrawProgressBar(12.0/export_total_steps,'Export Finished')
        print("Finished.\n")
        del export
    
        time2 = Blender.sys.time()
        print("Processing time: %f\n" %(time2-time1))
        return True
    
    
    
    @staticmethod
    def save_anim(filename):
        startF = Blender.Get('staframe')
        endF = Blender.Get('endframe')
        Lux.scene = Blender.Scene.GetCurrent()
        Run = Lux.Property(Lux.scene, "run", "true").get()
    
        print("\n\nRendering animation (frame %i to %i)\n\n"%(startF, endF))
    
        for i in range (startF, endF+1):
            Blender.Set('curframe', i)
            print("Rendering frame %i"%(i))
            Blender.Redraw()
            frameindex = ("-%05d" % (i)) + ".lxs"
            indexedname = sys.makename(filename, frameindex)
            unindexedname = filename
            Lux.Property(Lux.scene, "filename", Blender.Get("filename")).set(sys.makename(filename, "-%05d" %  (Blender.Get('curframe'))))
    
            success = Lux.save_lux(filename, unindexedname) 
            if Run == "true" and success:
                Lux.Launch.Wait(filename)
    
            Lux.MatSaved = True
    
        print("\n\nFinished Rendering animation\n")
        
    @staticmethod
    def save_still(filename):
        Lux.scene = Blender.Scene.GetCurrent()
        Lux.Property(Lux.scene, "filename", Blender.Get("filename")).set(sys.makename(filename, ""))
        Lux.MatSaved = False
        unindexedname = filename
        if Lux.save_lux(filename, unindexedname) and Lux.runRenderAfterExport:
            Lux.Launch.Normal(filename)
    
    class Presets:
        newluxdefaults      = {}
        presetsExclude = ['preset','lux','datadir','threads','filename','page','RGC','film.gamma','colorclamp','link']
        
        def __init__(self):
            # default settings
            defaultsExclude = ['preset','filename','page','link']
            try:
                luxdefaults = Blender.Registry.GetKey('luxblend', True)
                if not(type(luxdefaults) is types.DictType):
                    luxdefaults = {}
            except:
                luxdefaults = {}
            
            newluxdefaults = luxdefaults.copy()
            
        def saveluxdefaults(self):
            try:
                del self.newluxdefaults['page']
                Blender.Registry.SetKey('luxblend', self.newluxdefaults, True)
            except:
                pass
            
        def getPresets(key):
            presets = Blender.Registry.GetKey(key, True)
            if not(type(presets) is types.DictType):
                presets = {}
            return presets
        
        def getScenePresets():
            presets = self.getPresets('luxblend_presets').copy()
        
            # radiance's hardcoded render presets:
            presets = presets.update({
                '1 Preview - Direct Lighting': {
                    'film.displayinterval': 4,
                    'haltspp': 0,
                    'useparamkeys': 'false',
                    'sampler.showadvanced': 'false',
                    'sintegrator.showadvanced': 'false',
                    'pixelfilter.showadvanced': 'false',
                
                    'sampler.type': 'lowdiscrepancy',
                    'sampler.lowdisc.pixelsamples': 1,
                    'sampler.lowdisc.pixelsampler': 'lowdiscrepancy',
                
                    'sintegrator.type': 'directlighting',
                    'sintegrator.dlighting.maxdepth': 5,
                
                    'pixelfilter.type': 'mitchell',
                    'pixelfilter.mitchell.sharp': 0.333, 
                    'pixelfilter.mitchell.xwidth': 2.0, 
                    'pixelfilter.mitchell.ywidth': 2.0, 
                    'pixelfilter.mitchell.optmode': "slider"
                },
                
                '2 Final - MLT/Bidir Path Tracing (interior) (recommended)': {
                    'film.displayinterval': 8,
                    'haltspp': 0,
                    'useparamkeys': 'false',
                    'sampler.showadvanced': 'false',
                    'sintegrator.showadvanced': 'false',
                    'pixelfilter.showadvanced': 'false',
                
                    'sampler.type': 'metropolis',
                    'sampler.metro.strength': 0.6,
                    'sampler.metro.lmprob': 0.4,
                    'sampler.metro.maxrejects': 512,
                    'sampler.metro.initsamples': 262144,
                    'sampler.metro.stratawidth': 256,
                    'sampler.metro.usevariance': "false",
                
                    'sintegrator.type': 'bidirectional',
                    'sintegrator.bidir.bounces': 10,
                    'sintegrator.bidir.eyedepth': 10,
                    'sintegrator.bidir.lightdepth': 10,
                
                    'pixelfilter.type': 'mitchell',
                    'pixelfilter.mitchell.sharp': 0.333, 
                    'pixelfilter.mitchell.xwidth': 2.0, 
                    'pixelfilter.mitchell.ywidth': 2.0, 
                    'pixelfilter.mitchell.optmode': "slider"
                },
        
                '3 Final - MLT/Path Tracing (exterior)': {
                    'film.displayinterval': 8,
                    'haltspp': 0,
                    'useparamkeys': 'false',
                    'sampler.showadvanced': 'false',
                    'sintegrator.showadvanced': 'false',
                    'pixelfilter.showadvanced': 'false',
                
                    'sampler.type': 'metropolis',
                    'sampler.metro.strength': 0.6,
                    'sampler.metro.lmprob': 0.4,
                    'sampler.metro.maxrejects': 512,
                    'sampler.metro.initsamples': 262144,
                    'sampler.metro.stratawidth': 256,
                    'sampler.metro.usevariance': "false",
                
                    'sintegrator.type': 'path',
                    'sintegrator.bidir.bounces': 10,
                    'sintegrator.bidir.maxdepth': 10,
                
                    'pixelfilter.type': 'mitchell',
                    'pixelfilter.mitchell.sharp': 0.333, 
                    'pixelfilter.mitchell.xwidth': 2.0, 
                    'pixelfilter.mitchell.ywidth': 2.0, 
                    'pixelfilter.mitchell.optmode': "slider"
                },
                
                '4 ': {},
        
                '5 Progressive - Bidir Path Tracing (interior)': {
                    'film.displayinterval': 8,
                    'haltspp': 0,
                    'useparamkeys': 'false',
                    'sampler.showadvanced': 'false',
                    'sintegrator.showadvanced': 'false',
                    'pixelfilter.showadvanced': 'false',
                
                    'sampler.type': 'lowdiscrepancy',
                    'sampler.lowdisc.pixelsamples': 1,
                    'sampler.lowdisc.pixelsampler': 'lowdiscrepancy',
                
                    'sintegrator.type': 'bidirectional',
                    'sintegrator.bidir.bounces': 10,
                    'sintegrator.bidir.eyedepth': 10,
                    'sintegrator.bidir.lightdepth': 10,
                
                    'pixelfilter.type': 'mitchell',
                    'pixelfilter.mitchell.sharp': 0.333, 
                    'pixelfilter.mitchell.xwidth': 2.0, 
                    'pixelfilter.mitchell.ywidth': 2.0, 
                    'pixelfilter.mitchell.optmode': "slider"
                },
        
                '6 Progressive - Path Tracing (exterior)': {
                    'film.displayinterval': 8,
                    'haltspp': 0,
                    'useparamkeys': 'false',
                    'sampler.showadvanced': 'false',
                    'sintegrator.showadvanced': 'false',
                    'pixelfilter.showadvanced': 'false',
                
                    'sampler.type': 'lowdiscrepancy',
                    'sampler.lowdisc.pixelsamples': 1,
                    'sampler.lowdisc.pixelsampler': 'lowdiscrepancy',
                
                    'sintegrator.type': 'path',
                    'sintegrator.bidir.bounces': 10,
                    'sintegrator.bidir.maxdepth': 10,
                
                    'pixelfilter.type': 'mitchell',
                    'pixelfilter.mitchell.sharp': 0.333, 
                    'pixelfilter.mitchell.xwidth': 2.0, 
                    'pixelfilter.mitchell.ywidth': 2.0, 
                    'pixelfilter.mitchell.optmode': "slider"
                },
        
                '7 ': {},
        
                '8 Bucket - Bidir Path Tracing (interior)': {
                    'film.displayinterval': 8,
                    'haltspp': 0,
                    'useparamkeys': 'false',
                    'sampler.showadvanced': 'false',
                    'sintegrator.showadvanced': 'false',
                    'pixelfilter.showadvanced': 'false',
                
                    'sampler.type': 'lowdiscrepancy',
                    'sampler.lowdisc.pixelsamples': 64,
                    'sampler.lowdisc.pixelsampler': 'hilbert',
                
                    'sintegrator.type': 'bidirectional',
                    'sintegrator.bidir.bounces': 8,
                    'sintegrator.bidir.eyedepth': 8,
                    'sintegrator.bidir.lightdepth': 10,
                
                    'pixelfilter.type': 'mitchell',
                    'pixelfilter.mitchell.sharp': 0.333, 
                    'pixelfilter.mitchell.xwidth': 2.0, 
                    'pixelfilter.mitchell.ywidth': 2.0, 
                    'pixelfilter.mitchell.optmode': "slider"
                },
        
                '9 Bucket - Path Tracing (exterior)': {
                    'film.displayinterval': 8,
                    'haltspp': 0,
                    'useparamkeys': 'false',
                    'sampler.showadvanced': 'false',
                    'sintegrator.showadvanced': 'false',
                    'pixelfilter.showadvanced': 'false',
                
                    'sampler.type': 'lowdiscrepancy',
                    'sampler.lowdisc.pixelsamples': 64,
                    'sampler.lowdisc.pixelsampler': 'hilbert',
                
                    'sintegrator.type': 'path',
                    'sintegrator.bidir.bounces': 8,
                    'sintegrator.bidir.maxdepth': 8,
                
                    'pixelfilter.type': 'mitchell',
                    'pixelfilter.mitchell.sharp': 0.333, 
                    'pixelfilter.mitchell.xwidth': 2.0, 
                    'pixelfilter.mitchell.ywidth': 2.0, 
                    'pixelfilter.mitchell.optmode': "slider"
                },
        
                'A ': {},
        
                'B Anim - Distributed/GI low Q': {
                    'film.displayinterval': 8,
                    'haltspp': 1,
                    'useparamkeys': 'false',
                    'sampler.showadvanced': 'false',
                    'sintegrator.showadvanced': 'false',
                    'pixelfilter.showadvanced': 'false',
                
                    'sampler.type': 'lowdiscrepancy',
                    'sampler.lowdisc.pixelsamples': 16,
                    'sampler.lowdisc.pixelsampler': 'hilbert',
                
                    'sintegrator.type': 'distributedpath',
                    'sintegrator.distributedpath.causticsonglossy': 'true',
                    'sintegrator.distributedpath.diffuserefractdepth': 5,
                    'sintegrator.distributedpath.indirectglossy': 'true',
                    'sintegrator.distributedpath.directsamples': 1,
                    'sintegrator.distributedpath.diffuserefractsamples': 1,
                    'sintegrator.distributedpath.glossyreflectdepth': 2,
                    'sintegrator.distributedpath.causticsondiffuse': 'false',
                    'sintegrator.distributedpath.directsampleall': 'true',
                    'sintegrator.distributedpath.indirectdiffuse': 'true',
                    'sintegrator.distributedpath.specularreflectdepth': 3,
                    'sintegrator.distributedpath.diffusereflectsamples': 1,
                    'sintegrator.distributedpath.glossyreflectsamples': 1,
                    'sintegrator.distributedpath.glossyrefractdepth': 5,
                    'sintegrator.distributedpath.diffusereflectdepth': '2',
                    'sintegrator.distributedpath.indirectsamples': 1,
                    'sintegrator.distributedpath.indirectsampleall': 'false',
                    'sintegrator.distributedpath.glossyrefractsamples': 1,
                    'sintegrator.distributedpath.directdiffuse': 'true',
                    'sintegrator.distributedpath.directglossy': 'true',
                    'sintegrator.distributedpath.strategy': 'auto',
                    'sintegrator.distributedpath.specularrefractdepth': 5,
                
                    'pixelfilter.type': 'mitchell',
                    'pixelfilter.mitchell.sharp': 0.333, 
                    'pixelfilter.mitchell.xwidth': 2.0, 
                    'pixelfilter.mitchell.ywidth': 2.0, 
                    'pixelfilter.mitchell.optmode': "slider"
                },
        
                'C Anim - Distributed/GI medium Q': {
                    'film.displayinterval': 8,
                    'haltspp': 1,
                    'useparamkeys': 'false',
                    'sampler.showadvanced': 'false',
                    'sintegrator.showadvanced': 'false',
                    'pixelfilter.showadvanced': 'false',
                
                    'sampler.type': 'lowdiscrepancy',
                    'sampler.lowdisc.pixelsamples': 64,
                    'sampler.lowdisc.pixelsampler': 'hilbert',
                
                    'sintegrator.type': 'distributedpath',
                    'sintegrator.distributedpath.causticsonglossy': 'true',
                    'sintegrator.distributedpath.diffuserefractdepth': 5,
                    'sintegrator.distributedpath.indirectglossy': 'true',
                    'sintegrator.distributedpath.directsamples': 1,
                    'sintegrator.distributedpath.diffuserefractsamples': 1,
                    'sintegrator.distributedpath.glossyreflectdepth': 2,
                    'sintegrator.distributedpath.causticsondiffuse': 'false',
                    'sintegrator.distributedpath.directsampleall': 'true',
                    'sintegrator.distributedpath.indirectdiffuse': 'true',
                    'sintegrator.distributedpath.specularreflectdepth': 3,
                    'sintegrator.distributedpath.diffusereflectsamples': 1,
                    'sintegrator.distributedpath.glossyreflectsamples': 1,
                    'sintegrator.distributedpath.glossyrefractdepth': 5,
                    'sintegrator.distributedpath.diffusereflectdepth': '2',
                    'sintegrator.distributedpath.indirectsamples': 1,
                    'sintegrator.distributedpath.indirectsampleall': 'false',
                    'sintegrator.distributedpath.glossyrefractsamples': 1,
                    'sintegrator.distributedpath.directdiffuse': 'true',
                    'sintegrator.distributedpath.directglossy': 'true',
                    'sintegrator.distributedpath.strategy': 'auto',
                    'sintegrator.distributedpath.specularrefractdepth': 5,
                
                    'pixelfilter.type': 'mitchell',
                    'pixelfilter.mitchell.sharp': 0.333, 
                    'pixelfilter.mitchell.xwidth': 2.0, 
                    'pixelfilter.mitchell.ywidth': 2.0, 
                    'pixelfilter.mitchell.optmode': "slider"
                },
            
                'D Anim - Distributed/GI high Q': {
                    'film.displayinterval': 8,
                    'haltspp': 1,
                    'useparamkeys': 'false',
                    'sampler.showadvanced': 'false',
                    'sintegrator.showadvanced': 'false',
                    'pixelfilter.showadvanced': 'false',
                
                    'sampler.type': 'lowdiscrepancy',
                    'sampler.lowdisc.pixelsamples': 256,
                    'sampler.lowdisc.pixelsampler': 'hilbert',
                
                    'sintegrator.type': 'distributedpath',
                    'sintegrator.distributedpath.causticsonglossy': 'true',
                    'sintegrator.distributedpath.diffuserefractdepth': 5,
                    'sintegrator.distributedpath.indirectglossy': 'true',
                    'sintegrator.distributedpath.directsamples': 1,
                    'sintegrator.distributedpath.diffuserefractsamples': 1,
                    'sintegrator.distributedpath.glossyreflectdepth': 2,
                    'sintegrator.distributedpath.causticsondiffuse': 'false',
                    'sintegrator.distributedpath.directsampleall': 'true',
                    'sintegrator.distributedpath.indirectdiffuse': 'true',
                    'sintegrator.distributedpath.specularreflectdepth': 3,
                    'sintegrator.distributedpath.diffusereflectsamples': 1,
                    'sintegrator.distributedpath.glossyreflectsamples': 1,
                    'sintegrator.distributedpath.glossyrefractdepth': 5,
                    'sintegrator.distributedpath.diffusereflectdepth': '2',
                    'sintegrator.distributedpath.indirectsamples': 1,
                    'sintegrator.distributedpath.indirectsampleall': 'false',
                    'sintegrator.distributedpath.glossyrefractsamples': 1,
                    'sintegrator.distributedpath.directdiffuse': 'true',
                    'sintegrator.distributedpath.directglossy': 'true',
                    'sintegrator.distributedpath.strategy': 'auto',
                    'sintegrator.distributedpath.specularrefractdepth': 5,
                
                    'pixelfilter.type': 'mitchell',
                    'pixelfilter.mitchell.sharp': 0.333, 
                    'pixelfilter.mitchell.xwidth': 2.0, 
                    'pixelfilter.mitchell.ywidth': 2.0, 
                    'pixelfilter.mitchell.optmode': "slider"
                },
        
                'E Anim - Distributed/GI very high Q': {
                    'film.displayinterval': 8,
                    'haltspp': 1,
                    'useparamkeys': 'false',
                    'sampler.showadvanced': 'false',
                    'sintegrator.showadvanced': 'false',
                    'pixelfilter.showadvanced': 'false',
                
                    'sampler.type': 'lowdiscrepancy',
                    'sampler.lowdisc.pixelsamples': 512,
                    'sampler.lowdisc.pixelsampler': 'hilbert',
                
                    'sintegrator.type': 'distributedpath',
                    'sintegrator.distributedpath.causticsonglossy': 'true',
                    'sintegrator.distributedpath.diffuserefractdepth': 5,
                    'sintegrator.distributedpath.indirectglossy': 'true',
                    'sintegrator.distributedpath.directsamples': 1,
                    'sintegrator.distributedpath.diffuserefractsamples': 1,
                    'sintegrator.distributedpath.glossyreflectdepth': 2,
                    'sintegrator.distributedpath.causticsondiffuse': 'false',
                    'sintegrator.distributedpath.directsampleall': 'true',
                    'sintegrator.distributedpath.indirectdiffuse': 'true',
                    'sintegrator.distributedpath.specularreflectdepth': 3,
                    'sintegrator.distributedpath.diffusereflectsamples': 1,
                    'sintegrator.distributedpath.glossyreflectsamples': 1,
                    'sintegrator.distributedpath.glossyrefractdepth': 5,
                    'sintegrator.distributedpath.diffusereflectdepth': '2',
                    'sintegrator.distributedpath.indirectsamples': 1,
                    'sintegrator.distributedpath.indirectsampleall': 'false',
                    'sintegrator.distributedpath.glossyrefractsamples': 1,
                    'sintegrator.distributedpath.directdiffuse': 'true',
                    'sintegrator.distributedpath.directglossy': 'true',
                    'sintegrator.distributedpath.strategy': 'auto',
                    'sintegrator.distributedpath.specularrefractdepth': 5,
                
                    'pixelfilter.type': 'mitchell',
                    'pixelfilter.mitchell.sharp': 0.333, 
                    'pixelfilter.mitchell.xwidth': 2.0, 
                    'pixelfilter.mitchell.ywidth': 2.0, 
                    'pixelfilter.mitchell.optmode': "slider"
                }
            })
        
            return presets
        
        def getMaterialPresets():
            return getPresets('luxblend_materials')
        
        def savePreset(key, name, d):
            try:
                presets = getPresets(key)
                if d:
                    presets[name] = d.copy()
                else:
                    del presets[name]
                Blender.Registry.SetKey(key, presets, True)
            except: pass    
        
        def saveScenePreset(name, d):
            try:
                for n in presetsExclude:
                    try: del d[n];
                    except: pass
                savePreset('luxblend_presets', name, d)
            except: pass
            
        def saveMaterialPreset(name, d):
            try:
                for n in presetsExclude:
                    try: del d[n];
                    except: pass
                savePreset('luxblend_materials', name, d)
            except: pass
    
    class Util:
        '''Lux Utilities'''
        
        @staticmethod
        def newFName(ext):
            '''New name based on old with a different extension'''
            return Blender.Get('filename')[: -len(Blender.Get('filename').split('.', -1)[-1]) ] + ext
        
        @staticmethod
        def base64value(char):
            if 64 < ord(char) < 91: return ord(char)-65
            if 96 < ord(char) < 123: return ord(char)-97+26
            if 47 < ord(char) < 58: return ord(char)-48+52
            if char == '+': return 62
            return 63
        
        @staticmethod
        def luxstr(str):
            return str.replace("\\", "\\\\") # todo: do encode \ and " signs by a additional backslash
        
        @staticmethod
        def scalelist(list, factor):
            for i in range(len(list)):
                list[i] = list[i] * factor
            return list
    
    class Colour:
        '''Lux Colour Functions'''
        
        @staticmethod
        def rg(col):
            '''Reverse Gamma Correction'''
            Lux.scene = Blender.Scene.GetCurrent()
            if Lux.Property(Lux.scene, "RGC", "true").get()=="true":
                gamma = Lux.Property(Lux.scene, "film.gamma", 2.2).get()
            else:
                gamma = 1.0
            ncol = col**gamma
            if Lux.Property(Lux.scene, "colorclamp", "false").get()=="true":
                ncol = ncol * 0.9
                if ncol > 0.9:
                    ncol = 0.9
                if ncol < 0.0:
                    ncol = 0.0
            return ncol
        
        @staticmethod
        def texturegamma():
            '''Apply Gamma Value'''
            Lux.scene = Blender.Scene.GetCurrent()
            if Lux.Property(Lux.scene, "RGC", "true").get()=="true":
                return Lux.Property(Lux.scene, "film.gamma", 2.2).get()
            else:
                return 1.0
            
    
            
    class Export:
        '''Lux Export functions'''
        
        @staticmethod
        def getMaterials(obj, compress=False):
            '''Helper function to get the material list of an object in respect of obj.colbits'''
            
            mats = [None]*16
            colbits = obj.colbits
            objMats = obj.getMaterials(1)
            data = obj.getData(mesh=1)
            try:
                dataMats = data.materials
            except:
                try:
                    dataMats = data.getMaterials(1)
                except:
                    dataMats = []
                    colbits = 0xffff
            m = max(len(objMats), len(dataMats))
            if m>0:
                objMats.extend([None]*16)
                dataMats.extend([None]*16)
                for i in range(m):
                    if (colbits & (1<<i) > 0):
                        mats[i] = objMats[i]
                    else:
                        mats[i] = dataMats[i]
                if compress:
                    mats = [m for m in mats if m]
            else:
                print "Warning: object %s has no material assigned" % obj.getName()
                mats = []
            # clay option
            if Lux.Property(Blender.Scene.GetCurrent(), "clay", "false").get()=="true":
                if Lux.clayMat==None: Lux.clayMat = Blender.Material.New("lux_clayMat")
                for i in range(len(mats)):
                    if mats[i]:
                        mattype = Lux.Property(mats[i], "type", "").get()
                        if (mattype not in ["portal","light","boundvolume"]): mats[i] = Lux.clayMat
            return mats
        
        def __init__(self, scene):
            '''initializes the exporter object'''
            self.scene = scene
            self.camera = scene.objects.camera
            self.objects = []
            self.portals = []
            self.volumes = []
            self.meshes = {}
            self.materials = []
            self.lights = []
    
        def analyseObject(self, obj, matrix, name, isOriginal=True):
            '''called by analyseScene to build the lists before export'''
            
            light = False
            if (obj.users > 0):
                obj_type = obj.getType()
                if (obj.enableDupFrames and isOriginal):
                    for o, m in obj.DupObjects:
                        self.analyseObject(o, m, "%s.%s"%(name, o.getName()), False)    
                if (obj.enableDupGroup or obj.enableDupVerts):
                    for o, m in obj.DupObjects:
                        self.analyseObject(o, m, "%s.%s"%(name, o.getName()))    
                elif (obj_type == "Mesh") or (obj_type == "Surf") or (obj_type == "Curve") or (obj_type == "Text"):
                    mats = self.getMaterials(obj)
                    if (len(mats)>0) and (mats[0]!=None) and ((mats[0].name=="PORTAL") or (Lux.Property(mats[0], "type", "").get()=="portal")):
                        self.portals.append([obj, matrix])
                    elif (len(mats)>0) and (Lux.Property(mats[0], "type", "").get()=="boundvolume"):
                        self.volumes.append([obj, matrix])
                    else:
                        for mat in mats:
                            if (mat!=None) and (mat not in self.materials):
                                self.materials.append(mat)
                            if (mat!=None) and ((Lux.Property(mat, "type", "").get()=="light") or (Lux.Property(mat, "emission", "false").get()=="true")):
                                light = True
                        mesh_name = obj.getData(name_only=True)
                        try:
                            self.meshes[mesh_name] += [obj]
                        except KeyError:
                            self.meshes[mesh_name] = [obj]                
                        self.objects.append([obj, matrix])
                elif (obj_type == "Lamp"):
                    ltype = obj.getData(mesh=1).getType() # data
                    if (ltype == Lamp.Types["Lamp"]) or (ltype == Lamp.Types["Spot"]) or (ltype == Lamp.Types["Area"]):
                        self.lights.append([obj, matrix])
                        light = True
            return light
    
        def analyseScene(self):
            '''this function builds the lists of object, lights, meshes and materials before export'''
            
            light = False
            for obj in self.scene.objects:
                if ((obj.Layers & self.scene.Layers) > 0):
                    if self.analyseObject(obj, obj.getMatrix(), obj.getName()): light = True
            return light
    
        def MaterialLink(self, file, mat):
            '''exports material link. LuxRender "Material"'''
            if mat == dummyMat:
                file.write("\tMaterial \"matte\" # dummy material\n")
            else:
                file.write("\t%s" % Lux.exportMaterialGeomTag(mat)) # use original methode
    
        def Material(self, file, mat):
            '''exports material. LuxRender "Texture" '''
            file.write("\t%s" % Lux.exportMaterial(mat)) # use original methode        
        
        def Materials(self, file):
            '''exports materials to the file'''
            
            for mat in self.materials:
                print "material %s"%(mat.getName())
                self.exportMaterial(file, mat)
    
        def getMeshType(self, vertcount, mat):
            '''returns type of mesh as string to use depending on thresholds'''
            #Lux.scene = Blender.Scene.GetCurrent()
            if mat != dummyMat:
                usesubdiv = Lux.Property(mat, "subdiv", "false")
                usedisp = Lux.Property(mat, "dispmap", "false")
                sharpbound = Lux.Property(mat, "sharpbound", "false")
                nsmooth = Lux.Property(mat, "nsmooth", "true")
                sdoffset = Lux.Property(mat, "sdoffset", 0.0)
                dstr = ""
                if usesubdiv.get() == "true":
                    nlevels = Lux.Property(mat, "sublevels", 1)
                    dstr += "\"loopsubdiv\" \"integer nlevels\" [%i] \"bool dmnormalsmooth\" [\"%s\"] \"bool dmsharpboundary\" [\"%s\"]"% (nlevels.get(), nsmooth.get(), sharpbound.get())
                
                if usedisp.get() == "true":
                    dstr += " \"string displacementmap\" [\"%s::dispmap.scale\"] \"float dmscale\" [-1.0] \"float dmoffset\" [%f]"%(mat.getName(), sdoffset.get()) # scale is scaled in texture
    
                if dstr != "": return dstr
    
            return "\"trianglemesh\""
    
        def Mesh(self, file, mesh, mats, name, portal=False):
            '''exports mesh to the file without any optimization'''
            
            if mats == []:
                mats = [dummyMat]
            for matIndex in range(len(mats)):
                if (mats[matIndex] != None):
                    mesh_str = getMeshType(len(mesh.verts), mats[matIndex])
                    if (portal):
                        file.write("\tShape %s \"integer indices\" [\n"% mesh_str)
                    else:
                        self.MaterialLink(file, mats[matIndex])
                        file.write("\tPortalShape %s \"integer indices\" [\n"% mesh_str)
                    index = 0
                    ffaces = [f for f in mesh.faces if f.mat == matIndex]
                    for face in ffaces:
                        file.write("%d %d %d\n"%(index, index+1, index+2))
                        if (len(face)==4):
                            file.write("%d %d %d\n"%(index, index+2, index+3))
                        index += len(face.verts)
                    file.write("\t] \"point P\" [\n");
                    for face in ffaces:
                        for vertex in face:
                            file.write("%f %f %f\n"% tuple(vertex.co))
                    file.write("\t] \"normal N\" [\n")
                    for face in ffaces:
                        normal = face.no
                        for vertex in face:
                            if (face.smooth):
                                normal = vertex.no
                            file.write("%f %f %f\n"% tuple(normal))
                    if (mesh.faceUV):
                        file.write("\t] \"float uv\" [\n")
                        for face in ffaces:
                            for uv in face.uv:
                                file.write("%f %f\n"% tuple(uv))
                    file.write("\t]\n")
    
        def MeshOpt(self, file, mesh, mats, name, portal=False, optNormals=True):
            '''
            exports mesh to the file with optimization.
            portal: export without normals and UVs
            optNormals: speed and filesize optimization, flat faces get exported without normals
            '''
            shapeList, smoothFltr, shapeText = [0], [[0,1]], [""]
            if portal:
                normalFltr, uvFltr, shapeText = [0], [0], ["portal"] # portal, no normals, no UVs
            else:
                uvFltr, normalFltr, shapeText = [1], [1], ["mixed with normals"] # normals and UVs
                if optNormals: # one pass for flat faces without normals and another pass for smoothed faces with normals, all with UVs
                    shapeList, smoothFltr, normalFltr, uvFltr, shapeText = [0,1], [[0],[1]], [0,1], [1,1], ["flat w/o normals", "smoothed with normals"]
            if mats == []:
                mats = [dummyMat]
            for matIndex in range(len(mats)):
                if (mats[matIndex] != None):
                    if not(portal):
                        self.MaterialLink(file, mats[matIndex])
                    for shape in shapeList:
                        blenderExportVertexMap = []
                        exportVerts = []
                        exportFaces = []
                        ffaces = [f for f in mesh.faces if (f.mat == matIndex) and (f.smooth in smoothFltr[shape])]
                        for face in ffaces:
                            exportVIndices = []
                            index = 0
                            for vertex in face:
                                v = [vertex.co]
                                if normalFltr[shape]:
                                    if (face.smooth):
                                        v.append(vertex.no)
                                    else:
                                        v.append(face.no)
                                if (uvFltr[shape]) and (mesh.faceUV):
                                    v.append(face.uv[index])
                                blenderVIndex = vertex.index
                                newExportVIndex = -1
                                length = len(v)
                                if (blenderVIndex < len(blenderExportVertexMap)):
                                    for exportVIndex in blenderExportVertexMap[blenderVIndex]:
                                        v2 = exportVerts[exportVIndex]
                                        if (length==len(v2)) and (v == v2):
                                            newExportVIndex = exportVIndex
                                            break
                                if (newExportVIndex < 0):
                                    newExportVIndex = len(exportVerts)
                                    exportVerts.append(v)
                                    while blenderVIndex >= len(blenderExportVertexMap):
                                        blenderExportVertexMap.append([])
                                    blenderExportVertexMap[blenderVIndex].append(newExportVIndex)
                                exportVIndices.append(newExportVIndex)
                                index += 1
                            exportFaces.append(exportVIndices)
                        if (len(exportVerts)>0):
                            mesh_str = self.getMeshType(len(exportVerts), mats[matIndex])
                            if (portal):
                                file.write("\tPortalShape %s \"integer indices\" [\n"% mesh_str)
                            else:
                                file.write("\tShape %s \"integer indices\" [\n"% mesh_str)
                            for face in exportFaces:
                                file.write("%d %d %d\n"%(face[0], face[1], face[2]))
                                if (len(face)==4):
                                    file.write("%d %d %d\n"%(face[0], face[2], face[3]))
                            file.write("\t] \"point P\" [\n");
                            file.write("".join(["%f %f %f\n"%tuple(vertex[0]) for vertex in exportVerts]))
                            if normalFltr[shape]:
                                file.write("\t] \"normal N\" [\n")
                                file.write("".join(["%f %f %f\n"%tuple(vertex[1]) for vertex in exportVerts])) 
                                if (uvFltr[shape]) and (mesh.faceUV):
                                    file.write("\t] \"float uv\" [\n")
                                    file.write("".join(["%f %f\n"%tuple(vertex[2]) for vertex in exportVerts])) 
                            else:            
                                if (uvFltr[shape]) and (mesh.faceUV):
                                    file.write("\t] \"float uv\" [\n")
                                    file.write("".join(["%f %f\n"%tuple(vertex[1]) for vertex in exportVerts])) 
                            file.write("\t]\n")
                            print "  shape(%s): %d vertices, %d faces"%(shapeText[shape], len(exportVerts), len(exportFaces))
    
        def Meshes(self, file):
            '''exports meshes that uses instancing (meshes that are used by at least "instancing_threshold" objects)'''
            #Lux.scene = Blender.Scene.GetCurrent()
            instancing_threshold = Lux.Property(self.scene, "instancing_threshold", 2).get()
            mesh_optimizing = Lux.Property(seld.scene, "mesh_optimizing", True).get()
            mesh = Mesh.New('')
            for (mesh_name, objs) in self.meshes.items():
                allow_instancing = True
                mats = self.getMaterials(objs[0]) # mats = obj.getData().getMaterials()
                for mat in mats: # don't instance if one of the materials is emissive
                    if (mat!=None) and (Lux.Property(mat, "type", "").get()=="light"):
                        allow_instancing = False
                for obj in objs: # don't instance if the objects with same mesh uses different materials
                    ms = getMaterials(obj)
                    if ms <> mats:
                        allow_instancing = False
                if allow_instancing and (len(objs) >= instancing_threshold):
                    del self.meshes[mesh_name]
                    mesh.getFromObject(objs[0], 0, 1)
                    print "blender-mesh: %s (%d vertices, %d faces)"%(mesh_name, len(mesh.verts), len(mesh.faces))
                    file.write("ObjectBegin \"%s\"\n"%mesh_name)
                    if (mesh_optimizing):
                        self.MeshOpt(file, mesh, mats, mesh_name)
                    else:
                        self.Mesh(file, mesh, mats, mesh_name)
                    file.write("ObjectEnd # %s\n\n"%mesh_name)
            mesh.verts = None
    
        def Objects(self, file):
            '''exports objects to the file'''
            #Lux.scene = Blender.Scene.GetCurrent()
            cam = self.scene.getCurrentCamera().data
            objectmblur = Lux.Property(cam, "objectmblur", "true")
            usemblur = Lux.Property(cam, "usemblur", "false")
            mesh_optimizing = Lux.Property(scene, "mesh_optimizing", True).get()
            mesh = Mesh.New('')
            for [obj, matrix] in self.objects:
                print "object: %s"%(obj.getName())
                mesh_name = obj.getData(name_only=True)
    
                motion = None
                if(objectmblur.get() == "true" and usemblur.get() == "true"):
                    # motion blur
                    frame = Blender.Get('curframe')
                    Blender.Set('curframe', frame+1)
                    m1 = 1.0*matrix # multiply by 1.0 to get a copy of orignal matrix (will be frame-independant) 
                    Blender.Set('curframe', frame)
                    if m1 != matrix:
                        print "  motion blur"
                        motion = m1
        
                if motion: # motion-blur only works with instances, so ensure mesh is exported as instance first
                    if mesh_name in self.meshes:
                        del self.meshes[mesh_name]
                        mesh.getFromObject(obj, 0, 1)
                        mats = self.getMaterials(obj)
                        print "  blender-mesh: %s (%d vertices, %d faces)"%(mesh_name, len(mesh.verts), len(mesh.faces))
                        file.write("ObjectBegin \"%s\"\n"%mesh_name)
                        if (mesh_optimizing):
                            self.MeshOpt(file, mesh, mats, mesh_name)
                        else:
                            self.Mesh(file, mesh, mats, mesh_name)
                        file.write("ObjectEnd # %s\n\n"%mesh_name)
    
                file.write("AttributeBegin # %s\n"%obj.getName())
                file.write("\tTransform [%s %s %s %s  %s %s %s %s  %s %s %s %s  %s %s %s %s]\n"\
                    %(matrix[0][0], matrix[0][1], matrix[0][2], matrix[0][3],\
                      matrix[1][0], matrix[1][1], matrix[1][2], matrix[1][3],\
                      matrix[2][0], matrix[2][1], matrix[2][2], matrix[2][3],\
                      matrix[3][0], matrix[3][1], matrix[3][2], matrix[3][3]))
                if motion:
                    file.write("\tTransformBegin\n")
                    file.write("\t\tIdentity\n")
                    file.write("\t\tTransform [%s %s %s %s  %s %s %s %s  %s %s %s %s  %s %s %s %s]\n"\
                        %(motion[0][0], motion[0][1], motion[0][2], motion[0][3],\
                          motion[1][0], motion[1][1], motion[1][2], motion[1][3],\
                          motion[2][0], motion[2][1], motion[2][2], motion[2][3],\
                          motion[3][0], motion[3][1], motion[3][2], motion[3][3]))
                    file.write("\t\tCoordinateSystem \"%s\"\n"%(obj.getName()+"_motion"))
                    file.write("\tTransformEnd\n")
                if mesh_name in self.meshes:
                    mesh.getFromObject(obj, 0, 1)
                    mats = self.getMaterials(obj)
                    print "  blender-mesh: %s (%d vertices, %d faces)"%(mesh_name, len(mesh.verts), len(mesh.faces))
                    if (mesh_optimizing):
                        self.MeshOpt(file, mesh, mats, mesh_name)
                    else:
                        self.Mesh(file, mesh, mats, mesh_name)
                else:
                    print "  instance %s"%(mesh_name)
                    if motion:
                        file.write("\tMotionInstance \"%s\" 0.0 1.0 \"%s\"\n"%(mesh_name, obj.getName()+"_motion"))
                    else:
                        file.write("\tObjectInstance \"%s\"\n"%mesh_name)
                file.write("AttributeEnd\n\n")
            mesh.verts = None
    
        def Portals(self, file):
            '''exports portals objects to the file'''
            #Lux.scene = Blender.Scene.GetCurrent()
            mesh_optimizing = Lux.Property(self.scene, "mesh_optimizing", True).get()
            mesh = Mesh.New('')
            for [obj, matrix] in self.portals:
                print "portal: %s"%(obj.getName())
                file.write("\tTransform [%s %s %s %s  %s %s %s %s  %s %s %s %s  %s %s %s %s]\n"\
                    %(matrix[0][0], matrix[0][1], matrix[0][2], matrix[0][3],\
                      matrix[1][0], matrix[1][1], matrix[1][2], matrix[1][3],\
                      matrix[2][0], matrix[2][1], matrix[2][2], matrix[2][3],\
                      matrix[3][0], matrix[3][1], matrix[3][2], matrix[3][3]))
                mesh_name = obj.getData(name_only=True)
                mesh.getFromObject(obj, 0, 1)
                mats = getMaterials(obj) # mats = obj.getData().getMaterials()
                if (mesh_optimizing):
                    self.MeshOpt(file, mesh, mats, mesh_name, True)
                else:
                    self.Mesh(file, mesh, mats, mesh_name, True)
            mesh.verts = None
    
        def Lights(self, file):
            '''exports lights to the file'''
            for [obj, matrix] in self.lights:
                ltype = obj.getData(mesh=1).getType() # data
                if (ltype == Lamp.Types["Lamp"]) or (ltype == Lamp.Types["Spot"]) or (ltype == Lamp.Types["Area"]):
                    print "light: %s"%(obj.getName())
                    if ltype == Blender.Lamp.Types["Area"]:
                        (str, link) = Lux.Light.Area("", "", obj, None, 0)
                        file.write(str)
                    if ltype == Blender.Lamp.Types["Area"]: file.write("AttributeBegin # %s\n"%obj.getName())
                    else: file.write("TransformBegin # %s\n"%obj.getName())
                    file.write("\tTransform [%s %s %s %s  %s %s %s %s  %s %s %s %s  %s %s %s %s]\n"\
                        %(matrix[0][0], matrix[0][1], matrix[0][2], matrix[0][3],\
                          matrix[1][0], matrix[1][1], matrix[1][2], matrix[1][3],\
                          matrix[2][0], matrix[2][1], matrix[2][2], matrix[2][3],\
                          matrix[3][0], matrix[3][1], matrix[3][2], matrix[3][3]))
                    col = obj.getData(mesh=1).col # data
                    energy = obj.getData(mesh=1).energy # data
                    if ltype == Blender.Lamp.Types["Lamp"]:
                        lightgroup = Lux.Property(obj, "light.lightgroup", "default")
                        file.write("LightGroup \"%s\"\n"%lightgroup.get())
                        (str, link) = Lux.Light.Lamp("", "", obj, None, 0)
                        file.write(str+"LightSource \"point\""+link+"\n")
                    if ltype == Blender.Lamp.Types["Spot"]:
                        (str, link) = Lux.Light.Spot("", "", obj, None, 0)
                        file.write(str)
                        proj = Lux.Property(obj, "light.usetexproj", "false")
                        lightgroup = Lux.Property(obj, "light.lightgroup", "default")
                        file.write("LightGroup \"%s\"\n" % lightgroup.get())
                        if(proj.get() == "true"):
                            file.write("Rotate 180 0 1 0\n")
                            file.write("LightSource \"projection\" \"float fov\" [%f]"%(obj.getData(mesh=1).spotSize))
                        else:
                            file.write("LightSource \"spot\" \"point from\" [0 0 0] \"point to\" [0 0 -1] \"float coneangle\" [%f] \"float conedeltaangle\" [%f]"\
                                %(obj.getData(mesh=1).spotSize*0.5, obj.getData(mesh=1).spotSize*0.5*obj.getData(mesh=1).spotBlend)) # data
                        file.write(link+"\n")
                    if ltype == Blender.Lamp.Types["Area"]:
                        lightgroup = Lux.Property(obj, "light.lightgroup", "default")
                        file.write("LightGroup \"%s\"\n"%lightgroup.get())
                        file.write("\tAreaLightSource \"area\"")
                        file.write(link)
                        file.write("\n")
                        areax = obj.getData(mesh=1).getAreaSizeX()
                        # lamps "getAreaShape()" not implemented yet - so we can't detect shape! Using square as default
                        # todo: ideasman42
                        if (True): areay = areax
                        else: areay = obj.getData(mesh=1).getAreaSizeY()
                        file.write('\tShape "trianglemesh" "integer indices" [0 1 2 0 2 3] "point P" [-%(x)f %(y)f 0.0 %(x)f %(y)f 0.0 %(x)f -%(y)f 0.0 -%(x)f -%(y)f 0.0]\n'%{"x":areax/2, "y":areay/2})
                    if ltype == Blender.Lamp.Types["Area"]: file.write("AttributeEnd # %s\n"%obj.getName())
                    else: file.write("TransformEnd # %s\n"%obj.getName())
                    file.write("\n")
                    
        def Volumes(self, file):
            '''exports volumes to the file'''
            for [obj, matrix] in self.volumes:
                print "volume: %s"%(obj.getName())
                file.write("# Volume: %s\n"%(obj.getName()))
    
                # trickery to obtain objectspace boundingbox AABB
                mat = obj.matrixWorld.copy().invert()
                bb = [vec * mat for vec in obj.getBoundBox()]
                minx = miny = minz = 100000000000000.0
                maxx = maxy = maxz = -100000000000000.0
                for vec in bb:
                    if (vec[0] < minx): minx = vec[0]
                    if (vec[1] < miny): miny = vec[1]
                    if (vec[2] < minz): minz = vec[2]
                    if (vec[0] > maxx): maxx = vec[0]
                    if (vec[1] > maxy): maxy = vec[1]
                    if (vec[2] > maxz): maxz = vec[2]
    
                file.write("Transform [%s %s %s %s  %s %s %s %s  %s %s %s %s  %s %s %s %s]\n"\
                    %(matrix[0][0], matrix[0][1], matrix[0][2], matrix[0][3],\
                      matrix[1][0], matrix[1][1], matrix[1][2], matrix[1][3],\
                      matrix[2][0], matrix[2][1], matrix[2][2], matrix[2][3],\
                      matrix[3][0], matrix[3][1], matrix[3][2], matrix[3][3]))
    
                str_opt = (" \"point p0\" [%f %f %f] \"point p1\" [%f %f %f]"%(minx, miny, minz, maxx, maxy, maxz))
                mats = self.getMaterials(obj)
                if (len(mats)>0) and (mats[0]!=None) and (Lux.Property(mats[0], "type", "").get()=="boundvolume"):
                    mat = mats[0]
                    (str, link) = Lux.MaterialBlock("", "", "", mat, None, 0, str_opt)
                    file.write("%s"%link)
                    file.write("\n\n")
            
    
    
    class Launch:
        '''
        LAUNCH LuxRender AND RENDER CURRENT SCENE
        '''
        
        runRenderAfterExport = None
        
        def ExportStill(default, run):
            global runRenderAfterExport
            runRenderAfterExport = run
            if default:
                datadir = Lux.Property(Blender.Scene.GetCurrent(), "datadir", "").get()
                if datadir=="": datadir = Blender.Get("datadir")
                filename = datadir + os.sep + "default.lxs"
                save_still(filename)
            else:
                Window.FileSelector(save_still, "Export", sys.makename(Blender.Get("filename"), ".lxs"))
        
        
        def ExportAnim(default, run, fileselect=True):
            if default:
                datadir = Lux.Property(Blender.Scene.GetCurrent(), "datadir", "").get()
                if datadir=="": datadir = Blender.Get("datadir")
                filename = datadir + os.sep + "default.lxs"
                save_anim(filename)
            else:
                if fileselect:
                    Window.FileSelector(save_anim, "Export", sys.makename(Blender.Get("filename"), ".lxs"))
                else:
                    datadir = Lux.Property(Blender.Scene.GetCurrent(), "datadir", "").get()
                    if datadir=="": datadir = Blender.Get("datadir")
                    filename = sys.makename(Blender.Get("filename") , ".lxs")
                    save_anim(filename)
        
        @staticmethod
        def Normal(filename):
            ostype = osys.platform
            #get blenders 'bpydata' directory
            datadir = Blender.Get("datadir")
            
            Lux.scene = Blender.Scene.GetCurrent()
            ic = Lux.Property(Lux.scene, "lux", "").get()
            ic = Blender.sys.dirname(ic) + os.sep + "luxrender"
            if ostype == "win32": ic = ic + ".exe"
            if ostype == "darwin": ic = ic + ".app/Contents/MacOS/luxrender"
            checkluxpath = Lux.Property(Lux.scene, "checkluxpath", True).get()
            if checkluxpath:
                if sys.exists(ic) != 1:
                    Blender.Draw.PupMenu("Error: Lux renderer not found. Please set path on System page.%t|OK")
                    return        
            autothreads = Lux.Property(Lux.scene, "autothreads", "true").get()
            threads = Lux.Property(Lux.scene, "threads", 1).get()
            luxnice = Lux.Property(Lux.scene, "luxnice", 10).get()
            if ostype == "win32":
                prio = ""
                if luxnice > 15: prio = "/low"
                elif luxnice > 5: prio = "/belownormal"
                elif luxnice > -5: prio = "/normal"
                elif luxnice > -15: prio = "/abovenormal"
                else: prio = "/high"
                if(autothreads=="true"):
                    cmd = "start /b %s \"\" \"%s\" \"%s\" " % (prio, ic, filename)        
                else:
                    cmd = "start /b %s \"\" \"%s\" \"%s\" --threads=%d" % (prio, ic, filename, threads)        
        
            if ostype == "linux2" or ostype == "darwin":
                if(autothreads=="true"):
                    cmd = "(nice -n %d \"%s\" \"%s\")&" % (luxnice, ic, filename)
                else:
                    cmd = "(nice -n %d \"%s\" --threads=%d \"%s\")&"%(luxnice, ic, threads, filename)
        
            # call external shell script to start Lux    
            print("Running Luxrender:\n"+cmd)
            os.system(cmd)
        
        @staticmethod
        def Piped():
            ostype = osys.platform
            #get blenders 'bpydata' directory
            datadir = Blender.Get("datadir")
            
            Lux.scene = Blender.Scene.GetCurrent()
            ic = Lux.Property(Lux.scene, "lux", "").get()
            ic = Blender.sys.dirname(ic) + os.sep + "luxrender"
            if ostype == "win32": ic = ic + ".exe"
            if ostype == "darwin": ic = ic + ".app/Contents/MacOS/luxrender"
            checkluxpath = Lux.Property(Lux.scene, "checkluxpath", True).get()
            if checkluxpath:
                if sys.exists(ic) != 1:
                    Blender.Draw.PupMenu("Error: Lux renderer not found. Please set path on System page.%t|OK")
                    return        
            autothreads = Lux.Property(Lux.scene, "autothreads", "true").get()
            threads = Lux.Property(Lux.scene, "threads", 1).get()
        
            if ostype == "win32":
                if(autothreads=="true"):
                    cmd = "\"%s\" - "%(ic)        
                else:
                    cmd = "\"%s\" - --threads=%d" % (ic, threads)        
        
            if ostype == "linux2" or ostype == "darwin":
                if(autothreads=="true"):
                    cmd = "(\"%s\" \"%s\")&"%(ic, filename)
                else:
                    cmd = "(\"%s\" --threads=%d \"%s\")&"%(ic, threads, filename)
        
            # call external shell script to start Lux    
            print("Running Luxrender:\n"+cmd)
        
            import subprocess
            p = subprocess.Popen(cmd, stdin=subprocess.PIPE)
            
            return p.stdin
        
        @staticmethod
        def Wait(filename):
            ostype = osys.platform
            #get blenders 'bpydata' directory
            datadir=Blender.Get("datadir")
            
            Lux.scene = Blender.Scene.GetCurrent()
            ic = Lux.Property(Lux.scene, "lux", "").get()
            ic = Blender.sys.dirname(ic) + os.sep + "luxrender"
            if ostype == "win32": ic = ic + ".exe"
            if ostype == "darwin": ic = ic + ".app/Contents/MacOS/luxrender"
            checkluxpath = Lux.Property(Lux.scene, "checkluxpath", True).get()
            if checkluxpath:
                if sys.exists(ic) != 1:
                    Blender.Draw.PupMenu("Error: Lux renderer not found. Please set path on System page.%t|OK")
                    return        
            autothreads = Lux.Property(Lux.scene, "autothreads", "true").get()
            threads = Lux.Property(Lux.scene, "threads", 1).get()
        
            if ostype == "win32":
                if(autothreads=="true"):
                    cmd = "start /b /WAIT \"\" \"%s\" \"%s\" "%(ic, filename)        
                else:
                    cmd = "start /b /WAIT \"\" \"%s\" \"%s\" --threads=%d"%(ic, filename, threads)        
                # call external shell script to start Lux    
                #print("Running Luxrender:\n"+cmd)
                #os.spawnv(os.P_WAIT, cmd, 0)
                os.system(cmd)
        
            if ostype == "linux2" or ostype == "darwin":
                if(autothreads=="true"):
                    cmd = "\"%s\" \"%s\""%(ic, filename)
                else:
                    cmd = "\"%s\" --threads=%d \"%s\""%(ic, threads, filename)
                subprocess.call(cmd,shell=True)
    
    class Icon:
        
        @staticmethod
        def get_logo(name):
            return Lux.Icon.decodeLogoStr(Lux.Icon.Data.logos[name])
        
        @staticmethod
        def get_icon(name):
            return Lux.Icon.decodeIconStr(Lux.Icon.Data.icons[name])
        
        @staticmethod
        def get_bar(name):
            return Lux.Icon.decodeBarStr(Lux.Icon.Data.bars[name])
        
        class Data:
            logos = {
                'icon_luxblend'            : ("///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A/gAA/gAA/gAA/gAA/gAA/gAA/gAa/gA5/gAZ/gAA/gAA/gAA/gAA/gAA/gAA/gAA/gAA///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A/gAA/gAA/gAA/gAA/gAA/gAA/gAj/gA//gAh/gAA/gAA/gAA/gAA/gAA/gAA/gAA/gAA///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A/gAA/gAA/gAA/gAA/gAA/gAA/gAC/gAO/gAC/gAB/gAS/gAQ/gAA/gAA/gAA/gAA/gAA///A///A///A/gAA/gAZ/gAu/gA7/gA//gA//gA//gA//gA//gA//gA//gAd/gAA/gAZ/gAu/gA//gA//gA//gA//gA//gA//gA3/gAm/gAI/gAE/gAz/gA//gA//gAZ/gAA/gAA/gAA/gAZ/gA//gA//gAm/gAR/gA//gA//gA//gA//gA//gA//gA//gA//gA//gA//gAz/gAd/gAE/gAA/gA//gA//gAd/gAA/gAI/gAm/gA3/gA//gA//gA//gAR/gAA/gAA/gAA/gAA/gAA/gAu/gA//gAu/gAA/gAA/gAA/gAA/gAA/gAA/gAd/gA//gA//gAA/gAE/gAd/gAz/gA//gA//gA//gA//gA//gA7/gAq/gAV/gAA///A///A///A///A///A///A/gAA/gAA/gAA/gAI/gAK/gAA/gAA/gAA/gAA/gAn/gA//gA//gAc/gAA/gAA/gAA/gAA///A///A///A/gAi/gA//gA//gA//gA//gA//gA//gA//gA//gA//gA//gAd/gAZ/gA//gA//gA//gA//gA//gA//gA//gA//gA//gA//gA7/gAE/gAE/gAz/gA//gA//gAR/gAA/gAZ/gA//gA//gAm/gAA/gAR/gA//gA//gA//gA//gA//gA//gA//gA//gA//gA//gA//gA//gAz/gAA/gA//gA//gAd/gAI/gA7/gA//gA//gA//gA//gA//gAR/gAA/gAA/gAA/gAA/gAA/gAu/gA//gAu/gAA/gAA/gAA/gAA/gAA/gAA/gAd/gA//gA//gAA/gAu/gA//gA//gA//gA//gA//gA//gA//gA//gA//gA//gAi///A///A///A///A///A///A/gAA/gAA/gAA/gAv/gA4/gAA/gAA/gAA/gAD/gA9/gA//gA//gAz/gAA/gAA/gAA/gAA///A///A///A/gA//gA//gAq/gAI/gAA/gAA/gAA/gAA/gAA/gAA/gAA/gAA/gAu/gA//gA3/gAI/gAA/gAA/gAA/gAA/gAA/gAd/gA//gA//gAR/gAA/gAM/gA7/gA//gA7/gAZ/gA//gA//gAz/gAA/gAA/gAR/gA//gA//gAR/gAA/gAA/gAA/gAA/gAA/gAA/gAE/gAd/gA//gA//gAM/gA//gA//gAd/gAd/gA//gA//gAd/gAI/gAA/gAA/gAA/gAA/gAA/gAA/gAA/gAA/gAu/gA//gAu/gAA/gAA/gAA/gAA/gAA/gAA/gAd/gA//gA//gAA/gA//gA//gAq/gAA/gAA/gAA/gAA/gAA/gAE/gAq/gA//gA////A///A///A///A///A///A/gAA/gAA/gAA/gAN/gAQ/gAA/gAA/gAA/gAA/gAs/gA//gA//gA+/gAs/gAp/gAZ/gAA///A///A///A/gA//gA//gAd/gAA/gAA/gAA/gAA/gAA/gAA/gAA/gAA/gAA/gAu/gA//gAu/gAA/gAA/gAA/gAA/gAA/gAA/gAR/gA//gA//gAR/gAA/gAA/gAM/gA7/gA//gA//gA//gAz/gAE/gAA/gAA/gAR/gA//gA//gAR/gAA/gAA/gAA/gAA/gAA/gAA/gAA/gAR/gA//gA//gAR/gA//gA//gAd/gAd/gA//gA//gAu/gAu/gAu/gAu/gAu/gAu/gAu/gAu/gAu/gAM/gAu/gA//gAu/gAA/gAA/gAA/gAA/gAA/gAA/gAd/gA//gA//gAA/gA//gA//gAd/gAA/gAA/gAA/gAA/gAA/gAA/gAd/gA//gA////A///A///A///A///A///A/gAA/gAA/gAA/gAA/gAA/gAA/gAA/gAI/gAA/gAE/gAZ/gAw/gA//gA//gA//gA//gAh///A///A///A/gA//gA//gAd/gAA/gAA/gAA/gAA/gAA/gAA/gAA/gAA/gAA/gAu/gA//gAu/gAA/gAA/gAA/gAA/gAA/gAA/gAR/gA//gA//gAR/gAA/gAA/gAA/gAR/gA//gA//gA//gAI/gAA/gAA/gAA/gAR/gA//gA//gAm/gAd/gAd/gAd/gAd/gAd/gAd/gAd/gA3/gA//gA3/gAA/gA//gA//gAd/gAd/gA//gA//gA//gA//gA//gA//gA//gA//gA//gA//gA//gAR/gAu/gA//gAu/gAA/gAA/gAA/gAA/gAA/gAA/gAd/gA//gA//gAA/gA//gA//gAd/gAA/gAA/gAA/gAA/gAA/gAA/gAd/gA//gA////A///A///A///A///A///A/gAl/gAL/gAA/gAA/gAA/gAA/gAf/gA+/gAd/gAA/gAA/gAT/gA//gA//gA//gA//gA6///A///A///A/gA//gA//gAd/gAA/gAA/gAA/gAA/gAA/gAA/gAA/gAA/gAA/gAu/gA//gAu/gAA/gAA/gAA/gAA/gAA/gAA/gAR/gA//gA//gAR/gAA/gAA/gAE/gAz/gA//gA//gA//gAz/gAE/gAA/gAA/gAR/gA//gA//gA//gA//gA//gA//gA//gA//gA//gA//gA//gA//gAd/gAA/gA//gA//gAd/gAd/gA//gA//gAR/gAR/gAR/gAR/gAR/gAR/gAd/gA//gA//gAR/gAu/gA//gAu/gAA/gAA/gAA/gAA/gAA/gAA/gAd/gA//gA//gAA/gA//gA//gAd/gAA/gAA/gAA/gAA/gAA/gAA/gAd/gA//gA////A///A///A///A///A///A/gAl/gAK/gAA/gAA/gAA/gAA/gAf/gA+/gAd/gAA/gAA/gAT/gA//gA//gA//gA//gA6///A///A///A/gA//gA//gAd/gAA/gAA/gAA/gAA/gAA/gAA/gAA/gAA/gAA/gAu/gA//gAu/gAA/gAA/gAA/gAA/gAA/gAA/gAR/gA//gA//gAR/gAA/gAA/gAz/gA//gA7/gAd/gA//gA//gAm/gAA/gAA/gAR/gA//gA//gAm/gAd/gAd/gAd/gAd/gAd/gAd/gAd/gAu/gA//gA//gAI/gA//gA//gAd/gAd/gA//gA//gAd/gAR/gAR/gAR/gAR/gAR/gAq/gA//gA//gAR/gAu/gA//gA7/gAZ/gAR/gAR/gAR/gAR/gAV/gAz/gA//gA//gAA/gA3/gA//gA7/gAi/gAd/gAd/gAd/gAd/gAd/gAu/gA//gA////A///A///A///A///A///A/gAA/gAA/gAA/gAA/gAA/gAA/gAA/gAI/gAA/gAE/gAa/gAw/gA//gA//gA//gA//gAg///A///A///A/gA//gA//gAd/gAA/gAA/gAA/gAA/gAA/gAA/gAA/gAA/gAA/gAu/gA//gAu/gAA/gAA/gAA/gAA/gAA/gAA/gAR/gA//gA//gAR/gAA/gAm/gA//gA7/gAM/gAA/gAZ/gA//gA//gAm/gAA/gAR/gA//gA//gAR/gAA/gAA/gAA/gAA/gAA/gAA/gAA/gAR/gA//gA//gAR/gA//gA//gAd/gAE/gAz/gA//gA//gA//gA//gA//gA//gA//gA//gA//gAz/gAA/gAV/gA//gA//gA//gA//gA//gA//gA//gA//gA//gA//gAi/gAA/gAV/gA7/gA//gA//gA//gA//gA//gA//gA//gA//gA//gA////A///A///A///A///A///A/gAA/gAA/gAA/gAO/gAR/gAA/gAA/gAA/gAA/gAt/gA//gA//gA+/gAs/gAq/gAZ/gAA///A///A///A/gA//gA//gAd/gAA/gAA/gAA/gAA/gAA/gAA/gAA/gAA/gAA/gAi/gAu/gAi/gAA/gAA/gAA/gAA/gAA/gAA/gAM/gAu/gAu/gAM/gAm/gA//gA7/gAM/gAA/gAA/gAA/gAm/gA//gA//gAd/gAR/gA//gA//gAd/gAR/gAR/gAR/gAR/gAR/gAR/gAR/gAq/gA//gA//gAM/gA//gA//gAd/gAA/gAA/gAZ/gAm/gAu/gAu/gAu/gAu/gAu/gAq/gAZ/gAA/gAA/gAA/gAI/gAd/gAu/gAu/gAu/gAu/gAu/gAu/gAi/gAV/gAA/gAA/gAA/gAE/gAV/gAd/gAd/gAd/gAd/gAd/gAd/gAu/gA//gA////A///A///A///A///A///A/gAA/gAA/gAA/gAv/gA4/gAA/gAA/gAA/gAD/gA9/gA//gA//gAz/gAA/gAA/gAA/gAA///A///A///A/gA//gA//gAd/gAA/gAA/gAA/gAA/gAA/gAA/gAA/gAA/gAA/gAA/gAA/gAA/gAA/gAA/gAA/gAA/gAA/gAA/gAA/gAA/gAA/gAA/gAA/gAA/gAA/gAA/gAA/gAA/gAA/gAA/gAA/gAA/gAA/gAR/gA//gA//gA//gA//gA//gA//gA//gA//gA//gA//gA//gA//gAm/gAA/gA//gA//gAd/gAA/gAA/gAA/gAA/gAA/gAA/gAA/gAA/gAA/gAA/gAA/gAA/gAA/gAA/gAA/gAA/gAA/gAA/gAA/gAA/gAA/gAA/gAA/gAA/gAA/gAA/gAA/gAA/gAA/gAA/gAA/gAA/gAA/gAA/gAA/gAd/gA//gA////A///A///A///A///A///A/gAA/gAA/gAA/gAI/gAK/gAA/gAA/gAA/gAA/gAn/gA//gA//gAc/gAA/gAA/gAA/gAA///A///A///A/gA//gA//gAd/gAA/gAA/gAA/gAA/gAA/gAA/gAA/gAA/gAA/gAA/gAA/gAA/gAA/gAA/gAA/gAA/gAA/gAA/gAA/gAA/gAA/gAA/gAA/gAA/gAA/gAA/gAA/gAA/gAA/gAA/gAA/gAA/gAA/gAM/gAu/gAu/gAu/gAu/gAu/gAu/gAu/gAu/gAu/gAu/gAm/gAR/gAA/gAA/gA//gA//gAd/gAA/gAA/gAA/gAA/gAA/gAA/gAA/gAA/gAA/gAA/gAA/gAA/gAA/gAA/gAA/gAA/gAA/gAA/gAA/gAA/gAA/gAA/gAA/gAA/gAA/gAA/gAA/gAA/gAA/gAA/gAA/gAA/gAA/gAA/gAA/gAd/gA//gA////A///A///A///A///A///A/gAA/gAA/gAA/gAA/gAA/gAA/gAC/gAO/gAC/gAB/gAS/gAP/gAA/gAA/gAA/gAA/gAA///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A/gAA/gAA/gAA/gAA/gAA/gAA/gAj/gA//gAh/gAA/gAA/gAA/gAA/gAA/gAA/gAA/gAA///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A/gAA/gAA/gAA/gAA/gAA/gAA/gAa/gA5/gAY/gAA/gAA/gAA/gAA/gAA/gAA/gAA/gAA///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A")
            }
            icons = {
                 'icon_blender'            : ("///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A27wA27wA27wA27wA27wAFFFGIIIsNNN5IIIsFFFG27wA27wA27wA27wA27wA///A27wA27wA27wA27wA27wAFFFmnnn9sss/kkk9FFFm27wA27wA27wA27wA27wA///A27wA27wA27wA27wA27wAEEEvwww/AAA/sss/EEEv27wA27wA27wA27wA27wA///A27wA27wA27wA27wA27wAFFFxzzz/xxx/vvv/FFFx27wA27wA27wA27wA27wA///A27wAGGGRLLLtKKK7KKK9JJJ/111/ppp/xxx/III/JJJ9JJJ7LLLtGGGR27wA///AGGGQPPP8xxx/444/vvv/555/333/999/zzz/xxx/jjj/nnn/nnn/OOO8GGGQ///ALLL2222/zzz/lll/+++/888/666/444/222/000/yyy/aaa/nnn/vvv/LLL2///AMMMxqqq/+++/ttt/////AAA/888/666/444/AAA/000/iii/zzz/nnn/MMMx///AGGGKLLLqKKK7ZZZ/yyy/yyy/yyy/888/vvv/ttt/rrr/VVV/JJJ7LLLqGGGK///A27wA27wA27wAJJJ1999+////sss5UUU8qqq5777/333+III127wA27wA27wA///A27wA27wA27wAHHHJMMMzUUU7GGGpHHHIGGGpSSS7MMMzHHHJ27wA27wA27wA///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A")
                ,'icon_col'                : ("///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A27wA27wA27wA27wAVIAPXKB5VIAS27wA27wA27wA27wA///A///A///A///A///A27wA27wA27wAVIAPXKB8shU/XLC9VIAS27wA27wA27wA///A///A///A///A///A27wA27wAVIAPXKB8ymU/7xd/0qb/XLC9VIAS27wA27wA///A///A///A///A///A27wAVIAPXKA8xkO/7uW/7wa/7xd/0qb/XLC9VIAS27wA///A///A///A///A///AVIAPXKA8xiJ/6rO/6sS/7uW/7wZ/7xd/0qa/XLC9VIAS///A///A///A///A///AXKA1ypd/+6z/6rO/6rO/6sS/7uW/7vZ/7xd/shT/XKB5///A///A///A///A///AVJAMYMC873w/+6z/6rO/6rO/6sS/7uV/ymT/XKB8VIAP///A///A///A///A///A27wAVJAMYMC873w/+6z/6rO/6rO/xkN/XKB8VIAP27wA///A///A///A///A///A27wA27wAVJAMYMC873w/+6z/xiJ/XKA8VIAP27wA27wA///A///A///A///A///A27wA27wA27wAVJAMYMC8xpc/XKA8VIAP27wA27wA27wA///A///A///A///A///A27wA27wA27wA27wAVJAMXKA1VIAP27wA27wA27wA27wA///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A")
                ,'icon_float'              : ("///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A27wA27wA27wA27wAMMMSOOO5MMMP27wA27wA27wA27wA///A///A///A///A///A27wA27wA27wAMMMSPPP9nnn/PPP8MMMP27wA27wA27wA///A///A///A///A///A27wA27wAMMMSPPP9ttt/333/vvv/PPP8MMMP27wA27wA///A///A///A///A///A27wAMMMSOOO9ppp/zzz/111/333/vvv/PPP8MMMP27wA///A///A///A///A///AMMMSOOO9lll/uuu/www/zzz/111/333/vvv/PPP8MMMP///A///A///A///A///AOOO5sss/666/sss/uuu/www/zzz/111/333/kkk/PPP1///A///A///A///A///AMMMPQQQ8444/666/ttt/uuu/www/zzz/ppp/OOO8MMMM///A///A///A///A///A27wAMMMPQQQ8444/666/ttt/uuu/mmm/OOO8MMMM27wA///A///A///A///A///A27wA27wAMMMPQQQ8444/555/jjj/OOO8MMMM27wA27wA///A///A///A///A///A27wA27wA27wAMMMPQQQ8ppp/OOO8MMMM27wA27wA27wA///A///A///A///A///A27wA27wA27wA27wAMMMPOOO1MMMM27wA27wA27wA27wA///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A")
                ,'icon_map2d'              : ("///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A27wA27wA27wA27wA27wAMMMUMMMzMMMzMMMU27wA27wA27wA27wA27wA///A///A27wA27wA27wANNNPMMMyYVQ/wnV/bbb/RRR/MMMyNNNP27wA27wA27wA///A///A27wAMMMLMMMtWUQ/vnZ/7vY/6rP/aaa/eee/ZZZ/PPP/MMMtMMML27wA///A///AMMMfTSQ/tnc/7yg/7uV/6qN/6qM/YYY/ZZZ/ddd/fff/YYY/OOO/MMMf///A///AMMM/71o/7wb/6sQ/rgK/dVG/6qM/YYY/ZZZ/bbb/ccc/fff/ggg/MMM////A///AMMM/92q/AAA/6rP/dVH/AAA/6qM/YYY/ZZZ/bbb/ccc/eee/iii/MMM////A///AMMM/93r/dWI/6rP/dVH/AAA/6qM/XXX/ZZZ/bbb/ccc/eee/iii/MMM////A///AMMM/94t/6sR/6rQ/6rO/6qN/6qM/XXX/ZZZ/bbb/ccc/eee/jjj/MMM////A///AMMM/94u/dWI/dVI/6rP/6rN/6qM/XXX/ZZZ/bbb/ccc/eee/kkk/MMM////A///AMMM/+5v/AAA/AAA/6rP/7vX/94t/xxx/ggg/bbb/ccc/eee/lll/MMM////A///AMMM/+5x/6sR/7xd/+6y/////////////////111/mmm/eee/mmm/MMM////A///AMMM/+72//96/////////////////////////////////666/vvv/MMM////A///AMMMiTTS/wuq/986/////////////////////////555/ppp/SSS/MMMi///A///A27wAMMMHMMMdMMM0aZX/0yu/+97/888/uuu/XXX/MMM0MMMdMMMH27wA///A///A27wA27wA27wA27wANNNLMMMhMMM3MMM3MMMhNNNL27wA27wA27wA27wA///A")
                ,'icon_map2dparam'         : ("///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A27wAQQQB27wA27wA27wA27wA27wA27wA27wA27wA27wA27wA27wA27wA///A///A27wAUUUwMMM9EEE3AAAvAAAlAAAbAAAI27wA27wA27wA27wA27wA27wA///A///A27wAeeeOVVV9OOO/MMM/CCC/AAA+AAA9AAAg27wA27wA27wA27wA27wA///A///A27wA27wAfffKWWW9ggg/mmm/TTT/AAA/AAA9AAAS27wA27wA27wA27wA///A///A27wA27wA27wAeeeXVVV9hhh/lll/TTT/BBB/BBB6AAAN27wA27wA27wA///A///A27wAAAAK27wA27wAdddgTTT8NNN/NNN/JJJ/VVV9EEE8AAAoAAAG27wA///A///A27wAAAAXAAAA27wA27wAeeeaVVV2QQQ/nnn+222/mmm/PPP9JGF8KGCX///A///A27wAAAAkAAAA27wA27wA27wA27wAVVVXYYY8+++/333/gec+ZPL+XOJq///A///A27wAAAAxAAAB27wA27wA27wA27wA27wAXXXiiii83219ofY8eUO/aQL2///A///A27wAAAA9AAAC27wA27wA27wA27wA27wAgggAWWVwmgc84yt/oeW/gWP1///A///ACCC6AAA/AAA/CCC627wA27wA27wA27wA27wAKFFDKGDzxsm52wq/peW2///A///AAAA/////////AAA/AAABAAAAAAAAAAAA27wA27wALFCFMHE31wr61uo5///A///AAAA/////////AAA/AAA+AAAzAAAmAAAZAAAM27wA27wAKFDJPLH6umez///A///ACCC6AAA/AAA/CCC627wA27wA27wA27wA27wA27wA27wA27wAKFCOOJFf///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A")
                ,'icon_map3dparam'         : ("27wA27wA27wA27wA27wA27wA3nIC6pMJ6pMJ3nIC27wA27wA27wA27wA27wA27wA27wA27wA27wA27wA27wA3nIC6qMj6qM/6qM/6qMj3nIC27wA27wA27wA27wA27wA27wA27wA27wA27wA27wA6pMJ6qM/////////6qM/6pMJ27wA27wA27wA27wA27wA27wA27wA27wA27wANNNOSQMz5qM/////////5qM/SQMzNNNO27wA27wA27wA27wA27wA27wAMMMIMMMrXXX/www/5wg/6qM/5qM/vnX/bbb/PPP/MMMrMMMI27wA27wA27wA27wAMMM1xxx/777/222/yyy/zxu/caY/bbb/ggg/iii/YYY/MMM127wA27wA27wA27wAMMM/+++/zzz/yyy/yyy/yyy/ZZZ/bbb/ddd/fff/kkk/MMM/27wA27wA27wA27wAMMM/////yyy/yyy/yyy/yyy/ZZZ/bbb/ddd/eee/lll/MMM/27wA27wA27wA27wAMMM/////yyy/yyy/yyy/yyy/ZZZ/bbb/ddd/eee/nnn/MMM/27wA27wA27wA3nICRPM//97/yyy/yyy/yyy/yyy/ZZZ/bbb/ddd/eee/rpm/RPM/3nIC27wA3nIC6qMj5qM/6qM/2ue/zzz/444/999/666/rrr/fff/tkU/5qM/5qM/6qMj3nIC6pMJ6qM/////////6qM/+96/////////////////985/6qM/////////6qM/6pMJ6pMJ6qM/////////6qM/+86/////////////////974/6qM/////////6qM/6pMJ3nIC6qMj6qM/6qM/pfM2PPP+mmm/555/000/hhh/PPP+pfM26qM/6qM/6qMj3nIC27wA3nIC6pMJ6pMJ3nICMMMEMMMaMMMwMMMwMMMaMMME3nIC6pMJ6pMJ3nIC27wA///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A")
                ,'icon_mat'                : ("///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A27wA27wA27wAVJAMXKBnXLB1WJA9XLB1XKBnVJAM27wA27wA27wA///A///A///A27wAVAAAWJBgYMD9ukW/1sc/5we/0qY/sgQ/XLB9WJBgVAAA27wA///A///A///A27wAWJBghXM96zk/8yf/7wa/7vY/7vZ/YUN/TQM/aPF9WJBg27wA///A///A///AVIALZNE970o/7wb/QNG/QNG/7vX/7vX/JHD/DDD/bXP/XKB9VIAL///A///A///AXKBpype/8zj/7vX/QNG/QNG/7vX/7vX/sjR/IGD/keS/rfQ/XKBp///A///A///AXLB36zp/7xc/7vX/7vX/7vX/7vX/7vX/7vX/7vX/7vZ/0qZ/XLB3///A///A///AVJA+95x/2rX/fYM/zoU/7vX/7vX/7vX/7vX/7vX/7vY/6wf/VJA+///A///A///AXKB361s/VTO/AAA/NKF/7vX/7vX/meP/IGD/JHD/tkU/1rc/XKB3///A///A///AXKBq0tj/cba/AAA/HGD/7vX/7vX/IGD/AAA/AAA/VTQ/ujW/XKBq///A///A///AVIAMaPG920w/RPN/meP/7vX/7vX/gaM/BAA/HHH/njd/YMD9VIAM///A///A///A27wAWKBilbS995y/91n/8xd/7vZ/7xc/4wh/4yn/iXM9WKBi27wA///A///A///A27wAQQABWKBiaOF9zsj/61s/95x/5zp/xpe/ZNE9WKBiQQAB27wA///A///A///A27wA27wA27wAVIAMXKBqXKB3VJA+XKB3XKBqVIAM27wA27wA27wA///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A")
                ,'icon_matmix'             : ("27wA27wA27wA27wA27wA27wA27wAMIFdUMG7WNF+WNF+SLG5LHFS27wA27wA///A27wA27wA27wA27wA27wASLGAOJGziYN/xmV/wmT/pgQ/jaN/YPH/NJGm27wA///A27wA27wA27wA27wA27wAMIFjlbR/9ye/6sQ/zlJ/sgJ/ofM/ngT/YPH/MIGT///A27wA27wA27wA27wA27wAXQJ/6xk/9xZ/6sQ/5qM/zlK/sfI/ofM/jaN/SLG5///A27wA27wA27wA27wAHHHGgXQ//4r/8xc/7vX/7tR/5pM/zlK/sgJ/pgQ/WMF+///A27wA27wA27wA27wAJOVVYbf/58//y27/wz3/7vY/7tS/4pM/ykJ/vmU/WMF////A27wAAAAALIGkTMG+NQU/Qcu/Sfz/Sfz/Wi1/wz4/7vZ/7sR/6sR/wmW/UMH8///ASLGAOJG1iYN/xmV/kns/Rfz/99+/++//Rfz/z27/8ye/9yc/9zg/iYN/LIFh///AMHFilbR/9ye/6sQ/jns/Rfz/////////Rfz/57///4q/6xk/lbR/NJG227wA///AYQJ96xk/9xZ/6sQ/orw/Tgz/Rfz/Rez/Qdw/Xaf/gXP/XPI/MIGoAAAA27wA///AgXQ//4r/8xc/7vX/7tR/nrw/jms/dhn/ein/WNG/GGGRAAAA27wA27wA27wA///AhYR//7x/91m/8xe/7vY/7tS/4pM/ykJ/vmU/WMF/GGGH27wA27wA27wA27wA///AbTM995x//+6/80k/8ye/7vZ/7sR/6sR/wmW/TMG+27wA27wA27wA27wA27wA///APIEitld///7//+6/91n/8ye/9yc/9zg/iYN/LIGk27wA27wA27wA27wA27wA///ARKGCRKFyskc/94v//7w//4q/6xk/lbR/OJG0AAAA27wA27wA27wA27wA27wA///A27wAQJECPIEibTL9hYQ/gXP/YQJ9MHEi27wA27wA27wA27wA27wA27wA27wA///A")
                ,'icon_tex'                : ("///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///AOOO6MMM/MMM/MMM/MMM/MMM/MMM/MMM/MMM/MMM/MMM/MMM/OOO6///A///A///AMMM/444/555/555/555/555/666/666/777/777/888/888/MMM////A///A///AMMM/555/mmm/TTT/aaa/xxx/111/222/222/QQQ/ZZZ/777/MMM////A///A///AMMM/333/DDD/AAA/AAA/YYY/zzz/111/xxx/AAA/AAA/nnn/MMM////A///A///AMMM/222/DDD/AAA/AAA/bbb/yyy/zzz/111/RRR/AAA/iii/MMM////A///A///AMMM/666/jjj/TTT/ddd/vvv/xxx/yyy/zzz/000/rrr/555/MMM////A///A///AMMM/666/rrr/sss/uuu/vvv/www/xxx/yyy/zzz/000/666/MMM////A///A///AMMM/666/qqq/iii/qqq/uuu/vvv/ppp/nnn/yyy/zzz/555/MMM////A///A///AMMM/777/jjj/AAA/RRR/sss/bbb/AAA/AAA/SSS/yyy/555/MMM////A///A///AMMM/888/mmm/LLL/ccc/rrr/QQQ/AAA/AAA/AAA/www/555/MMM////A///A///AMMM/888/nnn/ooo/ppp/qqq/jjj/HHH/DDD/XXX/www/555/MMM////A///A///AMMM/666/888/888/777/666/666/555/555/555/444/333/MMM////A///A///ANNN4NNN+NNN+NNN+NNN+NNN+NNN+NNN+NNN+NNN+NNN+NNN+OOO4///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A")
                ,'icon_texcol'             : ("///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///AWKA4VJA+VJA+VJA+VJA+VJA+VJA+VJA+VJA+VJA+VJA+VJA+WKA4///A///A///AVIA/82p/93r/93r/93s/93s/93s/93t/94u/94u/94w/95w/VIA////A///A///AVIA/93s/xoV/ZVM/icR/6wf/8zi/80k/80l/USN/daU/94v/VIA////A///A///AVIA/72r/FDC/AAA/AAA/eZP/8yf/8zh/3vg/AAA/AAA/olf/VIA////A///A///AVIA/50p/DCB/AAA/AAA/faO/8xd/8yf/8zh/SPK/AAA/jga/VIA////A///A///AVIA/94t/rhO/WRI/haN/5uY/7wb/8xd/8yf/7yg/tma/72r/VIA////A///A///AVIA/94u/6sQ/6tT/7uV/7uX/7vY/7wa/7xc/8ye/8yg/93s/VIA////A///A///AVIA/94u/6rO/ylO/5sS/7uU/7uW/1qV/yoW/7xc/8ye/93s/VIA////A///A///AVIA/+5w/zlL/DDD/bVK/6tS/mdN/AAA/AAA/YTK/7xc/93r/VIA////A///A///AVIA/+5x/3oL/NKD/mcK/6sQ/WQG/AAA/AAA/BAA/5uZ/93r/VIA////A///A///AVIA/+6z/6qM/6qM/6qM/6rO/ujM/IGC/BBA/aUJ/7vX/93r/VIA////A///A///AVIA/+5w/+6y/+5w/+4v/94t/93s/82r/93r/93r/93r/92p/VIA////A///A///AWJA6VJA/WJB/WJB/WJB/WJB/WJB/WJB/WJB/WJB/WJB/VJA/WJA6///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A")
                ,'icon_texmix'             : ("///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///APPP7ccc/ddd/ccc/bbb/bbb/ddd/eee/RRR9///A///A///A///A///A///A///AYYY+yyy/fff/qqq/000/111/jjj/sss/eee////A///A///A///A///A///A///Aaaa9XXX/AAA/III/rrr/xxx/LLL/GGG/VVV////A///A///A///A///A///A///AZZZ9hhh/JJJ/XXX/rrr/uuu/kkk/eee/YYY////A///A///A///A///A///A///AVYd/sv0/imq/nqu/rrr/ttt/vvv/000/bbb////A///APPP7ccc/ddd/ccc/Ycg/Qcu/Sfz/Sfz/Wi1/fin/RRR/bbb/yyy/bbb////A///AYYY+yyy/fff/qqq/x05/Rfz/99+/++//Rfz/PSX/AAA/AAA/uuu/bbb////A///Aaaa9XXX/AAA/III/orw/Rfz/////////Rfz/lpu/XXX/eee/000/ccc////A///AZZZ9hhh/JJJ/XXX/osw/Tgz/Rfz/Rez/Qdw/Wae/bbb9aaa9YYY9PPP7///A///AYYY9vvv/lll/ppp/rrr/pty/sw1/w06/Ych////A///A///A///A///A///A///AZZZ9sss/SSS/iii/hhh/RRR/bbb/yyy/bbb////A///A///A///A///A///A///AZZZ9rrr/JJJ/eee/SSS/AAA/AAA/uuu/bbb////A///A///A///A///A///A///AZZZ+111/ttt/uuu/ooo/XXX/eee/000/ccc////A///A///A///A///A///A///AOOO4aaa9aaa9ZZZ9ZZZ9bbb9aaa9YYY9PPP7///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A")
                ,'icon_texmixcol'          : ("///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///AaOE7mcS/ndT/mcS/lbS/kbS/ndU/neV/bQH9///A///A///A///A///A///A///AiYP+92o/niY/0tg//4p//6s/pme/wun/neV////A///A///A///A///A///A///AkZP9aYT/AAA/LJF/5vd//2j/OMH/GHH/eVN////A///A///A///A///A///A///AjYP9qlZ/OKE/haO/7wb/+zf/voZ/jgY/hYP////A///A///A///A///A///A///AXae/z27/qty/ux2/9wZ/+yc//1f//5o/lbS////A///AaOE7mcS/ndT/mcS/adh/Qcu/Sfz/Sfz/Wi1/lot/ZUK/leQ//3l/kbR////A///AiYP+92o/niY/0tg/25+/Rfz/99+/++//Rfz/TXc/AAA/BAA/9zg/lbS////A///AkZP9aYT/AAA/LJF/tx2/Rfz/////////Rfz/quz/bZU/lhX//6o/lcS////A///AjYP9qlZ/OKE/haO/uy3/Tgz/Rfz/Rez/Qdw/Ybg/laQ9laQ9iYP9aOE7///A///AhXP9/1f/6sQ/8vW/9wZ/wz4/y28/26//aej////A///A///A///A///A///A///AhXQ98xd/eWH/znR/xmR/ZUK/leQ//3l/kbR////A///A///A///A///A///A///AhYR97xb/TMA/xkL/dVG/AAA/BAA/9zg/lbS////A///A///A///A///A///A///AiYR+/7q//zb//0d/1tb/bZU/lhX//6o/lcS////A///A///A///A///A///A///AZNE4iZS9iZS9iYR9jZQ9laQ9laQ9iYP9aOE7///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A")
                ,'icon_texparam'           : ("///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A27wAOOO5GGG/BBB9AAA5AAAwAAAnAAAO27wA27wA27wA27wA27wA27wA///A875F27wAYYYZPPP/KKK/III/BBB/AAA/AAA/AAAxAAAB27wA27wA27wA27wA///AoooO875K27wAaaaTRRR/eee/lll/SSS/AAA/AAA/AAAk27wA27wA27wA27wA///AeeeX222V876J27wAbbbkSSS/iii/mmm/TTT/AAA/AAA/CCCW27wA27wA27wA///AXXXfxxxftttW887I27wAcccwSSS/OOO/PPP/III/RRR/CCC/CCC3CCCL27wA///ATTTmtttsQQQvbbbd887H27wAdddrVVV/PPP/hhh/222/lll/NNN/HFE/KFCo///APPPssss3HHH6NNNwZZZd988G27wA27wAXXXlXXX/999/333/jhg/ZPK/WOJ5///AMMMvsss/jjj1XXXxrrrf333R998F27xA27wAYYYvggg/554/meX/eUO/ZQL////AJJJyvvv/jjj/oooztttoyyyc444Q999E27xAfffAYXW7jeZ/4yt/pfX/gWP////AHHH0zzz/iii/jjj+oooytttnlllggggX+99D27xALFAFKGD9wql/2wr/peW////AFFF3333/HHH/QQQ/jjj9mmmyDDD8KKKxTTTe555D26xAIFDKMHE+0vq/1uo////ADDD6666/HHH/QQQ/jjj/kkk8DDD+BBB+JJJyrrrR+++C26xAKFDROKG/wog+///ABBB9555/777/333/000/www/rrr9bbb6fffv000Y555M///B26xAKFCYOKF0///ABBB5BBB9DDD6EEE4GGG1IIIzKKKxNNNtPPPmSSSfUUUXUUUODDDE26xA27wA///A")
                ,'icon_emission'           : ("///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A27wA27wA27wAAAAgAAA/AAAg27wA27wA27wA///A///A///A///A///A///A///A27wAAAAFAAAxAAA/AAA/AAA/AAAxAAAF27wA///A///A///A///A///A///A///A27wAAAAZooo5////444/nnn/KKK2AAAZ27wA///A///A///A///A///A///A///A27wAAAALSSS/ggg/bbb/AAA/AAA/AAAL27wA///A///A///A///A///A///A///A27wAAAAYrrr/////777/nnn/KKJ+AAAZ27wA///A///A///A///A///A///A///A27wAPNBRTRI+kiX8ebQ+ebN8NLA+PNCP27wA///A///A///A///A///A///A///AQQABVRB1qlQ483g2qlR+81Z2pkO6VRB0QQAB///A///A///A///A///A///A///ATQBlieP685t361ezjcD+5ySx61c0dYG6TQBl///A///A///A///A///A///A///AVRA453x650gwhbB93vRthbB+4yXvwrX0VRA4///A///A///A///A///A///A///AVRA+++8941ow2xbs0tRp0tRp1vUr2yiyVRA+///A///A///A///A///A///A///AUQA48868/++999772yiszuYo2yhsvsdxVRA5///A///A///A///A///A///A///ATPBlqof6//////++64yy64yy7611cYK4TPBl///A///A///A///A///A///A///AKKABUQA1qnf59989//++6525ifT4UQA1KKAB///A///A///A///A///A///A///A27wAKKABSPBkUQA4VQA+UQA4SPBkKKAB27wA///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A")
                ,'icon_spectex'            : ("///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///AAAATGGGzAAAiAAAA27wA27wA27wA27wA27wA27wA27wAAAADAAAjGGGxAAAT///AFFFy555/SBx/MA5+ASx9AhZ9ArC9AwA9WvA9xnA9/WA97AA/xBB/555/FFFz///AAAAUccc/ka1/MA6/ASx/AhZ/ArC/AwA/WvA/xnA//WA/9AA/1ff/SSS+AAAZ///A27wAMMM6ph2/MA6/Xi0/AhZ/ArC/AwA/WvA/xnA//WA/1bb/jjj/AAAY27wA///A27wABBBnpmv/ni6/lr1/AhZ/ArC/AwA/WvA/xnA//WA/6vv/SSS/AAAE27wA///A27wAAAAEGGG1PPP/SUY/Zsn/ArC/AwA/hyS/xnA//WA/5uu/DDDw27wA27wA///A27wA27wAAAABAAAEIII3oyw/ArC/WvW/syn/31u/3vr/nll/AAAa27wA27wA///A27wA27wA///A///AAAAnlus/BrE/v4v/TTT/kkk/444/PPP+AAAE27wA27wA///A27wA27wA27wA27wAAAAZnnn/444/555/GGG3AAAdEEExAAAM27wA27wA27wA///A27wA27wA27wA27wAAAAKaaa/555/zzz/AAAn27wA27wA27wA27wA27wA27wA///A27wA27wA27wA27wAAAAALLL8555/iii/AAAX27wA27wA27wA27wA27wA27wA///A27wA27wA27wA27wA27wAAAAPKKK6AAArAAAB27wA27wA27wA27wA27wA27wA///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A")
                ,'icon_c_filter'           : ("///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///AAAASGGG1BBBsAAAW27wA27wA27wA27wA27wA27wA27wAAAAWBBBsGGGyAAAU///AHHHx555/333/ddd/AAAl27wA27wA27wA27wA27wAAAAlddd/333/555/FFFz///AAAAUMMM8eee/555/ccc/AAAT27wA27wA27wAAAATccc/555/eee/MMM8AAAV///A27wAAAAAAAAbfff/222/GGG1AAAA27wAAAAAGGG1222/fff/AAAbAAAA27wA///A27wA27wAAAAAFFFz222/hhh/AAAW27wAAAAWhhh/222/FFFzAAAA27wA27wA///A27wA27wA27wAAAAQccc/333/EEEz27wAEEEz333/ccc/AAAQ27wA27wA27wA///A27wA27wA27wA27wAGGG1444/aaa/AAAdaaa/444/GGG127wA27wA27wA27wA///A27wA27wA27wA27wAAAAakkk/000/UUU/000/kkk/AAAa27wA27wA27wA27wA///A27wA27wA27wA27wAAAACGGG1xxx/555/xxx/GGG1AAAC27wA27wA27wA27wA///A27wA27wA27wA27wA27wAAAAFAAAoJJJ1AAAoAAAF27wA27wA27wA27wA27wA///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A")
                ,'icon_c_camera'           : ("///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A27wA27wA27wA27wAAAAAAAABAAABAAABAAABAAAA27wA27wA27wA27wA///A///ANNN6MMM/MMM/JJJ/MMM/LLL/LLL/LLL/LLL/MMM/MMM/MMM/MMM/OOO6///A///AMMM/vvv/ttt/ccc/mmm/jjj/ggg/hhh/jjj/ooo/sss/www/iii/MMM////A///AMMM/uuu/eee/RRR/XXX/ZZZ/mmm/xxx/ppp/ggg/jjj/ppp/eee/MMM////A///AMMM/ttt/aaa/OOO/WWW/rrr/aaa/TTT/jjj/zzz/hhh/lll/ccc/MMM////A///AMMM/sss/XXX/LLL/ggg/QQQ/HHH/KKK/QQQ/hhh/rrr/ggg/bbb/MMM////A///AMMM/rrr/VVV/JJJ/ooo/QQQ/TTT/III/JJJ/RRR/yyy/ddd/ZZZ/MMM////A///AMMM/sss/UUU/JJJ/eee/eee/www/RRR/EEE/VVV/ooo/ccc/ZZZ/MMM////A///AMMM/uuu/VVV/KKK/RRR/kkk/fff/QQQ/OOO/ooo/bbb/eee/ZZZ/MMM////A///AMMM/xxx/WWW/LLL/NNN/SSS/eee/ooo/hhh/YYY/YYY/ggg/ZZZ/MMM////A///AMMM/zzz/vvv/aaa/fff/VVV/OOO/PPP/RRR/bbb/mmm/sss/fff/NNN9///A///ANNN6MLJ/MJE/IHG/OOO+ggg/bbb/ccc/eee/jjj/NNN+MMM/NNN9MMMP///A///A27wAMHAl9jA/NIApMMMmWWW/888/////888/bbb/NNNmAAAA27wA27wA///A///A27wALGAPMHAoMHASMMMGSSS/777/////888/WWW/NNNF27wA27wA27wA///A///A27wA27wA27wA27wA27wARRRiPPP+QQQ/RRR+VVVi27wA27wA27wA27wA///A")
                ,'icon_c_environment'      : ("///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///AGMV1HNV7HNV7HNV7HNV7HNV7HNV7HNV7HNV7HNV7HNV7GMV1///A///A///A///AHNV7y0u/z0u/y0t/xzs/wyr/wyq/vxp/uxo/twn/svm/HNV7///A///A///A///AIOW8341/tvm/qtj/qtj/qtj/qtj/qtj/qtj/qtj/two/HNV7///A///A///A///AINV8sts/cdc/qrp/uxp/qtj/qtj/qtj/qtj/qtj/tvo/HNU7///A///A///A///AGMV7svy/Ubh/VZb/ZZZ/xyt/ruk/qtj/qtj/rul/bcb/GLU7///A///A///A///AGMV7twz/Uci/Uci/Tbg/TUU/ssq/y0u/vxr/TVT/fko/GMV7///A///A///A///AGMV7vy0/Vdj/Zgl/Xfk/Uci/RWZ/TVV/PSU/Tag/hnr/GMV7///A///A///A///AGMV7wz1/gmq/023/txz/Xfk/Uci/Uci/Uci/Uci/jos/GMV7///A///A///A///AGMV7y02/jos/////023/Zgl/Uci/Uci/Uci/Uci/kpt/GMV7///A///A///A///AGMV7z23/ahm/jos/gmq/Vdj/Uci/Uci/Uci/Uci/mru/GMV7///A///A///A///AGMV7x02/023/y02/wz1/vy0/uxz/swy/rux/ptw/lqu/GMV7///A///A///A///AGMV1GMV7GMV7GMV7GMV7GMV7GMV7GMV7GMV7GMV7GMV7GMV1///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A")
                ,'icon_c_sampler'          : ("///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A27wA27wA27wAMMMXSSS3MMMg27wA27wA27wA27wAMMMdTTT2MMMc27wA27wA27wA27wA27wAMMMSggg/////XXX+MMMB27wA27wA27wAUUU8////jjj/MMMT27wA27wA27wAMMMIYYY8+++/xxx/NNNuMMMCMMMCMMMCMMMCNNNqwww/////ZZZ9MMMJ27wAMMMASSS0666/+++/fff/bbb/bbb/eee/eee/bbb/bbb/ddd/999/777/SSS327wAMMMGjjj/////////////////////////////////////////////////lll/MMMI27wARRRz555/999/ccc/YYY/YYY+aaa+bbb+YYY+YYY+bbb/999/666/RRR2MMMB27wAMMMHWWW7999/yyy/NNNu27wA27wA27wA27wANNNtxxx/+++/YYY8MMMI27wAVVqARfzGOTZZeee/////WWW+QctHRfzLRfzLRfzGUUU8////hhh/OSYaRfzGVVqARfzGRezcRfz5PXj8STV5NPSiRezcRfz5Rfz5RezcNQThRST6PYk7Rfz5RezcRfzGRfzLRfz5////////Rfz5RfzMRfz5////////Rfz5RfzMRfz5////////Rfz5RfzLRfzLRfz5////////Rfz5RfzMRfz5////////Rfz5RfzMRfz5////////Rfz5RfzLRfzGRezcRfz5Rfz5RezcRfzKRezcRfz5Rfz5RezcRfzKRezcRfz5Rfz5RezcRfzGVVqARfzGRfzLRfzLRfzGVVqARfzGRfzLRfzLRfzGVVqARfzGRfzLRfzLRfzGVVqA///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A")
                ,'icon_c_integrator'       : ("///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A27wA27wAAAAAEJPYHMT0MRY+GLS0EJPYAAAA27wA27wA27wA27wA27wA27wA27wA27wAAAVAEJPoVai/lr0/elv/Xeo/LRZ/EIPnDHOEAAVA27wA27wA27wA27wA27wA27wAEIPcZel/rw5/cir/NTb/SYi/PWh/MSb/QVd/KPW6EJPfAJSB27wA27wA27wAAAAAHMT4ty7/hmv/FKQyDGMXEJP7bhq/nt2/pv4/sy6/diq/EJQuIIQC27wA27wAFIQGRWd/u08/TYf/CFKQDGLfUai/flv/Zfp/SZj/bgp/rx6/fks/EJQuAJSB27wAAJSBINT7uz8/glt/EIOqGKQ4Xeo/SYi/KQY/SZk/IOW/Ydl/ty7/diq/EJPg27wA27wAEJPhflt/u08/Yel/JOW/QXi/HNV/TZi/Yfp/GLS6EJPuejr/tz8/HMT6AMMB27wAGGMCFLRxiow/u08/ciq/SZk/Yeo/gnw/Vaj/DINhDGJQQVd/u08/SXe/FIQG27wA27wAFJODFKRyhmu/u08/sy7/pv4/cir/FJQ7CGLTEIPudir/uz8/JOU6AMMB27wA27wA27wAFJODEJPjKPW8UZh/RXg/RYj/QXg/MSa/Zfo/pv4/diq/EJPg27wA27wA27wA27wA27wA27wAFKQDEIPLEJPtPVe/ahr/flv/jpz/diq/FJQtAJSB27wA27wA27wA27wA27wA27wA27wA27wAAMMBEJPeGLS5OUb/INU5EJPeAMMB27wA27wA27wA27wA27wA27wA27wA27wA27wA27wA27wAAAAAEIQEAAVA27wA27wA27wA27wA///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A")
                ,'icon_c_volumeintegrator' : ("///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A27wA27wA27wA27wAMMMAMMMWNNN8NNN9MMMWMMMA27wA27wA27wA27wA///A27wA27wAAAAAEJPYIMS3MRY/KOU/gik/ggg/TTT/MMMzMMMR27wA27wA27wA27wA27wAAAVAFJPtVai/lr0/elv/Xeo/LRZ/NQU/ggh/ddd/RRR/MMMvMMMN27wA27wA27wAHKOvZel/rw5/cir/NTb/SYi/PWh/MSb/QVd/LQW/TWZ/aaa/PPP/MMMh27wAAAAAIMS/ty7/hmv/OSX/gik/HMS/bhq/nt2/pv4/sy6/diq/MQV/hhh/MMM/27wAFIQGRWd/u08/TYf/lmn/bdf/Uai/flv/Zfp/SZj/bgp/rx6/fks/NRV/MMN/27wAAJSBINT/uz8/glt/TWa/LPU/Xeo/SYi/KQY/SZk/IOW/Ydl/ty7/diq/IKO/27wA27wAIKO/flt/u08/Yel/JOW/QXi/HNV/TZi/Yfp/INT/LOT/ejr/tz8/IMT/AMMB27wAMMM/SWb/iow/u08/ciq/SZk/Yeo/gnw/Vaj/PRU/XXY/QVd/u08/SXe/FIQG27wAMMM/899/PTY/hmu/u08/sy7/pv4/cir/HLR/UVX/KOT/dir/uz8/JOU/AMMB27wAMMM/////vww/WZd/MRX/UZh/RXg/RYj/QXg/MSa/Zfo/pv4/diq/IKO/27wA27wAMMM/////999/////999/123/VZd/PVe/ahr/flv/jpz/diq/RUa/MMN/27wA27wAMMMxRRR/rrr/888/////////+++/jmp/MRX/OUb/NRX/WYb/PQQ/MMMx27wA27wA27wANNNEMMMaMMMxWWW/www/+++/999/uuu/UUV/MMMxMMMaNNNE27wA27wA///A27wA27wA27wA27wANNNIMMMfMMM1MMM1MMMfNNNI27wA27wA27wA27wA///A")
                ,'icon_help'               : ("///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A27wA27wA27wAAAAOGGGtFFF4HHH6GGG3GGGqAAAK27wA27wA27wA///A///A///A27wAAAABEEEnNNN7vvv/666/888/888/vvv/III7EEEgAAAA27wA///A///A///A27wAEEEmfff+333/333/333/lll/999/999/999/WWW8EEEd27wA///A///A///AAAAPSSS7333/zzz/111/xxx/III/+++/777/999/999/JJJ6AAAJ///A///A///AFFFtxxx/yyy/xxx/zzz/444/999/777/666/777/999/ppp/FFFh///A///A///AEEE4555/uuu/vvv/xxx/ttt/MMM/yyy/666/666/777/111/GGGy///A///A///AJJJ7666/sss/ttt/vvv/yyy/ttt/HHH/yyy/666/555/777/FFF5///A///A///ADDD3777/sss/qqq/lll/vvv/yyy/sss/EEE/777/444/xxx/GGGv///A///A///ADDDq000/xxx/iii/FFF/kkk/lll/hhh/HHH/555/333/kkk/DDDe///A///A///AAAAJNNN8999/rrr/iii/DDD/DDD/GGG/000/000/000/GGG6AAAE///A///A///A27wACCCcccc9999/yyy/ttt/sss/www/000/000/QQQ8CCCT27wA///A///A///A27wA27wACCCXMMM7www/444/777/000/ooo+III5BBBR27wA27wA///A///A///A27wA27wA27wAAAAFBBBbEEEsEEE1FFFqBBBZAAAD27wA27wA27wA///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A")
            }
            bars = {
                 'bar_spectrum'            : ("AAA/AAA/AAB/AAC/AAD/BAF/CAH/DAK/EAN/GAQ/HAU/JAX/LAb/MAf/OAj/PAm/QAq/RAt/SAv/SAx/SAz/SA1/SA3/SA4/SA5/RA6/PA6/OA6/MA6/IA5/CA4/AA3/AD2/AJ1/AN0/AQy/ATw/AVu/AYr/AZo/Abl/Adj/Aeg/Agd/Ahb/AiY/AjW/AlT/AmR/AnO/AoL/AqI/AqE/ArA/AsA/AtA/AuA/AvA/AvA/AwA/AwA/AwA/AwA/AwA/AwA/AwA/AwA/CwA/OvA/UvA/ZuA/euA/htA/lsA/orA/rqA/tpA/woA/ymA/0lA/2jA/4hA/5fA/7eA/8cA/9aA/+YA//VA//TA//QA//NA//KA//FA/+AA/+AA/8AA/7AA/6AA/5AA/3AA/2AA/0AA/yAA/wAA/uAA/sAA/qAA/oAA/lAA/jAA/hAA/fAA/dAA/bAA/ZAA/YAA/WAA/UAA/SAA/RAA/QAA/OAA/NAA/MAA/LAA/KAA/JAA/IAA/HAA/GAA/FAA/FAA/EAA/DAA/DAA/CAA/CAA/CAA/AAA/AAA/AAB/AAC/AAD/BAF/CAH/DAK/EAN/GAQ/HAU/JAX/LAb/MAf/OAj/PAm/QAq/RAt/SAv/SAx/SAz/SA1/SA3/SA4/SA5/RA6/PA6/OA6/MA6/IA5/CA4/AA3/AD2/AJ1/AN0/AQy/ATw/AVu/AYr/AZo/Abl/Adj/Aeg/Agd/Ahb/AiY/AjW/AlT/AmR/AnO/AoL/AqI/AqE/ArA/AsA/AtA/AuA/AvA/AvA/AwA/AwA/AwA/AwA/AwA/AwA/AwA/AwA/CwA/OvA/UvA/ZuA/euA/htA/lsA/orA/rqA/tpA/woA/ymA/0lA/2jA/4hA/5fA/7eA/8cA/9aA/+YA//VA//TA//QA//NA//KA//FA/+AA/+AA/8AA/7AA/6AA/5AA/3AA/2AA/0AA/yAA/wAA/uAA/sAA/qAA/oAA/lAA/jAA/hAA/fAA/dAA/bAA/ZAA/YAA/WAA/UAA/SAA/RAA/QAA/OAA/NAA/MAA/LAA/KAA/JAA/IAA/HAA/GAA/FAA/FAA/EAA/DAA/DAA/CAA/CAA/CAA/AAA/AAA/AAB/AAC/AAD/BAF/CAH/DAK/EAN/GAQ/HAU/JAX/LAb/MAf/OAj/PAm/QAq/RAt/SAv/SAx/SAz/SA1/SA3/SA4/SA5/RA6/PA6/OA6/MA6/IA5/CA4/AA3/AD2/AJ1/AN0/AQy/ATw/AVu/AYr/AZo/Abl/Adj/Aeg/Agd/Ahb/AiY/AjW/AlT/AmR/AnO/AoL/AqI/AqE/ArA/AsA/AtA/AuA/AvA/AvA/AwA/AwA/AwA/AwA/AwA/AwA/AwA/AwA/CwA/OvA/UvA/ZuA/euA/htA/lsA/orA/rqA/tpA/woA/ymA/0lA/2jA/4hA/5fA/7eA/8cA/9aA/+YA//VA//TA//QA//NA//KA//FA/+AA/+AA/8AA/7AA/6AA/5AA/3AA/2AA/0AA/yAA/wAA/uAA/sAA/qAA/oAA/lAA/jAA/hAA/fAA/dAA/bAA/ZAA/YAA/WAA/UAA/SAA/RAA/QAA/OAA/NAA/MAA/LAA/KAA/JAA/IAA/HAA/GAA/FAA/FAA/EAA/DAA/DAA/CAA/CAA/CAA/AAA/AAA/AAB/AAC/AAD/BAF/CAH/DAK/EAN/GAQ/HAU/JAX/LAb/MAf/OAj/PAm/QAq/RAt/SAv/SAx/SAz/SA1/SA3/SA4/SA5/RA6/PA6/OA6/MA6/IA5/CA4/AA3/AD2/AJ1/AN0/AQy/ATw/AVu/AYr/AZo/Abl/Adj/Aeg/Agd/Ahb/AiY/AjW/AlT/AmR/AnO/AoL/AqI/AqE/ArA/AsA/AtA/AuA/AvA/AvA/AwA/AwA/AwA/AwA/AwA/AwA/AwA/AwA/CwA/OvA/UvA/ZuA/euA/htA/lsA/orA/rqA/tpA/woA/ymA/0lA/2jA/4hA/5fA/7eA/8cA/9aA/+YA//VA//TA//QA//NA//KA//FA/+AA/+AA/8AA/7AA/6AA/5AA/3AA/2AA/0AA/yAA/wAA/uAA/sAA/qAA/oAA/lAA/jAA/hAA/fAA/dAA/bAA/ZAA/YAA/WAA/UAA/SAA/RAA/QAA/OAA/NAA/MAA/LAA/KAA/JAA/IAA/HAA/GAA/FAA/FAA/EAA/DAA/DAA/CAA/CAA/CAA/AAA/AAA/AAB/AAC/AAD/BAF/CAH/DAK/EAN/GAQ/HAU/JAX/LAb/MAf/OAj/PAm/QAq/RAt/SAv/SAx/SAz/SA1/SA3/SA4/SA5/RA6/PA6/OA6/MA6/IA5/CA4/AA3/AD2/AJ1/AN0/AQy/ATw/AVu/AYr/AZo/Abl/Adj/Aeg/Agd/Ahb/AiY/AjW/AlT/AmR/AnO/AoL/AqI/AqE/ArA/AsA/AtA/AuA/AvA/AvA/AwA/AwA/AwA/AwA/AwA/AwA/AwA/AwA/CwA/OvA/UvA/ZuA/euA/htA/lsA/orA/rqA/tpA/woA/ymA/0lA/2jA/4hA/5fA/7eA/8cA/9aA/+YA//VA//TA//QA//NA//KA//FA/+AA/+AA/8AA/7AA/6AA/5AA/3AA/2AA/0AA/yAA/wAA/uAA/sAA/qAA/oAA/lAA/jAA/hAA/fAA/dAA/bAA/ZAA/YAA/WAA/UAA/SAA/RAA/QAA/OAA/NAA/MAA/LAA/KAA/JAA/IAA/HAA/GAA/FAA/FAA/EAA/DAA/DAA/CAA/CAA/CAA/AAA/AAA/AAB/AAC/AAD/BAF/CAH/DAK/EAN/GAQ/HAU/JAX/LAb/MAf/OAj/PAm/QAq/RAt/SAv/SAx/SAz/SA1/SA3/SA4/SA5/RA6/PA6/OA6/MA6/IA5/CA4/AA3/AD2/AJ1/AN0/AQy/ATw/AVu/AYr/AZo/Abl/Adj/Aeg/Agd/Ahb/AiY/AjW/AlT/AmR/AnO/AoL/AqI/AqE/ArA/AsA/AtA/AuA/AvA/AvA/AwA/AwA/AwA/AwA/AwA/AwA/AwA/AwA/CwA/OvA/UvA/ZuA/euA/htA/lsA/orA/rqA/tpA/woA/ymA/0lA/2jA/4hA/5fA/7eA/8cA/9aA/+YA//VA//TA//QA//NA//KA//FA/+AA/+AA/8AA/7AA/6AA/5AA/3AA/2AA/0AA/yAA/wAA/uAA/sAA/qAA/oAA/lAA/jAA/hAA/fAA/dAA/bAA/ZAA/YAA/WAA/UAA/SAA/RAA/QAA/OAA/NAA/MAA/LAA/KAA/JAA/IAA/HAA/GAA/FAA/FAA/EAA/DAA/DAA/CAA/CAA/CAA/AAA/AAA/AAB/AAC/AAD/BAF/CAH/DAK/EAN/GAQ/HAU/JAX/LAb/MAf/OAj/PAm/QAq/RAt/SAv/SAx/SAz/SA1/SA3/SA4/SA5/RA6/PA6/OA6/MA6/IA5/CA4/AA3/AD2/AJ1/AN0/AQy/ATw/AVu/AYr/AZo/Abl/Adj/Aeg/Agd/Ahb/AiY/AjW/AlT/AmR/AnO/AoL/AqI/AqE/ArA/AsA/AtA/AuA/AvA/AvA/AwA/AwA/AwA/AwA/AwA/AwA/AwA/AwA/CwA/OvA/UvA/ZuA/euA/htA/lsA/orA/rqA/tpA/woA/ymA/0lA/2jA/4hA/5fA/7eA/8cA/9aA/+YA//VA//TA//QA//NA//KA//FA/+AA/+AA/8AA/7AA/6AA/5AA/3AA/2AA/0AA/yAA/wAA/uAA/sAA/qAA/oAA/lAA/jAA/hAA/fAA/dAA/bAA/ZAA/YAA/WAA/UAA/SAA/RAA/QAA/OAA/NAA/MAA/LAA/KAA/JAA/IAA/HAA/GAA/FAA/FAA/EAA/DAA/DAA/CAA/CAA/CAA/AAA/AAA/AAB/AAC/AAD/BAF/CAH/DAK/EAN/GAQ/HAU/JAX/LAb/MAf/OAj/PAm/QAq/RAt/SAv/SAx/SAz/SA1/SA3/SA4/SA5/RA6/PA6/OA6/MA6/IA5/CA4/AA3/AD2/AJ1/AN0/AQy/ATw/AVu/AYr/AZo/Abl/Adj/Aeg/Agd/Ahb/AiY/AjW/AlT/AmR/AnO/AoL/AqI/AqE/ArA/AsA/AtA/AuA/AvA/AvA/AwA/AwA/AwA/AwA/AwA/AwA/AwA/AwA/CwA/OvA/UvA/ZuA/euA/htA/lsA/orA/rqA/tpA/woA/ymA/0lA/2jA/4hA/5fA/7eA/8cA/9aA/+YA//VA//TA//QA//NA//KA//FA/+AA/+AA/8AA/7AA/6AA/5AA/3AA/2AA/0AA/yAA/wAA/uAA/sAA/qAA/oAA/lAA/jAA/hAA/fAA/dAA/bAA/ZAA/YAA/WAA/UAA/SAA/RAA/QAA/OAA/NAA/MAA/LAA/KAA/JAA/IAA/HAA/GAA/FAA/FAA/EAA/DAA/DAA/CAA/CAA/CAA/AAA/AAA/AAB/AAC/AAD/BAF/CAH/DAK/EAN/GAQ/HAU/JAX/LAb/MAf/OAj/PAm/QAq/RAt/SAv/SAx/SAz/SA1/SA3/SA4/SA5/RA6/PA6/OA6/MA6/IA5/CA4/AA3/AD2/AJ1/AN0/AQy/ATw/AVu/AYr/AZo/Abl/Adj/Aeg/Agd/Ahb/AiY/AjW/AlT/AmR/AnO/AoL/AqI/AqE/ArA/AsA/AtA/AuA/AvA/AvA/AwA/AwA/AwA/AwA/AwA/AwA/AwA/AwA/CwA/OvA/UvA/ZuA/euA/htA/lsA/orA/rqA/tpA/woA/ymA/0lA/2jA/4hA/5fA/7eA/8cA/9aA/+YA//VA//TA//QA//NA//KA//FA/+AA/+AA/8AA/7AA/6AA/5AA/3AA/2AA/0AA/yAA/wAA/uAA/sAA/qAA/oAA/lAA/jAA/hAA/fAA/dAA/bAA/ZAA/YAA/WAA/UAA/SAA/RAA/QAA/OAA/NAA/MAA/LAA/KAA/JAA/IAA/HAA/GAA/FAA/FAA/EAA/DAA/DAA/CAA/CAA/CAA/AAA4AAA/AAB/AAC/AAD/BAF/CAH/DAK/EAN/GAQ/HAU/JAX/LAb/MAf/OAj/PAm/QAq/RAt/SAv/SAx/SAz/SA1/SA3/SA4/SA5/RA6/PA6/OA6/MA6/IA5/CA4/AA3/AD2/AJ1/AN0/AQy/ATw/AVu/AYr/AZo/Abl/Adj/Aeg/Agd/Ahb/AiY/AjW/AlT/AmR/AnO/AoL/AqI/AqE/ArA/AsA/AtA/AuA/AvA/AvA/AwA/AwA/AwA/AwA/AwA/AwA/AwA/AwA/CwA/OvA/UvA/ZuA/euA/htA/lsA/orA/rqA/tpA/woA/ymA/0lA/2jA/4hA/5fA/7eA/8cA/9aA/+YA//VA//TA//QA//NA//KA//FA/+AA/+AA/8AA/7AA/6AA/5AA/3AA/2AA/0AA/yAA/wAA/uAA/sAA/qAA/oAA/lAA/jAA/hAA/fAA/dAA/bAA/ZAA/YAA/WAA/UAA/SAA/RAA/QAA/OAA/NAA/MAA/LAA/KAA/JAA/IAA/HAA/GAA/FAA/FAA/EAA/DAA/DAA/CAA/CAA/CAA4AAAsAAA/AAB/AAC/AAD/BAF/CAH/DAK/EAN/GAQ/HAU/JAX/LAb/MAf/OAj/PAm/QAq/RAt/SAv/SAx/SAz/SA1/SA3/SA4/SA5/RA6/PA6/OA6/MA6/IA5/CA4/AA3/AD2/AJ1/AN0/AQy/ATw/AVu/AYr/AZo/Abl/Adj/Aeg/Agd/Ahb/AiY/AjW/AlT/AmR/AnO/AoL/AqI/AqE/ArA/AsA/AtA/AuA/AvA/AvA/AwA/AwA/AwA/AwA/AwA/AwA/AwA/AwA/CwA/OvA/UvA/ZuA/euA/htA/lsA/orA/rqA/tpA/woA/ymA/0lA/2jA/4hA/5fA/7eA/8cA/9aA/+YA//VA//TA//QA//NA//KA//FA/+AA/+AA/8AA/7AA/6AA/5AA/3AA/2AA/0AA/yAA/wAA/uAA/sAA/qAA/oAA/lAA/jAA/hAA/fAA/dAA/bAA/ZAA/YAA/WAA/UAA/SAA/RAA/QAA/OAA/NAA/MAA/LAA/KAA/JAA/IAA/HAA/GAA/FAA/FAA/EAA/DAA/DAA/CAA/CAA/CAAsAAAcAAA/AAB/AAC/AAD/BAF/CAH/DAK/EAN/GAQ/HAU/JAX/LAb/MAf/OAj/PAm/QAq/RAt/SAv/SAx/SAz/SA1/SA3/SA4/SA5/RA6/PA6/OA6/MA6/IA5/CA4/AA3/AD2/AJ1/AN0/AQy/ATw/AVu/AYr/AZo/Abl/Adj/Aeg/Agd/Ahb/AiY/AjW/AlT/AmR/AnO/AoL/AqI/AqE/ArA/AsA/AtA/AuA/AvA/AvA/AwA/AwA/AwA/AwA/AwA/AwA/AwA/AwA/CwA/OvA/UvA/ZuA/euA/htA/lsA/orA/rqA/tpA/woA/ymA/0lA/2jA/4hA/5fA/7eA/8cA/9aA/+YA//VA//TA//QA//NA//KA//FA/+AA/+AA/8AA/7AA/6AA/5AA/3AA/2AA/0AA/yAA/wAA/uAA/sAA/qAA/oAA/lAA/jAA/hAA/fAA/dAA/bAA/ZAA/YAA/WAA/UAA/SAA/RAA/QAA/OAA/NAA/MAA/LAA/KAA/JAA/IAA/HAA/GAA/FAA/FAA/EAA/DAA/DAA/CAA/CAA/CAAcAAAKAAAzAAB/AAC/AAD/BAF/CAH/DAK/EAN/GAQ/HAU/JAX/LAb/MAf/OAj/PAm/QAq/RAt/SAv/SAx/SAz/SA1/SA3/SA4/SA5/RA6/PA6/OA6/MA6/IA5/CA4/AA3/AD2/AJ1/AN0/AQy/ATw/AVu/AYr/AZo/Abl/Adj/Aeg/Agd/Ahb/AiY/AjW/AlT/AmR/AnO/AoL/AqI/AqE/ArA/AsA/AtA/AuA/AvA/AvA/AwA/AwA/AwA/AwA/AwA/AwA/AwA/AwA/CwA/OvA/UvA/ZuA/euA/htA/lsA/orA/rqA/tpA/woA/ymA/0lA/2jA/4hA/5fA/7eA/8cA/9aA/+YA//VA//TA//QA//NA//KA//FA/+AA/+AA/8AA/7AA/6AA/5AA/3AA/2AA/0AA/yAA/wAA/uAA/sAA/qAA/oAA/lAA/jAA/hAA/fAA/dAA/bAA/ZAA/YAA/WAA/UAA/SAA/RAA/QAA/OAA/NAA/MAA/LAA/KAA/JAA/IAA/HAA/GAA/FAA/FAA/EAA/DAA/DAA/CAA/CAAzCAAK///AAAAaAAB/AAC/AAD/BAF/CAH/DAK/EAN/GAQ/HAU/JAX/LAb/MAf/OAj/PAm/QAq/RAt/SAv/SAx/SAz/SA1/SA3/SA4/SA5/RA6/PA6/OA6/MA6/IA5/CA4/AA3/AD2/AJ1/AN0/AQy/ATw/AVu/AYr/AZo/Abl/Adj/Aeg/Agd/Ahb/AiY/AjW/AlT/AmR/AnO/AoL/AqI/AqE/ArA/AsA/AtA/AuA/AvA/AvA/AwA/AwA/AwA/AwA/AwA/AwA/AwA/AwA/CwA/OvA/UvA/ZuA/euA/htA/lsA/orA/rqA/tpA/woA/ymA/0lA/2jA/4hA/5fA/7eA/8cA/9aA/+YA//VA//TA//QA//NA//KA//FA/+AA/+AA/8AA/7AA/6AA/5AA/3AA/2AA/0AA/yAA/wAA/uAA/sAA/qAA/oAA/lAA/jAA/hAA/fAA/dAA/bAA/ZAA/YAA/WAA/UAA/SAA/RAA/QAA/OAA/NAA/MAA/LAA/KAA/JAA/IAA/HAA/GAA/FAA/FAA/EAA/DAA/DAA/CAA/CAAa///A///A///AAABfAAC/AAD/BAF/CAH/DAK/EAN/GAQ/HAU/JAX/LAb/MAf/OAj/PAm/QAq/RAt/SAv/SAx/SAz/SA1/SA3/SA4/SA5/RA6/PA6/OA6/MA6/IA5/CA4/AA3/AD2/AJ1/AN0/AQy/ATw/AVu/AYr/AZo/Abl/Adj/Aeg/Agd/Ahb/AiY/AjW/AlT/AmR/AnO/AoL/AqI/AqE/ArA/AsA/AtA/AuA/AvA/AvA/AwA/AwA/AwA/AwA/AwA/AwA/AwA/AwA/CwA/OvA/UvA/ZuA/euA/htA/lsA/orA/rqA/tpA/woA/ymA/0lA/2jA/4hA/5fA/7eA/8cA/9aA/+YA//VA//TA//QA//NA//KA//FA/+AA/+AA/8AA/7AA/6AA/5AA/3AA/2AA/0AA/yAA/wAA/uAA/sAA/qAA/oAA/lAA/jAA/hAA/fAA/dAA/bAA/ZAA/YAA/WAA/UAA/SAA/RAA/QAA/OAA/NAA/MAA/LAA/KAA/JAA/IAA/HAA/GAA/FAA/FAA/EAA/DAA/DAA/CAAf///A///A///A///A///AAACaAADzBAF/CAH/DAK/EAN/GAQ/HAU/JAX/LAb/MAf/OAj/PAm/QAq/RAt/SAv/SAx/SAz/SA1/SA3/SA4/SA5/RA6/PA6/OA6/MA6/IA5/CA4/AA3/AD2/AJ1/AN0/AQy/ATw/AVu/AYr/AZo/Abl/Adj/Aeg/Agd/Ahb/AiY/AjW/AlT/AmR/AnO/AoL/AqI/AqE/ArA/AsA/AtA/AuA/AvA/AvA/AwA/AwA/AwA/AwA/AwA/AwA/AwA/AwA/CwA/OvA/UvA/ZuA/euA/htA/lsA/orA/rqA/tpA/woA/ymA/0lA/2jA/4hA/5fA/7eA/8cA/9aA/+YA//VA//TA//QA//NA//KA//FA/+AA/+AA/8AA/7AA/6AA/5AA/3AA/2AA/0AA/yAA/wAA/uAA/sAA/qAA/oAA/lAA/jAA/hAA/fAA/dAA/bAA/ZAA/YAA/WAA/UAA/SAA/RAA/QAA/OAA/NAA/MAA/LAA/KAA/JAA/IAA/HAA/GAA/FAA/FAA/EAA/DAAzDAAa///A///A///A///A///A///A///AAADKBAFcCAHsDAK4EAN/GAQ/HAU/JAX/LAb/MAf/OAj/PAm/QAq/RAt/SAv/SAx/SAz/SA1/SA3/SA4/SA5/RA6/PA6/OA6/MA6/IA5/CA4/AA3/AD2/AJ1/AN0/AQy/ATw/AVu/AYr/AZo/Abl/Adj/Aeg/Agd/Ahb/AiY/AjW/AlT/AmR/AnO/AoL/AqI/AqE/ArA/AsA/AtA/AuA/AvA/AvA/AwA/AwA/AwA/AwA/AwA/AwA/AwA/AwA/CwA/OvA/UvA/ZuA/euA/htA/lsA/orA/rqA/tpA/woA/ymA/0lA/2jA/4hA/5fA/7eA/8cA/9aA/+YA//VA//TA//QA//NA//KA//FA/+AA/+AA/8AA/7AA/6AA/5AA/3AA/2AA/0AA/yAA/wAA/uAA/sAA/qAA/oAA/lAA/jAA/hAA/fAA/dAA/bAA/ZAA/YAA/WAA/UAA/SAA/RAA/QAA/OAA/NAA/MAA/LAA/KAA/JAA/IAA/HAA/GAA/FAA4FAAsEAAcDAAK///A///A///A///A")
                ,'bar_blackbody'           : ("+LA/+LA/+MA/+NA/+OA/+QA/+RA/+SA/+TA/+VA/+WA/+XA/+ZA/+aA//bA//cA//eA//fA//gA//hA//iA//kA//lA//mA//nA//oA//oB//pD//pE//qF//qG//qH//rI//rJ//sK//sM//sN//tO//tP//uQ//uR//vS//vT//vU//wW//wX//xY//xZ//xa//yb//yc//zd//ze//zg//0h//0i//1j//1k//1l//2m//2n//3p//3q//4r//4s//4t//5u//5v//6w//6y//6y//70//71//82//83//84//95//96//+7//+9///9/////////////////+///++//++//++//++//9+//9+//99//99//89//89//89//88//88//78//78//78//78//67//67//67//67//57//57//56//56//56//46//46//46//45//35//35//35//35//24//24//24//24//24//13//13//13//13//03//03//03//02//z2//z2//z2//z2//02//+LA/+LA/+MA/+NA/+OA/+QA/+RA/+SA/+TA/+VA/+WA/+XA/+ZA/QQQ//bA//cA//eA//fA//gA//hA//iA//kA//lA//mA//nA//oA//oB//pD//pE//qF//qG//qH//rI//rJ/QQQ//sM//sN//tO//tP//uQ//uR//vS//vT//vU//wW//wX//xY//xZ//xa//yb//yc//zd//ze//zg//0h//0i//1j//1k//1l//2m//2n//3p//3q//4r//4s//4t//5u//5v//6w//6y//6y//70//71//82//83//84//95//96//+7//+9///9/////////////////QQQ/++//++//++//++//9+//9+//99//99//89//89//89//88//88//78//78//78//78//67//67//67//67//57//57//56//56//56//46//46//46//45//35//35//35//35//24//24//24//24//24//13//13//13//13//03//03//03//02//z2//z2//z2//z2//02//+LA/+LA/+MA/+NA/+OA/+QA/+RA/+SA/+TA/+VA/+WA/+XA/+ZA/QQQ//bA//cA//eA//fA//gA//hA//iA//kA//lA//mA//nA//oA//oB//pD//pE//qF//qG//qH//rI//rJ/QQQ//sM//sN//tO//tP//uQ//uR//vS//vT//vU//wW//wX//xY//xZ//xa//yb//yc//zd//ze//zg//0h//0i//1j//1k//1l//2m//2n//3p//3q//4r//4s//4t//5u//5v//6w//6y//6y//70//71//82//83//84//95//96//+7//+9///9/////////////////QQQ/++//++//++//++//9+//9+//99//99//89//89//89//88//88//78//78//78//78//67//67//67//67//57//57//56//56//56//46//46//46//45//35//35//35//35//24//24//24//24//24//13//13//13//13//03//03//03//02//z2//z2//z2//z2//02//+LA/+LA/+MA/+NA/+OA/+QA/+RA/+SA/+TA/+VA/+WA/+XA/+ZA/QQQ//bA//cA//eA//fA//gA//hA//iA//kA//lA//mA//nA//oA//oB//pD//pE//qF//qG//qH//rI//rJ/QQQ//sM//sN//tO//tP//uQ//uR//vS//vT//vU//wW//wX//xY//xZ//xa//yb//yc//zd//ze//zg//0h//0i//1j//1k//1l//2m//2n//3p//3q//4r//4s//4t//5u//5v//6w//6y//6y//70//71//82//83//84//95//96//+7//+9///9/////////////////QQQ/++//++//++//++//9+//9+//99//99//89//89//89//88//88//78//78//78//78//67//67//67//67//57//57//56//56//56//46//46//46//45//35//35//35//35//24//24//24//24//24//13//13//13//13//03//03//03//02//z2//z2//z2//z2//02//+LA/+LA/+MA/+NA/+OA/+QA/+RA/+SA/+TA/+VA/+WA/+XA/+ZA/QQQ//bA//cA//eA//fA//gA//hA//iA//kA//lA//mA//nA//oA//oB//pD//pE//qF//qG//qH//rI//rJ/QQQ//sM//sN//tO//tP//uQ//uR//vS//vT//vU//wW//wX//xY//xZ//xa//yb//yc//zd//ze//zg//0h//0i//1j//1k//1l//2m//2n//3p//3q//4r//4s//4t//5u//5v//6w//6y//6y//70//71//82//83//84//95//96//+7//+9///9/////////////////QQQ/++//++//++//++//9+//9+//99//99//89//89//89//88//88//78//78//78//78//67//67//67//67//57//57//56//56//56//46//46//46//45//35//35//35//35//24//24//24//24//24//13//13//13//13//03//03//03//02//z2//z2//z2//z2//02//+LA/+LA/+MA/+NA/+OA/+QA/+RA/+SA/+TA/+VA/+WA/+XA/+ZA/+aA//bA//cA//eA//fA//gA//hA//iA//kA//lA//mA//nA//oA//oB//pD//pE//qF//qG//qH//rI//rJ//sK//sM//sN//tO//tP//uQ//uR//vS//vT//vU//wW//wX//xY//xZ//xa//yb//yc//zd//ze//zg//0h//0i//1j//1k//1l//2m//2n//3p//3q//4r//4s//4t//5u//5v//6w//6y//6y//70//71//82//83//84//95//96//+7//+9///9/////////////////+///++//++//++//++//9+//9+//99//99//89//89//89//88//88//78//78//78//78//67//67//67//67//57//57//56//56//56//46//46//46//45//35//35//35//35//24//24//24//24//24//13//13//13//13//03//03//03//02//z2//z2//z2//z2//02//+LA/+LA/+MA/+NA/+OA/+QA/+RA/+SA/+TA/+VA/+WA/+XA/+ZA/QQQ/QQQ/QQQ//eA//fA//gA//hA//iA//kA//lA//mA//nA//oA//oB//pD//pE//qF//qG//qH//rI//rJ/QQQ//sM//sN//tO//tP//uQ//uR//vS//vT//vU//wW//wX//xY//xZ//xa//yb//yc//zd//ze//zg//0h//0i//1j//1k//1l//2m//2n//3p//3q//4r//4s//4t//5u//5v//6w//6y//6y//70//71//82//83//84//95//96//+7//+9///9/////////////////QQQ/QQQ/QQQ/++//++//9+//9+//99//99//89//89//89//88//88//78//78//78//78//67//67//67//67//57//57//56//56//56//46//46//46//45//35//35//35//35//24//24//24//24//24//13//13//13//13//03//03//03//02//z2//z2//z2//z2//02//+LA/+LA/+MA/+NA/+OA/+QA/+RA/+SA/+TA/+VA/+WA/+XA/+ZA/QQQ//bA//cA//eA//fA//gA//hA//iA//kA//lA//mA//nA//oA//oB//pD//pE//qF//qG//qH//rI//rJ/QQQ//sM//sN//tO//tP//uQ//uR//vS//vT//vU//wW//wX//xY//xZ//xa//yb//yc//zd//ze//zg//0h//0i//1j//1k//1l//2m//2n//3p//3q//4r//4s//4t//5u//5v//6w//6y//6y//70//71//82//83//84//95//96//+7//+9///9/////////////////QQQ/++//QQQ/++//++//9+//9+//99//99//89//89//89//88//88//78//78//78//78//67//67//67//67//57//57//56//56//56//46//46//46//45//35//35//35//35//24//24//24//24//24//13//13//13//13//03//03//03//02//z2//z2//z2//z2//02//+LA/+LA/+MA/+NA/+OA/+QA/+RA/+SA/+TA/+VA/+WA/+XA/+ZA/QQQ//bA//cA//eA//fA//gA//hA//iA//kA//lA//mA//nA//oA//oB//pD//pE//qF//qG//qH//rI//rJ/QQQ//sM//sN//tO//tP//uQ//uR//vS//vT//vU//wW//wX//xY//xZ//xa//yb//yc//zd//ze//zg//0h//0i//1j//1k//1l//2m//2n//3p//3q//4r//4s//4t//5u//5v//6w//6y//6y//70//71//82//83//84//95//96//+7//+9///9/////////////////QQQ/++//QQQ/++//++//9+//9+//99//99//89//89//89//88//88//78//78//78//78//67//67//67//67//57//57//56//56//56//46//46//46//45//35//35//35//35//24//24//24//24//24//13//13//13//13//03//03//03//02//z2//z2//z2//z2//02//+LA4+LA/+MA/+NA/+OA/+QA/+RA/+SA/+TA/+VA/+WA/+XA/+ZA/+aA/QQQ/QQQ//eA//fA//gA//hA//iA//kA//lA//mA//nA//oA//oB//pD//pE//qF//qG//qH//rI//rJ/QQQ//sM//sN//tO//tP//uQ//uR//vS//vT//vU//wW//wX//xY//xZ//xa//yb//yc//zd//ze//zg//0h//0i//1j//1k//1l//2m//2n//3p//3q//4r//4s//4t//5u//5v//6w//6y//6y//70//71//82//83//84//95//96//+7//+9///9/////////////////QQQ/QQQ/++//++//++//9+//9+//99//99//89//89//89//88//88//78//78//78//78//67//67//67//67//57//57//56//56//56//46//46//46//45//35//35//35//35//24//24//24//24//24//13//13//13//13//03//03//03//02//z2//z2//z2//z2//02//+LAs+LA/+MA/+NA/+OA/+QA/+RA/+SA/+TA/+VA/+WA/+XA/+ZA/+aA//bA//cA//eA//fA//gA//hA//iA//kA//lA//mA//nA//oA//oB//pD//pE//qF//qG//qH//rI//rJ//sK//sM//sN//tO//tP//uQ//uR//vS//vT//vU//wW//wX//xY//xZ//xa//yb//yc//zd//ze//zg//0h//0i//1j//1k//1l//2m//2n//3p//3q//4r//4s//4t//5u//5v//6w//6y//6y//70//71//82//83//84//95//96//+7//+9///9/////////////////+///++//++//++//++//9+//9+//99//99//89//89//89//88//88//78//78//78//78//67//67//67//67//57//57//56//56//56//46//46//46//45//35//35//35//35//24//24//24//24//24//13//13//13//13//03//03//03//02//z2//z2//z2//z2//02//+LAc+LA/+MA/+NA/+OA/+QA/+RA/+SA/+TA/+VA/+WA/+XA/+ZA/+aA//bA//cA//eA//fA//gA//hA//iA//kA//lA//mA//nA//oA//oB//pD//pE//qF//qG//qH//rI//rJ//sK//sM//sN//tO//tP//uQ//uR//vS//vT//vU//wW//wX//xY//xZ//xa//yb//yc//zd//ze//zg//0h//0i//1j//1k//1l//2m//2n//3p//3q//4r//4s//4t//5u//5v//6w//6y//6y//70//71//82//83//84//95//96//+7//+9///9/////////////////+///++//++//++//++//9+//9+//99//99//89//89//89//88//88//78//78//78//78//67//67//67//67//57//57//56//56//56//46//46//46//45//35//35//35//35//24//24//24//24//24//13//13//13//13//03//03//03//02//z2//z2//z2//z2//02//+LAK+LAz+MA/+NA/+OA/+QA/+RA/+SA/+TA/+VA/+WA/+XA/+ZA/+aA//bA//cA//eA//fA//gA//hA//iA//kA//lA//mA//nA//oA//oB//pD//pE//qF//qG//qH//rI//rJ//sK//sM//sN//tO//tP//uQ//uR//vS//vT//vU//wW//wX//xY//xZ//xa//yb//yc//zd//ze//zg//0h//0i//1j//1k//1l//2m//2n//3p//3q//4r//4s//4t//5u//5v//6w//6y//6y//70//71//82//83//84//95//96//+7//+9///9/////////////////+///++//++//++//++//9+//9+//99//99//89//89//89//88//88//78//78//78//78//67//67//67//67//57//57//56//56//56//46//46//46//45//35//35//35//35//24//24//24//24//24//13//13//13//13//03//03//03//02//z2//z2//z2//z2//02//+LAA+LAa+MA/+NA/+OA/+QA/+RA/+SA/+TA/+VA/+WA/+XA/+ZA/+aA//bA//cA//eA//fA//gA//hA//iA//kA//lA//mA//nA//oA//oB//pD//pE//qF//qG//qH//rI//rJ//sK//sM//sN//tO//tP//uQ//uR//vS//vT//vU//wW//wX//xY//xZ//xa//yb//yc//zd//ze//zg//0h//0i//1j//1k//1l//2m//2n//3p//3q//4r//4s//4t//5u//5v//6w//6y//6y//70//71//82//83//84//95//96//+7//+9///9/////////////////+///++//++//++//++//9+//9+//99//99//89//89//89//88//88//78//78//78//78//67//67//67//67//57//57//56//56//56//46//46//46//45//35//35//35//35//24//24//24//24//24//13//13//13//13//03//03//03//02//z2//z2//z2//z2//02//+LAA+LAA+MAf+NA/+OA/+QA/+RA/+SA/+TA/+VA/+WA/+XA/+ZA/+aA//bA//cA//eA//fA//gA//hA//iA//kA//lA//mA//nA//oA//oB//pD//pE//qF//qG//qH//rI//rJ//sK//sM//sN//tO//tP//uQ//uR//vS//vT//vU//wW//wX//xY//xZ//xa//yb//yc//zd//ze//zg//0h//0i//1j//1k//1l//2m//2n//3p//3q//4r//4s//4t//5u//5v//6w//6y//6y//70//71//82//83//84//95//96//+7//+9///9/////////////////+///++//++//++//++//9+//9+//99//99//89//89//89//88//88//78//78//78//78//67//67//67//67//57//57//56//56//56//46//46//46//45//35//35//35//35//24//24//24//24//24//13//13//13//13//03//03//03//02//z2//z2//z2//z2//02//+LAA+LAA+MAA+NAa+OAz+QA/+RA/+SA/+TA/+VA/+WA/+XA/+ZA/+aA//bA//cA//eA//fA//gA//hA//iA//kA//lA//mA//nA//oA//oB//pD//pE//qF//qG//qH//rI//rJ//sK//sM//sN//tO//tP//uQ//uR//vS//vT//vU//wW//wX//xY//xZ//xa//yb//yc//zd//ze//zg//0h//0i//1j//1k//1l//2m//2n//3p//3q//4r//4s//4t//5u//5v//6w//6y//6y//70//71//82//83//84//95//96//+7//+9///9/////////////////+///++//++//++//++//9+//9+//99//99//89//89//89//88//88//78//78//78//78//67//67//67//67//57//57//56//56//56//46//46//46//45//35//35//35//35//24//24//24//24//24//13//13//13//13//03//03//03//02//z2//z2//z2//z2//02//+LAA+LAA+MAA+NAA+OAK+QAc+RAs+SA4+TA/+VA/+WA/+XA/+ZA/+aA//bA//cA//eA//fA//gA//hA//iA//kA//lA//mA//nA//oA//oB//pD//pE//qF//qG//qH//rI//rJ//sK//sM//sN//tO//tP//uQ//uR//vS//vT//vU//wW//wX//xY//xZ//xa//yb//yc//zd//ze//zg//0h//0i//1j//1k//1l//2m//2n//3p//3q//4r//4s//4t//5u//5v//6w//6y//6y//70//71//82//83//84//95//96//+7//+9///9/////////////////+///++//++//++//++//9+//9+//99//99//89//89//89//88//88//78//78//78//78//67//67//67//67//57//57//56//56//56//46//46//46//45//35//35//35//35//24//24//24//24//24//13//13//13//13//03//03//03//02//z2//z2//z2//z2//02//")
                ,'bar_equalenergy'         : ("AAA/AAA/AAA/AAA/BBB/BBB/BBB/BBB/CCC/CCC/CDC/DDD/DDD/DDD/EEE/EEE/EFF/FFF/FFF/GGG/GGG/HGG/HHH/HHH/III/III/JJJ/JJJ/KJK/KKK/KKK/LLL/LLL/MMM/MMM/NNN/NNN/OOO/OOO/PPP/PPP/QQQ/QQQ/RRR/RRR/SSS/TSS/TTT/UUU/UUU/VVV/VVV/WWW/WWW/XXX/XXY/YYY/ZZZ/ZZZ/aaa/aaa/bbb/cbb/ccc/ddd/ddd/eee/eee/fff/ffg/ggg/hhh/hhh/iii/iii/jjj/kkk/kkk/lll/lll/mmm/mnm/nnn/ono/ooo/ppp/ppp/qqq/qqq/rrr/rrr/sss/sss/ttt/utu/uuu/vvv/vvv/www/www/xxx/xxx/yyy/yyy/zzz/zzz/000/000/111/111/122/222/222/333/333/444/444/545/555/555/666/666/667/777/777/788/888/888/999/999/999/9++/+++/+++/+++/////////////AAA/AAA/AAA/AAA/BBB/BBB/BBB/BBB/CCC/CCC/CCC/DDD/DDD/DDD/EEE/EEE/EEF/FFF/FFF/GGG/GGG/GGH/HHH/HHH/III/III/JJJ/JJJ/KJJ/KKK/KKK/LLL/LLL/MMM/MMM/NNN/NNN/OOO/OOO/PPP/PPP/QQQ/QQQ/RRR/RSR/SSS/TTT/TTT/UUU/UUU/VVV/VVV/WWW/WWW/XXX/YXX/YYY/ZZZ/ZZZ/aaa/aaa/bbb/cbb/ccc/ddd/ddd/eee/eee/fff/ffg/ggg/hhh/hhh/iii/iii/jjj/kkj/kkk/lll/lll/mmm/mmn/nnn/ono/ooo/ppp/ppp/qqq/qqq/rrr/rrr/sss/stt/ttt/tuu/uuu/vvv/vvv/www/www/xxx/xxx/yyy/yyy/zzz/zzz/000/000/111/111/111/222/222/333/333/444/444/554/555/555/666/666/766/777/777/777/888/888/999/999/999/9++/+++/+++/+++/////////////AAA/AAA/AAA/AAA/BBB/BBB/BBB/BCC/CCC/CCC/DCC/DDD/DDD/DDD/EEE/EEE/FEF/FFF/FFF/GGG/GGG/GGG/HHH/HHH/III/III/JJJ/JJJ/KJJ/KKK/KLK/LLL/LLL/MMM/MMM/NNN/NNN/OOO/OOO/PPP/PPP/QQQ/RQQ/RRR/SRR/SSS/STT/TTT/UTU/UUU/VVV/VVV/WWW/WWW/XXX/XXX/YYY/ZZZ/ZZZ/aaa/aaa/bbb/cbb/ccc/ddd/ddd/eee/eee/fff/ggg/ggg/hhh/hhh/iii/iii/jjj/jjk/kkk/lll/lll/mmm/mmm/nnn/ooo/ooo/ppp/ppp/qqq/qqq/rrr/rrr/sss/tst/ttt/utt/uuu/vvv/vvv/www/www/xxx/xxx/yyy/yyy/zzz/zzz/000/000/111/111/122/222/222/333/333/444/444/555/555/555/666/666/667/777/777/888/888/888/999/999/999/++9/+++/+++/+++/////////////AAA/AAA/AAA/AAA/BBB/BBB/BBB/BBB/CCC/CCC/CCC/DDD/DDD/DDD/EEE/EEE/FEE/FFF/FFF/GGG/GGG/HGG/HHH/HHH/III/III/JJJ/JJJ/JKJ/KKK/KKK/LLL/LLL/MMM/MMM/NNN/NNN/OOO/OOO/PPP/PPP/QQQ/QRQ/RRR/RRS/SSS/TST/TTT/UUU/UUU/VVV/VVV/WWW/WWW/XXX/XYY/YYY/ZZZ/ZZZ/aaa/aaa/bbb/bcc/ccc/ddd/ddd/eee/eee/fff/gfg/ggg/hhh/hhh/iii/iii/jjj/jjk/kkk/lll/lll/mmm/mmm/nnn/onn/ooo/ppp/ppp/qqq/qqq/rrr/rrr/sss/tst/ttt/uuu/uuu/vvv/vvv/www/www/xxx/xxx/yyy/yyy/zzz/zzz/000/000/111/111/211/222/222/333/333/444/444/455/555/555/666/666/776/777/777/887/888/888/899/999/999/999/+++/+++/+++/////////////AAA/AAA/AAA/AAA/BBB/BBB/BBB/CBC/CCC/CCC/CCC/DDD/DDD/DDD/EEE/EEE/EEF/FFF/FFF/GGG/GGG/HHG/HHH/HHH/III/III/JJJ/JJJ/KKJ/KKK/KKK/LLL/LLL/MMM/MMM/NNN/NNN/OOO/OOO/PPP/PPP/QQQ/QQR/RRR/RRR/SSS/STT/TTT/UUU/UUU/VVV/VVV/WWW/WWW/XXX/XXX/YYY/ZZZ/ZZZ/aaa/aaa/bbb/bcb/ccc/ddd/ddd/eee/eee/fff/gff/ggg/hhh/hhh/iii/iii/jjj/jkk/kkk/lll/lll/mmm/mmm/nnn/noo/ooo/ppp/ppp/qqq/qqq/rrr/rrr/sss/sss/ttt/uuu/uuu/vvv/vvv/www/www/xxx/xxx/yyy/yyy/zzz/zzz/000/000/111/111/211/222/322/333/333/444/444/554/555/555/666/666/766/777/777/878/888/888/999/999/999/+9+/+++/+++/+++/////////////AAA/AAA/AAA/AAA/BBB/BBB/BBB/BBB/CCC/CCC/CCC/DDD/DDD/DDD/EEE/EEE/EEF/FFF/FFF/GGG/GGG/GGH/HHH/HHH/III/III/JJJ/JJJ/KJJ/KKK/KKK/LLL/LLL/MMM/MMM/NNN/NNN/OOO/OOO/PPP/PPP/QQQ/QQQ/RRR/RSR/SSS/TTT/TTT/UUU/UUU/VVV/VVV/WWW/WWW/XXX/YXX/YYY/ZZZ/ZZZ/aaa/aaa/bbb/cbb/ccc/ddd/ddd/eee/eee/fff/ffg/ggg/hhh/hhh/iii/iii/jjj/kkj/kkk/lll/lll/mmm/mmn/nnn/ono/ooo/ppp/ppp/qqq/qqq/rrr/rrr/sss/stt/ttt/tuu/uuu/vvv/vvv/www/www/xxx/xxx/yyy/yyy/zzz/zzz/000/000/111/111/111/222/222/333/333/444/444/554/555/555/666/666/766/777/777/777/888/888/999/999/999/9++/+++/+++/+++/////////////AAA/AAA/AAA/AAA/BBB/BBB/BBB/BCC/CCC/CCC/DCC/DDD/DDD/DDD/EEE/EEE/FEF/FFF/FFF/GGG/GGG/GGG/HHH/HHH/III/III/JJJ/JJJ/KJJ/KKK/KLK/LLL/LLL/MMM/MMM/NNN/NNN/OOO/OOO/PPP/PPP/QQQ/RQQ/RRR/SRR/SSS/STT/TTT/UTU/UUU/VVV/VVV/WWW/WWW/XXX/XXX/YYY/ZZZ/ZZZ/aaa/aaa/bbb/cbb/ccc/ddd/ddd/eee/eee/fff/ggg/ggg/hhh/hhh/iii/iii/jjj/jjk/kkk/lll/lll/mmm/mmm/nnn/ooo/ooo/ppp/ppp/qqq/qqq/rrr/rrr/sss/tst/ttt/utt/uuu/vvv/vvv/www/www/xxx/xxx/yyy/yyy/zzz/zzz/000/000/111/111/122/222/222/333/333/444/444/555/555/555/666/666/667/777/777/888/888/888/999/999/999/++9/+++/+++/+++/////////////AAA/AAA/AAA/AAA/BBB/BBB/BBB/BBB/CCC/CCC/CCC/DDD/DDD/DDD/EEE/EEE/FEE/FFF/FFF/GGG/GGG/HGG/HHH/HHH/III/III/JJJ/JJJ/JKJ/KKK/KKK/LLL/LLL/MMM/MMM/NNN/NNN/OOO/OOO/PPP/PPP/QQQ/QRQ/RRR/RRS/SSS/TST/TTT/UUU/UUU/VVV/VVV/WWW/WWW/XXX/XYY/YYY/ZZZ/ZZZ/aaa/aaa/bbb/bcc/ccc/ddd/ddd/eee/eee/fff/gfg/ggg/hhh/hhh/iii/iii/jjj/jjk/kkk/lll/lll/mmm/mmm/nnn/onn/ooo/ppp/ppp/qqq/qqq/rrr/rrr/sss/tst/ttt/uuu/uuu/vvv/vvv/www/www/xxx/xxx/yyy/yyy/zzz/zzz/000/000/111/111/211/222/222/333/333/444/444/455/555/555/666/666/776/777/777/887/888/888/899/999/999/999/+++/+++/+++/////////////AAA/AAA/AAA/AAA/BBB/BBB/BBB/CBC/CCC/CCC/CCC/DDD/DDD/DDD/EEE/EEE/EEF/FFF/FFF/GGG/GGG/HHG/HHH/HHH/III/III/JJJ/JJJ/KKJ/KKK/KKK/LLL/LLL/MMM/MMM/NNN/NNN/OOO/OOO/PPP/PPP/QQQ/QQR/RRR/RRR/SSS/STT/TTT/UUU/UUU/VVV/VVV/WWW/WWW/XXX/XXX/YYY/ZZZ/ZZZ/aaa/aaa/bbb/bcb/ccc/ddd/ddd/eee/eee/fff/gff/ggg/hhh/hhh/iii/iii/jjj/jkk/kkk/lll/lll/mmm/mmm/nnn/noo/ooo/ppp/ppp/qqq/qqq/rrr/rrr/sss/sss/ttt/uuu/uuu/vvv/vvv/www/www/xxx/xxx/yyy/yyy/zzz/zzz/000/000/111/111/211/222/322/333/333/444/444/554/555/555/666/666/766/777/777/878/888/888/999/999/999/+9+/+++/+++/+++/////////////GBA+AAA/AAA/AAA/BBB/BBB/BBB/BBB/CCC/CCC/CCC/DDD/DDD/DDD/EEE/EEE/EEF/FFF/FFF/GGG/GGG/GGH/HHH/HHH/III/III/JJJ/JJJ/KJJ/KKK/KKK/LLL/LLL/MMM/MMM/NNN/NNN/OOO/OOO/PPP/PPP/QQQ/QQQ/RRR/RSR/SSS/TTT/TTT/UUU/UUU/VVV/VVV/WWW/WWW/XXX/YXX/YYY/ZZZ/ZZZ/aaa/aaa/bbb/cbb/ccc/ddd/ddd/eee/eee/fff/ffg/ggg/hhh/hhh/iii/iii/jjj/kkj/kkk/lll/lll/mmm/mmn/nnn/ono/ooo/ppp/ppp/qqq/qqq/rrr/rrr/sss/stt/ttt/tuu/uuu/vvv/vvv/www/www/xxx/xxx/yyy/yyy/zzz/zzz/000/000/111/111/111/222/222/333/333/444/444/554/555/555/666/666/766/777/777/777/888/888/999/999/999/9++/+++/+++/+++/////////++/+OCA5AAA/AAA/AAA/BBB/BBB/BBB/BCC/CCC/CCC/DCC/DDD/DDD/DDD/EEE/EEE/FEF/FFF/FFF/GGG/GGG/GGG/HHH/HHH/III/III/JJJ/JJJ/KJJ/KKK/KLK/LLL/LLL/MMM/MMM/NNN/NNN/OOO/OOO/PPP/PPP/QQQ/RQQ/RRR/SRR/SSS/STT/TTT/UTU/UUU/VVV/VVV/WWW/WWW/XXX/XXX/YYY/ZZZ/ZZZ/aaa/aaa/bbb/cbb/ccc/ddd/ddd/eee/eee/fff/ggg/ggg/hhh/hhh/iii/iii/jjj/jjk/kkk/lll/lll/mmm/mmm/nnn/ooo/ooo/ppp/ppp/qqq/qqq/rrr/rrr/sss/tst/ttt/utt/uuu/vvv/vvv/www/www/xxx/xxx/yyy/yyy/zzz/zzz/000/000/111/111/122/222/222/333/333/444/444/555/555/555/666/666/667/777/777/888/888/888/999/999/999/++9/+++/+++/+++/////////89/5WEAsAAA/AAA/AAA/BBB/BBB/BBB/BBB/CCC/CCC/CCC/DDD/DDD/DDD/EEE/EEE/FEE/FFF/FFF/GGG/GGG/HGG/HHH/HHH/III/III/JJJ/JJJ/JKJ/KKK/KKK/LLL/LLL/MMM/MMM/NNN/NNN/OOO/OOO/PPP/PPP/QQQ/QRQ/RRR/RRS/SSS/TST/TTT/UUU/UUU/VVV/VVV/WWW/WWW/XXX/XYY/YYY/ZZZ/ZZZ/aaa/aaa/bbb/bcc/ccc/ddd/ddd/eee/eee/fff/gfg/ggg/hhh/hhh/iii/iii/jjj/jjk/kkk/lll/lll/mmm/mmm/nnn/onn/ooo/ppp/ppp/qqq/qqq/rrr/rrr/sss/tst/ttt/uuu/uuu/vvv/vvv/www/www/xxx/xxx/yyy/yyy/zzz/zzz/000/000/111/111/211/222/222/333/333/444/444/455/555/555/666/666/776/777/777/887/888/888/899/999/999/999/+++/+++/+++/////////78/scFASKCA9AAA/AAA/BBB/BBB/BBB/CBC/CCC/CCC/CCC/DDD/DDD/DDD/EEE/EEE/EEF/FFF/FFF/GGG/GGG/HHG/HHH/HHH/III/III/JJJ/JJJ/KKJ/KKK/KKK/LLL/LLL/MMM/MMM/NNN/NNN/OOO/OOO/PPP/PPP/QQQ/QQR/RRR/RRR/SSS/STT/TTT/UUU/UUU/VVV/VVV/WWW/WWW/XXX/XXX/YYY/ZZZ/ZZZ/aaa/aaa/bbb/bcb/ccc/ddd/ddd/eee/eee/fff/gff/ggg/hhh/hhh/iii/iii/jjj/jkk/kkk/lll/lll/mmm/mmm/nnn/noo/ooo/ppp/ppp/qqq/qqq/rrr/rrr/sss/sss/ttt/uuu/uuu/vvv/vvv/www/www/xxx/xxx/yyy/yyy/zzz/zzz/000/000/111/111/211/222/322/333/333/444/444/554/555/555/666/666/766/777/777/878/888/888/999/999/999/+9+/+++/+++/+++/////99/967/S///AXEApBAA/AAA/BBB/BBB/BBB/BBB/CCC/CCC/CCC/DDD/DDD/DDD/EEE/EEE/EEF/FFF/FFF/GGG/GGG/GGH/HHH/HHH/III/III/JJJ/JJJ/KJJ/KKK/KKK/LLL/LLL/MMM/MMM/NNN/NNN/OOO/OOO/PPP/PPP/QQQ/QQQ/RRR/RSR/SSS/TTT/TTT/UUU/UUU/VVV/VVV/WWW/WWW/XXX/YXX/YYY/ZZZ/ZZZ/aaa/aaa/bbb/cbb/ccc/ddd/ddd/eee/eee/fff/ffg/ggg/hhh/hhh/iii/iii/jjj/kkj/kkk/lll/lll/mmm/mmn/nnn/ono/ooo/ppp/ppp/qqq/qqq/rrr/rrr/sss/stt/ttt/tuu/uuu/vvv/vvv/www/www/xxx/xxx/yyy/yyy/zzz/zzz/000/000/111/111/111/222/222/333/333/444/444/554/555/555/666/666/766/777/777/777/888/888/999/999/999/9++/+++/+++/+++/////67/p///A///A///AVEAvBAA/BBB/BBB/BBB/BCC/CCC/CCC/DCC/DDD/DDD/DDD/EEE/EEE/FEF/FFF/FFF/GGG/GGG/GGG/HHH/HHH/III/III/JJJ/JJJ/KJJ/KKK/KLK/LLL/LLL/MMM/MMM/NNN/NNN/OOO/OOO/PPP/PPP/QQQ/RQQ/RRR/SRR/SSS/STT/TTT/UTU/UUU/VVV/VVV/WWW/WWW/XXX/XXX/YYY/ZZZ/ZZZ/aaa/aaa/bbb/cbb/ccc/ddd/ddd/eee/eee/fff/ggg/ggg/hhh/hhh/iii/iii/jjj/jjk/kkk/lll/lll/mmm/mmm/nnn/ooo/ooo/ppp/ppp/qqq/qqq/rrr/rrr/sss/tst/ttt/utt/uuu/vvv/vvv/www/www/xxx/xxx/yyy/yyy/zzz/zzz/000/000/111/111/122/222/222/333/333/444/444/555/555/555/666/666/667/777/777/888/888/888/999/999/999/++9/+++/+++/+++/78/v///A///A///A///A///AXFApKDA9BBB/BBB/BBB/CCC/CCC/CCC/DDD/DDD/DDD/EEE/EEE/FEE/FFF/FFF/GGG/GGG/HGG/HHH/HHH/III/III/JJJ/JJJ/JKJ/KKK/KKK/LLL/LLL/MMM/MMM/NNN/NNN/OOO/OOO/PPP/PPP/QQQ/QRQ/RRR/RRS/SSS/TST/TTT/UUU/UUU/VVV/VVV/WWW/WWW/XXX/XYY/YYY/ZZZ/ZZZ/aaa/aaa/bbb/bcc/ccc/ddd/ddd/eee/eee/fff/gfg/ggg/hhh/hhh/iii/iii/jjj/jjk/kkk/lll/lll/mmm/mmm/nnn/onn/ooo/ppp/ppp/qqq/qqq/rrr/rrr/sss/tst/ttt/uuu/uuu/vvv/vvv/www/www/xxx/xxx/yyy/yyy/zzz/zzz/000/000/111/111/211/222/222/333/333/444/444/455/555/555/666/666/776/777/777/887/888/888/899/999/999/999/+++/89+967/p///A///A///A///A///A///A///AdHASXGAsQFB5IDB+CCC/CCC/CCC/DDD/DDD/DDD/EEE/EEE/EEF/FFF/FFF/GGG/GGG/HHG/HHH/HHH/III/III/JJJ/JJJ/KKJ/KKK/KKK/LLL/LLL/MMM/MMM/NNN/NNN/OOO/OOO/PPP/PPP/QQQ/QQR/RRR/RRR/SSS/STT/TTT/UUU/UUU/VVV/VVV/WWW/WWW/XXX/XXX/YYY/ZZZ/ZZZ/aaa/aaa/bbb/bcb/ccc/ddd/ddd/eee/eee/fff/gff/ggg/hhh/hhh/iii/iii/jjj/jkk/kkk/lll/lll/mmm/mmm/nnn/noo/ooo/ppp/ppp/qqq/qqq/rrr/rrr/sss/sss/ttt/uuu/uuu/vvv/vvv/www/www/xxx/xxx/yyy/yyy/zzz/zzz/000/000/111/111/211/222/322/333/333/444/444/554/555/555/666/666/766/777/777/878/888/888/999/999/88++78+567+s56/S///A///A///A///A") 
            }
        
        @staticmethod
        def decodeIconStr(s):
            buf = Blender.BGL.Buffer(Blender.BGL.GL_BYTE, [16,16,4])
            offset = 0
            for y in range(16):
                for x in range(16):
                    for c in range(4):
                        buf[y][x][c] = int(Lux.Util.base64value(s[offset])*4.048)
                        offset += 1
            return buf
        
        @staticmethod
        def decodeLogoStr(s):
            buf = Blender.BGL.Buffer(Blender.BGL.GL_BYTE, [18,118,4])
            offset = 0
            for y in range(18):
                for x in range(118):
                    for c in range(4):
                        buf[y][x][c] = int(Lux.Util.base64value(s[offset])*4.048)
                        offset += 1
            return buf
        
        @staticmethod
        def decodeBarStr(s):
            buf = Blender.BGL.Buffer(Blender.BGL.GL_BYTE, [17,138,4])
            offset = 0
            for y in range(17):
                for x in range(138):
                    for c in range(4):
                        buf[y][x][c] = int(Lux.Util.base64value(s[offset])*4.048)
                        offset += 1
            return buf
        
        @staticmethod
        def drawIcon(icon, x, y):
            Blender.BGL.glEnable(Blender.BGL.GL_BLEND)
            Blender.BGL.glBlendFunc(Blender.BGL.GL_SRC_ALPHA, Blender.BGL.GL_ONE_MINUS_SRC_ALPHA) 
            Blender.BGL.glRasterPos2f(int(x)+0.5, int(y)+0.5)
            Blender.BGL.glDrawPixels(16, 16, Blender.BGL.GL_RGBA, Blender.BGL.GL_UNSIGNED_BYTE, icon)
            Blender.BGL.glDisable(Blender.BGL.GL_BLEND)
        
        @staticmethod
        def drawLogo(icon, x, y):
            Blender.BGL.glEnable(Blender.BGL.GL_BLEND)
            Blender.BGL.glBlendFunc(Blender.BGL.GL_SRC_ALPHA, Blender.BGL.GL_ONE_MINUS_SRC_ALPHA) 
            Blender.BGL.glRasterPos2f(int(x)+0.5, int(y)+0.5)
            Blender.BGL.glDrawPixels(118, 18, Blender.BGL.GL_RGBA, Blender.BGL.GL_UNSIGNED_BYTE, icon)
            Blender.BGL.glDisable(Blender.BGL.GL_BLEND)
        
        @staticmethod
        def drawBar(icon, x, y):
            Blender.BGL.glEnable(Blender.BGL.GL_BLEND)
            Blender.BGL.glBlendFunc(Blender.BGL.GL_SRC_ALPHA, Blender.BGL.GL_ONE_MINUS_SRC_ALPHA) 
            Blender.BGL.glRasterPos2f(int(x)+0.5, int(y)+0.5)
            Blender.BGL.glDrawPixels(138, 17, Blender.BGL.GL_RGBA, Blender.BGL.GL_UNSIGNED_BYTE, icon)
            Blender.BGL.glDisable(Blender.BGL.GL_BLEND)
            
    class Image:
        '''
        helper class to handle images and icons for the GUI
        '''
        
        def __init__(self, width=0, height=0):
            self.resize(width, height)
        
        def resize(self, width, height):
            self.width = width
            self.height = height
            self.buf = Blender.BGL.Buffer(Blender.BGL.GL_BYTE, [width,height,4]) # GL buffer
                
        def draw(self, x, y):
            Blender.BGL.glEnable(Blender.BGL.GL_BLEND)
            Blender.BGL.glBlendFunc(Blender.BGL.GL_SRC_ALPHA, Blender.BGL.GL_ONE_MINUS_SRC_ALPHA) 
            Blender.BGL.glRasterPos2f(int(x)+0.5, int(y)+0.5)
            Blender.BGL.glDrawPixels(self.width, self.height, Blender.BGL.GL_RGBA, Blender.BGL.GL_UNSIGNED_BYTE, self.buf)
            Blender.BGL.glDisable(Blender.BGL.GL_BLEND)
            
        def decodeStr(self, width, height, s):
            self.resize(width, height)
            offset = 0
            for y in range(self.height):
                for x in range(self.width):
                    for c in range(4):
                        self.buf[y][x][c] = int(Lux.Util.base64value(s[offset])*4.048)
                        offset += 1
    
        def decodeLuxConsole(self, width, height, data):
            self.resize(width, height)
            offset = 0
            for y in range(self.height-1,-1,-1):
                for x in range(self.width):
                    for c in range(3):
                        self.buf[y][x][c] = ord(data[offset])
                        offset += 1
                    self.buf[y][x][3] = 255
    
    class Experimental:
        '''Note - radiance - this is a work in progress'''
        
        @staticmethod
        def FlashBlock(camObj):
            str = ""
            str += "CoordSysTransform \"camera\"\n"
            str += "Texture \"camflashtex\" \"color\" \"blackbody\" \"float temperature\" [5500.0]"
            str += "AreaLightSource \"area\" \"texture L\" [\"camflashtex\"] \"float power\" [100.000000] \"float efficacy\" [17.000000] \"float gain\" [1.000000]\n"
            up = 10.0
            str += "Shape \"trianglemesh\" \"integer indices\" [ 0 1 2 0 2 3 ] \"point P\" [ 0.014 0.012 0.0   0.006 0.012 0.0   0.006 0.008 0.0   0.014 0.008 0.0 ]\n"
            return str
        
    class Property:
        '''
        class to access properties (for lux settings)
        '''
        
        def __init__(self, obj, name, default):
            self.obj = obj
            self.name = name
    #        if len(name)>31: print "Warning: property-name \"%s\" has more than 31 chars."%(name)
            self.hashmode = len(name)>31   # activate hash mode for keynames longer 31 chars (limited by blenders ID-prop)
            self.hashname = "__hash:%x"%(name.__hash__())
            self.default = default
            
        def parseassignment(self, s, name):
            l = s.split(" = ")
            if l[0] != name: print "Warning: property-name \"%s\" has hash-collide with \"%s\"."%(name, l[0])
            return l[1]
        
        def createassignment(self, name, value):
            return "%s = %s"%(name, value)
        
        def get(self):
            global usedproperties, usedpropertiesfilterobj, luxdefaults
            if self.obj:
                try:
                    value = self.obj.properties['luxblend'][self.name]
                    if not(usedpropertiesfilterobj) or (usedpropertiesfilterobj == self.obj):
                        usedproperties[self.name] = value
                    return value
                except KeyError:
                    try:
                        value = self.parseassignment(self.obj.properties['luxblend'][self.hashname], self.name)
                        if not(usedpropertiesfilterobj) or (usedpropertiesfilterobj == self.obj):
                            usedproperties[self.name] = value
                        return value
                    except KeyError:
                        if self.obj.__class__.__name__ == "Scene": # luxdefaults only for global setting
                            try:
                                value = luxdefaults[self.name]
                                if not(usedpropertiesfilterobj) or (usedpropertiesfilterobj == self.obj):
                                    usedproperties[self.name] = value
                                return value
                            except KeyError:
                                if not(usedpropertiesfilterobj) or (usedpropertiesfilterobj == self.obj):
                                    usedproperties[self.name] = self.default
                                return self.default
                        if not(usedpropertiesfilterobj) or (usedpropertiesfilterobj == self.obj):
                            usedproperties[self.name] = self.default
                        return self.default
            return None
        
        def getobj(self):
            if self.obj:
                return self.obj
            else:
                return None
            
        def getname(self):
            if self.name:
                return self.name
            else:
                return None
            
        def set(self, value):
            global newluxdefaults
            if self.obj:
                if self.hashmode: n, v = self.hashname, self.createassignment(self.name, value)
                else: n, v = self.name, value
                if value is not None:
                    try: self.obj.properties['luxblend'][n] = v
                    except (KeyError, TypeError):
                        self.obj.properties['luxblend'] = {}
                        self.obj.properties['luxblend'][n] = v
                else:
                    try: del self.obj.properties['luxblend'][n]
                    except:    pass
                if self.obj.__class__.__name__ == "Scene": # luxdefaults only for global setting
                    # value has changed, so this are user settings, remove preset reference
                    if not(self.name in defaultsExclude):
                        newluxdefaults[self.name] = value
                        try: self.obj.properties['luxblend']['preset']=""
                        except: pass
                        
        def delete(self):
            if self.obj:
                try: del self.obj.properties['luxblend'][self.name]
                except:    pass
                try: del self.obj.properties['luxblend'][self.hashname]
                except:    pass
                
        def getFloat(self):
            v = self.get()
            if type(v) == types.FloatType: return float(v)
            try:
                if type(v) == types.StringType: return float(v.split(" ")[0])
            except: pass
            v = self.default
            if type(v) == types.FloatType: return float(v)
            try:
                if type(v) == types.StringType: return float(v.split(" ")[0])
            except: pass
            return 0.0
        
        def getInt(self):
            try: return int(self.get())
            except: return int(self.default)
            
        def getRGB(self):
            return self.getVector()
        
        def getVector(self):
            v = self.get()
            if type(v) in [types.FloatType, types.IntType]: return (float(v), float(v), float(v))
            l = None
            try:
                if type(v) == types.StringType: l = self.get().split(" ")
            except: pass
            if (l==None) or (len(l) != 3): l = self.default.split(" ")
            return (float(l[0]), float(l[1]), float(l[2]))
        
        def getVectorStr(self):
            return "%f %f %f"%self.getVector()
        
        def isFloat(self):
            return type(self.get()) == types.FloatType
        
        def getRGC(self):
            col = self.getRGB()
            return "%f %f %f"%(rg(col[0]), rg(col[1]),rg(col[2]))
        
        def setRGB(self, value):
            self.set("%f %f %f"%(value[0], value[1], value[2]))
            
        def setVector(self, value):
            self.set("%f %f %f"%(value[0], value[1], value[2]))
            
    class Attribute:
        '''
        class to access blender attributes (for lux settings)
        '''
        
        def __init__(self, obj, name):
            self.obj = obj
            self.name = name
            
        def get(self):
            if self.obj:
                return getattr(self.obj, self.name)
            else:
                return None
            
        def getFloat(self):
            return float(self.get())
        
        def getInt(self):
            return int(self.get())
        
        def getobj(self):
            if self.obj:
                return self.obj
            else:
                return None
        
        def getname(self):
            if self.name:
                return self.name
            else:
                return None
            
        def set(self, value):
            if self.obj:
                setattr(self.obj, self.name, value)
                Window.QRedrawAll()
                
    class GUI:
        '''
        class for dynamic gui
        '''
        
        def __init__(self, y=200):
            self.x = 110 # left start position after captions
            self.xmax = 110+2*(140+4)
            self.y = y
            self.w = 140 # default element width in pixels
            self.h = 18  # default element height in pixels
            self.hmax = 0
            self.xgap = 4
            self.ygap = 4
            self.resethmax = False
            
        def getRect(self, wu, hu):
            w = int(self.w * wu + self.xgap * (wu-1))
            h = int(self.h * hu + self.ygap * (hu-1))
            if self.x + w > self.xmax: self.newline()
            if self.resethmax: self.hmax = 0; self.resethmax = False
            rect = [int(self.x), int(self.y-h), int(w), int(h)]
            self.x += int(w + self.xgap)
            if h+self.ygap > self.hmax: self.hmax = int(h+self.ygap)
            return rect
        
        def newline(self, title="", distance=0, level=0, icon=None, color=None):
            self.x = 110
            if not(self.resethmax): self.y -= int(self.hmax + distance)
            if color!=None:    Blender.BGL.glColor3f(color[0],color[1],color[2]); Blender.BGL.glRectf(0,self.y-self.hmax,self.xmax,self.y+distance); Blender.BGL.glColor3f(0.9, 0.9, 0.9)
            if icon!=None: drawIcon(icon, 2+level*10, self.y-16)
            self.resethmax = True
            if title!="":
                self.getRect(0, 1)
                Blender.BGL.glColor3f(0.9,0.9,0.9); Blender.BGL.glRasterPos2i(20+level*10,self.y-self.h+5); Blender.Draw.Text(title)
                
        # scrollbar
        class scrollbar:
            def __init__(self):
                self.position = 0 # current position at top (inside 0..height-viewHeight)
                self.height = 0 # total height of the content
                self.viewHeight = 0 # height of window
                self.x = 0 # horizontal position of the scrollbar
                self.scrolling = self.over = False # start without scrolling ;)
            def calcRects(self):
                # Blender doesn't give us direct access to the window size yet, but it does set the
                # GL scissor box for it, so we can get the size from that. (thx to Daniel Dunbar)
                size = Blender.BGL.Buffer(Blender.BGL.GL_FLOAT, 4)
                Blender.BGL.glGetFloatv(Blender.BGL.GL_SCISSOR_BOX, size)
                size = size.list # [winx, winy, width, height]
                self.winrect = size[:]
                self.viewHeight = size[3]
                size[0], size[1] = size[2]-20, 0 # [scrollx1, scrolly1, scrollx2, scrolly2]
                self.rect = size[:]
                if self.position < 0: self.position = 0
                if self.height < self.viewHeight: self.height = self.viewHeight
                if self.position > self.height-self.viewHeight: self.position = self.height-self.viewHeight
                self.factor = (size[3]-size[1]-4)/self.height
                self.sliderRect = [size[0]+2, size[3]-2-(self.position+self.viewHeight)*self.factor, size[2]-2, size[3]-2-self.position*self.factor]
            def draw(self):
                self.calcRects()
                Blender.BGL.glColor3f(0.5,0.5,0.5); Blender.BGL.glRectf(self.rect[0],self.rect[1],self.rect[2],self.rect[3])
                if self.over or self.scrolling: Blender.BGL.glColor3f(1.0,1.0,0.7)
                else: Blender.BGL.glColor3f(0.7,0.7,0.7)
                Blender.BGL.glRectf(self.sliderRect[0],self.sliderRect[1],self.sliderRect[2],self.sliderRect[3])
            def getTop(self):
                return self.viewHeight+self.position
            def scroll(self, delta):
                self.position = self.position + delta
                self.calcRects()
                Blender.Draw.Redraw()
            def Mouse(self):
                self.calcRects()
                coord, buttons = Window.GetMouseCoords(), Window.GetMouseButtons()
                over = (coord[0]>=self.winrect[0]+self.rect[0]) and (coord[0]<=self.winrect[0]+self.rect[2]) and \
                       (coord[1]>=self.winrect[1]+self.rect[1]) and (coord[1]<=self.winrect[1]+self.rect[3])
                if Window.MButs.L and buttons > 0:
                    if self.scrolling:
                        if self.factor > 0: self.scroll((self.lastcoord[1]-coord[1])/self.factor)
                        Blender.Draw.Redraw()
                    elif self.over:
                        self.scrolling = True
                    self.lastcoord = coord
                elif self.scrolling:
                    self.scrolling = False
                    Blender.Draw.Redraw()
                if self.over != over: Blender.Draw.Redraw()
                self.over = over
                
                # gui main draw
        def luxDraw():
            global icon_luxblend
        
            Blender.BGL.glClear(Blender.BGL.GL_COLOR_BUFFER_BIT)
        
            y = int(scrollbar.getTop()) # 420
            Blender.BGL.glColor3f(0.1,0.1,0.1); Blender.BGL.glRectf(0,0,440,y)
            Blender.BGL.glColor3f(1.0,0.5,0.0); Blender.BGL.glRasterPos2i(130,y-21); Blender.Draw.Text("CVS")
            Blender.BGL.glColor3f(0.9,0.9,0.9);
        
            drawLogo(icon_luxblend, 6, y-25);
        
            Lux.scene = Blender.Scene.GetCurrent()
            if Lux.scene:
                luxpage = Lux.Property(Lux.scene, "page", 0)
                Lux.i_gui = Lux.Gui(y-70)
        
                # render presets
                Blender.BGL.glRasterPos2i(10,y-45); Blender.Draw.Text("Render presets:")
                luxpreset = Lux.Property(Lux.scene, "preset", "1C - Final - medium MLT/Path Tracing (indoor) (recommended)")
                presets = getScenePresets()
                presetskeys = presets.keys()
                presetskeys.sort()
                presetskeys.insert(0, "")
                presetsstr = "presets: %t"
                for i, v in enumerate(presetskeys): presetsstr = "%s %%x%d|%s"%(v, i, presetsstr)
                try: i = presetskeys.index(luxpreset.get())
                except ValueError: i = 0
                Blender.Draw.Menu(presetsstr, Lux.Events.LuxGui, 110, y-50, 220, 18, i, "", lambda e,v: luxpreset.set(presetskeys[v]))
                Blender.Draw.Button("save", Lux.Events.SavePreset, 330, y-50, 40, 18, "create a render-settings preset")
                Blender.Draw.Button("del", Lux.Events.DeletePreset, 370, y-50, 40, 18, "delete a render-settings preset")
        
                # if preset is selected load values
                if luxpreset.get() != "":
                    try:
                        d = presets[luxpreset.get()]
                        for k,v in d.items(): Lux.scene.properties['luxblend'][k] = v
                    except: pass
        
                Blender.Draw.Button("Material", Lux.Events.LuxGui, 10, y-70, 80, 16, "", lambda e,v:luxpage.set(0))
                Blender.Draw.Button("Cam/Env", Lux.Events.LuxGui, 90, y-70, 80, 16, "", lambda e,v:luxpage.set(1))
                Blender.Draw.Button("Render", Lux.Events.LuxGui, 170, y-70, 80, 16, "", lambda e,v:luxpage.set(2))
                Blender.Draw.Button("Output", Lux.Events.LuxGui, 250, y-70, 80, 16, "", lambda e,v:luxpage.set(3))
                Blender.Draw.Button("System", Lux.Events.LuxGui, 330, y-70, 80, 16, "", lambda e,v:luxpage.set(4))
                if luxpage.get() == 0:
                    Blender.BGL.glColor3f(1.0,0.5,0.0);Blender.BGL.glRectf(10,y-74,90,y-70);Blender.BGL.glColor3f(0.9,0.9,0.9)
                    obj = Lux.scene.objects.active
                    if obj:
                        if (obj.getType() == "Lamp"):
                            ltype = obj.getData(mesh=1).getType() # data
                            if (ltype == Lamp.Types["Area"]): luxLight("Area LIGHT", "", obj, Lux.i_gui, 0)
                            elif (ltype == Lamp.Types["Spot"]): luxSpot("Spot LIGHT", "", obj, Lux.i_gui, 0)
                            elif (ltype == Lamp.Types["Lamp"]): luxLamp("Point LIGHT", "", obj, Lux.i_gui, 0)
                        else:
                            matfilter = Lux.Property(Lux.scene, "matlistfilter", "false")
                            mats = getMaterials(obj, True)
                            if (activemat == None) and (len(mats) > 0):
                                setactivemat(mats[0])
                            if matfilter.get() == "false":
                                mats = Material.Get()
                            matindex = 0
                            for i, v in enumerate(mats):
                                if v==activemat: matindex = i
                            matnames = [m.getName() for m in mats]
                            menustr = "Material: %t"
                            for i, v in enumerate(matnames): menustr = "%s %%x%d|%s"%(v, i, menustr)
                            Lux.i_gui.newline("MATERIAL:", 8) 
                            r = Lux.i_gui.getRect(1.1, 1)
                            Blender.Draw.Button("C", Lux.Events.ConvertMaterial, r[0]-Lux.i_gui.h, Lux.i_gui.y-Lux.i_gui.h, Lux.i_gui.h, Lux.i_gui.h, "convert blender material to lux material")
                            Blender.Draw.Menu(menustr, Lux.Events.LuxGui, r[0], r[1], r[2], r[3], matindex, "", lambda e,v: setactivemat(mats[v]))
                            Lux.TypedControls.Bool("", matfilter, "filter", "only show active object materials", 0.5)
        
                            Blender.Draw.Button("L", Lux.Events.LoadMaterial, Lux.i_gui.x, Lux.i_gui.y-Lux.i_gui.h, Lux.i_gui.h, Lux.i_gui.h, "load a material preset")
                            Blender.Draw.Button("S", Lux.Events.SaveMaterial, Lux.i_gui.x+Lux.i_gui.h, Lux.i_gui.y-Lux.i_gui.h, Lux.i_gui.h, Lux.i_gui.h, "save a material preset")
                            Blender.Draw.Button("D", Lux.Events.DeleteMaterial, Lux.i_gui.x+Lux.i_gui.h*2, Lux.i_gui.y-Lux.i_gui.h, Lux.i_gui.h, Lux.i_gui.h, "delete a material preset")
                            if len(mats) > 0:
                                setactivemat(mats[matindex])
                                Lux.SceneElements.Material(activemat)
                if luxpage.get() == 1:
                    Blender.BGL.glColor3f(1.0,0.5,0.0);Blender.BGL.glRectf(90,y-74,170,y-70);Blender.BGL.glColor3f(0.9,0.9,0.9)
                    cam = Lux.scene.getCurrentCamera()
                    if cam:
                        r = Lux.i_gui.getRect(1.1, 1)
                        Lux.SceneElements.Camera(cam.data, Lux.scene.getRenderingContext())
                    Lux.i_gui.newline("", 10)
                    Lux.SceneElements.Environment()
                if luxpage.get() == 2:
                    Blender.BGL.glColor3f(1.0,0.5,0.0);Blender.BGL.glRectf(170,y-74,250,y-70);Blender.BGL.glColor3f(0.9,0.9,0.9)
                    r = Lux.i_gui.getRect(1.1, 1)
                    Lux.SceneElements.Sampler()
                    Lux.i_gui.newline("", 10)
                    Lux.SceneElements.SurfaceIntegrator()
                    Lux.i_gui.newline("", 10)
                    Lux.SceneElements.VolumeIntegrator()
                    Lux.i_gui.newline("", 10)
                    Lux.SceneElements.PixelFilter()
                if luxpage.get() == 3:
                    Blender.BGL.glColor3f(1.0,0.5,0.0);Blender.BGL.glRectf(250,y-74,330,y-70);Blender.BGL.glColor3f(0.9,0.9,0.9)
                    r = Lux.i_gui.getRect(1.1, 1)
                    Lux.SceneElements.Film()
                if luxpage.get() == 4:
                    Blender.BGL.glColor3f(1.0,0.5,0.0);Blender.BGL.glRectf(330,y-74,410,y-70);Blender.BGL.glColor3f(0.9,0.9,0.9)
                    Lux.SceneElements.System()
                    Lux.i_gui.newline("", 10)
                    Lux.SceneElements.Accelerator()
                    Lux.i_gui.newline("MATERIALS:", 10)
                    r = Lux.i_gui.getRect(2,1)
                    Blender.Draw.Button("convert all blender materials", 0, r[0], r[1], r[2], r[3], "convert all blender-materials to lux-materials", lambda e,v:convertAllMaterials())
                    Lux.i_gui.newline("SETTINGS:", 10)
                    r = Lux.i_gui.getRect(2,1)
                    Blender.Draw.Button("save defaults", 0, r[0], r[1], r[2], r[3], "save current settings as defaults", lambda e,v:saveluxdefaults())
                y = Lux.i_gui.y - 80
                if y > 0: y = 0 # bottom align of render button
                run = Lux.Property(Lux.scene, "run", "true")
                dlt = Lux.Property(Lux.scene, "default", "true")
                clay = Lux.Property(Lux.scene, "clay", "false")
                lxs = Lux.Property(Lux.scene, "lxs", "true")
                lxo = Lux.Property(Lux.scene, "lxo", "true")
                lxm = Lux.Property(Lux.scene, "lxm", "true")
                lxv = Lux.Property(Lux.scene, "lxv", "true")
                net = Lux.Property(Lux.scene, "netrenderctl", "false")
                donet = Lux.Property(Lux.scene, "donetrender", "true")
                if (run.get()=="true"):
                    Blender.Draw.Button("Render", 0, 10, y+20, 100, 36, "Render with Lux", lambda e,v: Lux.Launch.ExportStill(dlt.get()=="true", True))
                    Blender.Draw.Button("Render Anim", 0, 110, y+20, 100, 36, "Render animation with Lux", lambda e,v:Lux.Launch.ExportAnim(dlt.get()=="true", True))
                else:
                    Blender.Draw.Button("Export", 0, 10, y+20, 100, 36, "Export", lambda e,v: Lux.Launch.ExportStill(dlt.get()=="true", False))
                    Blender.Draw.Button("Export Anim", 0, 110, y+20, 100, 36, "Export animation", lambda e,v: Lux.Launch.ExportAnim(dlt.get()=="true", False))
        
                Blender.Draw.Toggle("run", Lux.Events.LuxGui, 320, y+40, 30, 16, run.get()=="true", "start Lux after export", lambda e,v: run.set(["false","true"][bool(v)]))
                Blender.Draw.Toggle("def", Lux.Events.LuxGui, 350, y+40, 30, 16, dlt.get()=="true", "save to default.lxs", lambda e,v: dlt.set(["false","true"][bool(v)]))
                Blender.Draw.Toggle("clay", Lux.Events.LuxGui, 380, y+40, 30, 16, clay.get()=="true", "all materials are rendered as white-matte", lambda e,v: clay.set(["false","true"][bool(v)]))
                Blender.Draw.Toggle(".lxs", 0, 290, y+20, 30, 16, lxs.get()=="true", "export .lxs scene file", lambda e,v: lxs.set(["false","true"][bool(v)]))
                Blender.Draw.Toggle(".lxo", 0, 320, y+20, 30, 16, lxo.get()=="true", "export .lxo geometry file", lambda e,v: lxo.set(["false","true"][bool(v)]))
                Blender.Draw.Toggle(".lxm", 0, 350, y+20, 30, 16, lxm.get()=="true", "export .lxm material file", lambda e,v: lxm.set(["false","true"][bool(v)]))
                Blender.Draw.Toggle(".lxv", 0, 380, y+20, 30, 16, lxm.get()=="true", "export .lxv volume file", lambda e,v: lxm.set(["false","true"][bool(v)]))
            Blender.BGL.glColor3f(0.9, 0.9, 0.9) ; Blender.BGL.glRasterPos2i(340,y+5) ; Blender.Draw.Text("Press Q or ESC to quit.", "tiny")
            scrollbar.height = scrollbar.getTop() - y
            scrollbar.draw()
        
            
        # scrollbar = Lux.GUI.scrollbar()
        
        mouse_xr=1 
        mouse_yr=1 
        
        activeObject = None
        activeEvent = None
        lastEventTime = 0
        key_tabs = {
            Blender.Draw.ONEKEY:     0,
            Blender.Draw.TWOKEY:     1,
            Blender.Draw.THREEKEY:   2,
            Blender.Draw.FOURKEY:    3,
            Blender.Draw.FIVEKEY:    4,
        }
        def luxEvent(evt, val):  # function that handles keyboard and mouse events
            global activeObject, activemat, activeEvent, lastEventTime, key_tabs
            if evt == Blender.Draw.ESCKEY or evt == Blender.Draw.QKEY:
                stop = Blender.Draw.PupMenu("OK?%t|Cancel export %x1")
                if stop == 1:
                    Blender.Draw.Exit()
                    return
            Lux.scene = Blender.Scene.GetCurrent()
            if Lux.scene:
                if Lux.scene.objects.active != activeObject:
                    activeObject = Lux.scene.objects.active
                    activemat = None
                    Window.QRedrawAll()
            if (evt == Blender.Draw.MOUSEX) or (evt == Blender.Draw.MOUSEY): scrollbar.Mouse()
            if evt == Blender.Draw.WHEELUPMOUSE: scrollbar.scroll(-16)
            if evt == Blender.Draw.WHEELDOWNMOUSE: scrollbar.scroll(16)
            if evt == Blender.Draw.PAGEUPKEY: scrollbar.scroll(-50)
            if evt == Blender.Draw.PAGEDOWNKEY: scrollbar.scroll(50)
        
            # scroll to [T]op and [B]ottom
            if evt == Blender.Draw.TKEY:
                scrollbar.scroll(-scrollbar.position)
            if evt == Blender.Draw.BKEY:
                scrollbar.scroll(100000)   # Some large number should be enough ?!
        
            # R key shortcut to launch render
            # E key shortcut to export current scene (not render)
            # P key shortcut to preview current material
            # These keys need time and process-complete locks
            if evt in [Blender.Draw.RKEY, Blender.Draw.EKEY, Blender.Draw.PKEY]:
                if activeEvent == None and (sys.time() - lastEventTime) > 5:
                    lastEventTime = sys.time()
                    if evt == Blender.Draw.RKEY:
                        activeEvent = 'RKEY'
                        Lux.Launch.ExportStill(Lux.Property(Lux.scene, "default", "true").get() == "true", True)
                        activeEvent = None
                    if evt == Blender.Draw.EKEY:
                        activeEvent = 'EKEY'
                        Lux.Launch.ExportStill(Lux.Property(Lux.scene, "default", "true").get() == "true", False)
                        activeEvent = None
                    if evt == Blender.Draw.PKEY:
                        activeEvent = 'PKEY'
                        if activemat != None:
                            Preview_Update(activemat, '', True, 0, None, None, None)
                        activeEvent = None
                
            # Switch GUI tabs with number keys
            if evt in key_tabs.keys():
                Lux.Property(Lux.scene, "page", 0).set(key_tabs[evt])        
                luxDraw()
                Window.QRedrawAll()
                  
        
            # Handle icon button events - note - radiance - this is a work in progress! :)
        #    if evt == Blender.Draw.LEFTMOUSE and not val: 
        #           size=Blender.BGL.Buffer(Blender.BGL.GL_FLOAT, 4) 
        #           Blender.BGL.glGetFloatv(Blender.BGL.GL_SCISSOR_BOX, size) 
        #            size= [int(s) for s in size] 
        #        mx, my = Window.GetMouseCoords()
        #        mousex = mx - size[0]
        #        print "mousex = %i"%mousex
        #        #if((mousex > 2) and (mousex < 25)):
        #            # Mouse clicked in left button bar
        #        if((mousex > 399) and (mousex < 418)):
        #            # Mouse clicked in right button bar
        #            mousey = my - size[1] - scrollbar.position
        #            print "mousey = %i"%mousey
                    
            
        def luxButtonEvt(evt):  # function that handles button events
            global usedproperties, usedpropertiesfilterobj
            if evt == Lux.Events.LuxGui:
                Blender.Draw.Redraw()
            if evt == Lux.Events.SavePreset:
                Lux.scene = Blender.Scene.GetCurrent()
                if Lux.scene:
                    name = Blender.Draw.PupStrInput("preset name: ", "")
                    if name != "":
                        usedproperties = {}
                        usedpropertiesfilterobj = None
                        luxSurfaceIntegrator(Lux.scene)
                        luxSampler(Lux.scene)
                        luxPixelFilter(Lux.scene)
                        # Lux.SceneElements.Film()
                        luxAccelerator(Lux.scene)
                        # luxEnvironment(Lux.scene)
                        saveScenePreset(name, usedproperties.copy())
                        Lux.Property(Lux.scene, "preset", "").set(name)
                        Blender.Draw.Redraw()
            if evt == Lux.Events.DeletePreset:
                presets = getScenePresets().keys()
                presets.sort()
                presetsstr = "delete preset: %t"
                for i, v in enumerate(presets): presetsstr += "|%s %%x%d"%(v, i)
                r = Blender.Draw.PupMenu(presetsstr, 20)
                if r >= 0:
                    saveScenePreset(presets[r], None)
                    Blender.Draw.Redraw()
        
            if evt == Lux.Events.LoadMaterial:
                if activemat:
                    mats = getMaterialPresets()
                    matskeys = mats.keys()
                    matskeys.sort()
                    matsstr = "load preset: %t"
                    for i, v in enumerate(matskeys): matsstr += "|%s %%x%d"%(v, i)
                    r = Blender.Draw.PupMenu(matsstr, 20)
                    if r >= 0:
                        name = matskeys[r]
                        try:
        #                    for k,v in mats[name].items(): activemat.properties['luxblend'][k] = v
                            for k,v in mats[name].items(): Lux.Property(activemat, k, None).set(v)
                        except: pass
                        Blender.Draw.Redraw()
            if evt == Lux.Events.SaveMaterial:
                if activemat:
                    name = Blender.Draw.PupStrInput("preset name: ", "")
                    if name != "":
                        usedproperties = {}
                        usedpropertiesfilterobj = activemat
                        luxMaterial(activemat)
                        saveMaterialPreset(name, usedproperties.copy())
                        Blender.Draw.Redraw()
            if evt == Lux.Events.DeleteMaterial:
                matskeys = getMaterialPresets().keys()
                matskeys.sort()
                matsstr = "delete preset: %t"
                for i, v in enumerate(matskeys): matsstr += "|%s %%x%d"%(v, i)
                r = Blender.Draw.PupMenu(matsstr, 20)
                if r >= 0:
                    saveMaterialPreset(matskeys[r], None)
                    Blender.Draw.Redraw()
            if evt == Lux.Events.ConvertMaterial:
                if activemat: convertMaterial(activemat)
                Blender.Draw.Redraw()
            if evt == Lux.Events.LoadMaterial2:
                if activemat:
                    Lux.scene = Blender.Scene.GetCurrent()
                    Window.FileSelector(lambda fn:loadMatTex(activemat, fn), "load material", Lux.Property(Lux.scene, "lux", "").get()+os.sep+".lbm")
            if evt == Lux.Events.SaveMaterial2:
                if activemat:
                    Lux.scene = Blender.Scene.GetCurrent()
                    Window.FileSelector(lambda fn:saveMaterial(activemat, fn), "save material", Lux.Property(Lux.scene, "lux", "").get()+os.sep+".lbm")
            
                
    class TypedControls:
        
        def Help(name, lux, caption, hint, width=1.0):
            if Lux.i_gui:
                r = gui.getRect(width, 1)
                Blender.Draw.Toggle(caption, Lux.Events.LuxGui, r[0], r[1], r[2], r[3], lux.get()=="true", hint, lambda e,v: lux.set(["false","true"][bool(v)]))
                drawIcon(icon_help, r[0], r[1])
        
            return "\n   \"bool %s\" [\"%s\"]"%(name, lux.get())
        
        def Option(name, lux, options, caption, hint, width=1.0):
            if Lux.i_gui:
                menustr = caption+": %t"
                for i, v in enumerate(options): menustr = "%s %%x%d|%s"%(v, i, menustr)
                try:
                    i = options.index(lux.get())
                except ValueError:
                    try:
                        lux.set(lux.default) # not found, so try default value
                        i = options.index(lux.get())
                    except ValueError:
                        print "value %s not found in options list"%(lux.get())
                        i = 0
                r = Lux.i_gui.getRect(width, 1)
                Blender.Draw.Menu(menustr, Lux.Events.LuxGui, r[0], r[1], r[2], r[3], i, hint, lambda e,v: lux.set(options[v]))
            return "\n   \"string %s\" [\"%s\"]" % (name, lux.get())
        
        def OptionRect(name, lux, options, caption, hint, x, y, xx, yy):
            if Lux.i_gui:
                menustr = caption+": %t"
                for i, v in enumerate(options): menustr = "%s %%x%d|%s"%(v, i, menustr)
                try:
                    i = options.index(lux.get())
                except ValueError:
                    try:
                        lux.set(lux.default) # not found, so try default value
                        i = options.index(lux.get())
                    except ValueError:
                        print "value %s not found in options list"%(lux.get())
                        i = 0
                Blender.Draw.Menu(menustr, Lux.Events.LuxGui, x, y, xx, yy, i, hint, lambda e,v: lux.set(options[v]))
            return "\n   \"string %s\" [\"%s\"]"%(name, lux.get())
        
        def Identifier(name, lux, options, caption, hint, icon=None, width=1.0):
            if Lux.i_gui:
                Lux.i_gui.newline(caption+":", 8, 0, icon, [0.75,0.5,0.25])
            Lux.TypedControls.Option(name, lux, options, caption, hint, width)
            return "\n%s \"%s\""%(name, lux.get())
        
        # DH - some Float()s had gui = None - presumably deliberately hidden fields ?
        def Float(name, lux, min, max, caption, hint, width=1.0, useslider=0):
            if Lux.i_gui:
                if (Lux.Property(Blender.Scene.GetCurrent(), "useparamkeys", "false").get()=="true"):
                    r = Lux.i_gui.getRect(width-0.12, 1)
                else:
                    r = Lux.i_gui.getRect(width, 1)
        
                # Value
                if(useslider==1):
                    Blender.Draw.Slider(caption+": ", Lux.Events.LuxGui, r[0], r[1], r[2], r[3], lux.getFloat(), min, max, 0, hint, lambda e,v: lux.set(v))
                else:
                    Blender.Draw.Number(caption+": ", Lux.Events.LuxGui, r[0], r[1], r[2], r[3], lux.getFloat(), min, max, hint, lambda e,v: lux.set(v))
                if (Lux.Property(Blender.Scene.GetCurrent(), "useparamkeys", "false").get()=="true"):
                    # IPO Curve
                    obj = lux.getobj()
                    keyname = lux.getname()
            
                    useipo = Lux.Property(obj, keyname+".IPOuse", "false")
                    i = Lux.i_gui.getRect(0.12, 1)
                    Blender.Draw.Toggle("I", Lux.Events.LuxGui, i[0], i[1], i[2], i[3], useipo.get()=="true", "Use IPO Curve", lambda e,v: useipo.set(["false","true"][bool(v)]))
                    
                    if useipo.get() == "true":
                        if Lux.i_gui: Lux.i_gui.newline(caption+"IPO:", 8, 0, None, [0.5,0.45,0.35])
                        curve = Lux.Property(obj, keyname+".IPOCurveName", "") 
                        if curve.get() == "":
                            c = Lux.i_gui.getRect(2.0, 1)
                        else:
                            c = Lux.i_gui.getRect(1.1, 1)
                        
                        Blender.Draw.String("Ipo:", Lux.Events.LuxGui, c[0], c[1], c[2], c[3], curve.get(), 250, "Set IPO Name", lambda e,v: curve.set(v))
                        
                        usemapping = Lux.Property(obj, keyname+".IPOmap", "false")
                        icu_value = 0
            
                        # Apply IPO to value
                        if curve.get() != "":
                            try:
                                ipoob = Blender.Ipo.Get(curve.get())
                            except: 
                                curve.set("")
                            pass
                            if curve.get() != "":
                                names = list([x[0] for x in ipoob.curveConsts.items()])
                                ipotype = Lux.Property(obj, keyname+".IPOCurveType", "OB_LOCZ")
                                Lux.TypedControls.Option("ipocurve", ipotype, names, "IPO Curve", "Set IPO Curve", 0.6)
            
                                icu = ipoob[eval("Blender.Ipo.%s" % (ipotype.get()))]
                                icu_value = icu[Blender.Get('curframe')]
                                if usemapping.get() == "false": # if true is set during mapping below
                                    lux.set(icu_value)    
            
                                # Mapping options
                                m = Lux.i_gui.getRect(0.3, 1)
                                Blender.Draw.Toggle("Map", Lux.Events.LuxGui, m[0], m[1], m[2], m[3], usemapping.get()=="true", "Edit Curve mapping", lambda e,v: usemapping.set(["false","true"][bool(v)]))
                                if usemapping.get() == "true":
                                    if Lux.i_gui: Lux.i_gui.newline(caption+"IPO:", 8, 0, None, [0.5,0.45,0.35])
                                    fmin = Lux.Property(obj, keyname+".IPOCurvefmin", 0.0)
                                    Lux.TypedControls.FloatNoIPO("ipofmin", fmin, -100, 100, "fmin", "Map minimum value from Curve", 0.5)
                                    fmax = Lux.Property(obj, keyname+".IPOCurvefmax", 1.0)
                                    Lux.TypedControls.FloatNoIPO("ipofmax", fmax, -100, 100, "fmax", "Map maximum value from Curve", 0.5)
                                    tmin = Lux.Property(obj, keyname+".IPOCurvetmin", min)
                                    Lux.TypedControls.FloatNoIPO("ipotmin", tmin, min, max, "tmin", "Map miminum value to", 0.5)
                                    tmax = Lux.Property(obj, keyname+".IPOCurvetmax", max)
                                    Lux.TypedControls.FloatNoIPO("ipotmax", tmax, min, max, "tmax", "Map maximum value to", 0.5)
            
                                    sval = (icu_value - fmin.getFloat()) / (fmax.getFloat() - fmin.getFloat())
                                    lux.set(tmin.getFloat() + (sval * (tmax.getFloat() - tmin.getFloat())))
        
                                    # invert
                                    #v = Lux.i_gui.getRect(0.5, 1)
                                    #Blender.Draw.Toggle("Invert", Lux.Events.LuxGui, v[0], v[1], v[2], v[3], useipo.get()=="true", "Invert Curve values", lambda e,v: useipo.set(["false","true"][bool(v)]))
            else:
                if (Lux.Property(Blender.Scene.GetCurrent(), "useparamkeys", "false").get()=="true"):
                    obj = lux.getobj()
                    keyname = lux.getname()
                    useipo = Lux.Property(obj, keyname+".IPOuse", "false")
                    if useipo.get() == "true":
                        curve = Lux.Property(obj, keyname+".IPOCurveName", "") 
                        try:
                            ipoob = Blender.Ipo.Get(curve.get())
                        except: 
                            curve.set("")
                        pass
                        usemapping = Lux.Property(obj, keyname+".IPOmap", "false")
                        icu_value = 0
                        if curve.get() != "":
                            names = list([x[0] for x in ipoob.curveConsts.items()])
                            ipotype = Lux.Property(obj, keyname+".IPOCurveType", "OB_LOCZ")
            
                            icu = ipoob[eval("Blender.Ipo.%s" % (ipotype.get()))]
                            icu_value = icu[Blender.Get('curframe')]
                            if usemapping.get() == "false": # if true is set during mapping below
                                lux.set(icu_value)    
            
                        if usemapping.get() == "true":
                            if Lux.i_gui: Lux.i_gui.newline(caption+"IPO:", 8, 0, None, [0.5,0.45,0.35])
                            fmin = Lux.Property(obj, keyname+".IPOCurvefmin", 0.0)
                            fmax = Lux.Property(obj, keyname+".IPOCurvefmax", 1.0)
                            tmin = Lux.Property(obj, keyname+".IPOCurvetmin", min)
                            tmax = Lux.Property(obj, keyname+".IPOCurvetmax", max)
                            sval = (icu_value - fmin.getFloat()) / (fmax.getFloat() - fmin.getFloat())
                            lux.set(tmin.getFloat() + (sval * (tmax.getFloat() - tmin.getFloat())))
        
            return "\n   \"float %s\" [%f]"%(name, lux.getFloat())
        
        def FloatNoIPO(name, lux, min, max, caption, hint, width=1.0, useslider=0):
            if Lux.i_gui:
                r = Lux.i_gui.getRect(width, 1)
                if(useslider==1):
                    Blender.Draw.Slider(caption+": ", Lux.Events.LuxGui, r[0], r[1], r[2], r[3], lux.getFloat(), min, max, 0, hint, lambda e,v: lux.set(v))
                else:
                    Blender.Draw.Number(caption+": ", Lux.Events.LuxGui, r[0], r[1], r[2], r[3], lux.getFloat(), min, max, hint, lambda e,v: lux.set(v))
            return "\n   \"float %s\" [%f]"%(name, lux.getFloat())
               
        def Int(name, lux, min, max, caption, hint, width=1.0):
            if Lux.i_gui:
                r = Lux.i_gui.getRect(width, 1)
                Blender.Draw.Number(caption+": ", Lux.Events.LuxGui, r[0], r[1], r[2], r[3], lux.getInt(), min, max, hint, lambda e,v: lux.set(v))
            return "\n   \"integer %s\" [%d]"%(name, lux.getInt())
        
        def Bool(name, lux, caption, hint, width=1.0):
            if Lux.i_gui:
                r = Lux.i_gui.getRect(width, 1)
                Blender.Draw.Toggle(caption, Lux.Events.LuxGui, r[0], r[1], r[2], r[3], lux.get()=="true", hint, lambda e,v: lux.set(["false","true"][bool(v)]))
            return "\n   \"bool %s\" [\"%s\"]"%(name, lux.get())
        
        def String(name, lux, caption, hint, width=1.0):
            if Lux.i_gui:
                r = Lux.i_gui.getRect(width, 1)
                Blender.Draw.String(caption+": ", Lux.Events.LuxGui, r[0], r[1], r[2], r[3], lux.get(), 250, hint, lambda e,v: lux.set(v))
            if lux.get()==lux.default: return ""
            else: return "\n   \"string %s\" [\"%s\"]"%(name, luxstr(lux.get()))
        
        def File(name, lux, caption, hint, width=1.0):
            if Lux.i_gui:
                r = Lux.i_gui.getRect(width, 1)
                Blender.Draw.String(caption+": ", Lux.Events.LuxGui, r[0], r[1], r[2]-r[3]-2, r[3], lux.get(), 250, hint, lambda e,v: lux.set(v))
                Blender.Draw.Button("...", 0, r[0]+r[2]-r[3], r[1], r[3], r[3], "click to open file selector", lambda e,v:Window.FileSelector(lambda s:lux.set(s), "Select %s"%(caption), lux.get()))
            return "\n   \"string %s\" [\"%s\"]"%(name, luxstr(lux.get()))
        
        def Path(name, lux, caption, hint, width=1.0):
            if Lux.i_gui:
                r = Lux.i_gui.getRect(width, 1)
                Blender.Draw.String(caption+": ", Lux.Events.LuxGui, r[0], r[1], r[2]-r[3]-2, r[3], lux.get(), 250, hint, lambda e,v: lux.set(Blender.sys.dirname(v)+os.sep))
                Blender.Draw.Button("...", 0, r[0]+r[2]-r[3], r[1], r[3], r[3], "click to open file selector", lambda e,v:Window.FileSelector(lambda s:lux.set(s), "Select %s"%(caption), lux.get()))
            return "\n   \"string %s\" [\"%s\"]"%(name, luxstr(lux.get()))
        
        def RGB(name, lux, max, caption, hint, width=2.0):
            if Lux.i_gui:
                r = Lux.i_gui.getRect(width, 1)
                scale = 1.0
                rgb = lux.getRGB()
                if max > 1.0:
                    for i in range(3):
                        if rgb[i] > scale: scale = rgb[i]
                    rgb = (rgb[0]/scale, rgb[1]/scale, rgb[2]/scale)
                Blender.Draw.ColorPicker(Lux.Events.LuxGui, r[0], r[1], r[3], r[3], rgb, "click to select color", lambda e,v: lux.setRGB((v[0]*scale,v[1]*scale,v[2]*scale)))
                w = int((r[2]-r[3])/3); m = max
                if max > 1.0:
                    w = int((r[2]-r[3])/4); m = 1.0
                drawR, drawG, drawB, drawS = Blender.Draw.Create(rgb[0]), Blender.Draw.Create(rgb[1]), Blender.Draw.Create(rgb[2]), Blender.Draw.Create(scale)
                drawR = Blender.Draw.Number("R:", Lux.Events.LuxGui, r[0]+r[3], r[1], w, r[3], drawR.val, 0.0, m, "red", lambda e,v: lux.setRGB((v*scale,drawG.val*scale,drawB.val*scale)))
                drawG = Blender.Draw.Number("G:", Lux.Events.LuxGui, r[0]+r[3]+w, r[1], w, r[3], drawG.val, 0.0, m, "green", lambda e,v: lux.setRGB((drawR.val*scale,v*scale,drawB.val*scale)))
                drawB = Blender.Draw.Number("B:", Lux.Events.LuxGui, r[0]+r[3]+2*w, r[1], w, r[3], drawB.val, 0.0, m, "blue", lambda e,v: lux.setRGB((drawR.val*scale,drawG.val*scale,v*scale)))
                if max > 1.0:
                    Blender.Draw.Number("s:", Lux.Events.LuxGui, r[0]+r[3]+3*w, r[1], w, r[3], drawS.val, 0.0, max, "color scale", lambda e,v: lux.setRGB((drawR.val*v,drawG.val*v,drawB.val*v)))
            if max <= 1.0:
                return "\n   \"color %s\" [%s]"%(name, lux.getRGC())
            return "\n   \"color %s\" [%s]"%(name, lux.get())
        
        def Vector(name, lux, min, max, caption, hint, width=2.0):
            if Lux.i_gui:
                r = Lux.i_gui.getRect(width, 1)
                vec = lux.getVector()
                w = int(r[2]/3)
                drawX, drawY, drawZ = Blender.Draw.Create(vec[0]), Blender.Draw.Create(vec[1]), Blender.Draw.Create(vec[2])
                drawX = Blender.Draw.Number("x:", Lux.Events.LuxGui, r[0], r[1], w, r[3], drawX.val, min, max, "", lambda e,v: lux.setVector((v,drawY.val,drawZ.val)))
                drawY = Blender.Draw.Number("y:", Lux.Events.LuxGui, r[0]+w, r[1], w, r[3], drawY.val, min, max, "", lambda e,v: lux.setVector((drawX.val,v,drawZ.val)))
                drawZ = Blender.Draw.Number("z:", Lux.Events.LuxGui, r[0]+2*w, r[1], w, r[3], drawZ.val, min, max, "", lambda e,v: lux.setVector((drawX.val,drawY.val,v)))
            return "\n   \"vector %s\" [%s]"%(name, lux.get())
        
        def VectorUniform(name, lux, min, max, caption, hint, width=2.0):
            def setUniform(lux, value):
                if value: lux.set(lux.getFloat())
                else: lux.setVector(lux.getVector())
            if Lux.i_gui:
                r = Lux.i_gui.getRect(width, 1)
                vec = lux.getVector()
                Blender.Draw.Toggle("U", Lux.Events.LuxGui, r[0], r[1], Lux.i_gui.h, Lux.i_gui.h, lux.isFloat(), "uniform", lambda e,v: setUniform(lux, v))
                if lux.isFloat():
                    Blender.Draw.Number("v:", Lux.Events.LuxGui, r[0]+Lux.i_gui.h, r[1], r[2]-Lux.i_gui.h, r[3], lux.getFloat(), min, max, "", lambda e,v: lux.set(v))
                else:
                    w = int((r[2]-gui.h)/3)
                    drawX, drawY, drawZ = Blender.Draw.Create(vec[0]), Blender.Draw.Create(vec[1]), Blender.Draw.Create(vec[2])
                    drawX = Blender.Draw.Number("x:", Lux.Events.LuxGui, r[0]+Lux.i_gui.h, r[1], w, r[3], drawX.val, min, max, "", lambda e,v: lux.setVector((v,drawY.val,drawZ.val)))
                    drawY = Blender.Draw.Number("y:", Lux.Events.LuxGui, r[0]+w+Lux.i_gui.h, r[1], w, r[3], drawY.val, min, max, "", lambda e,v: lux.setVector((drawX.val,v,drawZ.val)))
                    drawZ = Blender.Draw.Number("z:", Lux.Events.LuxGui, r[0]+2*w+Lux.i_gui.h, r[1], w, r[3], drawZ.val, min, max, "", lambda e,v: lux.setVector((drawX.val,drawY.val,v)))
            return "\n   \"vector %s\" [%s]"%(name, lux.getVectorStr())
        
    class SceneElements:
    
        @staticmethod
        def Camera(cam, context):            
            str = ""
            if cam:
                camtype = Lux.Property(cam, "camera.type", "perspective")
                str = Lux.TypedControls.Identifier("Camera", camtype, ["perspective","orthographic","environment","realistic"], "CAMERA", "select camera type", Lux.Icon.get_icon('icon_c_camera'))
                scale = 1.0
                if camtype.get() == "perspective":
                    str += Lux.TypedControls.Float("fov", Lux.Attribute(cam, "angle"), 8.0, 170.0, "fov", "camera field-of-view angle")
                if camtype.get() == "orthographic" :
                    str += Lux.TypedControls.Float("scale", Lux.Attribute(cam, "scale"), 0.01, 1000.0, "scale", "orthographic camera scale")
                    scale = cam.scale / 2
                if camtype.get() == "realistic":
                    fov = Lux.Attribute(cam, "angle")
                    Lux.TypedControls.Float("fov", fov, 8.0, 170.0, "fov", "camera field-of-view angle")
                    if gui: gui.newline()
                    str += Lux.TypedControls.File("specfile", Lux.Property(cam, "camera.realistic.specfile", ""), "spec-file", "", 1.0)
        #            if gui: gui.newline()
        # auto calc        str += Lux.Types.Float("filmdistance", Lux.Prop(cam, "camera.realistic.filmdistance", 70.0), 0.1, 1000.0, "film-dist", "film-distance [mm]")
                    filmdiag = Lux.Property(cam, "camera.realistic.filmdiag", 35.0)
                    str += Lux.TypedControls.Float("filmdiag", filmdiag, 0.1, 1000.0, "film-diag", "[mm]")
                    if gui: gui.newline()
                    fstop = Lux.Property(cam, "camera.realistic.fstop", 1.0)
                    Lux.TypedControls.Float("aperture_diameter", fstop, 0.1, 100.0, "f-stop", "")
                    dofdist = Lux.Attribute(cam, "dofDist")
                    Lux.TypedControls.Float("focaldistance", dofdist, 0.0, 10000.0, "distance", "Distance from the camera at which objects will be in focus. Has no effect if Lens Radius is 0")
                    if gui:
                        Blender.Draw.Button("S", Lux.Events.LuxGui, gui.x, gui.y-gui.h, gui.h, gui.h, "focus selected object", lambda e,v:setFocus("S"))
                        Blender.Draw.Button("C", Lux.Events.LuxGui, gui.x+gui.h, gui.y-gui.h, gui.h, gui.h, "focus cursor", lambda e,v:setFocus("C"))
                    focal = filmdiag.get()*0.001 / math.tan(fov.get() * math.pi / 360.0) / 2.0
                    print "calculated focal length: %f mm"%(focal * 1000.0)
                    aperture_diameter = focal / fstop.get()
                    print "calculated aperture diameter: %f mm"%(aperture_diameter * 1000.0)
                    str += "\n   \"float aperture_diameter\" [%f]"%(aperture_diameter*1000.0)
                    filmdistance = dofdist.get() * focal / (dofdist.get() - focal)
                    print "calculated film distance: %f mm"%(filmdistance * 1000.0)
                    str += "\n   \"float filmdistance\" [%f]"%(filmdistance*1000.0)
        
                # Clipping
                useclip = Lux.Property(cam, "useclip", "false")
                Lux.TypedControls.Bool("useclip", useclip, "Near & Far Clipping", "Enable Camera near and far clipping options", 2.0)
                if(useclip.get() == "true"):
                    if gui: gui.newline("  Clipping:")
                    str += Lux.TypedControls.Float("hither", Lux.Attribute(cam, "clipStart"), 0.0, 100.0, "start", "near clip distance")
                    str += Lux.TypedControls.Float("yon", Lux.Attribute(cam, "clipEnd"), 1.0, 10000.0, "end", "far clip distance")
        
                # Depth of Field
                usedof = Lux.Property(cam, "usedof", "false")
                Lux.TypedControls.Bool("usedof", usedof, "Depth of Field & Bokeh", "Enable Depth of Field & Aperture options", 2.0)
                if camtype.get() in ["perspective", "orthographic"] and usedof.get() == "true":
                    if gui: gui.newline("  DOF:")
                    focustype = Lux.Property(cam, "camera.focustype", "autofocus")
                    Lux.TypedControls.Option("focustype", focustype, ["autofocus", "manual", "object"], "Focus Type", "Choose the focus behaviour")
                    str += Lux.TypedControls.Float("lensradius", Lux.Property(cam, "camera.lensradius", 0.01), 0.0, 1.0, "lens-radius", "Defines the lens radius. Values higher than 0. enable DOF and control the amount")
        
                    if focustype.get() == "autofocus":
                        str += Lux.TypedControls.Bool("autofocus",Lux.Property(cam, "camera.autofocus", "true"), "autofocus", "Enable automatic focus")
                    if focustype.get() == "object":
                        objectfocus = Lux.Property(cam, "camera.objectfocus", "")
                        Lux.TypedControls.String("objectfocus", objectfocus, "object", "Always focus camera on named object", 1.0)
                        dofdist = Lux.Attribute(cam, "dofDist")
                        str += Lux.TypedControls.Float("focaldistance", dofdist, 0.0, 100.0, "distance", "Distance from the camera at which objects will be in focus. Has no effect if Lens Radius is 0")
                        if objectfocus.get() != "":
                            setFocus(objectfocus.get())
                    if focustype.get() == "manual":
                        dofdist = Lux.Attribute(cam, "dofDist")
                        str += Lux.TypedControls.Float("focaldistance", dofdist, 0.0, 100.0, "distance", "Distance from the camera at which objects will be in focus. Has no effect if Lens Radius is 0")
                        if gui:
                            Blender.Draw.Button("S", Lux.Events.LuxGui, gui.x, gui.y-gui.h, gui.h, gui.h, "focus selected object", lambda e,v:setFocus("S"))
                            Blender.Draw.Button("C", Lux.Events.LuxGui, gui.x+gui.h, gui.y-gui.h, gui.h, gui.h, "focus cursor", lambda e,v:setFocus("C"))
        
                if camtype.get() == "perspective" and usedof.get() == "true":
                    str += Lux.TypedControls.Int("blades", Lux.Property(cam, "camera.blades", 6), 0, 16, "aperture blades", "Number of blade edges of the aperture, values 0 to 2 defaults to a circle")
                    str += Lux.TypedControls.Option("distribution", Lux.Property(cam, "camera.distribution", "uniform"), ["uniform", "exponential", "inverse exponential", "gaussian", "inverse gaussian"], "distribution", "Choose the lens sampling distribution. Non-uniform distributions allow for ring effects.")
                    str += Lux.TypedControls.Int("power", Lux.Property(cam, "camera.power", 1), 0, 512, "power", "Exponent for the expression in exponential distribution. Higher value gives a more pronounced ring effect.")
        
                useaspect = Lux.Property(cam, "useaspectratio", "false")
                aspectratio = Lux.Property(cam, "ratio", 1.3333)
                if camtype.get() in ["perspective", "orthographic"]:
                    useshift = Lux.Property(cam, "camera.useshift", "false")
                    Lux.TypedControls.Bool("useshift", useshift, "Architectural (Lens Shift) & Aspect Ratio", "Enable Lens Shift and Aspect Ratio options", 2.0)
                    if(useshift.get() == "true"):
                        if gui: gui.newline("  Shift:")
                        Lux.TypedControls.Float("X", Lux.Attribute(cam, "shiftX"), -2.0, 2.0, "X", "horizontal lens shift")
                        Lux.TypedControls.Float("Y", Lux.Attribute(cam, "shiftY"), -2.0, 2.0, "Y", "vertical lens shift")
        
                        if gui: gui.newline("  AspectRatio:")
                        Lux.TypedControls.Bool("useaspectratio", useaspect, "Custom", "Define a custom frame aspect ratio")
                        if useaspect.get() == "true":
                            str += Lux.TypedControls.Float("frameaspectratio", aspectratio, 0.0001, 3.0, "aspectratio", "Frame aspect ratio")
                    if context:
                        if useaspect.get() == "true":
                            ratio = 1./aspectratio.get()
                        else:
                                ratio = float(context.sizeY)/float(context.sizeX)
                        if ratio < 1.0:
                            screenwindow = [(2*cam.shiftX-1)*scale, (2*cam.shiftX+1)*scale, (2*cam.shiftY-ratio)*scale, (2*cam.shiftY+ratio)*scale]
                        else:
                            screenwindow = [(2*cam.shiftX-1/ratio)*scale, (2*cam.shiftX+1/ratio)*scale, (2*cam.shiftY-1)*scale, (2*cam.shiftY+1)*scale]
                        # render region option
                        if context.borderRender:
                            (x1,y1,x2,y2) = context.border
                            screenwindow = [screenwindow[0]*(1-x1)+screenwindow[1]*x1, screenwindow[0]*(1-x2)+screenwindow[1]*x2,\
                                    screenwindow[2]*(1-y1)+screenwindow[3]*y1, screenwindow[2]*(1-y2)+screenwindow[3]*y2]
                        str += "\n   \"float screenwindow\" [%f %f %f %f]"%(screenwindow[0], screenwindow[1], screenwindow[2], screenwindow[3])
        
                # Note - radiance - this is a work in progress
                # Flash lamp option for perspective and ortho cams
        #        if camtype.get() in ["perspective", "orthographic"]:
        #            useflash = Lux.Prop(cam, "useflash", "false")
        #            Lux.Types.Bool("useflash", useflash, "Flash Lamp", "Enable Camera mounted flash lamp options", 2.0)
        
                # Motion Blur Options (common to all cameras)
                usemblur = Lux.Property(cam, "usemblur", "false")
                Lux.TypedControls.Bool("usemblur", usemblur, "Motion Blur", "Enable Motion Blur", 2.0)
                if(usemblur.get() == "true"):    
                    if gui: gui.newline("  Shutter:")
                    mblurpreset = Lux.Property(cam, "mblurpreset", "true")
                    Lux.TypedControls.Bool("mblurpreset", mblurpreset, "Preset", "Enable use of Shutter Presets", 0.4)
                    if(mblurpreset.get() == "true"):
                        shutterpresets = ["full frame", "half frame", "quarter frame", "1/25", "1/30", "1/45", "1/60", "1/85", "1/125", "1/250", "1/500"]        
                        shutterpreset = Lux.Property(cam, "camera.shutterspeedpreset", "full frame")
                        Lux.TypedControls.Option("shutterpreset", shutterpreset, shutterpresets, "shutterspeed", "Choose the Shutter speed preset.", 1.0)
        
                        fpspresets = ["10 FPS", "12 FPS", "20 FPS", "25 FPS", "29.99 FPS", "30 FPS", "50 FPS", "60 FPS"]
                        shutfps = Lux.Property(cam, "camera.shutfps", "25 FPS")
                        Lux.TypedControls.Option("shutfps", shutfps, fpspresets, "@", "Choose the number of frames per second as the time base.", 0.6)
        
                        sfps = shutfps.get()
                        fps = 25
                        if sfps == "10 FPS": fps = 10
                        elif sfps == "12 FPS": fps = 12
                        elif sfps == "20 FPS": fps = 20
                        elif sfps == "25 FPS": fps = 25
                        elif sfps == "29.99 FPS": fps = 29.99
                        elif sfps == "30 FPS": fps = 30
                        elif sfps == "50 FPS": fps = 50
                        elif sfps == "60 FPS": fps = 60
        
                        spre = shutterpreset.get()
                        open = 0.0
                        close = 1.0
                        if spre == "full frame": close = 1.0
                        elif spre == "half frame": close = 0.5
                        elif spre == "quarter frame": close = 0.25
                        elif spre == "1/25": close = 1.0 / 25.0 * fps
                        elif spre == "1/30": close = 1.0 / 30.0 * fps
                        elif spre == "1/45": close = 1.0 / 45.0 * fps
                        elif spre == "1/60": close = 1.0 / 60.0 * fps
                        elif spre == "1/85": close = 1.0 / 85.0 * fps
                        elif spre == "1/125": close = 1.0 / 125.0 * fps
                        elif spre == "1/250": close = 1.0 / 250.0 * fps
                        elif spre == "1/500": close = 1.0 / 500.0 * fps
        
                        str += "\n   \"float shutteropen\" [%f]\n   \"float shutterclose\" [%f] "%(open,close)
        
                    else:
                        str += Lux.TypedControls.Float("shutteropen", Lux.Property(cam, "camera.shutteropen", 0.0), 0.0, 100.0, "open", "time in seconds when shutter opens", 0.8)
                        str += Lux.TypedControls.Float("shutterclose", Lux.Property(cam, "camera.shutterclose", 1.0), 0.0, 100.0, "close", "time in seconds when shutter closes", 0.8)
        
                    str += Lux.TypedControls.Option("shutterdistribution", Lux.Property(cam, "camera.shutterdistribution", "uniform"), ["uniform", "gaussian"], "distribution", "Choose the shutter sampling distribution.", 2.0)
                    objectmblur = Lux.Property(cam, "objectmblur", "true")
                    Lux.TypedControls.Bool("objectmblur", objectmblur, "Object", "Enable Motion Blur for scene object motions", 1.0)
                    cammblur = Lux.Property(cam, "cammblur", "true")
                    Lux.TypedControls.Bool("cammblur", cammblur, "Camera", "Enable Motion Blur for Camera motion", 1.0)
            return str
        
        @staticmethod
        def Film():
            str = ""
            if Lux.scene:
                filmtype = Lux.Property(Lux.scene, "film.type", "fleximage")
                str = Lux.TypedControls.Identifier("Film", filmtype, ["fleximage"], "FILM", "select film type")
                if filmtype.get() == "fleximage":
                    context = Lux.scene.getRenderingContext()
                    if context:
                        if gui: gui.newline("  Resolution:")
                        Lux.TypedControls.Int("xresolution", Lux.Attribute(context, "sizeX"), 0, 8192, "X", "width of the render", 0.666)
                        Lux.TypedControls.Int("yresolution", Lux.Attribute(context, "sizeY"), 0, 8192, "Y", "height of the render", 0.666)
                        scale = Lux.Property(Lux.scene, "film.scale", "100 %")
                        Lux.TypedControls.Option("", scale, ["100 %", "75 %", "50 %", "25 %"], "scale", "scale resolution", 0.666)
                        scale = int(scale.get()[:-1])
                        # render region option
                        if context.borderRender:
                            (x1,y1,x2,y2) = context.border
                            if (x1==x2) and (y1==y2): print "WARNING: empty render-region, use SHIFT-B to set render region in Blender."
                            str += "\n   \"integer xresolution\" [%d] \n   \"integer yresolution\" [%d]"%(Lux.Attribute(context, "sizeX").get()*scale/100*(x2-x1), Lux.Attribute(context, "sizeY").get()*scale/100*(y2-y1))
                        else:
                            str += "\n   \"integer xresolution\" [%d] \n   \"integer yresolution\" [%d]"%(Lux.Attribute(context, "sizeX").get()*scale/100, Lux.Attribute(context, "sizeY").get()*scale/100)
        
                    if gui: gui.newline("  Halt:")
                    str += Lux.TypedControls.Int("haltspp", Lux.Property(Lux.scene, "haltspp", 0), 0, 32768, "haltspp", "Stop rendering after specified amount of samples per pixel / 0 = never halt")
                    palpha = Lux.Property(Lux.scene, "film.premultiplyalpha", "true")
                    str += Lux.TypedControls.Bool("premultiplyalpha", palpha, "premultiplyalpha", "Pre multiply film alpha channel during normalization")
            
                    if gui: gui.newline("  Tonemap:")
                    tonemapkernel =    Lux.Property(Lux.scene, "film.tonemapkernel", "reinhard")
                    str += Lux.TypedControls.Option("tonemapkernel", tonemapkernel, ["reinhard", "linear", "contrast", "maxwhite"], "Tonemapping Kernel", "Select the tonemapping kernel to use", 2.0)
                    if tonemapkernel.get() == "reinhard":
                        autoywa = Lux.Property(Lux.scene, "film.reinhard.autoywa", "true")
                        str += Lux.TypedControls.Bool("reinhard_autoywa", autoywa, "auto Ywa", "Automatically determine World Adaption Luminance")
                        if autoywa.get() == "false":
                            str += Lux.TypedControls.Float("reinhard_ywa", Lux.Property(Lux.scene, "film.reinhard.ywa", 100.0), 0.0, 1000.0, "Ywa", "Display/World Adaption Luminance")
                        str += Lux.TypedControls.Float("reinhard_prescale", Lux.Property(Lux.scene, "film.reinhard.prescale", 1.0), 0.0, 10.0, "preScale", "Image scale before tonemap operator")
                        str += Lux.TypedControls.Float("reinhard_postscale", Lux.Property(Lux.scene, "film.reinhard.postscale", 1.2), 0.0, 10.0, "postScale", "Image scale after tonemap operator")
                        str += Lux.TypedControls.Float("reinhard_burn", Lux.Property(Lux.scene, "film.reinhard.burn", 6.0), 0.1, 12.0, "burn", "12.0: no burn out, 0.1 lot of burn out")
                    elif tonemapkernel.get() == "linear":
                        str += Lux.TypedControls.Float("linear_sensitivity", Lux.Property(Lux.scene, "film.linear.sensitivity", 100.0), 0.0, 1000.0, "sensitivity", "Adaption/Sensitivity")
                        str += Lux.TypedControls.Float("linear_exposure", Lux.Property(Lux.scene, "film.linear.exposure", 0.001), 0.001, 1.0, "exposure", "Exposure duration in seconds")
                        str += Lux.TypedControls.Float("linear_fstop", Lux.Property(Lux.scene, "film.linear.fstop", 2.8), 0.1, 64.0, "Fstop", "F-Stop")
                        str += Lux.TypedControls.Float("linear_gamma", Lux.Property(Lux.scene, "film.linear.gamma", 1.0), 0.0, 8.0, "gamma", "Tonemap operator gamma correction")
                    elif tonemapkernel.get() == "contrast":
                        str += Lux.TypedControls.Float("contrast_ywa", Lux.Property(Lux.scene, "film.contrast.ywa", 100.0), 0.0, 1000.0, "Ywa", "Display/World Adaption Luminance")
        
                    if gui: gui.newline("  Display:")
                    str += Lux.TypedControls.Int("displayinterval", Lux.Property(Lux.scene, "film.displayinterval", 12), 4, 3600, "interval", "Set display Interval (seconds)")
                    
                    if gui: gui.newline("  Write:")
                    str += Lux.TypedControls.Int("writeinterval", Lux.Property(Lux.scene, "film.writeinterval", 120), 12, 3600, "interval", "Set display Interval (seconds)")
        
                    # override output image dir in case of command line batch mode 
                    overrideop = Lux.Property(Lux.scene, "overrideoutputpath", "")
                    if overrideop.get() != "":
                        filebase = os.path.splitext(os.path.basename(Blender.Get('filename')))[0]
                        filename = overrideop.get() + "/" + filebase + "-%05d" %  (Blender.Get('curframe'))
                        str += "\n   \"string filename\" [\"%s\"]"%(filename)
                    else:
                        fn = Lux.Property(Lux.scene, "filename", "default-%05d" %  (Blender.Get('curframe')))
                        # DH - this has gui = None !
                        str += Lux.TypedControls.String("filename", fn, "File name", "save file name")
        
                    if gui: gui.newline("  Formats:")
                    savetga = Lux.Property(Lux.scene, "film.write_tonemapped_tga", "true")
                    str += Lux.TypedControls.Bool("write_tonemapped_tga", savetga, "Tonemapped TGA", "save tonemapped TGA file")
                    if gui: gui.newline("")
                    savetmexr = Lux.Property(Lux.scene, "film.write_tonemapped_exr", "false")
                    saveexr = Lux.Property(Lux.scene, "film.write_untonemapped_exr", "false")
                    str += Lux.TypedControls.Bool("write_tonemapped_exr", savetmexr, "Tonemapped EXR", "save tonemapped EXR file")
                    str += Lux.TypedControls.Bool("write_untonemapped_exr", saveexr, "Untonemapped EXR", "save untonemapped EXR file")
                    if gui: gui.newline("")
                    savetmigi = Lux.Property(Lux.scene, "film.write_tonemapped_igi", "false")
                    saveigi = Lux.Property(Lux.scene, "film.write_untonemapped_igi", "false")
                    str += Lux.TypedControls.Bool("write_tonemapped_igi", savetmigi, "Tonemapped IGI", "save tonemapped IGI file")
                    str += Lux.TypedControls.Bool("write_untonemapped_igi", saveigi, "Untonemapped IGI", "save untonemapped IGI file")
                    if gui: gui.newline("  Resume:")
                    resumeflm = Lux.Property(Lux.scene, "film.write_resume_flm", "false")
                    str += Lux.TypedControls.Bool("write_resume_flm", resumeflm, "Write/Use FLM", "Write a resume fleximage .flm file, or resume rendering if it already exists")
                    restartflm = Lux.Property(Lux.scene, "film.restart_resume_flm", "false")
                    str += Lux.TypedControls.Bool("restart_resume_flm", restartflm, "Restart/Erase", "Restart with a black flm, even it a previous flm exists")
                    if gui: gui.newline("  Reject:")
                    str += Lux.TypedControls.Int("reject_warmup", Lux.Property(Lux.scene, "film.reject_warmup", 128), 0, 32768, "warmup_spp", "Specify amount of samples per pixel for high intensity rejection")
                    debugmode = Lux.Property(Lux.scene, "film.debug", "false")
                    str += Lux.TypedControls.Bool("debug", debugmode, "debug", "Turn on debug reporting and switch off reject")
        
                    # Colorspace
                    if gui: gui.newline("  Colorspace:")
        
                    cspaceusepreset = Lux.Property(Lux.scene, "film.colorspaceusepreset", "true")
                    Lux.TypedControls.Bool("colorspaceusepreset", cspaceusepreset, "Preset", "Select from a list of predefined presets", 0.4)
        
                    # Default values for 'sRGB - HDTV (ITU-R BT.709-5)'
                    cspacewhiteX = Lux.Property(Lux.scene, "film.cspacewhiteX", 0.314275)
                    cspacewhiteY = Lux.Property(Lux.scene, "film.cspacewhiteY", 0.329411)
                    cspaceredX = Lux.Property(Lux.scene, "film.cspaceredX", 0.63)
                    cspaceredY = Lux.Property(Lux.scene, "film.cspaceredY", 0.34)
                    cspacegreenX = Lux.Property(Lux.scene, "film.cspacegreenX", 0.31)
                    cspacegreenY = Lux.Property(Lux.scene, "film.cspacegreenY", 0.595)
                    cspaceblueX = Lux.Property(Lux.scene, "film.cspaceblueX", 0.155)
                    cspaceblueY = Lux.Property(Lux.scene, "film.cspaceblueY", 0.07)
                    gamma = Lux.Property(Lux.scene, "film.gamma", 2.2)
        
                    if(cspaceusepreset.get() == "true"):
                        # preset controls
                        cspace = Lux.Property(Lux.scene, "film.colorspace", "sRGB - HDTV (ITU-R BT.709-5)")
                        cspaces = ["sRGB - HDTV (ITU-R BT.709-5)", "ROMM RGB", "Adobe RGB 98", "Apple RGB", "NTSC (FCC 1953, ITU-R BT.470-2 System M)", "NTSC (1979) (SMPTE C, SMPTE-RP 145)", "PAL/SECAM (EBU 3213, ITU-R BT.470-6)", "CIE (1931) E"]
                        Lux.TypedControls.Option("colorspace", cspace, cspaces, "Colorspace", "select output working colorspace", 1.6)
        
                        if cspace.get()=="ROMM RGB":
                            cspacewhiteX.set(0.346); cspacewhiteY.set(0.359) # D50
                            cspaceredX.set(0.7347); cspaceredY.set(0.2653)
                            cspacegreenX.set(0.1596); cspacegreenY.set(0.8404)
                            cspaceblueX.set(0.0366); cspaceblueY.set(0.0001)
                        elif cspace.get()=="Adobe RGB 98":
                            cspacewhiteX.set(0.313); cspacewhiteY.set(0.329) # D65
                            cspaceredX.set(0.64); cspaceredY.set(0.34)
                            cspacegreenX.set(0.21); cspacegreenY.set(0.71)
                            cspaceblueX.set(0.15); cspaceblueY.set(0.06)
                        elif cspace.get()=="Apple RGB":
                            cspacewhiteX.set(0.313); cspacewhiteY.set(0.329) # D65
                            cspaceredX.set(0.625); cspaceredY.set(0.34)
                            cspacegreenX.set(0.28); cspacegreenY.set(0.595)
                            cspaceblueX.set(0.155); cspaceblueY.set(0.07)
                        elif cspace.get()=="NTSC (FCC 1953, ITU-R BT.470-2 System M)":
                            cspacewhiteX.set(0.310); cspacewhiteY.set(0.316) # C
                            cspaceredX.set(0.67); cspaceredY.set(0.33)
                            cspacegreenX.set(0.21); cspacegreenY.set(0.71)
                            cspaceblueX.set(0.14); cspaceblueY.set(0.08)
                        elif cspace.get()=="NTSC (1979) (SMPTE C, SMPTE-RP 145)":
                            cspacewhiteX.set(0.313); cspacewhiteY.set(0.329) # D65
                            cspaceredX.set(0.63); cspaceredY.set(0.34)
                            cspacegreenX.set(0.31); cspacegreenY.set(0.595)
                            cspaceblueX.set(0.155); cspaceblueY.set(0.07)
                        elif cspace.get()=="PAL/SECAM (EBU 3213, ITU-R BT.470-6)":
                            cspacewhiteX.set(0.313); cspacewhiteY.set(0.329) # D65
                            cspaceredX.set(0.64); cspaceredY.set(0.33)
                            cspacegreenX.set(0.29); cspacegreenY.set(0.60)
                            cspaceblueX.set(0.15); cspaceblueY.set(0.06)
                        elif cspace.get()=="CIE (1931) E":
                            cspacewhiteX.set(0.333); cspacewhiteY.set(0.333) # E
                            cspaceredX.set(0.7347); cspaceredY.set(0.2653)
                            cspacegreenX.set(0.2738); cspacegreenY.set(0.7174)
                            cspaceblueX.set(0.1666); cspaceblueY.set(0.0089)
        
                        whitepointusecspace = Lux.Property(Lux.scene, "film.whitepointusecolorspace", "true")
                        Lux.TypedControls.Bool("whitepointusecolorspace", whitepointusecspace, "Colorspace Whitepoint", "Use default whitepoint for selected colorspace", 1.0)
                        gammausecspace = Lux.Property(Lux.scene, "film.gammausecolorspace", "true")
                        Lux.TypedControls.Bool("gammausecolorspace", gammausecspace, "Colorspace Gamma", "Use default output gamma for selected colorspace", 1.0)
        
                        if(whitepointusecspace.get() == "false"):
                            if gui: gui.newline("  Whitepoint:")
                            whitepointusepreset = Lux.Property(Lux.scene, "film.whitepointusepreset", "true")
                            Lux.TypedControls.Bool("whitepointusepreset", whitepointusepreset, "Preset", "Select from a list of predefined presets", 0.4)
        
                            if(whitepointusepreset.get() == "true"):
                                whitepointpresets = ["E", "D50", "D55", "D65", "D75", "A", "B", "C", "9300", "F2", "F7", "F11"]
                                whitepointpreset = Lux.Property(Lux.scene, "film.whitepointpreset", "D65")
                                Lux.TypedControls.Option("whitepointpreset", whitepointpreset, whitepointpresets, "  PRESET", "select Whitepoint preset", 1.6)
        
                                if whitepointpreset.get()=="E": cspacewhiteX.set(0.333); cspacewhiteY.set(0.333)
                                elif whitepointpreset.get()=="D50": cspacewhiteX.set(0.346); cspacewhiteY.set(0.359)
                                elif whitepointpreset.get()=="D55": cspacewhiteX.set(0.332); cspacewhiteY.set(0.347)
                                elif whitepointpreset.get()=="D65": cspacewhiteX.set(0.313); cspacewhiteY.set(0.329)
                                elif whitepointpreset.get()=="D75": cspacewhiteX.set(0.299); cspacewhiteY.set(0.315)
                                elif whitepointpreset.get()=="A": cspacewhiteX.set(0.448); cspacewhiteY.set(0.407)
                                elif whitepointpreset.get()=="B": cspacewhiteX.set(0.348); cspacewhiteY.set(0.352)
                                elif whitepointpreset.get()=="C": cspacewhiteX.set(0.310); cspacewhiteY.set(0.316)
                                elif whitepointpreset.get()=="9300": cspacewhiteX.set(0.285); cspacewhiteY.set(0.293)
                                elif whitepointpreset.get()=="F2": cspacewhiteX.set(0.372); cspacewhiteY.set(0.375)
                                elif whitepointpreset.get()=="F7": cspacewhiteX.set(0.313); cspacewhiteY.set(0.329)
                                elif whitepointpreset.get()=="F11": cspacewhiteX.set(0.381); cspacewhiteY.set(0.377)
                            else:
                                Lux.TypedControls.Float("white X", cspacewhiteX, 0.0, 1.0, "white X", "Whitepoint X weight", 0.8)
                                Lux.TypedControls.Float("white Y", cspacewhiteY, 0.0, 1.0, "white Y", "Whitepoint Y weight", 0.8)
        
                        if(gammausecspace.get() == "false"):
                            if gui: gui.newline("  Gamma:")
                            Lux.TypedControls.Float("gamma", gamma, 0.1, 6.0, "gamma", "Output and RGC Gamma", 2.0)
                    else:
                        # manual controls
                        Lux.TypedControls.Float("white X", cspacewhiteX, 0.0, 1.0, "white X", "Whitepoint X weight", 0.8)
                        Lux.TypedControls.Float("white Y", cspacewhiteY, 0.0, 1.0, "white Y", "Whitepoint Y weight", 0.8)
                        Lux.TypedControls.Float("red X", cspaceredX, 0.0, 1.0, "red X", "Red component X weight", 1.0)
                        Lux.TypedControls.Float("red Y", cspaceredY, 0.0, 1.0, "red Y", "Red component Y weight", 1.0)
                        Lux.TypedControls.Float("green X", cspacegreenX, 0.0, 1.0, "green X", "Green component X weight", 1.0)
                        Lux.TypedControls.Float("green Y", cspacegreenY, 0.0, 1.0, "green Y", "Green component Y weight", 1.0)
                        Lux.TypedControls.Float("blue X", cspaceblueX, 0.0, 1.0, "blue X", "Blue component X weight", 1.0)
                        Lux.TypedControls.Float("blue Y", cspaceblueY, 0.0, 1.0, "blue Y", "Blue component Y weight", 1.0)
                        if gui: gui.newline("  Gamma:")
                        Lux.TypedControls.Float("gamma", gamma, 0.1, 6.0, "gamma", "Output and RGC Gamma", 2.0)
        
                    str += "\n   \"float colorspace_white\" [%f %f]"%(cspacewhiteX.get(), cspacewhiteY.get())
                    str += "\n   \"float colorspace_red\" [%f %f]"%(cspaceredX.get(), cspaceredY.get())
                    str += "\n   \"float colorspace_green\" [%f %f]"%(cspacegreenX.get(), cspacegreenY.get())
                    str += "\n   \"float colorspace_blue\" [%f %f]"%(cspaceblueX.get(), cspaceblueY.get())
                    str += "\n   \"float gamma\" [%f]"%(gamma.get())
        
            return str
        
        @staticmethod
        def PixelFilter(): #scn, gui=None):
            global icon_c_filter
            str = ""
            if Lux.scene:
                filtertype = Lux.Property(Lux.scene, "pixelfilter.type", "mitchell")
                str = Lux.TypedControls.Identifier("PixelFilter", filtertype, ["box", "gaussian", "mitchell", "sinc", "triangle"], "FILTER", "select pixel filter type", icon_c_filter)
        
                # Advanced toggle
                parammodeadvanced = Lux.Property(Lux.scene, "parammodeadvanced", "false")
                showadvanced = Lux.Property(Lux.scene, "pixelfilter.showadvanced", parammodeadvanced.get())
                Lux.TypedControls.Bool("advanced", showadvanced, "Advanced", "Show advanced options", 0.6)
                # Help toggle
                showhelp = Lux.Property(Lux.scene, "pixelfilter.showhelp", "false")
                Lux.TypedControls.Help("help", showhelp, "Help", "Show Help Information", 0.4)
        
                if filtertype.get() == "box":
                    if showadvanced.get()=="true":
                        # Advanced parameters
                        if gui: gui.newline()
                        str += Lux.TypedControls.Float("xwidth", Lux.Property(Lux.scene, "pixelfilter.box.xwidth", 0.5), 0.0, 10.0, "x-width", "Width of the filter in the x direction")
                        str += Lux.TypedControls.Float("ywidth", Lux.Property(Lux.scene, "pixelfilter.box.ywidth", 0.5), 0.0, 10.0, "y-width", "Width of the filter in the y direction")
                if filtertype.get() == "gaussian":
                    if showadvanced.get()=="true":
                        # Advanced parameters
                        if gui: gui.newline()
                        str += Lux.TypedControls.Float("xwidth", Lux.Property(Lux.scene, "pixelfilter.gaussian.xwidth", 2.0), 0.0, 10.0, "x-width", "Width of the filter in the x direction")
                        str += Lux.TypedControls.Float("ywidth", Lux.Property(Lux.scene, "pixelfilter.gaussian.ywidth", 2.0), 0.0, 10.0, "y-width", "Width of the filter in the y direction")
                        if gui: gui.newline()
                        str += Lux.TypedControls.Float("alpha", Lux.Property(Lux.scene, "pixelfilter.gaussian.alpha", 2.0), 0.0, 10.0, "alpha", "Gaussian rate of falloff. Lower values give blurrier images")
                if filtertype.get() == "mitchell":
                    if showadvanced.get()=="false":
                        # Default parameters
                        if gui: gui.newline("", 8, 0, None, [0.4,0.4,0.4])
                        slidval = Lux.Property(Lux.scene, "pixelfilter.mitchell.sharp", 0.33)
                        Lux.TypedControls.Float("sharpness", slidval, 0.0, 1.0, "sharpness", "Specify amount between blurred (left) and sharp/ringed (right)", 2.0, 1)
                        # rule: B + 2*c = 1.0
                        C = slidval.getFloat() * 0.5
                        B = 1.0 - slidval.getFloat()
                        str += "\n   \"float B\" [%f]"%(B)
                        str += "\n   \"float C\" [%f]"%(C)
        
                    if showadvanced.get()=="true":
                        # Advanced parameters
                        if gui: gui.newline()
                        str += Lux.TypedControls.Float("xwidth", Lux.Property(Lux.scene, "pixelfilter.mitchell.xwidth", 2.0), 0.0, 10.0, "x-width", "Width of the filter in the x direction")
                        str += Lux.TypedControls.Float("ywidth", Lux.Property(Lux.scene, "pixelfilter.mitchell.ywidth", 2.0), 0.0, 10.0, "y-width", "Width of the filter in the y direction")
                        if gui: gui.newline()
            
                        optmode = Lux.Property(Lux.scene, "pixelfilter.mitchell.optmode", "slider")
                        Lux.TypedControls.Option("optmode", optmode, ["slider", "preset", "manual"], "Mode", "Mode of configuration", 0.5)
            
                        if(optmode.get() == "slider"):
                            slidval = Lux.Property(Lux.scene, "pixelfilter.mitchell.sharp", 0.33)
                            Lux.TypedControls.Float("sharpness", slidval, 0.0, 1.0, "sharpness", "Specify amount between blurred (left) and sharp/ringed (right)", 1.5, 1)
                            # rule: B + 2*c = 1.0
                            C = slidval.getFloat() * 0.5
                            B = 1.0 - slidval.getFloat()
                            str += "\n   \"float B\" [%f]"%(B)
                            str += "\n   \"float C\" [%f]"%(C)
                        elif(optmode.get() == "preset"):
                            print "not implemented"
                        else:
                            str += Lux.TypedControls.Float("B", Lux.Property(Lux.scene, "pixelfilter.mitchell.B", 0.3333), 0.0, 1.0, "B", "Specify the shape of the Mitchell filter. Often best result is when B + 2C = 1", 0.75)
                            str += Lux.TypedControls.Float("C", Lux.Property(Lux.scene, "pixelfilter.mitchell.C", 0.3333), 0.0, 1.0, "C", "Specify the shape of the Mitchell filter. Often best result is when B + 2C = 1", 0.75)
        
                if filtertype.get() == "sinc":
                    if showadvanced.get()=="true":
                        # Advanced parameters
                        if gui: gui.newline()
                        str += Lux.TypedControls.Float("xwidth", Lux.Property(Lux.scene, "pixelfilter.sinc.xwidth", 4.0), 0.0, 10.0, "x-width", "Width of the filter in the x direction")
                        str += Lux.TypedControls.Float("ywidth", Lux.Property(Lux.scene, "pixelfilter.sinc.ywidth", 4.0), 0.0, 10.0, "y-width", "Width of the filter in the y direction")
                        if gui: gui.newline()
                        str += Lux.TypedControls.Float("tau", Lux.Property(Lux.scene, "pixelfilter.sinc.tau", 3.0), 0.0, 10.0, "tau", "Permitted number of cycles of the sinc function before it is clamped to zero")
                if filtertype.get() == "triangle":
                    if showadvanced.get()=="true":
                        # Advanced parameters
                        if gui: gui.newline()
                        str += Lux.TypedControls.Float("xwidth", Lux.Property(Lux.scene, "pixelfilter.triangle.xwidth", 2.0), 0.0, 10.0, "x-width", "Width of the filter in the x direction")
                        str += Lux.TypedControls.Float("ywidth", Lux.Property(Lux.scene, "pixelfilter.triangle.ywidth", 2.0), 0.0, 10.0, "y-width", "Width of the filter in the y direction")
            return str
                    
        @staticmethod
        def Sampler(): #scn, gui=None):
            global icon_c_sampler, icon_help
            str = ""
            if Lux.scene:
                samplertype = Lux.Property(Lux.scene, "sampler.type", "metropolis")
                str = Lux.TypedControls.Identifier("Sampler", samplertype, ["metropolis", "erpt", "lowdiscrepancy", "random"], "SAMPLER", "select sampler type", icon_c_sampler)
        
                # Advanced toggle
                parammodeadvanced = Lux.Property(Lux.scene, "parammodeadvanced", "false")
                showadvanced = Lux.Property(Lux.scene, "sampler.showadvanced", parammodeadvanced.get())
                Lux.TypedControls.Bool("advanced", showadvanced, "Advanced", "Show advanced options", 0.6)
                # Help toggle
                showhelp = Lux.Property(Lux.scene, "sampler.showhelp", "false")
                Lux.TypedControls.Help("help", showhelp, "Help", "Show Help Information", 0.4)
        
                if samplertype.get() == "metropolis":
                    if showadvanced.get()=="false":
                        # Default parameters
                        if gui: gui.newline("  Mutation:", 8, 0, None, [0.4,0.4,0.4])
                        strength = Lux.Property(Lux.scene, "sampler.metro.strength", 0.6)
                        Lux.TypedControls.Float("strength", strength, 0.0, 1.0, "strength", "Mutation Strength (lmprob = 1.0-strength)", 2.0, 1)
                        v = 1.0 - strength.get()
                        str += "\n   \"float largemutationprob\" [%f]"%v
                    if showadvanced.get()=="true":
                        # Advanced parameters
                        if gui: gui.newline("  Mutation:")
                        str += Lux.TypedControls.Float("largemutationprob", Lux.Property(Lux.scene, "sampler.metro.lmprob", 0.4), 0.0, 1.0, "LM.prob.", "Probability of generating a large sample (mutation)")
                        str += Lux.TypedControls.Int("maxconsecrejects", Lux.Property(Lux.scene, "sampler.metro.maxrejects", 512), 0, 32768, "max.rejects", "number of consecutive rejects before a new mutation is forced")
                        if gui: gui.newline("  Screen:")
                        str += Lux.TypedControls.Int("initsamples", Lux.Property(Lux.scene, "sampler.metro.initsamples", 262144), 1, 1000000, "initsamples", "")
                        str += Lux.TypedControls.Int("stratawidth", Lux.Property(Lux.scene, "sampler.metro.stratawidth", 256), 1, 32768, "stratawidth", "The number of x/y strata for stratified sampling of seeds")
                        str += Lux.TypedControls.Bool("usevariance",Lux.Property(Lux.scene, "sampler.metro.usevariance", "false"), "usevariance", "Accept based on variance", 1.0)
        
                    if showhelp.get()=="true":
                        if gui: gui.newline("  Description:", 8, 0, icon_help, [0.4,0.5,0.56])
                        r = gui.getRect(2,1); Blender.BGL.glRasterPos2i(r[0],r[1]+5) 
                        Blender.Draw.Text("A Metropolis-Hastings mutating sampler which implements MLT", 'small')    
        
                if samplertype.get() == "erpt":
                    str += Lux.TypedControls.Int("initsamples", Lux.Property(Lux.scene, "sampler.erpt.initsamples", 100000), 1, 1000000, "initsamples", "")
                    if gui: gui.newline("  Mutation:")
                    str += Lux.TypedControls.Int("chainlength", Lux.Property(Lux.scene, "sampler.erpt.chainlength", 512), 1, 32768, "chainlength", "The number of mutations from a given seed")
                    if gui: gui.newline()
                    str += Lux.TypedControls.Int("stratawidth", Lux.Property(Lux.scene, "sampler.erpt.stratawidth", 256), 1, 32768, "stratawidth", "The number of x/y strata for stratified sampling of seeds")
        
                if samplertype.get() == "lowdiscrepancy":
                    if gui: gui.newline("  PixelSampler:")
                    str += Lux.TypedControls.Option("pixelsampler", Lux.Property(Lux.scene, "sampler.lowdisc.pixelsampler", "lowdiscrepancy"), ["linear", "tile", "random", "vegas","lowdiscrepancy","hilbert"], "pixel-sampler", "select pixel-sampler")
                    str += Lux.TypedControls.Int("pixelsamples", Lux.Property(Lux.scene, "sampler.lowdisc.pixelsamples", 4), 1, 2048, "samples", "Average number of samples taken per pixel. More samples create a higher quality image at the cost of render time")
        
                if samplertype.get() == "random":
                    if gui: gui.newline("  PixelSampler:")
                    str += Lux.TypedControls.Option("pixelsampler", Lux.Property(Lux.scene, "sampler.random.pixelsampler", "vegas"), ["linear", "tile", "random", "vegas","lowdiscrepancy","hilbert"], "pixel-sampler", "select pixel-sampler")
                    if gui: gui.newline()
                    str += Lux.TypedControls.Int("xsamples", Lux.Property(Lux.scene, "sampler.random.xsamples", 2), 1, 512, "xsamples", "Allows you to specify how many samples per pixel are taking in the x direction")
                    str += Lux.TypedControls.Int("ysamples", Lux.Property(Lux.scene, "sampler.random.ysamples", 2), 1, 512, "ysamples", "Allows you to specify how many samples per pixel are taking in the y direction")
            return str            
        
        @staticmethod
        def SurfaceIntegrator(): #scn, gui=None):
            global icon_c_integrator
            str = ""
            if Lux.scene:
                integratortype = Lux.Property(Lux.scene, "sintegrator.type", "bidirectional")
                str = Lux.TypedControls.Identifier("SurfaceIntegrator", integratortype, ["directlighting", "path", "bidirectional", "exphotonmap", "distributedpath" ], "INTEGRATOR", "select surface integrator type", icon_c_integrator)
        
                # Advanced toggle
                parammodeadvanced = Lux.Property(Lux.scene, "parammodeadvanced", "false")
                showadvanced = Lux.Property(Lux.scene, "sintegrator.showadvanced", parammodeadvanced.get())
                Lux.TypedControls.Bool("advanced", showadvanced, "Advanced", "Show advanced options", 0.6)
                # Help toggle
                showhelp = Lux.Property(Lux.scene, "sintegrator.showhelp", "false")
                Lux.TypedControls.Help("help", showhelp, "Help", "Show Help Information",  0.4)
        
                if integratortype.get() == "directlighting":
                    if showadvanced.get()=="false":
                        # Default parameters
                        if gui: gui.newline("  Depth:", 8, 0, None, [0.4,0.4,0.4])
                        str += Lux.TypedControls.Int("maxdepth", Lux.Property(Lux.scene, "sintegrator.dlighting.maxdepth", 8), 0, 2048, "bounces", "The maximum recursion depth for ray casting", 2.0)
        
                    if showadvanced.get()=="true":
                        # Advanced parameters
                        str += Lux.TypedControls.Option("strategy", Lux.Property(Lux.scene, "sintegrator.dlighting.strategy", "auto"), ["one", "all", "auto"], "strategy", "select directlighting strategy")
                        if gui: gui.newline("  Depth:")
                        str += Lux.TypedControls.Int("maxdepth", Lux.Property(Lux.scene, "sintegrator.dlighting.maxdepth", 8), 0, 2048, "max-depth", "The maximum recursion depth for ray casting")
                        if gui: gui.newline()
        
                if integratortype.get() == "path":
                    if showadvanced.get()=="false":
                        # Default parameters
                        if gui: gui.newline("  Depth:", 8, 0, None, [0.4,0.4,0.4])
                        str += Lux.TypedControls.Int("maxdepth", Lux.Property(Lux.scene, "sintegrator.path.maxdepth", 10), 0, 2048, "bounces", "The maximum recursion depth for ray casting", 2.0)
        
                    if showadvanced.get()=="true":
                        # Advanced parameters
                        if gui: gui.newline("  Depth:")
                        str += Lux.TypedControls.Int("maxdepth", Lux.Property(Lux.scene, "sintegrator.path.maxdepth", 10), 0, 2048, "maxdepth", "The maximum recursion depth for ray casting")
                        str += Lux.TypedControls.Option("strategy", Lux.Property(Lux.scene, "sintegrator.path.strategy", "auto"), ["one", "all", "auto"], "strategy", "select directlighting strategy")
                        if gui: gui.newline("  RR:")
                        rrstrat = Lux.Property(Lux.scene, "sintegrator.path.rrstrategy", "efficiency")
                        str += Lux.TypedControls.Option("rrstrategy", rrstrat, ["efficiency", "probability", "none"], "RR strategy", "select Russian Roulette path termination strategy")
                        if rrstrat.get() == "probability":
                            str += Lux.TypedControls.Float("rrcontinueprob", Lux.Property(Lux.scene, "sintegrator.path.rrcontinueprob", 0.65), 0.0, 1.0, "rrprob", "Russian roulette continue probability")
        
                if integratortype.get() == "bidirectional":
                    if showadvanced.get()=="false":
                        # Default parameters
                        if gui: gui.newline("  Depth:", 8, 0, None, [0.4,0.4,0.4])
                        bounces = Lux.Property(Lux.scene, "sintegrator.bidir.bounces", 10)
                        Lux.TypedControls.Int("bounces", bounces, 5, 32, "bounces", "The maximum recursion depth for ray casting (in both directions)", 2.0)
                        str += "\n   \"integer eyedepth\" [%i]\n"%bounces.get()
                        str += "   \"integer lightdepth\" [%i]"%bounces.get()
        
                    if showadvanced.get()=="true":
                        # Advanced parameters
                        if gui: gui.newline("  Depth:")
                        str += Lux.TypedControls.Int("eyedepth", Lux.Property(Lux.scene, "sintegrator.bidir.eyedepth", 10), 0, 2048, "eyedepth", "The maximum recursion depth for ray casting")
                        str += Lux.TypedControls.Int("lightdepth", Lux.Property(Lux.scene, "sintegrator.bidir.lightdepth", 10), 0, 2048, "lightdepth", "The maximum recursion depth for light ray casting")
                        str += Lux.TypedControls.Option("strategy", Lux.Property(Lux.scene, "sintegrator.bidir.strategy", "auto"), ["one", "all", "auto"], "strategy", "select directlighting strategy")
        
                if integratortype.get() == "exphotonmap":
                    if gui: gui.newline("  Photons:")
                    str += Lux.TypedControls.Int("indirectphotons", Lux.Property(Lux.scene, "sintegrator.photonmap.idphotons", 200000), 0, 10000000, "indirect", "The number of photons to shoot for indirect lighting during preprocessing of the photon map")
                    str += Lux.TypedControls.Int("maxdirectphotons", Lux.Property(Lux.scene, "sintegrator.photonmap.maxdphotons", 1000000), 0, 10000000, "maxdirect", "The maximum number of photons to shoot for direct lighting during preprocessing of the photon map")
                    str += Lux.TypedControls.Int("causticphotons", Lux.Property(Lux.scene, "sintegrator.photonmap.cphotons", 20000), 0, 10000000, "caustic", "The number of photons to shoot for caustics during preprocessing of the photon map")
                    if gui: gui.newline("  Render:")
                    str += Lux.TypedControls.Option("strategy", Lux.Property(Lux.scene, "sintegrator.photonmap.strategy", "auto"), ["one", "all", "auto"], "strategy", "select directlighting strategy")
                    str += Lux.TypedControls.Int("maxdepth", Lux.Property(Lux.scene, "sintegrator.photonmap.maxdepth", 6), 1, 1024, "maxdepth", "The maximum recursion depth of specular reflection and refraction")
                    str += Lux.TypedControls.Float("maxdist", Lux.Property(Lux.scene, "sintegrator.photonmap.maxdist", 0.1), 0.0, 10.0, "maxdist", "The maximum distance between a point being shaded and a photon that can contribute to that point")
                    str += Lux.TypedControls.Int("nused", Lux.Property(Lux.scene, "sintegrator.photonmap.nused", 50), 0, 1000000, "nused", "The number of photons to use in density estimation")
                    str += Lux.TypedControls.Option("renderingmode", Lux.Property(Lux.scene, "sintegrator.photonmap.renderingmode", "directlighting"), ["directlighting", "path"], "renderingmode", "select rendering mode")
        
                    if gui: gui.newline("  FinalGather:")
                    fg = Lux.Property(Lux.scene, "sintegrator.photonmap.fgather", "true")
                    str += Lux.TypedControls.Bool("finalgather", fg, "finalgather", "Enable use of final gather during rendering")
                    if fg.get() == "true":
                        str += Lux.TypedControls.Int("finalgathersamples", Lux.Property(Lux.scene, "sintegrator.photonmap.fgathers", 32), 1, 1024, "samples", "The number of finalgather samples to take per pixel during rendering")
                        rrstrat = Lux.Property(Lux.scene, "sintegrator.photonmap.gatherrrstrategy", "efficiency")
                        str += Lux.TypedControls.Option("gatherrrstrategy", rrstrat, ["efficiency", "probability", "none"], "RR strategy", "select Russian Roulette gather termination strategy")
                        str += Lux.TypedControls.Float("gatherangle", Lux.Property(Lux.scene, "sintegrator.photonmap.gangle", 10.0), 0.0, 360.0, "gatherangle", "Angle for final gather")
                        str += Lux.TypedControls.Float("gatherrrcontinueprob", Lux.Property(Lux.scene, "sintegrator.photonmap.gatherrrcontinueprob", 0.65), 0.0, 1.0, "rrcontinueprob", "Probability for russian roulette particle tracing termination")
        
                if integratortype.get() == "distributedpath":
                    str += Lux.TypedControls.Option("strategy", Lux.Property(Lux.scene, "sintegrator.distributedpath.strategy", "auto"), ["one", "all", "auto"], "strategy", "select directlighting strategy")
                    if gui: gui.newline("  Direct:")
                    str += Lux.TypedControls.Bool("directsampleall",Lux.Property(Lux.scene, "sintegrator.distributedpath.directsampleall", "true"), "Direct ALL", "Include diffuse direct light sample at first vertex", 0.75)
                    str += Lux.TypedControls.Int("directsamples", Lux.Property(Lux.scene, "sintegrator.distributedpath.directsamples", 1), 0, 1024, "s", "The number of direct light samples to take at the eye vertex", 0.25)
                    str += Lux.TypedControls.Bool("indirectsampleall",Lux.Property(Lux.scene, "sintegrator.distributedpath.indirectsampleall", "false"), "Indirect ALL", "Include diffuse direct light sample at first vertex", 0.75)
                    str += Lux.TypedControls.Int("indirectsamples", Lux.Property(Lux.scene, "sintegrator.distributedpath.indirectsamples", 1), 0, 1024, "s", "The number of direct light samples to take at the remaining vertices", 0.25)
                    if gui: gui.newline("  Diffuse:")
                    str += Lux.TypedControls.Int("diffusereflectdepth", Lux.Property(Lux.scene, "sintegrator.distributedpath.diffusereflectdepth", 3), 0, 2048, "Reflect", "The maximum recursion depth for diffuse reflection ray casting", 0.5)
                    str += Lux.TypedControls.Int("diffusereflectsamples", Lux.Property(Lux.scene, "sintegrator.distributedpath.diffusereflectsamples", 1), 0, 1024, "s", "The number of diffuse reflection samples to take at the eye vertex", 0.25)
                    str += Lux.TypedControls.Int("diffuserefractdepth", Lux.Property(Lux.scene, "sintegrator.distributedpath.diffuserefractdepth", 5), 0, 2048, "Refract", "The maximum recursion depth for diffuse refraction ray casting", 0.5)
                    str += Lux.TypedControls.Int("diffuserefractsamples", Lux.Property(Lux.scene, "sintegrator.distributedpath.diffuserefractsamples", 1), 0, 1024, "s", "The number of diffuse refraction samples to take at the eye vertex", 0.25)
                    str += Lux.TypedControls.Bool("directdiffuse",Lux.Property(Lux.scene, "sintegrator.distributedpath.directdiffuse", "true"), "DL", "Include diffuse direct light sample at first vertex", 0.25)
                    str += Lux.TypedControls.Bool("indirectdiffuse",Lux.Property(Lux.scene, "sintegrator.distributedpath.indirectdiffuse", "true"), "IDL", "Include diffuse indirect light sample at first vertex", 0.25)
                    if gui: gui.newline("  Glossy:")
                    str += Lux.TypedControls.Int("glossyreflectdepth", Lux.Property(Lux.scene, "sintegrator.distributedpath.glossyreflectdepth", 2), 0, 2048, "Reflect", "The maximum recursion depth for glossy reflection ray casting", 0.5)
                    str += Lux.TypedControls.Int("glossyreflectsamples", Lux.Property(Lux.scene, "sintegrator.distributedpath.glossyreflectsamples", 1), 0, 1024, "s", "The number of glossy reflection samples to take at the eye vertex", 0.25)
                    str += Lux.TypedControls.Int("glossyrefractdepth", Lux.Property(Lux.scene, "sintegrator.distributedpath.glossyrefractdepth", 5), 0, 2048, "Refract", "The maximum recursion depth for glossy refraction ray casting", 0.5)
                    str += Lux.TypedControls.Int("glossyrefractsamples", Lux.Property(Lux.scene, "sintegrator.distributedpath.glossyrefractsamples", 1), 0, 1024, "s", "The number of glossy refraction samples to take at the eye vertex", 0.25)
                    str += Lux.TypedControls.Bool("directglossy",Lux.Property(Lux.scene, "sintegrator.distributedpath.directglossy", "true"), "DL", "Include glossy direct light sample at first vertex", 0.25)
                    str += Lux.TypedControls.Bool("indirectglossy",Lux.Property(Lux.scene, "sintegrator.distributedpath.indirectglossy", "true"), "IDL", "Include glossy indirect light sample at first vertex", 0.25)
                    if gui: gui.newline("  Specular:")
                    str += Lux.TypedControls.Int("specularreflectdepth", Lux.Property(Lux.scene, "sintegrator.distributedpath.specularreflectdepth", 3), 0, 2048, "Reflect", "The maximum recursion depth for specular reflection ray casting", 1.0)
                    str += Lux.TypedControls.Int("specularrefractdepth", Lux.Property(Lux.scene, "sintegrator.distributedpath.specularrefractdepth", 5), 0, 2048, "Refract", "The maximum recursion depth for specular refraction ray casting", 1.0)
                    if gui: gui.newline("  Caustics:")
                    str += Lux.TypedControls.Bool("causticsondiffuse",Lux.Property(Lux.scene, "sintegrator.distributedpath.causticsondiffuse", "false"), "Caustics on Diffuse", "Enable caustics on diffuse surfaces (warning: might generate bright pixels)", 1.0)
                    str += Lux.TypedControls.Bool("causticsonglossy",Lux.Property(Lux.scene, "sintegrator.distributedpath.causticsonglossy", "true"), "Caustics on Glossy", "Enable caustics on glossy surfaces (warning: might generate bright pixels)", 1.0)
        
            return str
        
        @staticmethod
        def VolumeIntegrator(): #scn, gui=None):
            global icon_c_volumeintegrator
            str = ""
            if Lux.scene:
                integratortype = Lux.Property(Lux.scene, "vintegrator.type", "single")
                str = Lux.TypedControls.Identifier("VolumeIntegrator", integratortype, ["emission", "single"], "VOLUME INT", "select volume integrator type", icon_c_volumeintegrator)
                if integratortype.get() == "emission":
                    str += Lux.TypedControls.Float("stepsize", Lux.Property(Lux.scene, "vintegrator.emission.stepsize", 1.0), 0.0, 100.0, "stepsize", "Stepsize for volumes")
                if integratortype.get() == "single":
                    str += Lux.TypedControls.Float("stepsize", Lux.Property(Lux.scene, "vintegrator.emission.stepsize", 1.0), 0.0, 100.0, "stepsize", "Stepsize for volumes")
            return str
        
        @staticmethod
        def Environment(): #scn, gui=None):
            global icon_c_environment
            str = ""
            if Lux.scene:
                envtype = Lux.Property(Lux.scene, "env.type", "infinite")
                lsstr = Lux.TypedControls.Identifier("LightSource", envtype, ["none", "infinite", "sunsky"], "ENVIRONMENT", "select environment light type", icon_c_environment)
                if gui: gui.newline()
                str = ""
                if envtype.get() != "none":
                    if envtype.get() in ["infinite", "sunsky"]:
                        rot = Lux.Property(Lux.scene, "env.rotation", 0.0)
                        Lux.TypedControls.Float("rotation", rot, 0.0, 360.0, "rotation", "environment rotation")
                        if rot.get() != 0:
                            str += "\tRotate %d 0 0 1\n"%(rot.get())
                    str += "\t"+lsstr
        
                    infinitehassun = 0
                    if envtype.get() == "infinite":
                        mapping = Lux.Property(Lux.scene, "env.infinite.mapping", "latlong")
                        mappings = ["latlong","angular","vcross"]
                        mapstr = Lux.TypedControls.Option("mapping", mapping, mappings, "mapping", "Select mapping type", 1.0)
                        map = Lux.Property(Lux.scene, "env.infinite.mapname", "")
                        mapstr += Lux.TypedControls.File("mapname", map, "map-file", "filename of the environment map", 2.0)
                        mapstr += Lux.TypedControls.Float("gamma", Lux.Property(Lux.scene, "env.infinite.gamma", 1.0), 0.0, 6.0, "gamma", "", 1.0)
                        
                        if map.get() != "":
                            str += mapstr
                        else:
                            try:
                                worldcolor = Blender.World.Get('World').getHor()
                                str += "\n   \"color L\" [%g %g %g]" %(worldcolor[0], worldcolor[1], worldcolor[2])
                            except: pass
        
                        str += Lux.TypedControls.Float("gain", Lux.Property(Lux.scene, "env.infinite.gain", 1000.0), 0.0, 1000.0, "gain", "", 1.0)
        
                        infinitesun = Lux.Property(Lux.scene, "env.infinite.hassun", "false")
                        Lux.TypedControls.Bool("infinitesun", infinitesun, "Sun Component", "Add Sunlight Component", 2.0)
                        if(infinitesun.get() == "true"):
                            str += "\n\tLightSource \"sun\" "
                            infinitehassun = 1
        
        
                    if envtype.get() == "sunsky" or infinitehassun == 1:
                        sun = None
                        for obj in Lux.scene.objects:
                            if (obj.getType() == "Lamp") and ((obj.Layers & Lux.scene.Layers) > 0):
                                if obj.getData(mesh=1).getType() == 1: # sun object # data
                                    sun = obj
                        if sun:
                            str += Lux.TypedControls.Float("relsize", Lux.Property(Lux.scene, "env.sunsky.relisze", 1.0), 0.0, 100.0, "rel.size", "relative sun size")
                            invmatrix = Mathutils.Matrix(sun.getInverseMatrix())
                            str += "\n   \"vector sundir\" [%f %f %f]\n" %(invmatrix[0][2], invmatrix[1][2], invmatrix[2][2])
                            str += Lux.TypedControls.Float("gain", Lux.Property(Lux.scene, "env.sunsky.gain", 1.0), 0.0, 1000.0, "gain", "Sky gain")
                            str += Lux.TypedControls.Float("turbidity", Lux.Property(Lux.scene, "env.sunsky.turbidity", 2.2), 2.0, 50.0, "turbidity", "Sky turbidity")
                        else:
                            if gui:
                                gui.newline(); r = gui.getRect(2,1); Blender.BGL.glRasterPos2i(r[0],r[1]+5) 
                                Blender.Draw.Text("create a blender Sun Lamp")
        
        
                    str += "\n"
                if gui: gui.newline("GLOBAL:", 8, 0, None, [0.75,0.5,0.25])
                Lux.TypedControls.Float("scale", Lux.Property(Lux.scene, "global.scale", 1.0), 0.0, 10.0, "scale", "global world scale")
                
            return str
        
        @staticmethod
        def Accelerator(): #scn, gui=None):
            str = ""
            if Lux.scene:
                acceltype = Lux.Property(Lux.scene, "accelerator.type", "tabreckdtree")
                str = Lux.TypedControls.Identifier("Accelerator", acceltype, ["none", "tabreckdtree", "grid", "bvh"], "ACCEL", "select accelerator type")
                if acceltype.get() == "tabreckdtree":
                    if gui: gui.newline()
                    str += Lux.TypedControls.Int("intersectcost", Lux.Property(Lux.scene, "accelerator.kdtree.interscost", 80), 0, 1000, "inters.cost", "specifies how expensive ray-object intersections are")
                    str += Lux.TypedControls.Int("traversalcost", Lux.Property(Lux.scene, "accelerator.kdtree.travcost", 1), 0, 1000, "trav.cost", "specifies how expensive traversing a ray through the kdtree is")
                    if gui: gui.newline()
                    str += Lux.TypedControls.Float("emptybonus", Lux.Property(Lux.scene, "accelerator.kdtree.emptybonus", 0.2), 0.0, 100.0, "empty.b", "promotes kd-tree nodes that represent empty space")
                    if gui: gui.newline()
                    str += Lux.TypedControls.Int("maxprims", Lux.Property(Lux.scene, "accelerator.kdtree.maxprims", 1), 0, 1000, "maxprims", "maximum number of primitives in a kdtree volume before further splitting of the volume occurs")
                    str += Lux.TypedControls.Int("maxdepth", Lux.Property(Lux.scene, "accelerator.kdtree.maxdepth", -1), -1, 100, "maxdepth", "If positive, the maximum depth of the tree. If negative this value is set automatically")
                if acceltype.get() == "unsafekdtree":
                    if gui: gui.newline()
                    str += Lux.TypedControls.Int("intersectcost", Lux.Property(Lux.scene, "accelerator.kdtree.interscost", 80), 0, 1000, "inters.cost", "specifies how expensive ray-object intersections are")
                    str += Lux.TypedControls.Int("traversalcost", Lux.Property(Lux.scene, "accelerator.kdtree.travcost", 1), 0, 1000, "trav.cost", "specifies how expensive traversing a ray through the kdtree is")
                    if gui: gui.newline()
                    str += Lux.TypedControls.Float("emptybonus", Lux.Property(Lux.scene, "accelerator.kdtree.emptybonus", 0.2), 0.0, 100.0, "empty.b", "promotes kd-tree nodes that represent empty space")
                    if gui: gui.newline()
                    str += Lux.TypedControls.Int("maxprims", Lux.Property(Lux.scene, "accelerator.kdtree.maxprims", 1), 0, 1000, "maxprims", "maximum number of primitives in a kdtree volume before further splitting of the volume occurs")
                    str += Lux.TypedControls.Int("maxdepth", Lux.Property(Lux.scene, "accelerator.kdtree.maxdepth", -1), -1, 100, "maxdepth", "If positive, the maximum depth of the tree. If negative this value is set automatically")
                if acceltype.get() == "grid":
                    str += Lux.TypedControls.Bool("refineimmediately", Lux.Property(Lux.scene, "accelerator.grid.refine", "false"), "refine immediately", "Makes the primitive intersectable as soon as it is added to the grid")
            return str
        
        @staticmethod
        def System(): #scn, gui=None):
            if Lux.scene:
                if gui: gui.newline("PATHS:", 10)
                lp = Lux.Property(Lux.scene, "lux", "")
                lp.set(Blender.sys.dirname(lp.get())+os.sep)
                Lux.TypedControls.Path("LUX dir", lp, "lux binary dir", "Lux installation path", 2.0)
        
        #        Lux.Types.File("GUI filename", Lux.Prop(Lux.scene, "lux", ""), "lux-file", "filename and path of the lux GUI executable", 2.0)
        #        Lux.Types.File("Console filename", Lux.Prop(Lux.scene, "luxconsole", ""), "lux-file-console", "filename and path of the lux console executable", 2.0)
                if gui: gui.newline()
                Lux.TypedControls.File("datadir", Lux.Property(Lux.scene, "datadir", ""), "default out dir", "default.lxs save path", 2.0)
        
                if gui: gui.newline("PRIORITY:", 10)
                luxnice = Lux.Property(Lux.scene, "luxnice", 0)
                if osys.platform=="win32":
                    r = gui.getRect(2, 1)
                    Blender.Draw.Menu("priority%t|abovenormal%x-10|normal%x0|belownormal%x10|low%x19", Lux.Events.LuxGui, r[0], r[1], r[2], r[3], luxnice.get(), "", lambda e,v: luxnice.set(v))
                else: Lux.TypedControls.Int("nice", luxnice, -20, 19, "nice", "nice value. Range goes from -20 (highest priority) to 19 (lowest)")  
        
                if gui: gui.newline("THREADS:", 10)
                autothreads = Lux.Property(Lux.scene, "autothreads", "true")
                Lux.TypedControls.Bool("autothreads", autothreads, "Auto Detect", "Automatically use all available processors", 1.0)
                if autothreads.get()=="false":
                    Lux.TypedControls.Int("threads", Lux.Property(Lux.scene, "threads", 1), 1, 100, "threads", "number of threads used for rendering", 1.0)
        
                if gui: gui.newline("ANIM:", 10)
                useparamkeys = Lux.Property(Lux.scene, "useparamkeys", "false")
                Lux.TypedControls.Bool("useparamkeys", useparamkeys, "Enable Parameter IPO Keyframing", "Enables keyframing of luxblend parameters", 2.0)
        
                if gui: gui.newline("PARAMS:", 10)
                parammodeadvanced = Lux.Property(Lux.scene, "parammodeadvanced", "false")
                Lux.TypedControls.Bool("parammodeadvanced", parammodeadvanced, "Default Advanced Parameters", "Always use advanced parameters by default", 2.0)
        
                if gui: gui.newline("PREVIEW:", 10)
                qs = ["low","medium","high","very high"]
                defprevmat = Lux.Property(Lux.scene, "defprevmat", "high")
                Lux.TypedControls.Option("defprevmat", defprevmat, qs, "Materials", "Select default preview quality in material editor for materials", 1.0)
        
                if gui: gui.newline("GAMMA:", 10)
                Lux.TypedControls.Bool("RGC", Lux.Property(Lux.scene, "RGC", "true"), "RGC", "use reverse gamma correction")
                Lux.TypedControls.Bool("ColClamp", Lux.Property(Lux.scene, "colorclamp", "false"), "ColClamp", "clamp all colors to 0.0-0.9")
                if gui: gui.newline("MESH:", 10)
                Lux.TypedControls.Bool("mesh_optimizing", Lux.Property(Lux.scene, "mesh_optimizing", "true"), "optimize meshes", "Optimize meshes during export", 2.0)
                #Lux.Types.Int("trianglemesh thr", Lux.Prop(Lux.scene, "trianglemesh_thr", 0), 0, 10000000, "trianglemesh threshold", "Vertex threshold for exporting (wald) trianglemesh object(s)", 2.0)
                #if gui: gui.newline()
                #Lux.Types.Int("barytrianglemesh thr", Lux.Prop(Lux.scene, "barytrianglemesh_thr", 300000), 0, 100000000, "barytrianglemesh threshold", "Vertex threshold for exporting barytrianglemesh object(s) (slower but uses less memory)", 2.0)
                if gui: gui.newline("INSTANCING:", 10)
                Lux.TypedControls.Int("instancing_threshold", Lux.Property(Lux.scene, "instancing_threshold", 2), 0, 1000000, "object instanding threshold", "Threshold to created instanced objects", 2.0)
    
        @staticmethod
        def Texture(name, parentkey, type, default, min, max, caption, hint, mat, gui, matlevel, texlevel=0, lightsource=0, overrideicon=""):
            global icon_tex, icon_texcol, icon_texmix, icon_texmixcol, icon_texparam, icon_spectex
            def c(t1, t2):
                return (t1[0]+t2[0], t1[1]+t2[1])
            def alternativedefault(type, default):
                if type=="float": return 0.0
                else: return "0.0 0.0 0.0"
            level = matlevel + texlevel
            keyname = "%s:%s"%(parentkey, name)
            texname = "%s:%s"%(mat.getName(), keyname)
        #    if gui: gui.newline(caption+":", 0, level)
            if(lightsource == 0):
                if texlevel == 0: texture = Lux.Property(mat, keyname+".texture", "imagemap")
                else: texture = Lux.Property(mat, keyname+".texture", "constant")
            else:
                texture = Lux.Property(mat, keyname+".texture", "blackbody")
        
            textures = ["constant","blackbody","equalenergy", "frequency", "gaussian", "regulardata", "irregulardata", "imagemap","mix","scale","bilerp","uv", "checkerboard","dots","fbm","marble","wrinkled", "windy", "blender_marble", "blender_musgrave", "blender_wood", "blender_clouds", "blender_blend", "blender_distortednoise", "blender_noise", "blender_magic", "blender_stucci", "blender_voronoi", "harlequin"]
        
            if gui:
                if(overrideicon != ""):
                    icon = overrideicon
                else:
                    icon = icon_tex
                    if texture.get() in ["mix", "scale", "checkerboard", "dots"]:
                        if type=="color": icon = icon_texmixcol
                        else: icon = icon_texmix
                    elif texture.get() in ["constant", "blackbody", "equalenergy", "frequency", "gaussian", "regulardata", "irregulardata"]:
                        icon = icon_spectex
                    else:
                        if type=="color": icon = icon_texcol
                        else: icon = icon_tex
                if (texlevel > 0): gui.newline(caption+":", -2, level, icon, scalelist([0.5,0.5,0.5],2.0/(level+2)))
                else: gui.newline("texture:", -2, level, icon, scalelist([0.5,0.5,0.5],2.0/(level+2)))
            Lux.TypedControls.Option("texture", texture, textures, "texture", "", 0.9)
            str = "Texture \"%s\" \"%s\" \"%s\""%(texname, type, texture.get())
        
            if gui: Blender.Draw.PushButton(">", Lux.Events.LuxGui, gui.xmax+gui.h, gui.y-gui.h, gui.h, gui.h, "Menu", lambda e,v: showMatTexMenu(mat,keyname,True))
            if gui: # Draw Texture level Material preview
                luxPreview(mat, parentkey, 1, False, False, name, gui, texlevel, [0.5, 0.5, 0.5])
                # Add an offset for next controls
                #r = gui.getRect(1.0, 1)
                #gui.x += 140
        
            if texture.get() == "constant":
                value = Lux.Property(mat, keyname+".value", default)
                if type == "float": Lux.TypedControls.Float("value", value, min, max, "", "", 1.1)
                elif type == "color": Lux.TypedControls.RGB("value", value, max, "", "", 1.1)
        # direct version
                if type == "color": return ("", " \"%s %s\" [%s]"%(type, name, value.getRGC()))
                return ("", " \"%s %s\" [%s]"%(type, name, value.get()))
        # indirect version
        #        if type == "color": str += " \"%s value\" [%s]"%(type, value.getRGC())
        #        else: str += " \"%s value\" [%s]"%(type, value.get())
        
            if texture.get() == "blackbody":
                if gui:
                    if gui.xmax-gui.x < gui.w: gui.newline()
                    r = gui.getRect(1.0, 1)
                    gui.newline()
                    drawBar(bar_blackbody, gui.xmax-gui.w-7, r[1])
                str += Lux.TypedControls.Float("temperature", Lux.Property(mat, keyname+".bbtemp", 6500.0), 1000.0, 10000.0, "temperature", "Black Body temperature in degrees Kelvin", 2.0, 1)
        
            if texture.get() == "equalenergy":
                if gui:
                    if gui.xmax-gui.x < gui.w: gui.newline()
                    r = gui.getRect(1.0, 1)
                    gui.newline()
                    drawBar(bar_equalenergy, gui.xmax-gui.w-7, r[1])
                str += Lux.TypedControls.Float("energy", Lux.Property(mat, keyname+".energy", 1.0), 0.0, 1.0, "energy", "Energy of each spectral band", 2.0, 1)
        
            if texture.get() == "frequency":
                str += Lux.TypedControls.Float("freq", Lux.Property(mat, keyname+".freq", 0.01), 0.03, 100.0, "frequency", "Frequency in nm", 2.0, 1)
                str += Lux.TypedControls.Float("phase", Lux.Property(mat, keyname+".phase", 0.5), 0.0, 1.0, "phase", "Phase", 1.1, 1)
                str += Lux.TypedControls.Float("energy", Lux.Property(mat, keyname+".energy", 1.0), 0.0, 1.0, "energy", "Amount of mean energy", 0.9, 1)
        
            if texture.get() == "gaussian":
                if gui:
                    if gui.xmax-gui.x < gui.w: gui.newline()
                    r = gui.getRect(1.0, 1)
                    gui.newline()
                    drawBar(bar_spectrum, gui.xmax-gui.w-7, r[1])
                str += Lux.TypedControls.Float("wavelength", Lux.Property(mat, keyname+".wavelength", 550.0), 380.0, 720.0, "wavelength", "Mean Wavelength in visible spectrum in nm", 2.0, 1)
                str += Lux.TypedControls.Float("width", Lux.Property(mat, keyname+".width", 50.0), 20.0, 300.0, "width", "Width of gaussian distribution in nm", 1.1, 1)
                str += Lux.TypedControls.Float("energy", Lux.Property(mat, keyname+".energy", 1.0), 0.0, 1.0, "energy", "Amount of mean energy", 0.9, 1)
        
            if texture.get() == "imagemap":
                str += Lux.TypedControls.Option("wrap", Lux.Property(mat, keyname+".wrap", "repeat"), ["repeat","black","clamp"], "repeat", "", 1.1)
                str += Lux.TypedControls.File("filename", Lux.Property(mat, keyname+".filename", ""), "file", "texture file path", 2.0)
                str += Lux.TypedControls.Float("gamma", Lux.Property(mat, keyname+".gamma", texturegamma()), 0.0, 6.0, "gamma", "", 0.75)
                str += Lux.TypedControls.Float("gain", Lux.Property(mat, keyname+".gain", 1.0), 0.0, 10.0, "gain", "", 0.5)
                filttype = Lux.Property(mat, keyname+".filtertype", "bilinear")
                filttypes = ["mipmap_ewa","mipmap_trilinear","bilinear","nearest"]
                str += Lux.TypedControls.Option("filtertype", filttype, filttypes, "filtertype", "Choose the filtering method to use for the image texture", 0.75)
        
                if filttype.get() == "mipmap_ewa" or filttype.get() == "mipmap_trilinear":    
                    str += Lux.TypedControls.Float("maxanisotropy", Lux.Property(mat, keyname+".maxanisotropy", 8.0), 1.0, 512.0, "maxaniso", "", 1.0)
                    str += Lux.TypedControls.Int("discardmipmaps", Lux.Property(mat, keyname+".discardmipmaps", 0), 0, 1, "discardmips", "", 1.0)
        
                str += luxMapping(keyname, mat, gui, level+1)
        
            if texture.get() == "mix":
                (s, l) = c(("", ""), luxTexture("amount", keyname, "float", 0.5, 0.0, 1.0, "amount", "The degree of mix between the two textures", mat, gui, matlevel, texlevel+1, lightsource))
                (s, l) = c((s, l), luxTexture("tex1", keyname, type, default, min, max, "tex1", "", mat, gui, matlevel, texlevel+1, lightsource))
                (s, l) = c((s, l), luxTexture("tex2", keyname, type, alternativedefault(type, default), min, max, "tex2", "", mat, gui, matlevel, texlevel+1, lightsource))
                str = s + str + l
        
            if texture.get() == "scale":
                (s, l) = c(("", ""), luxTexture("tex1", keyname, type, default, min, max, "tex1", "", mat, gui, matlevel, texlevel+1, lightsource))
                (s, l) = c((s, l), luxTexture("tex2", keyname, type, alternativedefault(type, default), min, max, "tex2", "", mat, gui, matlevel, texlevel+1, lightsource))
                str = s + str + l
        
            if texture.get() == "bilerp":
                if type == "float":
                    str += Lux.TypedControls.Float("v00", Lux.Property(mat, keyname+".v00", 0.0), min, max, "v00", "", 1.0)
                    str += Lux.TypedControls.Float("v01", Lux.Property(mat, keyname+".v01", 1.0), min, max, "v01", "", 1.0)
                    if gui: gui.newline("", -2)
                    str += Lux.TypedControls.Float("v10", Lux.Property(mat, keyname+".v10", 0.0), min, max, "v10", "", 1.0)
                    str += Lux.TypedControls.Float("v11", Lux.Property(mat, keyname+".v11", 1.0), min, max, "v11", "", 1.0)
                elif type == "color":
                    if gui: gui.newline("          v00:", -2)
                    str += Lux.TypedControls.RGB("v00", Lux.Property(mat, keyname+".v00", "0.0 0.0 0.0"), max, "v00", "", 2.0)
                    if gui: gui.newline("          v01:", -2)
                    str += Lux.TypedControls.RGB("v01", Lux.Property(mat, keyname+".v01", "1.0 1.0 1.0"), max, "v01", "", 2.0)
                    if gui: gui.newline("          v10:", -2)
                    str += Lux.TypedControls.RGB("v10", Lux.Property(mat, keyname+".v10", "0.0 0.0 0.0"), max, "v10", "", 2.0)
                    if gui: gui.newline("          v11:", -2)
                    str += Lux.TypedControls.RGB("v11", Lux.Property(mat, keyname+".v11", "1.0 1.0 1.0"), max, "v11", "", 2.0)
                str += luxMapping(keyname, mat, gui, level+1)
        
            if texture.get() == "windy":
                str += lux3DMapping(keyname, mat, gui, level+1)
                # this texture has no options 
        
            if texture.get() == "checkerboard":
                dim = Lux.Property(mat, keyname+".dim", 2)
                str += Lux.TypedControls.Int("dimension", dim, 2, 3, "dim", "", 0.5)
                if dim.get() == 2: str += Lux.TypedControls.Option("aamode", Lux.Property(mat, keyname+".aamode", "closedform"), ["closedform","supersample","none"], "aamode", "antialiasing mode", 0.6)
                if gui: gui.newline("", -2)
                (s, l) = c(("", ""), luxTexture("tex1", keyname, type, default, min, max, "tex1", "", mat, gui, matlevel, texlevel+1, lightsource))
                (s, l) = c((s, l), luxTexture("tex2", keyname, type, alternativedefault(type, default), min, max, "tex2", "", mat, gui, matlevel, texlevel+1, lightsource))
                str = s + str + l
                if dim.get() == 2: str += luxMapping(keyname, mat, gui, level+1) 
                if dim.get() == 3: str += lux3DMapping(keyname, mat, gui, level+1)
        
            if texture.get() == "dots":
                (s, l) = c(("", ""), luxTexture("inside", keyname, type, default, min, max, "inside", "", mat, gui, matlevel, texlevel+1, lightsource))
                (s, l) = c((s, l), luxTexture("outside", keyname, type, alternativedefault(type, default), min, max, "outside", "", mat, gui, matlevel, texlevel+1, lightsource))
                str = s + str + l
                str += luxMapping(keyname, mat, gui, level+1)
        
            if texture.get() == "fbm":
                str += Lux.TypedControls.Int("octaves", Lux.Property(mat, keyname+".octaves", 8), 1, 100, "octaves", "", 1.1)
                if gui: gui.newline("", -2)
                str += Lux.TypedControls.Float("roughness", Lux.Property(mat, keyname+".roughness", 0.5), 0.0, 1.0, "roughness", "", 2.0, 1)
                if gui: gui.newline("", -2)
                str += lux3DMapping(keyname, mat, gui, level+1)
        
            if texture.get() == "marble":
                str += Lux.TypedControls.Int("octaves", Lux.Property(mat, keyname+".octaves", 8), 1, 100, "octaves", "", 1.1)
                if gui: gui.newline("", -2)
                str += Lux.TypedControls.Float("roughness", Lux.Property(mat, keyname+".roughness", 0.5), 0.0, 1.0, "roughness", "", 2.0, 1)
                if gui: gui.newline("", -2)
                str += Lux.TypedControls.Float("nscale", Lux.Property(mat, keyname+".nscale", 1.0), 0.0, 100.0, "nscale", "Scaling factor for the noise input", 1.0)
                str += Lux.TypedControls.Float("variation", Lux.Property(mat, keyname+".variation", 0.2), 0.0, 100.0, "variation", "A scaling factor for the noise input function", 1.0)
                if gui: gui.newline("", -2)
                str += lux3DMapping(keyname, mat, gui, level+1)
        
            if texture.get() == "wrinkled":
                str += Lux.TypedControls.Int("octaves", Lux.Property(mat, keyname+".octaves", 8), 1, 100, "octaves", "", 1.1)
                if gui: gui.newline("", -2)
                str += Lux.TypedControls.Float("roughness", Lux.Property(mat, keyname+".roughness", 0.5), 0.0, 1.0, "roughness", "", 2.0, 1)
                if gui: gui.newline("", -2)
                str += lux3DMapping(keyname, mat, gui, level+1)
        
            if texture.get() == "blender_marble":
                if gui: gui.newline("noise:", -2, level+1, icon_texparam)
        
                mtype = Lux.Property(mat, keyname+".mtype", "soft")
                mtypes = ["soft","sharp","sharper"]
                str += Lux.TypedControls.Option("type", mtype, mtypes, "type", "", 0.5)
        
                noisetype = Lux.Property(mat, keyname+".noisetype", "hard_noise")
                noisetypes = ["soft_noise","hard_noise"]
                str += Lux.TypedControls.Option("noisetype", noisetype, noisetypes, "noisetypes", "", 0.75)
        
                str += Lux.TypedControls.Int("noisedepth", Lux.Property(mat, keyname+".noisedepth", 2), 0, 6, "noisedepth", "", 0.75)
        
                str += Lux.TypedControls.Float("noisesize", Lux.Property(mat, keyname+".noisesize", 0.25), 0.0, 2.0, "noisesize", "", 1.0)
                str += Lux.TypedControls.Float("turbulance", Lux.Property(mat, keyname+".turbulance", 5.0), 0.0, 200.0, "turbulance", "", 1.0)
        
                if gui: gui.newline("basis:", -2, level+1, icon_texparam)
                noisebasis2 = Lux.Property(mat, keyname+".noisebasis2", "sin")
                noisebasises2 = ["sin","saw","tri"]
                str += Lux.TypedControls.Option("noisebasis2", noisebasis2, noisebasises2, "noisebasis2", "", 0.7)
        
                noisebasis = Lux.Property(mat, keyname+".noisebasis", "blender_original")
                noisebasises = ["blender_original","original_perlin", "improved_perlin", "voronoi_f1", "voronoi_f2", "voronoi_f3", "voronoi_f4", "voronoi_f2f1", "voronoi_crackle", "cell_noise"]
                str += Lux.TypedControls.Option("noisebasis", noisebasis, noisebasises, "noisebasis", "", 1.3)
        
                if gui: gui.newline("level:", -2, level+1, icon_texparam)
                str += Lux.TypedControls.Float("bright", Lux.Property(mat, keyname+".bright", 1.0), 0.0, 2.0, "bright", "", 1.0)
                str += Lux.TypedControls.Float("contrast", Lux.Property(mat, keyname+".contrast", 1.0), 0.0, 10.0, "contrast", "", 1.0)
        
                (s, l) = c(("", ""), luxTexture("tex1", keyname, type, default, min, max, "tex1", "", mat, gui, matlevel, texlevel+1, lightsource))
                (s, l) = c((s, l), luxTexture("tex2", keyname, type, alternativedefault(type, default), min, max, "tex2", "", mat, gui, matlevel, texlevel+1, lightsource))
                str = s + str + l
        
                str += lux3DMapping(keyname, mat, gui, level+1)
        
            if texture.get() == "blender_musgrave":
                if gui: gui.newline("type:", -2, level+1, icon_texparam)
                mtype = Lux.Property(mat, keyname+".mtype", "multifractal")
                mtypes = ["multifractal","ridged_multifractal", "hybrid_multifractal", "hetero_terrain", "fbm"]
                str += Lux.TypedControls.Option("type", mtype, mtypes, "type", "", 2.0)
        
                str += Lux.TypedControls.Float("h", Lux.Property(mat, keyname+".h", 1.0), 0.0, 2.0, "h", "", 0.5)
                str += Lux.TypedControls.Float("lacu", Lux.Property(mat, keyname+".lacu", 2.0), 0.0, 6.0, "lacu", "", 0.75)
                str += Lux.TypedControls.Float("octs", Lux.Property(mat, keyname+".octs", 2.0), 0.0, 8.0, "octs", "", 0.75)
        
                if mtype.get() == "hetero_terrain":
                    str += Lux.TypedControls.Float("offset", Lux.Property(mat, keyname+".offset", 2.0), 0.0, 6.0, "offset", "", 2.0)
                if mtype.get() == "ridged_multifractal":
                    str += Lux.TypedControls.Float("offset", Lux.Property(mat, keyname+".offset", 2.0), 0.0, 6.0, "offset", "", 1.25)
                    str += Lux.TypedControls.Float("gain", Lux.Property(mat, keyname+".gain", 2.0), 0.0, 6.0, "gain", "", 0.75)
                if mtype.get() == "hybrid_multifractal":
                    str += Lux.TypedControls.Float("offset", Lux.Property(mat, keyname+".offset", 2.0), 0.0, 6.0, "offset", "", 1.25)
                    str += Lux.TypedControls.Float("gain", Lux.Property(mat, keyname+".gain", 2.0), 0.0, 6.0, "gain", "", 0.75)
        
                str += Lux.TypedControls.Float("outscale", Lux.Property(mat, keyname+".outscale", 1.0), 0.0, 10.0, "iscale", "", 1.0)
                str += Lux.TypedControls.Float("noisesize", Lux.Property(mat, keyname+".noisesize", 0.25), 0.0, 2.0, "noisesize", "", 1.0)
        
                if gui: gui.newline("basis:", -2, level+1, icon_texparam)
                noisebasis = Lux.Property(mat, keyname+".noisebasis", "blender_original")
                noisebasises = ["blender_original","original_perlin", "improved_perlin", "voronoi_f1", "voronoi_f2", "voronoi_f3", "voronoi_f4", "voronoi_f2f1", "voronoi_crackle", "cell_noise"]
                str += Lux.TypedControls.Option("noisebasis", noisebasis, noisebasises, "noisebasis", "", 2.0)
        
                if gui: gui.newline("level:", -2, level+1, icon_texparam)
                str += Lux.TypedControls.Float("bright", Lux.Property(mat, keyname+".bright", 1.0), 0.0, 2.0, "bright", "", 1.0)
                str += Lux.TypedControls.Float("contrast", Lux.Property(mat, keyname+".contrast", 1.0), 0.0, 10.0, "contrast", "", 1.0)
        
                (s, l) = c(("", ""), luxTexture("tex1", keyname, type, default, min, max, "tex1", "", mat, gui, matlevel, texlevel+1, lightsource))
                (s, l) = c((s, l), luxTexture("tex2", keyname, type, alternativedefault(type, default), min, max, "tex2", "", mat, gui, matlevel, texlevel+1, lightsource))
                str = s + str + l
        
                str += lux3DMapping(keyname, mat, gui, level+1)
        
            if texture.get() == "blender_wood":
                if gui: gui.newline("noise:", -2, level+1, icon_texparam)
        
                mtype = Lux.Property(mat, keyname+".mtype", "bands")
                mtypes = ["bands","rings","bandnoise", "ringnoise"]
                str += Lux.TypedControls.Option("type", mtype, mtypes, "type", "", 0.5)
        
                noisetype = Lux.Property(mat, keyname+".noisetype", "hard_noise")
                noisetypes = ["soft_noise","hard_noise"]
                str += Lux.TypedControls.Option("noisetype", noisetype, noisetypes, "noisetypes", "", 0.75)
        
                str += Lux.TypedControls.Float("noisesize", Lux.Property(mat, keyname+".noisesize", 0.25), 0.0, 2.0, "noisesize", "", 1.0)
                str += Lux.TypedControls.Float("turbulance", Lux.Property(mat, keyname+".turbulance", 5.0), 0.0, 200.0, "turbulance", "", 1.0)
        
                if gui: gui.newline("basis:", -2, level+1, icon_texparam)
                noisebasis2 = Lux.Property(mat, keyname+".noisebasis2", "sin")
                noisebasises2 = ["sin","saw","tri"]
                str += Lux.TypedControls.Option("noisebasis2", noisebasis2, noisebasises2, "noisebasis2", "", 0.7)
        
                noisebasis = Lux.Property(mat, keyname+".noisebasis", "blender_original")
                noisebasises = ["blender_original","original_perlin", "improved_perlin", "voronoi_f1", "voronoi_f2", "voronoi_f3", "voronoi_f4", "voronoi_f2f1", "voronoi_crackle", "cell_noise"]
                str += Lux.TypedControls.Option("noisebasis", noisebasis, noisebasises, "noisebasis", "", 1.3)
        
                if gui: gui.newline("level:", -2, level+1, icon_texparam)
                str += Lux.TypedControls.Float("bright", Lux.Property(mat, keyname+".bright", 1.0), 0.0, 2.0, "bright", "", 1.0)
                str += Lux.TypedControls.Float("contrast", Lux.Property(mat, keyname+".contrast", 1.0), 0.0, 10.0, "contrast", "", 1.0)
        
                (s, l) = c(("", ""), luxTexture("tex1", keyname, type, default, min, max, "tex1", "", mat, gui, matlevel, texlevel+1, lightsource))
                (s, l) = c((s, l), luxTexture("tex2", keyname, type, alternativedefault(type, default), min, max, "tex2", "", mat, gui, matlevel, texlevel+1, lightsource))
                str = s + str + l
            
                str += lux3DMapping(keyname, mat, gui, level+1)
        
            if texture.get() == "blender_clouds":
                if gui: gui.newline("noise:", -2, level+1, icon_texparam)
        
                mtype = Lux.Property(mat, keyname+".mtype", "default")
                mtypes = ["default","color"]
                str += Lux.TypedControls.Option("type", mtype, mtypes, "type", "", 0.5)
        
                noisetype = Lux.Property(mat, keyname+".noisetype", "hard_noise")
                noisetypes = ["soft_noise","hard_noise"]
                str += Lux.TypedControls.Option("noisetype", noisetype, noisetypes, "noisetypes", "", 0.75)
        
                str += Lux.TypedControls.Float("noisesize", Lux.Property(mat, keyname+".noisesize", 0.25), 0.0, 2.0, "noisesize", "", 1.0)
                str += Lux.TypedControls.Int("noisedepth", Lux.Property(mat, keyname+".noisedepth", 2), 0, 6, "noisedepth", "", 1.0)
        
                if gui: gui.newline("basis:", -2, level+1, icon_texparam)
                noisebasis = Lux.Property(mat, keyname+".noisebasis", "blender_original")
                noisebasises = ["blender_original","original_perlin", "improved_perlin", "voronoi_f1", "voronoi_f2", "voronoi_f3", "voronoi_f4", "voronoi_f2f1", "voronoi_crackle", "cell_noise"]
                str += Lux.TypedControls.Option("noisebasis", noisebasis, noisebasises, "noisebasis", "", 1.3)
        
                if gui: gui.newline("level:", -2, level+1, icon_texparam)
                str += Lux.TypedControls.Float("bright", Lux.Property(mat, keyname+".bright", 1.0), 0.0, 2.0, "bright", "", 1.0)
                str += Lux.TypedControls.Float("contrast", Lux.Property(mat, keyname+".contrast", 1.0), 0.0, 10.0, "contrast", "", 1.0)
        
                (s, l) = c(("", ""), luxTexture("tex1", keyname, type, default, min, max, "tex1", "", mat, gui, matlevel, texlevel+1, lightsource))
                (s, l) = c((s, l), luxTexture("tex2", keyname, type, alternativedefault(type, default), min, max, "tex2", "", mat, gui, matlevel, texlevel+1, lightsource))
                str = s + str + l
            
                str += lux3DMapping(keyname, mat, gui, level+1)
        
            if texture.get() == "blender_blend":
                if gui: gui.newline("type:", -2, level+1, icon_texparam)
        
                mtype = Lux.Property(mat, keyname+".mtype", "lin")
                mtypes = ["lin","quad","ease","diag","sphere","halo","radial"]
                str += Lux.TypedControls.Option("type", mtype, mtypes, "type", "", 0.5)
                
                mflag = Lux.Property(mat, keyname+".flag", "false")
                str += Lux.TypedControls.Bool("flipxy", mflag, "flipXY", "", 0.5)
        
                if gui: gui.newline("level:", -2, level+1, icon_texparam)
                str += Lux.TypedControls.Float("bright", Lux.Property(mat, keyname+".bright", 1.0), 0.0, 2.0, "bright", "", 1.0)
                str += Lux.TypedControls.Float("contrast", Lux.Property(mat, keyname+".contrast", 1.0), 0.0, 10.0, "contrast", "", 1.0)
        
                (s, l) = c(("", ""), luxTexture("tex1", keyname, type, default, min, max, "tex1", "", mat, gui, matlevel, texlevel+1, lightsource))
                (s, l) = c((s, l), luxTexture("tex2", keyname, type, alternativedefault(type, default), min, max, "tex2", "", mat, gui, matlevel, texlevel+1, lightsource))
                str = s + str + l
                
                str += lux3DMapping(keyname, mat, gui, level+1)
        
            if texture.get() == "blender_distortednoise":
                if gui: gui.newline("noise:", -2, level+1, icon_texparam)
                
                str += Lux.TypedControls.Float("distamount", Lux.Property(mat, keyname+".distamount", 1.0), 0.0, 10.0, "distamount", "", 1.0)
                str += Lux.TypedControls.Float("noisesize", Lux.Property(mat, keyname+".noisesize", 0.25), 0.0, 2.0, "noisesize", "", 1.0)
                str += Lux.TypedControls.Float("nabla", Lux.Property(mat, keyname+".nabla", 0.025), 0.000, 2.0, "nabla", "", 1.0)
                
                if gui: gui.newline("distortion:", -2, level+1, icon_texparam)
                ntype = Lux.Property(mat, keyname+".type", "blender_original")
                ntypes = ["blender_original","original_perlin", "improved_perlin", "voronoi_f1", "voronoi_f2", "voronoi_f3", "voronoi_f4", "voronoi_f2f1", "voronoi_crackle", "cell_noise"]
                str += Lux.TypedControls.Option("type", ntype, ntypes, "type", "", 1.3)
                
                if gui: gui.newline("basis:", -2, level+1, icon_texparam)
                noisebasis = Lux.Property(mat, keyname+".noisebasis", "blender_original")
                noisebasises = ["blender_original","original_perlin", "improved_perlin", "voronoi_f1", "voronoi_f2", "voronoi_f3", "voronoi_f4", "voronoi_f2f1", "voronoi_crackle", "cell_noise"]
                str += Lux.TypedControls.Option("noisebasis", noisebasis, noisebasises, "noisebasis", "", 1.3)
        
                if gui: gui.newline("level:", -2, level+1, icon_texparam)
                str += Lux.TypedControls.Float("bright", Lux.Property(mat, keyname+".bright", 1.0), 0.0, 2.0, "bright", "", 1.0)
                str += Lux.TypedControls.Float("contrast", Lux.Property(mat, keyname+".contrast", 1.0), 0.0, 10.0, "contrast", "", 1.0)
        
                (s, l) = c(("", ""), luxTexture("tex1", keyname, type, default, min, max, "tex1", "", mat, gui, matlevel, texlevel+1, lightsource))
                (s, l) = c((s, l), luxTexture("tex2", keyname, type, alternativedefault(type, default), min, max, "tex2", "", mat, gui, matlevel, texlevel+1, lightsource))
                str = s + str + l
                
                str += lux3DMapping(keyname, mat, gui, level+1)
        
            if texture.get() == "blender_noise":        
                if gui: gui.newline("level:", -2, level+1, icon_texparam)
                str += Lux.TypedControls.Float("bright", Lux.Property(mat, keyname+".bright", 1.0), 0.0, 2.0, "bright", "", 1.0)
                str += Lux.TypedControls.Float("contrast", Lux.Property(mat, keyname+".contrast", 1.0), 0.0, 10.0, "contrast", "", 1.0)
        
                (s, l) = c(("", ""), luxTexture("tex1", keyname, type, default, min, max, "tex1", "", mat, gui, matlevel, texlevel+1, lightsource))
                (s, l) = c((s, l), luxTexture("tex2", keyname, type, alternativedefault(type, default), min, max, "tex2", "", mat, gui, matlevel, texlevel+1, lightsource))
                str = s + str + l
                
                str += lux3DMapping(keyname, mat, gui, level+1)
                
            if texture.get() == "blender_magic":
                if gui: gui.newline("noise:", -2, level+1, icon_texparam)
                
                str += Lux.TypedControls.Int("noisedepth", Lux.Property(mat, keyname+".noisedepth", 2), 0.0, 10.0, "noisedepth", "", 1.0)
                str += Lux.TypedControls.Float("turbulance", Lux.Property(mat, keyname+".turbulance", 5.0), 0.0, 2.0, "turbulance", "", 1.0)
        
                if gui: gui.newline("level:", -2, level+1, icon_texparam)
                str += Lux.TypedControls.Float("bright", Lux.Property(mat, keyname+".bright", 1.0), 0.0, 2.0, "bright", "", 1.0)
                str += Lux.TypedControls.Float("contrast", Lux.Property(mat, keyname+".contrast", 1.0), 0.0, 10.0, "contrast", "", 1.0)
        
                (s, l) = c(("", ""), luxTexture("tex1", keyname, type, default, min, max, "tex1", "", mat, gui, matlevel, texlevel+1, lightsource))
                (s, l) = c((s, l), luxTexture("tex2", keyname, type, alternativedefault(type, default), min, max, "tex2", "", mat, gui, matlevel, texlevel+1, lightsource))
                str = s + str + l
                
                str += lux3DMapping(keyname, mat, gui, level+1)
                
            if texture.get() == "blender_stucci":
                if gui: gui.newline("noise:", -2, level+1, icon_texparam)
                mtype = Lux.Property(mat, keyname+".mtype", "Plastic")
                mtypes = ["Plastic","Wall In","Wall Out"]
                str += Lux.TypedControls.Option("type", mtype, mtypes, "type", "", 0.5)
        
                noisetype = Lux.Property(mat, keyname+".noisetype", "soft_noise")
                noisetypes = ["soft_noise","hard_noise"]
                str += Lux.TypedControls.Option("noisetype", noisetype, noisetypes, "noisetypes", "", 0.75)
                
                str += Lux.TypedControls.Float("noisesize", Lux.Property(mat, keyname+".noisesize", 0.25), 0.0, 10.0, "noisesize", "", 1.0)
                str += Lux.TypedControls.Float("turbulance", Lux.Property(mat, keyname+".turbulance", 5.0), 0.0, 200.0, "turbulance", "", 1.0)
        
                noisebasis = Lux.Property(mat, keyname+".noisebasis", "blender_original")
                noisebasises = ["blender_original","original_perlin", "improved_perlin", "voronoi_f1", "voronoi_f2", "voronoi_f3", "voronoi_f4", "voronoi_f2f1", "voronoi_crackle", "cell_noise"]
                str += Lux.TypedControls.Option("noisebasis", noisebasis, noisebasises, "noisebasis", "", 1.3)
        
                if gui: gui.newline("level:", -2, level+1, icon_texparam)
                str += Lux.TypedControls.Float("bright", Lux.Property(mat, keyname+".bright", 1.0), 0.0, 2.0, "bright", "", 1.0)
                str += Lux.TypedControls.Float("contrast", Lux.Property(mat, keyname+".contrast", 1.0), 0.0, 10.0, "contrast", "", 1.0)
        
                (s, l) = c(("", ""), luxTexture("tex1", keyname, type, default, min, max, "tex1", "", mat, gui, matlevel, texlevel+1, lightsource))
                (s, l) = c((s, l), luxTexture("tex2", keyname, type, alternativedefault(type, default), min, max, "tex2", "", mat, gui, matlevel, texlevel+1, lightsource))
                str = s + str + l
        
                str += lux3DMapping(keyname, mat, gui, level+1)
        
            if texture.get() == "blender_voronoi":
                #if gui: gui.newline("distmetric:", -2, level+1, icon_texparam)
                mtype = Lux.Property(mat, keyname+".distmetric", "actual_distance")
                mtypes = ["actual_distance","distance_squared","manhattan", "chebychev", "minkovsky_half", "minkovsky_four", "minkovsky"]
                str += Lux.TypedControls.Option("distmetric", mtype, mtypes, "distmetric", "", 1.1)
        
                if gui: gui.newline("param:", -2, level+1, icon_texparam)
                str += Lux.TypedControls.Float("minkovsky_exp", Lux.Property(mat, keyname+".minkovsky_exp", 2.5), 0.001, 10.0, "minkovsky_exp", "", 1.0)
                str += Lux.TypedControls.Float("outscale", Lux.Property(mat, keyname+".outscale", 1.0), 0.01, 10.0, "outscale", "", 1.0)
                str += Lux.TypedControls.Float("noisesize", Lux.Property(mat, keyname+".noisesize", 0.25), 0.0, 2.0, "noisesize", "", 1.0)
                str += Lux.TypedControls.Float("nabla", Lux.Property(mat, keyname+".nabla", 0.025), 0.001, 0.1, "nabla", "", 1.0)
                if gui: gui.newline("wparam:", -2, level+1, icon_texparam)
                str += Lux.TypedControls.Float("w1", Lux.Property(mat, keyname+".w1", 1.0), -2.0, 2.0, "w1", "", 1.0)
                str += Lux.TypedControls.Float("w2", Lux.Property(mat, keyname+".w2", 0.0), -2.0, 2.0, "w2", "", 1.0)
                str += Lux.TypedControls.Float("w3", Lux.Property(mat, keyname+".w3", 0.0), -2.0, 2.0, "w3", "", 1.0)
                str += Lux.TypedControls.Float("w4", Lux.Property(mat, keyname+".w4", 0.0), -2.0, 2.0, "w4", "", 1.0)
        
                if gui: gui.newline("level:", -2, level+1, icon_texparam)
                str += Lux.TypedControls.Float("bright", Lux.Property(mat, keyname+".bright", 1.0), 0.0, 2.0, "bright", "", 1.0)
                str += Lux.TypedControls.Float("contrast", Lux.Property(mat, keyname+".contrast", 1.0), 0.0, 10.0, "contrast", "", 1.0)
        
                (s, l) = c(("", ""), luxTexture("tex1", keyname, type, default, min, max, "tex1", "", mat, gui, matlevel, texlevel+1, lightsource))
                (s, l) = c((s, l), luxTexture("tex2", keyname, type, alternativedefault(type, default), min, max, "tex2", "", mat, gui, matlevel, texlevel+1, lightsource))
                str = s + str + l
        
                str += lux3DMapping(keyname, mat, gui, level+1)
        
        
        
            return (str+"\n", " \"texture %s\" [\"%s\"]"%(name, texname))
        
        @staticmethod
        def SpectrumTexture(name, key, default, max, caption, hint, mat, gui, level=0):
            global icon_col
            if gui: gui.newline(caption, 4, level, icon_col, scalelist([0.5,0.6,0.5],2.0/(level+2)))
            str = ""
            keyname = "%s:%s"%(key, name)
            texname = "%s:%s"%(mat.getName(), keyname)
            value = Lux.Property(mat, keyname, default)
            link = Lux.TypedControls.RGB(name, value, max, "", hint, 2.0)
            tex = Lux.Property(mat, keyname+".textured", False)
            if gui: Blender.Draw.Toggle("T", Lux.Events.LuxGui, gui.x, gui.y-gui.h, gui.h, gui.h, tex.get()=="true", "use texture", lambda e,v:tex.set(["false","true"][bool(v)]))
            if tex.get()=="true":
                if gui: gui.newline("", -2)
                (str, link) = luxTexture(name, key, "color", default, 0, max, caption, hint, mat, gui, level+1)
                if value.getRGB() != (1.0, 1.0, 1.0):
                    if str == "": # handle special case if texture is a just a constant
                        str += "Texture \"%s\" \"color\" \"scale\" \"color tex1\" [%s] \"color tex2\" [%s]\n"%(texname+".scale", (link.rpartition("[")[2])[0:-1], value.get())
                    else: str += "Texture \"%s\" \"color\" \"scale\" \"texture tex1\" [\"%s\"] \"color tex2\" [%s]\n"%(texname+".scale", texname, value.get())
                    link = " \"texture %s\" [\"%s\"]"%(name, texname+".scale")
            return (str, link)
        
        @staticmethod
        def LightSpectrumTexture(name, key, default, max, caption, hint, mat, gui, level=0):
            #if gui: gui.newline(caption, 4, level, icon_emission, scalelist([0.6,0.5,0.5],2.0/(level+2)))
            str = ""
            keyname = "%s:%s"%(key, name)
            texname = "%s:%s"%(mat.getName(), keyname)
            (str, link) = luxTexture(name, key, "color", default, 0, max, caption, hint, mat, gui, level+1, 0, 1)
            return (str, link)
        
        @staticmethod
        def FloatTexture(name, key, default, min, max, caption, hint, mat, gui, level=0):
            global icon_float
            if gui: gui.newline(caption, 4, level, icon_float, scalelist([0.5,0.5,0.6],2.0/(level+2)))
            str = ""
            keyname = "%s:%s"%(key, name)
            texname = "%s:%s"%(mat.getName(), keyname)
            value = Lux.Property(mat, keyname, default)
            link = Lux.TypedControls.Float(name, value, min, max, "", hint, 2.0)
            tex = Lux.Property(mat, keyname+".textured", False)
            if gui: Blender.Draw.Toggle("T", Lux.Events.LuxGui, gui.x, gui.y-gui.h, gui.h, gui.h, tex.get()=="true", "use texture", lambda e,v:tex.set(["false","true"][bool(v)]))
            if tex.get()=="true":
                if gui: gui.newline("", -2)
                (str, link) = luxTexture(name, key, "float", default, min, max, caption, hint, mat, gui, level+1)
                if value.get() != 1.0:
                    if str == "": # handle special case if texture is a just a constant
                        str += "Texture \"%s\" \"float\" \"scale\" \"float tex1\" [%s] \"float tex2\" [%s]\n"%(texname+".scale", (link.rpartition("[")[2])[0:-1], value.get())
                    else: str += "Texture \"%s\" \"float\" \"scale\" \"texture tex1\" [\"%s\"] \"float tex2\" [%s]\n"%(texname+".scale", texname, value.get())
                    link = " \"texture %s\" [\"%s\"]"%(name, texname+".scale")
            return (str, link)
        
        @staticmethod
        def FloatSliderTexture(name, key, default, min, max, caption, hint, mat, gui, level=0):
                global icon_float
                if gui: gui.newline(caption, 4, level, icon_float, scalelist([0.5,0.5,0.6],2.0/(level+2)))
                str = ""
                keyname = "%s:%s"%(key, name)
                texname = "%s:%s"%(mat.getName(), keyname)
                value = Lux.Property(mat, keyname, default)
                link = Lux.TypedControls.Float(name, value, min, max, caption, hint, 2.0, 1)
                tex = Lux.Property(mat, keyname+".textured", False)
                if gui: Blender.Draw.Toggle("T", Lux.Events.LuxGui, gui.x, gui.y-gui.h, gui.h, gui.h, tex.get()=="true", "use texture", lambda e,v:tex.set(["false","true"][bool(v)]))
                if tex.get()=="true":
                        if gui: gui.newline("", -2)
                        (str, link) = luxTexture(name, key, "float", default, min, max, caption, hint, mat, gui, level+1)
                        if value.get() != 1.0:
                                if str == "": # handle special case if texture is a just a constant
                                        str += "Texture \"%s\" \"float\" \"scale\" \"float tex1\" [%s] \"float tex2\" [%s]\n"%(texname+".scale", (link.rpartition("[")[2])[0:-1], value.get())
                                else: str += "Texture \"%s\" \"float\" \"scale\" \"texture tex1\" [\"%s\"] \"float tex2\" [%s]\n"%(texname+".scale", texname, value.get())
                                link = " \"texture %s\" [\"%s\"]"%(name, texname+".scale")
                return (str, link)
        
        @staticmethod
        def ExponentTexture(name, key, default, min, max, caption, hint, mat, gui, level=0):
            global icon_float
            if gui: gui.newline(caption, 4, level, icon_float, scalelist([0.5,0.5,0.6],2.0/(level+2)))
            str = ""
            keyname = "%s:%s"%(key, name)
            texname = "%s:%s"%(mat.getName(), keyname)
            value = Lux.Property(mat, keyname, default)
        
            if(value.get() == None): value.set(0.002)
        
        #    link = Lux.Types.Float(name, value, min, max, "", hint, 2.0)
            if gui:
                r = gui.getRect(2.0, 1)
                Blender.Draw.Number("", Lux.Events.LuxGui, r[0], r[1], r[2], r[3], float(1.0/value.getFloat()), 1.0, 1000000.0, hint, lambda e,v: value.set(1.0/v))
            link = " \"float %s\" [%f]"%(name, value.getFloat())
        
            tex = Lux.Property(mat, keyname+".textured", False)
            if gui: Blender.Draw.Toggle("T", Lux.Events.LuxGui, gui.x, gui.y-gui.h, gui.h, gui.h, tex.get()=="true", "use texture", lambda e,v:tex.set(["false","true"][bool(v)]))
            if tex.get()=="true":
                if gui: gui.newline("", -2)
                (str, link) = luxTexture(name, key, "float", default, min, max, caption, hint, mat, gui, level+1)
                if value.get() != 1.0:
                    if str == "": # handle special case if texture is a just a constant
                        str += "Texture \"%s\" \"float\" \"scale\" \"float tex1\" [%s] \"float tex2\" [%s]\n"%(texname+".scale", (link.rpartition("[")[2])[0:-1], value.get())
                    else: str += "Texture \"%s\" \"float\" \"scale\" \"texture tex1\" [\"%s\"] \"float tex2\" [%s]\n"%(texname+".scale", texname, value.get())
                    link = " \"texture %s\" [\"%s\"]"%(name, texname+".scale")
            return (str, link)
        
        @staticmethod
        def DispFloatTexture(name, key, default, min, max, caption, hint, mat, gui, level=0):
            global icon_float
            if gui: gui.newline(caption, 4, level, icon_float, scalelist([0.5,0.5,0.6],2.0/(level+2)))
            str = ""
            keyname = "%s:%s"%(key, name)
            texname = "%s:%s"%(mat.getName(), keyname)
            value = Lux.Property(mat, keyname, default)
            link = Lux.TypedControls.Float(name, value, min, max, "", hint, 2.0)
            tex = Lux.Property(mat, keyname+".textured", False)
            if gui: Blender.Draw.Toggle("T", Lux.Events.LuxGui, gui.x, gui.y-gui.h, gui.h, gui.h, tex.get()=="true", "use texture", lambda e,v:tex.set(["false","true"][bool(v)]))
            if tex.get()=="true":
                if gui: gui.newline("", -2)
                (str, link) = luxTexture(name, key, "float", default, min, max, caption, hint, mat, gui, level+1)
                str += "Texture \"%s\" \"float\" \"scale\" \"texture tex1\" [\"%s\"] \"float tex2\" [%s]\n"%(texname+".scale", texname, value.get())
                link = " \"texture %s\" [\"%s\"]"%(name, texname+".scale")
            return (str, link)
        
        @staticmethod
        def IORFloatTexture(name, key, default, min, max, caption, hint, mat, gui, level=0):
            # IOR preset data
            iornames = ["0Z *** Gases @ 0 C ***", "01 - Vacuum", "02 - Air @ STP", "03 - Air", "04 - Helium", "05 - Hydrogen", "06 - Carbon dioxide",
            "1Z *** LIQUIDS @ 20 C ***", "11 - Benzene", "12 - Water", "13 - Ethyl alcohol", "14 - Carbon tetrachloride", "15 - Carbon disulfide", 
            "2Z *** SOLIDS at room temperature ***", "21 - Diamond", "22 - Strontium titanate", "23 - Amber", "24 - Fused silica glass", "25 - sodium chloride", 
            "3Z *** OTHER Materials ***", "31 - Pyrex (Borosilicate glass)", "32 - Ruby", "33 - Water ice", "34 - Cryolite", "35 - Acetone", "36 - Ethanol", "37 - Teflon", "38 - Glycerol", "39 - Acrylic glass", "40 - Rock salt", "41 - Crown glass (pure)", "42 - Salt (NaCl)", "43 - Polycarbonate", "44 - PMMA", "45 - PETg", "46 - PET", "47 - Flint glass (pure)", "48 - Crown glass (impure)", "49 - Fused Quartz", "50 - Bromine", "51 - Flint glass (impure)", "52 - Cubic zirconia", "53 - Moissanite", "54 - Cinnabar (Mercury sulfide)", "55 - Gallium(III) prosphide", "56 - Gallium(III) arsenide", "57 - Silicon"]
            iorvals = [1.0, 1.0, 1.0002926, 1.000293, 1.000036, 1.000132, 1.00045,
            1.501, 1.501, 1.333, 1.361, 1.461, 1.628,
            2.419, 2.419, 2.41, 1.55, 1.458, 1.50,
            1.470, 1.470, 1.760, 1.31, 1.388, 1.36, 1.36, 1.35, 1.4729, 1.490, 1.516, 1.50, 1.544, 1.584, 1.4893, 1.57, 1.575, 1.60, 1.485, 1.46, 1.661, 1.523, 2.15, 2.419, 2.65, 3.02, 3.5, 3.927, 4.01]
        
            global icon_float
            if gui: gui.newline(caption, 4, level, icon_float, scalelist([0.5,0.5,0.6],2.0/(level+2)))
            str = ""
            keyname = "%s:%s"%(key, name)
            texname = "%s:%s"%(mat.getName(), keyname)
            value = Lux.Property(mat, keyname, default)
        
            iorusepreset = Lux.Property(mat, keyname+".iorusepreset", "true")
            Lux.TypedControls.Bool("iorusepreset", iorusepreset, "Preset", "Select from a list of predefined presets", 0.4)
        
            if(iorusepreset.get() == "true"):
                iorpreset = Lux.Property(mat, keyname+".iorpreset", "24 - Fused silica glass")
                if gui:
                    def setIor(i, value, preset, tree, dict): # callback function to set ior value after selection
                        def getTreeNameById(tree, i): # helper function to retrive name of the selected treemenu-item
                            for t in tree:
                                if type(t)==types.TupleType:
                                    if type(t[1])==types.ListType: 
                                        n=getTreeNameById(t[1], i)
                                        if n: return n
                                    elif t[1]==i: return t[0]
                            return None                
                        if i >= 0:
                            value.set(dict[i])
                            preset.set(getTreeNameById(tree, i))            
                    iortree = [ ("LIQUIDS", [("Acetone", 1), ("Alcohol, Ethyl (grain)", 2), ("Alcohol, Methyl (wood)", 3), ("Beer", 4), ("Benzene", 5), ("Carbon tetrachloride", 6), ("Carbon disulfide", 7), ("Carbonated Beverages", 8), ("Chlorine (liq)", 9), ("Cranberry Juice (25%)", 10), ("Glycerin", 11), ("Honey, 13% water content", 12), ("Honey, 17% water content", 13), ("Honey, 21% water content", 14), ("Ice", 15), ("Milk", 16), ("Oil, Clove", 17), ("Oil, Lemon", 18), ("Oil, Neroli", 19), ("Oil, Orange", 20), ("Oil, Safflower", 21), ("Oil, vegetable (50 C)", 22), ("Oil of Wintergreen", 23), ("Rum, White", 24), ("Shampoo", 25), ("Sugar Solution 30%", 26), ("Sugar Solution 80%", 27), ("Turpentine", 28), ("Vodka", 29), ("Water (0 C)", 30), ("Water (100 C)", 31), ("Water (20 C)", 32), ("Whisky", 33) ] ), ("GASES(0C)", [("Vacuum", 101), ("Air @ STP", 102), ("Air", 103), ("Helium", 104), ("Hydrogen", 105), ("Carbon dioxide", 106) ]), ("TRANSPARENT", [("Eye, Aqueous humor", 201), ("Eye, Cornea", 202), ("Eye, Lens", 203), ("Eye, Vitreous humor", 204), ("Glass, Arsenic Trisulfide", 205), ("Glass, Crown (common)", 206), ("Glass, Flint, 29% lead", 207), ("Glass, Flint, 55% lead", 208), ("Glass, Flint, 71% lead", 209), ("Glass, Fused Silica", 210), ("Glass, Pyrex", 211), ("Lucite", 212), ("Nylon", 213), ("Obsidian", 214), ("Plastic", 215), ("Plexiglas", 216), ("Salt", 217)  ]), ("GEMSTONES", [("Agate", 301), ("Alexandrite", 302), ("Almandine", 303), ("Amber", 304), ("Amethyst", 305), ("Ammolite", 306), ("Andalusite", 307), ("Apatite", 308), ("Aquamarine", 309), ("Axenite", 310), ("Beryl", 311), ("Beryl, Red", 312), ("Chalcedony", 313), ("Chrome Tourmaline", 314), ("Citrine", 315), ("Clinohumite", 316), ("Coral", 317), ("Crystal", 318), ("Crysoberyl, Catseye", 319), ("Danburite", 320), ("Diamond", 321), ("Emerald", 322), ("Emerald Catseye", 323), ("Flourite", 324), ("Garnet, Grossular", 325), ("Garnet, Andradite", 326), ("Garnet, Demantiod", 327), ("Garnet, Mandarin", 328), ("Garnet, Pyrope", 329), ("Garnet, Rhodolite", 330), ("Garnet, Tsavorite", 331), ("Garnet, Uvarovite", 332), ("Hauyn", 333), ("Iolite", 334), ("Jade, Jadeite", 335), ("Jade, Nephrite", 336), ("Jet", 337), ("Kunzite", 338), ("Labradorite", 339), ("Lapis Lazuli", 340), ("Moonstone", 341), ("Morganite", 342), ("Obsidian", 343), ("Opal, Black", 344), ("Opal, Fire", 345), ("Opal, White", 346), ("Oregon Sunstone", 347), ("Padparadja", 348), ("Pearl", 349), ("Peridot", 350), ("Quartz", 351), ("Ruby", 352), ("Sapphire", 353), ("Sapphire, Star", 354), ("Spessarite", 355), ("Spinel", 356), ("Spinel, Blue", 357), ("Spinel, Red", 358), ("Star Ruby", 359), ("Tanzanite", 360), ("Topaz", 361), ("Topaz, Imperial", 362), ("Tourmaline", 363), ("Tourmaline, Blue", 364), ("Tourmaline, Catseye", 365), ("Tourmaline, Green", 366), ("Tourmaline, Paraiba", 367), ("Tourmaline, Red", 368), ("Zircon", 369), ("Zirconia, Cubic", 370) ] ), ("OTHER", [("Pyrex (Borosilicate glass)", 401), ("Ruby", 402), ("Water ice", 403), ("Cryolite", 404), ("Acetone", 405), ("Ethanol", 406), ("Teflon", 407), ("Glycerol", 408), ("Acrylic glass", 409), ("Rock salt", 410), ("Crown glass (pure)", 411), ("Salt (NaCl)", 412), ("Polycarbonate", 413), ("PMMA", 414), ("PETg", 415), ("PET", 416), ("Flint glass (pure)", 417), ("Crown glass (impure)", 418), ("Fused Quartz", 419), ("Bromine", 420), ("Flint glass (impure)", 421), ("Cubic zirconia", 422), ("Moissanite", 423), ("Cinnabar (Mercury sulfide)", 424), ("Gallium(III) prosphide", 425), ("Gallium(III) arsenide", 426), ("Silicon", 427) ] ) ]
                    iordict = {1:1.36, 2:1.36, 3:1.329, 4:1.345, 5:1.501, 6:1.000132, 7:1.00045, 8:1.34, 9:1.385, 10:1.351, 11:1.473, 12:1.504, 13:1.494, 14:1.484, 15:1.309, 16:1.35, 17:1.535, 18:1.481, 19:1.482, 20:1.473, 21:1.466, 22:1.47, 23:1.536, 24:1.361, 25:1.362, 26:1.38, 27:1.49, 28:1.472, 29:1.363, 30:1.33346, 31:1.31766, 32:1.33283, 33:1.356, 101:1.0, 102:1.0002926, 103:1.000293, 104:1.000036, 105:1.000132, 106:1.00045, 201:1.33, 202:1.38, 203:1.41, 204:1.34, 205:2.04, 206:1.52, 207:1.569, 208:1.669, 209:1.805, 210:1.459, 211:1.474, 212:1.495, 213:1.53, 214:1.50, 215:1.460, 216:1.488, 217:1.516, 301:1.544, 302:1.746, 303:1.75, 304:1.539, 305:1.532, 306:1.52, 307:1.629, 308:1.632, 309:1.567, 310:1.674, 311:1.57, 312:1.570, 313:1.544, 314:1.61, 315:1.532, 316:1.625, 317:1.486, 318:2.000, 319:1.746, 320:1.627, 321:2.417, 322:1.560, 323:1.560, 324:1.434, 325:1.72, 326:1.88, 327:1.880, 328:1.790, 329:1.73, 330:1.740, 331:1.739, 332:1.74, 333:1.490, 334:1.522, 335:1.64, 336:1.600, 337:1.660, 338:1.660, 339:1.560, 340:1.50, 341:1.518, 342:1.585, 343:1.50, 344:1.440, 345:1.430, 346:1.440, 347:1.560, 348:1.760, 349:1.53, 350:1.635, 351:1.544, 352:1.757, 353:1.757, 354:1.760, 355:1.79, 356:1.712, 357:1.712, 358:1.708, 359:1.76, 360:1.690, 361:1.607, 362:1.605, 363:1.603, 364:1.61, 365:1.61, 366:1.61, 367:1.61, 368:1.61, 369:1.777, 370:2.173, 401:1.47, 402:1.76, 403:1.31, 404:1.388, 405:1.36, 406:1.36, 407:1.35, 408:1.4729, 409:1.49, 410:1.516, 411:1.5, 412:1.544, 413:1.584, 414:1.4893, 415:1.57, 416:1.575, 417:1.6, 418:1.485, 419:1.46, 420:1.661, 421:1.523, 422:2.15, 423:2.419, 424:2.65, 425:3.02, 426:3.5, 427:3.927}
                    r = gui.getRect(1.6, 1)
                    Blender.Draw.Button(iorpreset.get(), Lux.Events.LuxGui, r[0], r[1], r[2], r[3], "select IOR preset", lambda e,v: setIor(Blender.Draw.PupTreeMenu(iortree), value, iorpreset, iortree, iordict))
                
                # DH - this line had gui = None !
                link = Lux.TypedControls.Float(name, value, min, max, "IOR", hint, 1.6)
            else:
                link = Lux.TypedControls.Float(name, value, min, max, "IOR", hint, 1.6, 1)
        
            tex = Lux.Property(mat, keyname+".textured", False)
            if gui: Blender.Draw.Toggle("T", Lux.Events.LuxGui, gui.x, gui.y-gui.h, gui.h, gui.h, tex.get()=="true", "use texture", lambda e,v:tex.set(["false","true"][bool(v)]))
            if tex.get()=="true":
                if gui: gui.newline("", -2)
                (str, link) = luxTexture(name, key, "float", default, min, max, caption, hint, mat, gui, level+1)
                if value.get() != 1.0:
                    str += "Texture \"%s\" \"float\" \"scale\" \"texture tex1\" [\"%s\"] \"float tex2\" [%s]\n"%(texname+".scale", texname, value.get())
                    link = " \"texture %s\" [\"%s\"]"%(name, texname+".scale")
            return (str, link)
        
        @staticmethod
        def CauchyBFloatTexture(name, key, default, min, max, caption, hint, mat, gui, level=0):
            # IOR preset data
            cauchybnames = ["01 - Fused silica glass", "02 - Borosilicate glass BK7", "03 - Hard crown glass K5", "04 - Barium crown glass BaK4", "05 - Barium flint glass BaF10", "06 - Dense flint glass SF10" ]
            cauchybvals = [ 0.00354, 0.00420, 0.00459, 0.00531, 0.00743, 0.01342 ]
        
            global icon_float
            if gui: gui.newline(caption, 4, level, icon_float, scalelist([0.5,0.5,0.6],2.0/(level+2)))
            str = ""
            keyname = "%s:%s"%(key, name)
            texname = "%s:%s"%(mat.getName(), keyname)
            value = Lux.Property(mat, keyname, default)
        
            cauchybusepreset = Lux.Property(mat, keyname+".cauchybusepreset", "true")
            Lux.TypedControls.Bool("cauchybusepreset", cauchybusepreset, "Preset", "Select from a list of predefined presets", 0.4)
        
            if(cauchybusepreset.get() == "true"):
                cauchybpreset = Lux.Property(mat, keyname+".cauchybpreset", "01 - Fused silica glass")
                Lux.TypedControls.Option("cauchybpreset", cauchybpreset, cauchybnames, "  PRESET", "select CauchyB preset", 1.6)
                idx = cauchybnames.index(cauchybpreset.get())
                value.set(cauchybvals[idx])
                
                # DH - this line had gui = None !
                link = Lux.TypedControls.Float(name, value, min, max, "cauchyb", hint, 1.6)
            else:
                link = Lux.TypedControls.Float(name, value, min, max, "cauchyb", hint, 1.6, 1)
        
            tex = Lux.Property(mat, keyname+".textured", False)
            if gui: Blender.Draw.Toggle("T", Lux.Events.LuxGui, gui.x, gui.y-gui.h, gui.h, gui.h, tex.get()=="true", "use texture", lambda e,v:tex.set(["false","true"][bool(v)]))
            if tex.get()=="true":
                if gui: gui.newline("", -2)
                (str, link) = luxTexture(name, key, "float", default, min, max, caption, hint, mat, gui, level+1)
                if value.get() != 1.0:
                    str += "Texture \"%s\" \"float\" \"scale\" \"texture tex1\" [\"%s\"] \"float tex2\" [%s]\n"%(texname+".scale", texname, value.get())
                    link = " \"texture %s\" [\"%s\"]"%(name, texname+".scale")
            return (str, link)

        def Material(mat, gui=None):
            str = ""
            if mat:
                if Lux.Property(mat, "type", "").get()=="": # lux material not defined yet
                    print "Blender material \"%s\" has no lux material definition, converting..."%(mat.getName())
                    try:
                        convertMaterial(mat) # try converting the blender material to a lux material
                    except: pass
                (str, link) = luxMaterialBlock("", "", "", mat, gui, 0)
                if Lux.Property(mat, "type", "matte").get() != "light":
                    link = "NamedMaterial \"%s\""%(mat.getName())
                # export emission options (no gui)
                useemission = Lux.Property(mat, "emission", "false")
                if useemission.get() == "true":
                    (estr, elink) = luxLight("", "", mat, None, 0)
                    str += estr
                    link += "\n\tAreaLightSource \"area\" "+elink 
                    
                Lux.Property(mat, "link", "").set("".join(link))
            return str

    class Mapping:
        
        @staticmethod
        def factory(dimension, *args):
            if   dimension == 2:
                return Lux.Mapping.Mapping2D(*args)
            elif dimension == 3:
                return Lux.Mapping.Mapping3D(*args)
            else:
                return False
        
        @staticmethod
        def Mapping2D(key, mat, gui, level=0):
            global icon_map2d, icon_map2dparam
            if gui: gui.newline("2Dmap:", -2, level, icon_map2d)
            mapping = Lux.Property(mat, key+".mapping", "uv")
            mappings = ["uv","spherical","cylindrical","planar"]
            str = Lux.TypedControls.Option("mapping", mapping, mappings, "mapping", "", 0.5)
            if mapping.get() == "uv":
                str += Lux.TypedControls.Float("uscale", Lux.Property(mat, key+".uscale", 1.0), -100.0, 100.0, "Us", "u-scale", 0.375)
                str += Lux.TypedControls.Float("vscale", Lux.Property(mat, key+".vscale", -1.0), -100.0, 100.0, "Vs", "v-scale", 0.375)
                str += Lux.TypedControls.Float("udelta", Lux.Property(mat, key+".udelta", 0.0), -100.0, 100.0, "Ud", "u-delta", 0.375)
                str += Lux.TypedControls.Float("vdelta", Lux.Property(mat, key+".vdelta", 0.0), -100.0, 100.0, "Vd", "v-delta", 0.375)
            if mapping.get() == "planar":
                str += Lux.TypedControls.Float("udelta", Lux.Property(mat, key+".udelta", 0.0), -100.0, 100.0, "Ud", "u-delta", 0.75)
                str += Lux.TypedControls.Float("vdelta", Lux.Property(mat, key+".vdelta", 0.0), -100.0, 100.0, "Vd", "v-delta", 0.75)
                if gui: gui.newline("v1:", -2, level+1, icon_map2dparam)
                str += Lux.TypedControls.Vector("v1", Lux.Property(mat, key+".v1", "1 0 0"), -100.0, 100.0, "v1", "v1-vector", 2.0)
                if gui: gui.newline("v2:", -2, level+1, icon_map2dparam)
                str += Lux.TypedControls.Vector("v2", Lux.Property(mat, key+".v2", "0 1 0"), -100.0, 100.0, "v2", "v2-vector", 2.0)
            return str
        
        @staticmethod
        def Mapping3D(key, mat, gui, level=0):
            global icon_map3dparam
            str = ""
            if gui: gui.newline("scale:", -2, level, icon_map3dparam)
            str += Lux.TypedControls.VectorUniform("scale", Lux.Property(mat, key+".3dscale", 1.0), 0.001, 1000.0, "scale", "scale-vector", 2.0)
            if gui: gui.newline("rot:", -2, level, icon_map3dparam)
            str += Lux.TypedControls.Vector("rotate", Lux.Property(mat, key+".3drotate", "0 0 0"), -360.0, 360.0, "rotate", "rotate-vector", 2.0)
            if gui: gui.newline("move:", -2, level, icon_map3dparam)
            str += Lux.TypedControls.Vector("translate", Lux.Property(mat, key+".3dtranslate", "0 0 0"), -1000.0, 1000.0, "move", "translate-vector", 2.0)
            return str
        
    class Light:
        # was luxLight
        def Area(name, kn, mat, gui, level):
            if gui:
                if name != "": gui.newline(name+":", 10, level)
                else: gui.newline("color:", 0, level+1)
            (str,link) = luxLightSpectrumTexture("L", kn+"light", "1.0 1.0 1.0", 1.0, "Spectrum", "", mat, gui, level+1)
            if gui: gui.newline("")
            link += Lux.TypedControls.Float("power", Lux.Property(mat, kn+"light.power", 100.0), 0.0, 10000.0, "Power(W)", "AreaLight Power in Watts")
            link += Lux.TypedControls.Float("efficacy", Lux.Property(mat, kn+"light.efficacy", 17.0), 0.0, 100.0, "Efficacy(lm/W)", "Efficacy Luminous flux/watt")
            if gui: gui.newline("")
            link += Lux.TypedControls.Float("gain", Lux.Property(mat, kn+"light.gain", 1.0), 0.0, 100.0, "gain", "Gain/scale multiplier")
            lightgroup = Lux.Property(mat, kn+"light.lightgroup", "default")
            Lux.TypedControls.String("lightgroup", lightgroup, "group", "assign light to a named light-group", 1.0)
        
            if gui: gui.newline("Photometric")
            pm = Lux.Property(mat, kn+"light.usepm", "false")
            Lux.TypedControls.Bool("photometric", pm, "Photometric Diagram", "Enable Photometric Diagram options", 2.0)
        
            if(pm.get()=="true"):
                pmtype = Lux.Property(mat, kn+"light.pmtype", "IESna")
                pmtypes = ["IESna", "imagemap"]
                Lux.TypedControls.Option("type", pmtype, pmtypes, "type", "Choose Photometric data type to use", 0.6)
                if(pmtype.get() == "imagemap"):
                    map = Lux.Property(mat, kn+"light.pmmapname", "")
                    link += Lux.TypedControls.File("mapname", map, "map-file", "filename of the photometric map", 1.4)        
                if(pmtype.get() == "IESna"):
                    map = Lux.Property(mat, kn+"light.pmiesname", "")
                    link += Lux.TypedControls.File("iesname", map, "ies-file", "filename of the IES photometric data file", 1.4)        
        
            has_bump_options = 0
            has_object_options = 1
            return (str, link)
        
        #was luxLamp
        def Point(name, kn, mat, gui, level):
            if gui:
                if name != "": gui.newline(name+":", 10, level)
                else: gui.newline("color:", 0, level+1)
        #    if gui: gui.newline("", 10, level)
            (str,link) = luxLightSpectrumTexture("L", kn+"light", "1.0 1.0 1.0", 1.0, "Spectrum", "", mat, gui, level+1)
            if gui: gui.newline("")
            link += Lux.TypedControls.Float("gain", Lux.Property(mat, kn+"light.gain", 1.0), 0.0, 100.0, "gain", "Gain/scale multiplier")
            lightgroup = Lux.Property(mat, kn+"light.lightgroup", "default")
            Lux.TypedControls.String("lightgroup", lightgroup, "group", "assign light to a named light-group", 1.0)
        
            if gui: gui.newline("Photometric")
            pm = Lux.Property(mat, kn+"light.usepm", "false")
            Lux.TypedControls.Bool("photometric", pm, "Photometric Diagram", "Enable Photometric Diagram options", 2.0)
        
            if(pm.get()=="true"):
                pmtype = Lux.Property(mat, kn+"light.pmtype", "IESna")
                pmtypes = ["IESna", "imagemap"]
                Lux.TypedControls.Option("type", pmtype, pmtypes, "type", "Choose Photometric data type to use", 0.6)
                if(pmtype.get() == "imagemap"):
                    map = Lux.Property(mat, kn+"light.pmmapname", "")
                    link += Lux.TypedControls.File("mapname", map, "map-file", "filename of the photometric map", 1.4)        
                if(pmtype.get() == "IESna"):
                    map = Lux.Property(mat, kn+"light.pmiesname", "")
                    link += Lux.TypedControls.File("iesname", map, "ies-file", "filename of the IES photometric data file", 1.4)        
        
                link += Lux.TypedControls.Bool("flipz", Lux.Property(mat, kn+"light.flipZ", "true"), "Flip Z", "Flip Z direction in mapping", 2.0)
        
            return (str, link)
        
        #was luxSpot
        def Spot(name, kn, mat, gui, level):
            if gui:
                if name != "": gui.newline(name+":", 10, level)
                else: gui.newline("color:", 0, level+1)
        #    if gui: gui.newline("", 10, level)
            (str,link) = luxLightSpectrumTexture("L", kn+"light", "1.0 1.0 1.0", 1.0, "Spectrum", "", mat, gui, level+1)
            if gui: gui.newline("")
            link += Lux.TypedControls.Float("gain", Lux.Property(mat, kn+"light.gain", 1.0), 0.0, 100.0, "gain", "Gain/scale multiplier")
            lightgroup = Lux.Property(mat, kn+"light.lightgroup", "default")
            Lux.TypedControls.String("lightgroup", lightgroup, "group", "assign light to a named light-group", 1.0)
        
            if gui: gui.newline("Projection")
            proj = Lux.Property(mat, kn+"light.usetexproj", "false")
            Lux.TypedControls.Bool("projection", proj, "Texture Projection", "Enable imagemap texture projection", 2.0)
        
            if(proj.get() == "true"):
                map = Lux.Property(mat, kn+"light.pmmapname", "")
                link += Lux.TypedControls.File("mapname", map, "map-file", "filename of the photometric map", 2.0)        
        
            return (str, link)
        
    class Preview:
        def Sphereset(mat, kn, state):
            if state=="true":
                Lux.Property(mat, kn+"prev_sphere", "true").set("true")
                Lux.Property(mat, kn+"prev_plane", "false").set("false")
                Lux.Property(mat, kn+"prev_torus", "false").set("false")
        
        def Planeset(mat, kn, state):
            if state=="true":
                Lux.Property(mat, kn+"prev_sphere", "true").set("false")
                Lux.Property(mat, kn+"prev_plane", "false").set("true")
                Lux.Property(mat, kn+"prev_torus", "false").set("false")
        
        def Torusset(mat, kn, state):
            if state=="true":
                Lux.Property(mat, kn+"prev_sphere", "true").set("false")
                Lux.Property(mat, kn+"prev_plane", "false").set("false")
                Lux.Property(mat, kn+"prev_torus", "false").set("true")
        
        def Update(mat, kn, defLarge, defType, texName, name, level):
            #print "%s %s %s %s %s %s %s" % (mat, kn, defLarge, defType, texName, name, level)
            
            Blender.Window.WaitCursor(True)
            Lux.scene = Blender.Scene.GetCurrent()
        
            # Size of preview thumbnail
            thumbres = 110 # default 110x110
            if(defLarge):
                large = Lux.Property(mat, kn+"prev_large", "true")
            else:
                large = Lux.Property(mat, kn+"prev_large", "false")
            if(large.get() == "true"):
                thumbres = 140 # small 140x140
        
            thumbbuf = thumbres*thumbres*3
        
        #        consolebin = Lux.Prop(Lux.scene, "luxconsole", "").get()
            consolebin = Blender.sys.dirname(Lux.Property(Lux.scene, "lux", "").get()) + os.sep + "luxconsole"
            if osys.platform == "win32": consolebin = consolebin + ".exe"
        
            PIPE = subprocess.PIPE
            p = subprocess.Popen((consolebin, '-b', '-'), bufsize=thumbbuf, stdin=PIPE, stdout=PIPE, stderr=PIPE)
        
            # Unremark to write debugging output to file
            # p.stdin = open('c:\preview.lxs', 'w')
        
            if defType == 0:    
                prev_sphere = Lux.Property(mat, kn+"prev_sphere", "true")
                prev_plane = Lux.Property(mat, kn+"prev_plane", "false")
                prev_torus = Lux.Property(mat, kn+"prev_torus", "false")
            elif defType == 1:
                prev_sphere = Lux.Property(mat, kn+"prev_sphere", "false")
                prev_plane = Lux.Property(mat, kn+"prev_plane", "true")
                prev_torus = Lux.Property(mat, kn+"prev_torus", "false")
            else:
                prev_sphere = Lux.Property(mat, kn+"prev_sphere", "false")
                prev_plane = Lux.Property(mat, kn+"prev_plane", "false")
                prev_torus = Lux.Property(mat, kn+"prev_torus", "true")
        
            # Zoom
            if Lux.Property(mat, kn+"prev_zoom", "false").get() == "true":
                p.stdin.write('LookAt 0.250000 -1.500000 0.750000 0.250000 -0.500000 0.750000 0.000000 0.000000 1.000000\nCamera "perspective" "float fov" [22.5]\n')
            else:
                p.stdin.write('LookAt 0.0 -3.0 0.5 0.0 -2.0 0.5 0.0 0.0 1.0\nCamera "perspective" "float fov" [22.5]\n')
            # Fleximage
            p.stdin.write('Film "fleximage" "integer xresolution" [%i] "integer yresolution" [%i] "integer displayinterval" [3] "integer ldr_writeinterval" [3600] "string tonemapper" ["reinhard"] "integer haltspp" [1] "integer reject_warmup" [64] "bool write_tonemapped_tga" ["false"] "bool write_untonemapped_exr" ["false"] "bool write_tonemapped_exr" ["false"] "bool write_untonemapped_igi" ["false"] "bool write_tonemapped_igi" ["false"] \n'%(thumbres, thumbres))
            p.stdin.write('PixelFilter "sinc"\n')
            # Quality
            Lux.scene = Blender.Scene.GetCurrent()
            defprevmat = Lux.Property(Lux.scene, "defprevmat", "high")
            quality = Lux.Property(mat, kn+"prev_quality", defprevmat.get())
            if quality.get()=="low":
                p.stdin.write('Sampler "lowdiscrepancy" "string pixelsampler" ["hilbert"] "integer pixelsamples" [2]\n')
            elif quality.get()=="medium":
                p.stdin.write('Sampler "lowdiscrepancy" "string pixelsampler" ["hilbert"] "integer pixelsamples" [4]\n')
            elif quality.get()=="high":
                p.stdin.write('Sampler "lowdiscrepancy" "string pixelsampler" ["hilbert"] "integer pixelsamples" [8]\n')
            else: 
                p.stdin.write('Sampler "lowdiscrepancy" "string pixelsampler" ["hilbert"] "integer pixelsamples" [32]\n')
            # SurfaceIntegrator
            if(prev_plane.get()=="false"):
                p.stdin.write('SurfaceIntegrator "distributedpath" "integer directsamples" [1] "integer diffusereflectdepth" [1] "integer diffusereflectsamples" [4] "integer diffuserefractdepth" [4] "integer diffuserefractsamples" [1] "integer glossyreflectdepth" [1] "integer glossyreflectsamples" [2] "integer glossyrefractdepth" [4] "integer glossyrefractsamples" [1] "integer specularreflectdepth" [2] "integer specularrefractdepth" [4]\n')
            else:
                p.stdin.write('SurfaceIntegrator "distributedpath" "integer directsamples" [1] "integer diffusereflectdepth" [0] "integer diffusereflectsamples" [0] "integer diffuserefractdepth" [0] "integer diffuserefractsamples" [0] "integer glossyreflectdepth" [0] "integer glossyreflectsamples" [0] "integer glossyrefractdepth" [0] "integer glossyrefractsamples" [0] "integer specularreflectdepth" [1] "integer specularrefractdepth" [1]\n')
            # World
            p.stdin.write('WorldBegin\n')
            if(prev_sphere.get()=="true"):
                p.stdin.write('AttributeBegin\nTransform [0.5 0.0 0.0 0.0  0.0 0.5 0.0 0.0  0.0 0.0 0.5 0.0  0.0 0.0 0.5 1.0]\n')
            elif (prev_plane.get()=="true"):
                p.stdin.write('AttributeBegin\nTransform [0.649999976158 0.0 0.0 0.0  0.0 4.90736340453e-008 0.649999976158 0.0  0.0 -0.649999976158 4.90736340453e-008 0.0  0.0 0.0 0.5 1.0]\n')
            else:
                p.stdin.write('AttributeBegin\nTransform [0.35 -0.35 0.0 0.0  0.25 0.25 0.35 0.0  -0.25 -0.25 0.35 0.0  0.0 0.0 0.5 1.0]\n')
            obwidth = Lux.Property(mat, kn+"prev_obwidth", 1.0)
            obw = obwidth.get()
            p.stdin.write('TransformBegin\n')
            p.stdin.write('Scale %f %f %f\n'%(obw,obw,obw))
            if texName:
                print "texture "+texName+"  "+name
                (str, link) = luxTexture(texName, name, "color", "1.0 1.0 1.0", None, None, "", "", mat, None, 0, level)
                link = link.replace(" "+texName+"\"", " Kd\"") # swap texture name to "Kd"
                p.stdin.write(str+"\n")
                p.stdin.write("Material \"matte\" "+link+"\n") 
            else:
                # Material
                p.stdin.write(luxMaterial(mat))
                link = Lux.Property(mat,"link","").get()
                if kn!="": link = link.rstrip("\"")+":"+kn.strip(".:")+"\""
                p.stdin.write(link+'\n')
            p.stdin.write('TransformEnd\n')
            # Shape
            if(prev_sphere.get()=="true"):
                p.stdin.write('Shape "sphere" "float radius" [1.0]\n')
            elif (prev_plane.get()=="true"):
                p.stdin.write('    Shape "trianglemesh" "integer indices" [ 0 1 2 0 2 3 ] "point P" [ 1.0 1.0 0.0 -1.0 1.0 0.0 -1.0 -1.0 -0.0 1.0 -1.0 -0.0 ] "float uv" [ 0.0 0.0 1.0 0.0 1.0 -1.0 0.0 -1.0 ]\n')
            elif (prev_torus.get()=="true"):
                p.stdin.write('Shape "torus" "float radius" [1.0]\n')
            p.stdin.write('AttributeEnd\n')
            # Checkerboard floor
            if(prev_plane.get()=="false"):
                p.stdin.write('AttributeBegin\nTransform [5.0 0.0 0.0 0.0  0.0 5.0 0.0 0.0  0.0 0.0 5.0 0.0  0.0 0.0 0.0 1.0]\n')
                p.stdin.write('Texture "checks" "color" "checkerboard"')
                p.stdin.write('"integer dimension" [2] "string aamode" ["supersample"] "color tex1" [0.9 0.9 0.9] "color tex2" [0.0 0.0 0.0]')
                p.stdin.write('"string mapping" ["uv"] "float uscale" [36.8] "float vscale" [36.0]\n')
                p.stdin.write('Material "matte" "texture Kd" ["checks"]\n')
                p.stdin.write('Shape "loopsubdiv" "integer nlevels" [3] "bool dmnormalsmooth" ["true"] "bool dmsharpboundary" ["true"] ')
                p.stdin.write('"integer indices" [ 0 1 2 0 2 3 1 0 4 1 4 5 5 4 6 5 6 7 ]')
                p.stdin.write('"point P" [ 1.000000 1.000000 0.000000 -1.000000 1.000000 0.000000 -1.000000 -1.000000 0.000000 1.000000 -1.000000 0.000000 1.000000 3.000000 0.000000 -1.000000 3.000000 0.000000 1.000000 3.000000 2.000000 -1.000000 3.000000 2.000000')
                p.stdin.write('] "normal N" [ 0.000000 0.000000 1.000000 0.000000 0.000000 1.000000 0.000000 0.000000 1.000000 0.000000 0.000000 1.000000 0.000000 -0.707083 0.707083 0.000000 -0.707083 0.707083 0.000000 -1.000000 0.000000 0.000000 -1.000000 0.000000')
                p.stdin.write('] "float uv" [ 0.333334 0.000000 0.333334 0.333334 0.000000 0.333334 0.000000 0.000000 0.666667 0.000000 0.666667 0.333333 1.000000 0.000000 1.000000 0.333333 ]\n')
                p.stdin.write('AttributeEnd\n')
            # Lightsource
            if(prev_plane.get()=="false"):
                p.stdin.write('AttributeBegin\nTransform [1.0 0.0 0.0 0.0  0.0 1.0 0.0 0.0  0.0 0.0 1.0 0.0  1.0 -1.0 4.0 1.0]\n')
            else:
                p.stdin.write('AttributeBegin\nTransform [1.0 0.0 0.0 0.0  0.0 1.0 0.0 0.0  0.0 0.0 1.0 0.0  1.0 -4.0 1.0 1.0]\n')
            area = Lux.Property(mat, kn+"prev_arealight", "false")
            if(area.get() == "false"):
                p.stdin.write('Texture "pL" "color" "blackbody" "float temperature" [6500.0]\n')
                p.stdin.write('LightSource "point" "texture L" ["pL"]')
            else:
                p.stdin.write('ReverseOrientation\n')
                p.stdin.write('AreaLightSource "area" "color L" [1.0 1.0 1.0]\n')
                p.stdin.write('Shape "disk" "float radius" [1.0]\nAttributeEnd\n')
            p.stdin.write('WorldEnd\n')
        
            data = p.communicate()[0]
            p.stdin.close()
            if(len(data) < thumbbuf): 
                print "error on preview"
                return
            global previewCache
            image = luxImage()
            image.decodeLuxConsole(thumbres, thumbres, data)
            previewCache[(mat.name+":"+kn).__hash__()] = image
            Blender.Draw.Redraw()
            Blender.Window.WaitCursor(False)
        
        def Preview(mat, name, defType=0, defEnabled=False, defLarge=False, texName=None, gui=None, level=0, color=None):
            if gui:
                kn = name
                if texName: kn += ":"+texName
                if kn != "": kn += "."
                if(defEnabled == True):
                    showpreview = Lux.Property(mat, kn+"prev_show", "true")
                else:
                    showpreview = Lux.Property(mat, kn+"prev_show", "false")
                Blender.Draw.Toggle("P", Lux.Events.LuxGui, gui.xmax, gui.y-gui.h, gui.h, gui.h, showpreview.get()=="true", "Preview", lambda e,v: showpreview.set(["false","true"][bool(v)]))
                if showpreview.get()=="true": 
                    if(defLarge):
                        large = Lux.Property(mat, kn+"prev_large", "true")
                    else:
                        large = Lux.Property(mat, kn+"prev_large", "false")
                    voffset = -8
                    rr = 5.65 
                    if(large.get() == "true"):
                        rr = 7
                        voffset = 22
                    gui.newline()
                    r = gui.getRect(1.1, rr)
                    if(color != None):
                        Blender.BGL.glColor3f(color[0],color[1],color[2]); Blender.BGL.glRectf(r[0]-110, r[1], 418, r[1]+128+voffset); Blender.BGL.glColor3f(0.9, 0.9, 0.9)
                    try: previewCache[(mat.name+":"+kn).__hash__()].draw(r[0]-82, r[1]+4)
                    except: pass
        
                    prev_sphere = Lux.Property(mat, kn+"prev_sphere", "true")
                    prev_plane = Lux.Property(mat, kn+"prev_plane", "false")
                    prev_torus = Lux.Property(mat, kn+"prev_torus", "false")
                    if defType == 1:
                        prev_sphere = Lux.Property(mat, kn+"prev_sphere", "false")
                        prev_plane = Lux.Property(mat, kn+"prev_plane", "true")
                        prev_torus = Lux.Property(mat, kn+"prev_torus", "false")
                    elif defType == 2:
                        prev_sphere = Lux.Property(mat, kn+"prev_sphere", "false")
                        prev_plane = Lux.Property(mat, kn+"prev_plane", "false")
                        prev_torus = Lux.Property(mat, kn+"prev_torus", "true")
        
                    # preview mode toggle buttons
                    Blender.Draw.Toggle("S", Lux.Events.LuxGui, r[0]-108, r[1]+100+voffset, 22, 22, prev_sphere.get()=="true", "Draw Sphere", lambda e,v: Preview_Sphereset(mat, kn, ["false","true"][bool(v)]))
                    Blender.Draw.Toggle("P", Lux.Events.LuxGui, r[0]-108, r[1]+74+voffset, 22, 22, prev_plane.get()=="true", "Draw 2D Plane", lambda e,v: Preview_Planeset(mat, kn, ["false","true"][bool(v)]))
                    Blender.Draw.Toggle("T", Lux.Events.LuxGui, r[0]-108, r[1]+48+voffset, 22, 22, prev_torus.get()=="true", "Draw Torus", lambda e,v: Preview_Torusset(mat, kn, ["false","true"][bool(v)]))
        
                    # Zoom toggle
                    zoom = Lux.Property(mat, kn+"prev_zoom", "false")
                    Blender.Draw.Toggle("Zoom", Lux.Events.LuxGui, r[0]+66, r[1]+100+voffset, 50, 18, zoom.get()=="true", "Zoom", lambda e,v: zoom.set(["false","true"][bool(v)]))
        
                    area = Lux.Property(mat, kn+"prev_arealight", "false")
                    Blender.Draw.Toggle("Area", Lux.Events.LuxGui, r[0]+66, r[1]+5, 50, 18, area.get()=="true", "Area", lambda e,v: area.set(["false","true"][bool(v)]))
        
                    # Object width
                    obwidth = Lux.Property(mat, kn+"prev_obwidth", 1.0)
                    Blender.Draw.Number("Width:", Lux.Events.LuxGui, r[0]+66, r[1]+78+voffset, 129, 18, obwidth.get(), 0.001, 10, "The width of the preview object in blender/lux 1m units", lambda e,v: obwidth.set(v))
        
                    # large/small size
                    Blender.Draw.Toggle("large", Lux.Events.LuxGui, r[0]+200, r[1]+78+voffset, 88, 18, large.get()=="true", "Large", lambda e,v: large.set(["false","true"][bool(v)]))
        
                    # Preview Quality
                    qs = ["low","medium","high","very high"]
                    Lux.scene = Blender.Scene.GetCurrent()
                    defprevmat = Lux.Property(Lux.scene, "defprevmat", "high")
                    quality = Lux.Property(mat, kn+"prev_quality", defprevmat.get())
                    Lux.TypedControls.OptionRect("quality", quality, qs, "  Quality", "select preview quality", r[0]+200, r[1]+100+voffset, 88, 18)
        
                    # Update preview
                    Blender.Draw.Button("Update Preview", Lux.Events.LuxGui, r[0]+120, r[1]+5, 167, 18, "Update Material Preview", lambda e,v: Preview_Update(mat, kn, defLarge, defType, texName, name, level))
        
                    # Reset depths after getRect()
                    gui.y -= 92+voffset
                    gui.y -= gui.h
                    gui.hmax = 18 + 4
        
    class Converter:
        
        def setFocus(target):
            currentscene = Blender.Scene.GetCurrent()
            camObj = currentscene.objects.camera # currentscene.getCurrentCamera()
            if target == "S":
                try:
                    refLoc = (Object.GetSelected()[0]).getLocation()
                except:
                    print "select an object to focus\n"
            elif target == "C":
                refLoc = Window.GetCursorPos()
            else:
                refLoc = (Object.Get(target)).getLocation()
            dist = Mathutils.Vector(refLoc) - Mathutils.Vector(camObj.getLocation())
            camDir = camObj.getMatrix()[2]*(-1.0)
            camObj.getData(mesh=1).dofDist = (camDir[0]*dist[0]+camDir[1]*dist[1]+camDir[2]*dist[2])/camDir.length # data
        
        # convert a Blender material to lux material
        def convertMaterial(mat):
            def dot(str):
                if str != "": return str+"."
                return str
            def ddot(str):
                if str != "": return str+":"
                return str
            def mapConstDict(value, constant_dict, lux_dict, default=None):
                for k,v in constant_dict.items():
                    if (v == value) and (lux_dict.has_key(k)):
                        return lux_dict[k]
                return default
        
            def convertMapping(name, tex):
                if tex.texco == Texture.TexCo["UV"]:
                    Lux.Property(mat, dot(name)+"mapping","").set("uv")
                    Lux.Property(mat, dot(name)+"uscale", 1.0).set(tex.size[0])
                    Lux.Property(mat, dot(name)+"vscale", 1.0).set(-tex.size[1])
                    Lux.Property(mat, dot(name)+"udelta", 0.0).set(tex.ofs[0]+0.5*(1.0-tex.size[0]))
                    Lux.Property(mat, dot(name)+"vdelta", 0.0).set(-tex.ofs[1]-0.5*(1.0-tex.size[1]))
                    if tex.mapping != Texture.Mappings["FLAT"]:
                        print "Material Conversion Warning: for UV-texture-input only FLAT mapping is supported\n" 
                else:
                    if tex.mapping == Texture.Mappings["FLAT"]:
                        Lux.Property(mat, dot(name)+"mapping","").set("planar")
                    elif tex.mapping == Texture.Mappings["TUBE"]:
                        Lux.Property(mat, dot(name)+"mapping","").set("cylindrical")
                    elif tex.mapping == Texture.Mappings["SPHERE"]:
                        Lux.Property(mat, dot(name)+"mapping","").set("spherical")
                    else: Lux.Property(mat, dot(name)+"mapping","").set("planar")
                Lux.Property(mat, dot(name)+"3dscale", "1.0 1.0 1.0").setVector((1.0/tex.size[0], 1.0/tex.size[1], 1.0/tex.size[2]))
                Lux.Property(mat, dot(name)+"3dtranslate", "0.0 0.0 0.0").setVector((-tex.ofs[0], -tex.ofs[1], -tex.ofs[2]))
        
            def convertColorband(colorband):
                # colorbands are not supported in lux - so lets extract a average low-side and high-side color
                cb = [colorband[0]] + colorband[:] + [colorband[-1]]
                cb[0][4], cb[-1][4] = 0.0, 1.0
                low, high = [0.0, 0.0, 0.0, 0.0], [0.0, 0.0, 0.0, 0.0]
                for i in range(1, len(cb)):
                    for c in range(4):
                        low[c] += (cb[i-1][c]*(1.0-cb[i-1][4]) + cb[i][c]*(1.0-cb[i][4])) * (cb[i][4]-cb[i-1][4])
                        high[c] += (cb[i-1][c]*cb[i-1][4] + cb[i][c]*cb[i][4]) * (cb[i][4]-cb[i-1][4])
                return low, high
        
            def createLuxTexture(name, tex):
                texture = tex.tex
                convertMapping(name, tex)
                if (texture.type == Texture.Types["IMAGE"]) and (texture.image) and (texture.image.filename!=""):
                    Lux.Property(mat, dot(name)+"texture", "").set("imagemap")
                    Lux.Property(mat, dot(name)+"filename", "").set(texture.image.filename)
                    Lux.Property(mat, dot(name)+"wrap", "").set(mapConstDict(texture.extend, Texture.ExtendModes, {"REPEAT":"repeat", "EXTEND":"clamp", "CLIP":"black"}, ""))
                else:
                    if tex.texco != Texture.TexCo["GLOB"]:
                        print "Material Conversion Warning: procedural textures supports global mapping only\n"
                    noiseDict = {"BLENDER":"blender_original", "CELLNOISE":"cell_noise", "IMPROVEDPERLIN":"improved_perlin", "PERLIN":"original_perlin", "VORONOICRACKLE":"voronoi_crackle", "VORONOIF1":"voronoi_f1", "VORONOIF2":"voronoi_f2", "VORONOIF2F1":"voronoi_f2f1", "VORONOIF3":"voronoi_f3", "VORONOIF4":"voronoi_f4"}
                    Lux.Property(mat, dot(name)+"bright", 1.0).set(texture.brightness)
                    Lux.Property(mat, dot(name)+"contrast", 1.0).set(texture.contrast)
                    if texture.type == Texture.Types["CLOUDS"]:
                        Lux.Property(mat, dot(name)+"texture", "").set("blender_clouds")
                        Lux.Property(mat, dot(name)+"mtype", "").set(mapConstDict(texture.stype, Texture.STypes, {"CLD_DEFAULT":"default", "CLD_COLOR":"color"}, ""))
                        Lux.Property(mat, dot(name)+"noisetype", "").set({"soft":"soft_noise", "hard":"hard_noise"}[texture.noiseType])
                        Lux.Property(mat, dot(name)+"noisesize", 0.25).set(texture.noiseSize)
                        Lux.Property(mat, dot(name)+"noisedepth", 2).set(texture.noiseDepth)
                        Lux.Property(mat, dot(name)+"noisebasis", "").set(mapConstDict(texture.noiseBasis, Texture.Noise, noiseDict, ""))
                    elif texture.type == Texture.Types["WOOD"]:
                        Lux.Property(mat, dot(name)+"texture", "").set("blender_wood")
                        Lux.Property(mat, dot(name)+"mtype", "").set(mapConstDict(texture.stype, Texture.STypes, {"WOD_BANDS":"bands", "WOD_RINGS":"rings", "WOD_BANDNOISE":"bandnoise", "WOD_RINGNOISE":"ringnoise"}, ""))
                        Lux.Property(mat, dot(name)+"noisebasis2", "").set(mapConstDict(texture.noiseBasis2, Texture.Noise, {"SINE":"sin", "SAW":"saw", "TRI":"tri"}, ""))
                        Lux.Property(mat, dot(name)+"noisebasis", "").set(mapConstDict(texture.noiseBasis, Texture.Noise, noiseDict, ""))
                        Lux.Property(mat, dot(name)+"noisetype", "").set({"soft":"soft_noise", "hard":"hard_noise"}[texture.noiseType])
                        Lux.Property(mat, dot(name)+"noisesize", 0.25).set(texture.noiseSize)
                        Lux.Property(mat, dot(name)+"turbulance", 0.25).set(texture.turbulence)
                    elif texture.type == Texture.Types["MUSGRAVE"]:
                        Lux.Property(mat, dot(name)+"texture", "").set("blender_musgrave")
                        Lux.Property(mat, dot(name)+"mtype", "").set(mapConstDict(texture.stype, Texture.STypes, {"MUS_MFRACTAL":"multifractal", "MUS_RIDGEDMF":"ridged_multifractal", "MUS_HYBRIDMF":"hybrid_multifractal", "MUS_HTERRAIN":"hetero_terrain", "MUS_FBM":"fbm"}, ""))
                        Lux.Property(mat, dot(name)+"noisebasis", "").set(mapConstDict(texture.noiseBasis, Texture.Noise, noiseDict, ""))
                        Lux.Property(mat, dot(name)+"noisesize", 0.25).set(texture.noiseSize)
                        # bug in blender python API: value of "hFracDim" is casted to Integer instead of Float (reported to Ideasman42 - will be fixed after Blender 2.47)
                        if texture.hFracDim != 0.0: Lux.Property(mat, dot(name)+"h", 1.0).set(texture.hFracDim) # bug in blender API, "texture.hFracDim" returns a Int instead of a Float
                        else: Lux.Property(mat, dot(name)+"h", 1.0).set(0.5) # use a default value
                        # bug in blender python API: values "offset" and "gain" are missing in Python-API (reported to Ideasman42 - will be fixed after Blender 2.47)
                        try:
                            Lux.Property(mat, dot(name)+"offset", 1.0).set(texture.offset)
                            Lux.Property(mat, dot(name)+"gain", 1.0).set(texture.gain)
                        except AttributeError: pass
                        Lux.Property(mat, dot(name)+"lacu", 2.0).set(texture.lacunarity)
                        Lux.Property(mat, dot(name)+"octs", 2.0).set(texture.octs)
                        Lux.Property(mat, dot(name)+"outscale", 1.0).set(texture.iScale)
                    elif texture.type == Texture.Types["MARBLE"]:
                        Lux.Property(mat, dot(name)+"texture", "").set("blender_marble")
                        Lux.Property(mat, dot(name)+"mtype", "").set(mapConstDict(texture.stype, Texture.STypes, {"MBL_SOFT":"soft", "MBL_SHARP":"sharp", "MBL_SHARPER":"sharper"}, ""))
                        Lux.Property(mat, dot(name)+"noisetype", "").set({"soft":"soft_noise", "hard":"hard_noise"}[texture.noiseType])
                        Lux.Property(mat, dot(name)+"turbulance", 0.25).set(texture.turbulence)
                        Lux.Property(mat, dot(name)+"noisedepth", 2).set(texture.noiseDepth)
                        Lux.Property(mat, dot(name)+"noisebasis", "").set(mapConstDict(texture.noiseBasis, Texture.Noise, noiseDict, ""))
                        Lux.Property(mat, dot(name)+"noisebasis2", "").set(mapConstDict(texture.noiseBasis2, Texture.Noise, {"SINE":"sin", "SAW":"saw", "TRI":"tri"}, ""))
                        Lux.Property(mat, dot(name)+"noisesize", 0.25).set(texture.noiseSize)
                    elif texture.type == Texture.Types["VORONOI"]:
                        Lux.Property(mat, dot(name)+"texture", "").set("blender_voronoi")
                        Lux.Property(mat, dot(name)+"distmetric", "").set({0:"actual_distance", 1:"distance_squared", 2:"manhattan", 3:"chebychev", 4:"minkovsky_half", 5:"minkovsky_four", 6:"minkovsky"}[texture.distMetric])
                        Lux.Property(mat, dot(name)+"outscale", 1.0).set(texture.iScale)
                        Lux.Property(mat, dot(name)+"noisesize", 0.25).set(texture.noiseSize)
                        Lux.Property(mat, dot(name)+"minkosky_exp", 2.5).set(texture.exp)
                        Lux.Property(mat, dot(name)+"w1", 1.0).set(texture.weight1)
                        Lux.Property(mat, dot(name)+"w2", 0.0).set(texture.weight2)
                        Lux.Property(mat, dot(name)+"w3", 0.0).set(texture.weight3)
                        Lux.Property(mat, dot(name)+"w4", 0.0).set(texture.weight4)
                    elif texture.type == Texture.Types["NOISE"]:
                        Lux.Property(mat, dot(name)+"texture", "").set("blender_noise")
                    elif texture.type == Texture.Types["DISTNOISE"]:
                        Lux.Property(mat, dot(name)+"texture", "").set("blender_distortednoise")
                        Lux.Property(mat, dot(name)+"distamount", 1.0).set(texture.distAmnt)
                        Lux.Property(mat, dot(name)+"noisesize", 0.25).set(texture.noiseSize)
                        Lux.Property(mat, dot(name)+"noisebasis", "").set(mapConstDict(texture.noiseBasis, Texture.Noise, noiseDict, ""))
                        Lux.Property(mat, dot(name)+"noisebasis2", "").set(mapConstDict(texture.noiseBasis2, Texture.Noise, noiseDict, ""))
                    elif texture.type == Texture.Types["MAGIC"]:
                        Lux.Property(mat, dot(name)+"texture", "").set("blender_magic")
                        Lux.Property(mat, dot(name)+"turbulance", 0.25).set(texture.turbulence)
                        Lux.Property(mat, dot(name)+"noisedepth", 2).set(texture.noiseDepth)
                    elif texture.type == Texture.Types["STUCCI"]:
                        Lux.Property(mat, dot(name)+"texture", "").set("blender_stucci")
                        Lux.Property(mat, dot(name)+"mtype", "").set(mapConstDict(texture.stype, Texture.STypes, {"STC_PLASTIC":"Plastic", "MSTC_WALLIN":"Wall In", "STC_WALLOUT":"Wall Out"}, ""))
                        Lux.Property(mat, dot(name)+"noisetype", "").set({"soft":"soft_noise", "hard":"hard_noise"}[texture.noiseType])
                        Lux.Property(mat, dot(name)+"noisesize", 0.25).set(texture.noiseSize)
                        Lux.Property(mat, dot(name)+"turbulance", 0.25).set(texture.turbulence)
                        Lux.Property(mat, dot(name)+"noisebasis", "").set(mapConstDict(texture.noiseBasis, Texture.Noise, noiseDict, ""))
                    elif texture.type == Texture.Types["BLEND"]:
                        Lux.Property(mat, dot(name)+"texture", "").set("blender_blend")
                        Lux.Property(mat, dot(name)+"type", "").set(mapConstDict(texture.stype, Texture.STypes, {"BLN_LIN":"lin", "BLN_QUAD":"quad", "BLN_EASE":"ease", "BLN_DIAG":"diag", "BLN_SPHERE":"sphere", "BLN_HALO":"halo", "BLN_RADIAL":"radial"}, ""))
                        Lux.Property(mat, dot(name)+"flipXY", "false").set({0:"false", 1:"true"}[texture.rot90])
                    else:
                        print "Material Conversion Warning: SORRY, this procedural texture isn\'t implemented in conversion\n"
        
            def convertTextures(basename, texs, type="float", channel="col", val=1.0):
                tex = texs.pop()
                texture = tex.tex
                isImagemap = (texture.type == Texture.Types["IMAGE"]) and (texture.image) and (texture.image.filename!="")
                if channel == "col":
                    if texture.flags & Texture.Flags["COLORBAND"] > 0:
                        cbLow, cbHigh = convertColorband(texture.colorband)
                        val1, alpha1, val2, alpha2 = (cbLow[0],cbLow[1],cbLow[2]), cbLow[3]*tex.colfac, (cbHigh[0], cbHigh[1], cbHigh[2]), cbHigh[3]*tex.colfac
                        if tex.noRGB:
                            lum1, lum2 = (val1[0]+val1[1]+val1[2])/3.0, (val2[0]+val2[1]+val2[2])/3.0
                            val1, val2 = (tex.col[0]*lum1,tex.col[1]*lum1,tex.col[2]*lum1), (tex.col[0]*lum2,tex.col[1]*lum2,tex.col[2]*lum2)
                    elif isImagemap and not(tex.noRGB): val1, alpha1, val2, alpha2 = (0.0,0.0,0.0), tex.colfac, (1.0,1.0,1.0), tex.colfac
                    else: val1, alpha1, val2, alpha2 = tex.col, 0.0, tex.col, tex.colfac
                elif channel == "nor": val1, alpha1, val2, alpha2 = tex.norfac * 0.01, 0.0, tex.norfac * 0.01, 1.0
                else: val1, alpha1, val2, alpha2 = 1.0, 0.0, 1.0, tex.varfac
                if (tex.neg)^((channel=="nor") and (tex.mtNor<0)): val1, alpha1, val2, alpha2 = val2, alpha2, val1, alpha1
                Lux.Property(mat, dot(basename)+"textured", "").set("true")
        
                name = basename
                if (alpha1 < 1.0) or (alpha2 < 1.0): # texture with transparency
                    Lux.Property(mat, dot(basename)+"texture", "").set("mix")
                    if alpha1 == alpha2: # constant alpha
                        Lux.Property(mat, ddot(basename)+"amount.value", 1.0).set(alpha1)
                    else:
                        createLuxTexture(ddot(basename)+"amount", tex)
                        Lux.Property(mat, ddot(basename)+"amount:tex1.value", 1.0).set(alpha1)
                        Lux.Property(mat, ddot(basename)+"amount:tex2.value", 1.0).set(alpha2)
                    # transparent to next texture
                    name = ddot(basename)+"tex1"
                    if len(texs) > 0:
                        convertTextures(ddot(basename)+"tex1", texs, type, channel, val)
                    else:
                        if type=="float": Lux.Property(mat, ddot(basename)+"tex1.value", 1.0).set(val);
                        else: Lux.Property(mat, ddot(basename)+"tex1.value", "1.0 1.0 1.0").setRGB((val[0], val[1], val[2]))
                    name = ddot(basename)+"tex2"
                if val1 == val2: # texture with different colors / value
                    if type == "col": Lux.Property(mat, dot(name)+"value", "1.0 1.0 1.0").setRGB(val1)
                    else: Lux.Property(mat, dot(name)+"value", 1.0).set(val1)
                else:
                    createLuxTexture(name, tex)
                    if type == "col": Lux.Property(mat, ddot(name)+"tex1.value", "1.0 1.0 1.0").setRGB(val1)
                    else: Lux.Property(mat, ddot(name)+"tex1.value", 1.0).set(val1)
                    if type == "col": Lux.Property(mat, ddot(name)+"tex2.value", "1.0 1.0 1.0").setRGB(val2)
                    else: Lux.Property(mat, ddot(name)+"tex2.value", 1.0).set(val2)
        
        
            def convertDiffuseTexture(name):
                texs = []
                for tex in mat.getTextures():
                    if tex and (tex.mapto & Texture.MapTo["COL"] > 0) and (tex.tex) and (tex.tex.type != Texture.Types["NONE"]): texs.append(tex)
                if len(texs) > 0:
                    Lux.Property(mat, name, "").setRGB((mat.ref, mat.ref, mat.ref))
                    convertTextures(name, texs, "col", "col", (mat.R, mat.G, mat.B))
            def convertSpecularTexture(name):
                texs = []
                for tex in mat.getTextures():
                    if tex and (tex.mapto & Texture.MapTo["CSP"] > 0) and (tex.tex) and (tex.tex.type != Texture.Types["NONE"]): texs.append(tex)
                if len(texs) > 0:
                    Lux.Property(mat, name, "").setRGB((mat.ref*mat.spec, mat.ref*mat.spec, mat.ref*mat.spec))
                    convertTextures(name, texs, "col", "col", (mat.specR, mat.specG, mat.specB))
            def convertMirrorTexture(name):
                texs = []
                for tex in mat.getTextures():
                    if tex and (tex.mapto & Texture.MapTo["CMIR"] > 0) and (tex.tex) and (tex.tex.type != Texture.Types["NONE"]): texs.append(tex)
                if len(texs) > 0:
                    Lux.Property(mat, name, "").setRGB((mat.ref, mat.ref, mat.ref))
                    convertTextures(name, texs, "col", "col", (mat.mirR, mat.mirG, mat.mirB))
            def convertBumpTexture(basename):
                texs = []
                for tex in mat.getTextures():
                    if tex and (tex.mapto & Texture.MapTo["NOR"] > 0) and (tex.tex) and (tex.tex.type != Texture.Types["NONE"]): texs.append(tex)
                if len(texs) > 0:
                    name = basename+":bumpmap"
                    Lux.Property(mat, basename+".usebump", "").set("true")
                    Lux.Property(mat, dot(name)+"textured", "").set("true")
                    Lux.Property(mat, name, "").set(1.0)
                    convertTextures(name, texs, "float", "nor", 0.0)
        
            def makeMatte(name):
                Lux.Property(mat, dot(name)+"type", "").set("matte")
                Lux.Property(mat, name+":Kd", "").setRGB((mat.R*mat.ref, mat.G*mat.ref, mat.B*mat.ref))
                convertDiffuseTexture(name+":Kd")
                convertBumpTexture(name)
            def makeGlossy(name, roughness):
                Lux.Property(mat, dot(name)+"type", "").set("glossy")
                Lux.Property(mat, name+":Kd", "").setRGB((mat.R*mat.ref, mat.G*mat.ref, mat.B*mat.ref))
                Lux.Property(mat, name+":Ks", "").setRGB((mat.specR*mat.spec*0.5, mat.specG*mat.spec*0.5, mat.specB*mat.spec*0.5))
                Lux.Property(mat, name+":uroughness", 0.0).set(roughness)
                Lux.Property(mat, name+":vroughness", 0.0).set(roughness)
                convertDiffuseTexture(name+":Kd")
                convertSpecularTexture(name+":Ks")
                convertBumpTexture(name)
            def makeMirror(name):
                Lux.Property(mat, dot(name)+"type", "").set("mirror")
                Lux.Property(mat, name+":Kr", "").setRGB((mat.mirR, mat.mirG, mat.mirB))
                convertMirrorTexture(name+":Kr")
                convertBumpTexture(name)
            def makeGlass(name):
                Lux.Property(mat, dot(name)+"type", "").set("glass")
                Lux.Property(mat, name+":Kr", "").setRGB((0.0, 0.0, 0.0))
                Lux.Property(mat, name+":Kt", "").setRGB((mat.R, mat.G, mat.B))
                Lux.Property(mat, name+":index.iorusepreset", "").set("false")
                Lux.Property(mat, name+":index", 0.0).set(mat.getIOR())
                convertMirrorTexture(name+":Kr")
                convertDiffuseTexture(name+":Kt")
                convertBumpTexture(name)
            def makeRoughglass(name, roughness):
                Lux.Property(mat, dot(name)+"type", "").set("roughglass")
                Lux.Property(mat, name+":Kr", "").setRGB((0.0, 0.0, 0.0))
                Lux.Property(mat, name+":Kt", "").setRGB((mat.R, mat.G, mat.B))
                Lux.Property(mat, name+":index.iorusepreset", "").set("false")
                Lux.Property(mat, name+":index", 0.0).set(mat.getIOR())
                Lux.Property(mat, name+":uroughness", 0.0).set(roughness)
                Lux.Property(mat, name+":vroughness", 0.0).set(roughness)
                convertMirrorTexture(name+":Kr")
                convertDiffuseTexture(name+":Kt")
                convertBumpTexture(name)
            print "convert Blender material \"%s\" to lux material"%(mat.name)
            mat.properties['luxblend'] = {}
            if mat.emit > 0.0001:
                Lux.Property(mat, "type", "").set("light")
                Lux.Property(mat, "light.l", "").setRGB((mat.R, mat.G, mat.B))
                Lux.Property(mat, "light.gain", 1.0).set(mat.emit)
                return
            alpha = mat.alpha
            if not(mat.mode & Material.Modes.RAYTRANSP): alpha = 1.0
            alpha0name, alpha1name = "", ""
            if (alpha > 0.0) and (alpha < 1.0):
                Lux.Property(mat, "type", "").set("mix")
                Lux.Property(mat, ":amount", 0.0).set(alpha)
                alpha0name, alpha1name = "mat2", "mat1"
            if alpha > 0.0:
                mirror = mat.rayMirr
                if not(mat.mode & Material.Modes.RAYMIRROR): mirror = 0.0
                mirror0name, mirror1name = alpha1name, alpha1name
                if (mirror > 0.0) and (mirror < 1.0):
                    Lux.Property(mat, dot(alpha1name)+"type", "").set("mix")
                    Lux.Property(mat, alpha1name+":amount", 0.0).set(1.0 - mirror)
                    mirror0name, mirror1name = ddot(alpha1name)+"mat1", ddot(alpha1name)+"mat2"
                if mirror > 0.0:
                    if mat.glossMir < 1.0: makeGlossy(mirror1name, 1.0-mat.glossMir**2)
                    else: makeMirror(mirror1name)
                if mirror < 1.0:
                    if mat.spec > 0.0: makeGlossy(mirror0name, 1.0/mat.hard)
                    else: makeMatte(mirror0name)
            if alpha < 1.0:
                if mat.glossTra < 1.0: makeRoughnessGlass(alpha0name, 1.0-mat.glossTra**2)
                else: makeGlass(alpha0name)
        
        def convertAllMaterials():
            for mat in Material.Get(): convertMaterial(mat)
            
        ### MatTex functions ###
        ### MatTex : is a dictionary of material or texture properties
        def getMatTex(mat, basekey='', tex=False):
            global usedproperties, usedpropertiesfilterobj
            usedproperties = {}
            usedpropertiesfilterobj = mat
            luxMaterial(mat)
            dict = {}
            for k,v in usedproperties.items():
                if k[:len(basekey)]==basekey:
                    if k[-9:] != '.textured':
                        name = k[len(basekey):]
                        if name == ".type": name = "type"
                        dict[name] = v
            dict["__type__"] = ["material","texture"][bool(tex)]
            return dict
        
        def putMatTex(mat, dict, basekey='', tex=None):
            if dict and (tex!=None) and (tex ^ (dict.has_key("__type__") and (dict["__type__"]=="texture"))):
                print "ERROR: Can't apply %s as %s"%(["texture","material"][bool(tex)],["material","texture"][bool(tex)])
                return
            if dict:
                # remove all current properties in mat that starts with basekey
                try:
                    d = mat.properties['luxblend']
                    for k,v in d.convert_to_pyobject().items():
                        kn = k
                        if k[:1]=="__hash:":    # decode if entry is hashed (cause of 32chars limit)
                            l = v.split(" = ")
                            kn = l[0]
                        if kn[:len(basekey)]==basekey:
                            del mat.properties['luxblend'][k]
                except: pass
                # assign loaded properties
                for k,v in dict.items():
                    try:
                        if (basekey!="") and (k=="type"): k = ".type"
                        Lux.Property(mat, basekey+k, None).set(v)
                        if k[-8:] == '.texture':
                            Lux.Property(mat, basekey+k[:-8]+'.textured', 'false').set('true')
                    except: pass
        
        
        LBX_VERSION = '0.7'
        
        def MatTex2str(d, tex = None):
            global LBX_VERSION
            
            if LBX_VERSION == '0.6':
            
                if tex is not None and tex == True:
                    d['LUX_DATA'] = 'TEXTURE'
                else:
                    d['LUX_DATA'] = 'MATERIAL'
                
                d['LUX_VERSION'] = '0.6'
                return str(d).replace(", \'", ",\n\'")
            
            elif LBX_VERSION == '0.7':
                definition = []
                for k in d.keys():
                    if type(d[k]) == types.IntType:
                        t = 'integer'
                    if type(d[k]) == types.FloatType:
                        t = 'float'
                    if type(d[k]) == types.BooleanType:
                        t = 'bool'
                    if type(d[k]) == types.StringType:
                        l=None
                        try:
                            l = d[k].split(" ")
                        except: pass
                        if l==None or len(l)!=3:
                            t = 'string'
                        else:
                            t = 'vector'
                        
                    definition.append([ t, k, d[k] ])
                
                
                lbx = {
                    'type': d['__type__'],
                    'version': '0.7',
                    'definition': definition,
                    'metadata': [
                        ['string', 'generator', 'luxblend'],
                    ]
                }
                return str(lbx).replace("], \'", "],\n\'").replace("[","\n\t[")
        
        def str2MatTex(s, tex = None):    # todo: this is not absolutely save from attacks!!!
            global LBX_VERSION
            
            s = s.strip()
            if (s[0]=='{') and (s[-1]=='}'):
                d = eval(s, dict(__builtins__=None,True=True,False=False))
                if type(d)==types.DictType:
                    
                    
                    if LBX_VERSION == '0.6':
                    
                        if tex is not None and tex == True:
                            test_str = 'TEXTURE'
                        else:
                            test_str = 'MATERIAL'
                            
                        if   ('LUX_DATA' in d.keys() and d['LUX_DATA'] == test_str) \
                        and  ('LUX_VERSION' in d.keys() and (d['LUX_VERSION'] == '0.6' or d['LUX_VERSION'] == 0.6)):
                            return d
                        else:
                            reason = 'Missing/incorrect metadata'
                            
                    elif LBX_VERSION == '0.7':
                        
                        def lb_list_to_dict(list):
                            d = {}
                            for t, k, v in list:
                                if t == 'float':
                                    v = float(v)
                                    
                                d[k] = v
                            return d
                        
                        if   ('version' in d.keys() and d['version'] in ['0.6', '0.7']) \
                        and  ('type' in d.keys() and d['type'] in ['material', 'texture']) \
                        and  ('definition' in d.keys()):
                            
                            
                            try:
                                definition = lb_list_to_dict(d['definition'])
                                
                                if 'metadata' in d.keys():
                                    definition.update( lb_list_to_dict(d['metadata']) )
                                
                                return definition
                            except:
                                reason = 'Incorrect LBX definition data'
                        else: 
                            reason = 'Missing/incorrect metadata'
                    else:
                        reason = 'Unknown LBX version'
                else:
                    reason = 'Not a parsed dict'
            else:
                reason = 'Not a stored dict'
                    
                    
            print "ERROR: string to material/texture conversion failed: %s" % reason
            return None

            
    class lrmdb:
        ConnectLrmdb = False
        @staticmethod
        def download(mat, id):
            if id.isalnum():
                try:
                    HOST = 'www.luxrender.net'
                    GET = '/lrmdb/en/material/download/'+id
                    PORT = 80
                    Blender.Window.DrawProgressBar(0.0,'Getting Material #'+id)
                    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                    sock.connect((HOST, PORT))
                    sock.send("GET %s HTTP/1.0\r\nHost: %s\r\n\r\n" % (GET, HOST))
                    data = sock.recv(1024)
                    str = ""
                    while len(data):
                        str += data
                        data = sock.recv(1024)
                    sock.close()
                    if str.split("\n", 1)[0].find("200") < 0:
                        print "ERROR: server error: %s"%(str.split("\n",1)[0])
                        return None
                    str = (str.split("\r\n\r\n")[1]).strip()
                    if (str[0]=="{") and (str[-1]=="}"):
                        return str2MatTex(str)
                    print "ERROR: downloaded data is not a material or texture"
                except:
                    print "ERROR: download failed"
                finally:
                    Blender.Window.DrawProgressBar(1.0,'')
            else:
                print "ERROR: material id is not valid"
                return None
        
        def __init__(self):
            ### Connect LRMDB ###
            try:
                # try import of libraries
                import socket, xmlrpclib
                self.ConnectLrmdb = True
            except:
                print "WARNING: LRMDB support not available"


    class Homeless:
        def luxMaterialBlock(name, luxname, key, mat, gui=None, level=0, str_opt=""):
            global icon_mat, icon_matmix, icon_map3dparam
            def c(t1, t2):
                return (t1[0]+t2[0], t1[1]+t2[1])
            str = ""
            if key == "": keyname = kn = name
            else: keyname = kn = "%s:%s"%(key, name)
            if kn != "": kn += "."
            if keyname == "": matname = mat.getName()
            else: matname = "%s:%s"%(mat.getName(), keyname)
        
            if mat:
                mattype = Lux.Property(mat, kn+"type", "matte")
                # Set backwards compatibility of glossy material from plastic and substrate
                if(mattype.get() == "substrate" or mattype.get() == "plastic"):
                    mattype.set("glossy")
        
                materials = ["carpaint","glass","matte","mattetranslucent","metal","mirror","roughglass","shinymetal","glossy","mix","null"]
                if level == 0: materials = ["light","portal","boundvolume"]+materials
                if gui:
                    icon = icon_mat
                    if mattype.get() == "mix": icon = icon_matmix
                    if level == 0: gui.newline("Material type:", 12, level, icon, [0.75,0.5,0.25])
                    else: gui.newline(name+":", 12, level, icon, scalelist([0.75,0.6,0.25],2.0/(level+2)))
        
        
                link = Lux.TypedControls.Option("type", mattype, materials, "  TYPE", "select material type")
                showadvanced = Lux.Property(mat, kn+"showadvanced", "false")
                Lux.TypedControls.Bool("advanced", showadvanced, "Advanced", "Show advanced options", 0.6)
                showhelp = Lux.Property(mat, kn+"showhelp", "false")
                Lux.TypedControls.Help("help", showhelp, "Help", "Show Help Information",  0.4)
        
                # show copy/paste menu button
                if gui: Blender.Draw.PushButton(">", Lux.Events.LuxGui, gui.xmax+gui.h, gui.y-gui.h, gui.h, gui.h, "Menu", lambda e,v: showMatTexMenu(mat,keyname,False))
        
                # Draw Material preview option
                showmatprev = False
                if level == 0:
                    showmatprev = True
                if gui: luxPreview(mat, keyname, 0, showmatprev, True, None, gui, level, [0.746, 0.625, 0.5])
        
        
                if gui: gui.newline()
                has_object_options   = 0 # disable object options by default
                has_bump_options     = 0 # disable bump mapping options by default
                has_emission_options = 0 # disable emission options by default
                if mattype.get() == "mix":
                    (str,link) = c((str,link), luxFloatTexture("amount", keyname, 0.5, 0.0, 1.0, "amount", "The degree of mix between the two materials", mat, gui, level+1))
                    (str,link) = c((str,link), luxMaterialBlock("mat1", "namedmaterial1", keyname, mat, gui, level+1))
                    (str,link) = c((str,link), luxMaterialBlock("mat2", "namedmaterial2", keyname, mat, gui, level+1))
                    has_bump_options = 0
                    has_object_options = 1
                    has_emission_options = 1
        
                if mattype.get() == "light":
                    lightgroup = Lux.Property(mat, kn+"light.lightgroup", "default")
                    link = "LightGroup \"%s\"\n"%lightgroup.get()
                    link += "AreaLightSource \"area\""
                    (str,link) = c((str,link), luxLight("", kn, mat, gui, level))
                    has_bump_options = 0
                    has_object_options = 1
                    has_emission_options = 0
        
                if mattype.get() == "boundvolume":
                    link = ""
                    voltype = Lux.Property(mat, kn+"vol.type", "homogeneous")
                    vols = ["homogeneous", "exponential"]
                    vollink = Lux.TypedControls.Option("type", voltype, vols, "type", "")
                    if voltype.get() == "homogeneous":
                        link = "Volume \"homogeneous\""
                    if voltype.get() == "exponential":
                        link = "Volume \"exponential\""
        
                    if gui: gui.newline("absorption:", 0, level+1)
                    link += Lux.TypedControls.RGB("sigma_a", Lux.Property(mat, kn+"vol.sig_a", "1.0 1.0 1.0"), 1.0, "sigma_a", "The absorption cross section")
                    if gui: gui.newline("scattering:", 0, level+1)
                    link += Lux.TypedControls.RGB("sigma_s", Lux.Property(mat, kn+"vol.sig_b", "0.0 0.0 0.0"), 1.0, "sigma_b", "The scattering cross section")
                    if gui: gui.newline("emission:", 0, level+1)
                    link += Lux.TypedControls.RGB("Le", Lux.Property(mat, kn+"vol.le", "0.0 0.0 0.0"), 1.0, "Le", "The volume's emission spectrum")
                    if gui: gui.newline("assymetry:", 0, level+1)
                    link += Lux.TypedControls.Float("g", Lux.Property(mat, kn+"vol.g", 0.0), 0.0, 100.0, "g", "The phase function asymmetry parameter")
        
                    if voltype.get() == "exponential":
                        if gui: gui.newline("form:", 0, level+1)
                        link += Lux.TypedControls.Float("a", Lux.Property(mat, kn+"vol.a", 1.0), 0.0, 100.0, "a/scale", "exponential::a parameter in the ae^{-bh} formula")
                        link += Lux.TypedControls.Float("b", Lux.Property(mat, kn+"vol.b", 2.0), 0.0, 100.0, "b/falloff", "exponential::b parameter in the ae^{-bh} formula")
                        if gui: gui.newline("updir:", 0, level+1)
                        link += Lux.TypedControls.Vector("updir", Lux.Property(mat, kn+"vol.updir", "0 0 1"), -1.0, 1.0, "updir", "Up direction vector", 2.0)
        
                    link += str_opt
        
                    has_bump_options = 0
                    has_object_options = 0
                    has_emission_options = 0
        
                    return (str, link)
        
                if mattype.get() == "carpaint":
                    if gui: gui.newline("name:", 0, level+1)
                    carname = Lux.Property(mat, kn+"carpaint.name", "white")
                    cars = ["","ford f8","polaris silber","opel titan","bmw339","2k acrylack","white","blue","blue matte"]
                    carlink = Lux.TypedControls.Option("name", carname, cars, "name", "")
                    if carname.get() == "":
                        (str,link) = c((str,link), luxSpectrumTexture("Kd", keyname, "1.0 1.0 1.0", 1.0, "diffuse", "", mat, gui, level+1))
                        (str,link) = c((str,link), luxSpectrumTexture("Ks1", keyname, "1.0 1.0 1.0", 1.0, "specular1", "", mat, gui, level+1))
                        (str,link) = c((str,link), luxSpectrumTexture("Ks2", keyname, "1.0 1.0 1.0", 1.0, "specular2", "", mat, gui, level+1))
                        (str,link) = c((str,link), luxSpectrumTexture("Ks3", keyname, "1.0 1.0 1.0", 1.0, "specular3", "", mat, gui, level+1))
                        (str,link) = c((str,link), luxFloatTexture("R1", keyname, 1.0, 0.0, 1.0, "R1", "", mat, gui, level+1))
                        (str,link) = c((str,link), luxFloatTexture("R2", keyname, 1.0, 0.0, 1.0, "R2", "", mat, gui, level+1))
                        (str,link) = c((str,link), luxFloatTexture("R3", keyname, 1.0, 0.0, 1.0, "R3", "", mat, gui, level+1))
                        (str,link) = c((str,link), luxFloatTexture("M1", keyname, 1.0, 0.0, 1.0, "M1", "", mat, gui, level+1))
                        (str,link) = c((str,link), luxFloatTexture("M2", keyname, 1.0, 0.0, 1.0, "M2", "", mat, gui, level+1))
                        (str,link) = c((str,link), luxFloatTexture("M3", keyname, 1.0, 0.0, 1.0, "M3", "", mat, gui, level+1))
                    else: link += carlink
                    has_bump_options = 1
                    has_object_options = 1
                    has_emission_options = 1
                if mattype.get() == "glass":
                    (str,link) = c((str,link), luxSpectrumTexture("Kr", keyname, "1.0 1.0 1.0", 1.0, "reflection", "", mat, gui, level+1))
                    (str,link) = c((str,link), luxSpectrumTexture("Kt", keyname, "1.0 1.0 1.0", 1.0, "transmission", "", mat, gui, level+1))
                    (str,link) = c((str,link), luxIORFloatTexture("index", keyname, 1.5, 1.0, 6.0, "IOR", "", mat, gui, level+1))
                    architectural = Lux.Property(mat, keyname+".architectural", "false")
                    link += Lux.TypedControls.Bool("architectural", architectural, "architectural", "Enable architectural glass", 2.0)
                    if architectural.get() == "false":
                        chromadisp = Lux.Property(mat, keyname+".chromadisp", "false")
                        Lux.TypedControls.Bool("chromadisp", chromadisp, "Dispersive Refraction", "Enable Chromatic Dispersion", 2.0)
                        if chromadisp.get() == "true":
                            (str,link) = c((str,link), luxCauchyBFloatTexture("cauchyb", keyname, 0.0, 0.0, 1.0, "cauchyb", "", mat, gui, level+1))
                        thinfilm = Lux.Property(mat, keyname+".thinfilm", "false")
                        Lux.TypedControls.Bool("thinfilm", thinfilm, "Thin Film Coating", "Enable Thin Film Coating", 2.0)
                        if thinfilm.get() == "true":
                            (str,link) = c((str,link), luxFloatSliderTexture("film", keyname, 200.0, 1.0, 1500.0, "film", "thickness of film coating in nanometers", mat, gui, level+1))
                            (str,link) = c((str,link), luxIORFloatTexture("filmindex", keyname, 1.5, 1.0, 6.0, "film IOR", "film coating index of refraction", mat, gui, level+1))
                    has_bump_options = 1
                    has_object_options = 1
                    has_emission_options = 1
                if mattype.get() == "matte":
                    orennayar = Lux.Property(mat, keyname+".orennayar", "false")
                    (str,link) = c((str,link), luxSpectrumTexture("Kd", keyname, "1.0 1.0 1.0", 1.0, "diffuse", "", mat, gui, level+1))
                    Lux.TypedControls.Bool("orennayar", orennayar, "Oren-Nayar", "Enable Oren-Nayar BRDF", 2.0)
                    if orennayar.get() == "true":
                        (str,link) = c((str,link), luxFloatTexture("sigma", keyname, 0.0, 0.0, 100.0, "sigma", "sigma value for Oren-Nayar BRDF", mat, gui, level+1))
                    has_bump_options = 1
                    has_object_options = 1
                    has_emission_options = 1
                if mattype.get() == "mattetranslucent":
                    orennayar = Lux.Property(mat, keyname+".orennayar", "false")
                    (str,link) = c((str,link), luxSpectrumTexture("Kr", keyname, "1.0 1.0 1.0", 1.0, "reflection", "", mat, gui, level+1))
                    (str,link) = c((str,link), luxSpectrumTexture("Kt", keyname, "1.0 1.0 1.0", 1.0, "transmission", "", mat, gui, level+1))
                    Lux.TypedControls.Bool("orennayar", orennayar, "Oren-Nayar", "Enable Oren-Nayar BRDF", 2.0)
                    if orennayar.get() == "true":
                        (str,link) = c((str,link), luxFloatTexture("sigma", keyname, 0.0, 0.0, 100.0, "sigma", "", mat, gui, level+1))
                    has_bump_options = 1
                    has_object_options = 1
                    has_emission_options = 1
                if mattype.get() == "metal":
                    if gui: gui.newline("name:", 0, level+1)
                    metalname = Lux.Property(mat, kn+"metal.name", "")
                    metals = ["aluminium","amorphous carbon","silver","gold","copper"]
        
                    if not(metalname.get() in metals):
                        metals.append(metalname.get())
                    metallink = Lux.TypedControls.Option("name", metalname, metals, "name", "", 1.88)
                    if gui: Blender.Draw.Button("...", Lux.Events.LuxGui, gui.x, gui.y-gui.h, gui.h, gui.h, "click to select a nk file",lambda e,v:Window.FileSelector(lambda s:metalname.set(s), "Select nk file"))
                    link += luxstr(metallink)
                    anisotropic = Lux.Property(mat, kn+"metal.anisotropic", "false")
                    if gui:
                        gui.newline("")
                        Blender.Draw.Toggle("A", Lux.Events.LuxGui, gui.x-gui.h, gui.y-gui.h, gui.h, gui.h, anisotropic.get()=="true", "anisotropic roughness", lambda e,v:anisotropic.set(["false","true"][bool(v)]))
                    if anisotropic.get()=="true":
                        (str,link) = c((str,link), luxExponentTexture("uroughness", keyname, 0.002, 0.0, 1.0, "u-exponent", "", mat, gui, level+1))
                        (str,link) = c((str,link), luxExponentTexture("vroughness", keyname, 0.002, 0.0, 1.0, "v-exponent", "", mat, gui, level+1))
                    else:
                        (s, l) = luxExponentTexture("uroughness", keyname, 0.002, 0.0, 1.0, "exponent", "", mat, gui, level+1)
                        (str,link) = c((str,link), (s, l))
                        link += l.replace("uroughness", "vroughness", 1)
                        
                    has_bump_options = 1
                    has_object_options = 1
                    has_emission_options = 1
                if mattype.get() == "mirror":
                    (str,link) = c((str,link), luxSpectrumTexture("Kr", keyname, "1.0 1.0 1.0", 1.0, "reflection", "", mat, gui, level+1))
                    thinfilm = Lux.Property(mat, keyname+".thinfilm", "false")
                    Lux.TypedControls.Bool("thinfilm", thinfilm, "Thin Film Coating", "Enable Thin Film Coating", 2.0)
                    if thinfilm.get() == "true":
                        (str,link) = c((str,link), luxFloatSliderTexture("film", keyname, 200.0, 1.0, 1500.0, "film", "thickness of film coating in nanometers", mat, gui, level+1))
                        (str,link) = c((str,link), luxIORFloatTexture("filmindex", keyname, 1.5, 1.0, 6.0, "film IOR", "film coating index of refraction", mat, gui, level+1))
        
                    has_bump_options = 1
                    has_object_options = 1
                    has_emission_options = 1
                if mattype.get() == "roughglass":
                    (str,link) = c((str,link), luxSpectrumTexture("Kr", keyname, "1.0 1.0 1.0", 1.0, "reflection", "", mat, gui, level+1))
                    (str,link) = c((str,link), luxSpectrumTexture("Kt", keyname, "1.0 1.0 1.0", 1.0, "transmission", "", mat, gui, level+1))
                    anisotropic = Lux.Property(mat, kn+"roughglass.anisotropic", "false")
                    if gui:
                        gui.newline("")
                        Blender.Draw.Toggle("A", Lux.Events.LuxGui, gui.x-gui.h, gui.y-gui.h, gui.h, gui.h, anisotropic.get()=="true", "anisotropic roughness", lambda e,v:anisotropic.set(["false","true"][bool(v)]))
                    if anisotropic.get()=="true":
                        (str,link) = c((str,link), luxExponentTexture("uroughness", keyname, 0.002, 0.0, 1.0, "u-exponent", "", mat, gui, level+1))
                        (str,link) = c((str,link), luxExponentTexture("vroughness", keyname, 0.002, 0.0, 1.0, "v-exponent", "", mat, gui, level+1))
                    else:
                        (s, l) = luxExponentTexture("uroughness", keyname, 0.002, 0.0, 1.0, "exponent", "", mat, gui, level+1)
                        (str,link) = c((str,link), (s, l))
                        link += l.replace("uroughness", "vroughness", 1)
                    (str,link) = c((str,link), luxIORFloatTexture("index", keyname, 1.5, 1.0, 6.0, "IOR", "", mat, gui, level+1))
                    chromadisp = Lux.Property(mat, keyname+".chromadisp", "false")
                    Lux.TypedControls.Bool("chromadisp", chromadisp, "Dispersive Refraction", "Enable Chromatic Dispersion", 2.0)
                    if chromadisp.get() == "true":
                        (str,link) = c((str,link), luxCauchyBFloatTexture("cauchyb", keyname, 0.0, 0.0, 1.0, "cauchyb", "", mat, gui, level+1))
                    has_bump_options = 1
                    has_object_options = 1
                    has_emission_options = 1
                if mattype.get() == "shinymetal":
                    (str,link) = c((str,link), luxSpectrumTexture("Kr", keyname, "1.0 1.0 1.0", 1.0, "reflection", "", mat, gui, level+1))
                    (str,link) = c((str,link), luxSpectrumTexture("Ks", keyname, "1.0 1.0 1.0", 1.0, "specular", "", mat, gui, level+1))
                    anisotropic = Lux.Property(mat, kn+"shinymetal.anisotropic", "false")
                    if gui:
                        gui.newline("")
                        Blender.Draw.Toggle("A", Lux.Events.LuxGui, gui.x-gui.h, gui.y-gui.h, gui.h, gui.h, anisotropic.get()=="true", "anisotropic roughness", lambda e,v:anisotropic.set(["false","true"][bool(v)]))
                    if anisotropic.get()=="true":
                        (str,link) = c((str,link), luxExponentTexture("uroughness", keyname, 0.002, 0.0, 1.0, "u-exponent", "", mat, gui, level+1))
                        (str,link) = c((str,link), luxExponentTexture("vroughness", keyname, 0.002, 0.0, 1.0, "v-exponent", "", mat, gui, level+1))
                    else:
                        (s, l) = luxExponentTexture("uroughness", keyname, 0.002, 0.0, 1.0, "exponent", "", mat, gui, level+1)
                        (str,link) = c((str,link), (s, l))
                        link += l.replace("uroughness", "vroughness", 1)
        
                    thinfilm = Lux.Property(mat, keyname+".thinfilm", "false")
                    Lux.TypedControls.Bool("thinfilm", thinfilm, "Thin Film Coating", "Enable Thin Film Coating", 2.0)
                    if thinfilm.get() == "true":
                        (str,link) = c((str,link), luxFloatSliderTexture("film", keyname, 200.0, 1.0, 1500.0, "film", "thickness of film coating in nanometers", mat, gui, level+1))
                        (str,link) = c((str,link), luxIORFloatTexture("filmindex", keyname, 1.5, 1.0, 6.0, "film IOR", "film coating index of refraction", mat, gui, level+1))
        
                    has_bump_options = 1
                    has_object_options = 1
                    has_emission_options = 1
                if mattype.get() == "glossy":
                    (str,link) = c((str,link), luxSpectrumTexture("Kd", keyname, "1.0 1.0 1.0", 1.0, "diffuse", "", mat, gui, level+1))
                    useior = Lux.Property(mat, keyname+".useior", "false")
                    if gui:
                        gui.newline("")
                        Blender.Draw.Toggle("I", Lux.Events.LuxGui, gui.x-gui.h, gui.y-gui.h, gui.h, gui.h, useior.get()=="true", "Use IOR/Reflective index input", lambda e,v:useior.set(["false","true"][bool(v)]))
                    if useior.get() == "true":
                        (str,link) = c((str,link), luxIORFloatTexture("index", keyname, 1.5, 1.0, 50.0, "IOR", "", mat, gui, level+1))
                        link += " \"color Ks\" [1.0 1.0 1.0]"    
                    else:
                        (str,link) = c((str,link), luxSpectrumTexture("Ks", keyname, "1.0 1.0 1.0", 1.0, "specular", "", mat, gui, level+1))
                        link += " \"float index\" [0.0]"    
                    anisotropic = Lux.Property(mat, kn+"glossy.anisotropic", "false")
                    if gui:
                        gui.newline("")
                        Blender.Draw.Toggle("A", Lux.Events.LuxGui, gui.x-gui.h, gui.y-gui.h, gui.h, gui.h, anisotropic.get()=="true", "anisotropic roughness", lambda e,v:anisotropic.set(["false","true"][bool(v)]))
                    if anisotropic.get()=="true":
                        (str,link) = c((str,link), luxExponentTexture("uroughness", keyname, 0.002, 0.0, 1.0, "u-exponent", "", mat, gui, level+1))
                        (str,link) = c((str,link), luxExponentTexture("vroughness", keyname, 0.002, 0.0, 1.0, "v-exponent", "", mat, gui, level+1))
                    else:
                        (s, l) = luxExponentTexture("uroughness", keyname, 0.002, 0.0, 1.0, "exponent", "", mat, gui, level+1)
                        (str,link) = c((str,link), (s, l))
                        link += l.replace("uroughness", "vroughness", 1)
        
                    absorption = Lux.Property(mat, keyname+".useabsorption", "false")
                    Lux.TypedControls.Bool("absorption", absorption, "Absorption", "Enable Coating Absorption", 2.0)
                    if absorption.get() == "true":
                        (str,link) = c((str,link), luxSpectrumTexture("Ka", keyname, "1.0 1.0 1.0", 1.0, "absorption", "", mat, gui, level+1))
                        (str,link) = c((str,link), luxFloatTexture("d", keyname, 0.15, 0.0, 1.0, "depth", "", mat, gui, level+1))
                    has_bump_options = 1
                    has_object_options = 1
                    has_emission_options = 1
        
        
                # Bump mapping options (common)
                if (has_bump_options == 1):
                    usebump = Lux.Property(mat, keyname+".usebump", "false")
                    Lux.TypedControls.Bool("usebump", usebump, "Bump Map", "Enable Bump Mapping options", 2.0)
                    if usebump.get() == "true":
                        (str,link) = c((str,link), luxFloatTexture("bumpmap", keyname, 0.0, 0.0, 1.0, "bumpmap", "", mat, gui, level+1))
        
                # emission options (common)
                if (level == 0):
                    if (has_emission_options == 1):
                        if gui: gui.newline("", 2, level, None, [0.6,0.6,0.4])
                        useemission = Lux.Property(mat, "emission", "false")
                        Lux.TypedControls.Bool("useemission", useemission, "Emission", "Enable emission options", 2.0)
                        if useemission.get() == "true":
                            # emission GUI is here but lux export will be done later 
                            luxLight("", "", mat, gui, level)
                    else: Lux.Property(mat, "emission", "false").set("false") # prevent from exporting later
        
                # transformation options (common)
                if (level == 0):
                    if gui: gui.newline("", 2, level, None, [0.6,0.6,0.4])
                    usetransformation = Lux.Property(mat, "transformation", "false")
                    Lux.TypedControls.Bool("usetransformation", usetransformation, "Texture Transformation", "Enable transformation option", 2.0)
                    if usetransformation.get() == "true":
                        scale = Lux.Property(mat, "3dscale", 1.0)
                        rotate = Lux.Property(mat, "3drotate", "0 0 0")
                        translate = Lux.Property(mat, "3dtranslate", "0 0 0")
                        if gui:
                            gui.newline("scale:", -2, level, icon_map3dparam)
                            Lux.TypedControls.VectorUniform("scale", scale, 0.001, 1000.0, "scale", "scale-vector", 2.0)
                            gui.newline("rot:", -2, level, icon_map3dparam)
                            Lux.TypedControls.Vector("rotate", rotate, -360.0, 360.0, "rotate", "rotate-vector", 2.0)
                            gui.newline("move:", -2, level, icon_map3dparam)
                            Lux.TypedControls.Vector("translate", translate, -1000.0, 1000.0, "move", "translate-vector", 2.0)
                        str = ("TransformBegin\n\tScale %f %f %f\n"%( 1.0/scale.getVector()[0],1.0/scale.getVector()[1],1.0/scale.getVector()[2] ))+("\tRotate %f 1 0 0\n\tRotate %f 0 1 0\n\tRotate %f 0 0 1\n"%rotate.getVector())+("\tTranslate %f %f %f\n"%translate.getVector()) + str + "TransformEnd\n"
        
                # Object options (common)
                if (level == 0) and (has_object_options == 1):
                    if gui: gui.newline("Mesh:", 2, level, icon, [0.6,0.6,0.4])
                    usesubdiv = Lux.Property(mat, "subdiv", "false")
                    Lux.TypedControls.Bool("usesubdiv", usesubdiv, "Subdivision", "Enable Loop Subdivision options", 1.0)
                    usedisp = Lux.Property(mat, "dispmap", "false")
                    Lux.TypedControls.Bool("usedisp", usedisp, "Displacement Map", "Enable Displacement mapping options", 1.0)
                    if usesubdiv.get() == "true" or usedisp.get() == "true":
                        Lux.TypedControls.Int("sublevels", Lux.Property(mat, "sublevels", 2), 0, 12, "sublevels", "The number of levels of object subdivision", 2.0)
                        sharpbound = Lux.Property(mat, "sharpbound", "false")
                        Lux.TypedControls.Bool("sharpbound", sharpbound, "Sharpen Bounds", "Sharpen boundaries during subdivision", 1.0)
                        nsmooth = Lux.Property(mat, "nsmooth", "true")
                        Lux.TypedControls.Bool("nsmooth", nsmooth, "Smooth", "Smooth faces during subdivision", 1.0)
                    if usedisp.get() == "true":
                        (str,ll) = c((str,link), luxDispFloatTexture("dispmap", keyname, 0.1, -10, 10.0, "dispmap", "Displacement Mapping amount", mat, gui, level+1))
                        Lux.TypedControls.Float("sdoffset",  Lux.Property(mat, "sdoffset", 0.0), 0.0, 1.0, "Offset", "Offset for displacement map", 2.0)
                        usesubdiv.set("true");
        
                if mattype.get() == "light":
                    return (str, link)
        
                str += "MakeNamedMaterial \"%s\"%s\n"%(matname, link)
            return (str, " \"string %s\" [\"%s\"]"%(luxname, matname))
        
        
        
                
        # DH - ORPHAN, not found in original LuxBlend
#        def luxVolume(mat, gui=None):
#            str = ""
#            if mat:
#                (str, link) = luxMaterialBlock("", "", "", mat, gui, 0)
#                Lux.Property(mat, "link", "").set("".join(link))
#            return str
        
        
        
        luxclipboard = None # global variable for copy/paste content
        def showMatTexMenu(mat, basekey='', tex=False):
            global luxclipboard, ConnectLrmdb
            if tex: menu="Texture menu:%t"
            else: menu="Material menu:%t"
            menu += "|Copy%x1"
            try:
                if luxclipboard and (not(tex) ^ (luxclipboard["__type__"]=="texture")): menu +="|Paste%x2"
            except: pass
            if (tex):
                menu += "|Load LBT%x3|Save LBT%x4"
            else:
                menu += "|Load LBM%x3|Save LBM%x4"
            if  Lux.lrmdb.ConnectLrmdb: menu += "|Download from DB%x5" #not(tex) and
        
        #    menu += "|%l|dump material%x99|dump clipboard%x98"
            r = Blender.Draw.PupMenu(menu)
            if r==1:
                luxclipboard = getMatTex(mat, basekey, tex)
            elif r==2: putMatTex(mat, luxclipboard, basekey, tex)
            elif r==3: 
                Lux.scene = Blender.Scene.GetCurrent()
                if (tex):
                    Window.FileSelector(lambda fn:loadMatTex(mat, fn, basekey, tex), "load texture", Lux.Property(Lux.scene, "lux", "").get()+os.sep+".lbt")
                else:
                    Window.FileSelector(lambda fn:loadMatTex(mat, fn, basekey, tex), "load material", Lux.Property(Lux.scene, "lux", "").get()+os.sep+".lbm")
            elif r==4:
                Lux.scene = Blender.Scene.GetCurrent()
                if (tex):
                    Window.FileSelector(lambda fn:saveMatTex(mat, fn, basekey, tex), "save texture", Lux.Property(Lux.scene, "lux", "").get()+os.sep+".lbt")
                else:
                    Window.FileSelector(lambda fn:saveMatTex(mat, fn, basekey, tex), "save material", Lux.Property(Lux.scene, "lux", "").get()+os.sep+".lbm")
            elif r==5:
                if not tex:
                    id = Blender.Draw.PupStrInput("Material ID:", "", 32)
                else:
                    id = Blender.Draw.PupStrInput("Texture ID:", "", 32)
                if id: putMatTex(mat, Lux.lrmdb.download(mat, id), basekey, tex)
        #    elif r==99:
        #        for k,v in mat.properties['luxblend'].convert_to_pyobject().items(): print k+"="+repr(v)
        #    elif r==98:
        #        for k,v in luxclipboard.items(): print k+"="+repr(v)
        #    print ""
            Blender.Draw.Redraw()
        
        
        def saveMatTex(mat, fn, basekey='', tex=False):
            d = getMatTex(mat, basekey, tex)
            file = open(fn, 'w')
            file.write(MatTex2str(d, tex))
            file.close()
            if Lux.i_gui: Blender.Draw.Redraw()
        
        
        def loadMatTex(mat, fn, basekey='', tex=None):
            file = open(fn, 'r')
            data = file.read()
            file.close()
            data = str2MatTex(data, tex)
            putMatTex(mat, data, basekey, tex) 
            if Lux.i_gui: Blender.Draw.Redraw()
        
        
        activemat = None
        
        def setactivemat(mat):
            global activemat
            activemat = mat

#------------------------------------------------------------------------------ 
# START !
#------------------------------------------------------------------------------ 

## Parse command line arguments for batch mode rendering if supplied
#try:
#    batchindex = osys.argv.index('--batch')
#    pyargs = osys.argv[osys.argv.index('--batch')+1:]
#except: pyargs = []
#
#if (pyargs != []) and (batchindex != 0):
#    print "\n\nLuxBlend CVS - BATCH mode\n"
#    #Lux.i_gui = False
#
#    scene = Blender.Scene.GetCurrent()
#    context = scene.getRenderingContext()
#
#    luxpath = ""
#    import getopt
#    o, a = getopt.getopt(pyargs, 's:e:o:t:l:',["scale=","haltspp=","run=", "lbm=", "lbt="])
#
#    opts = {}
#    for k,v in o:
#        opts[k] = v
#
#    if (opts.has_key('--run')) and (opts['--run'] == 'false'):
#        print "Run: false"
#        Lux.Prop(scene, "run", "true").set("false")
#    else:
#        Lux.Prop(scene, "run", "true").set("true")
#
#    if opts.has_key('--scale'):
#        print "Zoom: %s" %opts['--scale']
#        Lux.Prop(scene, "film.scale", "100 %").set(opts['--scale'])
#
#    if opts.has_key('--haltspp'):
#        print "haltspp: %s" %opts['--haltspp']
#        Lux.Prop(scene, "haltspp", 0).set(int(opts['--haltspp']))
#
#    if opts.has_key('-s'):
#        print "Start frame: %s" %opts['-s']
#        context.startFrame(int(opts['-s']))
#    else:
#        print "Error: Start frame not supplied (-s)"; osys.exit(1)
#    if opts.has_key('-e'):
#        print "End frame: %s" %opts['-e']
#        context.endFrame(int(opts['-e']))
#    else:
#        print "Error: End frame not supplied (-e)"; osys.exit(1)
#    if opts.has_key('-l'):
#        print "Path to lux binary: %s" %opts['-l']
#        luxpathprop = Lux.Prop(scene, "lux", "")
#        luxpathprop.set(opts['-l'])
#    else:
#        print "Error: path to lux binary not supplied (-l)"; osys.exit(1)    
#    if opts.has_key('-o'):
#        print "Image output path: %s" %opts['-o']
#        Lux.Prop(scene, "overrideoutputpath", "").set(opts['-o'])
#    else:
#        print "Error: image output path not supplied (-o)"; osys.exit(1)    
#    if opts.has_key('-t'):
#        print "Temporary export path: %s" %opts['-t']
#        Lux.Prop(scene, "datadir", "").set(opts['-t'])
#    else:
#        print "Error: Temporary export path not supplied (-t)"; osys.exit(1)            
#    
#    if opts.has_key('--lbm'):
#        print "Load material: %s" %opts['--lbm']
#        mat = Material.Get("Material")
#        if mat: loadMatTex(mat, opts['--lbm'])
#        else:
#            print "Error: No material with name \"Material\" found (--lbm)"; osys.exit(1)
#            
#    if opts.has_key('--lbt'):
#        print "Load material: %s" %opts['--lbt']
#        mat = Material.Get("Material")
#        if mat: loadMatTex(mat, opts['--lbt'], ':Kd')
#        else:
#            print "Error: No material with name \"Material\" found (--lbt)"; osys.exit(1)
#
#    Lux.Launch.ExportAnim(False, False, False) # as by zukazuka (http://www.luxrender.net/forum/viewtopic.php?f=11&t=1288)
#    osys.exit(0)
#
#else:
#    print "\n\nLuxBlend CVS - UI mode\n"
#    #Lux.i_gui = True
#    
#    Blender.Draw.Register(luxDraw, luxEvent, luxButtonEvt) # init GUI
#
#    luxpathprop = Lux.Prop(Blender.Scene.GetCurrent(), "lux", "")
#    luxpath = luxpathprop.get()
#    luxrun = Lux.Prop(Blender.Scene.GetCurrent(), "run", True).get()
#    checkluxpath = Lux.Prop(Blender.Scene.GetCurrent(), "checkluxpath", True).get()
#
#    if checkluxpath and luxrun:
#        if (luxpath is None) or (sys.exists(luxpath)<=0):
#            # luxpath not valid, so delete entry from .blend scene file ...
#            luxpathprop.delete()
#            # and re-get luxpath, so we get the path from default-settings
#            luxpath = luxpathprop.get()
#            if (luxpath is None) or (sys.exists(luxpath)<=0):
#                print "WARNING: LuxPath \"%s\" is not valid\n"%(luxpath)
#                Lux.scene = Blender.Scene.GetCurrent()
#                if Lux.scene:
#                    r = Blender.Draw.PupMenu("Installation: Set path to the lux render software?%t|Yes%x1|No%x0|Never%x2")
#                    if r == 1:
#                        Window.FileSelector(lambda s:Lux.Prop(Lux.scene, "lux", "").set(Blender.sys.dirname(s)+os.sep), "Select file in Lux path")
#                        saveluxdefaults()
#                    if r == 2:
#                        newluxdefaults["checkluxpath"] = False
#                        saveluxdefaults()
#    else    :
#        print "Lux path check disabled\n"