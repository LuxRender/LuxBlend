#!BPY
"""Registration info for Blender menus:
Name: 'LuxBlend-v0.1-alpha-MatEditor...'
Blender: 240
Group: 'Export'
Tooltip: 'Export to LuxRender v0.1 scene format (.lxs)'
"""
#
# ***** BEGIN GPL LICENSE BLOCK *****
#
# --------------------------------------------------------------------------
# LuxBlend v0.1 alpha-MatEditor exporter
# --------------------------------------------------------------------------
#
# Authors:
# radiance, zuegs, ideasman42, luxblender
#
# Based on:
# * Indigo exporter 
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
import os
import sys as osys
import Blender
from Blender import Mesh, Scene, Object, Material, Texture, Window, sys, Draw, BGL, Mathutils, Lamp



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
	if luxProp(scn, "colorclamp", "true").get()=="true":
		ncol = ncol * 0.9
		if ncol > 0.9:
			ncol = 0.9
		if ncol < 0.0:
			ncol = 0.0
	return ncol

def exportMaterial(mat):
	str = "# Material '%s'\n" %mat.name
	return str+luxMaterial(mat)+"\n"


def exportMaterialGeomTag(mat):
	return "%s\n"%(luxProp(mat, "link", "").get())




################################################################




#-------------------------------------------------
# getMaterials(obj)
# helper function to get the material list of an object in respect of obj.colbits
#-------------------------------------------------
def getMaterials(obj, compress=False):
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
	return mats



######################################################
# luxExport class
######################################################

dummyMat = 2394723948 # random identifier for dummy material

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
		self.meshes = {}
		self.materials = []
		self.lights = []

	#-------------------------------------------------
	# analyseObject(self, obj, matrix, name)
	# called by analyseScene to build the lists before export
	#-------------------------------------------------
	def analyseObject(self, obj, matrix, name):
		light = False
		if (obj.users > 0):
			obj_type = obj.getType()
			if (obj.enableDupGroup or obj.enableDupVerts):
				for o, m in obj.DupObjects:
					self.analyseObject(o, m, "%s.%s"%(name, o.getName()))	
			elif (obj_type == "Mesh") or (obj_type == "Surf") or (obj_type == "Curve") or (obj_type == "Text"):
				mats = getMaterials(obj)
				if (len(mats)>0) and (mats[0]!=None) and ((mats[0].name=="PORTAL") or (luxProp(mats[0], "type", "").get()=="portal")):
					self.portals.append([obj, matrix])
				else:
					for mat in mats:
						if (mat!=None) and (mat not in self.materials):
							self.materials.append(mat)
						if (mat!=None) and (luxProp(mat, "type", "").get()=="light"):
							light = True
					mesh_name = obj.getData(name_only=True)
					try:
						self.meshes[mesh_name] += [obj]
					except KeyError:
						self.meshes[mesh_name] = [obj]				
					self.objects.append([obj, matrix])
			elif (obj_type == "Lamp"):
				ltype = obj.getData(mesh=1).getType() # data
				if (ltype == Lamp.Types["Lamp"]) or (ltype == Lamp.Types["Spot"]):
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
	# exportMesh(self, file, mesh, mats, name, portal)
	# exports mesh to the file without any optimization
	#-------------------------------------------------
	def exportMesh(self, file, mesh, mats, name, portal=False):
		if mats == []:
			mats = [dummyMat]
		for matIndex in range(len(mats)):
			if (mats[matIndex] != None):
				if (portal):
					file.write("\tShape \"trianglemesh\" \"integer indices\" [\n")
				else:
					self.exportMaterialLink(file, mats[matIndex])
					file.write("\tPortalShape \"trianglemesh\" \"integer indices\" [\n")
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
#							v = [vertex.co[0], vertex.co[1], vertex.co[2]]
							v = [vertex.co]
							if normalFltr[shape]:
								if (face.smooth):
#									v.extend(vertex.no)
									v.append(vertex.no)
								else:
#									v.extend(face.no)
									v.append(face.no)
							if (uvFltr[shape]) and (mesh.faceUV):
#								v.extend(face.uv[index])
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
						if (portal):
							file.write("\tPortalShape \"trianglemesh\" \"integer indices\" [\n")
						else:
							file.write("\tShape \"trianglemesh\" \"integer indices\" [\n")
						for face in exportFaces:
							file.write("%d %d %d\n"%(face[0], face[1], face[2]))
							if (len(face)==4):
								file.write("%d %d %d\n"%(face[0], face[2], face[3]))
						file.write("\t] \"point P\" [\n");
#						for vertex in exportVerts:
#							file.write("%f %f %f\n"%(vertex[0], vertex[1], vertex[2]))
						file.write("".join(["%f %f %f\n"%tuple(vertex[0]) for vertex in exportVerts]))
						if normalFltr[shape]:
							file.write("\t] \"normal N\" [\n")
#							for vertex in exportVerts:
#								file.write("%f %f %f\n"%(vertex[3], vertex[4], vertex[5]))
							file.write("".join(["%f %f %f\n"%tuple(vertex[1]) for vertex in exportVerts])) 
							if (uvFltr[shape]) and (mesh.faceUV):
								file.write("\t] \"float uv\" [\n")
#								for vertex in exportVerts:
#									file.write("%f %f\n"%(vertex[6], vertex[7]))
								file.write("".join(["%f %f\n"%tuple(vertex[2]) for vertex in exportVerts])) 
						else:			
							if (uvFltr[shape]) and (mesh.faceUV):
								file.write("\t] \"float uv\" [\n")
#								for vertex in exportVerts:
#									file.write("%f %f\n"%(vertex[3], vertex[4]))
								file.write("".join(["%f %f\n"%tuple(vertex[1]) for vertex in exportVerts])) 
						file.write("\t]\n")
						print "  shape(%s): %d vertices, %d faces"%(shapeText[shape], len(exportVerts), len(exportFaces))
	
	#-------------------------------------------------
	# exportMeshes(self, file)
	# exports meshes that uses instancing (meshes that are used by at least "instancing_threshold" objects)
	#-------------------------------------------------
	def exportMeshes(self, file):
		instancing_threshold = 2 # getLuxProp(self.scene, "instancing_threshold", 2)
		mesh_optimizing = True # getLuxProp(self.scene, "mesh_optimizing", False)
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
			if allow_instancing and (len(objs) >= instancing_threshold):
				del self.meshes[mesh_name]
				mesh.getFromObject(objs[0], 0, 1)
				print "blender-mesh: %s (%d vertices, %d faces)"%(mesh_name, len(mesh.verts), len(mesh.faces))
				file.write("ObjectBegin \"%s\"\n"%mesh_name)
				if (mesh_optimizing):
					self.exportMeshOpt(file, mesh, mats, mesh_name)
				else:
					self.exportMesh(file, mesh, mats, mesh_name)
				file.write("ObjectEnd # %s\n\n"%mesh_name)

	#-------------------------------------------------
	# exportObjects(self, file)
	# exports objects to the file
	#-------------------------------------------------
	def exportObjects(self, file):
		mesh_optimizing = True # getLuxProp(self.scene, "mesh_optimizing", False)
		mesh = Mesh.New('')
		for [obj, matrix] in self.objects:
			print "object: %s"%(obj.getName())
			file.write("AttributeBegin # %s\n"%obj.getName())
			file.write("\tTransform [%s %s %s %s  %s %s %s %s  %s %s %s %s  %s %s %s %s]\n"\
				%(matrix[0][0], matrix[0][1], matrix[0][2], matrix[0][3],\
				  matrix[1][0], matrix[1][1], matrix[1][2], matrix[1][3],\
				  matrix[2][0], matrix[2][1], matrix[2][2], matrix[2][3],\
		  		  matrix[3][0], matrix[3][1], matrix[3][2], matrix[3][3]))
			mesh_name = obj.getData(name_only=True)
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
				file.write("\tObjectInstance \"%s\"\n"%mesh_name)
			file.write("AttributeEnd\n\n")

	#-------------------------------------------------
	# exportPortals(self, file)
	# exports portals objects to the file
	#-------------------------------------------------
	def exportPortals(self, file):
		mesh_optimizing = True # getLuxProp(self.scene, "mesh_optimizing", False)
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

	#-------------------------------------------------
	# exportLights(self, file)
	# exports lights to the file
	#-------------------------------------------------
	def exportLights(self, file):
		for [obj, matrix] in self.lights:
			ltype = obj.getData(mesh=1).getType() # data
			if (ltype == Lamp.Types["Lamp"]) or (ltype == Lamp.Types["Spot"]):
				print "light: %s"%(obj.getName())
				file.write("TransformBegin # %s\n"%obj.getName())
				file.write("\tTransform [%s %s %s %s  %s %s %s %s  %s %s %s %s  %s %s %s %s]\n"\
					%(matrix[0][0], matrix[0][1], matrix[0][2], matrix[0][3],\
					  matrix[1][0], matrix[1][1], matrix[1][2], matrix[1][3],\
					  matrix[2][0], matrix[2][1], matrix[2][2], matrix[2][3],\
			  		  matrix[3][0], matrix[3][1], matrix[3][2], matrix[3][3]))
				col = obj.getData(mesh=1).col # data
				energy = obj.getData(mesh=1).energy # data
				if ltype == Lamp.Types["Lamp"]:
					file.write("LightSource \"point\"")
				if ltype == Lamp.Types["Spot"]:
					file.write("LightSource \"spot\" \"point from\" [0 0 0] \"point to\" [0 0 -1] \"float coneangle\" [%f] \"float conedeltaangle\" [%f]"\
						%(obj.getData(mesh=1).spotSize*0.5, obj.getData(mesh=1).spotSize*0.5*obj.getData(mesh=1).spotBlend)) # data
				file.write(" \"color I\" [%f %f %f]\n"%(col[0]*energy, col[1]*energy, col[2]*energy))
				file.write("TransformEnd # %s\n"%obj.getName())
				file.write("\n")



######################################################
# EXPORT
######################################################

def save_lux(filename, unindexedname):
	global meshlist, matnames, geom_filename, geom_pfilename, mat_filename, mat_pfilename

	print("Lux Render Export started...\n")
	time1 = Blender.sys.time()
	scn = Scene.GetCurrent()

	filepath = os.path.dirname(filename)
	filebase = os.path.splitext(os.path.basename(filename))[0]

	geom_filename = os.path.join(filepath, filebase + "-geom.lxo")
	geom_pfilename = filebase + "-geom.lxo"

	mat_filename = os.path.join(filepath, filebase + "-mat.lxm")
	mat_pfilename = filebase + "-mat.lxm"
	
	### Zuegs: initialization for export class
	export = luxExport(Blender.Scene.GetCurrent())

	# check if a light is present
	envtype = luxProp(scn, "env.type", "infinite").get()
	if envtype == "sunsky":
		sun = None
		for obj in scn.objects:
			if obj.getType() == "Lamp":
				if obj.getData(mesh=1).getType() == 1: # sun object # data
					sun = obj
	if not(export.analyseScene()) and not(envtype == "infinite") and not((envtype == "sunsky") and (sun != None)):
		print("ERROR: No light source found")
		Draw.PupMenu("ERROR: No light source found%t|OK%x1")
		return False


	if luxProp(scn, "lxs", "true").get()=="true":
		##### Determine/open files
		print("Exporting scene to '" + filename + "'...\n")
		file = open(filename, 'w')
		##### Write Header ######
		file.write("# Lux Render v0.1 Scene File\n")
		file.write("# Exported by LuxBlend_0.1_alpha-MatEditor\n")
		file.write("\n")
	
		##### Write camera ######
		camObj = scn.getCurrentCamera()

		if camObj:
			print "processing Camera..."
			matrix = camObj.getMatrix()
			pos = matrix[3]
			forwards = -matrix[2]
			target = pos + forwards
			up = matrix[1]
			file.write("LookAt %f %f %f %f %f %f %f %f %f\n" % ( pos[0], pos[1], pos[2], target[0], target[1], target[2], up[0], up[1], up[2] ))
			file.write(luxCamera(camObj.data, scn.getRenderingContext()))
			file.write("\n")
		file.write("\n")
	
		##### Write film ######
		file.write(luxFilm(scn))
		file.write("\n")

		##### Write Pixel Filter ######
		file.write(luxPixelFilter(scn))
		file.write("\n")
	
		##### Write Sampler ######
		file.write(luxSampler(scn))
		file.write("\n")
	
		##### Write Integrator ######
		file.write(luxSurfaceIntegrator(scn))
		file.write("\n")
		
		##### Write Acceleration ######
		file.write(luxAccelerator(scn))
		file.write("\n")	
	
		########## BEGIN World
		file.write("\n")
		file.write("WorldBegin\n")
	
		file.write("\n")
		
		##### Write World Background, Sunsky or Env map ######
		env = luxEnvironment(scn)
		if env != "":
			file.write("AttributeBegin\n")
			file.write(env)
			export.exportPortals(file)
			file.write("AttributeEnd\n")
			file.write("\n")	


		#### Write material & geometry file includes in scene file
		file.write("Include \"%s\"\n\n" %(mat_pfilename))
		file.write("Include \"%s\"\n\n" %(geom_pfilename))
		
		#### Write End Tag
		file.write("WorldEnd\n\n")
		file.close()
		
	if luxProp(scn, "lxm", "true").get()=="true":
		##### Write Material file #####
		print("Exporting materials to '" + mat_filename + "'...\n")
		mat_file = open(mat_filename, 'w')
		mat_file.write("")
		export.exportMaterials(mat_file)
		mat_file.write("")
		mat_file.close()
	
	if luxProp(scn, "lxo", "true").get()=="true":
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

	print("Finished.\n")
	del export

	time2 = Blender.sys.time()
	print("Processing time: %f\n" %(time2-time1))
	return True



#########################################################################
###	 LAUNCH LuxRender AND RENDER CURRENT SCENE (WINDOWS AND MACOS)
#########################################################################

def launchLux(filename):
	ostype = osys.platform
	#get blenders 'bpydata' directory
	datadir=Blender.Get("datadir")
	
	#open 'LuxWrapper.conf' and read the first line
#	f = open(datadir + '/LuxWrapper.conf', 'r+')
#	ic=f.readline()
#	f.close()

	scn = Scene.GetCurrent()
	ic = luxProp(scn, "lux", "").get()
	checkluxpath = luxProp(scn, "checkluxpath", True).get()
	if checkluxpath:
		if sys.exists(ic) != 1:
			Draw.PupMenu("Error: Lux renderer not found. Please set path on System page.%t|OK")
			return		
	threads = luxProp(scn, "threads", 1).get()
		
	if ostype == "win32":
		
#		# create 'LuxWrapper.cmd' and write two lines of code into it
#		f = open(datadir + "\LuxWrapper.cmd", 'w')
#		f.write("cd /d " + sys.dirname(ic) + "\n")
#		f.write("start /b /belownormal " + sys.basename(ic) + " %1 \n")
#		f.close()
		
#		# call external shell script to start Lux
#		cmd= "\"" + datadir + "\LuxWrapper.cmd " + filename + "\""

		cmd = "start /b /belownormal \"\" \"%s\" \"%s\" --threads=%d"%(ic, filename, threads)		

	if ostype == "darwin":
		
		#create 'LuxWrapper.cmd' and write two lines of code into it
		f = open(datadir + "/LuxWrapper.command", 'w')
		f.write("cd " + sys.dirname(ic) + "\n")
		f.write("./luxrender " + filename +"\n")  # todo: use the sys.basename(ic) here
		f.close()
		com = "chmod 775 " + datadir + "/LuxWrapper.command"
		os.system(com)
		
		cmd	= datadir + "/LuxWrapper.command"

	if ostype == "linux2":
		cmd = "(%s --threads=%d %s)&"%(ic, threads, filename)

	# call external shell script to start Lux	
	print("Running Luxrender:\n"+cmd)
	os.system(cmd)

#### SAVE ANIMATION ####	
def save_anim(filename):
	global MatSaved
	
	MatSaved = 0
	startF = Blender.Get('staframe')
	endF = Blender.Get('endframe')

	for i in range (startF, endF):
		Blender.Set('curframe', i)
		Blender.Redraw()
		frameindex = "-" + str(i) + ".lxs"
		indexedname = makename(filename, frameindex)
		unindexedname = filename
		save_lux(indexedname, unindexedname)
		MatSaved = 1

#### SAVE STILL (hackish...) ####
def save_still(filename):
	global MatSaved
	scn = Scene.GetCurrent()
	luxProp(scn, "filename", Blender.Get("filename")).set(filename)
	MatSaved = 0
	unindexedname = filename
	if save_lux(filename, unindexedname):
		if luxProp(scn, "run", "true").get() == "true":
			launchLux(filename)



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
evtPreviewMaterial = 93


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

	# quick previews (biased)
	presets['0A - Preview - Directlighting'] = {'pixelfilter.type':'gaussian','sampler.type':'lowdiscrepancy','sampler.lowdisc.pixelsampler':'lowdiscrepancy','sintegrator.type':'directlighting','sintegrator.dlighting.maxdepth':3 }
	presets['0B - Preview - Path Tracing'] = {'pixelfilter.type':'gaussian','sampler.type':'lowdiscrepancy','sampler.lowdisc.pixelsampler':'lowdiscrepancy','sintegrator.type':'path','sintegrator.path.maxdepth':3 }

	# final renderings
	presets['1A - Final - Path Tracing'] = {'pixelfilter.type':'mitchell','sampler.type':'lowdiscrepancy','sampler.lowdisc.pixelsampler':'lowdiscrepancy','sintegrator.type':'path','sintegrator.path.maxdepth':12 }
	presets['1B - Final - low MLT/Path Tracing (outdoor)'] = {'pixelfilter.type':'mitchell','sampler.type':'metropolis','sampler.metro.lmprob':0.4,'sampler.metro.maxrejects':128,'sintegrator.type':'path','sintegrator.path.maxdepth':12 }
	presets['1C - Final - medium MLT/Path Tracing (indoor) (recommended)'] = {'pixelfilter.type':'mitchell','sampler.type':'metropolis','sampler.metro.lmprob':0.25,'sampler.metro.maxrejects':128,'sintegrator.type':'path','sintegrator.path.maxdepth':12 }
	presets['1D - Final - high MLT/Path Tracing (complex)'] = {'pixelfilter.type':'mitchell','sampler.type':'metropolis','sampler.metro.lmprob':0.1,'sampler.metro.maxrejects':128,'sintegrator.type':'path','sintegrator.path.maxdepth':12 }
	presets['1E - Final - ERPT/Path Tracing'] = {'pixelfilter.type':'mitchell','sampler.type':'erpt','sintegrator.type':'path','sintegrator.path.maxdepth':12 }

	# empirical test/debugging reference renderings
	presets['2A - Reference - Path Tracing'] = {'pixelfilter.type':'mitchell','sampler.type':'random','sampler.random.pixelsampler':'random','sintegrator.type':'path','sintegrator.path.maxdepth':1024 }
	presets['2B - Reference - MLT/Path Tracing'] = {'pixelfilter.type':'mitchell','sampler.type':'metropolis','sampler.metro.lmprob':0.25,'sampler.metro.maxrejects':8192,'sintegrator.type':'path','sintegrator.path.maxdepth':1024 }


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

# class to access properties (for lux settings)
class luxProp:
	def __init__(self, obj, name, default):
		self.obj = obj
		self.name = name
		self.default = default
	def get(self):
		global usedproperties, luxdefaults
		if self.obj:
			try:
				value = self.obj.properties['luxblend'][self.name]
				usedproperties[self.name] = value
				return value
			except KeyError:
				if self.obj.__class__.__name__ == "Scene": # luxdefaults only for global setting
					try:
						value = luxdefaults[self.name]
						usedproperties[self.name] = value
						return value
					except KeyError:
						usedproperties[self.name] = self.default
						return self.default
				usedproperties[self.name] = self.default
				return self.default
		return None
	def set(self, value):
		global newluxdefaults
		if self.obj:
			if value is not None:
				try: self.obj.properties['luxblend'][self.name] = value
				except (KeyError, TypeError):
					self.obj.properties['luxblend'] = {}
					self.obj.properties['luxblend'][self.name] = value
			else:
				try: del self.obj.properties['luxblend'][self.name]
				except:	pass
			if self.obj.__class__.__name__ == "Scene": # luxdefaults only for global setting
				# value has changed, so this are user settings, remove preset reference
				if not(self.name in defaultsExclude):
					newluxdefaults[self.name] = value
					try: self.obj.properties['luxblend']['preset']=""
					except: pass
	def delete(self):
		if self.obj:
			try: del self.obj.properties['luxblend'][self.name]
			except:	pass
	def getRGB(self):
		l = self.get().split(" ")
		if len(l) != 3: l = self.default.split(" ")
		return (float(l[0]), float(l[1]), float(l[2]))
	def getRGC(self):
		col = self.getRGB()
		return "%f %f %f"%(rg(col[0]), rg(col[1]),rg(col[2]))
	def setRGB(self, value):
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
	def getRect(self, wu, hu):
		w = int(self.w * wu + self.xgap * (wu-1))
		h = int(self.h * hu + self.ygap * (hu-1))
		if self.x + w > self.xmax: self.newline()
		rect = [int(self.x), int(self.y-h), int(w), int(h)]
		self.x += int(w + self.xgap)
		if h+self.ygap > self.hmax: self.hmax = int(h+self.ygap)
		return rect
	def newline(self, title="", distance=0):
		self.x = 110
		self.y -= int(self.hmax + distance)
		self.hmax = 0
		BGL.glColor3f(0.9,0.9,0.9); BGL.glRasterPos2i(10,self.y-self.h+5); Draw.Text(title)
		

# lux parameter types
def luxOption(name, lux, options, caption, hint, gui, width=1.0):
	if gui:
		menustr = caption+": %t"
		for i, v in enumerate(options): menustr = "%s %%x%d|%s"%(v, i, menustr)
		try:
			i = options.index(lux.get())
		except ValueError:
			print "value %s not found in options list"%(lux.get())
			i = 0
		r = gui.getRect(width, 1)
		Draw.Menu(menustr, evtLuxGui, r[0], r[1], r[2], r[3], i, hint, lambda e,v: lux.set(options[v]))
	return " \"string %s\" [\"%s\"]"%(name, lux.get())

def luxIdentifier(name, lux, options, caption, hint, gui, width=1.0):
	if gui: gui.newline(caption+":", 8)
	luxOption(name, lux, options, caption, hint, gui, width)
	return "%s \"%s\""%(name, lux.get())

def luxFloat(name, lux, min, max, caption, hint, gui, width=1.0):
	if gui:
		r = gui.getRect(width, 1)
		Draw.Number(caption+": ", evtLuxGui, r[0], r[1], r[2], r[3], float(lux.get()), min, max, hint, lambda e,v: lux.set(v))
	return " \"float %s\" [%f]"%(name, lux.get())

def luxInt(name, lux, min, max, caption, hint, gui, width=1.0):
	if gui:
		r = gui.getRect(width, 1)
		Draw.Number(caption+": ", evtLuxGui, r[0], r[1], r[2], r[3], int(lux.get()), min, max, hint, lambda e,v: lux.set(v))
	return " \"integer %s\" [%d]"%(name, lux.get())

def luxBool(name, lux, caption, hint, gui, width=1.0):
	if gui:
		r = gui.getRect(width, 1)
		Draw.Toggle(caption, evtLuxGui, r[0], r[1], r[2], r[3], lux.get()=="true", hint, lambda e,v: lux.set(["false","true"][bool(v)]))
	return " \"bool %s\" [\"%s\"]"%(name, lux.get())

def luxString(name, lux, caption, hint, gui, width=1.0):
	if gui:
		r = gui.getRect(width, 1)
		Draw.String(caption+": ", evtLuxGui, r[0], r[1], r[2], r[3], lux.get(), 250, hint, lambda e,v: lux.set(v))
	return " \"string %s\" [\"%s\"]"%(name, luxstr(lux.get()))

def luxFile(name, lux, caption, hint, gui, width=1.0):
	if gui:
		r = gui.getRect(width, 1)
		Draw.String(caption+": ", evtLuxGui, r[0], r[1], r[2]-r[3]-2, r[3], lux.get(), 250, hint, lambda e,v: lux.set(v))
		Draw.Button("...", 0, r[0]+r[2]-r[3], r[1], r[3], r[3], "click to open file selector", lambda e,v:Window.FileSelector(lambda s:lux.set(s), "Select %s"%(caption), lux.get()))
	return " \"string %s\" [\"%s\"]"%(name, luxstr(lux.get()))

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
		Draw.Number("R:", evtLuxGui, r[0]+r[3], r[1], w, r[3], rgb[0], 0.0, m, "red", lambda e,v: lux.setRGB((v,rgb[1],rgb[2])))
		Draw.Number("G:", evtLuxGui, r[0]+r[3]+w, r[1], w, r[3], rgb[1], 0.0, m, "green", lambda e,v: lux.setRGB((rgb[0],v,rgb[2])))
		Draw.Number("B:", evtLuxGui, r[0]+r[3]+2*w, r[1], w, r[3], rgb[2], 0.0, m, "blue", lambda e,v: lux.setRGB((rgb[0],rgb[1],v)))
		if max > 1.0:
			Draw.Number("s:", evtLuxGui, r[0]+r[3]+3*w, r[1], w, r[3], scale, 0.0, max, "color scale", lambda e,v: lux.setRGB((rgb[0]*v,rgb[1]*v,rgb[2]*v)))
	if max <= 1.0:
		return " \"color %s\" [%s]"%(name, lux.getRGC())
	return " \"color %s\" [%s]"%(name, lux.get())



# lux individual identifiers
def luxCamera(cam, context, gui=None):
	str = ""
	if cam:
		camtype = luxProp(cam, "camera.type", "perspective")
		str = luxIdentifier("Camera", camtype, ["perspective","orthographic","environment","realistic"], "CAMERA", "select camera type", gui)
		scale = 1.0
		if camtype.get() == "perspective":
			str += luxFloat("fov", luxAttr(cam, "angle"), 8.0, 170.0, "fov", "camera field-of-view angle", gui)
		if camtype.get() == "orthographic" :
			str += luxFloat("scale", luxAttr(cam, "scale"), 0.01, 1000.0, "scale", "orthographic camera scale", gui)
			scale = cam.scale / 2
		if camtype.get() == "realistic":
			fov = luxAttr(cam, "angle")
			luxFloat("fov", fov, 8.0, 170.0, "fov", "camera field-of-view angle", gui)
			if gui: gui.newline()
			str += luxFile("specfile", luxProp(cam, "camera.realistic.specfile", ""), "spec-file", "", gui, 1.0)
#			if gui: gui.newline()
# auto calc		str += luxFloat("filmdistance", luxProp(cam, "camera.realistic.filmdistance", 70.0), 0.1, 1000.0, "film-dist", "film-distance [mm]", gui)
			filmdiag = luxProp(cam, "camera.realistic.filmdiag", 35.0)
			str += luxFloat("filmdiag", filmdiag, 0.1, 1000.0, "film-diag", "[mm]", gui)
			if gui: gui.newline()
			fstop = luxProp(cam, "camera.realistic.fstop", 1.0)
			luxFloat("aperture_diameter", fstop, 0.0, 100.0, "f-stop", "", gui)
			dofdist = luxAttr(cam, "dofDist")
			luxFloat("focaldistance", dofdist, 0.0, 10000.0, "distance", "Distance from the camera at which objects will be in focus. Has no effect if Lens Radius is 0", gui)
			if gui:
				Draw.Button("S", evtLuxGui, gui.x, gui.y-gui.h, gui.h, gui.h, "focus selected object", lambda e,v:setFocus("S"))
				Draw.Button("C", evtLuxGui, gui.x+gui.h, gui.y-gui.h, gui.h, gui.h, "focus cursor", lambda e,v:setFocus("C"))
			focal = filmdiag.get()*0.001 / math.tan(fov.get() * math.pi / 360.0) / 2.0
			print "calculated focal length: %f mm"%(focal * 1000.0)
			aperture_diameter = focal / fstop.get()
			print "calculated aperture diameter: %f mm"%(aperture_diameter * 1000.0)
			str += " \"float aperture_diameter\" [%f]"%(aperture_diameter*1000.0)
			filmdistance = dofdist.get() * focal / (dofdist.get() - focal)
			print "calculated film distance: %f mm"%(filmdistance * 1000.0)
			str += " \"float filmdistance\" [%f]"%(filmdistance*1000.0)
		if gui: gui.newline("  Clipping:")
		str += luxFloat("hither", luxAttr(cam, "clipStart"), 0.0, 100.0, "hither", "near clip distance", gui)
		str += luxFloat("yon", luxAttr(cam, "clipEnd"), 1.0, 10000.0, "yon", "far clip distance", gui)
		if camtype.get() in ["perspective", "orthographic"]:
			if gui: gui.newline("  DOF:")
			str += luxFloat("lensradius", luxProp(cam, "camera.lensradius", 0.0), 0.0, 10.0, "lens-radius", "Defines the lens radius. Values higher than 0. enable DOF and control the amount", gui)
			dofdist = luxAttr(cam, "dofDist")
			str += luxFloat("focaldistance", dofdist, 0.0, 10000.0, "distance", "Distance from the camera at which objects will be in focus. Has no effect if Lens Radius is 0", gui)
			if gui:
				Draw.Button("S", evtLuxGui, gui.x, gui.y-gui.h, gui.h, gui.h, "focus selected object", lambda e,v:setFocus("S"))
				Draw.Button("C", evtLuxGui, gui.x+gui.h, gui.y-gui.h, gui.h, gui.h, "focus cursor", lambda e,v:setFocus("C"))
		if gui: gui.newline("  Shutter:")
		str += luxFloat("shutteropen", luxProp(cam, "camera.shutteropen", 0.0), 0.0, 100.0, "open", "time in seconds when shutter opens", gui)
		str += luxFloat("shutterclose", luxProp(cam, "camera.shutterclose", 1.0), 0.0, 100.0, "close", "time in seconds when shutter closes", gui)
		if camtype.get() in ["perspective", "orthographic"]:
			if gui: gui.newline("  Shift:")
			luxFloat("X", luxAttr(cam, "shiftX"), -2.0, 2.0, "X", "horizontal lens shift", gui)
			luxFloat("Y", luxAttr(cam, "shiftY"), -2.0, 2.0, "Y", "vertical lens shift", gui)
			if context:
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
				str += " \"float screenwindow\" [%f %f %f %f]"%(screenwindow[0], screenwindow[1], screenwindow[2], screenwindow[3])
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
				luxInt("xresolution", luxAttr(context, "sizeX"), 0, 4096, "X", "width of the render", gui, 0.666)
				luxInt("yresolution", luxAttr(context, "sizeY"), 0, 4096, "Y", "height of the render", gui, 0.666)
				scale = luxProp(scn, "film.scale", "100 %")
				luxOption("", scale, ["100 %", "75 %", "50 %", "25 %"], "scale", "scale resolution", gui, 0.666)
				scale = int(scale.get()[:-1])
	# render region option
				if context.borderRender:
					(x1,y1,x2,y2) = context.border
					if (x1==x2) and (y1==y2): print "WARNING: empty render-region, use SHIFT-B to set render region in Blender."
					str += " \"integer xresolution\" [%d] \"integer yresolution\" [%d]"%(luxAttr(context, "sizeX").get()*scale/100*(x2-x1), luxAttr(context, "sizeY").get()*scale/100*(y2-y1))
				else:
					str += " \"integer xresolution\" [%d] \"integer yresolution\" [%d]"%(luxAttr(context, "sizeX").get()*scale/100, luxAttr(context, "sizeY").get()*scale/100)
	
			if gui: gui.newline("  Tonemap:")
			str += luxFloat("reinhard_prescale", luxProp(scn, "film.reinhard.prescale", 1.0), 0.0, 10.0, "pre-scale", "Pre Scale: See Lux Manual ;)", gui)
			str += luxFloat("reinhard_postscale", luxProp(scn, "film.reinhard.postscale", 1.0), 0.0, 10.0, "post-scale", "Post Scale: See Lux Manual ;)", gui)
			str += luxFloat("reinhard_burn", luxProp(scn, "film.reinhard.burn", 6.0), 0.1, 12.0, "burn", "12.0: no burn out, 0.1 lot of burn out", gui)
			if gui: gui.newline("  Gamma:")
			str += luxFloat("gamma", luxProp(scn, "film.gamma", 2.2), 0.0, 6.0, "gamma", "Output and RGC Gamma", gui)
			if gui: gui.newline("  Display:")
			str += luxInt("displayinterval", luxProp(scn, "film.displayinterval", 12), 5, 3600, "interval", "Set display Interval (seconds)", gui)
			if gui: gui.newline("  Write:")
			str += luxInt("writeinterval", luxProp(scn, "film.writeinterval", 120), 5, 3600, "interval", "Set display Interval (seconds)", gui)
			if gui: gui.newline("  Formats:")
			fn = luxProp(scn, "filename", Blender.Get("filename")).get();
			if gui: gui.newline("")
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
	return str


def luxPixelFilter(scn, gui=None):
	str = ""
	if scn:
		filtertype = luxProp(scn, "pixelfilter.type", "mitchell")
		str = luxIdentifier("PixelFilter", filtertype, ["box", "gaussian", "mitchell", "sinc", "triangle"], "FILTER", "select pixel filter type", gui)
		if filtertype.get() == "box":
			if gui: gui.newline()
			str += luxFloat("xwidth", luxProp(scn, "pixelfilter.box.xwidth", 0.5), 0.0, 10.0, "x-width", "Width of the filter in the x direction", gui)
			str += luxFloat("ywidth", luxProp(scn, "pixelfilter.box.ywidth", 0.5), 0.0, 10.0, "y-width", "Width of the filter in the y direction", gui)
		if filtertype.get() == "gaussian":
			str += luxFloat("alpha", luxProp(scn, "pixelfilter.gaussian.alpha", 2.0), 0.0, 10.0, "alpha", "Gaussian rate of falloff. Lower values give blurrier images", gui)
			if gui: gui.newline()
			str += luxFloat("xwidth", luxProp(scn, "pixelfilter.gaussian.xwidth", 2.0), 0.0, 10.0, "x-width", "Width of the filter in the x direction", gui)
			str += luxFloat("ywidth", luxProp(scn, "pixelfilter.gaussian.ywidth", 2.0), 0.0, 10.0, "y-width", "Width of the filter in the y direction", gui)
		if filtertype.get() == "mitchell":
			if gui: gui.newline()
			str += luxFloat("B", luxProp(scn, "pixelfilter.mitchell.B", 0.3333), 0.0, 1.0, "B", "Specify the shape of the Mitchell filter. Often best result is when B + 2C = 1", gui)
			str += luxFloat("C", luxProp(scn, "pixelfilter.mitchell.C", 0.3333), 0.0, 1.0, "C", "Specify the shape of the Mitchell filter. Often best result is when B + 2C = 1", gui)
			if gui: gui.newline()
			str += luxFloat("xwidth", luxProp(scn, "pixelfilter.mitchell.xwidth", 2.0), 0.0, 10.0, "x-width", "Width of the filter in the x direction", gui)
			str += luxFloat("ywidth", luxProp(scn, "pixelfilter.mitchell.ywidth", 2.0), 0.0, 10.0, "y-width", "Width of the filter in the y direction", gui)
		if filtertype.get() == "sinc":
			str = luxFloat("tau", luxProp(scn, "pixelfilter.sinc.tau", 3.0), 0.0, 10.0, "tau", "Permitted number of cycles of the sinc function before it is clamped to zero", gui)
			if gui: gui.newline()
			str += luxFloat("xwidth", luxProp(scn, "pixelfilter.sinc.xwidth", 4.0), 0.0, 10.0, "x-width", "Width of the filter in the x direction", gui)
			str += luxFloat("ywidth", luxProp(scn, "pixelfilter.sinc.ywidth", 4.0), 0.0, 10.0, "y-width", "Width of the filter in the y direction", gui)
		if filtertype.get() == "triangle":
			if gui: gui.newline()
			str += luxFloat("xwidth", luxProp(scn, "pixelfilter.triangle.xwidth", 2.0), 0.0, 10.0, "x-width", "Width of the filter in the x direction", gui)
			str += luxFloat("ywidth", luxProp(scn, "pixelfilter.triangle.ywidth", 2.0), 0.0, 10.0, "y-width", "Width of the filter in the y direction", gui)
	return str			

def luxSampler(scn, gui=None):
	str = ""
	if scn:
		samplertype = luxProp(scn, "sampler.type", "lowdiscrepancy")
		str = luxIdentifier("Sampler", samplertype, ["metropolis", "erpt", "lowdiscrepancy", "random", "halton"], "SAMPLER", "select sampler type", gui)
		if samplertype.get() == "metropolis":
			str += luxInt("initsamples", luxProp(scn, "sampler.metro.initsamples", 100000), 1, 1000000, "initsamples", "", gui)
			if gui: gui.newline()
			str += luxInt("maxconsecrejects", luxProp(scn, "sampler.metro.maxrejects", 256), 0, 32768, "max.rejects", "number of consecutive rejects before a new mutation is forced", gui)
			str += luxFloat("largemutationprob", luxProp(scn, "sampler.metro.lmprob", 0.25), 0.0, 1.0, "LM.prob.", "probability of generation a large sample (mutation)", gui)
			if gui: gui.newline()
			str += luxBool("usevariance",luxProp(scn, "sampler.metro.usevariance", "false"), "usevariance", "Accept based on variance", gui)
		if samplertype.get() == "erpt":
			str += luxInt("initsamples", luxProp(scn, "sampler.erpt.initsamples", 100000), 1, 1000000, "initsamples", "", gui)
			if gui: gui.newline()
			str += luxInt("erpt", luxProp(scn, "sampler.erpt.chainlength", 512), 1, 32768, "chainlength", "The number of mutations from a given seed", gui)
		if samplertype.get() == "lowdiscrepancy":
			str += luxOption("pixelsampler", luxProp(scn, "sampler.lowdisc.pixelsampler", "lowdiscrepancy"), ["random", "vegas","lowdiscrepancy"], "pixel-sampler", "select pixel-sampler", gui)
			if gui: gui.newline()
			str += luxInt("pixelsamples", luxProp(scn, "sampler.lowdisc.pixelsamples", 4), 1, 512, "samples", "Average number of samples taken per pixel. More samples create a higher quality image at the cost of render time", gui)
		if samplertype.get() == "random":
			str += luxOption("pixelsampler", luxProp(scn, "sampler.random.pixelsampler", "vegas"), ["random", "vegas","lowdiscrepancy"], "pixel-sampler", "select pixel-sampler", gui)
			if gui: gui.newline()
			str += luxInt("xsamples", luxProp(scn, "sampler.random.xsamples", 2), 1, 512, "xsamples", "Allows you to specify how many samples per pixel are taking in the x direction", gui)
			str += luxInt("ysamples", luxProp(scn, "sampler.random.ysamples", 2), 1, 512, "ysamples", "Allows you to specify how many samples per pixel are taking in the y direction", gui)
		if samplertype.get() == "halton":
			str += luxOption("pixelsampler", luxProp(scn, "sampler.halton.pixelsampler", "lowdiscrepancy"), ["random", "vegas","lowdiscrepancy"], "pixel-sampler", "select pixel-sampler", gui)
			if gui: gui.newline()
			str += luxInt("pixelsamples", luxProp(scn, "sampler.halton.pixelsamples", 4), 1, 512, "samples", "Average number of samples taken per pixel. More samples create a higher quality image at the cost of render time", gui)
	return str			

def luxSurfaceIntegrator(scn, gui=None):
	str = ""
	if scn:
		integratortype = luxProp(scn, "sintegrator.type", "path")
		str = luxIdentifier("SurfaceIntegrator", integratortype, ["directlighting", "path", "path2", "bidirectional"], "INTEGRATOR", "select surface integrator type", gui)
		if integratortype.get() == "directlighting":
			str += luxInt("maxdepth", luxProp(scn, "sintegrator.dlighting.maxdepth", 5), 0, 2048, "max-depth", "The maximum recursion depth for ray casting", gui)
			if gui: gui.newline()
			str += luxOption("strategy", luxProp(scn, "sintegrator.dlighting.strategy", "all"), ["one", "all", "weighted"], "strategy", "select directlighting strategy", gui)
		if integratortype.get() == "path":
			str += luxInt("maxdepth", luxProp(scn, "sintegrator.path.maxdepth", 12), 0, 2048, "maxdepth", "The maximum recursion depth for ray casting", gui)
		if integratortype.get() == "path2":
			str += luxInt("maxdepth", luxProp(scn, "sintegrator.path2.maxdepth", 12), 0, 2048, "maxdepth", "The maximum recursion depth for ray casting", gui)
		if integratortype.get() == "bidirectional":
			str += luxInt("eyedepth", luxProp(scn, "sintegrator.bidirectional.eyedepth", 8), 0, 2048, "eyedepth", "The maximum recursion depth for ray casting", gui)
			if gui: gui.newline()
			str += luxInt("lightdepth", luxProp(scn, "sintegrator.bidirectional.lightdepth", 8), 0, 2048, "lightdepth", "The maximum recursion depth for light ray casting", gui)
	return str

def luxEnvironment(scn, gui=None):
	str = ""
	if scn:
		envtype = luxProp(scn, "env.type", "infinite")
		lsstr = luxIdentifier("LightSource", envtype, ["none", "infinite", "sunsky"], "ENVIRONMENT", "select environment light type", gui)
		if gui: gui.newline()
		str = ""
		if envtype.get() != "none":
			if envtype.get() in ["infinite", "sunsky"]:
				rot = luxProp(scn, "env.rotation", 0.0)
				luxFloat("rotation", rot, 0.0, 360.0, "rotation", "environment rotation", gui)
				if rot.get() != 0:
					str += "\tRotate %d 0 0 1\n"%(rot.get())
			str += "\t"+lsstr
			str += luxInt("nsamples", luxProp(scn, "env.samples", 1), 1, 100, "samples", "number of samples", gui)
			if gui: gui.newline()
			if envtype.get() == "infinite":
				map = luxProp(scn, "env.infinite.mapname", "")
				mapstr = luxFile("mapname", map, "map-file", "filename of the environment map", gui, 2.0)
				if map.get() != "":
					str += mapstr
				else:
					worldcolor = Blender.World.Get('World').getHor()
					str += " \"color L\" [%g %g %g]\n" %(worldcolor[0], worldcolor[1], worldcolor[2])
			if envtype.get() == "sunsky":
				sun = None
				for obj in scn.objects:
					if obj.getType() == "Lamp":
						if obj.getData(mesh=1).getType() == 1: # sun object # data
							sun = obj
				if sun:
					invmatrix = Mathutils.Matrix(sun.getInverseMatrix())
					str += " \"vector sundir\" [%f %f %f]\n" %(invmatrix[0][2], invmatrix[1][2], invmatrix[2][2])
					str += luxFloat("gain", luxProp(scn, "env.sunsky.gain", 1.0), 0.0, 100.0, "gain", "Sky gain", gui)
					str += luxFloat("turbidity", luxProp(scn, "env.sunsky.turbidity", 2.0), 1.5, 5.0, "turbidity", "Sky turbidity", gui)
					if gui: gui.newline()
					str += luxFloat("relsize", luxProp(scn, "env.sunsky.relisze", 1.0), 0.0, 100.0, "rel.size", "relative sun size", gui)
				else:
					if gui:
						gui.newline(); r = gui.getRect(2,1); BGL.glRasterPos2i(r[0],r[1]+5) 
						Draw.Text("create a blender Sun Lamp")
			str += "\n"
	return str

def luxAccelerator(scn, gui=None):
	str = ""
	if scn:
		acceltype = luxProp(scn, "accelerator.type", "kdtree")
		str = luxIdentifier("Accelerator", acceltype, ["kdtree", "grid"], "ACCELERATOR", "select accelerator type", gui)
		if acceltype.get() == "kdtree":
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
		if gui: gui.newline("SYSTEM:", 10)
		luxFile("filename", luxProp(scn, "lux", ""), "lux-file", "filename and path of the lux executable", gui, 2.0)
		if gui: gui.newline()
		luxFile("datadir", luxProp(scn, "datadir", ""), "default out dir", "default.lxs save path", gui, 2.0)
		if gui: gui.newline()
		luxInt("threads", luxProp(scn, "threads", 1), 1, 100, "threads", "number of threads used for rendering", gui)
		if gui: gui.newline()
		luxBool("RGC", luxProp(scn, "RGC", "true"), "RGC", "use reverse gamma correction", gui)
		luxBool("ColClamp", luxProp(scn, "colorclamp", "true"), "ColClamp", "clamp all colors to 0.0-0.9", gui)




# lux textures
def luxSpectrumTexture(name, key, default, max, caption, hint, mat, gui):
	str = ""
	texname = "%s--%s"%(mat.getName(), name)
	if gui: gui.newline("  "+caption)
	strvalue = luxRGB("value", luxProp(mat, key+".value", default), max, "", "", gui, 2.0)
	map = luxProp(mat, key+".map", False)
	if gui:
		Draw.Toggle("M", evtLuxGui, gui.x, gui.y-gui.h, gui.h, gui.h, map.get()=="true", "use file mapping", lambda e,v:map.set(["false","true"][bool(v)]))
	if map.get()=="true":
		if gui: gui.newline("", -2)
		mapfile = luxProp(mat, key+".mapfile", "")
		strmap = luxFile("filename", mapfile, "map", "texture file path", gui, 2.0)
		str = "Texture \"%s.map\" \"color\" \"imagemap\"%s \"float vscale\" [-1.0]\n"%(texname, strmap)
		str += "Texture \"%s.value\" \"color\" \"constant\"%s\n"%(texname, strvalue)
		str += "Texture \"%s\" \"color\" \"scale\" \"texture tex1\" [\"%s.value\"] \"texture tex2\" [\"%s.map\"]\n"%(texname, texname, texname)
	else:
		str = "Texture \"%s\" \"color\" \"constant\"%s\n"%(texname, strvalue)
	return (str," \"texture %s\" [\"%s\"]"%(name, texname))

def luxFloatTexture(name, key, default, min, max, caption, hint, mat, gui):
	str = ""
	texname = "%s--%s"%(mat.getName(), name)
	if gui: gui.newline("  "+caption)
	strvalue = luxFloat("value", luxProp(mat, key+".value", default), min, max, "", "", gui, 0.75)
	map = luxProp(mat, key+".map", "")
	strmap = luxFile("filename", map, "map", "texture file path", gui, 1.25)
	if map.get() == "":
		str = "Texture \"%s\" \"float\" \"constant\"%s\n"%(texname, strvalue)
	else:
		str = "Texture \"%s.map\" \"float\" \"imagemap\"%s \"float vscale\" [-1.0]\n"%(texname, strmap)
		str += "Texture \"%s.value\" \"float\" \"constant\"%s\n"%(texname, strvalue)
		str += "Texture \"%s\" \"float\" \"scale\" \"texture tex1\" [\"%s.value\"] \"texture tex2\" [\"%s.map\"]\n"%(texname, texname, texname)
	return (str, " \"texture %s\" [\"%s\"]"%(name, texname))



def luxMaterial(mat, gui=None):
	def c(t1, t2):
		return (t1[0]+t2[0], t1[1]+t2[1])
	str = ""
	if mat:
		mattype = luxProp(mat, "type", "matte")
		link = luxIdentifier("Material", mattype, ["light","portal","carpaint","glass","matte","mattetranslucent","metal","mirror","plastic","roughglass","shinymetal","substrate"], "  TYPE", "select material type", gui)
		if gui: gui.newline()
		if mattype.get() == "light":
			link = "AreaLightSource \"area\""
#			(str,link) = c((str,link), luxSpectrumTexture("L", "light.l", "1.0 1.0 1.0", 100.0, "color", "", mat, gui))
			if gui: gui.newline("  color")
			link += luxRGB("L", luxProp(mat, "light.l", "1.0 1.0 1.0"), 100.0, "L", "", gui)
			if gui: gui.newline("")
			link += luxInt("nsamples", luxProp(mat, "light.nsamples", 1), 1, 100, "samples", "number of samples", gui)
		if mattype.get() == "carpaint":
			if gui: gui.newline("  name:")
			carname = luxProp(mat, "carpaint.name", "white")
			cars = ["","ford f8","polaris silber","opel titan","bmw339","2k acrylack","white","blue","blue matte"]
			carlink = luxOption("name", carname, cars, "name", "", gui)
			if carname.get() == "":
				(str,link) = c((str,link), luxSpectrumTexture("Kd", "carpaint.kd", "1.0 1.0 1.0", 1.0, "diffuse", "", mat, gui))
				(str,link) = c((str,link), luxSpectrumTexture("Ks1", "carpaint.ks1", "1.0 1.0 1.0", 1.0, "specular1", "", mat, gui))
				(str,link) = c((str,link), luxSpectrumTexture("Ks2", "carpaint.ks2", "1.0 1.0 1.0", 1.0, "specular2", "", mat, gui))
				(str,link) = c((str,link), luxSpectrumTexture("Ks3", "carpaint.ks3", "1.0 1.0 1.0", 1.0, "specular3", "", mat, gui))
				(str,link) = c((str,link), luxFloatTexture("R1", "carpaint.r1", 1.0, 0.0, 1.0, "R1", "", mat, gui))
				(str,link) = c((str,link), luxFloatTexture("R2", "carpaint.r2", 1.0, 0.0, 1.0, "R2", "", mat, gui))
				(str,link) = c((str,link), luxFloatTexture("R3", "carpaint.r3", 1.0, 0.0, 1.0, "R3", "", mat, gui))
				(str,link) = c((str,link), luxFloatTexture("M1", "carpaint.m1", 1.0, 0.0, 1.0, "M1", "", mat, gui))
				(str,link) = c((str,link), luxFloatTexture("M2", "carpaint.m2", 1.0, 0.0, 1.0, "M2", "", mat, gui))
				(str,link) = c((str,link), luxFloatTexture("M3", "carpaint.m3", 1.0, 0.0, 1.0, "M3", "", mat, gui))
			else: link += carlink
			(str,link) = c((str,link), luxFloatTexture("bumpmap", "metal.bumpmap", 0.0, 0.0, 1.0, "bumpmap", "", mat, gui))
# obsolet
#		if mattype.get() == "clay":
#			(str,link) = c((str,link), luxFloatTexture("bumpmap", "clay.bumpmap", 0.0, 0.0, 1.0, "bumpmap", "", mat, gui))
# obsolet
#		if mattype.get() == "felt":
#			(str,link) = c((str,link), luxFloatTexture("bumpmap", "felt.bumpmap", 0.0, 0.0, 1.0, "bumpmap", "", mat, gui))
		if mattype.get() == "glass":
			(str,link) = c((str,link), luxSpectrumTexture("Kr", "glass.kr", "1.0 1.0 1.0", 1.0, "reflection", "", mat, gui))
			(str,link) = c((str,link), luxSpectrumTexture("Kt", "glass.kt", "1.0 1.0 1.0", 1.0, "transmission", "", mat, gui))
			(str,link) = c((str,link), luxFloatTexture("index", "glass.index", 1.5, 0.0, 100.0, "index", "", mat, gui))
			(str,link) = c((str,link), luxFloatTexture("cauchyb", "glass.cauchyb", 0.0, 0.0, 1.0, "cauchyb", "", mat, gui))
			(str,link) = c((str,link), luxFloatTexture("bumpmap", "glass.bumpmap", 0.0, 0.0, 1.0, "bumpmap", "", mat, gui))
		if mattype.get() == "matte":
			(str,link) = c((str,link), luxSpectrumTexture("Kd", "matte.kd", "1.0 1.0 1.0", 1.0, "diffuse", "", mat, gui))
			(str,link) = c((str,link), luxFloatTexture("sigma", "matte.sigma", 0.0, 0.0, 100.0, "sigma", "", mat, gui))
			(str,link) = c((str,link), luxFloatTexture("bumpmap", "matte.bumpmap", 0.0, 0.0, 1.0, "bumpmap", "", mat, gui))
		if mattype.get() == "mattetranslucent":
			(str,link) = c((str,link), luxSpectrumTexture("Kr", "matte.kr", "1.0 1.0 1.0", 1.0, "reflection", "", mat, gui))
			(str,link) = c((str,link), luxSpectrumTexture("Kt", "matte.kt", "1.0 1.0 1.0", 1.0, "transmission", "", mat, gui))
			(str,link) = c((str,link), luxFloatTexture("sigma", "matte.sigma", 0.0, 0.0, 100.0, "sigma", "", mat, gui))
			(str,link) = c((str,link), luxFloatTexture("bumpmap", "matte.bumpmap", 0.0, 0.0, 1.0, "bumpmap", "", mat, gui))
		if mattype.get() == "metal":
			if gui: gui.newline("  name:")
			metalname = luxProp(mat, "metal.name", "")
			metals = ["","aluminium","amorphous carbon","silver","gold","cobalt","copper","chromium","lithium","mercury","nickel","potassium","platinum","iridium","silicon","amorphous silicon","sodium","rhodium","tungsten","vanadium"]
			if not(metalname.get() in metals):
				metals.append(metalname.get())
			metallink = luxOption("name", metalname, metals, "name", "", gui)
			if gui: Draw.Button("...", evtLuxGui, gui.x, gui.y-gui.h, gui.h, gui.h, "click to select a nk file",lambda e,v:Window.FileSelector(lambda s:metalname.set(s), "Select nk file"))
			if metalname.get() == "":
				(str,link) = c((str,link), luxSpectrumTexture("n", "metal.n", "1.226973 0.930951 0.600745", 10.0, "n", "", mat, gui))
				(str,link) = c((str,link), luxSpectrumTexture("k", "metal.k", "7.284448 6.535680 5.363405", 10.0, "k", "", mat, gui))
			else: link += metallink
			(str,link) = c((str,link), luxFloatTexture("roughness", "metal.roughness", 0.1, 0.0, 1.0, "roughness", "", mat, gui))
			(str,link) = c((str,link), luxFloatTexture("bumpmap", "metal.bumpmap", 0.0, 0.0, 1.0, "bumpmap", "", mat, gui))
		if mattype.get() == "mirror":
			(str,link) = c((str,link), luxSpectrumTexture("Kr", "mirror.kr", "1.0 1.0 1.0", 1.0, "reflection", "", mat, gui))
			(str,link) = c((str,link), luxFloatTexture("bumpmap", "mirror.bumpmap", 0.0, 0.0, 1.0, "bumpmap", "", mat, gui))
		if mattype.get() == "plastic":
			(str,link) = c((str,link), luxSpectrumTexture("Kd", "plastic.kd", "1.0 1.0 1.0", 1.0, "diffuse", "", mat, gui))
			(str,link) = c((str,link), luxSpectrumTexture("Ks", "plastic.ks", "1.0 1.0 1.0", 1.0, "specular", "", mat, gui))
			(str,link) = c((str,link), luxFloatTexture("roughness", "plastic.roughness", 0.1, 0.0, 1.0, "roughness", "", mat, gui))
			(str,link) = c((str,link), luxFloatTexture("bumpmap", "plastic.bumpmap", 0.0, 0.0, 1.0, "bumpmap", "", mat, gui))
# obsolet
#		if mattype.get() == "primer":
#			(str,link) = c((str,link), luxFloatTexture("bumpmap", "primer.bumpmap", 0.0, 0.0, 1.0, "bumpmap", "", mat, gui))
		if mattype.get() == "roughglass":
			(str,link) = c((str,link), luxSpectrumTexture("Kr", "roughglass.kr", "1.0 1.0 1.0", 1.0, "reflection", "", mat, gui))
			(str,link) = c((str,link), luxSpectrumTexture("Kt", "roughglass.kt", "1.0 1.0 1.0", 1.0, "transmission", "", mat, gui))
			anisotropic = luxProp(mat, "roughglass.anisotropic", False)
			if gui:
				gui.newline("")
				Draw.Toggle("A", evtLuxGui, gui.x-gui.h, gui.y-gui.h, gui.h, gui.h, anisotropic.get()=="true", "anisotropic roughness", lambda e,v:anisotropic.set(["false","true"][bool(v)]))
			if anisotropic.get()=="true":
				(str,link) = c((str,link), luxFloatTexture("uroughness", "roughglass.uroughness", 0.1, 0.0, 1.0, "u-roughness", "", mat, gui))
				(str,link) = c((str,link), luxFloatTexture("vroughness", "roughglass.vroughness", 0.1, 0.0, 1.0, "v-roughness", "", mat, gui))
			else:
				(str,link) = c((str,link), luxFloatTexture("uroughness", "roughglass.uroughness", 0.1, 0.0, 1.0, "roughness", "", mat, gui))
				if not(gui):
					(str,link) = c((str,link), luxFloatTexture("vroughness", "roughglass.uroughness", 0.1, 0.0, 1.0, "v-roughness", "", mat, gui))
			(str,link) = c((str,link), luxFloatTexture("index", "roughglass.index", 1.5, 0.0, 100.0, "index", "", mat, gui))
			(str,link) = c((str,link), luxFloatTexture("cauchyb", "roughglass.cauchyb", 0.0, 0.0, 1.0, "cauchyb", "", mat, gui))
			(str,link) = c((str,link), luxFloatTexture("bumpmap", "roughglass.bumpmap", 0.0, 0.0, 1.0, "bumpmap", "", mat, gui))
		if mattype.get() == "shinymetal":
			(str,link) = c((str,link), luxSpectrumTexture("Kr", "shinymetal.kr", "1.0 1.0 1.0", 1.0, "reflection", "", mat, gui))
			(str,link) = c((str,link), luxSpectrumTexture("Ks", "shinymetal.ks", "1.0 1.0 1.0", 1.0, "specular", "", mat, gui))
			(str,link) = c((str,link), luxFloatTexture("roughness", "shinymetal.roughness", 0.1, 0.0, 1.0, "roughness", "", mat, gui))
			(str,link) = c((str,link), luxFloatTexture("bumpmap", "shinymetal.bumpmap", 0.0, 0.0, 1.0, "bumpmap", "", mat, gui))
		if mattype.get() == "substrate":
			(str,link) = c((str,link), luxSpectrumTexture("Kd", "substrade.kd", "1.0 1.0 1.0", 1.0, "diffuse", "", mat, gui))
			(str,link) = c((str,link), luxSpectrumTexture("Ks", "substrade.ks", "1.0 1.0 1.0", 1.0, "specular", "", mat, gui))
			anisotropic = luxProp(mat, "substrade.anisotropic", False)
			if gui:
				gui.newline("")
				Draw.Toggle("A", evtLuxGui, gui.x-gui.h, gui.y-gui.h, gui.h, gui.h, anisotropic.get()=="true", "anisotropic roughness", lambda e,v:anisotropic.set(["false","true"][bool(v)]))
			if anisotropic.get()=="true":
				(str,link) = c((str,link), luxFloatTexture("uroughness", "substrade.uroughness", 0.1, 0.0, 1.0, "u-roughness", "", mat, gui))
				(str,link) = c((str,link), luxFloatTexture("vroughness", "substrade.vroughness", 0.1, 0.0, 1.0, "v-roughness", "", mat, gui))
			else:
				(str,link) = c((str,link), luxFloatTexture("uroughness", "substrade.uroughness", 0.1, 0.0, 1.0, "roughness", "", mat, gui))
				if not(gui):
					(str,link) = c((str,link), luxFloatTexture("vroughness", "substrade.uroughness", 0.1, 0.0, 1.0, "v-roughness", "", mat, gui))
			(str,link) = c((str,link), luxFloatTexture("bumpmap", "substrade.bumpmap", 0.0, 0.0, 1.0, "bumpmap", "", mat, gui))
# obsolet
#		if mattype.get() == "translucent":
#			(str,link) = c((str,link), luxSpectrumTexture("Kd", "translucent.kd", "1.0 1.0 1.0", 1.0, "diffuse", "", mat, gui))
#			(str,link) = c((str,link), luxSpectrumTexture("Ks", "translucent.ks", "1.0 1.0 1.0", 1.0, "specular", "", mat, gui))
#			(str,link) = c((str,link), luxSpectrumTexture("reflect", "translucent.reflect", "1.0 1.0 1.0", 1.0, "reflection", "", mat, gui))
#			(str,link) = c((str,link), luxSpectrumTexture("transmit", "translucent.transmit", "1.0 1.0 1.0", 1.0, "transmission", "", mat, gui))
#			(str,link) = c((str,link), luxFloatTexture("roughness", "translucent.roughness", 0.1, 0.0, 1.0, "roughness", "", mat, gui))
#			(str,link) = c((str,link), luxFloatTexture("index", "translucent.index", 1.5, 0.0, 100.0, "index", "", mat, gui))
#			(str,link) = c((str,link), luxFloatTexture("bumpmap", "translucent.bumpmap", 0.0, 0.0, 1.0, "bumpmap", "", mat, gui))
# obsolet
#		if mattype.get() == "uber":
#			(str,link) = c((str,link), luxSpectrumTexture("Kd", "uber.kd", "1.0 1.0 1.0", 1.0, "diffuse", "", mat, gui))
#			(str,link) = c((str,link), luxSpectrumTexture("Ks", "uber.ks", "1.0 1.0 1.0", 1.0, "specular", "", mat, gui))
#			(str,link) = c((str,link), luxSpectrumTexture("Kr", "uber.kr", "1.0 1.0 1.0", 1.0, "reflection", "", mat, gui))
#			(str,link) = c((str,link), luxFloatTexture("roughness", "uber.roughness", 0.1, 0.0, 1.0, "roughness", "", mat, gui))
#			(str,link) = c((str,link), luxSpectrumTexture("opacity", "uber.opacity", "1.0 1.0 1.0", 1.0, "opacity", "", mat, gui))
#			(str,link) = c((str,link), luxFloatTexture("bumpmap", "uber.bumpmap", 0.0, 0.0, 1.0, "bumpmap", "", mat, gui))
		luxProp(mat, "link", "").set("".join(link))
	return str



def CBluxExport(default, run):
	if default:
		datadir = luxProp(Scene.GetCurrent(), "datadir", "").get()
		if datadir=="": datadir = Blender.Get("datadir")
		filename = datadir + os.sep + "default.lxs"
		save_still(filename)
	else:
		Window.FileSelector(save_still, "Export", sys.makename(Blender.Get("filename"), ".lxs"))



activemat = None
def setactivemat(mat):
	global activemat
	activemat = mat

# gui main draw
def luxDraw():
	BGL.glClear(BGL.GL_COLOR_BUFFER_BIT)
	y = 420
	BGL.glColor3f(0.2,0.2,0.2); BGL.glRectf(0,0,440,y)
	BGL.glColor3f(0.9,0.9,0.9); BGL.glRasterPos2i(10,y-15); Draw.Text("LuxBlend v0.1RC4alpha-MatEditor :::...")
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
			BGL.glColor3f(1.0,0.5,0.4);BGL.glRectf(10,y-74,90,y-70);BGL.glColor3f(0.9,0.9,0.9)
			obj = scn.objects.active
			if obj:
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
				Draw.Menu(menustr, evtLuxGui, r[0], r[1], r[2], r[3], matindex, "", lambda e,v: setactivemat(mats[v]))
				luxBool("", matfilter, "filter", "only show active object materials", gui, 0.3)
				Draw.Button("Preview", evtPreviewMaterial, gui.x, gui.y-gui.h, 50, gui.h, "preview material")
				Draw.Button("L", evtLoadMaterial, gui.x+50, gui.y-gui.h, gui.h, gui.h, "load a material preset")
				Draw.Button("S", evtSaveMaterial, gui.x+50+gui.h, gui.y-gui.h, gui.h, gui.h, "save a material preset")
				Draw.Button("D", evtDeleteMaterial, gui.x+50+gui.h*2, gui.y-gui.h, gui.h, gui.h, "delete a material preset")
				if len(mats) > 0:
					setactivemat(mats[matindex])
					luxMaterial(activemat, gui)
		if luxpage.get() == 1:
			BGL.glColor3f(1.0,0.5,0.4);BGL.glRectf(90,y-74,170,y-70);BGL.glColor3f(0.9,0.9,0.9)
			cam = scn.getCurrentCamera()
			if cam:
				luxCamera(cam.data, scn.getRenderingContext(), gui)
			gui.newline("", 10)
			luxEnvironment(scn, gui)
		if luxpage.get() == 2:
			BGL.glColor3f(1.0,0.5,0.4);BGL.glRectf(170,y-74,250,y-70);BGL.glColor3f(0.9,0.9,0.9)
			luxSurfaceIntegrator(scn, gui)
			gui.newline("", 10)
			luxSampler(scn, gui)
			gui.newline("", 10)
			luxPixelFilter(scn, gui)
		if luxpage.get() == 3:
			BGL.glColor3f(1.0,0.5,0.4);BGL.glRectf(250,y-74,330,y-70);BGL.glColor3f(0.9,0.9,0.9)
			luxFilm(scn, gui)
		if luxpage.get() == 4:
			BGL.glColor3f(1.0,0.5,0.4);BGL.glRectf(330,y-74,410,y-70);BGL.glColor3f(0.9,0.9,0.9)
			luxSystem(scn, gui)
			gui.newline("", 10)
			luxAccelerator(scn, gui)
			gui.newline("SETTINGS:", 10)
			r = gui.getRect(2,1)
			Draw.Button("save defaults", 0, r[0], r[1], r[2], r[3], "save current settings as defaults", lambda e,v:saveluxdefaults())
		run = luxProp(scn, "run", "true")
		dlt = luxProp(scn, "default", "true")
		lxs = luxProp(scn, "lxs", "true")
		lxo = luxProp(scn, "lxo", "true")
		lxm = luxProp(scn, "lxm", "true")
		if (run.get()=="true"):
			Draw.Button("Render", 0, 10, 20, 180, 36, "Render with Lux", lambda e,v:CBluxExport(dlt.get()=="true", True))
		else:
			Draw.Button("Export", 0, 10, 20, 180, 36, "Export", lambda e,v:CBluxExport(dlt.get()=="true", False))
#			Draw.Button("Export Anim", 0, 200, 20, 100, 36, "Export as animation")
		Draw.Toggle("run", evtLuxGui, 320, 40, 30, 16, run.get()=="true", "start Lux after export", lambda e,v: run.set(["false","true"][bool(v)]))
		Draw.Toggle("def", evtLuxGui, 350, 40, 30, 16, dlt.get()=="true", "save to default.lxs", lambda e,v: dlt.set(["false","true"][bool(v)]))
		Draw.Toggle(".lxs", 0, 320, 20, 30, 16, lxs.get()=="true", "export .lxs scene file", lambda e,v: lxs.set(["false","true"][bool(v)]))
		Draw.Toggle(".lxo", 0, 350, 20, 30, 16, lxo.get()=="true", "export .lxo geometry file", lambda e,v: lxo.set(["false","true"][bool(v)]))
		Draw.Toggle(".lxm", 0, 380, 20, 30, 16, lxm.get()=="true", "export .lxm material file", lambda e,v: lxm.set(["false","true"][bool(v)]))
	BGL.glColor3f(0.9, 0.9, 0.9) ; BGL.glRasterPos2i(340,5) ; Draw.Text("Press Q or ESC to quit.", "tiny")


activeObject = None			
def luxEvent(evt, val):  # function that handles keyboard and mouse events
	global activeObject, activemat
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

	
def luxButtonEvt(evt):  # function that handles button events
	global usedproperties
	if evt == evtLuxGui:
		Draw.Redraw()
		# Window.QRedrawAll() # moved to luxAttr.set()
	if evt == evtSavePreset:
		scn = Scene.GetCurrent()
		if scn:
			name = Draw.PupStrInput("preset name: ", "")
			if name != "":
				usedproperties = {}
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
			matsstr = "delete preset: %t"
			for i, v in enumerate(matskeys): matsstr += "|%s %%x%d"%(v, i)
			r = Draw.PupMenu(matsstr, 20)
			if r >= 0:
				name = matskeys[r]
				try:
					for k,v in mats[name].items(): activemat.properties['luxblend'][k] = v
				except: pass
				Draw.Redraw()
	if evt == evtSaveMaterial:
		if activemat:
			name = Draw.PupStrInput("preset name: ", "")
			if name != "":
				usedproperties = {}
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
	if evt == evtPreviewMaterial:
		if activemat:
# not finished yet
#			Draw.PupBlock("Preview settings", [("diameter", Draw.Create(1.0), 0.0, 100.0, "help")])
			datadir = Blender.Get("datadir")
			filename = datadir + os.sep + "preview.lxs"
			file = open(filename, 'w')
			file.write('LookAt 0.0 -5.0 1.0 0.0 -4.0 1.0 0.0 0.0 1.0\nCamera "perspective" "float fov" [22.5] "float screenwindow" [-1.0 1.0 -1.21 0.29]\n')
			file.write('Film "multiimage" "integer xresolution" [400] "integer yresolution" [300] "integer ldr_displayinterval" [5] "integer ldr_writeinterval" [3600] "string tonemapper" ["reinhard"]\n')
			file.write('Sampler "erpt"\nSurfaceIntegrator "path"\n')
			file.write('WorldBegin\n')
			file.write(luxMaterial(activemat))
			file.write('AttributeBegin\nTransform [0.5 0.0 0.0 0.0  0.0 0.5 0.0 0.0  0.0 0.0 0.5 0.0  0.0 0.0 0.5 1.0]\n')
			file.write(luxProp(activemat,"link","").get()+'\n')
			file.write('Shape "sphere" "float radius" [1.0]\nAttributeEnd\n')
			file.write('AttributeBegin\nTransform [5.0 0.0 0.0 0.0  0.0 5.0 0.0 0.0  0.0 0.0 5.0 0.0  0.0 0.0 0.0 1.0]\n')
			file.write('Material "matte" "float Kd" [0.8 0.8 0.8]\n')
			file.write('Shape "disk" "float radius" [1.0]\nAttributeEnd\n')
			file.write('AttributeBegin\nTransform [0.5 0.0 0.0 0.0  0.0 0.5 0.0 0.0  0.0 0.0 -0.5 0.0  0.5 -0.5 2.0 1.0]\n')
			file.write('AreaLightSource "area" "color L" [1.0 1.0 1.0]\n')
#			file.write('Shape "trianglemesh" "integer indices" [0 1 2 0 2 3] "point P" [-1.0 1.0 0.0 1.0 1.0 0.0 1.0 -1.0 0.0 -1.0 -1.0 0.0]\nAttributeEnd\n')
			file.write('Shape "disk" "float radius" [1.0]\nAttributeEnd\n')
			file.write('WorldEnd\n')
			file.close()
			launchLux(filename)




Draw.Register(luxDraw, luxEvent, luxButtonEvt)

def setFocus(target):
	currentscene = Scene.GetCurrent()
	camObj = currentscene.getCurrentCamera()
	if target == "S":
		try:
			refLoc = (Object.GetSelected()[0]).getLocation()
		except:
			print "select an object to focus\n"
	if target == "C":
		refLoc = Window.GetCursorPos()
	dist = Mathutils.Vector(refLoc) - Mathutils.Vector(camObj.getLocation())
	camDir = camObj.getMatrix()[2]*(-1.0)
	camObj.getData(mesh=1).dofDist = (camDir[0]*dist[0]+camDir[1]*dist[1]+camDir[2]*dist[2])/camDir.length # data







print "\n\nLuxBlend v0.1RC4alphaCVS\n"

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
					Window.FileSelector(lambda s:luxProp(scn, "lux", "").set(s), "Select Lux executable")
					saveluxdefaults()
				if r == 2:
					newluxdefaults["checkluxpath"] = False
					saveluxdefaults()
else:
	print "Lux path check disabled\n"
