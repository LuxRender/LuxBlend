#!BPY
"""Registration info for Blender menus:
Name: 'LuxBlend CVS Exporter'
Blender: 248
Group: 'Render'
Tooltip: 'Export/Render to LuxRender CVS scene format (.lxs)'
"""
#
# ***** BEGIN GPL LICENSE BLOCK *****
#
# --------------------------------------------------------------------------
# LuxBlend CVS exporter
# --------------------------------------------------------------------------
#
# Authors:
# radiance, zuegs, ideasman42, luxblender, dougal2
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
# --------------------------------------------------------------------------




######################################################
# Importing modules
######################################################

import math
import time
import os
import sys as osys
import types
import subprocess
import Blender
from Blender import Mesh, Scene, Object, Material, Texture, Window, sys, Draw, BGL, Mathutils, Lamp, Image




######################################################
# Functions
######################################################

# New name based on old with a different extension
def newFName(ext):
    return Blender.Get('filename')[: -len(Blender.Get('filename').split('.', -1)[-1]) ] + ext


###### RGC ##########################
def rg(col):
    scn = Scene.GetCurrent()
    if luxProp(scn, "RGC", "true").get()=="true":
        gamma = luxProp(scn, "film.gamma", 2.2).get()
    else:
        gamma = 1.0
    ncol = col**gamma
    if luxProp(scn, "colorclamp", "false").get()=="true":
        ncol = ncol * 0.9
        if ncol > 0.9:
            ncol = 0.9
        if ncol < 0.0:
            ncol = 0.0
    return ncol

def texturegamma():
    scn = Scene.GetCurrent()
    if luxProp(scn, "RGC", "true").get()=="true":
        return luxProp(scn, "film.gamma", 2.2).get()
    else:
        return 1.0

def exportMaterial(mat):
    str = "# Material '%s'\n" %mat.name
    return str+luxMaterial(mat)+"\n"


def exportMaterialGeomTag(mat):
    return "%s\n"%(luxProp(mat, "link", "").get())




################################################################


dummyMat = 2394723948 # random identifier for dummy material
clayMat = None

#-------------------------------------------------
# getMaterials(obj)
# helper function to get the material list of an object in respect of obj.colbits
#-------------------------------------------------
def getMaterials(obj, compress=False):
    global clayMat
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
        print "Warning: object %s has no material assigned"%(obj.getName())
        mats = []
    # clay option
    if luxProp(Scene.GetCurrent(), "clay", "false").get()=="true":
        if clayMat==None: clayMat = Material.New("lux_clayMat")
        for i in range(len(mats)):
            if mats[i]:
                mattype = luxProp(mats[i], "type", "").get()
                if (mattype not in ["portal","light","boundvolume"]): mats[i] = clayMat
    return mats



######################################################
# luxExport class
######################################################

class luxExport:
    #-------------------------------------------------
    # __init__
    # initializes the exporter object
    #-------------------------------------------------
    def __init__(self, scene):
        self.scene = scene
        self.camera = scene.objects.camera
        self.objects = []
        self.portals = []
        self.volumes = []
        self.meshes = {}
        self.materials = []
        self.lights = []

    #-------------------------------------------------
    # analyseObject(self, obj, matrix, name)
    # called by analyseScene to build the lists before export
    #-------------------------------------------------
    def analyseObject(self, obj, matrix, name, isOriginal=True):
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
                mats = getMaterials(obj)
                if (len(mats)>0) and (mats[0]!=None) and ((mats[0].name=="PORTAL") or (luxProp(mats[0], "type", "").get()=="portal")):
                    self.portals.append([obj, matrix])
                elif (len(mats)>0) and (luxProp(mats[0], "type", "").get()=="boundvolume"):
                    self.volumes.append([obj, matrix])
                else:
                    for mat in mats:
                        if (mat!=None) and (mat not in self.materials):
                            self.materials.append(mat)
                        if (mat!=None) and ((luxProp(mat, "type", "").get()=="light") or (luxProp(mat, "emission", "false").get()=="true")):
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

    #-------------------------------------------------
    # analyseScene(self)
    # this function builds the lists of object, lights, meshes and materials before export
    #-------------------------------------------------
    def analyseScene(self):
        light = False
        for obj in self.scene.objects:
            if ((obj.Layers & self.scene.Layers) > 0):
                if self.analyseObject(obj, obj.getMatrix(), obj.getName()): light = True
        return light

    #-------------------------------------------------
    # exportMaterialLink(self, file, mat)
    # exports material link. LuxRender "Material" 
    #-------------------------------------------------
    def exportMaterialLink(self, file, mat):
        if mat == dummyMat:
            file.write("\tMaterial \"matte\" # dummy material\n")
        else:
            file.write("\t%s"%exportMaterialGeomTag(mat)) # use original methode



    #-------------------------------------------------
    # exportMaterial(self, file, mat)
    # exports material. LuxRender "Texture" 
    #-------------------------------------------------
    def exportMaterial(self, file, mat):
        file.write("\t%s"%exportMaterial(mat)) # use original methode        
    
    #-------------------------------------------------
    # exportMaterials(self, file)
    # exports materials to the file
    #-------------------------------------------------
    def exportMaterials(self, file):
        for mat in self.materials:
            print "material %s"%(mat.getName())
            self.exportMaterial(file, mat)

    #-------------------------------------------------
    # getMeshType(self, vertcount, mat)
    # returns type of mesh as string to use depending on thresholds
    #-------------------------------------------------
    def getMeshType(self, vertcount, mat):
        scn = Scene.GetCurrent()
        if mat != dummyMat:
            usesubdiv = luxProp(mat, "subdiv", "false")
            usedisp = luxProp(mat, "dispmap", "false")
            sharpbound = luxProp(mat, "sharpbound", "false")
            nsmooth = luxProp(mat, "nsmooth", "true")
            sdoffset = luxProp(mat, "sdoffset", 0.0)
            dstr = ""
            if usesubdiv.get() == "true":
                nlevels = luxProp(mat, "sublevels", 1)
                dstr += "\"loopsubdiv\" \"integer nlevels\" [%i] \"bool dmnormalsmooth\" [\"%s\"] \"bool dmsharpboundary\" [\"%s\"]"% (nlevels.get(), nsmooth.get(), sharpbound.get())
            
            if usedisp.get() == "true":
                dstr += " \"string displacementmap\" [\"%s::dispmap.scale\"] \"float dmscale\" [-1.0] \"float dmoffset\" [%f]"%(mat.getName(), sdoffset.get()) # scale is scaled in texture

            if dstr != "": return dstr

        return "\"trianglemesh\""

    #-------------------------------------------------
    # exportMesh(self, file, mesh, mats, name, portal)
    # exports mesh to the file without any optimization
    #-------------------------------------------------
    def exportMesh(self, file, mesh, mats, name, portal=False):
        if mats == []:
            mats = [dummyMat]
        for matIndex in range(len(mats)):
            if (mats[matIndex] != None):
                mesh_str = getMeshType(len(mesh.verts), mats[matIndex])
                if (portal):
                    file.write("\tShape %s \"integer indices\" [\n"% mesh_str)
                else:
                    self.exportMaterialLink(file, mats[matIndex])
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

    #-------------------------------------------------
    # exportMeshOpt(self, file, mesh, mats, name, portal, optNormals)
    # exports mesh to the file with optimization.
    # portal: export without normals and UVs
    # optNormals: speed and filesize optimization, flat faces get exported without normals
    #-------------------------------------------------
    def exportMeshOpt(self, file, mesh, mats, name, portal=False, optNormals=True):
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
                    self.exportMaterialLink(file, mats[matIndex])
                for shape in shapeList:
                    blenderExportVertexMap = []
                    exportVerts = []
                    exportFaces = []
                    ffaces = [f for f in mesh.faces if (f.mat == matIndex) and (f.smooth in smoothFltr[shape])]
                    for face in ffaces:
                        exportVIndices = []
                        index = 0
                        for vertex in face:
#                            v = [vertex.co[0], vertex.co[1], vertex.co[2]]
                            v = [vertex.co]
                            if normalFltr[shape]:
                                if (face.smooth):
#                                    v.extend(vertex.no)
                                    v.append(vertex.no)
                                else:
#                                    v.extend(face.no)
                                    v.append(face.no)
                            if (uvFltr[shape]) and (mesh.faceUV):
#                                v.extend(face.uv[index])
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
#                        for vertex in exportVerts:
#                            file.write("%f %f %f\n"%(vertex[0], vertex[1], vertex[2]))
                        file.write("".join(["%f %f %f\n"%tuple(vertex[0]) for vertex in exportVerts]))
                        if normalFltr[shape]:
                            file.write("\t] \"normal N\" [\n")
#                            for vertex in exportVerts:
#                                file.write("%f %f %f\n"%(vertex[3], vertex[4], vertex[5]))
                            file.write("".join(["%f %f %f\n"%tuple(vertex[1]) for vertex in exportVerts])) 
                            if (uvFltr[shape]) and (mesh.faceUV):
                                file.write("\t] \"float uv\" [\n")
#                                for vertex in exportVerts:
#                                    file.write("%f %f\n"%(vertex[6], vertex[7]))
                                file.write("".join(["%f %f\n"%tuple(vertex[2]) for vertex in exportVerts])) 
                        else:            
                            if (uvFltr[shape]) and (mesh.faceUV):
                                file.write("\t] \"float uv\" [\n")
#                                for vertex in exportVerts:
#                                    file.write("%f %f\n"%(vertex[3], vertex[4]))
                                file.write("".join(["%f %f\n"%tuple(vertex[1]) for vertex in exportVerts])) 
                        file.write("\t]\n")
                        print "  shape(%s): %d vertices, %d faces"%(shapeText[shape], len(exportVerts), len(exportFaces))
    
    #-------------------------------------------------
    # exportMeshes(self, file)
    # exports meshes that uses instancing (meshes that are used by at least "instancing_threshold" objects)
    #-------------------------------------------------
    def exportMeshes(self, file):
        scn = Scene.GetCurrent()
        instancing_threshold = luxProp(scn, "instancing_threshold", 2).get()
        mesh_optimizing = luxProp(scn, "mesh_optimizing", True).get()
        mesh = Mesh.New('')
        for (mesh_name, objs) in self.meshes.items():
            allow_instancing = True
            mats = getMaterials(objs[0]) # mats = obj.getData().getMaterials()
            for mat in mats: # don't instance if one of the materials is emissive
                if (mat!=None) and (luxProp(mat, "type", "").get()=="light"):
                    allow_instancing = False
            for obj in objs: # don't instance if the objects with same mesh uses different materials
                ms = getMaterials(obj)
                if ms <> mats:
                    allow_instancing = False
            if obj.modifiers.__len__() > 0:
                allow_instancing = False
            if allow_instancing and (len(objs) > instancing_threshold):
                del self.meshes[mesh_name]
                mesh.getFromObject(objs[0], 0, 1)
                print "blender-mesh: %s (%d vertices, %d faces)"%(mesh_name, len(mesh.verts), len(mesh.faces))
                file.write("ObjectBegin \"%s\"\n"%mesh_name)
                if (mesh_optimizing):
                    self.exportMeshOpt(file, mesh, mats, mesh_name)
                else:
                    self.exportMesh(file, mesh, mats, mesh_name)
                file.write("ObjectEnd # %s\n\n"%mesh_name)
        mesh.verts = None

    #-------------------------------------------------
    # exportObjects(self, file)
    # exports objects to the file
    #-------------------------------------------------
    def exportObjects(self, file):
        scn = Scene.GetCurrent()
        cam = scn.getCurrentCamera().data
        objectmblur = luxProp(cam, "objectmblur", "true")
        usemblur = luxProp(cam, "usemblur", "false")
        mesh_optimizing = luxProp(scn, "mesh_optimizing", True).get()
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
                    mats = getMaterials(obj)
                    print "  blender-mesh: %s (%d vertices, %d faces)"%(mesh_name, len(mesh.verts), len(mesh.faces))
                    file.write("ObjectBegin \"%s\"\n"%mesh_name)
                    if (mesh_optimizing):
                        self.exportMeshOpt(file, mesh, mats, mesh_name)
                    else:
                        self.exportMesh(file, mesh, mats, mesh_name)
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
                mats = getMaterials(obj)
                print "  blender-mesh: %s (%d vertices, %d faces)"%(mesh_name, len(mesh.verts), len(mesh.faces))
                if (mesh_optimizing):
                    self.exportMeshOpt(file, mesh, mats, mesh_name)
                else:
                    self.exportMesh(file, mesh, mats, mesh_name)
            else:
                print "  instance %s"%(mesh_name)
                if motion:
                    file.write("\tMotionInstance \"%s\" 0.0 1.0 \"%s\"\n"%(mesh_name, obj.getName()+"_motion"))
                else:
                    file.write("\tObjectInstance \"%s\"\n"%mesh_name)
            file.write("AttributeEnd\n\n")
        mesh.verts = None

    #-------------------------------------------------
    # exportPortals(self, file)
    # exports portals objects to the file
    #-------------------------------------------------
    def exportPortals(self, file):
        scn = Scene.GetCurrent()
        mesh_optimizing = luxProp(scn, "mesh_optimizing", True).get()
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
                self.exportMeshOpt(file, mesh, mats, mesh_name, True)
            else:
                self.exportMesh(file, mesh, mats, mesh_name, True)
        mesh.verts = None

    #-------------------------------------------------
    # exportLights(self, file)
    # exports lights to the file
    #-------------------------------------------------
    def exportLights(self, file):
        for [obj, matrix] in self.lights:
            ltype = obj.getData(mesh=1).getType() # data
            if (ltype == Lamp.Types["Lamp"]) or (ltype == Lamp.Types["Spot"]) or (ltype == Lamp.Types["Area"]):
                print "light: %s"%(obj.getName())
                if ltype == Lamp.Types["Area"]:
                    (str, link) = luxLight("", "", obj, None, 0)
                    file.write(str)
                if ltype == Lamp.Types["Area"]: file.write("AttributeBegin # %s\n"%obj.getName())
                else: file.write("TransformBegin # %s\n"%obj.getName())
                file.write("\tTransform [%s %s %s %s  %s %s %s %s  %s %s %s %s  %s %s %s %s]\n"\
                    %(matrix[0][0], matrix[0][1], matrix[0][2], matrix[0][3],\
                      matrix[1][0], matrix[1][1], matrix[1][2], matrix[1][3],\
                      matrix[2][0], matrix[2][1], matrix[2][2], matrix[2][3],\
                        matrix[3][0], matrix[3][1], matrix[3][2], matrix[3][3]))
                col = obj.getData(mesh=1).col # data
                energy = obj.getData(mesh=1).energy # data
                if ltype == Lamp.Types["Lamp"]:
                    lightgroup = luxProp(obj, "light.lightgroup", "default")
                    file.write("LightGroup \"%s\"\n"%lightgroup.get())
                    (str, link) = luxLamp("", "", obj, None, 0)
                    file.write(str+"LightSource \"point\""+link+"\n")
                if ltype == Lamp.Types["Spot"]:
                    (str, link) = luxSpot("", "", obj, None, 0)
                    file.write(str)
                    proj = luxProp(obj, "light.usetexproj", "false")
                    lightgroup = luxProp(obj, "light.lightgroup", "default")
                    file.write("LightGroup \"%s\"\n"%lightgroup.get())
                    if(proj.get() == "true"):
                        file.write("Rotate 180 0 1 0\n")
                        file.write("LightSource \"projection\" \"float fov\" [%f]"%(obj.getData(mesh=1).spotSize))
                    else:
                        file.write("LightSource \"spot\" \"point from\" [0 0 0] \"point to\" [0 0 -1] \"float coneangle\" [%f] \"float conedeltaangle\" [%f]"\
                            %(obj.getData(mesh=1).spotSize*0.5, obj.getData(mesh=1).spotSize*0.5*obj.getData(mesh=1).spotBlend)) # data
                    file.write(link+"\n")
                if ltype == Lamp.Types["Area"]:
                    lightgroup = luxProp(obj, "light.lightgroup", "default")
                    file.write("LightGroup \"%s\"\n"%lightgroup.get())
                    file.write("\tAreaLightSource \"area\"")
                    file.write(link)
#                    file.write(luxLight("", "", obj, None, 0))
                    file.write("\n")
                    areax = obj.getData(mesh=1).getAreaSizeX()
                    # lamps "getAreaShape()" not implemented yet - so we can't detect shape! Using square as default
                    # todo: ideasman42
                    if (True): areay = areax
                    else: areay = obj.getData(mesh=1).getAreaSizeY()
                    file.write('\tShape "trianglemesh" "integer indices" [0 1 2 0 2 3] "point P" [-%(x)f %(y)f 0.0 %(x)f %(y)f 0.0 %(x)f -%(y)f 0.0 -%(x)f -%(y)f 0.0]\n'%{"x":areax/2, "y":areay/2})
                if ltype == Lamp.Types["Area"]: file.write("AttributeEnd # %s\n"%obj.getName())
                else: file.write("TransformEnd # %s\n"%obj.getName())
                file.write("\n")


    #-------------------------------------------------
    # exportVolumes(self, file)
    # exports volumes to the file
    #-------------------------------------------------
    def exportVolumes(self, file):
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
            mats = getMaterials(obj)
            if (len(mats)>0) and (mats[0]!=None) and (luxProp(mats[0], "type", "").get()=="boundvolume"):
                mat = mats[0]
                (str, link) = luxMaterialBlock("", "", "", mat, None, 0, str_opt)
                file.write("%s"%link)
                file.write("\n\n")


# Note - radiance - this is a work in progress
def luxFlashBlock(camObj):
    str = ""
    str += "CoordSysTransform \"camera\"\n"

    str += "Texture \"camflashtex\" \"color\" \"blackbody\" \"float temperature\" [5500.0]"
    str += "AreaLightSource \"area\" \"texture L\" [\"camflashtex\"] \"float power\" [100.000000] \"float efficacy\" [17.000000] \"float gain\" [1.000000]\n"

    up = 10.0

    str += "Shape \"trianglemesh\" \"integer indices\" [ 0 1 2 0 2 3 ] \"point P\" [ 0.014 0.012 0.0   0.006 0.012 0.0   0.006 0.008 0.0   0.014 0.008 0.0 ]\n"

    return str


######################################################
# EXPORT
######################################################

def save_lux(filename, unindexedname):
    
    export_total_steps = 12.0
    
    global meshlist, matnames, geom_filename, geom_pfilename, mat_filename, mat_pfilename, vol_filename, vol_pfilename, LuxIsGUI

    print("Lux Render Export started...\n")
    time1 = Blender.sys.time()
    scn = Scene.GetCurrent()

    filepath = os.path.dirname(filename)
    filebase = os.path.splitext(os.path.basename(filename))[0]

    geom_filename = os.path.join(filepath, filebase + "-geom.lxo")
    geom_pfilename = filebase + "-geom.lxo"

    mat_filename = os.path.join(filepath, filebase + "-mat.lxm")
    mat_pfilename = filebase + "-mat.lxm"
    
    vol_filename = os.path.join(filepath, filebase + "-vol.lxv")
    vol_pfilename = filebase + "-vol.lxv"

    ### Zuegs: initialization for export class
    export = luxExport(Blender.Scene.GetCurrent())

    # check if a light is present
    envtype = luxProp(scn, "env.type", "infinite").get()
    if envtype == "sunsky":
        sun = None
        for obj in scn.objects:
            if (obj.getType() == "Lamp") and ((obj.Layers & scn.Layers) > 0):
                if obj.getData(mesh=1).getType() == 1: # sun object # data
                    sun = obj
    if not(export.analyseScene()) and not(envtype == "infinite") and not((envtype == "sunsky") and (sun != None)):
        print("ERROR: No light source found")
        Draw.PupMenu("ERROR: No light source found%t|OK%x1")
        return False

    if LuxIsGUI: DrawProgressBar(0.0/export_total_steps,'Setting up Scene file')
    if luxProp(scn, "lxs", "true").get()=="true":
        ##### Determine/open files
        print("Exporting scene to '" + filename + "'...\n")
        file = open(filename, 'w')

        ##### Write Header ######
        file.write("# Lux Render CVS Scene File\n")
        file.write("# Exported by LuxBlend Blender Exporter\n")
        file.write("\n")
    
        ##### Write camera ######
        camObj = scn.getCurrentCamera()

        if LuxIsGUI: DrawProgressBar(1.0/export_total_steps,'Exporting Camera')
        if camObj:
            print "processing Camera..."
            cam = camObj.data
            cammblur = luxProp(cam, "cammblur", "true")
            usemblur = luxProp(cam, "usemblur", "false")

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
            file.write(luxCamera(camObj.data, scn.getRenderingContext()))
            if motion:
                file.write("\n   \"string endtransform\" [\"CameraEndTransform\"]")
            file.write("\n")
        file.write("\n")
    
        if LuxIsGUI: DrawProgressBar(2.0/export_total_steps,'Exporting Film Settings')
        ##### Write film ######
        file.write(luxFilm(scn))
        file.write("\n")

        if LuxIsGUI: DrawProgressBar(3.0/export_total_steps,'Exporting Pixel Filter')
        ##### Write Pixel Filter ######
        file.write(luxPixelFilter(scn))
        file.write("\n")
    
        if LuxIsGUI: DrawProgressBar(4.0/export_total_steps,'Exporting Sampler')
        ##### Write Sampler ######
        file.write(luxSampler(scn))
        file.write("\n")
    
        if LuxIsGUI: DrawProgressBar(5.0/export_total_steps,'Exporting Surface Integrator')
        ##### Write Surface Integrator ######
        file.write(luxSurfaceIntegrator(scn))
        file.write("\n")
        
        if LuxIsGUI: DrawProgressBar(6.0/export_total_steps,'Exporting Volume Integrator')
        ##### Write Volume Integrator ######
        file.write(luxVolumeIntegrator(scn))
        file.write("\n")
        
        if LuxIsGUI: DrawProgressBar(7.0/export_total_steps,'Exporting Accelerator')
        ##### Write Acceleration ######
        file.write(luxAccelerator(scn))
        file.write("\n")    
    
        ########## BEGIN World
        file.write("\n")
        file.write("WorldBegin\n")
        file.write("\n")

        ########## World scale
        #scale = luxProp(scn, "global.scale", 1.0).get()
        #if scale != 1.0:
        #    # TODO: not working yet !!!
        #    # TODO: propabily scale needs to be applyed on camera coords too 
        #    file.write("Transform [%s 0.0 0.0 0.0  0.0 %s 0.0 0.0  0.0 0.0 %s 0.0  0.0 0.0 0 1.0]\n"%(scale, scale, scale))
        #    file.write("\n")
        
        if LuxIsGUI: DrawProgressBar(8.0/export_total_steps,'Exporting Environment')
        ##### Write World Background, Sunsky or Env map ######
        env = luxEnvironment(scn)
        if env != "":
            file.write("AttributeBegin\n")
            file.write(env)
            export.exportPortals(file)
            file.write("AttributeEnd\n")
            file.write("\n")    

    # Note - radiance - this is a work in progress
#        flash = luxFlashBlock(camObj)
#        if flash != "":
#            file.write("# Camera flash lamp\n")
#            file.write("AttributeBegin\n")
#            #file.write("CoordSysTransform \"camera\"\n")
#            file.write(flash)
#            file.write("AttributeEnd\n\n")

        #### Write material & geometry file includes in scene file
        file.write("Include \"%s\"\n\n" %(mat_pfilename))
        file.write("Include \"%s\"\n\n" %(geom_pfilename))
        file.write("Include \"%s\"\n\n" %(vol_pfilename))
        
        #### Write End Tag
        file.write("WorldEnd\n\n")
        file.close()
        
    if luxProp(scn, "lxm", "true").get()=="true":
        if LuxIsGUI: DrawProgressBar(9.0/export_total_steps,'Exporting Materials')
        ##### Write Material file #####
        print("Exporting materials to '" + mat_filename + "'...\n")
        mat_file = open(mat_filename, 'w')
        mat_file.write("")
        export.exportMaterials(mat_file)
        mat_file.write("")
        mat_file.close()
    
    if luxProp(scn, "lxo", "true").get()=="true":
        if LuxIsGUI: DrawProgressBar(10.0/export_total_steps,'Exporting Geometry')
        ##### Write Geometry file #####
        print("Exporting geometry to '" + geom_filename + "'...\n")
        geom_file = open(geom_filename, 'w')
        meshlist = []
        geom_file.write("")
        export.exportLights(geom_file)
        export.exportMeshes(geom_file)
        export.exportObjects(geom_file)
        geom_file.write("")
        geom_file.close()

    if luxProp(scn, "lxv", "true").get()=="true":
        if LuxIsGUI: DrawProgressBar(11.0/export_total_steps,'Exporting Volumes')
        ##### Write Volume file #####
        print("Exporting volumes to '" + vol_filename + "'...\n")
        vol_file = open(vol_filename, 'w')
        meshlist = []
        vol_file.write("")
        export.exportVolumes(vol_file)
        vol_file.write("")
        vol_file.close()


    if LuxIsGUI: DrawProgressBar(12.0/export_total_steps,'Export Finished')
    print("Finished.\n")
    del export

    time2 = Blender.sys.time()
    print("Processing time: %f\n" %(time2-time1))
    return True



#########################################################################
###     LAUNCH LuxRender AND RENDER CURRENT SCENE
#########################################################################

def launchLux(filename):
    ostype = osys.platform
    #get blenders 'bpydata' directory
    datadir=Blender.Get("datadir")
    
    scn = Scene.GetCurrent()
    ic = luxProp(scn, "lux", "").get()
    ic = Blender.sys.dirname(ic) + os.sep + "luxrender"
    if ostype == "win32": ic = ic + ".exe"
    if ostype == "darwin": ic = ic + ".app/Contents/MacOS/luxrender"
    checkluxpath = luxProp(scn, "checkluxpath", True).get()
    if checkluxpath:
        if sys.exists(ic) != 1:
            Draw.PupMenu("Error: Lux renderer not found. Please set path on System page.%t|OK")
            return        
    autothreads = luxProp(scn, "autothreads", "true").get()
    threads = luxProp(scn, "threads", 1).get()
    luxnice = luxProp(scn, "luxnice", 0).get()
    if ostype == "win32":
        prio = ""
        if luxnice > 15: prio = "/low"
        elif luxnice > 5: prio = "/belownormal"
        elif luxnice > -5: prio = "/normal"
        elif luxnice > -15: prio = "/abovenormal"
        else: prio = "/high"
        if(autothreads=="true"):
            cmd = "start /b %s \"\" \"%s\" \"%s\" "%(prio, ic, filename)        
        else:
            cmd = "start /b %s \"\" \"%s\" \"%s\" --threads=%d"%(prio, ic, filename, threads)        

    if ostype == "linux2" or ostype == "darwin":
        if(autothreads=="true"):
            cmd = "(nice -n %d \"%s\" \"%s\")&"%(luxnice, ic, filename)
        else:
            cmd = "(nice -n %d \"%s\" --threads=%d \"%s\")&"%(luxnice, ic, threads, filename)

    # call external shell script to start Lux    
    print("Running Luxrender:\n"+cmd)
    os.system(cmd)

def launchLuxPiped():
    ostype = osys.platform
    #get blenders 'bpydata' directory
    datadir=Blender.Get("datadir")
    
    scn = Scene.GetCurrent()
    ic = luxProp(scn, "lux", "").get()
    ic = Blender.sys.dirname(ic) + os.sep + "luxrender"
    if ostype == "win32": ic = ic + ".exe"
    if ostype == "darwin": ic = ic + ".app/Contents/MacOS/luxrender"
    checkluxpath = luxProp(scn, "checkluxpath", True).get()
    if checkluxpath:
        if sys.exists(ic) != 1:
            Draw.PupMenu("Error: Lux renderer not found. Please set path on System page.%t|OK")
            return        
    autothreads = luxProp(scn, "autothreads", "true").get()
    threads = luxProp(scn, "threads", 1).get()

    if ostype == "win32":
        if(autothreads=="true"):
            cmd = "\"%s\" - "%(ic)        
        else:
            cmd = "\"%s\" - --threads=%d"%(ic, threads)        

    if ostype == "linux2" or ostype == "darwin":
        if(autothreads=="true"):
            cmd = "(\"%s\" \"%s\")&"%(ic, filename)
        else:
            cmd = "(\"%s\" --threads=%d \"%s\")&"%(ic, threads, filename)

    # call external shell script to start Lux    
    print("Running Luxrender:\n"+cmd)

    import subprocess, os

    PIPE = subprocess.PIPE
    p = subprocess.Popen(cmd, stdin=PIPE)
    
    return p.stdin

def launchLuxWait(filename):
    ostype = osys.platform
    #get blenders 'bpydata' directory
    datadir=Blender.Get("datadir")
    
    scn = Scene.GetCurrent()
    ic = luxProp(scn, "lux", "").get()
    ic = Blender.sys.dirname(ic) + os.sep + "luxrender"
    if ostype == "win32": ic = ic + ".exe"
    if ostype == "darwin": ic = ic + ".app/Contents/MacOS/luxrender"
    checkluxpath = luxProp(scn, "checkluxpath", True).get()
    if checkluxpath:
        if sys.exists(ic) != 1:
            Draw.PupMenu("Error: Lux renderer not found. Please set path on System page.%t|OK")
            return        
    autothreads = luxProp(scn, "autothreads", "true").get()
    threads = luxProp(scn, "threads", 1).get()

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

#### SAVE ANIMATION ####    
def save_anim(filename):
    global MatSaved
    
    MatSaved = 0
    startF = Blender.Get('staframe')
    endF = Blender.Get('endframe')
    scn = Scene.GetCurrent()

    Run = luxProp(scn, "run", "true").get()

    print("\n\nRendering animation (frame %i to %i)\n\n"%(startF, endF))

    for i in range (startF, endF+1):
        Blender.Set('curframe', i)
        print("Rendering frame %i"%(i))
        Blender.Redraw()
        frameindex = ("-%05d" % (i)) + ".lxs"
        indexedname = sys.makename(filename, frameindex)
        unindexedname = filename
        luxProp(scn, "filename", Blender.Get("filename")).set(sys.makename(filename, "-%05d" %  (Blender.Get('curframe'))))

        if Run == "true":
            if save_lux(filename, unindexedname):
                launchLuxWait(filename)
        else:
            save_lux(indexedname, unindexedname)

        MatSaved = 1

    print("\n\nFinished Rendering animation\n")

#### SAVE STILL (hackish...) ####
def save_still(filename):
    global MatSaved
    scn = Scene.GetCurrent()
    luxProp(scn, "filename", Blender.Get("filename")).set(sys.makename(filename, ""))
    MatSaved = 0
    unindexedname = filename
    if save_lux(filename, unindexedname):
        if runRenderAfterExport: #(run == None and luxProp(scn, "run", "true").get() == "true") or run:
            launchLux(filename)


######################################################
# Icons
######################################################

def base64value(char):
    if 64 < ord(char) < 91: return ord(char)-65
    if 96 < ord(char) < 123: return ord(char)-97+26
    if 47 < ord(char) < 58: return ord(char)-48+52
    if char == '+': return 62
    return 63

def decodeIconStr(s):
    buf = BGL.Buffer(BGL.GL_BYTE, [16,16,4])
    offset = 0
    for y in range(16):
        for x in range(16):
            for c in range(4):
                buf[y][x][c] = int(base64value(s[offset])*4.048)
                offset += 1
    return buf

def decodeLogoStr(s):
    buf = BGL.Buffer(BGL.GL_BYTE, [18,118,4])
    offset = 0
    for y in range(18):
        for x in range(118):
            for c in range(4):
                buf[y][x][c] = int(base64value(s[offset])*4.048)
                offset += 1
    return buf

def decodeBarStr(s):
    buf = BGL.Buffer(BGL.GL_BYTE, [17,138,4])
    offset = 0
    for y in range(17):
        for x in range(138):
            for c in range(4):
                buf[y][x][c] = int(base64value(s[offset])*4.048)
                offset += 1
    return buf

icon_luxblend = decodeLogoStr("///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A/gAA/gAA/gAA/gAA/gAA/gAA/gAa/gA5/gAZ/gAA/gAA/gAA/gAA/gAA/gAA/gAA/gAA///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A/gAA/gAA/gAA/gAA/gAA/gAA/gAj/gA//gAh/gAA/gAA/gAA/gAA/gAA/gAA/gAA/gAA///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A/gAA/gAA/gAA/gAA/gAA/gAA/gAC/gAO/gAC/gAB/gAS/gAQ/gAA/gAA/gAA/gAA/gAA///A///A///A/gAA/gAZ/gAu/gA7/gA//gA//gA//gA//gA//gA//gA//gAd/gAA/gAZ/gAu/gA//gA//gA//gA//gA//gA//gA3/gAm/gAI/gAE/gAz/gA//gA//gAZ/gAA/gAA/gAA/gAZ/gA//gA//gAm/gAR/gA//gA//gA//gA//gA//gA//gA//gA//gA//gA//gAz/gAd/gAE/gAA/gA//gA//gAd/gAA/gAI/gAm/gA3/gA//gA//gA//gAR/gAA/gAA/gAA/gAA/gAA/gAu/gA//gAu/gAA/gAA/gAA/gAA/gAA/gAA/gAd/gA//gA//gAA/gAE/gAd/gAz/gA//gA//gA//gA//gA//gA7/gAq/gAV/gAA///A///A///A///A///A///A/gAA/gAA/gAA/gAI/gAK/gAA/gAA/gAA/gAA/gAn/gA//gA//gAc/gAA/gAA/gAA/gAA///A///A///A/gAi/gA//gA//gA//gA//gA//gA//gA//gA//gA//gA//gAd/gAZ/gA//gA//gA//gA//gA//gA//gA//gA//gA//gA//gA7/gAE/gAE/gAz/gA//gA//gAR/gAA/gAZ/gA//gA//gAm/gAA/gAR/gA//gA//gA//gA//gA//gA//gA//gA//gA//gA//gA//gA//gAz/gAA/gA//gA//gAd/gAI/gA7/gA//gA//gA//gA//gA//gAR/gAA/gAA/gAA/gAA/gAA/gAu/gA//gAu/gAA/gAA/gAA/gAA/gAA/gAA/gAd/gA//gA//gAA/gAu/gA//gA//gA//gA//gA//gA//gA//gA//gA//gA//gAi///A///A///A///A///A///A/gAA/gAA/gAA/gAv/gA4/gAA/gAA/gAA/gAD/gA9/gA//gA//gAz/gAA/gAA/gAA/gAA///A///A///A/gA//gA//gAq/gAI/gAA/gAA/gAA/gAA/gAA/gAA/gAA/gAA/gAu/gA//gA3/gAI/gAA/gAA/gAA/gAA/gAA/gAd/gA//gA//gAR/gAA/gAM/gA7/gA//gA7/gAZ/gA//gA//gAz/gAA/gAA/gAR/gA//gA//gAR/gAA/gAA/gAA/gAA/gAA/gAA/gAE/gAd/gA//gA//gAM/gA//gA//gAd/gAd/gA//gA//gAd/gAI/gAA/gAA/gAA/gAA/gAA/gAA/gAA/gAA/gAu/gA//gAu/gAA/gAA/gAA/gAA/gAA/gAA/gAd/gA//gA//gAA/gA//gA//gAq/gAA/gAA/gAA/gAA/gAA/gAE/gAq/gA//gA////A///A///A///A///A///A/gAA/gAA/gAA/gAN/gAQ/gAA/gAA/gAA/gAA/gAs/gA//gA//gA+/gAs/gAp/gAZ/gAA///A///A///A/gA//gA//gAd/gAA/gAA/gAA/gAA/gAA/gAA/gAA/gAA/gAA/gAu/gA//gAu/gAA/gAA/gAA/gAA/gAA/gAA/gAR/gA//gA//gAR/gAA/gAA/gAM/gA7/gA//gA//gA//gAz/gAE/gAA/gAA/gAR/gA//gA//gAR/gAA/gAA/gAA/gAA/gAA/gAA/gAA/gAR/gA//gA//gAR/gA//gA//gAd/gAd/gA//gA//gAu/gAu/gAu/gAu/gAu/gAu/gAu/gAu/gAu/gAM/gAu/gA//gAu/gAA/gAA/gAA/gAA/gAA/gAA/gAd/gA//gA//gAA/gA//gA//gAd/gAA/gAA/gAA/gAA/gAA/gAA/gAd/gA//gA////A///A///A///A///A///A/gAA/gAA/gAA/gAA/gAA/gAA/gAA/gAI/gAA/gAE/gAZ/gAw/gA//gA//gA//gA//gAh///A///A///A/gA//gA//gAd/gAA/gAA/gAA/gAA/gAA/gAA/gAA/gAA/gAA/gAu/gA//gAu/gAA/gAA/gAA/gAA/gAA/gAA/gAR/gA//gA//gAR/gAA/gAA/gAA/gAR/gA//gA//gA//gAI/gAA/gAA/gAA/gAR/gA//gA//gAm/gAd/gAd/gAd/gAd/gAd/gAd/gAd/gA3/gA//gA3/gAA/gA//gA//gAd/gAd/gA//gA//gA//gA//gA//gA//gA//gA//gA//gA//gA//gAR/gAu/gA//gAu/gAA/gAA/gAA/gAA/gAA/gAA/gAd/gA//gA//gAA/gA//gA//gAd/gAA/gAA/gAA/gAA/gAA/gAA/gAd/gA//gA////A///A///A///A///A///A/gAl/gAL/gAA/gAA/gAA/gAA/gAf/gA+/gAd/gAA/gAA/gAT/gA//gA//gA//gA//gA6///A///A///A/gA//gA//gAd/gAA/gAA/gAA/gAA/gAA/gAA/gAA/gAA/gAA/gAu/gA//gAu/gAA/gAA/gAA/gAA/gAA/gAA/gAR/gA//gA//gAR/gAA/gAA/gAE/gAz/gA//gA//gA//gAz/gAE/gAA/gAA/gAR/gA//gA//gA//gA//gA//gA//gA//gA//gA//gA//gA//gA//gAd/gAA/gA//gA//gAd/gAd/gA//gA//gAR/gAR/gAR/gAR/gAR/gAR/gAd/gA//gA//gAR/gAu/gA//gAu/gAA/gAA/gAA/gAA/gAA/gAA/gAd/gA//gA//gAA/gA//gA//gAd/gAA/gAA/gAA/gAA/gAA/gAA/gAd/gA//gA////A///A///A///A///A///A/gAl/gAK/gAA/gAA/gAA/gAA/gAf/gA+/gAd/gAA/gAA/gAT/gA//gA//gA//gA//gA6///A///A///A/gA//gA//gAd/gAA/gAA/gAA/gAA/gAA/gAA/gAA/gAA/gAA/gAu/gA//gAu/gAA/gAA/gAA/gAA/gAA/gAA/gAR/gA//gA//gAR/gAA/gAA/gAz/gA//gA7/gAd/gA//gA//gAm/gAA/gAA/gAR/gA//gA//gAm/gAd/gAd/gAd/gAd/gAd/gAd/gAd/gAu/gA//gA//gAI/gA//gA//gAd/gAd/gA//gA//gAd/gAR/gAR/gAR/gAR/gAR/gAq/gA//gA//gAR/gAu/gA//gA7/gAZ/gAR/gAR/gAR/gAR/gAV/gAz/gA//gA//gAA/gA3/gA//gA7/gAi/gAd/gAd/gAd/gAd/gAd/gAu/gA//gA////A///A///A///A///A///A/gAA/gAA/gAA/gAA/gAA/gAA/gAA/gAI/gAA/gAE/gAa/gAw/gA//gA//gA//gA//gAg///A///A///A/gA//gA//gAd/gAA/gAA/gAA/gAA/gAA/gAA/gAA/gAA/gAA/gAu/gA//gAu/gAA/gAA/gAA/gAA/gAA/gAA/gAR/gA//gA//gAR/gAA/gAm/gA//gA7/gAM/gAA/gAZ/gA//gA//gAm/gAA/gAR/gA//gA//gAR/gAA/gAA/gAA/gAA/gAA/gAA/gAA/gAR/gA//gA//gAR/gA//gA//gAd/gAE/gAz/gA//gA//gA//gA//gA//gA//gA//gA//gA//gAz/gAA/gAV/gA//gA//gA//gA//gA//gA//gA//gA//gA//gA//gAi/gAA/gAV/gA7/gA//gA//gA//gA//gA//gA//gA//gA//gA//gA////A///A///A///A///A///A/gAA/gAA/gAA/gAO/gAR/gAA/gAA/gAA/gAA/gAt/gA//gA//gA+/gAs/gAq/gAZ/gAA///A///A///A/gA//gA//gAd/gAA/gAA/gAA/gAA/gAA/gAA/gAA/gAA/gAA/gAi/gAu/gAi/gAA/gAA/gAA/gAA/gAA/gAA/gAM/gAu/gAu/gAM/gAm/gA//gA7/gAM/gAA/gAA/gAA/gAm/gA//gA//gAd/gAR/gA//gA//gAd/gAR/gAR/gAR/gAR/gAR/gAR/gAR/gAq/gA//gA//gAM/gA//gA//gAd/gAA/gAA/gAZ/gAm/gAu/gAu/gAu/gAu/gAu/gAq/gAZ/gAA/gAA/gAA/gAI/gAd/gAu/gAu/gAu/gAu/gAu/gAu/gAi/gAV/gAA/gAA/gAA/gAE/gAV/gAd/gAd/gAd/gAd/gAd/gAd/gAu/gA//gA////A///A///A///A///A///A/gAA/gAA/gAA/gAv/gA4/gAA/gAA/gAA/gAD/gA9/gA//gA//gAz/gAA/gAA/gAA/gAA///A///A///A/gA//gA//gAd/gAA/gAA/gAA/gAA/gAA/gAA/gAA/gAA/gAA/gAA/gAA/gAA/gAA/gAA/gAA/gAA/gAA/gAA/gAA/gAA/gAA/gAA/gAA/gAA/gAA/gAA/gAA/gAA/gAA/gAA/gAA/gAA/gAA/gAR/gA//gA//gA//gA//gA//gA//gA//gA//gA//gA//gA//gA//gAm/gAA/gA//gA//gAd/gAA/gAA/gAA/gAA/gAA/gAA/gAA/gAA/gAA/gAA/gAA/gAA/gAA/gAA/gAA/gAA/gAA/gAA/gAA/gAA/gAA/gAA/gAA/gAA/gAA/gAA/gAA/gAA/gAA/gAA/gAA/gAA/gAA/gAA/gAA/gAd/gA//gA////A///A///A///A///A///A/gAA/gAA/gAA/gAI/gAK/gAA/gAA/gAA/gAA/gAn/gA//gA//gAc/gAA/gAA/gAA/gAA///A///A///A/gA//gA//gAd/gAA/gAA/gAA/gAA/gAA/gAA/gAA/gAA/gAA/gAA/gAA/gAA/gAA/gAA/gAA/gAA/gAA/gAA/gAA/gAA/gAA/gAA/gAA/gAA/gAA/gAA/gAA/gAA/gAA/gAA/gAA/gAA/gAA/gAM/gAu/gAu/gAu/gAu/gAu/gAu/gAu/gAu/gAu/gAu/gAm/gAR/gAA/gAA/gA//gA//gAd/gAA/gAA/gAA/gAA/gAA/gAA/gAA/gAA/gAA/gAA/gAA/gAA/gAA/gAA/gAA/gAA/gAA/gAA/gAA/gAA/gAA/gAA/gAA/gAA/gAA/gAA/gAA/gAA/gAA/gAA/gAA/gAA/gAA/gAA/gAA/gAd/gA//gA////A///A///A///A///A///A/gAA/gAA/gAA/gAA/gAA/gAA/gAC/gAO/gAC/gAB/gAS/gAP/gAA/gAA/gAA/gAA/gAA///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A/gAA/gAA/gAA/gAA/gAA/gAA/gAj/gA//gAh/gAA/gAA/gAA/gAA/gAA/gAA/gAA/gAA///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A/gAA/gAA/gAA/gAA/gAA/gAA/gAa/gA5/gAY/gAA/gAA/gAA/gAA/gAA/gAA/gAA/gAA///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A")


icon_blender = decodeIconStr("///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A27wA27wA27wA27wA27wAFFFGIIIsNNN5IIIsFFFG27wA27wA27wA27wA27wA///A27wA27wA27wA27wA27wAFFFmnnn9sss/kkk9FFFm27wA27wA27wA27wA27wA///A27wA27wA27wA27wA27wAEEEvwww/AAA/sss/EEEv27wA27wA27wA27wA27wA///A27wA27wA27wA27wA27wAFFFxzzz/xxx/vvv/FFFx27wA27wA27wA27wA27wA///A27wAGGGRLLLtKKK7KKK9JJJ/111/ppp/xxx/III/JJJ9JJJ7LLLtGGGR27wA///AGGGQPPP8xxx/444/vvv/555/333/999/zzz/xxx/jjj/nnn/nnn/OOO8GGGQ///ALLL2222/zzz/lll/+++/888/666/444/222/000/yyy/aaa/nnn/vvv/LLL2///AMMMxqqq/+++/ttt/////AAA/888/666/444/AAA/000/iii/zzz/nnn/MMMx///AGGGKLLLqKKK7ZZZ/yyy/yyy/yyy/888/vvv/ttt/rrr/VVV/JJJ7LLLqGGGK///A27wA27wA27wAJJJ1999+////sss5UUU8qqq5777/333+III127wA27wA27wA///A27wA27wA27wAHHHJMMMzUUU7GGGpHHHIGGGpSSS7MMMzHHHJ27wA27wA27wA///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A")
icon_col = decodeIconStr("///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A27wA27wA27wA27wAVIAPXKB5VIAS27wA27wA27wA27wA///A///A///A///A///A27wA27wA27wAVIAPXKB8shU/XLC9VIAS27wA27wA27wA///A///A///A///A///A27wA27wAVIAPXKB8ymU/7xd/0qb/XLC9VIAS27wA27wA///A///A///A///A///A27wAVIAPXKA8xkO/7uW/7wa/7xd/0qb/XLC9VIAS27wA///A///A///A///A///AVIAPXKA8xiJ/6rO/6sS/7uW/7wZ/7xd/0qa/XLC9VIAS///A///A///A///A///AXKA1ypd/+6z/6rO/6rO/6sS/7uW/7vZ/7xd/shT/XKB5///A///A///A///A///AVJAMYMC873w/+6z/6rO/6rO/6sS/7uV/ymT/XKB8VIAP///A///A///A///A///A27wAVJAMYMC873w/+6z/6rO/6rO/xkN/XKB8VIAP27wA///A///A///A///A///A27wA27wAVJAMYMC873w/+6z/xiJ/XKA8VIAP27wA27wA///A///A///A///A///A27wA27wA27wAVJAMYMC8xpc/XKA8VIAP27wA27wA27wA///A///A///A///A///A27wA27wA27wA27wAVJAMXKA1VIAP27wA27wA27wA27wA///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A")
icon_float = decodeIconStr("///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A27wA27wA27wA27wAMMMSOOO5MMMP27wA27wA27wA27wA///A///A///A///A///A27wA27wA27wAMMMSPPP9nnn/PPP8MMMP27wA27wA27wA///A///A///A///A///A27wA27wAMMMSPPP9ttt/333/vvv/PPP8MMMP27wA27wA///A///A///A///A///A27wAMMMSOOO9ppp/zzz/111/333/vvv/PPP8MMMP27wA///A///A///A///A///AMMMSOOO9lll/uuu/www/zzz/111/333/vvv/PPP8MMMP///A///A///A///A///AOOO5sss/666/sss/uuu/www/zzz/111/333/kkk/PPP1///A///A///A///A///AMMMPQQQ8444/666/ttt/uuu/www/zzz/ppp/OOO8MMMM///A///A///A///A///A27wAMMMPQQQ8444/666/ttt/uuu/mmm/OOO8MMMM27wA///A///A///A///A///A27wA27wAMMMPQQQ8444/555/jjj/OOO8MMMM27wA27wA///A///A///A///A///A27wA27wA27wAMMMPQQQ8ppp/OOO8MMMM27wA27wA27wA///A///A///A///A///A27wA27wA27wA27wAMMMPOOO1MMMM27wA27wA27wA27wA///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A")
icon_map2d = decodeIconStr("///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A27wA27wA27wA27wA27wAMMMUMMMzMMMzMMMU27wA27wA27wA27wA27wA///A///A27wA27wA27wANNNPMMMyYVQ/wnV/bbb/RRR/MMMyNNNP27wA27wA27wA///A///A27wAMMMLMMMtWUQ/vnZ/7vY/6rP/aaa/eee/ZZZ/PPP/MMMtMMML27wA///A///AMMMfTSQ/tnc/7yg/7uV/6qN/6qM/YYY/ZZZ/ddd/fff/YYY/OOO/MMMf///A///AMMM/71o/7wb/6sQ/rgK/dVG/6qM/YYY/ZZZ/bbb/ccc/fff/ggg/MMM////A///AMMM/92q/AAA/6rP/dVH/AAA/6qM/YYY/ZZZ/bbb/ccc/eee/iii/MMM////A///AMMM/93r/dWI/6rP/dVH/AAA/6qM/XXX/ZZZ/bbb/ccc/eee/iii/MMM////A///AMMM/94t/6sR/6rQ/6rO/6qN/6qM/XXX/ZZZ/bbb/ccc/eee/jjj/MMM////A///AMMM/94u/dWI/dVI/6rP/6rN/6qM/XXX/ZZZ/bbb/ccc/eee/kkk/MMM////A///AMMM/+5v/AAA/AAA/6rP/7vX/94t/xxx/ggg/bbb/ccc/eee/lll/MMM////A///AMMM/+5x/6sR/7xd/+6y/////////////////111/mmm/eee/mmm/MMM////A///AMMM/+72//96/////////////////////////////////666/vvv/MMM////A///AMMMiTTS/wuq/986/////////////////////////555/ppp/SSS/MMMi///A///A27wAMMMHMMMdMMM0aZX/0yu/+97/888/uuu/XXX/MMM0MMMdMMMH27wA///A///A27wA27wA27wA27wANNNLMMMhMMM3MMM3MMMhNNNL27wA27wA27wA27wA///A")
icon_map2dparam = decodeIconStr("///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A27wAQQQB27wA27wA27wA27wA27wA27wA27wA27wA27wA27wA27wA27wA///A///A27wAUUUwMMM9EEE3AAAvAAAlAAAbAAAI27wA27wA27wA27wA27wA27wA///A///A27wAeeeOVVV9OOO/MMM/CCC/AAA+AAA9AAAg27wA27wA27wA27wA27wA///A///A27wA27wAfffKWWW9ggg/mmm/TTT/AAA/AAA9AAAS27wA27wA27wA27wA///A///A27wA27wA27wAeeeXVVV9hhh/lll/TTT/BBB/BBB6AAAN27wA27wA27wA///A///A27wAAAAK27wA27wAdddgTTT8NNN/NNN/JJJ/VVV9EEE8AAAoAAAG27wA///A///A27wAAAAXAAAA27wA27wAeeeaVVV2QQQ/nnn+222/mmm/PPP9JGF8KGCX///A///A27wAAAAkAAAA27wA27wA27wA27wAVVVXYYY8+++/333/gec+ZPL+XOJq///A///A27wAAAAxAAAB27wA27wA27wA27wA27wAXXXiiii83219ofY8eUO/aQL2///A///A27wAAAA9AAAC27wA27wA27wA27wA27wAgggAWWVwmgc84yt/oeW/gWP1///A///ACCC6AAA/AAA/CCC627wA27wA27wA27wA27wAKFFDKGDzxsm52wq/peW2///A///AAAA/////////AAA/AAABAAAAAAAAAAAA27wA27wALFCFMHE31wr61uo5///A///AAAA/////////AAA/AAA+AAAzAAAmAAAZAAAM27wA27wAKFDJPLH6umez///A///ACCC6AAA/AAA/CCC627wA27wA27wA27wA27wA27wA27wA27wAKFCOOJFf///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A")
icon_map3dparam = decodeIconStr("27wA27wA27wA27wA27wA27wA3nIC6pMJ6pMJ3nIC27wA27wA27wA27wA27wA27wA27wA27wA27wA27wA27wA3nIC6qMj6qM/6qM/6qMj3nIC27wA27wA27wA27wA27wA27wA27wA27wA27wA27wA6pMJ6qM/////////6qM/6pMJ27wA27wA27wA27wA27wA27wA27wA27wA27wANNNOSQMz5qM/////////5qM/SQMzNNNO27wA27wA27wA27wA27wA27wAMMMIMMMrXXX/www/5wg/6qM/5qM/vnX/bbb/PPP/MMMrMMMI27wA27wA27wA27wAMMM1xxx/777/222/yyy/zxu/caY/bbb/ggg/iii/YYY/MMM127wA27wA27wA27wAMMM/+++/zzz/yyy/yyy/yyy/ZZZ/bbb/ddd/fff/kkk/MMM/27wA27wA27wA27wAMMM/////yyy/yyy/yyy/yyy/ZZZ/bbb/ddd/eee/lll/MMM/27wA27wA27wA27wAMMM/////yyy/yyy/yyy/yyy/ZZZ/bbb/ddd/eee/nnn/MMM/27wA27wA27wA3nICRPM//97/yyy/yyy/yyy/yyy/ZZZ/bbb/ddd/eee/rpm/RPM/3nIC27wA3nIC6qMj5qM/6qM/2ue/zzz/444/999/666/rrr/fff/tkU/5qM/5qM/6qMj3nIC6pMJ6qM/////////6qM/+96/////////////////985/6qM/////////6qM/6pMJ6pMJ6qM/////////6qM/+86/////////////////974/6qM/////////6qM/6pMJ3nIC6qMj6qM/6qM/pfM2PPP+mmm/555/000/hhh/PPP+pfM26qM/6qM/6qMj3nIC27wA3nIC6pMJ6pMJ3nICMMMEMMMaMMMwMMMwMMMaMMME3nIC6pMJ6pMJ3nIC27wA///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A")
icon_mat = decodeIconStr("///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A27wA27wA27wAVJAMXKBnXLB1WJA9XLB1XKBnVJAM27wA27wA27wA///A///A///A27wAVAAAWJBgYMD9ukW/1sc/5we/0qY/sgQ/XLB9WJBgVAAA27wA///A///A///A27wAWJBghXM96zk/8yf/7wa/7vY/7vZ/YUN/TQM/aPF9WJBg27wA///A///A///AVIALZNE970o/7wb/QNG/QNG/7vX/7vX/JHD/DDD/bXP/XKB9VIAL///A///A///AXKBpype/8zj/7vX/QNG/QNG/7vX/7vX/sjR/IGD/keS/rfQ/XKBp///A///A///AXLB36zp/7xc/7vX/7vX/7vX/7vX/7vX/7vX/7vX/7vZ/0qZ/XLB3///A///A///AVJA+95x/2rX/fYM/zoU/7vX/7vX/7vX/7vX/7vX/7vY/6wf/VJA+///A///A///AXKB361s/VTO/AAA/NKF/7vX/7vX/meP/IGD/JHD/tkU/1rc/XKB3///A///A///AXKBq0tj/cba/AAA/HGD/7vX/7vX/IGD/AAA/AAA/VTQ/ujW/XKBq///A///A///AVIAMaPG920w/RPN/meP/7vX/7vX/gaM/BAA/HHH/njd/YMD9VIAM///A///A///A27wAWKBilbS995y/91n/8xd/7vZ/7xc/4wh/4yn/iXM9WKBi27wA///A///A///A27wAQQABWKBiaOF9zsj/61s/95x/5zp/xpe/ZNE9WKBiQQAB27wA///A///A///A27wA27wA27wAVIAMXKBqXKB3VJA+XKB3XKBqVIAM27wA27wA27wA///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A")
icon_matmix = decodeIconStr("27wA27wA27wA27wA27wA27wA27wAMIFdUMG7WNF+WNF+SLG5LHFS27wA27wA///A27wA27wA27wA27wA27wASLGAOJGziYN/xmV/wmT/pgQ/jaN/YPH/NJGm27wA///A27wA27wA27wA27wA27wAMIFjlbR/9ye/6sQ/zlJ/sgJ/ofM/ngT/YPH/MIGT///A27wA27wA27wA27wA27wAXQJ/6xk/9xZ/6sQ/5qM/zlK/sfI/ofM/jaN/SLG5///A27wA27wA27wA27wAHHHGgXQ//4r/8xc/7vX/7tR/5pM/zlK/sgJ/pgQ/WMF+///A27wA27wA27wA27wAJOVVYbf/58//y27/wz3/7vY/7tS/4pM/ykJ/vmU/WMF////A27wAAAAALIGkTMG+NQU/Qcu/Sfz/Sfz/Wi1/wz4/7vZ/7sR/6sR/wmW/UMH8///ASLGAOJG1iYN/xmV/kns/Rfz/99+/++//Rfz/z27/8ye/9yc/9zg/iYN/LIFh///AMHFilbR/9ye/6sQ/jns/Rfz/////////Rfz/57///4q/6xk/lbR/NJG227wA///AYQJ96xk/9xZ/6sQ/orw/Tgz/Rfz/Rez/Qdw/Xaf/gXP/XPI/MIGoAAAA27wA///AgXQ//4r/8xc/7vX/7tR/nrw/jms/dhn/ein/WNG/GGGRAAAA27wA27wA27wA///AhYR//7x/91m/8xe/7vY/7tS/4pM/ykJ/vmU/WMF/GGGH27wA27wA27wA27wA///AbTM995x//+6/80k/8ye/7vZ/7sR/6sR/wmW/TMG+27wA27wA27wA27wA27wA///APIEitld///7//+6/91n/8ye/9yc/9zg/iYN/LIGk27wA27wA27wA27wA27wA///ARKGCRKFyskc/94v//7w//4q/6xk/lbR/OJG0AAAA27wA27wA27wA27wA27wA///A27wAQJECPIEibTL9hYQ/gXP/YQJ9MHEi27wA27wA27wA27wA27wA27wA27wA///A")
icon_tex = decodeIconStr("///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///AOOO6MMM/MMM/MMM/MMM/MMM/MMM/MMM/MMM/MMM/MMM/MMM/OOO6///A///A///AMMM/444/555/555/555/555/666/666/777/777/888/888/MMM////A///A///AMMM/555/mmm/TTT/aaa/xxx/111/222/222/QQQ/ZZZ/777/MMM////A///A///AMMM/333/DDD/AAA/AAA/YYY/zzz/111/xxx/AAA/AAA/nnn/MMM////A///A///AMMM/222/DDD/AAA/AAA/bbb/yyy/zzz/111/RRR/AAA/iii/MMM////A///A///AMMM/666/jjj/TTT/ddd/vvv/xxx/yyy/zzz/000/rrr/555/MMM////A///A///AMMM/666/rrr/sss/uuu/vvv/www/xxx/yyy/zzz/000/666/MMM////A///A///AMMM/666/qqq/iii/qqq/uuu/vvv/ppp/nnn/yyy/zzz/555/MMM////A///A///AMMM/777/jjj/AAA/RRR/sss/bbb/AAA/AAA/SSS/yyy/555/MMM////A///A///AMMM/888/mmm/LLL/ccc/rrr/QQQ/AAA/AAA/AAA/www/555/MMM////A///A///AMMM/888/nnn/ooo/ppp/qqq/jjj/HHH/DDD/XXX/www/555/MMM////A///A///AMMM/666/888/888/777/666/666/555/555/555/444/333/MMM////A///A///ANNN4NNN+NNN+NNN+NNN+NNN+NNN+NNN+NNN+NNN+NNN+NNN+OOO4///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A")
icon_texcol = decodeIconStr("///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///AWKA4VJA+VJA+VJA+VJA+VJA+VJA+VJA+VJA+VJA+VJA+VJA+WKA4///A///A///AVIA/82p/93r/93r/93s/93s/93s/93t/94u/94u/94w/95w/VIA////A///A///AVIA/93s/xoV/ZVM/icR/6wf/8zi/80k/80l/USN/daU/94v/VIA////A///A///AVIA/72r/FDC/AAA/AAA/eZP/8yf/8zh/3vg/AAA/AAA/olf/VIA////A///A///AVIA/50p/DCB/AAA/AAA/faO/8xd/8yf/8zh/SPK/AAA/jga/VIA////A///A///AVIA/94t/rhO/WRI/haN/5uY/7wb/8xd/8yf/7yg/tma/72r/VIA////A///A///AVIA/94u/6sQ/6tT/7uV/7uX/7vY/7wa/7xc/8ye/8yg/93s/VIA////A///A///AVIA/94u/6rO/ylO/5sS/7uU/7uW/1qV/yoW/7xc/8ye/93s/VIA////A///A///AVIA/+5w/zlL/DDD/bVK/6tS/mdN/AAA/AAA/YTK/7xc/93r/VIA////A///A///AVIA/+5x/3oL/NKD/mcK/6sQ/WQG/AAA/AAA/BAA/5uZ/93r/VIA////A///A///AVIA/+6z/6qM/6qM/6qM/6rO/ujM/IGC/BBA/aUJ/7vX/93r/VIA////A///A///AVIA/+5w/+6y/+5w/+4v/94t/93s/82r/93r/93r/93r/92p/VIA////A///A///AWJA6VJA/WJB/WJB/WJB/WJB/WJB/WJB/WJB/WJB/WJB/VJA/WJA6///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A")
icon_texmix = decodeIconStr("///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///APPP7ccc/ddd/ccc/bbb/bbb/ddd/eee/RRR9///A///A///A///A///A///A///AYYY+yyy/fff/qqq/000/111/jjj/sss/eee////A///A///A///A///A///A///Aaaa9XXX/AAA/III/rrr/xxx/LLL/GGG/VVV////A///A///A///A///A///A///AZZZ9hhh/JJJ/XXX/rrr/uuu/kkk/eee/YYY////A///A///A///A///A///A///AVYd/sv0/imq/nqu/rrr/ttt/vvv/000/bbb////A///APPP7ccc/ddd/ccc/Ycg/Qcu/Sfz/Sfz/Wi1/fin/RRR/bbb/yyy/bbb////A///AYYY+yyy/fff/qqq/x05/Rfz/99+/++//Rfz/PSX/AAA/AAA/uuu/bbb////A///Aaaa9XXX/AAA/III/orw/Rfz/////////Rfz/lpu/XXX/eee/000/ccc////A///AZZZ9hhh/JJJ/XXX/osw/Tgz/Rfz/Rez/Qdw/Wae/bbb9aaa9YYY9PPP7///A///AYYY9vvv/lll/ppp/rrr/pty/sw1/w06/Ych////A///A///A///A///A///A///AZZZ9sss/SSS/iii/hhh/RRR/bbb/yyy/bbb////A///A///A///A///A///A///AZZZ9rrr/JJJ/eee/SSS/AAA/AAA/uuu/bbb////A///A///A///A///A///A///AZZZ+111/ttt/uuu/ooo/XXX/eee/000/ccc////A///A///A///A///A///A///AOOO4aaa9aaa9ZZZ9ZZZ9bbb9aaa9YYY9PPP7///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A")
icon_texmixcol = decodeIconStr("///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///AaOE7mcS/ndT/mcS/lbS/kbS/ndU/neV/bQH9///A///A///A///A///A///A///AiYP+92o/niY/0tg//4p//6s/pme/wun/neV////A///A///A///A///A///A///AkZP9aYT/AAA/LJF/5vd//2j/OMH/GHH/eVN////A///A///A///A///A///A///AjYP9qlZ/OKE/haO/7wb/+zf/voZ/jgY/hYP////A///A///A///A///A///A///AXae/z27/qty/ux2/9wZ/+yc//1f//5o/lbS////A///AaOE7mcS/ndT/mcS/adh/Qcu/Sfz/Sfz/Wi1/lot/ZUK/leQ//3l/kbR////A///AiYP+92o/niY/0tg/25+/Rfz/99+/++//Rfz/TXc/AAA/BAA/9zg/lbS////A///AkZP9aYT/AAA/LJF/tx2/Rfz/////////Rfz/quz/bZU/lhX//6o/lcS////A///AjYP9qlZ/OKE/haO/uy3/Tgz/Rfz/Rez/Qdw/Ybg/laQ9laQ9iYP9aOE7///A///AhXP9/1f/6sQ/8vW/9wZ/wz4/y28/26//aej////A///A///A///A///A///A///AhXQ98xd/eWH/znR/xmR/ZUK/leQ//3l/kbR////A///A///A///A///A///A///AhYR97xb/TMA/xkL/dVG/AAA/BAA/9zg/lbS////A///A///A///A///A///A///AiYR+/7q//zb//0d/1tb/bZU/lhX//6o/lcS////A///A///A///A///A///A///AZNE4iZS9iZS9iYR9jZQ9laQ9laQ9iYP9aOE7///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A")
icon_texparam = decodeIconStr("///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A27wAOOO5GGG/BBB9AAA5AAAwAAAnAAAO27wA27wA27wA27wA27wA27wA///A875F27wAYYYZPPP/KKK/III/BBB/AAA/AAA/AAAxAAAB27wA27wA27wA27wA///AoooO875K27wAaaaTRRR/eee/lll/SSS/AAA/AAA/AAAk27wA27wA27wA27wA///AeeeX222V876J27wAbbbkSSS/iii/mmm/TTT/AAA/AAA/CCCW27wA27wA27wA///AXXXfxxxftttW887I27wAcccwSSS/OOO/PPP/III/RRR/CCC/CCC3CCCL27wA///ATTTmtttsQQQvbbbd887H27wAdddrVVV/PPP/hhh/222/lll/NNN/HFE/KFCo///APPPssss3HHH6NNNwZZZd988G27wA27wAXXXlXXX/999/333/jhg/ZPK/WOJ5///AMMMvsss/jjj1XXXxrrrf333R998F27xA27wAYYYvggg/554/meX/eUO/ZQL////AJJJyvvv/jjj/oooztttoyyyc444Q999E27xAfffAYXW7jeZ/4yt/pfX/gWP////AHHH0zzz/iii/jjj+oooytttnlllggggX+99D27xALFAFKGD9wql/2wr/peW////AFFF3333/HHH/QQQ/jjj9mmmyDDD8KKKxTTTe555D26xAIFDKMHE+0vq/1uo////ADDD6666/HHH/QQQ/jjj/kkk8DDD+BBB+JJJyrrrR+++C26xAKFDROKG/wog+///ABBB9555/777/333/000/www/rrr9bbb6fffv000Y555M///B26xAKFCYOKF0///ABBB5BBB9DDD6EEE4GGG1IIIzKKKxNNNtPPPmSSSfUUUXUUUODDDE26xA27wA///A")

icon_emission = decodeIconStr("///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A27wA27wA27wAAAAgAAA/AAAg27wA27wA27wA///A///A///A///A///A///A///A27wAAAAFAAAxAAA/AAA/AAA/AAAxAAAF27wA///A///A///A///A///A///A///A27wAAAAZooo5////444/nnn/KKK2AAAZ27wA///A///A///A///A///A///A///A27wAAAALSSS/ggg/bbb/AAA/AAA/AAAL27wA///A///A///A///A///A///A///A27wAAAAYrrr/////777/nnn/KKJ+AAAZ27wA///A///A///A///A///A///A///A27wAPNBRTRI+kiX8ebQ+ebN8NLA+PNCP27wA///A///A///A///A///A///A///AQQABVRB1qlQ483g2qlR+81Z2pkO6VRB0QQAB///A///A///A///A///A///A///ATQBlieP685t361ezjcD+5ySx61c0dYG6TQBl///A///A///A///A///A///A///AVRA453x650gwhbB93vRthbB+4yXvwrX0VRA4///A///A///A///A///A///A///AVRA+++8941ow2xbs0tRp0tRp1vUr2yiyVRA+///A///A///A///A///A///A///AUQA48868/++999772yiszuYo2yhsvsdxVRA5///A///A///A///A///A///A///ATPBlqof6//////++64yy64yy7611cYK4TPBl///A///A///A///A///A///A///AKKABUQA1qnf59989//++6525ifT4UQA1KKAB///A///A///A///A///A///A///A27wAKKABSPBkUQA4VQA+UQA4SPBkKKAB27wA///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A")

icon_spectex = decodeIconStr("///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///AAAATGGGzAAAiAAAA27wA27wA27wA27wA27wA27wA27wAAAADAAAjGGGxAAAT///AFFFy555/SBx/MA5+ASx9AhZ9ArC9AwA9WvA9xnA9/WA97AA/xBB/555/FFFz///AAAAUccc/ka1/MA6/ASx/AhZ/ArC/AwA/WvA/xnA//WA/9AA/1ff/SSS+AAAZ///A27wAMMM6ph2/MA6/Xi0/AhZ/ArC/AwA/WvA/xnA//WA/1bb/jjj/AAAY27wA///A27wABBBnpmv/ni6/lr1/AhZ/ArC/AwA/WvA/xnA//WA/6vv/SSS/AAAE27wA///A27wAAAAEGGG1PPP/SUY/Zsn/ArC/AwA/hyS/xnA//WA/5uu/DDDw27wA27wA///A27wA27wAAAABAAAEIII3oyw/ArC/WvW/syn/31u/3vr/nll/AAAa27wA27wA///A27wA27wA///A///AAAAnlus/BrE/v4v/TTT/kkk/444/PPP+AAAE27wA27wA///A27wA27wA27wA27wAAAAZnnn/444/555/GGG3AAAdEEExAAAM27wA27wA27wA///A27wA27wA27wA27wAAAAKaaa/555/zzz/AAAn27wA27wA27wA27wA27wA27wA///A27wA27wA27wA27wAAAAALLL8555/iii/AAAX27wA27wA27wA27wA27wA27wA///A27wA27wA27wA27wA27wAAAAPKKK6AAArAAAB27wA27wA27wA27wA27wA27wA///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A")

icon_c_filter = decodeIconStr("///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///AAAASGGG1BBBsAAAW27wA27wA27wA27wA27wA27wA27wAAAAWBBBsGGGyAAAU///AHHHx555/333/ddd/AAAl27wA27wA27wA27wA27wAAAAlddd/333/555/FFFz///AAAAUMMM8eee/555/ccc/AAAT27wA27wA27wAAAATccc/555/eee/MMM8AAAV///A27wAAAAAAAAbfff/222/GGG1AAAA27wAAAAAGGG1222/fff/AAAbAAAA27wA///A27wA27wAAAAAFFFz222/hhh/AAAW27wAAAAWhhh/222/FFFzAAAA27wA27wA///A27wA27wA27wAAAAQccc/333/EEEz27wAEEEz333/ccc/AAAQ27wA27wA27wA///A27wA27wA27wA27wAGGG1444/aaa/AAAdaaa/444/GGG127wA27wA27wA27wA///A27wA27wA27wA27wAAAAakkk/000/UUU/000/kkk/AAAa27wA27wA27wA27wA///A27wA27wA27wA27wAAAACGGG1xxx/555/xxx/GGG1AAAC27wA27wA27wA27wA///A27wA27wA27wA27wA27wAAAAFAAAoJJJ1AAAoAAAF27wA27wA27wA27wA27wA///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A")

icon_c_camera = decodeIconStr("///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A27wA27wA27wA27wAAAAAAAABAAABAAABAAABAAAA27wA27wA27wA27wA///A///ANNN6MMM/MMM/JJJ/MMM/LLL/LLL/LLL/LLL/MMM/MMM/MMM/MMM/OOO6///A///AMMM/vvv/ttt/ccc/mmm/jjj/ggg/hhh/jjj/ooo/sss/www/iii/MMM////A///AMMM/uuu/eee/RRR/XXX/ZZZ/mmm/xxx/ppp/ggg/jjj/ppp/eee/MMM////A///AMMM/ttt/aaa/OOO/WWW/rrr/aaa/TTT/jjj/zzz/hhh/lll/ccc/MMM////A///AMMM/sss/XXX/LLL/ggg/QQQ/HHH/KKK/QQQ/hhh/rrr/ggg/bbb/MMM////A///AMMM/rrr/VVV/JJJ/ooo/QQQ/TTT/III/JJJ/RRR/yyy/ddd/ZZZ/MMM////A///AMMM/sss/UUU/JJJ/eee/eee/www/RRR/EEE/VVV/ooo/ccc/ZZZ/MMM////A///AMMM/uuu/VVV/KKK/RRR/kkk/fff/QQQ/OOO/ooo/bbb/eee/ZZZ/MMM////A///AMMM/xxx/WWW/LLL/NNN/SSS/eee/ooo/hhh/YYY/YYY/ggg/ZZZ/MMM////A///AMMM/zzz/vvv/aaa/fff/VVV/OOO/PPP/RRR/bbb/mmm/sss/fff/NNN9///A///ANNN6MLJ/MJE/IHG/OOO+ggg/bbb/ccc/eee/jjj/NNN+MMM/NNN9MMMP///A///A27wAMHAl9jA/NIApMMMmWWW/888/////888/bbb/NNNmAAAA27wA27wA///A///A27wALGAPMHAoMHASMMMGSSS/777/////888/WWW/NNNF27wA27wA27wA///A///A27wA27wA27wA27wA27wARRRiPPP+QQQ/RRR+VVVi27wA27wA27wA27wA///A")

icon_c_environment = decodeIconStr("///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///AGMV1HNV7HNV7HNV7HNV7HNV7HNV7HNV7HNV7HNV7HNV7GMV1///A///A///A///AHNV7y0u/z0u/y0t/xzs/wyr/wyq/vxp/uxo/twn/svm/HNV7///A///A///A///AIOW8341/tvm/qtj/qtj/qtj/qtj/qtj/qtj/qtj/two/HNV7///A///A///A///AINV8sts/cdc/qrp/uxp/qtj/qtj/qtj/qtj/qtj/tvo/HNU7///A///A///A///AGMV7svy/Ubh/VZb/ZZZ/xyt/ruk/qtj/qtj/rul/bcb/GLU7///A///A///A///AGMV7twz/Uci/Uci/Tbg/TUU/ssq/y0u/vxr/TVT/fko/GMV7///A///A///A///AGMV7vy0/Vdj/Zgl/Xfk/Uci/RWZ/TVV/PSU/Tag/hnr/GMV7///A///A///A///AGMV7wz1/gmq/023/txz/Xfk/Uci/Uci/Uci/Uci/jos/GMV7///A///A///A///AGMV7y02/jos/////023/Zgl/Uci/Uci/Uci/Uci/kpt/GMV7///A///A///A///AGMV7z23/ahm/jos/gmq/Vdj/Uci/Uci/Uci/Uci/mru/GMV7///A///A///A///AGMV7x02/023/y02/wz1/vy0/uxz/swy/rux/ptw/lqu/GMV7///A///A///A///AGMV1GMV7GMV7GMV7GMV7GMV7GMV7GMV7GMV7GMV7GMV7GMV1///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A")

icon_c_sampler = decodeIconStr("///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A27wA27wA27wAMMMXSSS3MMMg27wA27wA27wA27wAMMMdTTT2MMMc27wA27wA27wA27wA27wAMMMSggg/////XXX+MMMB27wA27wA27wAUUU8////jjj/MMMT27wA27wA27wAMMMIYYY8+++/xxx/NNNuMMMCMMMCMMMCMMMCNNNqwww/////ZZZ9MMMJ27wAMMMASSS0666/+++/fff/bbb/bbb/eee/eee/bbb/bbb/ddd/999/777/SSS327wAMMMGjjj/////////////////////////////////////////////////lll/MMMI27wARRRz555/999/ccc/YYY/YYY+aaa+bbb+YYY+YYY+bbb/999/666/RRR2MMMB27wAMMMHWWW7999/yyy/NNNu27wA27wA27wA27wANNNtxxx/+++/YYY8MMMI27wAVVqARfzGOTZZeee/////WWW+QctHRfzLRfzLRfzGUUU8////hhh/OSYaRfzGVVqARfzGRezcRfz5PXj8STV5NPSiRezcRfz5Rfz5RezcNQThRST6PYk7Rfz5RezcRfzGRfzLRfz5////////Rfz5RfzMRfz5////////Rfz5RfzMRfz5////////Rfz5RfzLRfzLRfz5////////Rfz5RfzMRfz5////////Rfz5RfzMRfz5////////Rfz5RfzLRfzGRezcRfz5Rfz5RezcRfzKRezcRfz5Rfz5RezcRfzKRezcRfz5Rfz5RezcRfzGVVqARfzGRfzLRfzLRfzGVVqARfzGRfzLRfzLRfzGVVqARfzGRfzLRfzLRfzGVVqA///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A")

icon_c_integrator = decodeIconStr("///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A27wA27wAAAAAEJPYHMT0MRY+GLS0EJPYAAAA27wA27wA27wA27wA27wA27wA27wA27wAAAVAEJPoVai/lr0/elv/Xeo/LRZ/EIPnDHOEAAVA27wA27wA27wA27wA27wA27wAEIPcZel/rw5/cir/NTb/SYi/PWh/MSb/QVd/KPW6EJPfAJSB27wA27wA27wAAAAAHMT4ty7/hmv/FKQyDGMXEJP7bhq/nt2/pv4/sy6/diq/EJQuIIQC27wA27wAFIQGRWd/u08/TYf/CFKQDGLfUai/flv/Zfp/SZj/bgp/rx6/fks/EJQuAJSB27wAAJSBINT7uz8/glt/EIOqGKQ4Xeo/SYi/KQY/SZk/IOW/Ydl/ty7/diq/EJPg27wA27wAEJPhflt/u08/Yel/JOW/QXi/HNV/TZi/Yfp/GLS6EJPuejr/tz8/HMT6AMMB27wAGGMCFLRxiow/u08/ciq/SZk/Yeo/gnw/Vaj/DINhDGJQQVd/u08/SXe/FIQG27wA27wAFJODFKRyhmu/u08/sy7/pv4/cir/FJQ7CGLTEIPudir/uz8/JOU6AMMB27wA27wA27wAFJODEJPjKPW8UZh/RXg/RYj/QXg/MSa/Zfo/pv4/diq/EJPg27wA27wA27wA27wA27wA27wAFKQDEIPLEJPtPVe/ahr/flv/jpz/diq/FJQtAJSB27wA27wA27wA27wA27wA27wA27wA27wAAMMBEJPeGLS5OUb/INU5EJPeAMMB27wA27wA27wA27wA27wA27wA27wA27wA27wA27wA27wAAAAAEIQEAAVA27wA27wA27wA27wA///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A")

icon_c_volumeintegrator = decodeIconStr("///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A27wA27wA27wA27wAMMMAMMMWNNN8NNN9MMMWMMMA27wA27wA27wA27wA///A27wA27wAAAAAEJPYIMS3MRY/KOU/gik/ggg/TTT/MMMzMMMR27wA27wA27wA27wA27wAAAVAFJPtVai/lr0/elv/Xeo/LRZ/NQU/ggh/ddd/RRR/MMMvMMMN27wA27wA27wAHKOvZel/rw5/cir/NTb/SYi/PWh/MSb/QVd/LQW/TWZ/aaa/PPP/MMMh27wAAAAAIMS/ty7/hmv/OSX/gik/HMS/bhq/nt2/pv4/sy6/diq/MQV/hhh/MMM/27wAFIQGRWd/u08/TYf/lmn/bdf/Uai/flv/Zfp/SZj/bgp/rx6/fks/NRV/MMN/27wAAJSBINT/uz8/glt/TWa/LPU/Xeo/SYi/KQY/SZk/IOW/Ydl/ty7/diq/IKO/27wA27wAIKO/flt/u08/Yel/JOW/QXi/HNV/TZi/Yfp/INT/LOT/ejr/tz8/IMT/AMMB27wAMMM/SWb/iow/u08/ciq/SZk/Yeo/gnw/Vaj/PRU/XXY/QVd/u08/SXe/FIQG27wAMMM/899/PTY/hmu/u08/sy7/pv4/cir/HLR/UVX/KOT/dir/uz8/JOU/AMMB27wAMMM/////vww/WZd/MRX/UZh/RXg/RYj/QXg/MSa/Zfo/pv4/diq/IKO/27wA27wAMMM/////999/////999/123/VZd/PVe/ahr/flv/jpz/diq/RUa/MMN/27wA27wAMMMxRRR/rrr/888/////////+++/jmp/MRX/OUb/NRX/WYb/PQQ/MMMx27wA27wA27wANNNEMMMaMMMxWWW/www/+++/999/uuu/UUV/MMMxMMMaNNNE27wA27wA///A27wA27wA27wA27wANNNIMMMfMMM1MMM1MMMfNNNI27wA27wA27wA27wA///A")

icon_help = decodeIconStr("///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A27wA27wA27wAAAAOGGGtFFF4HHH6GGG3GGGqAAAK27wA27wA27wA///A///A///A27wAAAABEEEnNNN7vvv/666/888/888/vvv/III7EEEgAAAA27wA///A///A///A27wAEEEmfff+333/333/333/lll/999/999/999/WWW8EEEd27wA///A///A///AAAAPSSS7333/zzz/111/xxx/III/+++/777/999/999/JJJ6AAAJ///A///A///AFFFtxxx/yyy/xxx/zzz/444/999/777/666/777/999/ppp/FFFh///A///A///AEEE4555/uuu/vvv/xxx/ttt/MMM/yyy/666/666/777/111/GGGy///A///A///AJJJ7666/sss/ttt/vvv/yyy/ttt/HHH/yyy/666/555/777/FFF5///A///A///ADDD3777/sss/qqq/lll/vvv/yyy/sss/EEE/777/444/xxx/GGGv///A///A///ADDDq000/xxx/iii/FFF/kkk/lll/hhh/HHH/555/333/kkk/DDDe///A///A///AAAAJNNN8999/rrr/iii/DDD/DDD/GGG/000/000/000/GGG6AAAE///A///A///A27wACCCcccc9999/yyy/ttt/sss/www/000/000/QQQ8CCCT27wA///A///A///A27wA27wACCCXMMM7www/444/777/000/ooo+III5BBBR27wA27wA///A///A///A27wA27wA27wAAAAFBBBbEEEsEEE1FFFqBBBZAAAD27wA27wA27wA///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A///A")


bar_spectrum = decodeBarStr("AAA/AAA/AAB/AAC/AAD/BAF/CAH/DAK/EAN/GAQ/HAU/JAX/LAb/MAf/OAj/PAm/QAq/RAt/SAv/SAx/SAz/SA1/SA3/SA4/SA5/RA6/PA6/OA6/MA6/IA5/CA4/AA3/AD2/AJ1/AN0/AQy/ATw/AVu/AYr/AZo/Abl/Adj/Aeg/Agd/Ahb/AiY/AjW/AlT/AmR/AnO/AoL/AqI/AqE/ArA/AsA/AtA/AuA/AvA/AvA/AwA/AwA/AwA/AwA/AwA/AwA/AwA/AwA/CwA/OvA/UvA/ZuA/euA/htA/lsA/orA/rqA/tpA/woA/ymA/0lA/2jA/4hA/5fA/7eA/8cA/9aA/+YA//VA//TA//QA//NA//KA//FA/+AA/+AA/8AA/7AA/6AA/5AA/3AA/2AA/0AA/yAA/wAA/uAA/sAA/qAA/oAA/lAA/jAA/hAA/fAA/dAA/bAA/ZAA/YAA/WAA/UAA/SAA/RAA/QAA/OAA/NAA/MAA/LAA/KAA/JAA/IAA/HAA/GAA/FAA/FAA/EAA/DAA/DAA/CAA/CAA/CAA/AAA/AAA/AAB/AAC/AAD/BAF/CAH/DAK/EAN/GAQ/HAU/JAX/LAb/MAf/OAj/PAm/QAq/RAt/SAv/SAx/SAz/SA1/SA3/SA4/SA5/RA6/PA6/OA6/MA6/IA5/CA4/AA3/AD2/AJ1/AN0/AQy/ATw/AVu/AYr/AZo/Abl/Adj/Aeg/Agd/Ahb/AiY/AjW/AlT/AmR/AnO/AoL/AqI/AqE/ArA/AsA/AtA/AuA/AvA/AvA/AwA/AwA/AwA/AwA/AwA/AwA/AwA/AwA/CwA/OvA/UvA/ZuA/euA/htA/lsA/orA/rqA/tpA/woA/ymA/0lA/2jA/4hA/5fA/7eA/8cA/9aA/+YA//VA//TA//QA//NA//KA//FA/+AA/+AA/8AA/7AA/6AA/5AA/3AA/2AA/0AA/yAA/wAA/uAA/sAA/qAA/oAA/lAA/jAA/hAA/fAA/dAA/bAA/ZAA/YAA/WAA/UAA/SAA/RAA/QAA/OAA/NAA/MAA/LAA/KAA/JAA/IAA/HAA/GAA/FAA/FAA/EAA/DAA/DAA/CAA/CAA/CAA/AAA/AAA/AAB/AAC/AAD/BAF/CAH/DAK/EAN/GAQ/HAU/JAX/LAb/MAf/OAj/PAm/QAq/RAt/SAv/SAx/SAz/SA1/SA3/SA4/SA5/RA6/PA6/OA6/MA6/IA5/CA4/AA3/AD2/AJ1/AN0/AQy/ATw/AVu/AYr/AZo/Abl/Adj/Aeg/Agd/Ahb/AiY/AjW/AlT/AmR/AnO/AoL/AqI/AqE/ArA/AsA/AtA/AuA/AvA/AvA/AwA/AwA/AwA/AwA/AwA/AwA/AwA/AwA/CwA/OvA/UvA/ZuA/euA/htA/lsA/orA/rqA/tpA/woA/ymA/0lA/2jA/4hA/5fA/7eA/8cA/9aA/+YA//VA//TA//QA//NA//KA//FA/+AA/+AA/8AA/7AA/6AA/5AA/3AA/2AA/0AA/yAA/wAA/uAA/sAA/qAA/oAA/lAA/jAA/hAA/fAA/dAA/bAA/ZAA/YAA/WAA/UAA/SAA/RAA/QAA/OAA/NAA/MAA/LAA/KAA/JAA/IAA/HAA/GAA/FAA/FAA/EAA/DAA/DAA/CAA/CAA/CAA/AAA/AAA/AAB/AAC/AAD/BAF/CAH/DAK/EAN/GAQ/HAU/JAX/LAb/MAf/OAj/PAm/QAq/RAt/SAv/SAx/SAz/SA1/SA3/SA4/SA5/RA6/PA6/OA6/MA6/IA5/CA4/AA3/AD2/AJ1/AN0/AQy/ATw/AVu/AYr/AZo/Abl/Adj/Aeg/Agd/Ahb/AiY/AjW/AlT/AmR/AnO/AoL/AqI/AqE/ArA/AsA/AtA/AuA/AvA/AvA/AwA/AwA/AwA/AwA/AwA/AwA/AwA/AwA/CwA/OvA/UvA/ZuA/euA/htA/lsA/orA/rqA/tpA/woA/ymA/0lA/2jA/4hA/5fA/7eA/8cA/9aA/+YA//VA//TA//QA//NA//KA//FA/+AA/+AA/8AA/7AA/6AA/5AA/3AA/2AA/0AA/yAA/wAA/uAA/sAA/qAA/oAA/lAA/jAA/hAA/fAA/dAA/bAA/ZAA/YAA/WAA/UAA/SAA/RAA/QAA/OAA/NAA/MAA/LAA/KAA/JAA/IAA/HAA/GAA/FAA/FAA/EAA/DAA/DAA/CAA/CAA/CAA/AAA/AAA/AAB/AAC/AAD/BAF/CAH/DAK/EAN/GAQ/HAU/JAX/LAb/MAf/OAj/PAm/QAq/RAt/SAv/SAx/SAz/SA1/SA3/SA4/SA5/RA6/PA6/OA6/MA6/IA5/CA4/AA3/AD2/AJ1/AN0/AQy/ATw/AVu/AYr/AZo/Abl/Adj/Aeg/Agd/Ahb/AiY/AjW/AlT/AmR/AnO/AoL/AqI/AqE/ArA/AsA/AtA/AuA/AvA/AvA/AwA/AwA/AwA/AwA/AwA/AwA/AwA/AwA/CwA/OvA/UvA/ZuA/euA/htA/lsA/orA/rqA/tpA/woA/ymA/0lA/2jA/4hA/5fA/7eA/8cA/9aA/+YA//VA//TA//QA//NA//KA//FA/+AA/+AA/8AA/7AA/6AA/5AA/3AA/2AA/0AA/yAA/wAA/uAA/sAA/qAA/oAA/lAA/jAA/hAA/fAA/dAA/bAA/ZAA/YAA/WAA/UAA/SAA/RAA/QAA/OAA/NAA/MAA/LAA/KAA/JAA/IAA/HAA/GAA/FAA/FAA/EAA/DAA/DAA/CAA/CAA/CAA/AAA/AAA/AAB/AAC/AAD/BAF/CAH/DAK/EAN/GAQ/HAU/JAX/LAb/MAf/OAj/PAm/QAq/RAt/SAv/SAx/SAz/SA1/SA3/SA4/SA5/RA6/PA6/OA6/MA6/IA5/CA4/AA3/AD2/AJ1/AN0/AQy/ATw/AVu/AYr/AZo/Abl/Adj/Aeg/Agd/Ahb/AiY/AjW/AlT/AmR/AnO/AoL/AqI/AqE/ArA/AsA/AtA/AuA/AvA/AvA/AwA/AwA/AwA/AwA/AwA/AwA/AwA/AwA/CwA/OvA/UvA/ZuA/euA/htA/lsA/orA/rqA/tpA/woA/ymA/0lA/2jA/4hA/5fA/7eA/8cA/9aA/+YA//VA//TA//QA//NA//KA//FA/+AA/+AA/8AA/7AA/6AA/5AA/3AA/2AA/0AA/yAA/wAA/uAA/sAA/qAA/oAA/lAA/jAA/hAA/fAA/dAA/bAA/ZAA/YAA/WAA/UAA/SAA/RAA/QAA/OAA/NAA/MAA/LAA/KAA/JAA/IAA/HAA/GAA/FAA/FAA/EAA/DAA/DAA/CAA/CAA/CAA/AAA/AAA/AAB/AAC/AAD/BAF/CAH/DAK/EAN/GAQ/HAU/JAX/LAb/MAf/OAj/PAm/QAq/RAt/SAv/SAx/SAz/SA1/SA3/SA4/SA5/RA6/PA6/OA6/MA6/IA5/CA4/AA3/AD2/AJ1/AN0/AQy/ATw/AVu/AYr/AZo/Abl/Adj/Aeg/Agd/Ahb/AiY/AjW/AlT/AmR/AnO/AoL/AqI/AqE/ArA/AsA/AtA/AuA/AvA/AvA/AwA/AwA/AwA/AwA/AwA/AwA/AwA/AwA/CwA/OvA/UvA/ZuA/euA/htA/lsA/orA/rqA/tpA/woA/ymA/0lA/2jA/4hA/5fA/7eA/8cA/9aA/+YA//VA//TA//QA//NA//KA//FA/+AA/+AA/8AA/7AA/6AA/5AA/3AA/2AA/0AA/yAA/wAA/uAA/sAA/qAA/oAA/lAA/jAA/hAA/fAA/dAA/bAA/ZAA/YAA/WAA/UAA/SAA/RAA/QAA/OAA/NAA/MAA/LAA/KAA/JAA/IAA/HAA/GAA/FAA/FAA/EAA/DAA/DAA/CAA/CAA/CAA/AAA/AAA/AAB/AAC/AAD/BAF/CAH/DAK/EAN/GAQ/HAU/JAX/LAb/MAf/OAj/PAm/QAq/RAt/SAv/SAx/SAz/SA1/SA3/SA4/SA5/RA6/PA6/OA6/MA6/IA5/CA4/AA3/AD2/AJ1/AN0/AQy/ATw/AVu/AYr/AZo/Abl/Adj/Aeg/Agd/Ahb/AiY/AjW/AlT/AmR/AnO/AoL/AqI/AqE/ArA/AsA/AtA/AuA/AvA/AvA/AwA/AwA/AwA/AwA/AwA/AwA/AwA/AwA/CwA/OvA/UvA/ZuA/euA/htA/lsA/orA/rqA/tpA/woA/ymA/0lA/2jA/4hA/5fA/7eA/8cA/9aA/+YA//VA//TA//QA//NA//KA//FA/+AA/+AA/8AA/7AA/6AA/5AA/3AA/2AA/0AA/yAA/wAA/uAA/sAA/qAA/oAA/lAA/jAA/hAA/fAA/dAA/bAA/ZAA/YAA/WAA/UAA/SAA/RAA/QAA/OAA/NAA/MAA/LAA/KAA/JAA/IAA/HAA/GAA/FAA/FAA/EAA/DAA/DAA/CAA/CAA/CAA/AAA/AAA/AAB/AAC/AAD/BAF/CAH/DAK/EAN/GAQ/HAU/JAX/LAb/MAf/OAj/PAm/QAq/RAt/SAv/SAx/SAz/SA1/SA3/SA4/SA5/RA6/PA6/OA6/MA6/IA5/CA4/AA3/AD2/AJ1/AN0/AQy/ATw/AVu/AYr/AZo/Abl/Adj/Aeg/Agd/Ahb/AiY/AjW/AlT/AmR/AnO/AoL/AqI/AqE/ArA/AsA/AtA/AuA/AvA/AvA/AwA/AwA/AwA/AwA/AwA/AwA/AwA/AwA/CwA/OvA/UvA/ZuA/euA/htA/lsA/orA/rqA/tpA/woA/ymA/0lA/2jA/4hA/5fA/7eA/8cA/9aA/+YA//VA//TA//QA//NA//KA//FA/+AA/+AA/8AA/7AA/6AA/5AA/3AA/2AA/0AA/yAA/wAA/uAA/sAA/qAA/oAA/lAA/jAA/hAA/fAA/dAA/bAA/ZAA/YAA/WAA/UAA/SAA/RAA/QAA/OAA/NAA/MAA/LAA/KAA/JAA/IAA/HAA/GAA/FAA/FAA/EAA/DAA/DAA/CAA/CAA/CAA/AAA4AAA/AAB/AAC/AAD/BAF/CAH/DAK/EAN/GAQ/HAU/JAX/LAb/MAf/OAj/PAm/QAq/RAt/SAv/SAx/SAz/SA1/SA3/SA4/SA5/RA6/PA6/OA6/MA6/IA5/CA4/AA3/AD2/AJ1/AN0/AQy/ATw/AVu/AYr/AZo/Abl/Adj/Aeg/Agd/Ahb/AiY/AjW/AlT/AmR/AnO/AoL/AqI/AqE/ArA/AsA/AtA/AuA/AvA/AvA/AwA/AwA/AwA/AwA/AwA/AwA/AwA/AwA/CwA/OvA/UvA/ZuA/euA/htA/lsA/orA/rqA/tpA/woA/ymA/0lA/2jA/4hA/5fA/7eA/8cA/9aA/+YA//VA//TA//QA//NA//KA//FA/+AA/+AA/8AA/7AA/6AA/5AA/3AA/2AA/0AA/yAA/wAA/uAA/sAA/qAA/oAA/lAA/jAA/hAA/fAA/dAA/bAA/ZAA/YAA/WAA/UAA/SAA/RAA/QAA/OAA/NAA/MAA/LAA/KAA/JAA/IAA/HAA/GAA/FAA/FAA/EAA/DAA/DAA/CAA/CAA/CAA4AAAsAAA/AAB/AAC/AAD/BAF/CAH/DAK/EAN/GAQ/HAU/JAX/LAb/MAf/OAj/PAm/QAq/RAt/SAv/SAx/SAz/SA1/SA3/SA4/SA5/RA6/PA6/OA6/MA6/IA5/CA4/AA3/AD2/AJ1/AN0/AQy/ATw/AVu/AYr/AZo/Abl/Adj/Aeg/Agd/Ahb/AiY/AjW/AlT/AmR/AnO/AoL/AqI/AqE/ArA/AsA/AtA/AuA/AvA/AvA/AwA/AwA/AwA/AwA/AwA/AwA/AwA/AwA/CwA/OvA/UvA/ZuA/euA/htA/lsA/orA/rqA/tpA/woA/ymA/0lA/2jA/4hA/5fA/7eA/8cA/9aA/+YA//VA//TA//QA//NA//KA//FA/+AA/+AA/8AA/7AA/6AA/5AA/3AA/2AA/0AA/yAA/wAA/uAA/sAA/qAA/oAA/lAA/jAA/hAA/fAA/dAA/bAA/ZAA/YAA/WAA/UAA/SAA/RAA/QAA/OAA/NAA/MAA/LAA/KAA/JAA/IAA/HAA/GAA/FAA/FAA/EAA/DAA/DAA/CAA/CAA/CAAsAAAcAAA/AAB/AAC/AAD/BAF/CAH/DAK/EAN/GAQ/HAU/JAX/LAb/MAf/OAj/PAm/QAq/RAt/SAv/SAx/SAz/SA1/SA3/SA4/SA5/RA6/PA6/OA6/MA6/IA5/CA4/AA3/AD2/AJ1/AN0/AQy/ATw/AVu/AYr/AZo/Abl/Adj/Aeg/Agd/Ahb/AiY/AjW/AlT/AmR/AnO/AoL/AqI/AqE/ArA/AsA/AtA/AuA/AvA/AvA/AwA/AwA/AwA/AwA/AwA/AwA/AwA/AwA/CwA/OvA/UvA/ZuA/euA/htA/lsA/orA/rqA/tpA/woA/ymA/0lA/2jA/4hA/5fA/7eA/8cA/9aA/+YA//VA//TA//QA//NA//KA//FA/+AA/+AA/8AA/7AA/6AA/5AA/3AA/2AA/0AA/yAA/wAA/uAA/sAA/qAA/oAA/lAA/jAA/hAA/fAA/dAA/bAA/ZAA/YAA/WAA/UAA/SAA/RAA/QAA/OAA/NAA/MAA/LAA/KAA/JAA/IAA/HAA/GAA/FAA/FAA/EAA/DAA/DAA/CAA/CAA/CAAcAAAKAAAzAAB/AAC/AAD/BAF/CAH/DAK/EAN/GAQ/HAU/JAX/LAb/MAf/OAj/PAm/QAq/RAt/SAv/SAx/SAz/SA1/SA3/SA4/SA5/RA6/PA6/OA6/MA6/IA5/CA4/AA3/AD2/AJ1/AN0/AQy/ATw/AVu/AYr/AZo/Abl/Adj/Aeg/Agd/Ahb/AiY/AjW/AlT/AmR/AnO/AoL/AqI/AqE/ArA/AsA/AtA/AuA/AvA/AvA/AwA/AwA/AwA/AwA/AwA/AwA/AwA/AwA/CwA/OvA/UvA/ZuA/euA/htA/lsA/orA/rqA/tpA/woA/ymA/0lA/2jA/4hA/5fA/7eA/8cA/9aA/+YA//VA//TA//QA//NA//KA//FA/+AA/+AA/8AA/7AA/6AA/5AA/3AA/2AA/0AA/yAA/wAA/uAA/sAA/qAA/oAA/lAA/jAA/hAA/fAA/dAA/bAA/ZAA/YAA/WAA/UAA/SAA/RAA/QAA/OAA/NAA/MAA/LAA/KAA/JAA/IAA/HAA/GAA/FAA/FAA/EAA/DAA/DAA/CAA/CAAzCAAK///AAAAaAAB/AAC/AAD/BAF/CAH/DAK/EAN/GAQ/HAU/JAX/LAb/MAf/OAj/PAm/QAq/RAt/SAv/SAx/SAz/SA1/SA3/SA4/SA5/RA6/PA6/OA6/MA6/IA5/CA4/AA3/AD2/AJ1/AN0/AQy/ATw/AVu/AYr/AZo/Abl/Adj/Aeg/Agd/Ahb/AiY/AjW/AlT/AmR/AnO/AoL/AqI/AqE/ArA/AsA/AtA/AuA/AvA/AvA/AwA/AwA/AwA/AwA/AwA/AwA/AwA/AwA/CwA/OvA/UvA/ZuA/euA/htA/lsA/orA/rqA/tpA/woA/ymA/0lA/2jA/4hA/5fA/7eA/8cA/9aA/+YA//VA//TA//QA//NA//KA//FA/+AA/+AA/8AA/7AA/6AA/5AA/3AA/2AA/0AA/yAA/wAA/uAA/sAA/qAA/oAA/lAA/jAA/hAA/fAA/dAA/bAA/ZAA/YAA/WAA/UAA/SAA/RAA/QAA/OAA/NAA/MAA/LAA/KAA/JAA/IAA/HAA/GAA/FAA/FAA/EAA/DAA/DAA/CAA/CAAa///A///A///AAABfAAC/AAD/BAF/CAH/DAK/EAN/GAQ/HAU/JAX/LAb/MAf/OAj/PAm/QAq/RAt/SAv/SAx/SAz/SA1/SA3/SA4/SA5/RA6/PA6/OA6/MA6/IA5/CA4/AA3/AD2/AJ1/AN0/AQy/ATw/AVu/AYr/AZo/Abl/Adj/Aeg/Agd/Ahb/AiY/AjW/AlT/AmR/AnO/AoL/AqI/AqE/ArA/AsA/AtA/AuA/AvA/AvA/AwA/AwA/AwA/AwA/AwA/AwA/AwA/AwA/CwA/OvA/UvA/ZuA/euA/htA/lsA/orA/rqA/tpA/woA/ymA/0lA/2jA/4hA/5fA/7eA/8cA/9aA/+YA//VA//TA//QA//NA//KA//FA/+AA/+AA/8AA/7AA/6AA/5AA/3AA/2AA/0AA/yAA/wAA/uAA/sAA/qAA/oAA/lAA/jAA/hAA/fAA/dAA/bAA/ZAA/YAA/WAA/UAA/SAA/RAA/QAA/OAA/NAA/MAA/LAA/KAA/JAA/IAA/HAA/GAA/FAA/FAA/EAA/DAA/DAA/CAAf///A///A///A///A///AAACaAADzBAF/CAH/DAK/EAN/GAQ/HAU/JAX/LAb/MAf/OAj/PAm/QAq/RAt/SAv/SAx/SAz/SA1/SA3/SA4/SA5/RA6/PA6/OA6/MA6/IA5/CA4/AA3/AD2/AJ1/AN0/AQy/ATw/AVu/AYr/AZo/Abl/Adj/Aeg/Agd/Ahb/AiY/AjW/AlT/AmR/AnO/AoL/AqI/AqE/ArA/AsA/AtA/AuA/AvA/AvA/AwA/AwA/AwA/AwA/AwA/AwA/AwA/AwA/CwA/OvA/UvA/ZuA/euA/htA/lsA/orA/rqA/tpA/woA/ymA/0lA/2jA/4hA/5fA/7eA/8cA/9aA/+YA//VA//TA//QA//NA//KA//FA/+AA/+AA/8AA/7AA/6AA/5AA/3AA/2AA/0AA/yAA/wAA/uAA/sAA/qAA/oAA/lAA/jAA/hAA/fAA/dAA/bAA/ZAA/YAA/WAA/UAA/SAA/RAA/QAA/OAA/NAA/MAA/LAA/KAA/JAA/IAA/HAA/GAA/FAA/FAA/EAA/DAAzDAAa///A///A///A///A///A///A///AAADKBAFcCAHsDAK4EAN/GAQ/HAU/JAX/LAb/MAf/OAj/PAm/QAq/RAt/SAv/SAx/SAz/SA1/SA3/SA4/SA5/RA6/PA6/OA6/MA6/IA5/CA4/AA3/AD2/AJ1/AN0/AQy/ATw/AVu/AYr/AZo/Abl/Adj/Aeg/Agd/Ahb/AiY/AjW/AlT/AmR/AnO/AoL/AqI/AqE/ArA/AsA/AtA/AuA/AvA/AvA/AwA/AwA/AwA/AwA/AwA/AwA/AwA/AwA/CwA/OvA/UvA/ZuA/euA/htA/lsA/orA/rqA/tpA/woA/ymA/0lA/2jA/4hA/5fA/7eA/8cA/9aA/+YA//VA//TA//QA//NA//KA//FA/+AA/+AA/8AA/7AA/6AA/5AA/3AA/2AA/0AA/yAA/wAA/uAA/sAA/qAA/oAA/lAA/jAA/hAA/fAA/dAA/bAA/ZAA/YAA/WAA/UAA/SAA/RAA/QAA/OAA/NAA/MAA/LAA/KAA/JAA/IAA/HAA/GAA/FAA4FAAsEAAcDAAK///A///A///A///A")

bar_blackbody = decodeBarStr("+LA/+LA/+MA/+NA/+OA/+QA/+RA/+SA/+TA/+VA/+WA/+XA/+ZA/+aA//bA//cA//eA//fA//gA//hA//iA//kA//lA//mA//nA//oA//oB//pD//pE//qF//qG//qH//rI//rJ//sK//sM//sN//tO//tP//uQ//uR//vS//vT//vU//wW//wX//xY//xZ//xa//yb//yc//zd//ze//zg//0h//0i//1j//1k//1l//2m//2n//3p//3q//4r//4s//4t//5u//5v//6w//6y//6y//70//71//82//83//84//95//96//+7//+9///9/////////////////+///++//++//++//++//9+//9+//99//99//89//89//89//88//88//78//78//78//78//67//67//67//67//57//57//56//56//56//46//46//46//45//35//35//35//35//24//24//24//24//24//13//13//13//13//03//03//03//02//z2//z2//z2//z2//02//+LA/+LA/+MA/+NA/+OA/+QA/+RA/+SA/+TA/+VA/+WA/+XA/+ZA/QQQ//bA//cA//eA//fA//gA//hA//iA//kA//lA//mA//nA//oA//oB//pD//pE//qF//qG//qH//rI//rJ/QQQ//sM//sN//tO//tP//uQ//uR//vS//vT//vU//wW//wX//xY//xZ//xa//yb//yc//zd//ze//zg//0h//0i//1j//1k//1l//2m//2n//3p//3q//4r//4s//4t//5u//5v//6w//6y//6y//70//71//82//83//84//95//96//+7//+9///9/////////////////QQQ/++//++//++//++//9+//9+//99//99//89//89//89//88//88//78//78//78//78//67//67//67//67//57//57//56//56//56//46//46//46//45//35//35//35//35//24//24//24//24//24//13//13//13//13//03//03//03//02//z2//z2//z2//z2//02//+LA/+LA/+MA/+NA/+OA/+QA/+RA/+SA/+TA/+VA/+WA/+XA/+ZA/QQQ//bA//cA//eA//fA//gA//hA//iA//kA//lA//mA//nA//oA//oB//pD//pE//qF//qG//qH//rI//rJ/QQQ//sM//sN//tO//tP//uQ//uR//vS//vT//vU//wW//wX//xY//xZ//xa//yb//yc//zd//ze//zg//0h//0i//1j//1k//1l//2m//2n//3p//3q//4r//4s//4t//5u//5v//6w//6y//6y//70//71//82//83//84//95//96//+7//+9///9/////////////////QQQ/++//++//++//++//9+//9+//99//99//89//89//89//88//88//78//78//78//78//67//67//67//67//57//57//56//56//56//46//46//46//45//35//35//35//35//24//24//24//24//24//13//13//13//13//03//03//03//02//z2//z2//z2//z2//02//+LA/+LA/+MA/+NA/+OA/+QA/+RA/+SA/+TA/+VA/+WA/+XA/+ZA/QQQ//bA//cA//eA//fA//gA//hA//iA//kA//lA//mA//nA//oA//oB//pD//pE//qF//qG//qH//rI//rJ/QQQ//sM//sN//tO//tP//uQ//uR//vS//vT//vU//wW//wX//xY//xZ//xa//yb//yc//zd//ze//zg//0h//0i//1j//1k//1l//2m//2n//3p//3q//4r//4s//4t//5u//5v//6w//6y//6y//70//71//82//83//84//95//96//+7//+9///9/////////////////QQQ/++//++//++//++//9+//9+//99//99//89//89//89//88//88//78//78//78//78//67//67//67//67//57//57//56//56//56//46//46//46//45//35//35//35//35//24//24//24//24//24//13//13//13//13//03//03//03//02//z2//z2//z2//z2//02//+LA/+LA/+MA/+NA/+OA/+QA/+RA/+SA/+TA/+VA/+WA/+XA/+ZA/QQQ//bA//cA//eA//fA//gA//hA//iA//kA//lA//mA//nA//oA//oB//pD//pE//qF//qG//qH//rI//rJ/QQQ//sM//sN//tO//tP//uQ//uR//vS//vT//vU//wW//wX//xY//xZ//xa//yb//yc//zd//ze//zg//0h//0i//1j//1k//1l//2m//2n//3p//3q//4r//4s//4t//5u//5v//6w//6y//6y//70//71//82//83//84//95//96//+7//+9///9/////////////////QQQ/++//++//++//++//9+//9+//99//99//89//89//89//88//88//78//78//78//78//67//67//67//67//57//57//56//56//56//46//46//46//45//35//35//35//35//24//24//24//24//24//13//13//13//13//03//03//03//02//z2//z2//z2//z2//02//+LA/+LA/+MA/+NA/+OA/+QA/+RA/+SA/+TA/+VA/+WA/+XA/+ZA/+aA//bA//cA//eA//fA//gA//hA//iA//kA//lA//mA//nA//oA//oB//pD//pE//qF//qG//qH//rI//rJ//sK//sM//sN//tO//tP//uQ//uR//vS//vT//vU//wW//wX//xY//xZ//xa//yb//yc//zd//ze//zg//0h//0i//1j//1k//1l//2m//2n//3p//3q//4r//4s//4t//5u//5v//6w//6y//6y//70//71//82//83//84//95//96//+7//+9///9/////////////////+///++//++//++//++//9+//9+//99//99//89//89//89//88//88//78//78//78//78//67//67//67//67//57//57//56//56//56//46//46//46//45//35//35//35//35//24//24//24//24//24//13//13//13//13//03//03//03//02//z2//z2//z2//z2//02//+LA/+LA/+MA/+NA/+OA/+QA/+RA/+SA/+TA/+VA/+WA/+XA/+ZA/QQQ/QQQ/QQQ//eA//fA//gA//hA//iA//kA//lA//mA//nA//oA//oB//pD//pE//qF//qG//qH//rI//rJ/QQQ//sM//sN//tO//tP//uQ//uR//vS//vT//vU//wW//wX//xY//xZ//xa//yb//yc//zd//ze//zg//0h//0i//1j//1k//1l//2m//2n//3p//3q//4r//4s//4t//5u//5v//6w//6y//6y//70//71//82//83//84//95//96//+7//+9///9/////////////////QQQ/QQQ/QQQ/++//++//9+//9+//99//99//89//89//89//88//88//78//78//78//78//67//67//67//67//57//57//56//56//56//46//46//46//45//35//35//35//35//24//24//24//24//24//13//13//13//13//03//03//03//02//z2//z2//z2//z2//02//+LA/+LA/+MA/+NA/+OA/+QA/+RA/+SA/+TA/+VA/+WA/+XA/+ZA/QQQ//bA//cA//eA//fA//gA//hA//iA//kA//lA//mA//nA//oA//oB//pD//pE//qF//qG//qH//rI//rJ/QQQ//sM//sN//tO//tP//uQ//uR//vS//vT//vU//wW//wX//xY//xZ//xa//yb//yc//zd//ze//zg//0h//0i//1j//1k//1l//2m//2n//3p//3q//4r//4s//4t//5u//5v//6w//6y//6y//70//71//82//83//84//95//96//+7//+9///9/////////////////QQQ/++//QQQ/++//++//9+//9+//99//99//89//89//89//88//88//78//78//78//78//67//67//67//67//57//57//56//56//56//46//46//46//45//35//35//35//35//24//24//24//24//24//13//13//13//13//03//03//03//02//z2//z2//z2//z2//02//+LA/+LA/+MA/+NA/+OA/+QA/+RA/+SA/+TA/+VA/+WA/+XA/+ZA/QQQ//bA//cA//eA//fA//gA//hA//iA//kA//lA//mA//nA//oA//oB//pD//pE//qF//qG//qH//rI//rJ/QQQ//sM//sN//tO//tP//uQ//uR//vS//vT//vU//wW//wX//xY//xZ//xa//yb//yc//zd//ze//zg//0h//0i//1j//1k//1l//2m//2n//3p//3q//4r//4s//4t//5u//5v//6w//6y//6y//70//71//82//83//84//95//96//+7//+9///9/////////////////QQQ/++//QQQ/++//++//9+//9+//99//99//89//89//89//88//88//78//78//78//78//67//67//67//67//57//57//56//56//56//46//46//46//45//35//35//35//35//24//24//24//24//24//13//13//13//13//03//03//03//02//z2//z2//z2//z2//02//+LA4+LA/+MA/+NA/+OA/+QA/+RA/+SA/+TA/+VA/+WA/+XA/+ZA/+aA/QQQ/QQQ//eA//fA//gA//hA//iA//kA//lA//mA//nA//oA//oB//pD//pE//qF//qG//qH//rI//rJ/QQQ//sM//sN//tO//tP//uQ//uR//vS//vT//vU//wW//wX//xY//xZ//xa//yb//yc//zd//ze//zg//0h//0i//1j//1k//1l//2m//2n//3p//3q//4r//4s//4t//5u//5v//6w//6y//6y//70//71//82//83//84//95//96//+7//+9///9/////////////////QQQ/QQQ/++//++//++//9+//9+//99//99//89//89//89//88//88//78//78//78//78//67//67//67//67//57//57//56//56//56//46//46//46//45//35//35//35//35//24//24//24//24//24//13//13//13//13//03//03//03//02//z2//z2//z2//z2//02//+LAs+LA/+MA/+NA/+OA/+QA/+RA/+SA/+TA/+VA/+WA/+XA/+ZA/+aA//bA//cA//eA//fA//gA//hA//iA//kA//lA//mA//nA//oA//oB//pD//pE//qF//qG//qH//rI//rJ//sK//sM//sN//tO//tP//uQ//uR//vS//vT//vU//wW//wX//xY//xZ//xa//yb//yc//zd//ze//zg//0h//0i//1j//1k//1l//2m//2n//3p//3q//4r//4s//4t//5u//5v//6w//6y//6y//70//71//82//83//84//95//96//+7//+9///9/////////////////+///++//++//++//++//9+//9+//99//99//89//89//89//88//88//78//78//78//78//67//67//67//67//57//57//56//56//56//46//46//46//45//35//35//35//35//24//24//24//24//24//13//13//13//13//03//03//03//02//z2//z2//z2//z2//02//+LAc+LA/+MA/+NA/+OA/+QA/+RA/+SA/+TA/+VA/+WA/+XA/+ZA/+aA//bA//cA//eA//fA//gA//hA//iA//kA//lA//mA//nA//oA//oB//pD//pE//qF//qG//qH//rI//rJ//sK//sM//sN//tO//tP//uQ//uR//vS//vT//vU//wW//wX//xY//xZ//xa//yb//yc//zd//ze//zg//0h//0i//1j//1k//1l//2m//2n//3p//3q//4r//4s//4t//5u//5v//6w//6y//6y//70//71//82//83//84//95//96//+7//+9///9/////////////////+///++//++//++//++//9+//9+//99//99//89//89//89//88//88//78//78//78//78//67//67//67//67//57//57//56//56//56//46//46//46//45//35//35//35//35//24//24//24//24//24//13//13//13//13//03//03//03//02//z2//z2//z2//z2//02//+LAK+LAz+MA/+NA/+OA/+QA/+RA/+SA/+TA/+VA/+WA/+XA/+ZA/+aA//bA//cA//eA//fA//gA//hA//iA//kA//lA//mA//nA//oA//oB//pD//pE//qF//qG//qH//rI//rJ//sK//sM//sN//tO//tP//uQ//uR//vS//vT//vU//wW//wX//xY//xZ//xa//yb//yc//zd//ze//zg//0h//0i//1j//1k//1l//2m//2n//3p//3q//4r//4s//4t//5u//5v//6w//6y//6y//70//71//82//83//84//95//96//+7//+9///9/////////////////+///++//++//++//++//9+//9+//99//99//89//89//89//88//88//78//78//78//78//67//67//67//67//57//57//56//56//56//46//46//46//45//35//35//35//35//24//24//24//24//24//13//13//13//13//03//03//03//02//z2//z2//z2//z2//02//+LAA+LAa+MA/+NA/+OA/+QA/+RA/+SA/+TA/+VA/+WA/+XA/+ZA/+aA//bA//cA//eA//fA//gA//hA//iA//kA//lA//mA//nA//oA//oB//pD//pE//qF//qG//qH//rI//rJ//sK//sM//sN//tO//tP//uQ//uR//vS//vT//vU//wW//wX//xY//xZ//xa//yb//yc//zd//ze//zg//0h//0i//1j//1k//1l//2m//2n//3p//3q//4r//4s//4t//5u//5v//6w//6y//6y//70//71//82//83//84//95//96//+7//+9///9/////////////////+///++//++//++//++//9+//9+//99//99//89//89//89//88//88//78//78//78//78//67//67//67//67//57//57//56//56//56//46//46//46//45//35//35//35//35//24//24//24//24//24//13//13//13//13//03//03//03//02//z2//z2//z2//z2//02//+LAA+LAA+MAf+NA/+OA/+QA/+RA/+SA/+TA/+VA/+WA/+XA/+ZA/+aA//bA//cA//eA//fA//gA//hA//iA//kA//lA//mA//nA//oA//oB//pD//pE//qF//qG//qH//rI//rJ//sK//sM//sN//tO//tP//uQ//uR//vS//vT//vU//wW//wX//xY//xZ//xa//yb//yc//zd//ze//zg//0h//0i//1j//1k//1l//2m//2n//3p//3q//4r//4s//4t//5u//5v//6w//6y//6y//70//71//82//83//84//95//96//+7//+9///9/////////////////+///++//++//++//++//9+//9+//99//99//89//89//89//88//88//78//78//78//78//67//67//67//67//57//57//56//56//56//46//46//46//45//35//35//35//35//24//24//24//24//24//13//13//13//13//03//03//03//02//z2//z2//z2//z2//02//+LAA+LAA+MAA+NAa+OAz+QA/+RA/+SA/+TA/+VA/+WA/+XA/+ZA/+aA//bA//cA//eA//fA//gA//hA//iA//kA//lA//mA//nA//oA//oB//pD//pE//qF//qG//qH//rI//rJ//sK//sM//sN//tO//tP//uQ//uR//vS//vT//vU//wW//wX//xY//xZ//xa//yb//yc//zd//ze//zg//0h//0i//1j//1k//1l//2m//2n//3p//3q//4r//4s//4t//5u//5v//6w//6y//6y//70//71//82//83//84//95//96//+7//+9///9/////////////////+///++//++//++//++//9+//9+//99//99//89//89//89//88//88//78//78//78//78//67//67//67//67//57//57//56//56//56//46//46//46//45//35//35//35//35//24//24//24//24//24//13//13//13//13//03//03//03//02//z2//z2//z2//z2//02//+LAA+LAA+MAA+NAA+OAK+QAc+RAs+SA4+TA/+VA/+WA/+XA/+ZA/+aA//bA//cA//eA//fA//gA//hA//iA//kA//lA//mA//nA//oA//oB//pD//pE//qF//qG//qH//rI//rJ//sK//sM//sN//tO//tP//uQ//uR//vS//vT//vU//wW//wX//xY//xZ//xa//yb//yc//zd//ze//zg//0h//0i//1j//1k//1l//2m//2n//3p//3q//4r//4s//4t//5u//5v//6w//6y//6y//70//71//82//83//84//95//96//+7//+9///9/////////////////+///++//++//++//++//9+//9+//99//99//89//89//89//88//88//78//78//78//78//67//67//67//67//57//57//56//56//56//46//46//46//45//35//35//35//35//24//24//24//24//24//13//13//13//13//03//03//03//02//z2//z2//z2//z2//02//")

bar_equalenergy = decodeBarStr("AAA/AAA/AAA/AAA/BBB/BBB/BBB/BBB/CCC/CCC/CDC/DDD/DDD/DDD/EEE/EEE/EFF/FFF/FFF/GGG/GGG/HGG/HHH/HHH/III/III/JJJ/JJJ/KJK/KKK/KKK/LLL/LLL/MMM/MMM/NNN/NNN/OOO/OOO/PPP/PPP/QQQ/QQQ/RRR/RRR/SSS/TSS/TTT/UUU/UUU/VVV/VVV/WWW/WWW/XXX/XXY/YYY/ZZZ/ZZZ/aaa/aaa/bbb/cbb/ccc/ddd/ddd/eee/eee/fff/ffg/ggg/hhh/hhh/iii/iii/jjj/kkk/kkk/lll/lll/mmm/mnm/nnn/ono/ooo/ppp/ppp/qqq/qqq/rrr/rrr/sss/sss/ttt/utu/uuu/vvv/vvv/www/www/xxx/xxx/yyy/yyy/zzz/zzz/000/000/111/111/122/222/222/333/333/444/444/545/555/555/666/666/667/777/777/788/888/888/999/999/999/9++/+++/+++/+++/////////////AAA/AAA/AAA/AAA/BBB/BBB/BBB/BBB/CCC/CCC/CCC/DDD/DDD/DDD/EEE/EEE/EEF/FFF/FFF/GGG/GGG/GGH/HHH/HHH/III/III/JJJ/JJJ/KJJ/KKK/KKK/LLL/LLL/MMM/MMM/NNN/NNN/OOO/OOO/PPP/PPP/QQQ/QQQ/RRR/RSR/SSS/TTT/TTT/UUU/UUU/VVV/VVV/WWW/WWW/XXX/YXX/YYY/ZZZ/ZZZ/aaa/aaa/bbb/cbb/ccc/ddd/ddd/eee/eee/fff/ffg/ggg/hhh/hhh/iii/iii/jjj/kkj/kkk/lll/lll/mmm/mmn/nnn/ono/ooo/ppp/ppp/qqq/qqq/rrr/rrr/sss/stt/ttt/tuu/uuu/vvv/vvv/www/www/xxx/xxx/yyy/yyy/zzz/zzz/000/000/111/111/111/222/222/333/333/444/444/554/555/555/666/666/766/777/777/777/888/888/999/999/999/9++/+++/+++/+++/////////////AAA/AAA/AAA/AAA/BBB/BBB/BBB/BCC/CCC/CCC/DCC/DDD/DDD/DDD/EEE/EEE/FEF/FFF/FFF/GGG/GGG/GGG/HHH/HHH/III/III/JJJ/JJJ/KJJ/KKK/KLK/LLL/LLL/MMM/MMM/NNN/NNN/OOO/OOO/PPP/PPP/QQQ/RQQ/RRR/SRR/SSS/STT/TTT/UTU/UUU/VVV/VVV/WWW/WWW/XXX/XXX/YYY/ZZZ/ZZZ/aaa/aaa/bbb/cbb/ccc/ddd/ddd/eee/eee/fff/ggg/ggg/hhh/hhh/iii/iii/jjj/jjk/kkk/lll/lll/mmm/mmm/nnn/ooo/ooo/ppp/ppp/qqq/qqq/rrr/rrr/sss/tst/ttt/utt/uuu/vvv/vvv/www/www/xxx/xxx/yyy/yyy/zzz/zzz/000/000/111/111/122/222/222/333/333/444/444/555/555/555/666/666/667/777/777/888/888/888/999/999/999/++9/+++/+++/+++/////////////AAA/AAA/AAA/AAA/BBB/BBB/BBB/BBB/CCC/CCC/CCC/DDD/DDD/DDD/EEE/EEE/FEE/FFF/FFF/GGG/GGG/HGG/HHH/HHH/III/III/JJJ/JJJ/JKJ/KKK/KKK/LLL/LLL/MMM/MMM/NNN/NNN/OOO/OOO/PPP/PPP/QQQ/QRQ/RRR/RRS/SSS/TST/TTT/UUU/UUU/VVV/VVV/WWW/WWW/XXX/XYY/YYY/ZZZ/ZZZ/aaa/aaa/bbb/bcc/ccc/ddd/ddd/eee/eee/fff/gfg/ggg/hhh/hhh/iii/iii/jjj/jjk/kkk/lll/lll/mmm/mmm/nnn/onn/ooo/ppp/ppp/qqq/qqq/rrr/rrr/sss/tst/ttt/uuu/uuu/vvv/vvv/www/www/xxx/xxx/yyy/yyy/zzz/zzz/000/000/111/111/211/222/222/333/333/444/444/455/555/555/666/666/776/777/777/887/888/888/899/999/999/999/+++/+++/+++/////////////AAA/AAA/AAA/AAA/BBB/BBB/BBB/CBC/CCC/CCC/CCC/DDD/DDD/DDD/EEE/EEE/EEF/FFF/FFF/GGG/GGG/HHG/HHH/HHH/III/III/JJJ/JJJ/KKJ/KKK/KKK/LLL/LLL/MMM/MMM/NNN/NNN/OOO/OOO/PPP/PPP/QQQ/QQR/RRR/RRR/SSS/STT/TTT/UUU/UUU/VVV/VVV/WWW/WWW/XXX/XXX/YYY/ZZZ/ZZZ/aaa/aaa/bbb/bcb/ccc/ddd/ddd/eee/eee/fff/gff/ggg/hhh/hhh/iii/iii/jjj/jkk/kkk/lll/lll/mmm/mmm/nnn/noo/ooo/ppp/ppp/qqq/qqq/rrr/rrr/sss/sss/ttt/uuu/uuu/vvv/vvv/www/www/xxx/xxx/yyy/yyy/zzz/zzz/000/000/111/111/211/222/322/333/333/444/444/554/555/555/666/666/766/777/777/878/888/888/999/999/999/+9+/+++/+++/+++/////////////AAA/AAA/AAA/AAA/BBB/BBB/BBB/BBB/CCC/CCC/CCC/DDD/DDD/DDD/EEE/EEE/EEF/FFF/FFF/GGG/GGG/GGH/HHH/HHH/III/III/JJJ/JJJ/KJJ/KKK/KKK/LLL/LLL/MMM/MMM/NNN/NNN/OOO/OOO/PPP/PPP/QQQ/QQQ/RRR/RSR/SSS/TTT/TTT/UUU/UUU/VVV/VVV/WWW/WWW/XXX/YXX/YYY/ZZZ/ZZZ/aaa/aaa/bbb/cbb/ccc/ddd/ddd/eee/eee/fff/ffg/ggg/hhh/hhh/iii/iii/jjj/kkj/kkk/lll/lll/mmm/mmn/nnn/ono/ooo/ppp/ppp/qqq/qqq/rrr/rrr/sss/stt/ttt/tuu/uuu/vvv/vvv/www/www/xxx/xxx/yyy/yyy/zzz/zzz/000/000/111/111/111/222/222/333/333/444/444/554/555/555/666/666/766/777/777/777/888/888/999/999/999/9++/+++/+++/+++/////////////AAA/AAA/AAA/AAA/BBB/BBB/BBB/BCC/CCC/CCC/DCC/DDD/DDD/DDD/EEE/EEE/FEF/FFF/FFF/GGG/GGG/GGG/HHH/HHH/III/III/JJJ/JJJ/KJJ/KKK/KLK/LLL/LLL/MMM/MMM/NNN/NNN/OOO/OOO/PPP/PPP/QQQ/RQQ/RRR/SRR/SSS/STT/TTT/UTU/UUU/VVV/VVV/WWW/WWW/XXX/XXX/YYY/ZZZ/ZZZ/aaa/aaa/bbb/cbb/ccc/ddd/ddd/eee/eee/fff/ggg/ggg/hhh/hhh/iii/iii/jjj/jjk/kkk/lll/lll/mmm/mmm/nnn/ooo/ooo/ppp/ppp/qqq/qqq/rrr/rrr/sss/tst/ttt/utt/uuu/vvv/vvv/www/www/xxx/xxx/yyy/yyy/zzz/zzz/000/000/111/111/122/222/222/333/333/444/444/555/555/555/666/666/667/777/777/888/888/888/999/999/999/++9/+++/+++/+++/////////////AAA/AAA/AAA/AAA/BBB/BBB/BBB/BBB/CCC/CCC/CCC/DDD/DDD/DDD/EEE/EEE/FEE/FFF/FFF/GGG/GGG/HGG/HHH/HHH/III/III/JJJ/JJJ/JKJ/KKK/KKK/LLL/LLL/MMM/MMM/NNN/NNN/OOO/OOO/PPP/PPP/QQQ/QRQ/RRR/RRS/SSS/TST/TTT/UUU/UUU/VVV/VVV/WWW/WWW/XXX/XYY/YYY/ZZZ/ZZZ/aaa/aaa/bbb/bcc/ccc/ddd/ddd/eee/eee/fff/gfg/ggg/hhh/hhh/iii/iii/jjj/jjk/kkk/lll/lll/mmm/mmm/nnn/onn/ooo/ppp/ppp/qqq/qqq/rrr/rrr/sss/tst/ttt/uuu/uuu/vvv/vvv/www/www/xxx/xxx/yyy/yyy/zzz/zzz/000/000/111/111/211/222/222/333/333/444/444/455/555/555/666/666/776/777/777/887/888/888/899/999/999/999/+++/+++/+++/////////////AAA/AAA/AAA/AAA/BBB/BBB/BBB/CBC/CCC/CCC/CCC/DDD/DDD/DDD/EEE/EEE/EEF/FFF/FFF/GGG/GGG/HHG/HHH/HHH/III/III/JJJ/JJJ/KKJ/KKK/KKK/LLL/LLL/MMM/MMM/NNN/NNN/OOO/OOO/PPP/PPP/QQQ/QQR/RRR/RRR/SSS/STT/TTT/UUU/UUU/VVV/VVV/WWW/WWW/XXX/XXX/YYY/ZZZ/ZZZ/aaa/aaa/bbb/bcb/ccc/ddd/ddd/eee/eee/fff/gff/ggg/hhh/hhh/iii/iii/jjj/jkk/kkk/lll/lll/mmm/mmm/nnn/noo/ooo/ppp/ppp/qqq/qqq/rrr/rrr/sss/sss/ttt/uuu/uuu/vvv/vvv/www/www/xxx/xxx/yyy/yyy/zzz/zzz/000/000/111/111/211/222/322/333/333/444/444/554/555/555/666/666/766/777/777/878/888/888/999/999/999/+9+/+++/+++/+++/////////////GBA+AAA/AAA/AAA/BBB/BBB/BBB/BBB/CCC/CCC/CCC/DDD/DDD/DDD/EEE/EEE/EEF/FFF/FFF/GGG/GGG/GGH/HHH/HHH/III/III/JJJ/JJJ/KJJ/KKK/KKK/LLL/LLL/MMM/MMM/NNN/NNN/OOO/OOO/PPP/PPP/QQQ/QQQ/RRR/RSR/SSS/TTT/TTT/UUU/UUU/VVV/VVV/WWW/WWW/XXX/YXX/YYY/ZZZ/ZZZ/aaa/aaa/bbb/cbb/ccc/ddd/ddd/eee/eee/fff/ffg/ggg/hhh/hhh/iii/iii/jjj/kkj/kkk/lll/lll/mmm/mmn/nnn/ono/ooo/ppp/ppp/qqq/qqq/rrr/rrr/sss/stt/ttt/tuu/uuu/vvv/vvv/www/www/xxx/xxx/yyy/yyy/zzz/zzz/000/000/111/111/111/222/222/333/333/444/444/554/555/555/666/666/766/777/777/777/888/888/999/999/999/9++/+++/+++/+++/////////++/+OCA5AAA/AAA/AAA/BBB/BBB/BBB/BCC/CCC/CCC/DCC/DDD/DDD/DDD/EEE/EEE/FEF/FFF/FFF/GGG/GGG/GGG/HHH/HHH/III/III/JJJ/JJJ/KJJ/KKK/KLK/LLL/LLL/MMM/MMM/NNN/NNN/OOO/OOO/PPP/PPP/QQQ/RQQ/RRR/SRR/SSS/STT/TTT/UTU/UUU/VVV/VVV/WWW/WWW/XXX/XXX/YYY/ZZZ/ZZZ/aaa/aaa/bbb/cbb/ccc/ddd/ddd/eee/eee/fff/ggg/ggg/hhh/hhh/iii/iii/jjj/jjk/kkk/lll/lll/mmm/mmm/nnn/ooo/ooo/ppp/ppp/qqq/qqq/rrr/rrr/sss/tst/ttt/utt/uuu/vvv/vvv/www/www/xxx/xxx/yyy/yyy/zzz/zzz/000/000/111/111/122/222/222/333/333/444/444/555/555/555/666/666/667/777/777/888/888/888/999/999/999/++9/+++/+++/+++/////////89/5WEAsAAA/AAA/AAA/BBB/BBB/BBB/BBB/CCC/CCC/CCC/DDD/DDD/DDD/EEE/EEE/FEE/FFF/FFF/GGG/GGG/HGG/HHH/HHH/III/III/JJJ/JJJ/JKJ/KKK/KKK/LLL/LLL/MMM/MMM/NNN/NNN/OOO/OOO/PPP/PPP/QQQ/QRQ/RRR/RRS/SSS/TST/TTT/UUU/UUU/VVV/VVV/WWW/WWW/XXX/XYY/YYY/ZZZ/ZZZ/aaa/aaa/bbb/bcc/ccc/ddd/ddd/eee/eee/fff/gfg/ggg/hhh/hhh/iii/iii/jjj/jjk/kkk/lll/lll/mmm/mmm/nnn/onn/ooo/ppp/ppp/qqq/qqq/rrr/rrr/sss/tst/ttt/uuu/uuu/vvv/vvv/www/www/xxx/xxx/yyy/yyy/zzz/zzz/000/000/111/111/211/222/222/333/333/444/444/455/555/555/666/666/776/777/777/887/888/888/899/999/999/999/+++/+++/+++/////////78/scFASKCA9AAA/AAA/BBB/BBB/BBB/CBC/CCC/CCC/CCC/DDD/DDD/DDD/EEE/EEE/EEF/FFF/FFF/GGG/GGG/HHG/HHH/HHH/III/III/JJJ/JJJ/KKJ/KKK/KKK/LLL/LLL/MMM/MMM/NNN/NNN/OOO/OOO/PPP/PPP/QQQ/QQR/RRR/RRR/SSS/STT/TTT/UUU/UUU/VVV/VVV/WWW/WWW/XXX/XXX/YYY/ZZZ/ZZZ/aaa/aaa/bbb/bcb/ccc/ddd/ddd/eee/eee/fff/gff/ggg/hhh/hhh/iii/iii/jjj/jkk/kkk/lll/lll/mmm/mmm/nnn/noo/ooo/ppp/ppp/qqq/qqq/rrr/rrr/sss/sss/ttt/uuu/uuu/vvv/vvv/www/www/xxx/xxx/yyy/yyy/zzz/zzz/000/000/111/111/211/222/322/333/333/444/444/554/555/555/666/666/766/777/777/878/888/888/999/999/999/+9+/+++/+++/+++/////99/967/S///AXEApBAA/AAA/BBB/BBB/BBB/BBB/CCC/CCC/CCC/DDD/DDD/DDD/EEE/EEE/EEF/FFF/FFF/GGG/GGG/GGH/HHH/HHH/III/III/JJJ/JJJ/KJJ/KKK/KKK/LLL/LLL/MMM/MMM/NNN/NNN/OOO/OOO/PPP/PPP/QQQ/QQQ/RRR/RSR/SSS/TTT/TTT/UUU/UUU/VVV/VVV/WWW/WWW/XXX/YXX/YYY/ZZZ/ZZZ/aaa/aaa/bbb/cbb/ccc/ddd/ddd/eee/eee/fff/ffg/ggg/hhh/hhh/iii/iii/jjj/kkj/kkk/lll/lll/mmm/mmn/nnn/ono/ooo/ppp/ppp/qqq/qqq/rrr/rrr/sss/stt/ttt/tuu/uuu/vvv/vvv/www/www/xxx/xxx/yyy/yyy/zzz/zzz/000/000/111/111/111/222/222/333/333/444/444/554/555/555/666/666/766/777/777/777/888/888/999/999/999/9++/+++/+++/+++/////67/p///A///A///AVEAvBAA/BBB/BBB/BBB/BCC/CCC/CCC/DCC/DDD/DDD/DDD/EEE/EEE/FEF/FFF/FFF/GGG/GGG/GGG/HHH/HHH/III/III/JJJ/JJJ/KJJ/KKK/KLK/LLL/LLL/MMM/MMM/NNN/NNN/OOO/OOO/PPP/PPP/QQQ/RQQ/RRR/SRR/SSS/STT/TTT/UTU/UUU/VVV/VVV/WWW/WWW/XXX/XXX/YYY/ZZZ/ZZZ/aaa/aaa/bbb/cbb/ccc/ddd/ddd/eee/eee/fff/ggg/ggg/hhh/hhh/iii/iii/jjj/jjk/kkk/lll/lll/mmm/mmm/nnn/ooo/ooo/ppp/ppp/qqq/qqq/rrr/rrr/sss/tst/ttt/utt/uuu/vvv/vvv/www/www/xxx/xxx/yyy/yyy/zzz/zzz/000/000/111/111/122/222/222/333/333/444/444/555/555/555/666/666/667/777/777/888/888/888/999/999/999/++9/+++/+++/+++/78/v///A///A///A///A///AXFApKDA9BBB/BBB/BBB/CCC/CCC/CCC/DDD/DDD/DDD/EEE/EEE/FEE/FFF/FFF/GGG/GGG/HGG/HHH/HHH/III/III/JJJ/JJJ/JKJ/KKK/KKK/LLL/LLL/MMM/MMM/NNN/NNN/OOO/OOO/PPP/PPP/QQQ/QRQ/RRR/RRS/SSS/TST/TTT/UUU/UUU/VVV/VVV/WWW/WWW/XXX/XYY/YYY/ZZZ/ZZZ/aaa/aaa/bbb/bcc/ccc/ddd/ddd/eee/eee/fff/gfg/ggg/hhh/hhh/iii/iii/jjj/jjk/kkk/lll/lll/mmm/mmm/nnn/onn/ooo/ppp/ppp/qqq/qqq/rrr/rrr/sss/tst/ttt/uuu/uuu/vvv/vvv/www/www/xxx/xxx/yyy/yyy/zzz/zzz/000/000/111/111/211/222/222/333/333/444/444/455/555/555/666/666/776/777/777/887/888/888/899/999/999/999/+++/89+967/p///A///A///A///A///A///A///AdHASXGAsQFB5IDB+CCC/CCC/CCC/DDD/DDD/DDD/EEE/EEE/EEF/FFF/FFF/GGG/GGG/HHG/HHH/HHH/III/III/JJJ/JJJ/KKJ/KKK/KKK/LLL/LLL/MMM/MMM/NNN/NNN/OOO/OOO/PPP/PPP/QQQ/QQR/RRR/RRR/SSS/STT/TTT/UUU/UUU/VVV/VVV/WWW/WWW/XXX/XXX/YYY/ZZZ/ZZZ/aaa/aaa/bbb/bcb/ccc/ddd/ddd/eee/eee/fff/gff/ggg/hhh/hhh/iii/iii/jjj/jkk/kkk/lll/lll/mmm/mmm/nnn/noo/ooo/ppp/ppp/qqq/qqq/rrr/rrr/sss/sss/ttt/uuu/uuu/vvv/vvv/www/www/xxx/xxx/yyy/yyy/zzz/zzz/000/000/111/111/211/222/322/333/333/444/444/554/555/555/666/666/766/777/777/878/888/888/999/999/88++78+567+s56/S///A///A///A///A") 

def drawIcon(icon, x, y):
    BGL.glEnable(BGL.GL_BLEND)
    BGL.glBlendFunc(BGL.GL_SRC_ALPHA, BGL.GL_ONE_MINUS_SRC_ALPHA) 
    BGL.glRasterPos2f(int(x)+0.5, int(y)+0.5)
    BGL.glDrawPixels(16, 16, BGL.GL_RGBA, BGL.GL_UNSIGNED_BYTE, icon)
    BGL.glDisable(BGL.GL_BLEND)

def drawLogo(icon, x, y):
    BGL.glEnable(BGL.GL_BLEND)
    BGL.glBlendFunc(BGL.GL_SRC_ALPHA, BGL.GL_ONE_MINUS_SRC_ALPHA) 
    BGL.glRasterPos2f(int(x)+0.5, int(y)+0.5)
    BGL.glDrawPixels(118, 18, BGL.GL_RGBA, BGL.GL_UNSIGNED_BYTE, icon)
    BGL.glDisable(BGL.GL_BLEND)

def drawBar(icon, x, y):
    BGL.glEnable(BGL.GL_BLEND)
    BGL.glBlendFunc(BGL.GL_SRC_ALPHA, BGL.GL_ONE_MINUS_SRC_ALPHA) 
    BGL.glRasterPos2f(int(x)+0.5, int(y)+0.5)
    BGL.glDrawPixels(138, 17, BGL.GL_RGBA, BGL.GL_UNSIGNED_BYTE, icon)
    BGL.glDisable(BGL.GL_BLEND)



#-------------------------------------------------
# luxImage()
# helper class to handle images and icons for the GUI
#-------------------------------------------------

class luxImage:
    def resize(self, width, height):
        self.width = width
        self.height = height
        self.buf = BGL.Buffer(BGL.GL_BYTE, [width,height,4]) # GL buffer
    def __init__(self, width=0, height=0):
        self.resize(width, height)
    def draw(self, x, y):
        BGL.glEnable(BGL.GL_BLEND)
        BGL.glBlendFunc(BGL.GL_SRC_ALPHA, BGL.GL_ONE_MINUS_SRC_ALPHA) 
        BGL.glRasterPos2f(int(x)+0.5, int(y)+0.5)
        BGL.glDrawPixels(self.width, self.height, BGL.GL_RGBA, BGL.GL_UNSIGNED_BYTE, self.buf)
        BGL.glDisable(BGL.GL_BLEND)        
    def decodeStr(self, width, height, s):
        self.resize(width, height)
        offset = 0
        for y in range(self.height):
            for x in range(self.width):
                for c in range(4):
                    self.buf[y][x][c] = int(base64value(s[offset])*4.048)
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


previewCache = {}  # dictionary that will hold all preview images


######################################################
# New GUI by Zuegs
######################################################

from types import *

evtLuxGui = 99
evtSavePreset = 98
evtDeletePreset = 97
evtSaveMaterial = 96
evtLoadMaterial = 95
evtDeleteMaterial = 94
evtConvertMaterial = 92
evtSaveMaterial2 = 91
evtLoadMaterial2 = 90


# default settings
defaultsExclude = ['preset','filename','page','link']
try:
    luxdefaults = Blender.Registry.GetKey('luxblend', True)
    if not(type(luxdefaults) is DictType):
        luxdefaults = {}
except:
    luxdefaults = {}
newluxdefaults = luxdefaults.copy()


def saveluxdefaults():
    try: del newluxdefaults['page']
    except: pass
    try: Blender.Registry.SetKey('luxblend', newluxdefaults, True)
    except: pass





# *** PRESETS **************************************
presetsExclude = ['preset','lux','datadir','threads','filename','page','RGC','film.gamma','colorclamp','link']
def getPresets(key):
    presets = Blender.Registry.GetKey(key, True)
    if not(type(presets) is DictType):
        presets = {}
    return presets
def getScenePresets():
    presets = getPresets('luxblend_presets').copy()

    # radiance's hardcoded render presets:

    presets['0 Preview - Direct Lighting'] = {
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
    'pixelfilter.mitchell.optmode': "slider" }

    presets['1 Final - MLT/Bidir Path Tracing (interior) (recommended)'] =  {
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
    'pixelfilter.mitchell.optmode': "slider" }

    presets['2 Final - MLT/Path Tracing (exterior)'] =  {
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
    'pixelfilter.mitchell.optmode': "slider" }
    
    presets['4 '] = { }

    presets['5 Progressive - Bidir Path Tracing (interior)'] =  {
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
    'pixelfilter.mitchell.optmode': "slider" }

    presets['6 Progressive - Path Tracing (exterior)'] =  {
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
    'pixelfilter.mitchell.optmode': "slider" }

    presets['7 '] = { }

    presets['8 Bucket - Bidir Path Tracing (interior)'] =  {
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
    'pixelfilter.mitchell.optmode': "slider" }

    presets['9 Bucket - Path Tracing (exterior)'] =  {
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
    'pixelfilter.mitchell.optmode': "slider" }

    presets['A '] = { }

    presets['B Anim - Distributed/GI low Q'] =  {
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
    'pixelfilter.mitchell.optmode': "slider" }

    presets['C Anim - Distributed/GI medium Q'] =  {
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
    'pixelfilter.mitchell.optmode': "slider" }
    
    presets['D Anim - Distributed/GI high Q'] =  {
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
    'pixelfilter.mitchell.optmode': "slider" }

    presets['E Anim - Distributed/GI very high Q'] =  {
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
    'pixelfilter.mitchell.optmode': "slider" }

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


# **************************************************


# some helpers
def luxstr(str):
    return str.replace("\\", "\\\\") # todo: do encode \ and " signs by a additional backslash



usedproperties = {} # global variable to collect used properties for storing presets
usedpropertiesfilterobj = None # assign a object to only collect the properties that are assigned to this object

# class to access properties (for lux settings)
class luxProp:
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
        try:
            if (l==None) or (len(l) != 3): l = self.default.split(" ")
            return (float(l[0]), float(l[1]), float(l[2]))
        except AttributeError:
            return (float(l[0]), float(l[0]), float(l[0]))
        
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


# class to access blender attributes (for lux settings)
class luxAttr:
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


# class for dynamic gui
class luxGui:
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
        if color!=None:    BGL.glColor3f(color[0],color[1],color[2]); BGL.glRectf(0,self.y-self.hmax,self.xmax,self.y+distance); BGL.glColor3f(0.9, 0.9, 0.9)
        if icon!=None: drawIcon(icon, 2+level*10, self.y-16)
        self.resethmax = True
        if title!="":
            self.getRect(0, 1)
            BGL.glColor3f(0.9,0.9,0.9); BGL.glRasterPos2i(20+level*10,self.y-self.h+5); Draw.Text(title)
    
def luxHelp(name, lux, caption, hint, gui, width=1.0):
    if gui:
        r = gui.getRect(width, 1)
        Draw.Toggle(caption, evtLuxGui, r[0], r[1], r[2], r[3], lux.get()=="true", hint, lambda e,v: lux.set(["false","true"][bool(v)]))
        drawIcon(icon_help, r[0], r[1])

    return "\n   \"bool %s\" [\"%s\"]"%(name, lux.get())

# lux parameter types
def luxOption(name, lux, options, caption, hint, gui, width=1.0):
    if gui:
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
        r = gui.getRect(width, 1)
        Draw.Menu(menustr, evtLuxGui, r[0], r[1], r[2], r[3], i, hint, lambda e,v: lux.set(options[v]))
    return "\n   \"string %s\" [\"%s\"]"%(name, lux.get())

def luxOptionRect(name, lux, options, caption, hint, gui, x, y, xx, yy):
    if gui:
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
        Draw.Menu(menustr, evtLuxGui, x, y, xx, yy, i, hint, lambda e,v: lux.set(options[v]))
    return "\n   \"string %s\" [\"%s\"]"%(name, lux.get())

def luxIdentifier(name, lux, options, caption, hint, gui, icon=None, width=1.0):
    if gui: gui.newline(caption+":", 8, 0, icon, [0.75,0.5,0.25])
    luxOption(name, lux, options, caption, hint, gui, width)
    return "\n%s \"%s\""%(name, lux.get())

def luxFloat(name, lux, min, max, caption, hint, gui, width=1.0, useslider=0):
    if gui:
        if (luxProp(Scene.GetCurrent(), "useparamkeys", "false").get()=="true"):
            r = gui.getRect(width-0.12, 1)
        else:
            r = gui.getRect(width, 1)

        # Value
        if(useslider==1):
            Draw.Slider(caption+": ", evtLuxGui, r[0], r[1], r[2], r[3], lux.getFloat(), min, max, 0, hint, lambda e,v: lux.set(v))
        else:
            Draw.Number(caption+": ", evtLuxGui, r[0], r[1], r[2], r[3], lux.getFloat(), min, max, hint, lambda e,v: lux.set(v))
        if (luxProp(Scene.GetCurrent(), "useparamkeys", "false").get()=="true"):
            # IPO Curve
            obj = lux.getobj()
            keyname = lux.getname()
    
            useipo = luxProp(obj, keyname+".IPOuse", "false")
            i = gui.getRect(0.12, 1)
            Draw.Toggle("I", evtLuxGui, i[0], i[1], i[2], i[3], useipo.get()=="true", "Use IPO Curve", lambda e,v: useipo.set(["false","true"][bool(v)]))
            
            if useipo.get() == "true":
                if gui: gui.newline(caption+"IPO:", 8, 0, None, [0.5,0.45,0.35])
                curve = luxProp(obj, keyname+".IPOCurveName", "") 
                if curve.get() == "":
                    c = gui.getRect(2.0, 1)
                else:
                    c = gui.getRect(1.1, 1)
                
                Draw.String("Ipo:", evtLuxGui, c[0], c[1], c[2], c[3], curve.get(), 250, "Set IPO Name", lambda e,v: curve.set(v))
                
                usemapping = luxProp(obj, keyname+".IPOmap", "false")
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
                        ipotype = luxProp(obj, keyname+".IPOCurveType", "OB_LOCZ")
                        luxOption("ipocurve", ipotype, names, "IPO Curve", "Set IPO Curve", gui, 0.6)
    
                        icu = ipoob[eval("Blender.Ipo.%s" % (ipotype.get()))]
                        icu_value = icu[Blender.Get('curframe')]
                        if usemapping.get() == "false": # if true is set during mapping below
                            lux.set(icu_value)    
    
                        # Mapping options
                        m = gui.getRect(0.3, 1)
                        Draw.Toggle("Map", evtLuxGui, m[0], m[1], m[2], m[3], usemapping.get()=="true", "Edit Curve mapping", lambda e,v: usemapping.set(["false","true"][bool(v)]))
                        if usemapping.get() == "true":
                            if gui: gui.newline(caption+"IPO:", 8, 0, None, [0.5,0.45,0.35])
                            fmin = luxProp(obj, keyname+".IPOCurvefmin", 0.0)
                            luxFloatNoIPO("ipofmin", fmin, -100, 100, "fmin", "Map minimum value from Curve", gui, 0.5)
                            fmax = luxProp(obj, keyname+".IPOCurvefmax", 1.0)
                            luxFloatNoIPO("ipofmax", fmax, -100, 100, "fmax", "Map maximum value from Curve", gui, 0.5)
                            tmin = luxProp(obj, keyname+".IPOCurvetmin", min)
                            luxFloatNoIPO("ipotmin", tmin, min, max, "tmin", "Map miminum value to", gui, 0.5)
                            tmax = luxProp(obj, keyname+".IPOCurvetmax", max)
                            luxFloatNoIPO("ipotmax", tmax, min, max, "tmax", "Map maximum value to", gui, 0.5)
    
                            sval = (icu_value - fmin.getFloat()) / (fmax.getFloat() - fmin.getFloat())
                            lux.set(tmin.getFloat() + (sval * (tmax.getFloat() - tmin.getFloat())))

                            # invert
                            #v = gui.getRect(0.5, 1)
                            #Draw.Toggle("Invert", evtLuxGui, v[0], v[1], v[2], v[3], useipo.get()=="true", "Invert Curve values", lambda e,v: useipo.set(["false","true"][bool(v)]))
    else:
        if (luxProp(Scene.GetCurrent(), "useparamkeys", "false").get()=="true"):
            obj = lux.getobj()
            keyname = lux.getname()
            useipo = luxProp(obj, keyname+".IPOuse", "false")
            if useipo.get() == "true":
                curve = luxProp(obj, keyname+".IPOCurveName", "") 
                try:
                    ipoob = Blender.Ipo.Get(curve.get())
                except: 
                    curve.set("")
                pass
                usemapping = luxProp(obj, keyname+".IPOmap", "false")
                icu_value = 0
                if curve.get() != "":
                    names = list([x[0] for x in ipoob.curveConsts.items()])
                    ipotype = luxProp(obj, keyname+".IPOCurveType", "OB_LOCZ")
    
                    icu = ipoob[eval("Blender.Ipo.%s" % (ipotype.get()))]
                    icu_value = icu[Blender.Get('curframe')]
                    if usemapping.get() == "false": # if true is set during mapping below
                        lux.set(icu_value)    
    
                if usemapping.get() == "true":
                    if gui: gui.newline(caption+"IPO:", 8, 0, None, [0.5,0.45,0.35])
                    fmin = luxProp(obj, keyname+".IPOCurvefmin", 0.0)
                    fmax = luxProp(obj, keyname+".IPOCurvefmax", 1.0)
                    tmin = luxProp(obj, keyname+".IPOCurvetmin", min)
                    tmax = luxProp(obj, keyname+".IPOCurvetmax", max)
                    sval = (icu_value - fmin.getFloat()) / (fmax.getFloat() - fmin.getFloat())
                    lux.set(tmin.getFloat() + (sval * (tmax.getFloat() - tmin.getFloat())))

    return "\n   \"float %s\" [%f]"%(name, lux.getFloat())

def luxFloatNoIPO(name, lux, min, max, caption, hint, gui, width=1.0, useslider=0):
    if gui:
        r = gui.getRect(width, 1)
        if(useslider==1):
            Draw.Slider(caption+": ", evtLuxGui, r[0], r[1], r[2], r[3], lux.getFloat(), min, max, 0, hint, lambda e,v: lux.set(v))
        else:
            Draw.Number(caption+": ", evtLuxGui, r[0], r[1], r[2], r[3], lux.getFloat(), min, max, hint, lambda e,v: lux.set(v))
    return "\n   \"float %s\" [%f]"%(name, lux.getFloat())



def luxInt(name, lux, min, max, caption, hint, gui, width=1.0):
    if gui:
        r = gui.getRect(width, 1)
        Draw.Number(caption+": ", evtLuxGui, r[0], r[1], r[2], r[3], lux.getInt(), min, max, hint, lambda e,v: lux.set(v))
    return "\n   \"integer %s\" [%d]"%(name, lux.getInt())

def luxBool(name, lux, caption, hint, gui, width=1.0):
    if gui:
        r = gui.getRect(width, 1)
        Draw.Toggle(caption, evtLuxGui, r[0], r[1], r[2], r[3], lux.get()=="true", hint, lambda e,v: lux.set(["false","true"][bool(v)]))
    return "\n   \"bool %s\" [\"%s\"]"%(name, lux.get())

def luxString(name, lux, caption, hint, gui, width=1.0):
    if gui:
        r = gui.getRect(width, 1)
        Draw.String(caption+": ", evtLuxGui, r[0], r[1], r[2], r[3], lux.get(), 250, hint, lambda e,v: lux.set(v))
    if lux.get()==lux.default: return ""
    else: return "\n   \"string %s\" [\"%s\"]"%(name, luxstr(lux.get()))

def luxFile(name, lux, caption, hint, gui, width=1.0):
    if gui:
        r = gui.getRect(width, 1)
        Draw.String(caption+": ", evtLuxGui, r[0], r[1], r[2]-r[3]-2, r[3], lux.get(), 250, hint, lambda e,v: lux.set(v))
        Draw.Button("...", 0, r[0]+r[2]-r[3], r[1], r[3], r[3], "click to open file selector", lambda e,v:Window.FileSelector(lambda s:lux.set(s), "Select %s"%(caption), lux.get()))
    return "\n   \"string %s\" [\"%s\"]"%(name, luxstr(lux.get()))

def luxPath(name, lux, caption, hint, gui, width=1.0):
    if gui:
        r = gui.getRect(width, 1)
        Draw.String(caption+": ", evtLuxGui, r[0], r[1], r[2]-r[3]-2, r[3], lux.get(), 250, hint, lambda e,v: lux.set(Blender.sys.dirname(v)+os.sep))
        Draw.Button("...", 0, r[0]+r[2]-r[3], r[1], r[3], r[3], "click to open file selector", lambda e,v:Window.FileSelector(lambda s:lux.set(s), "Select %s"%(caption), lux.get()))
    return "\n   \"string %s\" [\"%s\"]"%(name, luxstr(lux.get()))

def luxRGB(name, lux, max, caption, hint, gui, width=2.0):
    if gui:
        r = gui.getRect(width, 1)
        scale = 1.0
        rgb = lux.getRGB()
        if max > 1.0:
            for i in range(3):
                if rgb[i] > scale: scale = rgb[i]
            rgb = (rgb[0]/scale, rgb[1]/scale, rgb[2]/scale)
        Draw.ColorPicker(evtLuxGui, r[0], r[1], r[3], r[3], rgb, "click to select color", lambda e,v: lux.setRGB((v[0]*scale,v[1]*scale,v[2]*scale)))
        w = int((r[2]-r[3])/3); m = max
        if max > 1.0:
            w = int((r[2]-r[3])/4); m = 1.0
        drawR, drawG, drawB, drawS = Draw.Create(rgb[0]), Draw.Create(rgb[1]), Draw.Create(rgb[2]), Draw.Create(scale)
        drawR = Draw.Number("R:", evtLuxGui, r[0]+r[3], r[1], w, r[3], drawR.val, 0.0, m, "red", lambda e,v: lux.setRGB((v*scale,drawG.val*scale,drawB.val*scale)))
        drawG = Draw.Number("G:", evtLuxGui, r[0]+r[3]+w, r[1], w, r[3], drawG.val, 0.0, m, "green", lambda e,v: lux.setRGB((drawR.val*scale,v*scale,drawB.val*scale)))
        drawB = Draw.Number("B:", evtLuxGui, r[0]+r[3]+2*w, r[1], w, r[3], drawB.val, 0.0, m, "blue", lambda e,v: lux.setRGB((drawR.val*scale,drawG.val*scale,v*scale)))
        if max > 1.0:
            Draw.Number("s:", evtLuxGui, r[0]+r[3]+3*w, r[1], w, r[3], drawS.val, 0.0, max, "color scale", lambda e,v: lux.setRGB((drawR.val*v,drawG.val*v,drawB.val*v)))
    if max <= 1.0:
        return "\n   \"color %s\" [%s]"%(name, lux.getRGC())
    return "\n   \"color %s\" [%s]"%(name, lux.get())

def luxVector(name, lux, min, max, caption, hint, gui, width=2.0):
    if gui:
        r = gui.getRect(width, 1)
        vec = lux.getVector()
        w = int(r[2]/3)
        drawX, drawY, drawZ = Draw.Create(vec[0]), Draw.Create(vec[1]), Draw.Create(vec[2])
        drawX = Draw.Number("x:", evtLuxGui, r[0], r[1], w, r[3], drawX.val, min, max, "", lambda e,v: lux.setVector((v,drawY.val,drawZ.val)))
        drawY = Draw.Number("y:", evtLuxGui, r[0]+w, r[1], w, r[3], drawY.val, min, max, "", lambda e,v: lux.setVector((drawX.val,v,drawZ.val)))
        drawZ = Draw.Number("z:", evtLuxGui, r[0]+2*w, r[1], w, r[3], drawZ.val, min, max, "", lambda e,v: lux.setVector((drawX.val,drawY.val,v)))
    return "\n   \"vector %s\" [%s]"%(name, lux.get())

def luxVectorUniform(name, lux, min, max, caption, hint, gui, width=2.0):
    def setUniform(lux, value):
        if value: lux.set(lux.getFloat())
        else: lux.setVector(lux.getVector())
    if gui:
        r = gui.getRect(width, 1)
        vec = lux.getVector()
        Draw.Toggle("U", evtLuxGui, r[0], r[1], gui.h, gui.h, lux.isFloat(), "uniform", lambda e,v: setUniform(lux, v))
        if lux.isFloat():
            Draw.Number("v:", evtLuxGui, r[0]+gui.h, r[1], r[2]-gui.h, r[3], lux.getFloat(), min, max, "", lambda e,v: lux.set(v))
        else:
            w = int((r[2]-gui.h)/3)
            drawX, drawY, drawZ = Draw.Create(vec[0]), Draw.Create(vec[1]), Draw.Create(vec[2])
            drawX = Draw.Number("x:", evtLuxGui, r[0]+gui.h, r[1], w, r[3], drawX.val, min, max, "", lambda e,v: lux.setVector((v,drawY.val,drawZ.val)))
            drawY = Draw.Number("y:", evtLuxGui, r[0]+w+gui.h, r[1], w, r[3], drawY.val, min, max, "", lambda e,v: lux.setVector((drawX.val,v,drawZ.val)))
            drawZ = Draw.Number("z:", evtLuxGui, r[0]+2*w+gui.h, r[1], w, r[3], drawZ.val, min, max, "", lambda e,v: lux.setVector((drawX.val,drawY.val,v)))
    return "\n   \"vector %s\" [%s]"%(name, lux.getVectorStr())


# lux individual identifiers
def luxCamera(cam, context, gui=None):
    global icon_c_camera
    str = ""
    if cam:
        camtype = luxProp(cam, "camera.type", "perspective")
        str = luxIdentifier("Camera", camtype, ["perspective","orthographic","environment","realistic"], "CAMERA", "select camera type", gui, icon_c_camera)
        scale = 1.0
        if camtype.get() == "perspective":
            if gui: gui.newline("  View:")
            str += luxFloat("fov", luxAttr(cam, "angle"), 8.0, 170.0, "fov", "camera field-of-view angle", gui)
            fl = luxAttr(cam, "lens")
            if gui:
                luxFloat("lens", fl, 1.0, 250.0, "focallength", "camera focal length", gui)
            
        if camtype.get() == "orthographic" :
            str += luxFloat("scale", luxAttr(cam, "scale"), 0.01, 1000.0, "scale", "orthographic camera scale", gui)
            scale = cam.scale / 2
        if camtype.get() == "realistic":
            
            if gui: gui.newline("  View:")
            fov = luxAttr(cam, "angle")
            str += luxFloat("fov", fov, 8.0, 170.0, "fov", "camera field-of-view angle", gui)
            if gui: luxFloat("lens", luxAttr(cam, "lens"), 1.0, 250.0, "focallength", "camera focal length", gui)
            
            
            if gui: gui.newline()
            str += luxFile("specfile", luxProp(cam, "camera.realistic.specfile", ""), "spec-file", "", gui, 1.0)
#            if gui: gui.newline()
# auto calc        str += luxFloat("filmdistance", luxProp(cam, "camera.realistic.filmdistance", 70.0), 0.1, 1000.0, "film-dist", "film-distance [mm]", gui)
            filmdiag = luxProp(cam, "camera.realistic.filmdiag", 35.0)
            str += luxFloat("filmdiag", filmdiag, 0.1, 1000.0, "film-diag", "[mm]", gui)
            if gui: gui.newline()
            fstop = luxProp(cam, "camera.realistic.fstop", 1.0)
            luxFloat("aperture_diameter", fstop, 0.1, 100.0, "f-stop", "", gui)
            dofdist = luxAttr(cam, "dofDist")
            luxFloat("focaldistance", dofdist, 0.0, 10000.0, "distance", "Distance from the camera at which objects will be in focus. Has no effect if Lens Radius is 0", gui)
            if gui:
                Draw.Button("S", evtLuxGui, gui.x, gui.y-gui.h, gui.h, gui.h, "focus selected object", lambda e,v:setFocus("S"))
                Draw.Button("C", evtLuxGui, gui.x+gui.h, gui.y-gui.h, gui.h, gui.h, "focus cursor", lambda e,v:setFocus("C"))
            focal = filmdiag.get()*0.001 / math.tan(fov.get() * math.pi / 360.0) / 2.0
            print "calculated focal length: %f mm"%(focal * 1000.0)
            aperture_diameter = focal / fstop.get()
            print "calculated aperture diameter: %f mm"%(aperture_diameter * 1000.0)
            str += "\n   \"float aperture_diameter\" [%f]"%(aperture_diameter*1000.0)
            filmdistance = dofdist.get() * focal / (dofdist.get() - focal)
            print "calculated film distance: %f mm"%(filmdistance * 1000.0)
            str += "\n   \"float filmdistance\" [%f]"%(filmdistance*1000.0)

        # Clipping
        useclip = luxProp(cam, "useclip", "false")
        luxBool("useclip", useclip, "Near & Far Clipping", "Enable Camera near and far clipping options", gui, 2.0)
        if(useclip.get() == "true"):
            if gui: gui.newline("  Clipping:")
            str += luxFloat("hither", luxAttr(cam, "clipStart"), 0.0, 100.0, "start", "near clip distance", gui)
            str += luxFloat("yon", luxAttr(cam, "clipEnd"), 1.0, 10000.0, "end", "far clip distance", gui)

        # Depth of Field
        usedof = luxProp(cam, "usedof", "false")
        
        if camtype.get() in ["perspective", "orthographic"]:
            luxBool("usedof", usedof, "Depth of Field & Bokeh", "Enable Depth of Field & Aperture options", gui, 2.0)
            
            
            if usedof.get() == "true":
                
                if gui: gui.newline("  DOF:")
                
                lr = luxProp(cam, "camera.lensradius", 0.01)
                fs = luxProp(cam, "camera.fstop", 2.8)
                
                if camtype.get() == "perspective":
                    
                    usefstop = luxProp(cam, "usefstop", "false")
                    luxBool("usefstop", usefstop, "Use f/stop", "Use f/stop to define DOF effect", gui, 1.0)
                    
                    LR_SCALE = 1000.0       # lr in metres -> mm
                    FL_SCALE = 1.0          # fl in mm -> mm
                    
                    def lr_2_fs(fl, lr):
                        lr += 0.00000001
                        return fl / ( 2.0 * lr )
                    
                    def fs_2_lr(fl, fs):
                        return fl / ( 2.0 * fs )
                    
                    if usefstop.get() == 'true':
                        lr.set(fs_2_lr(fl.get() * FL_SCALE, fs.get()) / LR_SCALE)
                        luxFloat("fstop", fs, 0.9, 64.0, "fstop", "Defines the lens aperture.", gui)
                        str += luxFloat("lensradius", lr, 0.0, 1.0, "", "", None)
                    else:
                        fs.set(lr_2_fs(fl.get() * FL_SCALE, lr.get() * LR_SCALE))
                        str += luxFloat("lensradius", lr, 0.0, 1.0, "lens-radius", "Defines the lens radius. Values higher than 0. enable DOF and control the amount", gui)
                else:
                    str += luxFloat("lensradius", lr, 0.0, 1.0, "lens-radius", "Defines the lens radius. Values higher than 0. enable DOF and control the amount", gui)
                
                focustype = luxProp(cam, "camera.focustype", "autofocus")
                luxOption("focustype", focustype, ["autofocus", "manual", "object"], "Focus Type", "Choose the focus behaviour", gui)
                
    
                if focustype.get() == "autofocus":
                    str += luxBool("autofocus",luxProp(cam, "camera.autofocus", "true"), "autofocus", "Enable automatic focus", gui)
                if focustype.get() == "object":
                    objectfocus = luxProp(cam, "camera.objectfocus", "")
                    luxString("objectfocus", objectfocus, "object", "Always focus camera on named object", gui, 1.0)
                    dofdist = luxAttr(cam, "dofDist")
                    str += luxFloat("focaldistance", dofdist, 0.0, 100.0, "distance", "Distance from the camera at which objects will be in focus. Has no effect if Lens Radius is 0", gui)
                    if objectfocus.get() != "":
                        setFocus(objectfocus.get())
                if focustype.get() == "manual":
                    dofdist = luxAttr(cam, "dofDist")
                    str += luxFloat("focaldistance", dofdist, 0.0, 100.0, "distance", "Distance from the camera at which objects will be in focus. Has no effect if Lens Radius is 0", gui)
                    if gui:
                        Draw.Button("S", evtLuxGui, gui.x, gui.y-gui.h, gui.h, gui.h, "focus selected object", lambda e,v:setFocus("S"))
                        Draw.Button("C", evtLuxGui, gui.x+gui.h, gui.y-gui.h, gui.h, gui.h, "focus cursor", lambda e,v:setFocus("C"))

        if camtype.get() == "perspective" and usedof.get() == "true":
            str += luxInt("blades", luxProp(cam, "camera.blades", 6), 0, 16, "aperture blades", "Number of blade edges of the aperture, values 0 to 2 defaults to a circle", gui)
            str += luxOption("distribution", luxProp(cam, "camera.distribution", "uniform"), ["uniform", "exponential", "inverse exponential", "gaussian", "inverse gaussian"], "distribution", "Choose the lens sampling distribution. Non-uniform distributions allow for ring effects.", gui)
            str += luxInt("power", luxProp(cam, "camera.power", 1), 0, 512, "power", "Exponent for the expression in exponential distribution. Higher value gives a more pronounced ring effect.", gui)

        useaspect = luxProp(cam, "useaspectratio", "false")
        aspectratio = luxProp(cam, "ratio", 1.3333)
        if camtype.get() in ["perspective", "orthographic"]:
            useshift = luxProp(cam, "camera.useshift", "false")
            luxBool("useshift", useshift, "Architectural (Lens Shift) & Aspect Ratio", "Enable Lens Shift and Aspect Ratio options", gui, 2.0)
            if(useshift.get() == "true"):
                if gui: gui.newline("  Shift:")
                luxFloat("X", luxAttr(cam, "shiftX"), -2.0, 2.0, "X", "horizontal lens shift", gui)
                luxFloat("Y", luxAttr(cam, "shiftY"), -2.0, 2.0, "Y", "vertical lens shift", gui)

                if gui: gui.newline("  AspectRatio:")
                luxBool("useaspectratio", useaspect, "Custom", "Define a custom frame aspect ratio", gui)
                if useaspect.get() == "true":
                    str += luxFloat("frameaspectratio", aspectratio, 0.0001, 3.0, "aspectratio", "Frame aspect ratio", gui)
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
#            useflash = luxProp(cam, "useflash", "false")
#            luxBool("useflash", useflash, "Flash Lamp", "Enable Camera mounted flash lamp options", gui, 2.0)

        # Motion Blur Options (common to all cameras)
        usemblur = luxProp(cam, "usemblur", "false")
        luxBool("usemblur", usemblur, "Motion Blur", "Enable Motion Blur", gui, 2.0)
        if(usemblur.get() == "true"):    
            if gui: gui.newline("  Shutter:")
            mblurpreset = luxProp(cam, "mblurpreset", "true")
            luxBool("mblurpreset", mblurpreset, "Preset", "Enable use of Shutter Presets", gui, 0.4)
            if(mblurpreset.get() == "true"):
                shutterpresets = ["full frame", "half frame", "quarter frame", "1/25", "1/30", "1/45", "1/60", "1/85", "1/125", "1/250", "1/500"]        
                shutterpreset = luxProp(cam, "camera.shutterspeedpreset", "full frame")
                luxOption("shutterpreset", shutterpreset, shutterpresets, "shutterspeed", "Choose the Shutter speed preset.", gui, 1.0)

                fpspresets = ["10 FPS", "12 FPS", "20 FPS", "25 FPS", "29.99 FPS", "30 FPS", "50 FPS", "60 FPS"]
                shutfps = luxProp(cam, "camera.shutfps", "25 FPS")
                luxOption("shutfps", shutfps, fpspresets, "@", "Choose the number of frames per second as the time base.", gui, 0.6)

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
                str += luxFloat("shutteropen", luxProp(cam, "camera.shutteropen", 0.0), 0.0, 100.0, "open", "time in seconds when shutter opens", gui, 0.8)
                str += luxFloat("shutterclose", luxProp(cam, "camera.shutterclose", 1.0), 0.0, 100.0, "close", "time in seconds when shutter closes", gui, 0.8)

            str += luxOption("shutterdistribution", luxProp(cam, "camera.shutterdistribution", "uniform"), ["uniform", "gaussian"], "distribution", "Choose the shutter sampling distribution.", gui, 2.0)
            objectmblur = luxProp(cam, "objectmblur", "true")
            luxBool("objectmblur", objectmblur, "Object", "Enable Motion Blur for scene object motions", gui, 1.0)
            cammblur = luxProp(cam, "cammblur", "true")
            luxBool("cammblur", cammblur, "Camera", "Enable Motion Blur for Camera motion", gui, 1.0)
    return str


def luxFilm(scn, gui=None):
    str = ""
    if scn:
        filmtype = luxProp(scn, "film.type", "fleximage")
        str = luxIdentifier("Film", filmtype, ["fleximage"], "FILM", "select film type", gui)
        if filmtype.get() == "fleximage":
            context = scn.getRenderingContext()
            if context:
                if gui: gui.newline("  Resolution:")
                luxInt("xresolution", luxAttr(context, "sizeX"), 0, 8192, "X", "width of the render", gui, 0.666)
                luxInt("yresolution", luxAttr(context, "sizeY"), 0, 8192, "Y", "height of the render", gui, 0.666)
                scale = luxProp(scn, "film.scale", "100 %")
                luxOption("", scale, ["100 %", "75 %", "50 %", "25 %"], "scale", "scale resolution", gui, 0.666)
                scale = int(scale.get()[:-1])
                # render region option
                if context.borderRender:
                    (x1,y1,x2,y2) = context.border
                    if (x1==x2) and (y1==y2): print "WARNING: empty render-region, use SHIFT-B to set render region in Blender."
                    str += "\n   \"integer xresolution\" [%d] \n   \"integer yresolution\" [%d]"%(luxAttr(context, "sizeX").get()*scale/100*(x2-x1), luxAttr(context, "sizeY").get()*scale/100*(y2-y1))
                else:
                    str += "\n   \"integer xresolution\" [%d] \n   \"integer yresolution\" [%d]"%(luxAttr(context, "sizeX").get()*scale/100, luxAttr(context, "sizeY").get()*scale/100)

            if gui: gui.newline("  Halt:")
            str += luxInt("haltspp", luxProp(scn, "haltspp", 0), 0, 32768, "haltspp", "Stop rendering after specified amount of samples per pixel / 0 = never halt", gui)
            palpha = luxProp(scn, "film.premultiplyalpha", "true")
            str += luxBool("premultiplyalpha", palpha, "premultiplyalpha", "Pre multiply film alpha channel during normalization", gui)
    
            if gui: gui.newline("  Tonemap:")
            tonemapkernel =    luxProp(scn, "film.tonemapkernel", "reinhard")
            str += luxOption("tonemapkernel", tonemapkernel, ["reinhard", "linear", "contrast", "maxwhite"], "Tonemapping Kernel", "Select the tonemapping kernel to use", gui, 2.0)
            if tonemapkernel.get() == "reinhard":
                autoywa = luxProp(scn, "film.reinhard.autoywa", "true")
                str += luxBool("reinhard_autoywa", autoywa, "auto Ywa", "Automatically determine World Adaption Luminance", gui)
                if autoywa.get() == "false":
                    str += luxFloat("reinhard_ywa", luxProp(scn, "film.reinhard.ywa", 0.1), 0.001, 1.0, "Ywa", "Display/World Adaption Luminance", gui)
                str += luxFloat("reinhard_prescale", luxProp(scn, "film.reinhard.prescale", 1.0), 0.0, 10.0, "preScale", "Image scale before tonemap operator", gui)
                str += luxFloat("reinhard_postscale", luxProp(scn, "film.reinhard.postscale", 1.2), 0.0, 10.0, "postScale", "Image scale after tonemap operator", gui)
                str += luxFloat("reinhard_burn", luxProp(scn, "film.reinhard.burn", 6.0), 0.1, 12.0, "burn", "12.0: no burn out, 0.1 lot of burn out", gui)
            elif tonemapkernel.get() == "linear":
                str += luxFloat("linear_sensitivity", luxProp(scn, "film.linear.sensitivity", 50.0), 0.0, 100.0, "sensitivity", "Adaption/Sensitivity", gui)
                str += luxFloat("linear_exposure", luxProp(scn, "film.linear.exposure", 1.0), 0.001, 1.0, "exposure", "Exposure duration in seconds", gui)
                str += luxFloat("linear_fstop", luxProp(scn, "film.linear.fstop", 2.8), 0.1, 64.0, "Fstop", "F-Stop", gui)
                str += luxFloat("linear_gamma", luxProp(scn, "film.linear.gamma", 1.0), 0.0, 8.0, "gamma", "Tonemap operator gamma correction", gui)
            elif tonemapkernel.get() == "contrast":
                str += luxFloat("contrast_ywa", luxProp(scn, "film.contrast.ywa", 0.1), 0.001, 1.0, "Ywa", "Display/World Adaption Luminance", gui)

            if gui: gui.newline("  Display:")
            str += luxInt("displayinterval", luxProp(scn, "film.displayinterval", 12), 4, 3600, "interval", "Set display Interval (seconds)", gui)
            
            if gui: gui.newline("  Write:")
            str += luxInt("writeinterval", luxProp(scn, "film.writeinterval", 120), 12, 3600, "interval", "Set display Interval (seconds)", gui)

            # override output image dir in case of command line batch mode 
            overrideop = luxProp(scn, "overrideoutputpath", "")
            if overrideop.get() != "":
                filebase = os.path.splitext(os.path.basename(Blender.Get('filename')))[0]
                filename = overrideop.get() + "/" + filebase + "-%05d" %  (Blender.Get('curframe'))
                str += "\n   \"string filename\" [\"%s\"]"%(filename)
            else:
                fn = luxProp(scn, "filename", "default-%05d" %  (Blender.Get('curframe')))
                str += luxString("filename", fn, "File name", "save file name", None)

            if gui: gui.newline("  Formats:")
            savetga = luxProp(scn, "film.write_tonemapped_tga", "true")
            str += luxBool("write_tonemapped_tga", savetga, "Tonemapped TGA", "save tonemapped TGA file", gui)
            if gui: gui.newline("")
            savetmexr = luxProp(scn, "film.write_tonemapped_exr", "false")
            saveexr = luxProp(scn, "film.write_untonemapped_exr", "false")
            str += luxBool("write_tonemapped_exr", savetmexr, "Tonemapped EXR", "save tonemapped EXR file", gui)
            str += luxBool("write_untonemapped_exr", saveexr, "Untonemapped EXR", "save untonemapped EXR file", gui)
            if gui: gui.newline("")
            savetmigi = luxProp(scn, "film.write_tonemapped_igi", "false")
            saveigi = luxProp(scn, "film.write_untonemapped_igi", "false")
            str += luxBool("write_tonemapped_igi", savetmigi, "Tonemapped IGI", "save tonemapped IGI file", gui)
            str += luxBool("write_untonemapped_igi", saveigi, "Untonemapped IGI", "save untonemapped IGI file", gui)
            if gui: gui.newline("  Resume:")
            resumeflm = luxProp(scn, "film.write_resume_flm", "false")
            str += luxBool("write_resume_flm", resumeflm, "Write/Use FLM", "Write a resume fleximage .flm file, or resume rendering if it already exists", gui)
            restartflm = luxProp(scn, "film.restart_resume_flm", "false")
            str += luxBool("restart_resume_flm", restartflm, "Restart/Erase", "Restart with a black flm, even it a previous flm exists", gui)
            if gui: gui.newline("  Reject:")
            str += luxInt("reject_warmup", luxProp(scn, "film.reject_warmup", 128), 0, 32768, "warmup_spp", "Specify amount of samples per pixel for high intensity rejection", gui)
            debugmode = luxProp(scn, "film.debug", "false")
            str += luxBool("debug", debugmode, "debug", "Turn on debug reporting and switch off reject", gui)

            # Colorspace
            if gui: gui.newline("  Colorspace:")

            cspaceusepreset = luxProp(scn, "film.colorspaceusepreset", "true")
            luxBool("colorspaceusepreset", cspaceusepreset, "Preset", "Select from a list of predefined presets", gui, 0.4)

            # Default values for 'sRGB - HDTV (ITU-R BT.709-5)'
            cspacewhiteX = luxProp(scn, "film.cspacewhiteX", 0.314275)
            cspacewhiteY = luxProp(scn, "film.cspacewhiteY", 0.329411)
            cspaceredX = luxProp(scn, "film.cspaceredX", 0.63)
            cspaceredY = luxProp(scn, "film.cspaceredY", 0.34)
            cspacegreenX = luxProp(scn, "film.cspacegreenX", 0.31)
            cspacegreenY = luxProp(scn, "film.cspacegreenY", 0.595)
            cspaceblueX = luxProp(scn, "film.cspaceblueX", 0.155)
            cspaceblueY = luxProp(scn, "film.cspaceblueY", 0.07)
            gamma = luxProp(scn, "film.gamma", 2.2)

            if(cspaceusepreset.get() == "true"):
                # preset controls
                cspace = luxProp(scn, "film.colorspace", "sRGB - HDTV (ITU-R BT.709-5)")
                cspaces = ["sRGB - HDTV (ITU-R BT.709-5)", "ROMM RGB", "Adobe RGB 98", "Apple RGB", "NTSC (FCC 1953, ITU-R BT.470-2 System M)", "NTSC (1979) (SMPTE C, SMPTE-RP 145)", "PAL/SECAM (EBU 3213, ITU-R BT.470-6)", "CIE (1931) E"]
                luxOption("colorspace", cspace, cspaces, "Colorspace", "select output working colorspace", gui, 1.6)

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

                whitepointusecspace = luxProp(scn, "film.whitepointusecolorspace", "true")
                luxBool("whitepointusecolorspace", whitepointusecspace, "Colorspace Whitepoint", "Use default whitepoint for selected colorspace", gui, 1.0)
                gammausecspace = luxProp(scn, "film.gammausecolorspace", "true")
                luxBool("gammausecolorspace", gammausecspace, "Colorspace Gamma", "Use default output gamma for selected colorspace", gui, 1.0)

                if(whitepointusecspace.get() == "false"):
                    if gui: gui.newline("  Whitepoint:")
                    whitepointusepreset = luxProp(scn, "film.whitepointusepreset", "true")
                    luxBool("whitepointusepreset", whitepointusepreset, "Preset", "Select from a list of predefined presets", gui, 0.4)

                    if(whitepointusepreset.get() == "true"):
                        whitepointpresets = ["E", "D50", "D55", "D65", "D75", "A", "B", "C", "9300", "F2", "F7", "F11"]
                        whitepointpreset = luxProp(scn, "film.whitepointpreset", "D65")
                        luxOption("whitepointpreset", whitepointpreset, whitepointpresets, "  PRESET", "select Whitepoint preset", gui, 1.6)

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
                        luxFloat("white X", cspacewhiteX, 0.0, 1.0, "white X", "Whitepoint X weight", gui, 0.8)
                        luxFloat("white Y", cspacewhiteY, 0.0, 1.0, "white Y", "Whitepoint Y weight", gui, 0.8)

                if(gammausecspace.get() == "false"):
                    if gui: gui.newline("  Gamma:")
                    luxFloat("gamma", gamma, 0.1, 6.0, "gamma", "Output and RGC Gamma", gui, 2.0)
            else:
                # manual controls
                luxFloat("white X", cspacewhiteX, 0.0, 1.0, "white X", "Whitepoint X weight", gui, 0.8)
                luxFloat("white Y", cspacewhiteY, 0.0, 1.0, "white Y", "Whitepoint Y weight", gui, 0.8)
                luxFloat("red X", cspaceredX, 0.0, 1.0, "red X", "Red component X weight", gui, 1.0)
                luxFloat("red Y", cspaceredY, 0.0, 1.0, "red Y", "Red component Y weight", gui, 1.0)
                luxFloat("green X", cspacegreenX, 0.0, 1.0, "green X", "Green component X weight", gui, 1.0)
                luxFloat("green Y", cspacegreenY, 0.0, 1.0, "green Y", "Green component Y weight", gui, 1.0)
                luxFloat("blue X", cspaceblueX, 0.0, 1.0, "blue X", "Blue component X weight", gui, 1.0)
                luxFloat("blue Y", cspaceblueY, 0.0, 1.0, "blue Y", "Blue component Y weight", gui, 1.0)
                if gui: gui.newline("  Gamma:")
                luxFloat("gamma", gamma, 0.1, 6.0, "gamma", "Output and RGC Gamma", gui, 2.0)

            str += "\n   \"float colorspace_white\" [%f %f]"%(cspacewhiteX.get(), cspacewhiteY.get())
            str += "\n   \"float colorspace_red\" [%f %f]"%(cspaceredX.get(), cspaceredY.get())
            str += "\n   \"float colorspace_green\" [%f %f]"%(cspacegreenX.get(), cspacegreenY.get())
            str += "\n   \"float colorspace_blue\" [%f %f]"%(cspaceblueX.get(), cspaceblueY.get())
            str += "\n   \"float gamma\" [%f]"%(gamma.get())

    return str


def luxPixelFilter(scn, gui=None):
    global icon_c_filter
    str = ""
    if scn:
        filtertype = luxProp(scn, "pixelfilter.type", "mitchell")
        str = luxIdentifier("PixelFilter", filtertype, ["box", "gaussian", "mitchell", "sinc", "triangle"], "FILTER", "select pixel filter type", gui, icon_c_filter)

        # Advanced toggle
        parammodeadvanced = luxProp(scn, "parammodeadvanced", "false")
        showadvanced = luxProp(scn, "pixelfilter.showadvanced", parammodeadvanced.get())
        luxBool("advanced", showadvanced, "Advanced", "Show advanced options", gui, 0.6)
        # Help toggle
        showhelp = luxProp(scn, "pixelfilter.showhelp", "false")
        luxHelp("help", showhelp, "Help", "Show Help Information", gui, 0.4)

        if filtertype.get() == "box":
            if showadvanced.get()=="true":
                # Advanced parameters
                if gui: gui.newline()
                str += luxFloat("xwidth", luxProp(scn, "pixelfilter.box.xwidth", 0.5), 0.0, 10.0, "x-width", "Width of the filter in the x direction", gui)
                str += luxFloat("ywidth", luxProp(scn, "pixelfilter.box.ywidth", 0.5), 0.0, 10.0, "y-width", "Width of the filter in the y direction", gui)
        if filtertype.get() == "gaussian":
            if showadvanced.get()=="true":
                # Advanced parameters
                if gui: gui.newline()
                str += luxFloat("xwidth", luxProp(scn, "pixelfilter.gaussian.xwidth", 2.0), 0.0, 10.0, "x-width", "Width of the filter in the x direction", gui)
                str += luxFloat("ywidth", luxProp(scn, "pixelfilter.gaussian.ywidth", 2.0), 0.0, 10.0, "y-width", "Width of the filter in the y direction", gui)
                if gui: gui.newline()
                str += luxFloat("alpha", luxProp(scn, "pixelfilter.gaussian.alpha", 2.0), 0.0, 10.0, "alpha", "Gaussian rate of falloff. Lower values give blurrier images", gui)
        if filtertype.get() == "mitchell":
            if showadvanced.get()=="false":
                # Default parameters
                if gui: gui.newline("", 8, 0, None, [0.4,0.4,0.4])
                slidval = luxProp(scn, "pixelfilter.mitchell.sharp", 0.33)
                luxFloat("sharpness", slidval, 0.0, 1.0, "sharpness", "Specify amount between blurred (left) and sharp/ringed (right)", gui, 2.0, 1)
                # rule: B + 2*c = 1.0
                C = slidval.getFloat() * 0.5
                B = 1.0 - slidval.getFloat()
                str += "\n   \"float B\" [%f]"%(B)
                str += "\n   \"float C\" [%f]"%(C)

            if showadvanced.get()=="true":
                # Advanced parameters
                if gui: gui.newline()
                str += luxFloat("xwidth", luxProp(scn, "pixelfilter.mitchell.xwidth", 2.0), 0.0, 10.0, "x-width", "Width of the filter in the x direction", gui)
                str += luxFloat("ywidth", luxProp(scn, "pixelfilter.mitchell.ywidth", 2.0), 0.0, 10.0, "y-width", "Width of the filter in the y direction", gui)
                if gui: gui.newline()
    
                optmode = luxProp(scn, "pixelfilter.mitchell.optmode", "slider")
                luxOption("optmode", optmode, ["slider", "preset", "manual"], "Mode", "Mode of configuration", gui, 0.5)
    
                if(optmode.get() == "slider"):
                    slidval = luxProp(scn, "pixelfilter.mitchell.sharp", 0.33)
                    luxFloat("sharpness", slidval, 0.0, 1.0, "sharpness", "Specify amount between blurred (left) and sharp/ringed (right)", gui, 1.5, 1)
                    # rule: B + 2*c = 1.0
                    C = slidval.getFloat() * 0.5
                    B = 1.0 - slidval.getFloat()
                    str += "\n   \"float B\" [%f]"%(B)
                    str += "\n   \"float C\" [%f]"%(C)
                elif(optmode.get() == "preset"):
                    print "not implemented"
                else:
                    str += luxFloat("B", luxProp(scn, "pixelfilter.mitchell.B", 0.3333), 0.0, 1.0, "B", "Specify the shape of the Mitchell filter. Often best result is when B + 2C = 1", gui, 0.75)
                    str += luxFloat("C", luxProp(scn, "pixelfilter.mitchell.C", 0.3333), 0.0, 1.0, "C", "Specify the shape of the Mitchell filter. Often best result is when B + 2C = 1", gui, 0.75)

        if filtertype.get() == "sinc":
            if showadvanced.get()=="true":
                # Advanced parameters
                if gui: gui.newline()
                str += luxFloat("xwidth", luxProp(scn, "pixelfilter.sinc.xwidth", 4.0), 0.0, 10.0, "x-width", "Width of the filter in the x direction", gui)
                str += luxFloat("ywidth", luxProp(scn, "pixelfilter.sinc.ywidth", 4.0), 0.0, 10.0, "y-width", "Width of the filter in the y direction", gui)
                if gui: gui.newline()
                str += luxFloat("tau", luxProp(scn, "pixelfilter.sinc.tau", 3.0), 0.0, 10.0, "tau", "Permitted number of cycles of the sinc function before it is clamped to zero", gui)
        if filtertype.get() == "triangle":
            if showadvanced.get()=="true":
                # Advanced parameters
                if gui: gui.newline()
                str += luxFloat("xwidth", luxProp(scn, "pixelfilter.triangle.xwidth", 2.0), 0.0, 10.0, "x-width", "Width of the filter in the x direction", gui)
                str += luxFloat("ywidth", luxProp(scn, "pixelfilter.triangle.ywidth", 2.0), 0.0, 10.0, "y-width", "Width of the filter in the y direction", gui)
    return str            

def luxSampler(scn, gui=None):
    global icon_c_sampler, icon_help
    str = ""
    if scn:
        samplertype = luxProp(scn, "sampler.type", "metropolis")
        str = luxIdentifier("Sampler", samplertype, ["metropolis", "erpt", "lowdiscrepancy", "random"], "SAMPLER", "select sampler type", gui, icon_c_sampler)

        # Advanced toggle
        parammodeadvanced = luxProp(scn, "parammodeadvanced", "false")
        showadvanced = luxProp(scn, "sampler.showadvanced", parammodeadvanced.get())
        luxBool("advanced", showadvanced, "Advanced", "Show advanced options", gui, 0.6)
        # Help toggle
        showhelp = luxProp(scn, "sampler.showhelp", "false")
        luxHelp("help", showhelp, "Help", "Show Help Information", gui, 0.4)

        if samplertype.get() == "metropolis":
            if showadvanced.get()=="false":
                # Default parameters
                if gui: gui.newline("  Mutation:", 8, 0, None, [0.4,0.4,0.4])
                strength = luxProp(scn, "sampler.metro.strength", 0.6)
                luxFloat("strength", strength, 0.0, 1.0, "strength", "Mutation Strength (lmprob = 1.0-strength)", gui, 2.0, 1)
                v = 1.0 - strength.get()
                str += "\n   \"float largemutationprob\" [%f]"%v
            if showadvanced.get()=="true":
                # Advanced parameters
                if gui: gui.newline("  Mutation:")
                str += luxFloat("largemutationprob", luxProp(scn, "sampler.metro.lmprob", 0.4), 0.0, 1.0, "LM.prob.", "Probability of generating a large sample (mutation)", gui)
                str += luxInt("maxconsecrejects", luxProp(scn, "sampler.metro.maxrejects", 512), 0, 32768, "max.rejects", "number of consecutive rejects before a new mutation is forced", gui)
                if gui: gui.newline("  Screen:")
                str += luxInt("initsamples", luxProp(scn, "sampler.metro.initsamples", 262144), 1, 1000000, "initsamples", "", gui)
                str += luxInt("stratawidth", luxProp(scn, "sampler.metro.stratawidth", 256), 1, 32768, "stratawidth", "The number of x/y strata for stratified sampling of seeds", gui)
                str += luxBool("usevariance",luxProp(scn, "sampler.metro.usevariance", "false"), "usevariance", "Accept based on variance", gui, 1.0)

            if showhelp.get()=="true":
                if gui: gui.newline("  Description:", 8, 0, icon_help, [0.4,0.5,0.56])
                r = gui.getRect(2,1); BGL.glRasterPos2i(r[0],r[1]+5) 
                Draw.Text("A Metropolis-Hastings mutating sampler which implements MLT", 'small')    

        if samplertype.get() == "erpt":
            str += luxInt("initsamples", luxProp(scn, "sampler.erpt.initsamples", 100000), 1, 1000000, "initsamples", "", gui)
            if gui: gui.newline("  Mutation:")
            str += luxInt("chainlength", luxProp(scn, "sampler.erpt.chainlength", 512), 1, 32768, "chainlength", "The number of mutations from a given seed", gui)
            if gui: gui.newline()
            str += luxInt("stratawidth", luxProp(scn, "sampler.erpt.stratawidth", 256), 1, 32768, "stratawidth", "The number of x/y strata for stratified sampling of seeds", gui)

        if samplertype.get() == "lowdiscrepancy":
            if gui: gui.newline("  PixelSampler:")
            str += luxOption("pixelsampler", luxProp(scn, "sampler.lowdisc.pixelsampler", "lowdiscrepancy"), ["linear", "tile", "random", "vegas","lowdiscrepancy","hilbert"], "pixel-sampler", "select pixel-sampler", gui)
            str += luxInt("pixelsamples", luxProp(scn, "sampler.lowdisc.pixelsamples", 4), 1, 2048, "samples", "Average number of samples taken per pixel. More samples create a higher quality image at the cost of render time", gui)

        if samplertype.get() == "random":
            if gui: gui.newline("  PixelSampler:")
            str += luxOption("pixelsampler", luxProp(scn, "sampler.random.pixelsampler", "vegas"), ["linear", "tile", "random", "vegas","lowdiscrepancy","hilbert"], "pixel-sampler", "select pixel-sampler", gui)
            if gui: gui.newline()
            str += luxInt("xsamples", luxProp(scn, "sampler.random.xsamples", 2), 1, 512, "xsamples", "Allows you to specify how many samples per pixel are taking in the x direction", gui)
            str += luxInt("ysamples", luxProp(scn, "sampler.random.ysamples", 2), 1, 512, "ysamples", "Allows you to specify how many samples per pixel are taking in the y direction", gui)
    return str            

def luxSurfaceIntegrator(scn, gui=None):
    global icon_c_integrator
    str = ""
    if scn:
        integratortype = luxProp(scn, "sintegrator.type", "bidirectional")
        str = luxIdentifier("SurfaceIntegrator", integratortype, ["directlighting", "path", "bidirectional", "exphotonmap", "distributedpath" ], "INTEGRATOR", "select surface integrator type", gui, icon_c_integrator)

        # Advanced toggle
        parammodeadvanced = luxProp(scn, "parammodeadvanced", "false")
        showadvanced = luxProp(scn, "sintegrator.showadvanced", parammodeadvanced.get())
        luxBool("advanced", showadvanced, "Advanced", "Show advanced options", gui, 0.6)
        # Help toggle
        showhelp = luxProp(scn, "sintegrator.showhelp", "false")
        luxHelp("help", showhelp, "Help", "Show Help Information", gui, 0.4)

        if integratortype.get() == "directlighting":
            if showadvanced.get()=="false":
                # Default parameters
                if gui: gui.newline("  Depth:", 8, 0, None, [0.4,0.4,0.4])
                str += luxInt("maxdepth", luxProp(scn, "sintegrator.dlighting.maxdepth", 8), 0, 2048, "bounces", "The maximum recursion depth for ray casting", gui, 2.0)

            if showadvanced.get()=="true":
                # Advanced parameters
                str += luxOption("strategy", luxProp(scn, "sintegrator.dlighting.strategy", "auto"), ["one", "all", "auto"], "strategy", "select directlighting strategy", gui)
                if gui: gui.newline("  Depth:")
                str += luxInt("maxdepth", luxProp(scn, "sintegrator.dlighting.maxdepth", 8), 0, 2048, "max-depth", "The maximum recursion depth for ray casting", gui)
                if gui: gui.newline()

        if integratortype.get() == "path":
            if showadvanced.get()=="false":
                # Default parameters
                if gui: gui.newline("  Depth:", 8, 0, None, [0.4,0.4,0.4])
                str += luxInt("maxdepth", luxProp(scn, "sintegrator.path.maxdepth", 10), 0, 2048, "bounces", "The maximum recursion depth for ray casting", gui, 2.0)

            if showadvanced.get()=="true":
                # Advanced parameters
                if gui: gui.newline("  Depth:")
                str += luxInt("maxdepth", luxProp(scn, "sintegrator.path.maxdepth", 10), 0, 2048, "maxdepth", "The maximum recursion depth for ray casting", gui)
                str += luxOption("strategy", luxProp(scn, "sintegrator.path.strategy", "auto"), ["one", "all", "auto"], "strategy", "select directlighting strategy", gui)
                if gui: gui.newline("  RR:")
                rrstrat = luxProp(scn, "sintegrator.path.rrstrategy", "efficiency")
                str += luxOption("rrstrategy", rrstrat, ["efficiency", "probability", "none"], "RR strategy", "select Russian Roulette path termination strategy", gui)
                if rrstrat.get() == "probability":
                    str += luxFloat("rrcontinueprob", luxProp(scn, "sintegrator.path.rrcontinueprob", 0.65), 0.0, 1.0, "rrprob", "Russian roulette continue probability", gui)

        if integratortype.get() == "bidirectional":
            if showadvanced.get()=="false":
                # Default parameters
                if gui: gui.newline("  Depth:", 8, 0, None, [0.4,0.4,0.4])
                bounces = luxProp(scn, "sintegrator.bidir.bounces", 10)
                luxInt("bounces", bounces, 5, 32, "bounces", "The maximum recursion depth for ray casting (in both directions)", gui, 2.0)
                str += "\n   \"integer eyedepth\" [%i]\n"%bounces.get()
                str += "   \"integer lightdepth\" [%i]"%bounces.get()

            if showadvanced.get()=="true":
                # Advanced parameters
                if gui: gui.newline("  Depth:")
                str += luxInt("eyedepth", luxProp(scn, "sintegrator.bidir.eyedepth", 10), 0, 2048, "eyedepth", "The maximum recursion depth for ray casting", gui)
                str += luxInt("lightdepth", luxProp(scn, "sintegrator.bidir.lightdepth", 10), 0, 2048, "lightdepth", "The maximum recursion depth for light ray casting", gui)
                str += luxOption("strategy", luxProp(scn, "sintegrator.bidir.strategy", "auto"), ["one", "all", "auto"], "strategy", "select directlighting strategy", gui)

        if integratortype.get() == "exphotonmap":
            if gui: gui.newline("  Photons:")
            str += luxInt("indirectphotons", luxProp(scn, "sintegrator.photonmap.idphotons", 200000), 0, 10000000, "indirect", "The number of photons to shoot for indirect lighting during preprocessing of the photon map", gui)
            str += luxInt("maxdirectphotons", luxProp(scn, "sintegrator.photonmap.maxdphotons", 1000000), 0, 10000000, "maxdirect", "The maximum number of photons to shoot for direct lighting during preprocessing of the photon map", gui)
            str += luxInt("causticphotons", luxProp(scn, "sintegrator.photonmap.cphotons", 20000), 0, 10000000, "caustic", "The number of photons to shoot for caustics during preprocessing of the photon map", gui)
            if gui: gui.newline("  Render:")
            str += luxOption("strategy", luxProp(scn, "sintegrator.photonmap.strategy", "auto"), ["one", "all", "auto"], "strategy", "select directlighting strategy", gui)
            str += luxInt("maxdepth", luxProp(scn, "sintegrator.photonmap.maxdepth", 6), 1, 1024, "maxdepth", "The maximum recursion depth of specular reflection and refraction", gui)
            str += luxFloat("maxdist", luxProp(scn, "sintegrator.photonmap.maxdist", 0.1), 0.0, 10.0, "maxdist", "The maximum distance between a point being shaded and a photon that can contribute to that point", gui)
            str += luxInt("nused", luxProp(scn, "sintegrator.photonmap.nused", 50), 0, 1000000, "nused", "The number of photons to use in density estimation", gui)
            str += luxOption("renderingmode", luxProp(scn, "sintegrator.photonmap.renderingmode", "directlighting"), ["directlighting", "path"], "renderingmode", "select rendering mode", gui)

            if gui: gui.newline("  FinalGather:")
            fg = luxProp(scn, "sintegrator.photonmap.fgather", "true")
            str += luxBool("finalgather", fg, "finalgather", "Enable use of final gather during rendering", gui)
            if fg.get() == "true":
                str += luxInt("finalgathersamples", luxProp(scn, "sintegrator.photonmap.fgathers", 32), 1, 1024, "samples", "The number of finalgather samples to take per pixel during rendering", gui)
                rrstrat = luxProp(scn, "sintegrator.photonmap.gatherrrstrategy", "efficiency")
                str += luxOption("gatherrrstrategy", rrstrat, ["efficiency", "probability", "none"], "RR strategy", "select Russian Roulette gather termination strategy", gui)
                str += luxFloat("gatherangle", luxProp(scn, "sintegrator.photonmap.gangle", 10.0), 0.0, 360.0, "gatherangle", "Angle for final gather", gui)
                str += luxFloat("gatherrrcontinueprob", luxProp(scn, "sintegrator.photonmap.gatherrrcontinueprob", 0.65), 0.0, 1.0, "rrcontinueprob", "Probability for russian roulette particle tracing termination", gui)

        if integratortype.get() == "distributedpath":
            str += luxOption("strategy", luxProp(scn, "sintegrator.distributedpath.strategy", "auto"), ["one", "all", "auto"], "strategy", "select directlighting strategy", gui)
            if gui: gui.newline("  Direct:")
            str += luxBool("directsampleall",luxProp(scn, "sintegrator.distributedpath.directsampleall", "true"), "Direct ALL", "Include diffuse direct light sample at first vertex", gui, 0.75)
            str += luxInt("directsamples", luxProp(scn, "sintegrator.distributedpath.directsamples", 1), 0, 1024, "s", "The number of direct light samples to take at the eye vertex", gui, 0.25)
            str += luxBool("indirectsampleall",luxProp(scn, "sintegrator.distributedpath.indirectsampleall", "false"), "Indirect ALL", "Include diffuse direct light sample at first vertex", gui, 0.75)
            str += luxInt("indirectsamples", luxProp(scn, "sintegrator.distributedpath.indirectsamples", 1), 0, 1024, "s", "The number of direct light samples to take at the remaining vertices", gui, 0.25)
            if gui: gui.newline("  Diffuse:")
            str += luxInt("diffusereflectdepth", luxProp(scn, "sintegrator.distributedpath.diffusereflectdepth", 3), 0, 2048, "Reflect", "The maximum recursion depth for diffuse reflection ray casting", gui, 0.5)
            str += luxInt("diffusereflectsamples", luxProp(scn, "sintegrator.distributedpath.diffusereflectsamples", 1), 0, 1024, "s", "The number of diffuse reflection samples to take at the eye vertex", gui, 0.25)
            str += luxInt("diffuserefractdepth", luxProp(scn, "sintegrator.distributedpath.diffuserefractdepth", 5), 0, 2048, "Refract", "The maximum recursion depth for diffuse refraction ray casting", gui, 0.5)
            str += luxInt("diffuserefractsamples", luxProp(scn, "sintegrator.distributedpath.diffuserefractsamples", 1), 0, 1024, "s", "The number of diffuse refraction samples to take at the eye vertex", gui, 0.25)
            str += luxBool("directdiffuse",luxProp(scn, "sintegrator.distributedpath.directdiffuse", "true"), "DL", "Include diffuse direct light sample at first vertex", gui, 0.25)
            str += luxBool("indirectdiffuse",luxProp(scn, "sintegrator.distributedpath.indirectdiffuse", "true"), "IDL", "Include diffuse indirect light sample at first vertex", gui, 0.25)
            if gui: gui.newline("  Glossy:")
            str += luxInt("glossyreflectdepth", luxProp(scn, "sintegrator.distributedpath.glossyreflectdepth", 2), 0, 2048, "Reflect", "The maximum recursion depth for glossy reflection ray casting", gui, 0.5)
            str += luxInt("glossyreflectsamples", luxProp(scn, "sintegrator.distributedpath.glossyreflectsamples", 1), 0, 1024, "s", "The number of glossy reflection samples to take at the eye vertex", gui, 0.25)
            str += luxInt("glossyrefractdepth", luxProp(scn, "sintegrator.distributedpath.glossyrefractdepth", 5), 0, 2048, "Refract", "The maximum recursion depth for glossy refraction ray casting", gui, 0.5)
            str += luxInt("glossyrefractsamples", luxProp(scn, "sintegrator.distributedpath.glossyrefractsamples", 1), 0, 1024, "s", "The number of glossy refraction samples to take at the eye vertex", gui, 0.25)
            str += luxBool("directglossy",luxProp(scn, "sintegrator.distributedpath.directglossy", "true"), "DL", "Include glossy direct light sample at first vertex", gui, 0.25)
            str += luxBool("indirectglossy",luxProp(scn, "sintegrator.distributedpath.indirectglossy", "true"), "IDL", "Include glossy indirect light sample at first vertex", gui, 0.25)
            if gui: gui.newline("  Specular:")
            str += luxInt("specularreflectdepth", luxProp(scn, "sintegrator.distributedpath.specularreflectdepth", 3), 0, 2048, "Reflect", "The maximum recursion depth for specular reflection ray casting", gui, 1.0)
            str += luxInt("specularrefractdepth", luxProp(scn, "sintegrator.distributedpath.specularrefractdepth", 5), 0, 2048, "Refract", "The maximum recursion depth for specular refraction ray casting", gui, 1.0)
            if gui: gui.newline("  Caustics:")
            str += luxBool("causticsondiffuse",luxProp(scn, "sintegrator.distributedpath.causticsondiffuse", "false"), "Caustics on Diffuse", "Enable caustics on diffuse surfaces (warning: might generate bright pixels)", gui, 1.0)
            str += luxBool("causticsonglossy",luxProp(scn, "sintegrator.distributedpath.causticsonglossy", "true"), "Caustics on Glossy", "Enable caustics on glossy surfaces (warning: might generate bright pixels)", gui, 1.0)

    return str

def luxVolumeIntegrator(scn, gui=None):
    global icon_c_volumeintegrator
    str = ""
    if scn:
        integratortype = luxProp(scn, "vintegrator.type", "single")
        str = luxIdentifier("VolumeIntegrator", integratortype, ["emission", "single"], "VOLUME INT", "select volume integrator type", gui, icon_c_volumeintegrator)
        if integratortype.get() == "emission":
            str += luxFloat("stepsize", luxProp(scn, "vintegrator.emission.stepsize", 1.0), 0.0, 100.0, "stepsize", "Stepsize for volumes", gui)
        if integratortype.get() == "single":
            str += luxFloat("stepsize", luxProp(scn, "vintegrator.emission.stepsize", 1.0), 0.0, 100.0, "stepsize", "Stepsize for volumes", gui)
    return str

def luxEnvironment(scn, gui=None):
    global icon_c_environment
    str = ""
    if scn:
        envtype = luxProp(scn, "env.type", "infinite")
        lsstr = luxIdentifier("LightSource", envtype, ["none", "infinite", "sunsky"], "ENVIRONMENT", "select environment light type", gui, icon_c_environment)
        if gui: gui.newline()
        str = ""
        
        if envtype.get() != "none":
            
            if envtype.get() in ["infinite", "sunsky"]:
                env_lg = luxProp(scn, "env.lightgroup", "default")
                luxString("env.lightgroup", env_lg, "lightgroup", "Environment light group", gui)
                lsstr = '\nLightGroup "' + env_lg.get() + '"' + lsstr
                rot = luxProp(scn, "env.rotation", 0.0)
                luxFloat("rotation", rot, 0.0, 360.0, "rotation", "environment rotation", gui)
                if rot.get() != 0:
                    str += "\tRotate %d 0 0 1\n"%(rot.get())
            str += "\t"+lsstr

            infinitehassun = 0
            if envtype.get() == "infinite":
                mapping = luxProp(scn, "env.infinite.mapping", "latlong")
                mappings = ["latlong","angular","vcross"]
                mapstr = luxOption("mapping", mapping, mappings, "mapping", "Select mapping type", gui, 0.5)
                map = luxProp(scn, "env.infinite.mapname", "")
                mapstr += luxFile("mapname", map, "map-file", "filename of the environment map", gui, 1.5)
                mapstr += luxFloat("gamma", luxProp(scn, "env.infinite.gamma", 1.0), 0.0, 6.0, "gamma", "", gui, 1.0)
                
                if map.get() != "":
                    str += mapstr
                else:
                    try:
                        worldcolor = Blender.World.Get('World').getHor()
                        str += "\n   \"color L\" [%g %g %g]" %(worldcolor[0], worldcolor[1], worldcolor[2])
                    except: pass

                str += luxFloat("gain", luxProp(scn, "env.infinite.gain", 1.0), 0.0, 1000.0, "gain", "", gui, 1.0)

                infinitesun = luxProp(scn, "env.infinite.hassun", "false")
                luxBool("infinitesun", infinitesun, "Sun Component", "Add Sunlight Component", gui, 2.0)
                if(infinitesun.get() == "true"):
                    sun_lg = luxProp(scn, "env.sun_lightgroup", "default")
                    luxString("env.lightgroup", sun_lg, "lightgroup", "Sun component light group", gui)
                    str += '\nLightGroup "' + sun_lg.get() + '"'
                    str += "\nLightSource \"sun\" "
                    infinitehassun = 1


            if envtype.get() == "sunsky" or infinitehassun == 1:
                
                
                sun = None
                for obj in scn.objects:
                    if (obj.getType() == "Lamp") and ((obj.Layers & scn.Layers) > 0):
                        if obj.getData(mesh=1).getType() == 1: # sun object # data
                            sun = obj
                if sun:
                    str += luxFloat("gain", luxProp(scn, "env.sunsky.gain", 1.0), 0.0, 1000.0, "gain", "Sky gain", gui)
                    
                    invmatrix = Mathutils.Matrix(sun.getInverseMatrix())
                    str += "\n   \"vector sundir\" [%f %f %f]\n" %(invmatrix[0][2], invmatrix[1][2], invmatrix[2][2])
                    str += luxFloat("relsize", luxProp(scn, "env.sunsky.relsize", 1.0), 0.0, 100.0, "rel.size", "relative sun size", gui)
                    str += luxFloat("turbidity", luxProp(scn, "env.sunsky.turbidity", 2.2), 2.0, 50.0, "turbidity", "Sky turbidity", gui)
                    
                    showGeo = luxProp(sun, 'sc.show', 'false')
                    if gui:
                        luxBool("sc.show", showGeo, "Geographic Sun", "Set sun position by world location, date and time", gui, 2.0)
                    if gui and showGeo.get() == 'true':
                        gui.newline("Geographic:")
                        sc = sun_calculator(sun)
                        
                        luxInt("sc.day", luxProp(sun, "sc.day", 1), 1, 31, "day", "Local date: day", gui, 0.66)
                        luxInt("sc.month", luxProp(sun, "sc.month", 1), 1, 12, "month", "Local date: month", gui, 0.67)
                        luxInt("sc.year", luxProp(sun, "sc.year", 2009), 1800, 2100, "year", "Local date: year", gui, 0.66)
                        
                        luxInt("sc.hour", luxProp(sun, "sc.hour", 0), 0, 23, "hour", "Local time: hour", gui, 0.72)
                        luxInt("sc.minute", luxProp(sun, "sc.minute", 0), 0, 59, "minute", "Local time: minute", gui, 0.72)
                        luxBool("sc.dst", luxProp(sun, "sc.dst", 'false'), "DST", "DST", gui, 0.28)
                        r = gui.getRect(0.28,1)
                        Draw.Button("NOW", 0, r[0], r[1], r[2], r[3], "Set to current time", lambda e,v: sc.now())
                        
                        r = gui.getRect(0.3,1)
                        Draw.Button("Preset", 0, r[0], r[1], r[2], r[3], "Choose a preset location", lambda e,v: sc.set_location(
                            Draw.PupTreeMenu(sun_calculator.location_list)
                        ))
                        
                        luxFloat("sc.lat", luxProp(sun, "sc.lat", 0.0), -90.0, 90.0, "lat", "Location: latitude", gui, 0.56)
                        luxFloat("sc.long", luxProp(sun, "sc.long", 0.0), -180.0, 180.0, "long", "Location: longitude", gui, 0.56)
                        luxInt("sc.tz", luxProp(sun, "sc.tz", 0), -12, 12, "timezone", "Local time: timezone offset from GMT", gui, 0.56)
                        
                        r = gui.getRect(2,1)
                        Draw.Button("Calculate", 0, r[0], r[1], r[2], r[3], "Calculate sun's position", lambda e,v: sc.compute())
                    
                else:
                    if gui:
                        gui.newline(); r = gui.getRect(2,1); BGL.glRasterPos2i(r[0],r[1]+5) 
                        Draw.Text("create a blender Sun Lamp")


            str += "\n"
        #if gui: gui.newline("GLOBAL:", 8, 0, None, [0.75,0.5,0.25])
        #luxFloat("scale", luxProp(scn, "global.scale", 1.0), 0.0, 10.0, "scale", "global world scale", gui)
        
    return str

class sun_calculator:
    #Based on SunLight v1.0 by Miguel Kabantsov (miguelkab@gmail.com)
    #Replaces the faulty sun position calculation algorythm with a precise calculation (Source for algorythm: http://de.wikipedia.org/wiki/Sonnenstand),
    #Co-Ordinates: http://www.bcca.org/misc/qiblih/latlong.html
    #Author: Nils-Peter Fischer (Nils-Peter.Fischer@web.de)
    
    sun = None
    
    lat = 0
    long = 0
    
    hour = 0
    min = 0
    tz = 0
    dst = 'false'
    
    day = 0
    month = 0
    year = 0
    
    location_list = [
        ("EUROPE",[
            ("Berlin, Germany",            1),
            ("Helsinki, Finland",          7),
            ("London, England",           10),
            ("Oslo, Norway",              58),
            ("Paris, France",             15),
            ("Rome, Italy",               18),
            ("Zurich, Switzerland",       21),
        ]),
    
        ("WORLD CITIES", [
            ("Beijing, China",             0),
            ("Bombay, India",              2),
            ("Buenos Aires, Argentina",    3),
            ("Cairo, Egypt",               4),
            ("Cape Town, South Africa",    5),
            ("Caracas, Venezuela",         6),
            ("Hong Kong, China",           8),
            ("Jerusalem, Israel",          9),
            ("Mexico City, Mexico",       11),
            ("Moscow, Russia",            12),
            ("New Delhi, India",          13),
            ("Ottawa, Canada",            14),
            ("Rio de Janeiro, Brazil",    16),
            ("Riyadh, Saudi Arabia",      17),
            ("Sydney, Australia",         19),
            ("Tokyo, Japan",              20), 
        ]),
        
        ("US CITIES", [
            ("Albuquerque, NM",           22),
            ("Anchorage, AK",             23),
            ("Atlanta, GA",               24),
            ("Austin, TX",                25),
            ("Birmingham, AL",            26),
            ("Bismarck, ND",              27),
            ("Boston, MA",                28),
            ("Boulder, CO",               29),
            ("Chicago, IL",               30),
            ("Dallas, TX",                31),
            ("Denver, CO",                32),
            ("Detroit, MI",               33),
            ("Honolulu, HI",              34),
            ("Houston, TX",               35),
            ("Indianapolis, IN",          36),
            ("Jackson, MS",               37),
            ("Kansas City, MO",           38),
            ("Los Angeles, CA",           39),
            ("Menomonee Falls, WI",       40),
            ("Miami, FL",                 41),
            ("Minneapolis, MN",           42),
            ("New Orleans, LA",           43),
            ("New York City, NY",         44),
            ("Oklahoma City, OK",         45),
            ("Philadelphia, PA",          46),
            ("Phoenix, AZ",               47),
            ("Pittsburgh, PA",            48),
            ("Portland, ME",              49),
            ("Portland, OR",              50),
            ("Raleigh, NC",               51),
            ("Richmond, VA",              52),
            ("Saint Louis, MO",           53),
            ("San Diego, CA",             54),
            ("San Francisco, CA",         55),
            ("Seattle, WA",               56),
            ("Washington DC",             57),
        ])
    ]

    location_data = {
        # Europe
        1:    ( 52.33, 13.30, 1),
        7:    ( 60.1667, 24.9667,2),
        10:   ( 51.50, 0.0, 0),
        58:   ( 59.56, 10.41, 1),
        15:   ( 48.8667, 2.667, 1),
        18:   ( 41.90, 12.4833, 1),
        21:   ( 47.3833, 8.5333, 1),
    
        # World Cities
        0:    ( 39.9167, 116.4167, 8),
        2:    ( 18.9333, 72.8333, 5.5),
        3:    (-34.60, -58.45, -3),
        4:    ( 30.10, 31.3667, 2),
        5:    (-33.9167, 18.3667, 2),
        6:    ( 10.50, -66.9333, -4),
        8:    ( 22.25, 114.1667, 8),
        9:    ( 31.7833, 35.2333, 2),
        11:   ( 19.4, -99.15, -6),
        12:   ( 55.75, 37.5833, 3),
        13:   ( 28.6, 77.2, 5.5),
        14:   ( 45.41667, -75.7, -5),
        16:   (-22.90, -43.2333, -3),
        17:   ( 24.633, 46.71667, 3),
        19:   (-33.8667,151.2167,10),
        20:   ( 35.70, 139.7667, 9), 
    
        # US Cities
        22:   ( 35.0833, -106.65, -7),
        23:   ( 61.217, -149.90, -9),
        24:   ( 33.733, -84.383, -5),
        25:   ( 30.283, -97.733, -6),
        26:   ( 33.521, -86.8025, -6),
        27:   ( 46.817, -100.783, -6),
        28:   ( 42.35, -71.05, -5),
        29:   ( 40.125, -105.237, -7),
        30:   ( 41.85, -87.65, -6),
        31:   ( 32.46, -96.47, -6),
        32:   ( 39.733, -104.983, -7),
        33:   ( 42.333, -83.05, -5),
        34:   ( 21.30, -157.85, -10),
        35:   ( 29.75, -95.35, -6),
        36:   ( 39.767, -86.15, -5),
        37:   ( 32.283, -90.183, -6),
        38:   ( 39.083, -94.567, -6),
        39:   ( 34.05, -118.233, -8),
        40:   ( 43.11, -88.10, -6),
        41:   ( 25.767, -80.183, -5),
        42:   ( 44.967, -93.25, -6),
        43:   ( 29.95, -90.067, -6),
        44:   ( 40.7167, -74.0167, -5),
        45:   ( 35.483, -97.533, -6),
        46:   ( 39.95, -75.15, -5),
        47:   ( 33.433, -112.067,-7),
        48:   ( 40.433, -79.9833, -5),
        49:   ( 43.666, -70.283, -5),
        50:   ( 45.517, -122.65, -8),
        51:   ( 35.783, -78.65, -5),
        52:   ( 37.5667, -77.450, -5),
        53:   ( 38.6167, -90.1833, -6),
        54:   ( 32.7667, -117.2167, -8),
        55:   ( 37.7667, -122.4167, -8),
        56:   ( 47.60, -122.3167, -8),
        57:   ( 38.8833, -77.0333, -5),
    }

    def __init__(self, sun):
        self.sun = sun
    
    def now(self):
        ct = time.localtime()
        
        if ct[8] == 0:
            dst = 'false'
        else:
            dst = 'true'
        
        luxProp(self.sun, 'sc.day', 0).set(ct[2])
        luxProp(self.sun, 'sc.month', 0).set(ct[1])
        luxProp(self.sun, 'sc.year', 0).set(ct[0])
        luxProp(self.sun, 'sc.hour', 0).set(ct[3])
        luxProp(self.sun, 'sc.minute', 0).set(ct[4])
        luxProp(self.sun, 'sc.dst', 0).set(dst)
        
        self.compute()
        
    def set_location(self, location):
        if location < 0: return
        
        lat, long, tz = self.location_data[location]
        luxProp(self.sun, "sc.lat", 0).set(lat)
        luxProp(self.sun, "sc.long", 0).set(long)
        luxProp(self.sun, "sc.tz", 0).set(tz)
        
        self.compute()
    
    def compute(self):
        
        self.lat  = luxProp(self.sun, "sc.lat", 0).get()
        self.long = luxProp(self.sun, "sc.long", 0).get()
        self.tz   = luxProp(self.sun, "sc.tz", 0).get()
        
        self.hour = luxProp(self.sun, "sc.hour", 0).get()
        self.min  = luxProp(self.sun, "sc.minute", 0).get()
        self.dst  = luxProp(self.sun, "sc.dst", 'false').get()
        if self.dst == 'true':
            self.dst = 1
        else:
            self.dst = 0
        
        self.day   = luxProp(self.sun, "sc.day", 0).get()
        self.month = luxProp(self.sun, "sc.month", 0).get()
        self.year  = luxProp(self.sun, "sc.year", 0).get()
        
        
        az,el = self.geoSunData(
            self.lat,
            self.long,
            self.year,
            self.month,
            self.day,
            self.hour + self.min/60.0,
            -self.tz + self.dst
        )
        
        self.sun.rot = math.radians(90-el), 0, math.radians(-az)
        
        Window.Redraw()
        
        
    # --- THE FOLLOWING METHODS ARE ADAPTED FROM LUXMAYA ---
    
    # mathematical helpers
    def sind(self, deg):
        return math.sin(math.radians(deg))
    
    def cosd(self, deg):
        return math.cos(math.radians(deg))
    
    def tand(self, deg):
        return math.tan(math.radians(deg))
    
    def asind(self, deg):
        return math.degrees(math.asin(deg))
    
    def atand(self, deg):
        return math.degrees(math.atan(deg))
    
    
    def geo_sun_astronomicJulianDate(self, Year, Month, Day, LocalTime, Timezone):
        """
        See quoted source in class header for explanation
        """
        
        if Month > 2.0:
            Y = Year
            M = Month
        else:
            Y = Year - 1.0
            M = Month + 12.0
            
        UT = LocalTime - Timezone
        hour = UT / 24.0
        A = int(Y/100.0)
        B = 2.0 - A+int(A/4.0)
        
        JD = math.floor(365.25*(Y+4716.0)) + math.floor(30.6001*(M+1.0)) + Day + hour + B - 1524.4
        
        return JD
    
    def geoSunData(self, Latitude, Longitude, Year, Month, Day, LocalTime, Timezone):
        """
        See quoted source in class header for explanation
        """
        
        JD = self.geo_sun_astronomicJulianDate(Year, Month, Day, LocalTime, Timezone)
        
        phi = Latitude
        llambda = Longitude
                
        n = JD - 2451545.0
        LDeg = (280.460 + 0.9856474*n) - (math.floor((280.460 + 0.9856474*n)/360.0) * 360.0)
        gDeg = (357.528 + 0.9856003*n) - (math.floor((357.528 + 0.9856003*n)/360.0) * 360.0)
        LambdaDeg = LDeg + 1.915 * self.sind(gDeg) + 0.02 * self.sind(2.0*gDeg)
        
        epsilonDeg = 23.439 - 0.0000004*n
        
        alphaDeg = self.atand( (self.cosd(epsilonDeg) * self.sind(LambdaDeg)) / self.cosd(LambdaDeg) )
        if self.cosd(LambdaDeg) < 0.0:
            alphaDeg += 180.0
            
        deltaDeg = self.asind( self.sind(epsilonDeg) * self.sind(LambdaDeg) )
        
        JDNull = self.geo_sun_astronomicJulianDate(Year, Month, Day, 0.0, 0.0)
        
        TNull = (JDNull - 2451545.0) / 36525.0
        T = LocalTime - Timezone
        
        thetaGh = 6.697376 + 2400.05134*TNull + 1.002738*T
        thetaGh -= math.floor(thetaGh/24.0) * 24.0
        
        thetaG = thetaGh * 15.0
        theta = thetaG + llambda
        
        tau = theta - alphaDeg
        
        a = self.atand( self.sind(tau) / ( self.cosd(tau)*self.sind(phi) - self.tand(deltaDeg)*self.cosd(phi)) )
        if self.cosd(tau)*self.sind(phi) - self.tand(deltaDeg)*self.cosd(phi) < 0.0:
            a += 180.0
        
        h = self.asind( self.cosd(deltaDeg)*self.cosd(tau)*self.cosd(phi) + self.sind(deltaDeg)*self.sind(phi) )
        
        R = 1.02 / (self.tand (h+(10.3/(h+5.11))))
        hR = h + R/60.0
        
        azimuth = a
        elevation = hR
        
        return azimuth, elevation

def luxAccelerator(scn, gui=None):
    str = ""
    if scn:
        acceltype = luxProp(scn, "accelerator.type", "tabreckdtree")
        str = luxIdentifier("Accelerator", acceltype, ["none", "tabreckdtree", "grid", "bvh"], "ACCEL", "select accelerator type", gui)
        if acceltype.get() == "tabreckdtree":
            if gui: gui.newline()
            str += luxInt("intersectcost", luxProp(scn, "accelerator.kdtree.interscost", 80), 0, 1000, "inters.cost", "specifies how expensive ray-object intersections are", gui)
            str += luxInt("traversalcost", luxProp(scn, "accelerator.kdtree.travcost", 1), 0, 1000, "trav.cost", "specifies how expensive traversing a ray through the kdtree is", gui)
            if gui: gui.newline()
            str += luxFloat("emptybonus", luxProp(scn, "accelerator.kdtree.emptybonus", 0.2), 0.0, 100.0, "empty.b", "promotes kd-tree nodes that represent empty space", gui)
            if gui: gui.newline()
            str += luxInt("maxprims", luxProp(scn, "accelerator.kdtree.maxprims", 1), 0, 1000, "maxprims", "maximum number of primitives in a kdtree volume before further splitting of the volume occurs", gui)
            str += luxInt("maxdepth", luxProp(scn, "accelerator.kdtree.maxdepth", -1), -1, 100, "maxdepth", "If positive, the maximum depth of the tree. If negative this value is set automatically", gui)
        if acceltype.get() == "unsafekdtree":
            if gui: gui.newline()
            str += luxInt("intersectcost", luxProp(scn, "accelerator.kdtree.interscost", 80), 0, 1000, "inters.cost", "specifies how expensive ray-object intersections are", gui)
            str += luxInt("traversalcost", luxProp(scn, "accelerator.kdtree.travcost", 1), 0, 1000, "trav.cost", "specifies how expensive traversing a ray through the kdtree is", gui)
            if gui: gui.newline()
            str += luxFloat("emptybonus", luxProp(scn, "accelerator.kdtree.emptybonus", 0.2), 0.0, 100.0, "empty.b", "promotes kd-tree nodes that represent empty space", gui)
            if gui: gui.newline()
            str += luxInt("maxprims", luxProp(scn, "accelerator.kdtree.maxprims", 1), 0, 1000, "maxprims", "maximum number of primitives in a kdtree volume before further splitting of the volume occurs", gui)
            str += luxInt("maxdepth", luxProp(scn, "accelerator.kdtree.maxdepth", -1), -1, 100, "maxdepth", "If positive, the maximum depth of the tree. If negative this value is set automatically", gui)
        if acceltype.get() == "grid":
            str += luxBool("refineimmediately", luxProp(scn, "accelerator.grid.refine", "false"), "refine immediately", "Makes the primitive intersectable as soon as it is added to the grid", gui)
    return str

def luxSystem(scn, gui=None):
    if scn:
        if gui: gui.newline("PATHS:", 10)
        lp = luxProp(scn, "lux", "")
        lp.set(Blender.sys.dirname(lp.get())+os.sep)
        luxPath("LUX dir", lp, "lux binary dir", "Lux installation path", gui, 2.0)

#        luxFile("GUI filename", luxProp(scn, "lux", ""), "lux-file", "filename and path of the lux GUI executable", gui, 2.0)
#        luxFile("Console filename", luxProp(scn, "luxconsole", ""), "lux-file-console", "filename and path of the lux console executable", gui, 2.0)
        if gui: gui.newline()
        luxFile("datadir", luxProp(scn, "datadir", ""), "default out dir", "default.lxs save path", gui, 2.0)

        if gui: gui.newline("PRIORITY:", 10)
        luxnice = luxProp(scn, "luxnice", 0)
        if osys.platform=="win32":
            r = gui.getRect(2, 1)
            Draw.Menu("priority%t|abovenormal%x-10|normal%x0|belownormal%x10|low%x19", evtLuxGui, r[0], r[1], r[2], r[3], luxnice.get(), "", lambda e,v: luxnice.set(v))
        else: luxInt("nice", luxnice, -20, 19, "nice", "nice value. Range goes from -20 (highest priority) to 19 (lowest)", gui)  

        if gui: gui.newline("THREADS:", 10)
        autothreads = luxProp(scn, "autothreads", "true")
        luxBool("autothreads", autothreads, "Auto Detect", "Automatically use all available processors", gui, 1.0)
        if autothreads.get()=="false":
            luxInt("threads", luxProp(scn, "threads", 1), 1, 100, "threads", "number of threads used for rendering", gui, 1.0)

        if gui: gui.newline("ANIM:", 10)
        useparamkeys = luxProp(scn, "useparamkeys", "false")
        luxBool("useparamkeys", useparamkeys, "Enable Parameter IPO Keyframing", "Enables keyframing of luxblend parameters", gui, 2.0)

        if gui: gui.newline("PARAMS:", 10)
        parammodeadvanced = luxProp(scn, "parammodeadvanced", "false")
        luxBool("parammodeadvanced", parammodeadvanced, "Default Advanced Parameters", "Always use advanced parameters by default", gui, 2.0)

        if gui: gui.newline("PREVIEW:", 10)
        qs = ["low","medium","high","very high"]
        defprevmat = luxProp(scn, "defprevmat", "high")
        luxOption("defprevmat", defprevmat, qs, "Materials", "Select default preview quality in material editor for materials", gui, 1.0)

        if gui: gui.newline("GAMMA:", 10)
        luxBool("RGC", luxProp(scn, "RGC", "true"), "RGC", "use reverse gamma correction", gui)
        luxBool("ColClamp", luxProp(scn, "colorclamp", "false"), "ColClamp", "clamp all colors to 0.0-0.9", gui)
        if gui: gui.newline("MESH:", 10)
        luxBool("mesh_optimizing", luxProp(scn, "mesh_optimizing", "true"), "optimize meshes", "Optimize meshes during export", gui, 2.0)
        #luxInt("trianglemesh thr", luxProp(scn, "trianglemesh_thr", 0), 0, 10000000, "trianglemesh threshold", "Vertex threshold for exporting (wald) trianglemesh object(s)", gui, 2.0)
        #if gui: gui.newline()
        #luxInt("barytrianglemesh thr", luxProp(scn, "barytrianglemesh_thr", 300000), 0, 100000000, "barytrianglemesh threshold", "Vertex threshold for exporting barytrianglemesh object(s) (slower but uses less memory)", gui, 2.0)
        if gui: gui.newline("INSTANCING:", 10)
        luxInt("instancing_threshold", luxProp(scn, "instancing_threshold", 2), 0, 1000000, "object instanding threshold", "Threshold to created instanced objects", gui, 2.0)


def scalelist(list, factor):
    for i in range(len(list)): list[i] = list[i] * factor
    return list


def luxMapping(key, mat, gui, level=0):
    global icon_map2d, icon_map2dparam
    if gui: gui.newline("2Dmap:", -2, level, icon_map2d)
    mapping = luxProp(mat, key+".mapping", "uv")
    mappings = ["uv","spherical","cylindrical","planar"]
    str = luxOption("mapping", mapping, mappings, "mapping", "", gui, 0.5)
    if mapping.get() == "uv":
        str += luxFloat("uscale", luxProp(mat, key+".uscale", 1.0), -100.0, 100.0, "Us", "u-scale", gui, 0.375)
        str += luxFloat("vscale", luxProp(mat, key+".vscale", -1.0), -100.0, 100.0, "Vs", "v-scale", gui, 0.375)
        str += luxFloat("udelta", luxProp(mat, key+".udelta", 0.0), -100.0, 100.0, "Ud", "u-delta", gui, 0.375)
        str += luxFloat("vdelta", luxProp(mat, key+".vdelta", 0.0), -100.0, 100.0, "Vd", "v-delta", gui, 0.375)
    if mapping.get() == "planar":
        str += luxFloat("udelta", luxProp(mat, key+".udelta", 0.0), -100.0, 100.0, "Ud", "u-delta", gui, 0.75)
        str += luxFloat("vdelta", luxProp(mat, key+".vdelta", 0.0), -100.0, 100.0, "Vd", "v-delta", gui, 0.75)
        if gui: gui.newline("v1:", -2, level+1, icon_map2dparam)
        str += luxVector("v1", luxProp(mat, key+".v1", "1 0 0"), -100.0, 100.0, "v1", "v1-vector", gui, 2.0)
        if gui: gui.newline("v2:", -2, level+1, icon_map2dparam)
        str += luxVector("v2", luxProp(mat, key+".v2", "0 1 0"), -100.0, 100.0, "v2", "v2-vector", gui, 2.0)
    return str

def lux3DMapping(key, mat, gui, level=0):
    global icon_map3dparam
    str = ""
    if gui: gui.newline("scale:", -2, level, icon_map3dparam)
    str += luxVectorUniform("scale", luxProp(mat, key+".3dscale", 1.0), 0.001, 1000.0, "scale", "scale-vector", gui, 2.0)
    if gui: gui.newline("rot:", -2, level, icon_map3dparam)
    str += luxVector("rotate", luxProp(mat, key+".3drotate", "0 0 0"), -360.0, 360.0, "rotate", "rotate-vector", gui, 2.0)
    if gui: gui.newline("move:", -2, level, icon_map3dparam)
    str += luxVector("translate", luxProp(mat, key+".3dtranslate", "0 0 0"), -1000.0, 1000.0, "move", "translate-vector", gui, 2.0)
    return str
    
    

def luxTexture(name, parentkey, type, default, min, max, caption, hint, mat, gui, matlevel, texlevel=0, lightsource=0, overrideicon=""):
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
        if texlevel == 0: texture = luxProp(mat, keyname+".texture", "imagemap")
        else: texture = luxProp(mat, keyname+".texture", "constant")
    else:
        texture = luxProp(mat, keyname+".texture", "blackbody")

    textures = ["constant","blackbody","equalenergy", "frequency", "gaussian", "regulardata", "irregulardata", "imagemap","mix","scale","bilerp","uv", "checkerboard","brick","dots","fbm","marble","wrinkled", "windy", "blender_marble", "blender_musgrave", "blender_wood", "blender_clouds", "blender_blend", "blender_distortednoise", "blender_noise", "blender_magic", "blender_stucci", "blender_voronoi", "harlequin"]

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
    luxOption("texture", texture, textures, "texture", "", gui, 0.9)
    str = "Texture \"%s\" \"%s\" \"%s\""%(texname, type, texture.get())

    if gui: Draw.PushButton(">", evtLuxGui, gui.xmax+gui.h, gui.y-gui.h, gui.h, gui.h, "Menu", lambda e,v: showMatTexMenu(mat,keyname,True))
    if gui: # Draw Texture level Material preview
        luxPreview(mat, parentkey, 1, False, False, name, gui, texlevel, [0.5, 0.5, 0.5])
        # Add an offset for next controls
        #r = gui.getRect(1.0, 1)
        #gui.x += 140

    if texture.get() == "constant":
        value = luxProp(mat, keyname+".value", default)
        if type == "float": luxFloat("value", value, min, max, "", "", gui, 1.1)
        elif type == "color": luxRGB("value", value, max, "", "", gui, 1.1)
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
        str += luxFloat("temperature", luxProp(mat, keyname+".bbtemp", 6500.0), 1000.0, 10000.0, "temperature", "Black Body temperature in degrees Kelvin", gui, 2.0, 1)

    if texture.get() == "equalenergy":
        if gui:
            if gui.xmax-gui.x < gui.w: gui.newline()
            r = gui.getRect(1.0, 1)
            gui.newline()
            drawBar(bar_equalenergy, gui.xmax-gui.w-7, r[1])
        str += luxFloat("energy", luxProp(mat, keyname+".energy", 1.0), 0.0, 1.0, "energy", "Energy of each spectral band", gui, 2.0, 1)

    if texture.get() == "frequency":
        str += luxFloat("freq", luxProp(mat, keyname+".freq", 0.01), 0.03, 100.0, "frequency", "Frequency in nm", gui, 2.0, 1)
        str += luxFloat("phase", luxProp(mat, keyname+".phase", 0.5), 0.0, 1.0, "phase", "Phase", gui, 1.1, 1)
        str += luxFloat("energy", luxProp(mat, keyname+".energy", 1.0), 0.0, 1.0, "energy", "Amount of mean energy", gui, 0.9, 1)

    if texture.get() == "gaussian":
        if gui:
            if gui.xmax-gui.x < gui.w: gui.newline()
            r = gui.getRect(1.0, 1)
            gui.newline()
            drawBar(bar_spectrum, gui.xmax-gui.w-7, r[1])
        str += luxFloat("wavelength", luxProp(mat, keyname+".wavelength", 550.0), 380.0, 720.0, "wavelength", "Mean Wavelength in visible spectrum in nm", gui, 2.0, 1)
        str += luxFloat("width", luxProp(mat, keyname+".width", 50.0), 20.0, 300.0, "width", "Width of gaussian distribution in nm", gui, 1.1, 1)
        str += luxFloat("energy", luxProp(mat, keyname+".energy", 1.0), 0.0, 1.0, "energy", "Amount of mean energy", gui, 0.9, 1)

    if texture.get() == "imagemap":
        str += luxOption("wrap", luxProp(mat, keyname+".wrap", "repeat"), ["repeat","black","clamp"], "repeat", "", gui, 1.1)
        str += luxFile("filename", luxProp(mat, keyname+".filename", ""), "file", "texture file path", gui, 2.0)
        str += luxFloat("gamma", luxProp(mat, keyname+".gamma", texturegamma()), 0.0, 6.0, "gamma", "", gui, 0.75)
        str += luxFloat("gain", luxProp(mat, keyname+".gain", 1.0), 0.0, 10.0, "gain", "", gui, 0.5)
        filttype = luxProp(mat, keyname+".filtertype", "bilinear")
        filttypes = ["mipmap_ewa","mipmap_trilinear","bilinear","nearest"]
        str += luxOption("filtertype", filttype, filttypes, "filtertype", "Choose the filtering method to use for the image texture", gui, 0.75)

        if filttype.get() == "mipmap_ewa" or filttype.get() == "mipmap_trilinear":    
            str += luxFloat("maxanisotropy", luxProp(mat, keyname+".maxanisotropy", 8.0), 1.0, 512.0, "maxaniso", "", gui, 1.0)
            str += luxInt("discardmipmaps", luxProp(mat, keyname+".discardmipmaps", 0), 0, 1, "discardmips", "", gui, 1.0)

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
            str += luxFloat("v00", luxProp(mat, keyname+".v00", 0.0), min, max, "v00", "", gui, 1.0)
            str += luxFloat("v01", luxProp(mat, keyname+".v01", 1.0), min, max, "v01", "", gui, 1.0)
            if gui: gui.newline("", -2)
            str += luxFloat("v10", luxProp(mat, keyname+".v10", 0.0), min, max, "v10", "", gui, 1.0)
            str += luxFloat("v11", luxProp(mat, keyname+".v11", 1.0), min, max, "v11", "", gui, 1.0)
        elif type == "color":
            if gui: gui.newline("          v00:", -2)
            str += luxRGB("v00", luxProp(mat, keyname+".v00", "0.0 0.0 0.0"), max, "v00", "", gui, 2.0)
            if gui: gui.newline("          v01:", -2)
            str += luxRGB("v01", luxProp(mat, keyname+".v01", "1.0 1.0 1.0"), max, "v01", "", gui, 2.0)
            if gui: gui.newline("          v10:", -2)
            str += luxRGB("v10", luxProp(mat, keyname+".v10", "0.0 0.0 0.0"), max, "v10", "", gui, 2.0)
            if gui: gui.newline("          v11:", -2)
            str += luxRGB("v11", luxProp(mat, keyname+".v11", "1.0 1.0 1.0"), max, "v11", "", gui, 2.0)
        str += luxMapping(keyname, mat, gui, level+1)

    if texture.get() == "windy":
        str += lux3DMapping(keyname, mat, gui, level+1)
        # this texture has no options 

    if texture.get() == "checkerboard":
        dim = luxProp(mat, keyname+".dim", 2)
        str += luxInt("dimension", dim, 2, 3, "dim", "", gui, 0.5)
        if dim.get() == 2: str += luxOption("aamode", luxProp(mat, keyname+".aamode", "closedform"), ["closedform","supersample","none"], "aamode", "antialiasing mode", gui, 0.6)
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
        str += luxInt("octaves", luxProp(mat, keyname+".octaves", 8), 1, 100, "octaves", "", gui, 1.1)
        if gui: gui.newline("", -2)
        str += luxFloat("roughness", luxProp(mat, keyname+".roughness", 0.5), 0.0, 1.0, "roughness", "", gui, 2.0, 1)
        if gui: gui.newline("", -2)
        str += lux3DMapping(keyname, mat, gui, level+1)

    if texture.get() == "marble":
        str += luxInt("octaves", luxProp(mat, keyname+".octaves", 8), 1, 100, "octaves", "", gui, 1.1)
        if gui: gui.newline("", -2)
        str += luxFloat("roughness", luxProp(mat, keyname+".roughness", 0.5), 0.0, 1.0, "roughness", "", gui, 2.0, 1)
        if gui: gui.newline("", -2)
        str += luxFloat("nscale", luxProp(mat, keyname+".nscale", 1.0), 0.0, 100.0, "nscale", "Scaling factor for the noise input", gui, 1.0)
        str += luxFloat("variation", luxProp(mat, keyname+".variation", 0.2), 0.0, 100.0, "variation", "A scaling factor for the noise input function", gui, 1.0)
        if gui: gui.newline("", -2)
        str += lux3DMapping(keyname, mat, gui, level+1)

    if texture.get() == "wrinkled":
        str += luxInt("octaves", luxProp(mat, keyname+".octaves", 8), 1, 100, "octaves", "", gui, 1.1)
        if gui: gui.newline("", -2)
        str += luxFloat("roughness", luxProp(mat, keyname+".roughness", 0.5), 0.0, 1.0, "roughness", "", gui, 2.0, 1)
        if gui: gui.newline("", -2)
        str += lux3DMapping(keyname, mat, gui, level+1)

    if texture.get() == "brick":
        if gui: gui.newline("brick:", -2, level+1, icon_texparam)

        str += luxFloat("brickwidth", luxProp(mat, keyname+".brickwidth", 0.3), 0.0, 10.0, "brickwidth (X)", "", gui, 1.0)
        str += luxFloat("brickheight", luxProp(mat, keyname+".brickheight", 0.1), 0.0, 10.0, "brickheight (Z)", "", gui, 1.0)
        str += luxFloat("brickdepth", luxProp(mat, keyname+".brickdepth", 0.15), 0.0, 10.0, "brickdepth (Y)", "", gui, 1.0)

        if gui: gui.newline("mortar:", -2, level+1, icon_texparam)

        str += luxFloat("mortarsize", luxProp(mat, keyname+".mortarsize", 0.01), 0.0, 1.0, "mortarsize", "", gui, 1.0)

        (s, l) = c(("", ""), luxTexture("bricktex", keyname, type, default, min, max, "bricktex", "", mat, gui, matlevel, texlevel+1, lightsource))
        (s, l) = c((s, l), luxTexture("mortartex", keyname, type, alternativedefault(type, default), min, max, "mortartex", "", mat, gui, matlevel, texlevel+1, lightsource))
        str = s + str + l

        str += lux3DMapping(keyname, mat, gui, level+1)

    if texture.get() == "blender_marble":
        if gui: gui.newline("noise:", -2, level+1, icon_texparam)

        mtype = luxProp(mat, keyname+".mtype", "soft")
        mtypes = ["soft","sharp","sharper"]
        str += luxOption("type", mtype, mtypes, "type", "", gui, 0.5)

        noisetype = luxProp(mat, keyname+".noisetype", "hard_noise")
        noisetypes = ["soft_noise","hard_noise"]
        str += luxOption("noisetype", noisetype, noisetypes, "noisetypes", "", gui, 0.75)

        str += luxInt("noisedepth", luxProp(mat, keyname+".noisedepth", 2), 0, 6, "noisedepth", "", gui, 0.75)

        str += luxFloat("noisesize", luxProp(mat, keyname+".noisesize", 0.25), 0.0, 2.0, "noisesize", "", gui, 1.0)
        str += luxFloat("turbulance", luxProp(mat, keyname+".turbulance", 5.0), 0.0, 200.0, "turbulance", "", gui, 1.0)

        if gui: gui.newline("basis:", -2, level+1, icon_texparam)
        noisebasis2 = luxProp(mat, keyname+".noisebasis2", "sin")
        noisebasises2 = ["sin","saw","tri"]
        str += luxOption("noisebasis2", noisebasis2, noisebasises2, "noisebasis2", "", gui, 0.7)

        noisebasis = luxProp(mat, keyname+".noisebasis", "blender_original")
        noisebasises = ["blender_original","original_perlin", "improved_perlin", "voronoi_f1", "voronoi_f2", "voronoi_f3", "voronoi_f4", "voronoi_f2f1", "voronoi_crackle", "cell_noise"]
        str += luxOption("noisebasis", noisebasis, noisebasises, "noisebasis", "", gui, 1.3)

        if gui: gui.newline("level:", -2, level+1, icon_texparam)
        str += luxFloat("bright", luxProp(mat, keyname+".bright", 1.0), 0.0, 2.0, "bright", "", gui, 1.0)
        str += luxFloat("contrast", luxProp(mat, keyname+".contrast", 1.0), 0.0, 10.0, "contrast", "", gui, 1.0)

        (s, l) = c(("", ""), luxTexture("tex1", keyname, type, default, min, max, "tex1", "", mat, gui, matlevel, texlevel+1, lightsource))
        (s, l) = c((s, l), luxTexture("tex2", keyname, type, alternativedefault(type, default), min, max, "tex2", "", mat, gui, matlevel, texlevel+1, lightsource))
        str = s + str + l

        str += lux3DMapping(keyname, mat, gui, level+1)

    if texture.get() == "blender_musgrave":
        if gui: gui.newline("type:", -2, level+1, icon_texparam)
        mtype = luxProp(mat, keyname+".mtype", "multifractal")
        mtypes = ["multifractal","ridged_multifractal", "hybrid_multifractal", "hetero_terrain", "fbm"]
        str += luxOption("type", mtype, mtypes, "type", "", gui, 2.0)

        str += luxFloat("h", luxProp(mat, keyname+".h", 1.0), 0.0, 2.0, "h", "", gui, 0.5)
        str += luxFloat("lacu", luxProp(mat, keyname+".lacu", 2.0), 0.0, 6.0, "lacu", "", gui, 0.75)
        str += luxFloat("octs", luxProp(mat, keyname+".octs", 2.0), 0.0, 8.0, "octs", "", gui, 0.75)

        if mtype.get() == "hetero_terrain":
            str += luxFloat("offset", luxProp(mat, keyname+".offset", 2.0), 0.0, 6.0, "offset", "", gui, 2.0)
        if mtype.get() == "ridged_multifractal":
            str += luxFloat("offset", luxProp(mat, keyname+".offset", 2.0), 0.0, 6.0, "offset", "", gui, 1.25)
            str += luxFloat("gain", luxProp(mat, keyname+".gain", 2.0), 0.0, 6.0, "gain", "", gui, 0.75)
        if mtype.get() == "hybrid_multifractal":
            str += luxFloat("offset", luxProp(mat, keyname+".offset", 2.0), 0.0, 6.0, "offset", "", gui, 1.25)
            str += luxFloat("gain", luxProp(mat, keyname+".gain", 2.0), 0.0, 6.0, "gain", "", gui, 0.75)

        str += luxFloat("outscale", luxProp(mat, keyname+".outscale", 1.0), 0.0, 10.0, "iscale", "", gui, 1.0)
        str += luxFloat("noisesize", luxProp(mat, keyname+".noisesize", 0.25), 0.0, 2.0, "noisesize", "", gui, 1.0)

        if gui: gui.newline("basis:", -2, level+1, icon_texparam)
        noisebasis = luxProp(mat, keyname+".noisebasis", "blender_original")
        noisebasises = ["blender_original","original_perlin", "improved_perlin", "voronoi_f1", "voronoi_f2", "voronoi_f3", "voronoi_f4", "voronoi_f2f1", "voronoi_crackle", "cell_noise"]
        str += luxOption("noisebasis", noisebasis, noisebasises, "noisebasis", "", gui, 2.0)

        if gui: gui.newline("level:", -2, level+1, icon_texparam)
        str += luxFloat("bright", luxProp(mat, keyname+".bright", 1.0), 0.0, 2.0, "bright", "", gui, 1.0)
        str += luxFloat("contrast", luxProp(mat, keyname+".contrast", 1.0), 0.0, 10.0, "contrast", "", gui, 1.0)

        (s, l) = c(("", ""), luxTexture("tex1", keyname, type, default, min, max, "tex1", "", mat, gui, matlevel, texlevel+1, lightsource))
        (s, l) = c((s, l), luxTexture("tex2", keyname, type, alternativedefault(type, default), min, max, "tex2", "", mat, gui, matlevel, texlevel+1, lightsource))
        str = s + str + l

        str += lux3DMapping(keyname, mat, gui, level+1)

    if texture.get() == "blender_wood":
        if gui: gui.newline("noise:", -2, level+1, icon_texparam)

        mtype = luxProp(mat, keyname+".mtype", "bands")
        mtypes = ["bands","rings","bandnoise", "ringnoise"]
        str += luxOption("type", mtype, mtypes, "type", "", gui, 0.5)

        noisetype = luxProp(mat, keyname+".noisetype", "hard_noise")
        noisetypes = ["soft_noise","hard_noise"]
        str += luxOption("noisetype", noisetype, noisetypes, "noisetypes", "", gui, 0.75)

        str += luxFloat("noisesize", luxProp(mat, keyname+".noisesize", 0.25), 0.0, 2.0, "noisesize", "", gui, 1.0)
        str += luxFloat("turbulance", luxProp(mat, keyname+".turbulance", 5.0), 0.0, 200.0, "turbulance", "", gui, 1.0)

        if gui: gui.newline("basis:", -2, level+1, icon_texparam)
        noisebasis2 = luxProp(mat, keyname+".noisebasis2", "sin")
        noisebasises2 = ["sin","saw","tri"]
        str += luxOption("noisebasis2", noisebasis2, noisebasises2, "noisebasis2", "", gui, 0.7)

        noisebasis = luxProp(mat, keyname+".noisebasis", "blender_original")
        noisebasises = ["blender_original","original_perlin", "improved_perlin", "voronoi_f1", "voronoi_f2", "voronoi_f3", "voronoi_f4", "voronoi_f2f1", "voronoi_crackle", "cell_noise"]
        str += luxOption("noisebasis", noisebasis, noisebasises, "noisebasis", "", gui, 1.3)

        if gui: gui.newline("level:", -2, level+1, icon_texparam)
        str += luxFloat("bright", luxProp(mat, keyname+".bright", 1.0), 0.0, 2.0, "bright", "", gui, 1.0)
        str += luxFloat("contrast", luxProp(mat, keyname+".contrast", 1.0), 0.0, 10.0, "contrast", "", gui, 1.0)

        (s, l) = c(("", ""), luxTexture("tex1", keyname, type, default, min, max, "tex1", "", mat, gui, matlevel, texlevel+1, lightsource))
        (s, l) = c((s, l), luxTexture("tex2", keyname, type, alternativedefault(type, default), min, max, "tex2", "", mat, gui, matlevel, texlevel+1, lightsource))
        str = s + str + l
    
        str += lux3DMapping(keyname, mat, gui, level+1)

    if texture.get() == "blender_clouds":
        if gui: gui.newline("noise:", -2, level+1, icon_texparam)

        mtype = luxProp(mat, keyname+".mtype", "default")
        mtypes = ["default","color"]
        str += luxOption("type", mtype, mtypes, "type", "", gui, 0.5)

        noisetype = luxProp(mat, keyname+".noisetype", "hard_noise")
        noisetypes = ["soft_noise","hard_noise"]
        str += luxOption("noisetype", noisetype, noisetypes, "noisetypes", "", gui, 0.75)

        str += luxFloat("noisesize", luxProp(mat, keyname+".noisesize", 0.25), 0.0, 2.0, "noisesize", "", gui, 1.0)
        str += luxInt("noisedepth", luxProp(mat, keyname+".noisedepth", 2), 0, 6, "noisedepth", "", gui, 1.0)

        if gui: gui.newline("basis:", -2, level+1, icon_texparam)
        noisebasis = luxProp(mat, keyname+".noisebasis", "blender_original")
        noisebasises = ["blender_original","original_perlin", "improved_perlin", "voronoi_f1", "voronoi_f2", "voronoi_f3", "voronoi_f4", "voronoi_f2f1", "voronoi_crackle", "cell_noise"]
        str += luxOption("noisebasis", noisebasis, noisebasises, "noisebasis", "", gui, 1.3)

        if gui: gui.newline("level:", -2, level+1, icon_texparam)
        str += luxFloat("bright", luxProp(mat, keyname+".bright", 1.0), 0.0, 2.0, "bright", "", gui, 1.0)
        str += luxFloat("contrast", luxProp(mat, keyname+".contrast", 1.0), 0.0, 10.0, "contrast", "", gui, 1.0)

        (s, l) = c(("", ""), luxTexture("tex1", keyname, type, default, min, max, "tex1", "", mat, gui, matlevel, texlevel+1, lightsource))
        (s, l) = c((s, l), luxTexture("tex2", keyname, type, alternativedefault(type, default), min, max, "tex2", "", mat, gui, matlevel, texlevel+1, lightsource))
        str = s + str + l
    
        str += lux3DMapping(keyname, mat, gui, level+1)

    if texture.get() == "blender_blend":
        if gui: gui.newline("type:", -2, level+1, icon_texparam)

        mtype = luxProp(mat, keyname+".mtype", "lin")
        mtypes = ["lin","quad","ease","diag","sphere","halo","radial"]
        str += luxOption("type", mtype, mtypes, "type", "", gui, 0.5)
        
        mflag = luxProp(mat, keyname+".flag", "false")
        str += luxBool("flipxy", mflag, "flipXY", "", gui, 0.5)

        if gui: gui.newline("level:", -2, level+1, icon_texparam)
        str += luxFloat("bright", luxProp(mat, keyname+".bright", 1.0), 0.0, 2.0, "bright", "", gui, 1.0)
        str += luxFloat("contrast", luxProp(mat, keyname+".contrast", 1.0), 0.0, 10.0, "contrast", "", gui, 1.0)

        (s, l) = c(("", ""), luxTexture("tex1", keyname, type, default, min, max, "tex1", "", mat, gui, matlevel, texlevel+1, lightsource))
        (s, l) = c((s, l), luxTexture("tex2", keyname, type, alternativedefault(type, default), min, max, "tex2", "", mat, gui, matlevel, texlevel+1, lightsource))
        str = s + str + l
        
        str += lux3DMapping(keyname, mat, gui, level+1)

    if texture.get() == "blender_distortednoise":
        if gui: gui.newline("noise:", -2, level+1, icon_texparam)
        
        str += luxFloat("distamount", luxProp(mat, keyname+".distamount", 1.0), 0.0, 10.0, "distamount", "", gui, 1.0)
        str += luxFloat("noisesize", luxProp(mat, keyname+".noisesize", 0.25), 0.0, 2.0, "noisesize", "", gui, 1.0)
        str += luxFloat("nabla", luxProp(mat, keyname+".nabla", 0.025), 0.000, 2.0, "nabla", "", gui, 1.0)
        
        if gui: gui.newline("distortion:", -2, level+1, icon_texparam)
        ntype = luxProp(mat, keyname+".type", "blender_original")
        ntypes = ["blender_original","original_perlin", "improved_perlin", "voronoi_f1", "voronoi_f2", "voronoi_f3", "voronoi_f4", "voronoi_f2f1", "voronoi_crackle", "cell_noise"]
        str += luxOption("type", ntype, ntypes, "type", "", gui, 1.3)
        
        if gui: gui.newline("basis:", -2, level+1, icon_texparam)
        noisebasis = luxProp(mat, keyname+".noisebasis", "blender_original")
        noisebasises = ["blender_original","original_perlin", "improved_perlin", "voronoi_f1", "voronoi_f2", "voronoi_f3", "voronoi_f4", "voronoi_f2f1", "voronoi_crackle", "cell_noise"]
        str += luxOption("noisebasis", noisebasis, noisebasises, "noisebasis", "", gui, 1.3)

        if gui: gui.newline("level:", -2, level+1, icon_texparam)
        str += luxFloat("bright", luxProp(mat, keyname+".bright", 1.0), 0.0, 2.0, "bright", "", gui, 1.0)
        str += luxFloat("contrast", luxProp(mat, keyname+".contrast", 1.0), 0.0, 10.0, "contrast", "", gui, 1.0)

        (s, l) = c(("", ""), luxTexture("tex1", keyname, type, default, min, max, "tex1", "", mat, gui, matlevel, texlevel+1, lightsource))
        (s, l) = c((s, l), luxTexture("tex2", keyname, type, alternativedefault(type, default), min, max, "tex2", "", mat, gui, matlevel, texlevel+1, lightsource))
        str = s + str + l
        
        str += lux3DMapping(keyname, mat, gui, level+1)

    if texture.get() == "blender_noise":        
        if gui: gui.newline("level:", -2, level+1, icon_texparam)
        str += luxFloat("bright", luxProp(mat, keyname+".bright", 1.0), 0.0, 2.0, "bright", "", gui, 1.0)
        str += luxFloat("contrast", luxProp(mat, keyname+".contrast", 1.0), 0.0, 10.0, "contrast", "", gui, 1.0)

        (s, l) = c(("", ""), luxTexture("tex1", keyname, type, default, min, max, "tex1", "", mat, gui, matlevel, texlevel+1, lightsource))
        (s, l) = c((s, l), luxTexture("tex2", keyname, type, alternativedefault(type, default), min, max, "tex2", "", mat, gui, matlevel, texlevel+1, lightsource))
        str = s + str + l
        
        str += lux3DMapping(keyname, mat, gui, level+1)
        
    if texture.get() == "blender_magic":
        if gui: gui.newline("noise:", -2, level+1, icon_texparam)
        
        str += luxInt("noisedepth", luxProp(mat, keyname+".noisedepth", 2), 0.0, 10.0, "noisedepth", "", gui, 1.0)
        str += luxFloat("turbulance", luxProp(mat, keyname+".turbulance", 5.0), 0.0, 2.0, "turbulance", "", gui, 1.0)

        if gui: gui.newline("level:", -2, level+1, icon_texparam)
        str += luxFloat("bright", luxProp(mat, keyname+".bright", 1.0), 0.0, 2.0, "bright", "", gui, 1.0)
        str += luxFloat("contrast", luxProp(mat, keyname+".contrast", 1.0), 0.0, 10.0, "contrast", "", gui, 1.0)

        (s, l) = c(("", ""), luxTexture("tex1", keyname, type, default, min, max, "tex1", "", mat, gui, matlevel, texlevel+1, lightsource))
        (s, l) = c((s, l), luxTexture("tex2", keyname, type, alternativedefault(type, default), min, max, "tex2", "", mat, gui, matlevel, texlevel+1, lightsource))
        str = s + str + l
        
        str += lux3DMapping(keyname, mat, gui, level+1)
        
    if texture.get() == "blender_stucci":
        if gui: gui.newline("noise:", -2, level+1, icon_texparam)
        mtype = luxProp(mat, keyname+".mtype", "Plastic")
        mtypes = ["Plastic","Wall In","Wall Out"]
        str += luxOption("type", mtype, mtypes, "type", "", gui, 0.5)

        noisetype = luxProp(mat, keyname+".noisetype", "soft_noise")
        noisetypes = ["soft_noise","hard_noise"]
        str += luxOption("noisetype", noisetype, noisetypes, "noisetypes", "", gui, 0.75)
        
        str += luxFloat("noisesize", luxProp(mat, keyname+".noisesize", 0.25), 0.0, 10.0, "noisesize", "", gui, 1.0)
        str += luxFloat("turbulance", luxProp(mat, keyname+".turbulance", 5.0), 0.0, 200.0, "turbulance", "", gui, 1.0)

        noisebasis = luxProp(mat, keyname+".noisebasis", "blender_original")
        noisebasises = ["blender_original","original_perlin", "improved_perlin", "voronoi_f1", "voronoi_f2", "voronoi_f3", "voronoi_f4", "voronoi_f2f1", "voronoi_crackle", "cell_noise"]
        str += luxOption("noisebasis", noisebasis, noisebasises, "noisebasis", "", gui, 1.3)

        if gui: gui.newline("level:", -2, level+1, icon_texparam)
        str += luxFloat("bright", luxProp(mat, keyname+".bright", 1.0), 0.0, 2.0, "bright", "", gui, 1.0)
        str += luxFloat("contrast", luxProp(mat, keyname+".contrast", 1.0), 0.0, 10.0, "contrast", "", gui, 1.0)

        (s, l) = c(("", ""), luxTexture("tex1", keyname, type, default, min, max, "tex1", "", mat, gui, matlevel, texlevel+1, lightsource))
        (s, l) = c((s, l), luxTexture("tex2", keyname, type, alternativedefault(type, default), min, max, "tex2", "", mat, gui, matlevel, texlevel+1, lightsource))
        str = s + str + l

        str += lux3DMapping(keyname, mat, gui, level+1)

    if texture.get() == "blender_voronoi":
        #if gui: gui.newline("distmetric:", -2, level+1, icon_texparam)
        mtype = luxProp(mat, keyname+".distmetric", "actual_distance")
        mtypes = ["actual_distance","distance_squared","manhattan", "chebychev", "minkovsky_half", "minkovsky_four", "minkovsky"]
        str += luxOption("distmetric", mtype, mtypes, "distmetric", "", gui, 1.1)

        if gui: gui.newline("param:", -2, level+1, icon_texparam)
        str += luxFloat("minkovsky_exp", luxProp(mat, keyname+".minkovsky_exp", 2.5), 0.001, 10.0, "minkovsky_exp", "", gui, 1.0)
        str += luxFloat("outscale", luxProp(mat, keyname+".outscale", 1.0), 0.01, 10.0, "outscale", "", gui, 1.0)
        str += luxFloat("noisesize", luxProp(mat, keyname+".noisesize", 0.25), 0.0, 2.0, "noisesize", "", gui, 1.0)
        str += luxFloat("nabla", luxProp(mat, keyname+".nabla", 0.025), 0.001, 0.1, "nabla", "", gui, 1.0)
        if gui: gui.newline("wparam:", -2, level+1, icon_texparam)
        str += luxFloat("w1", luxProp(mat, keyname+".w1", 1.0), -2.0, 2.0, "w1", "", gui, 1.0)
        str += luxFloat("w2", luxProp(mat, keyname+".w2", 0.0), -2.0, 2.0, "w2", "", gui, 1.0)
        str += luxFloat("w3", luxProp(mat, keyname+".w3", 0.0), -2.0, 2.0, "w3", "", gui, 1.0)
        str += luxFloat("w4", luxProp(mat, keyname+".w4", 0.0), -2.0, 2.0, "w4", "", gui, 1.0)

        if gui: gui.newline("level:", -2, level+1, icon_texparam)
        str += luxFloat("bright", luxProp(mat, keyname+".bright", 1.0), 0.0, 2.0, "bright", "", gui, 1.0)
        str += luxFloat("contrast", luxProp(mat, keyname+".contrast", 1.0), 0.0, 10.0, "contrast", "", gui, 1.0)

        (s, l) = c(("", ""), luxTexture("tex1", keyname, type, default, min, max, "tex1", "", mat, gui, matlevel, texlevel+1, lightsource))
        (s, l) = c((s, l), luxTexture("tex2", keyname, type, alternativedefault(type, default), min, max, "tex2", "", mat, gui, matlevel, texlevel+1, lightsource))
        str = s + str + l

        str += lux3DMapping(keyname, mat, gui, level+1)



    return (str+"\n", " \"texture %s\" [\"%s\"]"%(name, texname))


def luxSpectrumTexture(name, key, default, max, caption, hint, mat, gui, level=0):
    global icon_col
    if gui: gui.newline(caption, 4, level, icon_col, scalelist([0.5,0.6,0.5],2.0/(level+2)))
    str = ""
    keyname = "%s:%s"%(key, name)
    texname = "%s:%s"%(mat.getName(), keyname)
    value = luxProp(mat, keyname, default)
    link = luxRGB(name, value, max, "", hint, gui, 2.0)
    tex = luxProp(mat, keyname+".textured", False)
    if gui: Draw.Toggle("T", evtLuxGui, gui.x, gui.y-gui.h, gui.h, gui.h, tex.get()=="true", "use texture", lambda e,v:tex.set(["false","true"][bool(v)]))
    if tex.get()=="true":
        if gui: gui.newline("", -2)
        (str, link) = luxTexture(name, key, "color", default, 0, max, caption, hint, mat, gui, level+1)
        if value.getRGB() != (1.0, 1.0, 1.0):
            if str == "": # handle special case if texture is a just a constant
                str += "Texture \"%s\" \"color\" \"scale\" \"color tex1\" [%s] \"color tex2\" [%s]\n"%(texname+".scale", (link.rpartition("[")[2])[0:-1], value.get())
            else: str += "Texture \"%s\" \"color\" \"scale\" \"texture tex1\" [\"%s\"] \"color tex2\" [%s]\n"%(texname+".scale", texname, value.get())
            link = " \"texture %s\" [\"%s\"]"%(name, texname+".scale")
    return (str, link)

def luxLightSpectrumTexture(name, key, default, max, caption, hint, mat, gui, level=0):
    #if gui: gui.newline(caption, 4, level, icon_emission, scalelist([0.6,0.5,0.5],2.0/(level+2)))
    str = ""
    keyname = "%s:%s"%(key, name)
    texname = "%s:%s"%(mat.getName(), keyname)
    (str, link) = luxTexture(name, key, "color", default, 0, max, caption, hint, mat, gui, level+1, 0, 1)
    return (str, link)

def luxFloatTexture(name, key, default, min, max, caption, hint, mat, gui, level=0):
    global icon_float
    if gui: gui.newline(caption, 4, level, icon_float, scalelist([0.5,0.5,0.6],2.0/(level+2)))
    str = ""
    keyname = "%s:%s"%(key, name)
    texname = "%s:%s"%(mat.getName(), keyname)
    value = luxProp(mat, keyname, default)
    link = luxFloat(name, value, min, max, "", hint, gui, 2.0)
    tex = luxProp(mat, keyname+".textured", False)
    if gui: Draw.Toggle("T", evtLuxGui, gui.x, gui.y-gui.h, gui.h, gui.h, tex.get()=="true", "use texture", lambda e,v:tex.set(["false","true"][bool(v)]))
    if tex.get()=="true":
        if gui: gui.newline("", -2)
        (str, link) = luxTexture(name, key, "float", default, min, max, caption, hint, mat, gui, level+1)
        if value.get() != 1.0:
            if str == "": # handle special case if texture is a just a constant
                str += "Texture \"%s\" \"float\" \"scale\" \"float tex1\" [%s] \"float tex2\" [%s]\n"%(texname+".scale", (link.rpartition("[")[2])[0:-1], value.get())
            else: str += "Texture \"%s\" \"float\" \"scale\" \"texture tex1\" [\"%s\"] \"float tex2\" [%s]\n"%(texname+".scale", texname, value.get())
            link = " \"texture %s\" [\"%s\"]"%(name, texname+".scale")
    return (str, link)

def luxFloatSliderTexture(name, key, default, min, max, caption, hint, mat, gui, level=0):
        global icon_float
        if gui: gui.newline(caption, 4, level, icon_float, scalelist([0.5,0.5,0.6],2.0/(level+2)))
        str = ""
        keyname = "%s:%s"%(key, name)
        texname = "%s:%s"%(mat.getName(), keyname)
        value = luxProp(mat, keyname, default)
        link = luxFloat(name, value, min, max, caption, hint, gui, 2.0, 1)
        tex = luxProp(mat, keyname+".textured", False)
        if gui: Draw.Toggle("T", evtLuxGui, gui.x, gui.y-gui.h, gui.h, gui.h, tex.get()=="true", "use texture", lambda e,v:tex.set(["false","true"][bool(v)]))
        if tex.get()=="true":
                if gui: gui.newline("", -2)
                (str, link) = luxTexture(name, key, "float", default, min, max, caption, hint, mat, gui, level+1)
                if value.get() != 1.0:
                        if str == "": # handle special case if texture is a just a constant
                                str += "Texture \"%s\" \"float\" \"scale\" \"float tex1\" [%s] \"float tex2\" [%s]\n"%(texname+".scale", (link.rpartition("[")[2])[0:-1], value.get())
                        else: str += "Texture \"%s\" \"float\" \"scale\" \"texture tex1\" [\"%s\"] \"float tex2\" [%s]\n"%(texname+".scale", texname, value.get())
                        link = " \"texture %s\" [\"%s\"]"%(name, texname+".scale")
        return (str, link)


def luxExponentTexture(name, key, default, min, max, caption, hint, mat, gui, level=0):
    global icon_float
    if gui: gui.newline(caption, 4, level, icon_float, scalelist([0.5,0.5,0.6],2.0/(level+2)))
    str = ""
    keyname = "%s:%s"%(key, name)
    texname = "%s:%s"%(mat.getName(), keyname)
    value = luxProp(mat, keyname, default)

    if(value.get() == None): value.set(0.002)

#    link = luxFloat(name, value, min, max, "", hint, gui, 2.0)
    if gui:
        r = gui.getRect(2.0, 1)
        Draw.Number("", evtLuxGui, r[0], r[1], r[2], r[3], float(1.0/value.getFloat()), 1.0, 1000000.0, hint, lambda e,v: value.set(1.0/v))
    link = " \"float %s\" [%f]"%(name, value.getFloat())

    tex = luxProp(mat, keyname+".textured", False)
    if gui: Draw.Toggle("T", evtLuxGui, gui.x, gui.y-gui.h, gui.h, gui.h, tex.get()=="true", "use texture", lambda e,v:tex.set(["false","true"][bool(v)]))
    if tex.get()=="true":
        if gui: gui.newline("", -2)
        (str, link) = luxTexture(name, key, "float", default, min, max, caption, hint, mat, gui, level+1)
        if value.get() != 1.0:
            if str == "": # handle special case if texture is a just a constant
                str += "Texture \"%s\" \"float\" \"scale\" \"float tex1\" [%s] \"float tex2\" [%s]\n"%(texname+".scale", (link.rpartition("[")[2])[0:-1], value.get())
            else: str += "Texture \"%s\" \"float\" \"scale\" \"texture tex1\" [\"%s\"] \"float tex2\" [%s]\n"%(texname+".scale", texname, value.get())
            link = " \"texture %s\" [\"%s\"]"%(name, texname+".scale")
    return (str, link)


def luxDispFloatTexture(name, key, default, min, max, caption, hint, mat, gui, level=0):
    global icon_float
    if gui: gui.newline(caption, 4, level, icon_float, scalelist([0.5,0.5,0.6],2.0/(level+2)))
    str = ""
    keyname = "%s:%s"%(key, name)
    texname = "%s:%s"%(mat.getName(), keyname)
    value = luxProp(mat, keyname, default)
    link = luxFloat(name, value, min, max, "", hint, gui, 2.0)
    tex = luxProp(mat, keyname+".textured", False)
    if gui: Draw.Toggle("T", evtLuxGui, gui.x, gui.y-gui.h, gui.h, gui.h, tex.get()=="true", "use texture", lambda e,v:tex.set(["false","true"][bool(v)]))
    if tex.get()=="true":
        if gui: gui.newline("", -2)
        (str, link) = luxTexture(name, key, "float", default, min, max, caption, hint, mat, gui, level+1)
        str += "Texture \"%s\" \"float\" \"scale\" \"texture tex1\" [\"%s\"] \"float tex2\" [%s]\n"%(texname+".scale", texname, value.get())
        link = " \"texture %s\" [\"%s\"]"%(name, texname+".scale")
    return (str, link)

def luxIORFloatTexture(name, key, default, min, max, caption, hint, mat, gui, level=0):
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
    value = luxProp(mat, keyname, default)

    iorusepreset = luxProp(mat, keyname+".iorusepreset", "true")
    luxBool("iorusepreset", iorusepreset, "Preset", "Select from a list of predefined presets", gui, 0.4)

    if(iorusepreset.get() == "true"):
        iorpreset = luxProp(mat, keyname+".iorpreset", "24 - Fused silica glass")
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
            Draw.Button(iorpreset.get(), evtLuxGui, r[0], r[1], r[2], r[3], "select IOR preset", lambda e,v: setIor(Draw.PupTreeMenu(iortree), value, iorpreset, iortree, iordict))
        link = luxFloat(name, value, min, max, "IOR", hint, None, 1.6)
    else:
        link = luxFloat(name, value, min, max, "IOR", hint, gui, 1.6, 1)

    tex = luxProp(mat, keyname+".textured", False)
    if gui: Draw.Toggle("T", evtLuxGui, gui.x, gui.y-gui.h, gui.h, gui.h, tex.get()=="true", "use texture", lambda e,v:tex.set(["false","true"][bool(v)]))
    if tex.get()=="true":
        if gui: gui.newline("", -2)
        (str, link) = luxTexture(name, key, "float", default, min, max, caption, hint, mat, gui, level+1)
        if value.get() != 1.0:
            str += "Texture \"%s\" \"float\" \"scale\" \"texture tex1\" [\"%s\"] \"float tex2\" [%s]\n"%(texname+".scale", texname, value.get())
            link = " \"texture %s\" [\"%s\"]"%(name, texname+".scale")
    return (str, link)

def luxCauchyBFloatTexture(name, key, default, min, max, caption, hint, mat, gui, level=0):
    # IOR preset data
    cauchybnames = ["01 - Fused silica glass", "02 - Borosilicate glass BK7", "03 - Hard crown glass K5", "04 - Barium crown glass BaK4", "05 - Barium flint glass BaF10", "06 - Dense flint glass SF10" ]
    cauchybvals = [ 0.00354, 0.00420, 0.00459, 0.00531, 0.00743, 0.01342 ]

    global icon_float
    if gui: gui.newline(caption, 4, level, icon_float, scalelist([0.5,0.5,0.6],2.0/(level+2)))
    str = ""
    keyname = "%s:%s"%(key, name)
    texname = "%s:%s"%(mat.getName(), keyname)
    value = luxProp(mat, keyname, default)

    cauchybusepreset = luxProp(mat, keyname+".cauchybusepreset", "true")
    luxBool("cauchybusepreset", cauchybusepreset, "Preset", "Select from a list of predefined presets", gui, 0.4)

    if(cauchybusepreset.get() == "true"):
        cauchybpreset = luxProp(mat, keyname+".cauchybpreset", "01 - Fused silica glass")
        luxOption("cauchybpreset", cauchybpreset, cauchybnames, "  PRESET", "select CauchyB preset", gui, 1.6)
        idx = cauchybnames.index(cauchybpreset.get())
        value.set(cauchybvals[idx])
        link = luxFloat(name, value, min, max, "cauchyb", hint, None, 1.6)
    else:
        link = luxFloat(name, value, min, max, "cauchyb", hint, gui, 1.6, 1)

    tex = luxProp(mat, keyname+".textured", False)
    if gui: Draw.Toggle("T", evtLuxGui, gui.x, gui.y-gui.h, gui.h, gui.h, tex.get()=="true", "use texture", lambda e,v:tex.set(["false","true"][bool(v)]))
    if tex.get()=="true":
        if gui: gui.newline("", -2)
        (str, link) = luxTexture(name, key, "float", default, min, max, caption, hint, mat, gui, level+1)
        if value.get() != 1.0:
            str += "Texture \"%s\" \"float\" \"scale\" \"texture tex1\" [\"%s\"] \"float tex2\" [%s]\n"%(texname+".scale", texname, value.get())
            link = " \"texture %s\" [\"%s\"]"%(name, texname+".scale")
    return (str, link)

def luxLight(name, kn, mat, gui, level):
    if gui:
        if name != "": gui.newline(name+":", 10, level)
        else: gui.newline("color:", 0, level+1)
    (str,link) = luxLightSpectrumTexture("L", kn+"light", "1.0 1.0 1.0", 1.0, "Spectrum", "", mat, gui, level+1)
    if gui: gui.newline("")
    link += luxFloat("power", luxProp(mat, kn+"light.power", 100.0), 0.0, 10000.0, "Power(W)", "AreaLight Power in Watts", gui)
    link += luxFloat("efficacy", luxProp(mat, kn+"light.efficacy", 17.0), 0.0, 100.0, "Efficacy(lm/W)", "Efficacy Luminous flux/watt", gui)
    if gui: gui.newline("")
    link += luxFloat("gain", luxProp(mat, kn+"light.gain", 1.0), 0.0, 100.0, "gain", "Gain/scale multiplier", gui)
    lightgroup = luxProp(mat, kn+"light.lightgroup", "default")
    luxString("lightgroup", lightgroup, "group", "assign light to a named light-group", gui, 1.0)

    if gui: gui.newline("Photometric")
    pm = luxProp(mat, kn+"light.usepm", "false")
    luxBool("photometric", pm, "Photometric Diagram", "Enable Photometric Diagram options", gui, 2.0)

    if(pm.get()=="true"):
        pmtype = luxProp(mat, kn+"light.pmtype", "IESna")
        pmtypes = ["IESna", "imagemap"]
        luxOption("type", pmtype, pmtypes, "type", "Choose Photometric data type to use", gui, 0.6)
        if(pmtype.get() == "imagemap"):
            map = luxProp(mat, kn+"light.pmmapname", "")
            link += luxFile("mapname", map, "map-file", "filename of the photometric map", gui, 1.4)        
        if(pmtype.get() == "IESna"):
            map = luxProp(mat, kn+"light.pmiesname", "")
            link += luxFile("iesname", map, "ies-file", "filename of the IES photometric data file", gui, 1.4)        

    has_bump_options = 0
    has_object_options = 1
    return (str, link)

def luxLamp(name, kn, mat, gui, level):
    if gui:
        if name != "": gui.newline(name+":", 10, level)
        else: gui.newline("color:", 0, level+1)
#    if gui: gui.newline("", 10, level)
    (str,link) = luxLightSpectrumTexture("L", kn+"light", "1.0 1.0 1.0", 1.0, "Spectrum", "", mat, gui, level+1)
    if gui: gui.newline("")
    link += luxFloat("gain", luxProp(mat, kn+"light.gain", 1.0), 0.0, 100.0, "gain", "Gain/scale multiplier", gui)
    lightgroup = luxProp(mat, kn+"light.lightgroup", "default")
    luxString("lightgroup", lightgroup, "group", "assign light to a named light-group", gui, 1.0)

    if gui: gui.newline("Photometric")
    pm = luxProp(mat, kn+"light.usepm", "false")
    luxBool("photometric", pm, "Photometric Diagram", "Enable Photometric Diagram options", gui, 2.0)

    if(pm.get()=="true"):
        pmtype = luxProp(mat, kn+"light.pmtype", "IESna")
        pmtypes = ["IESna", "imagemap"]
        luxOption("type", pmtype, pmtypes, "type", "Choose Photometric data type to use", gui, 0.6)
        if(pmtype.get() == "imagemap"):
            map = luxProp(mat, kn+"light.pmmapname", "")
            link += luxFile("mapname", map, "map-file", "filename of the photometric map", gui, 1.4)        
        if(pmtype.get() == "IESna"):
            map = luxProp(mat, kn+"light.pmiesname", "")
            link += luxFile("iesname", map, "ies-file", "filename of the IES photometric data file", gui, 1.4)        

        link += luxBool("flipz", luxProp(mat, kn+"light.flipZ", "true"), "Flip Z", "Flip Z direction in mapping", gui, 2.0)

    return (str, link)

def luxSpot(name, kn, mat, gui, level):
    if gui:
        if name != "": gui.newline(name+":", 10, level)
        else: gui.newline("color:", 0, level+1)
#    if gui: gui.newline("", 10, level)
    (str,link) = luxLightSpectrumTexture("L", kn+"light", "1.0 1.0 1.0", 1.0, "Spectrum", "", mat, gui, level+1)
    if gui: gui.newline("")
    link += luxFloat("gain", luxProp(mat, kn+"light.gain", 1.0), 0.0, 100.0, "gain", "Gain/scale multiplier", gui)
    lightgroup = luxProp(mat, kn+"light.lightgroup", "default")
    luxString("lightgroup", lightgroup, "group", "assign light to a named light-group", gui, 1.0)

    if gui: gui.newline("Projection")
    proj = luxProp(mat, kn+"light.usetexproj", "false")
    luxBool("projection", proj, "Texture Projection", "Enable imagemap texture projection", gui, 2.0)

    if(proj.get() == "true"):
        map = luxProp(mat, kn+"light.pmmapname", "")
        link += luxFile("mapname", map, "map-file", "filename of the photometric map", gui, 2.0)        

    return (str, link)


def Preview_Sphereset(mat, kn, state):
    if state=="true":
        luxProp(mat, kn+"prev_sphere", "true").set("true")
        luxProp(mat, kn+"prev_plane", "false").set("false")
        luxProp(mat, kn+"prev_torus", "false").set("false")
def Preview_Planeset(mat, kn, state):
    if state=="true":
        luxProp(mat, kn+"prev_sphere", "true").set("false")
        luxProp(mat, kn+"prev_plane", "false").set("true")
        luxProp(mat, kn+"prev_torus", "false").set("false")
def Preview_Torusset(mat, kn, state):
    if state=="true":
        luxProp(mat, kn+"prev_sphere", "true").set("false")
        luxProp(mat, kn+"prev_plane", "false").set("false")
        luxProp(mat, kn+"prev_torus", "false").set("true")

def Preview_Update(mat, kn, defLarge, defType, texName, name, level):
    #print "%s %s %s %s %s %s %s" % (mat, kn, defLarge, defType, texName, name, level)
    
    Blender.Window.WaitCursor(True)
    scn = Scene.GetCurrent()

    # Size of preview thumbnail
    thumbres = 110 # default 110x110
    if(defLarge):
        large = luxProp(mat, kn+"prev_large", "true")
    else:
        large = luxProp(mat, kn+"prev_large", "false")
    if(large.get() == "true"):
        thumbres = 140 # small 140x140

    thumbbuf = thumbres*thumbres*3

#        consolebin = luxProp(scn, "luxconsole", "").get()
    consolebin = Blender.sys.dirname(luxProp(scn, "lux", "").get()) + os.sep + "luxconsole"
    if osys.platform == "win32": consolebin = consolebin + ".exe"

    PIPE = subprocess.PIPE
    p = subprocess.Popen((consolebin, '-b', '-'), bufsize=thumbbuf, stdin=PIPE, stdout=PIPE, stderr=PIPE)

    # Unremark to write debugging output to file
    # p.stdin = open('c:\preview.lxs', 'w')

    if defType == 0:    
        prev_sphere = luxProp(mat, kn+"prev_sphere", "true")
        prev_plane = luxProp(mat, kn+"prev_plane", "false")
        prev_torus = luxProp(mat, kn+"prev_torus", "false")
    elif defType == 1:
        prev_sphere = luxProp(mat, kn+"prev_sphere", "false")
        prev_plane = luxProp(mat, kn+"prev_plane", "true")
        prev_torus = luxProp(mat, kn+"prev_torus", "false")
    else:
        prev_sphere = luxProp(mat, kn+"prev_sphere", "false")
        prev_plane = luxProp(mat, kn+"prev_plane", "false")
        prev_torus = luxProp(mat, kn+"prev_torus", "true")

    # Zoom
    if luxProp(mat, kn+"prev_zoom", "false").get() == "true":
        p.stdin.write('LookAt 0.250000 -1.500000 0.750000 0.250000 -0.500000 0.750000 0.000000 0.000000 1.000000\nCamera "perspective" "float fov" [22.5]\n')
    else:
        p.stdin.write('LookAt 0.0 -3.0 0.5 0.0 -2.0 0.5 0.0 0.0 1.0\nCamera "perspective" "float fov" [22.5]\n')
    # Fleximage
    p.stdin.write('Film "fleximage" "integer xresolution" [%i] "integer yresolution" [%i] "integer displayinterval" [3] "integer ldr_writeinterval" [3600] "string tonemapper" ["reinhard"] "integer haltspp" [1] "integer reject_warmup" [64] "bool write_tonemapped_tga" ["false"] "bool write_untonemapped_exr" ["false"] "bool write_tonemapped_exr" ["false"] "bool write_untonemapped_igi" ["false"] "bool write_tonemapped_igi" ["false"] \n'%(thumbres, thumbres))
    p.stdin.write('PixelFilter "sinc"\n')
    # Quality
    scn = Scene.GetCurrent()
    defprevmat = luxProp(scn, "defprevmat", "high")
    quality = luxProp(mat, kn+"prev_quality", defprevmat.get())
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
    obwidth = luxProp(mat, kn+"prev_obwidth", 1.0)
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
        link = luxProp(mat,"link","").get()
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
        p.stdin.write('Shape "loopsubdiv" "integer nlevels" [3] "bool dmnormalsmooth" ["true"] "bool dmsharpboundary" ["false"] ')
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
    area = luxProp(mat, kn+"prev_arealight", "false")
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
    Draw.Redraw()
    Blender.Window.WaitCursor(False)

def luxPreview(mat, name, defType=0, defEnabled=False, defLarge=False, texName=None, gui=None, level=0, color=None):
    

    if gui:
        kn = name
        if texName: kn += ":"+texName
        if kn != "": kn += "."
        if(defEnabled == True):
            showpreview = luxProp(mat, kn+"prev_show", "true")
        else:
            showpreview = luxProp(mat, kn+"prev_show", "false")
        Draw.Toggle("P", evtLuxGui, gui.xmax, gui.y-gui.h, gui.h, gui.h, showpreview.get()=="true", "Preview", lambda e,v: showpreview.set(["false","true"][bool(v)]))
        if showpreview.get()=="true": 
            if(defLarge):
                large = luxProp(mat, kn+"prev_large", "true")
            else:
                large = luxProp(mat, kn+"prev_large", "false")
            voffset = -8
            rr = 5.65 
            if(large.get() == "true"):
                rr = 7
                voffset = 22
            gui.newline()
            r = gui.getRect(1.1, rr)
            if(color != None):
                BGL.glColor3f(color[0],color[1],color[2]); BGL.glRectf(r[0]-110, r[1], 418, r[1]+128+voffset); BGL.glColor3f(0.9, 0.9, 0.9)
            try: previewCache[(mat.name+":"+kn).__hash__()].draw(r[0]-82, r[1]+4)
            except: pass

            prev_sphere = luxProp(mat, kn+"prev_sphere", "true")
            prev_plane = luxProp(mat, kn+"prev_plane", "false")
            prev_torus = luxProp(mat, kn+"prev_torus", "false")
            if defType == 1:
                prev_sphere = luxProp(mat, kn+"prev_sphere", "false")
                prev_plane = luxProp(mat, kn+"prev_plane", "true")
                prev_torus = luxProp(mat, kn+"prev_torus", "false")
            elif defType == 2:
                prev_sphere = luxProp(mat, kn+"prev_sphere", "false")
                prev_plane = luxProp(mat, kn+"prev_plane", "false")
                prev_torus = luxProp(mat, kn+"prev_torus", "true")

            # preview mode toggle buttons
            Draw.Toggle("S", evtLuxGui, r[0]-108, r[1]+100+voffset, 22, 22, prev_sphere.get()=="true", "Draw Sphere", lambda e,v: Preview_Sphereset(mat, kn, ["false","true"][bool(v)]))
            Draw.Toggle("P", evtLuxGui, r[0]-108, r[1]+74+voffset, 22, 22, prev_plane.get()=="true", "Draw 2D Plane", lambda e,v: Preview_Planeset(mat, kn, ["false","true"][bool(v)]))
            Draw.Toggle("T", evtLuxGui, r[0]-108, r[1]+48+voffset, 22, 22, prev_torus.get()=="true", "Draw Torus", lambda e,v: Preview_Torusset(mat, kn, ["false","true"][bool(v)]))

            # Zoom toggle
            zoom = luxProp(mat, kn+"prev_zoom", "false")
            Draw.Toggle("Zoom", evtLuxGui, r[0]+66, r[1]+100+voffset, 50, 18, zoom.get()=="true", "Zoom", lambda e,v: zoom.set(["false","true"][bool(v)]))

            area = luxProp(mat, kn+"prev_arealight", "false")
            Draw.Toggle("Area", evtLuxGui, r[0]+66, r[1]+5, 50, 18, area.get()=="true", "Area", lambda e,v: area.set(["false","true"][bool(v)]))

            # Object width
            obwidth = luxProp(mat, kn+"prev_obwidth", 1.0)
            Draw.Number("Width:", evtLuxGui, r[0]+66, r[1]+78+voffset, 129, 18, obwidth.get(), 0.001, 10, "The width of the preview object in blender/lux 1m units", lambda e,v: obwidth.set(v))

            # large/small size
            Draw.Toggle("large", evtLuxGui, r[0]+200, r[1]+78+voffset, 88, 18, large.get()=="true", "Large", lambda e,v: large.set(["false","true"][bool(v)]))

            # Preview Quality
            qs = ["low","medium","high","very high"]
            scn = Scene.GetCurrent()
            defprevmat = luxProp(scn, "defprevmat", "high")
            quality = luxProp(mat, kn+"prev_quality", defprevmat.get())
            luxOptionRect("quality", quality, qs, "  Quality", "select preview quality", gui, r[0]+200, r[1]+100+voffset, 88, 18)

            # Update preview
            Draw.Button("Update Preview", evtLuxGui, r[0]+120, r[1]+5, 167, 18, "Update Material Preview", lambda e,v: Preview_Update(mat, kn, defLarge, defType, texName, name, level))

            # Reset depths after getRect()
            gui.y -= 92+voffset
            gui.y -= gui.h
            gui.hmax = 18 + 4

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
        mattype = luxProp(mat, kn+"type", "matte")
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


        link = luxOption("type", mattype, materials, "  TYPE", "select material type", gui)
        showadvanced = luxProp(mat, kn+"showadvanced", "false")
        luxBool("advanced", showadvanced, "Advanced", "Show advanced options", gui, 0.6)
        showhelp = luxProp(mat, kn+"showhelp", "false")
        luxHelp("help", showhelp, "Help", "Show Help Information", gui, 0.4)

        # show copy/paste menu button
        if gui: Draw.PushButton(">", evtLuxGui, gui.xmax+gui.h, gui.y-gui.h, gui.h, gui.h, "Menu", lambda e,v: showMatTexMenu(mat,keyname,False))

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
            lightgroup = luxProp(mat, kn+"light.lightgroup", "default")
            link = "LightGroup \"%s\"\n"%lightgroup.get()
            link += "AreaLightSource \"area\""
            (str,link) = c((str,link), luxLight("", kn, mat, gui, level))
            has_bump_options = 0
            has_object_options = 1
            has_emission_options = 0

        if mattype.get() == "boundvolume":
            link = ""
            voltype = luxProp(mat, kn+"vol.type", "homogeneous")
            vols = ["homogeneous", "exponential"]
            vollink = luxOption("type", voltype, vols, "type", "", gui)
            if voltype.get() == "homogeneous":
                link = "Volume \"homogeneous\""
            if voltype.get() == "exponential":
                link = "Volume \"exponential\""

            if gui: gui.newline("absorption:", 0, level+1)
            link += luxRGB("sigma_a", luxProp(mat, kn+"vol.sig_a", "1.0 1.0 1.0"), 1.0, "sigma_a", "The absorption cross section", gui)
            if gui: gui.newline("scattering:", 0, level+1)
            link += luxRGB("sigma_s", luxProp(mat, kn+"vol.sig_b", "0.0 0.0 0.0"), 1.0, "sigma_b", "The scattering cross section", gui)
            if gui: gui.newline("emission:", 0, level+1)
            link += luxRGB("Le", luxProp(mat, kn+"vol.le", "0.0 0.0 0.0"), 1.0, "Le", "The volume's emission spectrum", gui)
            if gui: gui.newline("assymetry:", 0, level+1)
            link += luxFloat("g", luxProp(mat, kn+"vol.g", 0.0), 0.0, 100.0, "g", "The phase function asymmetry parameter", gui)

            if voltype.get() == "exponential":
                if gui: gui.newline("form:", 0, level+1)
                link += luxFloat("a", luxProp(mat, kn+"vol.a", 1.0), 0.0, 100.0, "a/scale", "exponential::a parameter in the ae^{-bh} formula", gui)
                link += luxFloat("b", luxProp(mat, kn+"vol.b", 2.0), 0.0, 100.0, "b/falloff", "exponential::b parameter in the ae^{-bh} formula", gui)
                if gui: gui.newline("updir:", 0, level+1)
                link += luxVector("updir", luxProp(mat, kn+"vol.updir", "0 0 1"), -1.0, 1.0, "updir", "Up direction vector", gui, 2.0)

            link += str_opt

            has_bump_options = 0
            has_object_options = 0
            has_emission_options = 0

            return (str, link)

        if mattype.get() == "carpaint":
            if gui: gui.newline("name:", 0, level+1)
            carname = luxProp(mat, kn+"carpaint.name", "white")
            cars = ["","ford f8","polaris silber","opel titan","bmw339","2k acrylack","white","blue","blue matte"]
            carlink = luxOption("name", carname, cars, "name", "", gui)
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
            architectural = luxProp(mat, keyname+".architectural", "false")
            link += luxBool("architectural", architectural, "architectural", "Enable architectural glass", gui, 2.0)
            if architectural.get() == "false":
                chromadisp = luxProp(mat, keyname+".chromadisp", "false")
                luxBool("chromadisp", chromadisp, "Dispersive Refraction", "Enable Chromatic Dispersion", gui, 2.0)
                if chromadisp.get() == "true":
                    (str,link) = c((str,link), luxCauchyBFloatTexture("cauchyb", keyname, 0.0, 0.0, 1.0, "cauchyb", "", mat, gui, level+1))
                thinfilm = luxProp(mat, keyname+".thinfilm", "false")
                luxBool("thinfilm", thinfilm, "Thin Film Coating", "Enable Thin Film Coating", gui, 2.0)
                if thinfilm.get() == "true":
                    (str,link) = c((str,link), luxFloatSliderTexture("film", keyname, 200.0, 1.0, 1500.0, "film", "thickness of film coating in nanometers", mat, gui, level+1))
                    (str,link) = c((str,link), luxIORFloatTexture("filmindex", keyname, 1.5, 1.0, 6.0, "film IOR", "film coating index of refraction", mat, gui, level+1))
            has_bump_options = 1
            has_object_options = 1
            has_emission_options = 1
        if mattype.get() == "matte":
            orennayar = luxProp(mat, keyname+".orennayar", "false")
            (str,link) = c((str,link), luxSpectrumTexture("Kd", keyname, "1.0 1.0 1.0", 1.0, "diffuse", "", mat, gui, level+1))
            luxBool("orennayar", orennayar, "Oren-Nayar", "Enable Oren-Nayar BRDF", gui, 2.0)
            if orennayar.get() == "true":
                (str,link) = c((str,link), luxFloatTexture("sigma", keyname, 0.0, 0.0, 100.0, "sigma", "sigma value for Oren-Nayar BRDF", mat, gui, level+1))
            has_bump_options = 1
            has_object_options = 1
            has_emission_options = 1
        if mattype.get() == "mattetranslucent":
            orennayar = luxProp(mat, keyname+".orennayar", "false")
            (str,link) = c((str,link), luxSpectrumTexture("Kr", keyname, "1.0 1.0 1.0", 1.0, "reflection", "", mat, gui, level+1))
            (str,link) = c((str,link), luxSpectrumTexture("Kt", keyname, "1.0 1.0 1.0", 1.0, "transmission", "", mat, gui, level+1))
            luxBool("orennayar", orennayar, "Oren-Nayar", "Enable Oren-Nayar BRDF", gui, 2.0)
            if orennayar.get() == "true":
                (str,link) = c((str,link), luxFloatTexture("sigma", keyname, 0.0, 0.0, 100.0, "sigma", "", mat, gui, level+1))
            has_bump_options = 1
            has_object_options = 1
            has_emission_options = 1
        if mattype.get() == "metal":
            if gui: gui.newline("name:", 0, level+1)
            metalname = luxProp(mat, kn+"metal.name", "")
            metals = ["aluminium","amorphous carbon","silver","gold","copper"]

            if not(metalname.get() in metals):
                metals.append(metalname.get())
            metallink = luxOption("name", metalname, metals, "name", "", gui, 1.88)
            if gui: Draw.Button("...", evtLuxGui, gui.x, gui.y-gui.h, gui.h, gui.h, "click to select a nk file",lambda e,v:Window.FileSelector(lambda s:metalname.set(s), "Select nk file"))
            link += luxstr(metallink)
            anisotropic = luxProp(mat, kn+"metal.anisotropic", "false")
            if gui:
                gui.newline("")
                Draw.Toggle("A", evtLuxGui, gui.x-gui.h, gui.y-gui.h, gui.h, gui.h, anisotropic.get()=="true", "anisotropic roughness", lambda e,v:anisotropic.set(["false","true"][bool(v)]))
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
            thinfilm = luxProp(mat, keyname+".thinfilm", "false")
            luxBool("thinfilm", thinfilm, "Thin Film Coating", "Enable Thin Film Coating", gui, 2.0)
            if thinfilm.get() == "true":
                (str,link) = c((str,link), luxFloatSliderTexture("film", keyname, 200.0, 1.0, 1500.0, "film", "thickness of film coating in nanometers", mat, gui, level+1))
                (str,link) = c((str,link), luxIORFloatTexture("filmindex", keyname, 1.5, 1.0, 6.0, "film IOR", "film coating index of refraction", mat, gui, level+1))

            has_bump_options = 1
            has_object_options = 1
            has_emission_options = 1
        if mattype.get() == "roughglass":
            (str,link) = c((str,link), luxSpectrumTexture("Kr", keyname, "1.0 1.0 1.0", 1.0, "reflection", "", mat, gui, level+1))
            (str,link) = c((str,link), luxSpectrumTexture("Kt", keyname, "1.0 1.0 1.0", 1.0, "transmission", "", mat, gui, level+1))
            anisotropic = luxProp(mat, kn+"roughglass.anisotropic", "false")
            if gui:
                gui.newline("")
                Draw.Toggle("A", evtLuxGui, gui.x-gui.h, gui.y-gui.h, gui.h, gui.h, anisotropic.get()=="true", "anisotropic roughness", lambda e,v:anisotropic.set(["false","true"][bool(v)]))
            if anisotropic.get()=="true":
                (str,link) = c((str,link), luxExponentTexture("uroughness", keyname, 0.002, 0.0, 1.0, "u-exponent", "", mat, gui, level+1))
                (str,link) = c((str,link), luxExponentTexture("vroughness", keyname, 0.002, 0.0, 1.0, "v-exponent", "", mat, gui, level+1))
            else:
                (s, l) = luxExponentTexture("uroughness", keyname, 0.002, 0.0, 1.0, "exponent", "", mat, gui, level+1)
                (str,link) = c((str,link), (s, l))
                link += l.replace("uroughness", "vroughness", 1)
            (str,link) = c((str,link), luxIORFloatTexture("index", keyname, 1.5, 1.0, 6.0, "IOR", "", mat, gui, level+1))
            chromadisp = luxProp(mat, keyname+".chromadisp", "false")
            luxBool("chromadisp", chromadisp, "Dispersive Refraction", "Enable Chromatic Dispersion", gui, 2.0)
            if chromadisp.get() == "true":
                (str,link) = c((str,link), luxCauchyBFloatTexture("cauchyb", keyname, 0.0, 0.0, 1.0, "cauchyb", "", mat, gui, level+1))
            has_bump_options = 1
            has_object_options = 1
            has_emission_options = 1
        if mattype.get() == "shinymetal":
            (str,link) = c((str,link), luxSpectrumTexture("Kr", keyname, "1.0 1.0 1.0", 1.0, "reflection", "", mat, gui, level+1))
            (str,link) = c((str,link), luxSpectrumTexture("Ks", keyname, "1.0 1.0 1.0", 1.0, "specular", "", mat, gui, level+1))
            anisotropic = luxProp(mat, kn+"shinymetal.anisotropic", "false")
            if gui:
                gui.newline("")
                Draw.Toggle("A", evtLuxGui, gui.x-gui.h, gui.y-gui.h, gui.h, gui.h, anisotropic.get()=="true", "anisotropic roughness", lambda e,v:anisotropic.set(["false","true"][bool(v)]))
            if anisotropic.get()=="true":
                (str,link) = c((str,link), luxExponentTexture("uroughness", keyname, 0.002, 0.0, 1.0, "u-exponent", "", mat, gui, level+1))
                (str,link) = c((str,link), luxExponentTexture("vroughness", keyname, 0.002, 0.0, 1.0, "v-exponent", "", mat, gui, level+1))
            else:
                (s, l) = luxExponentTexture("uroughness", keyname, 0.002, 0.0, 1.0, "exponent", "", mat, gui, level+1)
                (str,link) = c((str,link), (s, l))
                link += l.replace("uroughness", "vroughness", 1)

            thinfilm = luxProp(mat, keyname+".thinfilm", "false")
            luxBool("thinfilm", thinfilm, "Thin Film Coating", "Enable Thin Film Coating", gui, 2.0)
            if thinfilm.get() == "true":
                (str,link) = c((str,link), luxFloatSliderTexture("film", keyname, 200.0, 1.0, 1500.0, "film", "thickness of film coating in nanometers", mat, gui, level+1))
                (str,link) = c((str,link), luxIORFloatTexture("filmindex", keyname, 1.5, 1.0, 6.0, "film IOR", "film coating index of refraction", mat, gui, level+1))

            has_bump_options = 1
            has_object_options = 1
            has_emission_options = 1
        if mattype.get() == "glossy":
            (str,link) = c((str,link), luxSpectrumTexture("Kd", keyname, "1.0 1.0 1.0", 1.0, "diffuse", "", mat, gui, level+1))
            useior = luxProp(mat, keyname+".useior", "false")
            if gui:
                gui.newline("")
                Draw.Toggle("I", evtLuxGui, gui.x-gui.h, gui.y-gui.h, gui.h, gui.h, useior.get()=="true", "Use IOR/Reflective index input", lambda e,v:useior.set(["false","true"][bool(v)]))
            if useior.get() == "true":
                (str,link) = c((str,link), luxIORFloatTexture("index", keyname, 1.5, 1.0, 50.0, "IOR", "", mat, gui, level+1))
                link += " \"color Ks\" [1.0 1.0 1.0]"    
            else:
                (str,link) = c((str,link), luxSpectrumTexture("Ks", keyname, "1.0 1.0 1.0", 1.0, "specular", "", mat, gui, level+1))
                link += " \"float index\" [0.0]"    
            anisotropic = luxProp(mat, kn+"glossy.anisotropic", "false")
            if gui:
                gui.newline("")
                Draw.Toggle("A", evtLuxGui, gui.x-gui.h, gui.y-gui.h, gui.h, gui.h, anisotropic.get()=="true", "anisotropic roughness", lambda e,v:anisotropic.set(["false","true"][bool(v)]))
            if anisotropic.get()=="true":
                (str,link) = c((str,link), luxExponentTexture("uroughness", keyname, 0.002, 0.0, 1.0, "u-exponent", "", mat, gui, level+1))
                (str,link) = c((str,link), luxExponentTexture("vroughness", keyname, 0.002, 0.0, 1.0, "v-exponent", "", mat, gui, level+1))
            else:
                (s, l) = luxExponentTexture("uroughness", keyname, 0.002, 0.0, 1.0, "exponent", "", mat, gui, level+1)
                (str,link) = c((str,link), (s, l))
                link += l.replace("uroughness", "vroughness", 1)

            absorption = luxProp(mat, keyname+".useabsorption", "false")
            luxBool("absorption", absorption, "Absorption", "Enable Coating Absorption", gui, 2.0)
            if absorption.get() == "true":
                (str,link) = c((str,link), luxSpectrumTexture("Ka", keyname, "1.0 1.0 1.0", 1.0, "absorption", "", mat, gui, level+1))
                (str,link) = c((str,link), luxFloatTexture("d", keyname, 0.15, 0.0, 1.0, "depth", "", mat, gui, level+1))
            has_bump_options = 1
            has_object_options = 1
            has_emission_options = 1


        # Bump mapping options (common)
        if (has_bump_options == 1):
            usebump = luxProp(mat, keyname+".usebump", "false")
            luxBool("usebump", usebump, "Bump Map", "Enable Bump Mapping options", gui, 2.0)
            if usebump.get() == "true":
                (str,link) = c((str,link), luxFloatTexture("bumpmap", keyname, 0.0, 0.0, 1.0, "bumpmap", "", mat, gui, level+1))

        # emission options (common)
        if (level == 0):
            if (has_emission_options == 1):
                if gui: gui.newline("", 2, level, None, [0.6,0.6,0.4])
                useemission = luxProp(mat, "emission", "false")
                luxBool("useemission", useemission, "Emission", "Enable emission options", gui, 2.0)
                if useemission.get() == "true":
                    # emission GUI is here but lux export will be done later 
                    luxLight("", "", mat, gui, level)
            else: luxProp(mat, "emission", "false").set("false") # prevent from exporting later

        # transformation options (common)
        if (level == 0):
            if gui: gui.newline("", 2, level, None, [0.6,0.6,0.4])
            usetransformation = luxProp(mat, "transformation", "false")
            luxBool("usetransformation", usetransformation, "Texture Transformation", "Enable transformation option", gui, 2.0)
            if usetransformation.get() == "true":
                scale = luxProp(mat, "3dscale", 1.0)
                rotate = luxProp(mat, "3drotate", "0 0 0")
                translate = luxProp(mat, "3dtranslate", "0 0 0")
                if gui:
                    gui.newline("scale:", -2, level, icon_map3dparam)
                    luxVectorUniform("scale", scale, 0.001, 1000.0, "scale", "scale-vector", gui, 2.0)
                    gui.newline("rot:", -2, level, icon_map3dparam)
                    luxVector("rotate", rotate, -360.0, 360.0, "rotate", "rotate-vector", gui, 2.0)
                    gui.newline("move:", -2, level, icon_map3dparam)
                    luxVector("translate", translate, -1000.0, 1000.0, "move", "translate-vector", gui, 2.0)
                str = ("TransformBegin\n\tScale %f %f %f\n"%( 1.0/scale.getVector()[0],1.0/scale.getVector()[1],1.0/scale.getVector()[2] ))+("\tRotate %f 1 0 0\n\tRotate %f 0 1 0\n\tRotate %f 0 0 1\n"%rotate.getVector())+("\tTranslate %f %f %f\n"%translate.getVector()) + str + "TransformEnd\n"

        # Object options (common)
        if (level == 0) and (has_object_options == 1):
            if gui: gui.newline("Mesh:", 2, level, icon, [0.6,0.6,0.4])
            usesubdiv = luxProp(mat, "subdiv", "false")
            luxBool("usesubdiv", usesubdiv, "Subdivision", "Enable Loop Subdivision options", gui, 1.0)
            usedisp = luxProp(mat, "dispmap", "false")
            luxBool("usedisp", usedisp, "Displacement Map", "Enable Displacement mapping options", gui, 1.0)
            if usesubdiv.get() == "true" or usedisp.get() == "true":
                luxInt("sublevels", luxProp(mat, "sublevels", 2), 0, 12, "sublevels", "The number of levels of object subdivision", gui, 2.0)
                sharpbound = luxProp(mat, "sharpbound", "false")
                luxBool("sharpbound", sharpbound, "Sharpen Bounds", "Sharpen boundaries during subdivision", gui, 1.0)
                nsmooth = luxProp(mat, "nsmooth", "true")
                luxBool("nsmooth", nsmooth, "Smooth", "Smooth faces during subdivision", gui, 1.0)
            if usedisp.get() == "true":
                (str,ll) = c((str,link), luxDispFloatTexture("dispmap", keyname, 0.1, -10, 10.0, "dispmap", "Displacement Mapping amount", mat, gui, level+1))
                luxFloat("sdoffset",  luxProp(mat, "sdoffset", 0.0), 0.0, 1.0, "Offset", "Offset for displacement map", gui, 2.0)
                usesubdiv.set("true");

        if mattype.get() == "light":
            return (str, link)

        str += "MakeNamedMaterial \"%s\"%s\n"%(matname, link)
    return (str, " \"string %s\" [\"%s\"]"%(luxname, matname))


def luxMaterial(mat, gui=None):
    str = ""
    if mat:
        if luxProp(mat, "type", "").get()=="": # lux material not defined yet
            print "Blender material \"%s\" has no lux material definition, converting..."%(mat.getName())
            try:
                convertMaterial(mat) # try converting the blender material to a lux material
            except: pass
        (str, link) = luxMaterialBlock("", "", "", mat, gui, 0)
        if luxProp(mat, "type", "matte").get() != "light":
            link = "NamedMaterial \"%s\""%(mat.getName())
        # export emission options (no gui)
        useemission = luxProp(mat, "emission", "false")
        if useemission.get() == "true":
            lightgroup = luxProp(mat, "light.lightgroup", "default")
            link += "\n\tLightGroup \"%s\"\n"%lightgroup.get()
            
            (estr, elink) = luxLight("", "", mat, None, 0)
            str += estr
            link += "\n\tAreaLightSource \"area\" "+elink 
            
        luxProp(mat, "link", "").set("".join(link))
    return str
        

def luxVolume(mat, gui=None):
    str = ""
    if mat:
        (str, link) = luxMaterialBlock("", "", "", mat, gui, 0)
        luxProp(mat, "link", "").set("".join(link))
    return str

runRenderAfterExport = None
def CBluxExport(default, run):
    global runRenderAfterExport
    runRenderAfterExport = run
    if default:
        datadir = luxProp(Scene.GetCurrent(), "datadir", "").get()
        if datadir=="": datadir = Blender.Get("datadir")
        filename = datadir + os.sep + "default.lxs"
        save_still(filename)
    else:
        Window.FileSelector(save_still, "Export", sys.makename(Blender.Get("filename"), ".lxs"))


def CBluxAnimExport(default, run, fileselect=True):
    if default:
        datadir = luxProp(Scene.GetCurrent(), "datadir", "").get()
        if datadir=="": datadir = Blender.Get("datadir")
        filename = datadir + os.sep + "default.lxs"
        save_anim(filename)
    else:
        if fileselect:
            Window.FileSelector(save_anim, "Export", sys.makename(Blender.Get("filename"), ".lxs"))
        else:
            datadir = luxProp(Scene.GetCurrent(), "datadir", "").get()
            if datadir=="": datadir = Blender.Get("datadir")
            filename = sys.makename(Blender.Get("filename") , ".lxs")
            save_anim(filename)


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
            luxProp(mat, dot(name)+"mapping","").set("uv")
            luxProp(mat, dot(name)+"uscale", 1.0).set(tex.size[0])
            luxProp(mat, dot(name)+"vscale", 1.0).set(-tex.size[1])
            luxProp(mat, dot(name)+"udelta", 0.0).set(tex.ofs[0]+0.5*(1.0-tex.size[0]))
            luxProp(mat, dot(name)+"vdelta", 0.0).set(-tex.ofs[1]-0.5*(1.0-tex.size[1]))
            if tex.mapping != Texture.Mappings["FLAT"]:
                print "Material Conversion Warning: for UV-texture-input only FLAT mapping is supported\n" 
        else:
            if tex.mapping == Texture.Mappings["FLAT"]:
                luxProp(mat, dot(name)+"mapping","").set("planar")
            elif tex.mapping == Texture.Mappings["TUBE"]:
                luxProp(mat, dot(name)+"mapping","").set("cylindrical")
            elif tex.mapping == Texture.Mappings["SPHERE"]:
                luxProp(mat, dot(name)+"mapping","").set("spherical")
            else: luxProp(mat, dot(name)+"mapping","").set("planar")
        luxProp(mat, dot(name)+"3dscale", "1.0 1.0 1.0").setVector((1.0/tex.size[0], 1.0/tex.size[1], 1.0/tex.size[2]))
        luxProp(mat, dot(name)+"3dtranslate", "0.0 0.0 0.0").setVector((-tex.ofs[0], -tex.ofs[1], -tex.ofs[2]))

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
            luxProp(mat, dot(name)+"texture", "").set("imagemap")
            luxProp(mat, dot(name)+"filename", "").set(texture.image.filename)
            luxProp(mat, dot(name)+"wrap", "").set(mapConstDict(texture.extend, Texture.ExtendModes, {"REPEAT":"repeat", "EXTEND":"clamp", "CLIP":"black"}, ""))
        else:
            if tex.texco != Texture.TexCo["GLOB"]:
                print "Material Conversion Warning: procedural textures supports global mapping only\n"
            noiseDict = {"BLENDER":"blender_original", "CELLNOISE":"cell_noise", "IMPROVEDPERLIN":"improved_perlin", "PERLIN":"original_perlin", "VORONOICRACKLE":"voronoi_crackle", "VORONOIF1":"voronoi_f1", "VORONOIF2":"voronoi_f2", "VORONOIF2F1":"voronoi_f2f1", "VORONOIF3":"voronoi_f3", "VORONOIF4":"voronoi_f4"}
            luxProp(mat, dot(name)+"bright", 1.0).set(texture.brightness)
            luxProp(mat, dot(name)+"contrast", 1.0).set(texture.contrast)
            if texture.type == Texture.Types["CLOUDS"]:
                luxProp(mat, dot(name)+"texture", "").set("blender_clouds")
                luxProp(mat, dot(name)+"mtype", "").set(mapConstDict(texture.stype, Texture.STypes, {"CLD_DEFAULT":"default", "CLD_COLOR":"color"}, ""))
                luxProp(mat, dot(name)+"noisetype", "").set({"soft":"soft_noise", "hard":"hard_noise"}[texture.noiseType])
                luxProp(mat, dot(name)+"noisesize", 0.25).set(texture.noiseSize)
                luxProp(mat, dot(name)+"noisedepth", 2).set(texture.noiseDepth)
                luxProp(mat, dot(name)+"noisebasis", "").set(mapConstDict(texture.noiseBasis, Texture.Noise, noiseDict, ""))
            elif texture.type == Texture.Types["WOOD"]:
                luxProp(mat, dot(name)+"texture", "").set("blender_wood")
                luxProp(mat, dot(name)+"mtype", "").set(mapConstDict(texture.stype, Texture.STypes, {"WOD_BANDS":"bands", "WOD_RINGS":"rings", "WOD_BANDNOISE":"bandnoise", "WOD_RINGNOISE":"ringnoise"}, ""))
                luxProp(mat, dot(name)+"noisebasis2", "").set(mapConstDict(texture.noiseBasis2, Texture.Noise, {"SINE":"sin", "SAW":"saw", "TRI":"tri"}, ""))
                luxProp(mat, dot(name)+"noisebasis", "").set(mapConstDict(texture.noiseBasis, Texture.Noise, noiseDict, ""))
                luxProp(mat, dot(name)+"noisetype", "").set({"soft":"soft_noise", "hard":"hard_noise"}[texture.noiseType])
                luxProp(mat, dot(name)+"noisesize", 0.25).set(texture.noiseSize)
                luxProp(mat, dot(name)+"turbulance", 0.25).set(texture.turbulence)
            elif texture.type == Texture.Types["MUSGRAVE"]:
                luxProp(mat, dot(name)+"texture", "").set("blender_musgrave")
                luxProp(mat, dot(name)+"mtype", "").set(mapConstDict(texture.stype, Texture.STypes, {"MUS_MFRACTAL":"multifractal", "MUS_RIDGEDMF":"ridged_multifractal", "MUS_HYBRIDMF":"hybrid_multifractal", "MUS_HTERRAIN":"hetero_terrain", "MUS_FBM":"fbm"}, ""))
                luxProp(mat, dot(name)+"noisebasis", "").set(mapConstDict(texture.noiseBasis, Texture.Noise, noiseDict, ""))
                luxProp(mat, dot(name)+"noisesize", 0.25).set(texture.noiseSize)
                # bug in blender python API: value of "hFracDim" is casted to Integer instead of Float (reported to Ideasman42 - will be fixed after Blender 2.47)
                if texture.hFracDim != 0.0: luxProp(mat, dot(name)+"h", 1.0).set(texture.hFracDim) # bug in blender API, "texture.hFracDim" returns a Int instead of a Float
                else: luxProp(mat, dot(name)+"h", 1.0).set(0.5) # use a default value
                # bug in blender python API: values "offset" and "gain" are missing in Python-API (reported to Ideasman42 - will be fixed after Blender 2.47)
                try:
                    luxProp(mat, dot(name)+"offset", 1.0).set(texture.offset)
                    luxProp(mat, dot(name)+"gain", 1.0).set(texture.gain)
                except AttributeError: pass
                luxProp(mat, dot(name)+"lacu", 2.0).set(texture.lacunarity)
                luxProp(mat, dot(name)+"octs", 2.0).set(texture.octs)
                luxProp(mat, dot(name)+"outscale", 1.0).set(texture.iScale)
            elif texture.type == Texture.Types["MARBLE"]:
                luxProp(mat, dot(name)+"texture", "").set("blender_marble")
                luxProp(mat, dot(name)+"mtype", "").set(mapConstDict(texture.stype, Texture.STypes, {"MBL_SOFT":"soft", "MBL_SHARP":"sharp", "MBL_SHARPER":"sharper"}, ""))
                luxProp(mat, dot(name)+"noisetype", "").set({"soft":"soft_noise", "hard":"hard_noise"}[texture.noiseType])
                luxProp(mat, dot(name)+"turbulance", 0.25).set(texture.turbulence)
                luxProp(mat, dot(name)+"noisedepth", 2).set(texture.noiseDepth)
                luxProp(mat, dot(name)+"noisebasis", "").set(mapConstDict(texture.noiseBasis, Texture.Noise, noiseDict, ""))
                luxProp(mat, dot(name)+"noisebasis2", "").set(mapConstDict(texture.noiseBasis2, Texture.Noise, {"SINE":"sin", "SAW":"saw", "TRI":"tri"}, ""))
                luxProp(mat, dot(name)+"noisesize", 0.25).set(texture.noiseSize)
            elif texture.type == Texture.Types["VORONOI"]:
                luxProp(mat, dot(name)+"texture", "").set("blender_voronoi")
                luxProp(mat, dot(name)+"distmetric", "").set({0:"actual_distance", 1:"distance_squared", 2:"manhattan", 3:"chebychev", 4:"minkovsky_half", 5:"minkovsky_four", 6:"minkovsky"}[texture.distMetric])
                luxProp(mat, dot(name)+"outscale", 1.0).set(texture.iScale)
                luxProp(mat, dot(name)+"noisesize", 0.25).set(texture.noiseSize)
                luxProp(mat, dot(name)+"minkosky_exp", 2.5).set(texture.exp)
                luxProp(mat, dot(name)+"w1", 1.0).set(texture.weight1)
                luxProp(mat, dot(name)+"w2", 0.0).set(texture.weight2)
                luxProp(mat, dot(name)+"w3", 0.0).set(texture.weight3)
                luxProp(mat, dot(name)+"w4", 0.0).set(texture.weight4)
            elif texture.type == Texture.Types["NOISE"]:
                luxProp(mat, dot(name)+"texture", "").set("blender_noise")
            elif texture.type == Texture.Types["DISTNOISE"]:
                luxProp(mat, dot(name)+"texture", "").set("blender_distortednoise")
                luxProp(mat, dot(name)+"distamount", 1.0).set(texture.distAmnt)
                luxProp(mat, dot(name)+"noisesize", 0.25).set(texture.noiseSize)
                luxProp(mat, dot(name)+"noisebasis", "").set(mapConstDict(texture.noiseBasis, Texture.Noise, noiseDict, ""))
                luxProp(mat, dot(name)+"noisebasis2", "").set(mapConstDict(texture.noiseBasis2, Texture.Noise, noiseDict, ""))
            elif texture.type == Texture.Types["MAGIC"]:
                luxProp(mat, dot(name)+"texture", "").set("blender_magic")
                luxProp(mat, dot(name)+"turbulance", 0.25).set(texture.turbulence)
                luxProp(mat, dot(name)+"noisedepth", 2).set(texture.noiseDepth)
            elif texture.type == Texture.Types["STUCCI"]:
                luxProp(mat, dot(name)+"texture", "").set("blender_stucci")
                luxProp(mat, dot(name)+"mtype", "").set(mapConstDict(texture.stype, Texture.STypes, {"STC_PLASTIC":"Plastic", "MSTC_WALLIN":"Wall In", "STC_WALLOUT":"Wall Out"}, ""))
                luxProp(mat, dot(name)+"noisetype", "").set({"soft":"soft_noise", "hard":"hard_noise"}[texture.noiseType])
                luxProp(mat, dot(name)+"noisesize", 0.25).set(texture.noiseSize)
                luxProp(mat, dot(name)+"turbulance", 0.25).set(texture.turbulence)
                luxProp(mat, dot(name)+"noisebasis", "").set(mapConstDict(texture.noiseBasis, Texture.Noise, noiseDict, ""))
            elif texture.type == Texture.Types["BLEND"]:
                luxProp(mat, dot(name)+"texture", "").set("blender_blend")
                luxProp(mat, dot(name)+"type", "").set(mapConstDict(texture.stype, Texture.STypes, {"BLN_LIN":"lin", "BLN_QUAD":"quad", "BLN_EASE":"ease", "BLN_DIAG":"diag", "BLN_SPHERE":"sphere", "BLN_HALO":"halo", "BLN_RADIAL":"radial"}, ""))
                luxProp(mat, dot(name)+"flipXY", "false").set({0:"false", 1:"true"}[texture.rot90])
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
        luxProp(mat, dot(basename)+"textured", "").set("true")

        name = basename
        if (alpha1 < 1.0) or (alpha2 < 1.0): # texture with transparency
            luxProp(mat, dot(basename)+"texture", "").set("mix")
            if alpha1 == alpha2: # constant alpha
                luxProp(mat, ddot(basename)+"amount.value", 1.0).set(alpha1)
            else:
                createLuxTexture(ddot(basename)+"amount", tex)
                luxProp(mat, ddot(basename)+"amount:tex1.value", 1.0).set(alpha1)
                luxProp(mat, ddot(basename)+"amount:tex2.value", 1.0).set(alpha2)
            # transparent to next texture
            name = ddot(basename)+"tex1"
            if len(texs) > 0:
                convertTextures(ddot(basename)+"tex1", texs, type, channel, val)
            else:
                if type=="float": luxProp(mat, ddot(basename)+"tex1.value", 1.0).set(val);
                else: luxProp(mat, ddot(basename)+"tex1.value", "1.0 1.0 1.0").setRGB((val[0], val[1], val[2]))
            name = ddot(basename)+"tex2"
        if val1 == val2: # texture with different colors / value
            if type == "col": luxProp(mat, dot(name)+"value", "1.0 1.0 1.0").setRGB(val1)
            else: luxProp(mat, dot(name)+"value", 1.0).set(val1)
        else:
            createLuxTexture(name, tex)
            if type == "col": luxProp(mat, ddot(name)+"tex1.value", "1.0 1.0 1.0").setRGB(val1)
            else: luxProp(mat, ddot(name)+"tex1.value", 1.0).set(val1)
            if type == "col": luxProp(mat, ddot(name)+"tex2.value", "1.0 1.0 1.0").setRGB(val2)
            else: luxProp(mat, ddot(name)+"tex2.value", 1.0).set(val2)


    def convertDiffuseTexture(name):
        texs = []
        for tex in mat.getTextures():
            if tex and (tex.mapto & Texture.MapTo["COL"] > 0) and (tex.tex) and (tex.tex.type != Texture.Types["NONE"]): texs.append(tex)
        if len(texs) > 0:
            luxProp(mat, name, "").setRGB((mat.ref, mat.ref, mat.ref))
            convertTextures(name, texs, "col", "col", (mat.R, mat.G, mat.B))
    def convertSpecularTexture(name):
        texs = []
        for tex in mat.getTextures():
            if tex and (tex.mapto & Texture.MapTo["CSP"] > 0) and (tex.tex) and (tex.tex.type != Texture.Types["NONE"]): texs.append(tex)
        if len(texs) > 0:
            luxProp(mat, name, "").setRGB((mat.ref*mat.spec, mat.ref*mat.spec, mat.ref*mat.spec))
            convertTextures(name, texs, "col", "col", (mat.specR, mat.specG, mat.specB))
    def convertMirrorTexture(name):
        texs = []
        for tex in mat.getTextures():
            if tex and (tex.mapto & Texture.MapTo["CMIR"] > 0) and (tex.tex) and (tex.tex.type != Texture.Types["NONE"]): texs.append(tex)
        if len(texs) > 0:
            luxProp(mat, name, "").setRGB((mat.ref, mat.ref, mat.ref))
            convertTextures(name, texs, "col", "col", (mat.mirR, mat.mirG, mat.mirB))
    def convertBumpTexture(basename):
        texs = []
        for tex in mat.getTextures():
            if tex and (tex.mapto & Texture.MapTo["NOR"] > 0) and (tex.tex) and (tex.tex.type != Texture.Types["NONE"]): texs.append(tex)
        if len(texs) > 0:
            name = basename+":bumpmap"
            luxProp(mat, basename+".usebump", "").set("true")
            luxProp(mat, dot(name)+"textured", "").set("true")
            luxProp(mat, name, "").set(1.0)
            convertTextures(name, texs, "float", "nor", 0.0)

    def makeMatte(name):
        luxProp(mat, dot(name)+"type", "").set("matte")
        luxProp(mat, name+":Kd", "").setRGB((mat.R*mat.ref, mat.G*mat.ref, mat.B*mat.ref))
        convertDiffuseTexture(name+":Kd")
        convertBumpTexture(name)
    def makeGlossy(name, roughness):
        luxProp(mat, dot(name)+"type", "").set("glossy")
        luxProp(mat, name+":Kd", "").setRGB((mat.R*mat.ref, mat.G*mat.ref, mat.B*mat.ref))
        luxProp(mat, name+":Ks", "").setRGB((mat.specR*mat.spec*0.5, mat.specG*mat.spec*0.5, mat.specB*mat.spec*0.5))
        luxProp(mat, name+":uroughness", 0.0).set(roughness)
        luxProp(mat, name+":vroughness", 0.0).set(roughness)
        convertDiffuseTexture(name+":Kd")
        convertSpecularTexture(name+":Ks")
        convertBumpTexture(name)
    def makeMirror(name):
        luxProp(mat, dot(name)+"type", "").set("mirror")
        luxProp(mat, name+":Kr", "").setRGB((mat.mirR, mat.mirG, mat.mirB))
        convertMirrorTexture(name+":Kr")
        convertBumpTexture(name)
    def makeGlass(name):
        luxProp(mat, dot(name)+"type", "").set("glass")
        luxProp(mat, name+":Kr", "").setRGB((0.0, 0.0, 0.0))
        luxProp(mat, name+":Kt", "").setRGB((mat.R, mat.G, mat.B))
        luxProp(mat, name+":index.iorusepreset", "").set("false")
        luxProp(mat, name+":index", 0.0).set(mat.getIOR())
        convertMirrorTexture(name+":Kr")
        convertDiffuseTexture(name+":Kt")
        convertBumpTexture(name)
    def makeRoughglass(name, roughness):
        luxProp(mat, dot(name)+"type", "").set("roughglass")
        luxProp(mat, name+":Kr", "").setRGB((0.0, 0.0, 0.0))
        luxProp(mat, name+":Kt", "").setRGB((mat.R, mat.G, mat.B))
        luxProp(mat, name+":index.iorusepreset", "").set("false")
        luxProp(mat, name+":index", 0.0).set(mat.getIOR())
        luxProp(mat, name+":uroughness", 0.0).set(roughness)
        luxProp(mat, name+":vroughness", 0.0).set(roughness)
        convertMirrorTexture(name+":Kr")
        convertDiffuseTexture(name+":Kt")
        convertBumpTexture(name)
    print "convert Blender material \"%s\" to lux material"%(mat.name)
    mat.properties['luxblend'] = {}
    if mat.emit > 0.0001:
        luxProp(mat, "type", "").set("light")
        luxProp(mat, "light.l", "").setRGB((mat.R, mat.G, mat.B))
        luxProp(mat, "light.gain", 1.0).set(mat.emit)
        return
    alpha = mat.alpha
    if not(mat.mode & Material.Modes.RAYTRANSP): alpha = 1.0
    alpha0name, alpha1name = "", ""
    if (alpha > 0.0) and (alpha < 1.0):
        luxProp(mat, "type", "").set("mix")
        luxProp(mat, ":amount", 0.0).set(alpha)
        alpha0name, alpha1name = "mat2", "mat1"
    if alpha > 0.0:
        mirror = mat.rayMirr
        if not(mat.mode & Material.Modes.RAYMIRROR): mirror = 0.0
        mirror0name, mirror1name = alpha1name, alpha1name
        if (mirror > 0.0) and (mirror < 1.0):
            luxProp(mat, dot(alpha1name)+"type", "").set("mix")
            luxProp(mat, alpha1name+":amount", 0.0).set(1.0 - mirror)
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




### Connect LRMDB ###
ConnectLrmdb = False
try:
    import socket  # try import of socket library
    ConnectLrmdb = True
    def downloadLRMDB(mat, id):
        if id.isalnum():
            DrawProgressBar(0.0,'Getting Material #'+id)
            try:
                HOST = 'www.luxrender.net'
                GET = '/lrmdb/en/material/download/'+id
                PORT = 80
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
                
            DrawProgressBar(1.0,'')
        else:
            print "ERROR: material id is not valid"
        return None
    
        
    #===========================================================================
    # COOKIETRANSPORT
    #===========================================================================
    
    #--------------------------------------------------------------------------- 
    # IMPORTS
    import cookielib, urllib2, xmlrpclib
    
    #---------------------------------------------------------------------------
    # pilfered from
    # https://fedorahosted.org/python-bugzilla/browser/bugzilla.py?rev=e6f699f06e92b1e49b1b8d2c8fbe89d9425a4a9a
    class CookieTransport(xmlrpclib.Transport):
        '''
        A subclass of xmlrpclib.Transport that supports cookies.
        '''
        
        cookiejar = None
        scheme = 'http'
        verbose = None
    
        # Cribbed from xmlrpclib.Transport.send_user_agent 
        def send_cookies(self, connection, cookie_request):
            '''
            Send all the cookie data that we have received
            '''
            
            if self.cookiejar is None:
                self.cookiejar = cookielib.CookieJar()
            elif self.cookiejar:
                # Let the cookiejar figure out what cookies are appropriate
                self.cookiejar.add_cookie_header(cookie_request)
                # Pull the cookie headers out of the request object...
                cookielist = list()
                for header, value in cookie_request.header_items():
                    if header.startswith('Cookie'):
                        cookielist.append([header, value])
                # ...and put them over the connection
                for header, value in cookielist:
                    connection.putheader(header, value)
    
        # This is the same request() method from xmlrpclib.Transport,
        # with a couple additions noted below
        def request(self, host, handler, request_body, verbose=0):
            '''
            Handle the request
            '''
            
            host_connection = self.make_connection(host)
            if verbose:
                host_connection.set_debuglevel(1)
    
            # ADDED: construct the URL and Request object for proper cookie handling
            request_url = "%s://%s/" % (self.scheme, host)
            cookie_request  = urllib2.Request(request_url) 
    
            self.send_request(host_connection, handler, request_body)
            self.send_host(host_connection, host) 
            
            # ADDED. creates cookiejar if None.
            self.send_cookies(host_connection, cookie_request)
            self.send_user_agent(host_connection)
            self.send_content(host_connection, request_body)
    
            errcode, errmsg, headers = host_connection.getreply()
    
            # ADDED: parse headers and get cookies here
            class CookieResponse:
                '''
                fake a response object that we can fill with the headers above
                '''
                
                def __init__(self, headers):
                    self.headers = headers
                    
                def info(self):
                    return self.headers
                
            cookie_response = CookieResponse(headers)
            
            # Okay, extract the cookies from the headers
            self.cookiejar.extract_cookies(cookie_response, cookie_request)
            
            # And write back any changes
            # DH THIS DOESN'T WORK
            # self.cookiejar.save(self.cookiejar.filename)
    
            if errcode != 200:
                raise xmlrpclib.ProtocolError(
                    host + handler,
                    errcode, errmsg,
                    headers
                )
    
            self.verbose = verbose
    
            try:
                sock = host_connection._conn.sock
            except AttributeError:
                sock = None
    
            return self._parse_response(host_connection.getfile(), sock)
    

    #===========================================================================
    # LRMDB Integration
    #===========================================================================
    class lrmdb:
        host              = 'http://www.luxrender.net/lrmdb/ixr'
        
        username          = ""
        password          = ""
        logged_in         = False
        
        SERVER            = None
        
        last_error_str    = None
        
        def last_error(self):
            return self.last_error_str #'LRMDB Connector: %s' %
        
        def login(self):
            try:
                result = self.SERVER.user.login(
                    self.username,
                    self.password
                )
                if not result:
                    raise
                else:
                    self.logged_in = True
                    return True
            except:
                self.last_error_str = 'Login Failed'
                self.logged_in = False
                return False
            
        def submit_object(self, mat, basekey, tex):
            if not self.check_creds(): return False
            
            try:
                result = 'Unknown Error'
                
                if tex:
                    name = Draw.PupStrInput('Name: ', '', 32)
                else:
                    name = mat.name
                
                result = self.SERVER.object.submit(
                    name,
                    MatTex2dict( getMatTex(mat, basekey, tex), tex )
                )
                if result is not True:
                    raise
                else:
                    return True
            except:
                self.last_error_str = 'Submit failed: %s' % result
                return False
        
        def check_creds(self):
            if self.SERVER is None:
                try:
                    self.SERVER = xmlrpclib.ServerProxy(self.host, transport=CookieTransport())
                except:
                    self.last_error_str = 'ServerProxy init failed'
                    return False
            
            
            if not self.logged_in:
                #if self.username is "":
                self.request_username()
                
                #if self.password is "":
                self.request_password()
                    
                return self.login()
            else:
                return True
                
        def request_username(self):
            self.username = Draw.PupStrInput("Username:", self.username, 32)
            
        def request_password(self):
            self.password = Draw.PupStrInput("Password:", self.password, 32)

    lrmdb_connector = lrmdb()
        
    
except: print "WARNING: LRMDB support not available"



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
                luxProp(mat, basekey+k, None).set(v)
                if k[-8:] == '.texture':
                    luxProp(mat, basekey+k[:-8]+'.textured', 'false').set('true')
            except: pass


LBX_VERSION = '0.7'

def MatTex2dict(d, tex = None):
    global LBX_VERSION
    
    if LBX_VERSION == '0.6':
    
        if tex is not None and tex == True:
            d['LUX_DATA'] = 'TEXTURE'
        else:
            d['LUX_DATA'] = 'MATERIAL'
        
        d['LUX_VERSION'] = '0.6'
        
        return d
    
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
        
        return lbx

def format_dictStr(dictStr):
    result = ''
    pos = 0
    indentStr = '  '
    newLine = '\n'
    
    for char in dictStr:
        if char in ['}', ']']:
            result += newLine
            pos -= 1
            for j in range(0,pos):
                result += indentStr
                
        result += char
        
        if char in [',', '{', '[']:
            result += newLine
            if char in ['{', '[']:
                pos += 1
            for j in range(0,pos):
                result += indentStr
            
    return result


def MatTex2str(d, tex = None):
    global LBX_VERSION
    
    if LBX_VERSION == '0.6':
        return format_dictStr(str( MatTex2dict(d, tex) )) #.replace(", \'", ",\n\'")
    
    elif LBX_VERSION == '0.7':
        return format_dictStr(str( MatTex2dict(d, tex) )) #.replace("], \'", "],\r\n\'").replace("[","\r\n\t[")
        

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
    if  ConnectLrmdb:
        menu += "|Download from DB%x5" #not(tex) and
        menu += "|Upload to DB%x6"

#    menu += "|%l|dump material%x99|dump clipboard%x98"
    r = Draw.PupMenu(menu)
    if r==1:
        luxclipboard = getMatTex(mat, basekey, tex)
    elif r==2: putMatTex(mat, luxclipboard, basekey, tex)
    elif r==3: 
        scn = Scene.GetCurrent()
        if (tex):
            Window.FileSelector(lambda fn:loadMatTex(mat, fn, basekey, tex), "load texture", luxProp(scn, "lux", "").get()+os.sep+".lbt")
        else:
            Window.FileSelector(lambda fn:loadMatTex(mat, fn, basekey, tex), "load material", luxProp(scn, "lux", "").get()+os.sep+".lbm")
    elif r==4:
        scn = Scene.GetCurrent()
        if (tex):
            Window.FileSelector(lambda fn:saveMatTex(mat, fn, basekey, tex), "save texture", luxProp(scn, "lux", "").get()+os.sep+".lbt")
        else:
            Window.FileSelector(lambda fn:saveMatTex(mat, fn, basekey, tex), "save material", luxProp(scn, "lux", "").get()+os.sep+".lbm")
    elif r==5:
        if not tex:
            id = Draw.PupStrInput("Material ID:", "", 32)
        else:
            id = Draw.PupStrInput("Texture ID:", "", 32)
        if id: putMatTex(mat, downloadLRMDB(mat, id), basekey, tex)
    elif r==6:
        global lrmdb_connector
        if not lrmdb_connector.submit_object(mat, basekey, tex):
            msg = lrmdb_connector.last_error()
        else:
            msg = 'OK'
            
        Draw.PupMenu("Upload: "+msg+".%t|OK")
#    elif r==99:
#        for k,v in mat.properties['luxblend'].convert_to_pyobject().items(): print k+"="+repr(v)
#    elif r==98:
#        for k,v in luxclipboard.items(): print k+"="+repr(v)
#    print ""
    Draw.Redraw()


def saveMatTex(mat, fn, basekey='', tex=False):
    global LuxIsGUI
    d = getMatTex(mat, basekey, tex)
    file = open(fn, 'w')
    file.write(MatTex2str(d, tex))
    file.close()
    if LuxIsGUI: Draw.Redraw()


def loadMatTex(mat, fn, basekey='', tex=None):
    global LuxIsGUI
    file = open(fn, 'r')
    data = file.read()
    file.close()
    data = str2MatTex(data, tex)
    putMatTex(mat, data, basekey, tex) 
    if LuxIsGUI: Draw.Redraw()


activemat = None
def setactivemat(mat):
    global activemat
    activemat = mat


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
        size = BGL.Buffer(BGL.GL_FLOAT, 4)
        BGL.glGetFloatv(BGL.GL_SCISSOR_BOX, size)
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
        BGL.glColor3f(0.5,0.5,0.5); BGL.glRectf(self.rect[0],self.rect[1],self.rect[2],self.rect[3])
        if self.over or self.scrolling: BGL.glColor3f(1.0,1.0,0.7)
        else: BGL.glColor3f(0.7,0.7,0.7)
        BGL.glRectf(self.sliderRect[0],self.sliderRect[1],self.sliderRect[2],self.sliderRect[3])
    def getTop(self):
        return self.viewHeight+self.position
    def scroll(self, delta):
        self.position = self.position + delta
        self.calcRects()
        Draw.Redraw()
    def Mouse(self):
        self.calcRects()
        coord, buttons = Window.GetMouseCoords(), Window.GetMouseButtons()
        over = (coord[0]>=self.winrect[0]+self.rect[0]) and (coord[0]<=self.winrect[0]+self.rect[2]) and \
               (coord[1]>=self.winrect[1]+self.rect[1]) and (coord[1]<=self.winrect[1]+self.rect[3])
        if Window.MButs.L and buttons > 0:
            if self.scrolling:
                if self.factor > 0: self.scroll((self.lastcoord[1]-coord[1])/self.factor)
                Draw.Redraw()
            elif self.over:
                self.scrolling = True
            self.lastcoord = coord
        elif self.scrolling:
            self.scrolling = False
            Draw.Redraw()
        if self.over != over: Draw.Redraw()
        self.over = over

scrollbar = scrollbar()


# gui main draw
def luxDraw():
    global icon_luxblend

    BGL.glClear(BGL.GL_COLOR_BUFFER_BIT)

    y = int(scrollbar.getTop()) # 420
    BGL.glColor3f(0.1,0.1,0.1); BGL.glRectf(0,0,440,y)
    BGL.glColor3f(1.0,0.5,0.0); BGL.glRasterPos2i(130,y-21); Draw.Text("CVS")
    BGL.glColor3f(0.9,0.9,0.9);

    drawLogo(icon_luxblend, 6, y-25);

    scn = Scene.GetCurrent()
    if scn:
        luxpage = luxProp(scn, "page", 0)
        gui = luxGui(y-70)

        # render presets
        BGL.glRasterPos2i(10,y-45); Draw.Text("Render presets:")
        luxpreset = luxProp(scn, "preset", "1C - Final - medium MLT/Path Tracing (indoor) (recommended)")
        presets = getScenePresets()
        presetskeys = presets.keys()
        presetskeys.sort()
        presetskeys.insert(0, "")
        presetsstr = "presets: %t"
        for i, v in enumerate(presetskeys): presetsstr = "%s %%x%d|%s"%(v, i, presetsstr)
        try: i = presetskeys.index(luxpreset.get())
        except ValueError: i = 0
        Draw.Menu(presetsstr, evtLuxGui, 110, y-50, 220, 18, i, "", lambda e,v: luxpreset.set(presetskeys[v]))
        Draw.Button("save", evtSavePreset, 330, y-50, 40, 18, "create a render-settings preset")
        Draw.Button("del", evtDeletePreset, 370, y-50, 40, 18, "delete a render-settings preset")

        # if preset is selected load values
        if luxpreset.get() != "":
            try:
                d = presets[luxpreset.get()]
                for k,v in d.items(): scn.properties['luxblend'][k] = v
            except: pass

        Draw.Button("Material", evtLuxGui, 10, y-70, 80, 16, "", lambda e,v:luxpage.set(0))
        Draw.Button("Cam/Env", evtLuxGui, 90, y-70, 80, 16, "", lambda e,v:luxpage.set(1))
        Draw.Button("Render", evtLuxGui, 170, y-70, 80, 16, "", lambda e,v:luxpage.set(2))
        Draw.Button("Output", evtLuxGui, 250, y-70, 80, 16, "", lambda e,v:luxpage.set(3))
        Draw.Button("System", evtLuxGui, 330, y-70, 80, 16, "", lambda e,v:luxpage.set(4))
        if luxpage.get() == 0:
            BGL.glColor3f(1.0,0.5,0.0);BGL.glRectf(10,y-74,90,y-70);BGL.glColor3f(0.9,0.9,0.9)
            obj = scn.objects.active
            if obj:
                if (obj.getType() == "Lamp"):
                    ltype = obj.getData(mesh=1).getType() # data
                    if (ltype == Lamp.Types["Area"]): luxLight("Area LIGHT", "", obj, gui, 0)
                    elif (ltype == Lamp.Types["Spot"]): luxSpot("Spot LIGHT", "", obj, gui, 0)
                    elif (ltype == Lamp.Types["Lamp"]): luxLamp("Point LIGHT", "", obj, gui, 0)
                else:
                    matfilter = luxProp(scn, "matlistfilter", "false")
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
                    gui.newline("MATERIAL:", 8) 
                    r = gui.getRect(1.1, 1)
                    Draw.Button("C", evtConvertMaterial, r[0]-gui.h, gui.y-gui.h, gui.h, gui.h, "convert blender material to lux material")
                    Draw.Menu(menustr, evtLuxGui, r[0], r[1], r[2], r[3], matindex, "", lambda e,v: setactivemat(mats[v]))
                    luxBool("", matfilter, "filter", "only show active object materials", gui, 0.5)

                    Draw.Button("L", evtLoadMaterial, gui.x, gui.y-gui.h, gui.h, gui.h, "load a material preset")
                    Draw.Button("S", evtSaveMaterial, gui.x+gui.h, gui.y-gui.h, gui.h, gui.h, "save a material preset")
                    Draw.Button("D", evtDeleteMaterial, gui.x+gui.h*2, gui.y-gui.h, gui.h, gui.h, "delete a material preset")
                    if len(mats) > 0:
                        setactivemat(mats[matindex])
                        luxMaterial(activemat, gui)
        if luxpage.get() == 1:
            BGL.glColor3f(1.0,0.5,0.0);BGL.glRectf(90,y-74,170,y-70);BGL.glColor3f(0.9,0.9,0.9)
            cam = scn.getCurrentCamera()
            if cam:
                r = gui.getRect(1.1, 1)
                luxCamera(cam.data, scn.getRenderingContext(), gui)
            gui.newline("", 10)
            luxEnvironment(scn, gui)
        if luxpage.get() == 2:
            BGL.glColor3f(1.0,0.5,0.0);BGL.glRectf(170,y-74,250,y-70);BGL.glColor3f(0.9,0.9,0.9)
            r = gui.getRect(1.1, 1)
            luxSampler(scn, gui)
            gui.newline("", 10)
            luxSurfaceIntegrator(scn, gui)
            gui.newline("", 10)
            luxVolumeIntegrator(scn, gui)
            gui.newline("", 10)
            luxPixelFilter(scn, gui)
        if luxpage.get() == 3:
            BGL.glColor3f(1.0,0.5,0.0);BGL.glRectf(250,y-74,330,y-70);BGL.glColor3f(0.9,0.9,0.9)
            r = gui.getRect(1.1, 1)
            luxFilm(scn, gui)
        if luxpage.get() == 4:
            BGL.glColor3f(1.0,0.5,0.0);BGL.glRectf(330,y-74,410,y-70);BGL.glColor3f(0.9,0.9,0.9)
            luxSystem(scn, gui)
            gui.newline("", 10)
            luxAccelerator(scn, gui)
            gui.newline("MATERIALS:", 10)
            r = gui.getRect(2,1)
            Draw.Button("convert all blender materials", 0, r[0], r[1], r[2], r[3], "convert all blender-materials to lux-materials", lambda e,v:convertAllMaterials())
            gui.newline("SETTINGS:", 10)
            r = gui.getRect(2,1)
            Draw.Button("save defaults", 0, r[0], r[1], r[2], r[3], "save current settings as defaults", lambda e,v:saveluxdefaults())
        y = gui.y - 80
        if y > 0: y = 0 # bottom align of render button
        run = luxProp(scn, "run", "true")
        dlt = luxProp(scn, "default", "true")
        clay = luxProp(scn, "clay", "false")
        lxs = luxProp(scn, "lxs", "true")
        lxo = luxProp(scn, "lxo", "true")
        lxm = luxProp(scn, "lxm", "true")
        lxv = luxProp(scn, "lxv", "true")
        net = luxProp(scn, "netrenderctl", "false")
        donet = luxProp(scn, "donetrender", "true")
        if (run.get()=="true"):
            Draw.Button("Render", 0, 10, y+20, 100, 36, "Render with Lux", lambda e,v:CBluxExport(dlt.get()=="true", True))
            Draw.Button("Render Anim", 0, 110, y+20, 100, 36, "Render animation with Lux", lambda e,v:CBluxAnimExport(dlt.get()=="true", True))
        else:
            Draw.Button("Export", 0, 10, y+20, 100, 36, "Export", lambda e,v:CBluxExport(dlt.get()=="true", False))
            Draw.Button("Export Anim", 0, 110, y+20, 100, 36, "Export animation", lambda e,v:CBluxAnimExport(dlt.get()=="true", False))

        Draw.Toggle("run", evtLuxGui, 320, y+40, 30, 16, run.get()=="true", "start Lux after export", lambda e,v: run.set(["false","true"][bool(v)]))
        Draw.Toggle("def", evtLuxGui, 350, y+40, 30, 16, dlt.get()=="true", "save to default.lxs", lambda e,v: dlt.set(["false","true"][bool(v)]))
        Draw.Toggle("clay", evtLuxGui, 380, y+40, 30, 16, clay.get()=="true", "all materials are rendered as white-matte", lambda e,v: clay.set(["false","true"][bool(v)]))
        Draw.Toggle(".lxs", 0, 290, y+20, 30, 16, lxs.get()=="true", "export .lxs scene file", lambda e,v: lxs.set(["false","true"][bool(v)]))
        Draw.Toggle(".lxo", 0, 320, y+20, 30, 16, lxo.get()=="true", "export .lxo geometry file", lambda e,v: lxo.set(["false","true"][bool(v)]))
        Draw.Toggle(".lxm", 0, 350, y+20, 30, 16, lxm.get()=="true", "export .lxm material file", lambda e,v: lxm.set(["false","true"][bool(v)]))
        Draw.Toggle(".lxv", 0, 380, y+20, 30, 16, lxm.get()=="true", "export .lxv volume file", lambda e,v: lxm.set(["false","true"][bool(v)]))
    BGL.glColor3f(0.9, 0.9, 0.9) ; BGL.glRasterPos2i(340,y+5) ; Draw.Text("Press Q or ESC to quit.", "tiny")
    scrollbar.height = scrollbar.getTop() - y
    scrollbar.draw()

mouse_xr=1 
mouse_yr=1 

activeObject = None
activeEvent = None
lastEventTime = 0
key_tabs = {
    Draw.ONEKEY:     0,
    Draw.TWOKEY:     1,
    Draw.THREEKEY:   2,
    Draw.FOURKEY:    3,
    Draw.FIVEKEY:    4,
}
def luxEvent(evt, val):  # function that handles keyboard and mouse events
    global activeObject, activemat, activeEvent, lastEventTime, key_tabs
    if evt == Draw.ESCKEY or evt == Draw.QKEY:
        stop = Draw.PupMenu("OK?%t|Cancel export %x1")
        if stop == 1:
            Draw.Exit()
            return
    scn = Scene.GetCurrent()
    if scn:
        if scn.objects.active != activeObject:
            activeObject = scn.objects.active
            activemat = None
            Window.QRedrawAll()
    if (evt == Draw.MOUSEX) or (evt == Draw.MOUSEY): scrollbar.Mouse()
    if evt == Draw.WHEELUPMOUSE: scrollbar.scroll(-16)
    if evt == Draw.WHEELDOWNMOUSE: scrollbar.scroll(16)
    if evt == Draw.PAGEUPKEY: scrollbar.scroll(-50)
    if evt == Draw.PAGEDOWNKEY: scrollbar.scroll(50)

    # scroll to [T]op and [B]ottom
    if evt == Draw.TKEY:
        scrollbar.scroll(-scrollbar.position)
    if evt == Draw.BKEY:
        scrollbar.scroll(100000)   # Some large number should be enough ?!

    # R key shortcut to launch render
    # E key shortcut to export current scene (not render)
    # P key shortcut to preview current material
    # These keys need time and process-complete locks
    if evt in [Draw.RKEY, Draw.EKEY, Draw.PKEY]:
        if activeEvent == None and (sys.time() - lastEventTime) > 5:
            lastEventTime = sys.time()
            if evt == Draw.RKEY:
                activeEvent = 'RKEY'
                CBluxExport(luxProp(scn, "default", "true").get() == "true", True)
                activeEvent = None
            if evt == Draw.EKEY:
                activeEvent = 'EKEY'
                CBluxExport(luxProp(scn, "default", "true").get() == "true", False)
                activeEvent = None
            if evt == Draw.PKEY:
                activeEvent = 'PKEY'
                if activemat != None:
                    Preview_Update(activemat, '', True, 0, None, None, None)
                activeEvent = None
        
    # Switch GUI tabs with number keys
    if evt in key_tabs.keys():
        luxProp(scn, "page", 0).set(key_tabs[evt])        
        luxDraw()
        Window.QRedrawAll()
          

    # Handle icon button events - note - radiance - this is a work in progress! :)
#    if evt == Draw.LEFTMOUSE and not val: 
#           size=BGL.Buffer(BGL.GL_FLOAT, 4) 
#           BGL.glGetFloatv(BGL.GL_SCISSOR_BOX, size) 
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
    if evt == evtLuxGui:
        Draw.Redraw()
    if evt == evtSavePreset:
        scn = Scene.GetCurrent()
        if scn:
            name = Draw.PupStrInput("preset name: ", "")
            if name != "":
                usedproperties = {}
                usedpropertiesfilterobj = None
                luxSurfaceIntegrator(scn)
                luxSampler(scn)
                luxPixelFilter(scn)
                # luxFilm(scn)
                luxAccelerator(scn)
                # luxEnvironment(scn)
                saveScenePreset(name, usedproperties.copy())
                luxProp(scn, "preset", "").set(name)
                Draw.Redraw()
    if evt == evtDeletePreset:
        presets = getScenePresets().keys()
        presets.sort()
        presetsstr = "delete preset: %t"
        for i, v in enumerate(presets): presetsstr += "|%s %%x%d"%(v, i)
        r = Draw.PupMenu(presetsstr, 20)
        if r >= 0:
            saveScenePreset(presets[r], None)
            Draw.Redraw()

    if evt == evtLoadMaterial:
        if activemat:
            mats = getMaterialPresets()
            matskeys = mats.keys()
            matskeys.sort()
            matsstr = "load preset: %t"
            for i, v in enumerate(matskeys): matsstr += "|%s %%x%d"%(v, i)
            r = Draw.PupMenu(matsstr, 20)
            if r >= 0:
                name = matskeys[r]
                try:
#                    for k,v in mats[name].items(): activemat.properties['luxblend'][k] = v
                    for k,v in mats[name].items(): luxProp(activemat, k, None).set(v)
                except: pass
                Draw.Redraw()
    if evt == evtSaveMaterial:
        if activemat:
            name = Draw.PupStrInput("preset name: ", "")
            if name != "":
                usedproperties = {}
                usedpropertiesfilterobj = activemat
                luxMaterial(activemat)
                saveMaterialPreset(name, usedproperties.copy())
                Draw.Redraw()
    if evt == evtDeleteMaterial:
        matskeys = getMaterialPresets().keys()
        matskeys.sort()
        matsstr = "delete preset: %t"
        for i, v in enumerate(matskeys): matsstr += "|%s %%x%d"%(v, i)
        r = Draw.PupMenu(matsstr, 20)
        if r >= 0:
            saveMaterialPreset(matskeys[r], None)
            Draw.Redraw()
    if evt == evtConvertMaterial:
        if activemat: convertMaterial(activemat)
        Draw.Redraw()
    if evt == evtLoadMaterial2:
        if activemat:
            scn = Scene.GetCurrent()
            Window.FileSelector(lambda fn:loadMatTex(activemat, fn), "load material", luxProp(scn, "lux", "").get()+os.sep+".lbm")
    if evt == evtSaveMaterial2:
        if activemat:
            scn = Scene.GetCurrent()
            Window.FileSelector(lambda fn:saveMaterial(activemat, fn), "save material", luxProp(scn, "lux", "").get()+os.sep+".lbm")
    

def setFocus(target):
    currentscene = Scene.GetCurrent()
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


# Parse command line arguments for batch mode rendering if supplied

try:
    batchindex = osys.argv.index('--batch')
    pyargs = osys.argv[osys.argv.index('--batch')+1:]
except: pyargs = []

if (pyargs != []) and (batchindex != 0):
    print "\n\nLuxBlend CVS - BATCH mode\n"
    LuxIsGUI = False

    scene = Scene.GetCurrent()
    context = scene.getRenderingContext()

    luxpath = ""
    import getopt
    o, a = getopt.getopt(pyargs, 's:e:o:t:l:',["scale=","haltspp=","run=", "lbm=", "lbt="])

    opts = {}
    for k,v in o:
        opts[k] = v

    if (opts.has_key('--run')) and (opts['--run'] == 'false'):
        print "Run: false"
        luxProp(scene, "run", "true").set("false")
    else:
        luxProp(scene, "run", "true").set("true")

    if opts.has_key('--scale'):
        print "Zoom: %s" %opts['--scale']
        luxProp(scene, "film.scale", "100 %").set(opts['--scale'])

    if opts.has_key('--haltspp'):
        print "haltspp: %s" %opts['--haltspp']
        luxProp(scene, "haltspp", 0).set(int(opts['--haltspp']))

    if opts.has_key('-s'):
        print "Start frame: %s" %opts['-s']
        context.startFrame(int(opts['-s']))
    else:
        print "Error: Start frame not supplied (-s)"; osys.exit(1)
    if opts.has_key('-e'):
        print "End frame: %s" %opts['-e']
        context.endFrame(int(opts['-e']))
    else:
        print "Error: End frame not supplied (-e)"; osys.exit(1)
    if opts.has_key('-l'):
        print "Path to lux binary: %s" %opts['-l']
        luxpathprop = luxProp(scene, "lux", "")
        luxpathprop.set(opts['-l'])
    else:
        print "Error: path to lux binary not supplied (-l)"; osys.exit(1)    
    if opts.has_key('-o'):
        print "Image output path: %s" %opts['-o']
        luxProp(scene, "overrideoutputpath", "").set(opts['-o'])
    else:
        print "Error: image output path not supplied (-o)"; osys.exit(1)    
    if opts.has_key('-t'):
        print "Temporary export path: %s" %opts['-t']
        luxProp(scene, "datadir", "").set(opts['-t'])
    else:
        print "Error: Temporary export path not supplied (-t)"; osys.exit(1)            
    
    if opts.has_key('--lbm'):
        print "Load material: %s" %opts['--lbm']
        mat = Material.Get("Material")
        if mat: loadMatTex(mat, opts['--lbm'])
        else:
            print "Error: No material with name \"Material\" found (--lbm)"; osys.exit(1)
            
    if opts.has_key('--lbt'):
        print "Load material: %s" %opts['--lbt']
        mat = Material.Get("Material")
        if mat: loadMatTex(mat, opts['--lbt'], ':Kd')
        else:
            print "Error: No material with name \"Material\" found (--lbt)"; osys.exit(1)

#    CBluxAnimExport(True, True)
    CBluxAnimExport(False, False, False) # as by zukazuka (http://www.luxrender.net/forum/viewtopic.php?f=11&t=1288)
    osys.exit(0)

else:
    print "\n\nLuxBlend CVS - UI mode\n"
    from Blender.Window import DrawProgressBar
    LuxIsGUI = True
    
    Draw.Register(luxDraw, luxEvent, luxButtonEvt) # init GUI

    luxpathprop = luxProp(Scene.GetCurrent(), "lux", "")
    luxpath = luxpathprop.get()
    luxrun = luxProp(Scene.GetCurrent(), "run", True).get()
    checkluxpath = luxProp(Scene.GetCurrent(), "checkluxpath", True).get()

    if checkluxpath and luxrun:
        if (luxpath is None) or (sys.exists(luxpath)<=0):
            # luxpath not valid, so delete entry from .blend scene file ...
            luxpathprop.delete()
            # and re-get luxpath, so we get the path from default-settings
            luxpath = luxpathprop.get()
            if (luxpath is None) or (sys.exists(luxpath)<=0):
                print "WARNING: LuxPath \"%s\" is not valid\n"%(luxpath)
                scn = Scene.GetCurrent()
                if scn:
                    r = Draw.PupMenu("Installation: Set path to the lux render software?%t|Yes%x1|No%x0|Never%x2")
                    if r == 1:
                        Window.FileSelector(lambda s:luxProp(scn, "lux", "").set(Blender.sys.dirname(s)+os.sep), "Select file in Lux path")
                        saveluxdefaults()
                    if r == 2:
                        newluxdefaults["checkluxpath"] = False
                        saveluxdefaults()
    else    :
        print "Lux path check disabled\n"
