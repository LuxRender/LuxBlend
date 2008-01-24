#!BPY
"""Registration info for Blender menus:
Name: 'LuxBlend-v0.1-alphaCVS...'
Blender: 240
Group: 'Export'
Tooltip: 'Export to LuxRender v0.1 scene format (.lxs)'
"""
#
# ***** BEGIN GPL LICENSE BLOCK *****
#
# --------------------------------------------------------------------------
# LuxBlend v0.1 alphaCVS exporter
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
from Blender import Mesh, Scene, Object, Material, Texture, Window, sys, Draw, BGL, Mathutils


######################################################
# Functions
######################################################

# New name based on old with a different extension
def newFName(ext):
	return Blender.Get('filename')[: -len(Blender.Get('filename').split('.', -1)[-1]) ] + ext

def luxMatrix(matrix):
	ostr = ""
	ostr += "Transform [%s %s %s %s  %s %s %s %s  %s %s %s %s  %s %s %s %s]\n"\
		%(matrix[0][0], matrix[0][1], matrix[0][2], matrix[0][3],\
		  matrix[1][0], matrix[1][1], matrix[1][2], matrix[1][3],\
		  matrix[2][0], matrix[2][1], matrix[2][2], matrix[2][3],\
		  matrix[3][0], matrix[3][1], matrix[3][2], matrix[3][3]) 
	return ostr

	
#################### Export Material Texture ###

# MATERIAL TYPES enum
# 0 = 'glass'
# 1 = 'roughglass'
# 2 = 'mirror'
# 3 = 'plastic'
# 4 = 'shinymetal'
# 5 = 'substrate'
# 6 = 'matte' (Oren-Nayar)
# 7 = 'matte' (Lambertian)

# 8 = 'metal'
metal_names = [None]*100
metal_names[0] = "ALUMINIUM"
metal_names[1] = "AMORPHOUS_CARBON"
metal_names[2] = "SILVER"
metal_names[3] = "GOLD"
metal_names[4] = "COBALT"
metal_names[5] = "COPPER"
metal_names[6] = "CHROMIUM"
metal_names[7] = "LITHIUM"
metal_names[8] = "MERCURY"
metal_names[9] = "NICKEL"
metal_names[10] = "POTASSIUM"
metal_names[11] = "PLATIUM"
metal_names[12] = "IRIDIUM"
metal_names[13] = "SILICON"
metal_names[14] = "AMORPHOUS_SILICON"
metal_names[15] = "SODIUM"
metal_names[16] = "RHODIUM"
metal_names[17] = "TUNGSTEN"
metal_names[18] = "VANADIUM"

# 9 = 'carpaint'
carpaint_names = [None]*100
carpaint_names[0] = "CAR_FORD_F8"
carpaint_names[1] = "CAR_POLARIS_SILBER"
carpaint_names[2] = "CAR_OPEL_TITAN"
carpaint_names[3] = "CAR_BMW339"
carpaint_names[4] = "CAR_2K_ACRYLACK"
carpaint_names[5] = "CAR_WHITE"
carpaint_names[6] = "CAR_BLUE"
carpaint_names[7] = "CAR_BLUE_MATTE"


def makeCarpaintName(name):
	if (name == carpaint_names[0]):
		return "ford f8"
	if (name == carpaint_names[1]):
		return "polaris silber"
	if (name == carpaint_names[2]):
		return "opel titan"
	if (name == carpaint_names[3]):
		return "bmw339"
	if (name == carpaint_names[4]):
		return "2k acrylack"
	if (name == carpaint_names[5]):
		return "white"
	if (name == carpaint_names[6]):
		return "blue"
	if (name == carpaint_names[7]):
		return "blue matte"

def makeMetalName(name):
	if (name == metal_names[0]):
		return "aluminum"
	if (name == metal_names[1]):
		return "amorphous carbon"
	if (name == metal_names[2]):
		return "silver"
	if (name == metal_names[3]):
		return "gold"
	if (name == metal_names[4]):
		return "cobalt"
	if (name == metal_names[5]):
		return "copper"
	if (name == metal_names[6]):
		return "chromium"
	if (name == metal_names[7]):
		return "lithium"
	if (name == metal_names[8]):
		return "mercury"
	if (name == metal_names[9]):
		return "nickel"
	if (name == metal_names[10]):
		return "potassium"
	if (name == metal_names[11]):
		return "platium"
	if (name == metal_names[12]):
		return "iridium"
	if (name == metal_names[13]):
		return "silicon"
	if (name == metal_names[14]):
		return "amorphous silicon"
	if (name == metal_names[15]):
		return "sodium"
	if (name == metal_names[16]):
		return "rhodium"
	if (name == metal_names[17]):
		return "tungsten"
	if (name == metal_names[18]):
		return "vanadium"

### Determine the type of material ###
def getMaterialType(mat):
	# default to matte (Lambertian)
	mat_type = 7

	# test for metal material
	if (mat.name in metal_names):
		mat_type = 8
		return mat_type

	# test for carpaint material
	if (mat.name in carpaint_names):
		mat_type = 9
		return mat_type

	# test for emissive material
	if (mat.emit > 0):
		### emitter material ###
		mat_type = 100
		return mat_type

	# test for Transmissive (transparent) Materials
	elif (mat.mode & Material.Modes.RAYTRANSP):
		if(mat.getTranslucency() < 1.0):
			### 'glass' material ###
			mat_type = 0	
		else:
			### 'roughglass' material ###
			mat_type = 1

	# test for Mirror Material
	elif(mat.mode & Material.Modes.RAYMIRROR):
		### 'mirror' material ###
		mat_type = 2

	# test for Diffuse / Specular Reflective materials
	else:
		if (mat.getSpec() > 0.0001):
			# Reflective 
			if (mat.getSpecShader() == 2):			# Blinn
				### 'plastic' material ###
				mat_type = 3
			elif (mat.getSpecShader() == 1):		# Phong
				### 'shinymetal' material ###
				mat_type = 4
			else:						# CookTor/other
				### 'substrate' material ###
				mat_type = 5
		else:
			### 'matte' material ### 
			if (mat.getDiffuseShader() == 1):	# Oren-Nayar
				# oren-nayar sigma
				mat_type = 6
			else:					# Lambertian/other
				# lambertian sigma
				mat_type = 7

	return mat_type


# Determine the type of material / returns filename or 'NONE' 
def getTextureChannel(mat, channel):
	for t in mat.getTextures():
		if (t != None) and (t.texco & Blender.Texture.TexCo['UV']) and\
				(t.tex.type == Blender.Texture.Types.IMAGE):
			if t.mapto & Blender.Texture.MapTo[channel]:
				(imagefilepath, imagefilename) = os.path.split(t.tex.getImage().getFilename())
				return imagefilename
	return 'NONE'

def getTextureforChannel(mat, channel):
	for t in mat.getTextures():
		if (t != None) and (t.texco & Blender.Texture.TexCo['UV']) and\
				(t.tex.type == Blender.Texture.Types.IMAGE):
			if t.mapto & Blender.Texture.MapTo[channel]:
				return t
	return 0

# MATERIAL TYPES enum
# 0 = 'glass'
# 1 = 'roughglass'
# 2 = 'mirror'
# 3 = 'plastic'
# 4 = 'shinymetal'
# 5 = 'substrate'
# 6 = 'matte' (Oren-Nayar)
# 7 = 'matte' (Lambertian)
# 8 = 'metal'
#
# 100 = emissive (area light source / trianglemesh)

###### RGC ##########################
def rg(col):
	scn = Scene.GetCurrent()
	if getProp(scn, "RGC", 1):
		gamma = getProp(scn, "OutputGamma", 2.2)
	else:
		gamma = 1.0
	ncol = col**gamma
	if getProp(scn, "ColClamp", 0):
		ncol = ncol * 0.9
		if ncol > 0.9:
			ncol = 0.9
		if ncol < 0.0:
			ncol = 0.0
	return ncol

def exportMaterial(mat):
	str = "# Material '%s'\n" %mat.name

	def write_color_constant( chan, name, r, g, b ):
		return "Texture \"%s-%s\" \"color\" \"constant\" \"color value\" [%.3f %.3f %.3f]\n" %(chan, name, rg(r), rg(g), rg(b))

	def write_color_imagemap( chan, name, filename, scaleR, scaleG, scaleB ):
		om = "Texture \"%s-map-%s\" \"color\" \"imagemap\" \"string filename\" [\"%s\"] \"float vscale\" [-1.0]\n" %(chan, name, filename)
		om += "Texture \"%s-scale-%s\" \"color\" \"constant\" \"color value\" [%f %f %f]\n" %(chan, name, rg(scaleR), rg(scaleG), rg(scaleB))
		om += "Texture \"%s-%s\" \"color\" \"scale\" \"texture tex1\" [\"%s-map-%s\"] \"texture tex2\" [\"%s-scale-%s\"]\n" %(chan, name, chan, name, chan, name)
		return om

	def write_float_constant( chan, name, v ):
		return "Texture \"%s-%s\" \"float\" \"constant\" \"float value\" [%f]\n" %(chan, name, v)

	def write_float_imagemap( chan, name, filename, scale ):
		om = "Texture \"%s-map-%s\" \"float\" \"imagemap\" \"string filename\" [\"%s\"] \"float vscale\" [-1.0]\n" %(chan, name, filename)
		om += "Texture \"%s-scale-%s\" \"float\" \"constant\" \"float value\" [%f]\n" %(chan, name, scale)
		om += "Texture \"%s-%s\" \"float\" \"scale\" \"texture tex1\" [\"%s-map-%s\"] \"texture tex2\" [\"%s-scale-%s\"]\n" %(chan, name, chan, name, chan, name)
		return om

	def write_color_param( m, param, chan, r, g, b ):
		chan_file = getTextureChannel(m, chan)
		if (chan_file == 'NONE'):
			return write_color_constant( param, m.name, r, g, b )
		else:
			tc = getTextureforChannel(m, chan)
			if(tc == 0):
				ss = 1.0
			else:
				ss = tc.colfac
			return write_color_imagemap( param, m.name, chan_file, r * ss, g * ss, b * ss )

	def write_float_param( m, param, chan, v ):
		chan_file = getTextureChannel(m, chan)
		if (chan_file == 'NONE'):
			return write_float_constant( param, m.name, v )
		else:
			tc = getTextureforChannel(m, chan)
			if (chan == 'NOR'):
				ss = tc.norfac * 0.1
			else:
				ss = v
			return write_float_imagemap( param, m.name, chan_file, ss )

	# translates blender mat.hard (range: 1-511) 
	# to lux microfacet shinyness value (0.00001 = nearly specular - 1.0 = diffuse)
	def HardtoMicro(hard):
		micro = 1.0 / (float(hard) *5)
		if( micro < 0.00001 ):
			micro = 0.00001
		if( micro > 1.0 ):
			micro = 1.0
		return micro

	mat_type = getMaterialType(mat)

	if (mat_type == 100):
		### emitter material ### COMPLETE
		str += "# Type: emitter\n"
		str += "# See geometry block.\n\n"

	elif (mat_type == 0):
		### 'glass' material ### COMPLETE
		str += "# Type: 'glass'\n"
		str += write_color_param( mat, "Kr", 'SPEC', mat.specR, mat.specG, mat.specB )
		str += write_color_param( mat, "Kt", 'COL', mat.R, mat.G, mat.B )
		str += write_float_param( mat, "index", 'REF', mat.IOR )
		str += write_float_param( mat, "bumpmap", 'NOR', 0.0 )

	elif (mat_type == 1):
		### 'roughglass' material ###
		str += "# Type: 'roughglass'\n"
		str += write_color_param( mat, "Kr", 'SPEC', mat.specR, mat.specG, mat.specB )
		str += write_color_param( mat, "Kt", 'COL', mat.R, mat.G, mat.B )
		str += write_float_param( mat, "uroughness", 'HARD', HardtoMicro(mat.hard) )
		str += write_float_param( mat, "vroughness", 'HARD', HardtoMicro(mat.hard) )
		str += write_float_param( mat, "index", 'REF', mat.IOR )
		str += write_float_param( mat, "bumpmap", 'NOR', 0.0 )

	elif (mat_type == 2):
		### 'mirror' material ### COMPLETE
		str += "# Type: 'mirror'\n"
		str += write_color_param( mat, "Kr", 'COL', mat.R, mat.G, mat.B )
		str += write_float_param( mat, "bumpmap", 'NOR', 0.0 )

	elif (mat_type == 3):
		### 'plastic' material ### COMPLETE
		str += "# Type: 'plastic'\n"
		str += write_color_param( mat, "Kd", 'COL', mat.R, mat.G, mat.B )
		spec = mat.getSpec()
		if spec > 1.0:
			spec = 0
		str += write_color_param( mat, "Ks", 'SPEC', mat.specR * spec, mat.specG * spec, mat.specB * spec )
		str += write_float_param( mat, "roughness", 'HARD', HardtoMicro(mat.hard) )
		str += write_float_param( mat, "bumpmap", 'NOR', 0.0 )

	elif (mat_type == 4):
		### 'shinymetal' material ### COMPLETE
		str += "# Type: 'shinymetal'\n"
		str += write_color_param( mat, "Ks", 'COL', mat.R, mat.G, mat.B )
		spec = mat.getSpec()
		if spec > 1.0:
			spec = 0
		str += write_color_param( mat, "Kr", 'SPEC', mat.specR * spec, mat.specG * spec, mat.specB * spec )
		str += write_float_param( mat, "roughness", 'HARD', HardtoMicro(mat.hard) )
		str += write_float_param( mat, "bumpmap", 'NOR', 0.0 )

	elif (mat_type == 8):
		### 'metal' material ### COMPLETE
		str += "# Type: 'metal'\n"
		str += write_float_param( mat, "roughness", 'HARD', HardtoMicro(mat.hard) )
		str += write_float_param( mat, "bumpmap", 'NOR', 0.0 )

	elif (mat_type == 9):
		### 'carpaint' material ### COMPLETE
		str += "# Type: 'carpaint'\n"
		str += write_float_param( mat, "bumpmap", 'NOR', 0.0 )

	elif (mat_type == 5):
		### 'substrate' material ### COMPLETE
		str += "# Type: 'substrate'\n"
		str += write_color_param( mat, "Kd", 'COL', mat.R, mat.G, mat.B )
		spec = mat.getSpec()
		if spec > 1.0:
			spec = 0
		str += write_color_param( mat, "Ks", 'SPEC', mat.specR * spec, mat.specG * spec, mat.specB * spec )
		# TODO: add different inputs for both u/v roughenss for aniso effect
		str += write_float_param( mat, "uroughness", 'HARD', HardtoMicro(mat.hard) )
		str += write_float_param( mat, "vroughness", 'HARD', HardtoMicro(mat.hard) )
		str += write_float_param( mat, "bumpmap", 'NOR', 0.0 )

	elif (mat_type == 6):
		### 'matte' (Oren-Nayar) material ###
		# TODO
		str += "\n"
	else:
		### 'matte' (Lambertian) material ### COMPLETE
		str += "# Type: 'matte' (Lambertian)\n"
		str += write_color_param( mat, "Kd", 'COL', mat.R, mat.G, mat.B )
		str += write_float_param( mat, "sigma", 'REF', 0 )
		str += write_float_param( mat, "bumpmap", 'NOR', 0.0 )

	str += "#####\n\n"
	return str

def exportMaterialGeomTag(mat):
	mat_type = getMaterialType(mat)
	if (mat_type == 100):
		str = "AreaLightSource \"area\" \"integer nsamples\" [1] \"color L\" [%f %f %f]" %(mat.R * mat.emit, mat.G * mat.emit, mat.B * mat.emit)
	else:

	 	str = "Material "

		if (mat_type == 0):
			### 'glass' material ### COMPLETE
			str += " \"glass\" \"texture Kr\" \"Kr-%s\"" %mat.name
			str += " \"texture Kt\" \"Kt-%s\"" %mat.name
			str += " \"texture index\" \"index-%s\"" %mat.name
			str += " \"texture bumpmap\" \"bumpmap-%s\"" %mat.name

		elif (mat_type == 1):
			### 'roughglass' material ###
			str += " \"roughglass\" \"texture Kr\" \"Kr-%s\"" %mat.name
			str += " \"texture Kt\" \"Kt-%s\"" %mat.name
			str += " \"texture uroughness\" \"uroughness-%s\"" %mat.name
			str += " \"texture vroughness\" \"vroughness-%s\"" %mat.name
			str += " \"texture index\" \"index-%s\"" %mat.name
			str += " \"texture bumpmap\" \"bumpmap-%s\"" %mat.name

		elif (mat_type == 2):
			### 'mirror' material ### COMPLETE
			str += " \"mirror\" \"texture Kr\" \"Kr-%s\"" %mat.name
			str += " \"texture bumpmap\" \"bumpmap-%s\"" %mat.name

		elif (mat_type == 3):
			### 'plastic' material ### COMPLETE
			str += " \"plastic\" \"texture Kd\" \"Kd-%s\"" %mat.name
			str += " \"texture Ks\" \"Ks-%s\"" %mat.name
			str += " \"texture roughness\" \"roughness-%s\"" %mat.name
			str += " \"texture bumpmap\" \"bumpmap-%s\"" %mat.name

		elif (mat_type == 4):
			### 'shinymetal' material ### COMPLETE
			str += " \"shinymetal\" \"texture Ks\" \"Ks-%s\"" %mat.name
			str += " \"texture Kr\" \"Kr-%s\"" %mat.name
			str += " \"texture roughness\" \"roughness-%s\"" %mat.name
			str += " \"texture bumpmap\" \"bumpmap-%s\"" %mat.name

		elif (mat_type == 8):
			### 'metal' material ### COMPLETE
			metalname = makeMetalName(mat.name)
			str += " \"metal\" \"string name\" \"%s\"" %metalname
			str += " \"texture roughness\" \"roughness-%s\"" %mat.name
			str += " \"texture bumpmap\" \"bumpmap-%s\"" %mat.name

		elif (mat_type == 9):
			### 'carpaint' material ### COMPLETE
			carpaintname = makeCarpaintName(mat.name)
			str += " \"carpaint\" \"string name\" \"%s\"" %carpaintname
			str += " \"texture bumpmap\" \"bumpmap-%s\"" %mat.name

		elif (mat_type == 5):
			### 'substrate' material ### COMPLETE
			str += " \"substrate\" \"texture Kd\" \"Kd-%s\"" %mat.name
			str += " \"texture Ks\" \"Ks-%s\"" %mat.name
			str += " \"texture uroughness\" \"uroughness-%s\"" %mat.name
			str += " \"texture vroughness\" \"vroughness-%s\"" %mat.name
			str += " \"texture bumpmap\" \"bumpmap-%s\"" %mat.name

		elif (mat_type == 6) or (mat_type == 7):
			### 'matte' (Oren-Nayar or Lambertian) material ###
			str += " \"matte\" \"texture Kd\" \"Kd-%s\"" %mat.name
			str += " \"texture sigma\" \"sigma-%s\"" %mat.name
			str += " \"texture bumpmap\" \"bumpmap-%s\"" %mat.name

	str += "\n"
	return str


################################################################




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

	#-------------------------------------------------
	# getMaterials(obj)
	# helper function to get the material list of an object in respect of obj.colbits
	#-------------------------------------------------
	def getMaterials(self, obj):
		mats = [None]*16
		colbits = obj.colbits
		objMats = obj.getMaterials(1)
		data = obj.getData()
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
		else:
			print "Warning: object %s has no material assigned"%(obj.getName())
			mats = []
		return mats

	#-------------------------------------------------
	# analyseObject(self, obj, matrix, name)
	# called by analyseScene to build the lists before export
	#-------------------------------------------------
	def analyseObject(self, obj, matrix, name):
		if (obj.users > 0):
			obj_type = obj.getType()
			if (obj.enableDupGroup or obj.enableDupVerts):
				for o, m in obj.DupObjects:
					self.analyseObject(o, m, "%s.%s"%(name, o.getName()))	
			elif (obj_type == "Mesh") or (obj_type == "Surf") or (obj_type == "Curve") or (obj_type == "Text"):
				mats = self.getMaterials(obj)
				if (len(mats)>0) and (mats[0]!=None) and (mats[0].name=="PORTAL"):
					self.portals.append([obj, matrix])
				else:
					for mat in mats:
						if (mat!=None) and (mat not in self.materials):
							self.materials.append(mat)
					mesh_name = obj.getData(name_only=True)
					try:
						self.meshes[mesh_name] += [obj]
					except KeyError:
						self.meshes[mesh_name] = [obj]				
					self.objects.append([obj, matrix])


	#-------------------------------------------------
	# analyseScene(self)
	# this function builds the lists of object, lights, meshes and materials before export
	#-------------------------------------------------
	def analyseScene(self):
		for obj in self.scene.objects:
			if ((obj.Layers & self.scene.Layers) > 0):
				self.analyseObject(obj, obj.getMatrix(), obj.getName())

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
				for face in mesh.faces:
					if (face.mat == matIndex):
						file.write("%d %d %d\n"%(index, index+1, index+2))
						if (len(face.verts)==4):
							file.write("%d %d %d\n"%(index, index+2, index+3))
						index += len(face.verts)
				file.write("\t] \"point P\" [\n");
				for face in mesh.faces:
					if (face.mat == matIndex):
						for vertex in face.verts:
							file.write("%f %f %f\n"%(vertex.co[0], vertex.co[1], vertex.co[2]))
				file.write("\t] \"normal N\" [\n")
				for face in mesh.faces:
					if (face.mat == matIndex):
						normal = face.no
						for vertex in face.verts:
							if (face.smooth):
								normal = vertex.no
							file.write("%f %f %f\n"%(normal[0], normal[1], normal[2]))
				if (mesh.faceUV):
					file.write("\t] \"float uv\" [\n")
					for face in mesh.faces:
						if (face.mat == matIndex):
							for uv in face.uv:
								file.write("%f %f\n"%(uv[0], uv[1]))
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
					for face in mesh.faces:
						if (face.mat == matIndex) and (face.smooth in smoothFltr[shape]):
							exportVIndices = []
							index = 0
							for vertex in face.verts:
								v = [vertex.co[0], vertex.co[1], vertex.co[2]]
								if normalFltr[shape]:
									if (face.smooth):
										v.extend(vertex.no)
									else:
										v.extend(face.no)
								if (uvFltr[shape]) and (mesh.faceUV):
									v.extend(face.uv[index])
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
						for vertex in exportVerts:
							file.write("%f %f %f\n"%(vertex[0], vertex[1], vertex[2]))
						if normalFltr[shape]:
							file.write("\t] \"normal N\" [\n")
							for vertex in exportVerts:
								file.write("%f %f %f\n"%(vertex[3], vertex[4], vertex[5]))
							if (uvFltr[shape]) and (mesh.faceUV):
								file.write("\t] \"float uv\" [\n")
								for vertex in exportVerts:
									file.write("%f %f\n"%(vertex[6], vertex[7]))
						else:			
							if (uvFltr[shape]) and (mesh.faceUV):
								file.write("\t] \"float uv\" [\n")
								for vertex in exportVerts:
									file.write("%f %f\n"%(vertex[3], vertex[4]))
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
			mats = self.getMaterials(objs[0]) # mats = obj.getData().getMaterials()
			for mat in mats: # don't instance if one of the materials is emissive
				if (mat!=None) and (mat.emit > 0.0):
					allow_instancing = False
			for obj in objs: # don't instance if the objects with same mesh uses different materials
				ms = self.getMaterials(obj)
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
				mats = self.getMaterials(obj)
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
			mats = self.getMaterials(obj) # mats = obj.getData().getMaterials()
			if (mesh_optimizing):
				self.exportMeshOpt(file, mesh, mats, mesh_name, True)
			else:
				self.exportMesh(file, mesh, mats, mesh_name, True)



######################################################
# EXPORT
######################################################

def save_lux(filename, unindexedname):
	global meshlist, matnames, geom_filename, geom_pfilename, mat_filename, mat_pfilename

	print("Lux Render Export started...\n")
	time1 = Blender.sys.time()
	scn = Scene.GetCurrent()
	##### Determine/open files
	if getProp(scn, "ExportScene", 1):
		print("Exporting scene to '" + filename + "'...\n")
		file = open(filename, 'w')

	filepath = os.path.dirname(filename)
	print filename
	print filepath
	filebase = os.path.splitext(os.path.basename(filename))[0]

	geom_filename = os.path.join(filepath, filebase + "-geom.lxo")
	geom_pfilename = filebase + "-geom.lxo"

	mat_filename = os.path.join(filepath, filebase + "-mat.lxm")
	mat_pfilename = filebase + "-mat.lxm"
	
	### Zuegs: initialization for export class
	export = luxExport(Blender.Scene.GetCurrent())
	
	if getProp(scn, "ExportScene", 1):
		##### Write Header ######
		file.write("# Lux Render v0.1 Scene File\n")
		file.write("# Exported by LuxBlend_01_alphaCVS\n")
	
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
			lens = camObj.data.getLens() 
	    		context = Blender.Scene.getCurrent().getRenderingContext()
	    		ratio = float(context.imageSizeY())/float(context.imageSizeX())
			ctype = getProp(camObj.data, "CameraType", 0)
			scale = 1.0
			if (ratio < 1.0):
				fov = 2*math.atan(16/lens*ratio) * (180 / 3.141592653)
				if ctype==1: # ortho scale
					scale = camObj.data.scale/2 * ratio
				screenwindow = [((2*camObj.data.shiftX)-1)/ratio*scale, ((2*camObj.data.shiftX)+1)/ratio*scale, ((2*camObj.data.shiftY/ratio)-1)*scale, ((2*camObj.data.shiftY/ratio)+1)*scale]
			else:
				fov = 2*math.atan(16/lens/ratio) * (180 / 3.141592653)
				if ctype==1: # ortho scale
					scale = camObj.data.scale/2 / ratio
				screenwindow = [((2*camObj.data.shiftX*ratio)-1)*scale, ((2*camObj.data.shiftX*ratio)+1)*scale, ((2*camObj.data.shiftY)-1)*ratio*scale, ((2*camObj.data.shiftY)+1)*ratio*scale]
			file.write("LookAt %f %f %f   %f %f %f %f %f %f\n" % ( pos[0], pos[1], pos[2], target[0], target[1], target[2], up[0], up[1], up[2] ))
			if ctype==0:
				file.write("Camera \"perspective\" \"float fov\" [%f] \"float lensradius\" [%f] \"float focaldistance\" [%f] \"float screenwindow\" [%f, %f, %f, %f] \"float shutteropen\" [%f] \"float shutterclose\" [%f]\n"\
					% (fov, getProp(camObj.data, "LensRadius", 0.0), getProp(camObj.data, "FocalDistance", 2.0), screenwindow[0], screenwindow[1], screenwindow[2], screenwindow[3], getProp(camObj.data, "ShutterOpen", 0.0), getProp(camObj.data, "ShutterClose", 1.0)))
			if ctype==1:
				file.write("Camera \"orthographic\" \"float lensradius\" [%f] \"float focaldistance\" [%f] \"float screenwindow\" [%f, %f, %f, %f] \"float shutteropen\" [%f] \"float shutterclose\" [%f]\n"\
					% (getProp(camObj.data, "LensRadius", 0.0),getProp(camObj.data, "FocalDistance", 2.0), screenwindow[0], screenwindow[1], screenwindow[2], screenwindow[3], getProp(camObj.data, "ShutterOpen", 0.0), getProp(camObj.data, "ShutterClose", 1.0)))
			if ctype==2:
				file.write("Camera \"environment\" \"float shutteropen\" [%f] \"float shutterclose\" [%f]\n"\
					% (getProp(camObj.data, "ShutterOpen", 0.0), getProp(camObj.data, "ShutterClose", 1.0)))
		file.write("\n")
	
		##### Write film ######
		file.write("Film \"multiimage\"\n") 
		file.write("     \"integer xresolution\" [%d] \"integer yresolution\" [%d]\n" % (scn.getRenderingContext().sizeX*getProp(scn, "ScaleSize", 100)/100, scn.getRenderingContext().sizeY*getProp(scn, "ScaleSize", 100)/100) )
		if(getProp(scn, "SaveIGI", 0)):
			file.write("	 \"string igi_filename\" [\"out.igi\"]\n")
			file.write("	 	\"integer igi_writeinterval\" [%i]\n" %(getProp(scn, "SaveIGIInterval", 120)))
		if(getProp(scn, "SaveEXR", 0)):
			file.write("	 \"string hdr_filename\" [\"out.exr\"]\n")
			file.write("	 	\"integer hdr_writeinterval\" [%i]\n" %(getProp(scn, "SaveEXRInterval", 120)))
		if(getProp(scn, "SaveTGA", 0)):
			file.write("	 \"string ldr_filename\" [\"out.tga\"]\n")
			file.write("		\"integer ldr_writeinterval\" [%i]\n" %(getProp(scn, "SaveTGAInterval", 120)))
		file.write("		\"integer ldr_displayinterval\" [%i]\n" %(getProp(scn, "DisplayInterval", 12)))
		file.write("		\"string tonemapper\" [\"reinhard\"]\n")
		file.write("			\"float reinhard_prescale\" [%f]\n" %(getProp(scn, "ToneMapPreScale", 1.0)))
		file.write("			\"float reinhard_postscale\" [%f]\n" %(getProp(scn, "ToneMapPostScale", 1.0)))
		file.write("			\"float reinhard_burn\" [%f]\n" %(getProp(scn, "ToneMapBurn", 6.0)))
		file.write("		\"float gamma\" [%f]\n" %(getProp(scn, "OutputGamma",2.2)))
		file.write("		\"float dither\" [%f]\n\n" %(getProp(scn, "OutputDither",0)))
		if(getProp(scn, "Bloom", 0)):
			file.write("		\"float bloomwidth\" [%f]\n" %(getProp(scn, "BloomWidth", 0.1)))
			file.write("		\"float bloomradius\" [%f]\n" %(getProp(scn, "BloomRadius", 0.1)))
	
		if(getProp(scn, "FilterType", 0) == 1):
			file.write("PixelFilter \"mitchell\" \"float xwidth\" [%f] \"float ywidth\" [%f]\n" %(getProp(scn, "FilterXWidth", 2.0), getProp(scn, "FilterYWidth", 2.0)))
		else:
			file.write("PixelFilter \"gaussian\" \"float xwidth\" [%f] \"float ywidth\" [%f]\n" %(getProp(scn, "FilterXWidth", 2.0), getProp(scn, "FilterYWidth", 2.0)))
		file.write("\n")
	
		##### Write Pixel Sampler ######
		if(getProp(scn, "SamplerType", 1) == 1):
			file.write("Sampler \"random\" ")
		else:
			file.write("Sampler \"lowdiscrepancy\" ")
	
		if(getProp(scn, "PixelSamplerType", 0) == 0):
			file.write("\"string pixelsampler\" [\"vegas\"] ")
		if(getProp(scn, "PixelSamplerType", 0) == 1):
			file.write("\"string pixelsampler\" [\"random\"] ")
		if(getProp(scn, "PixelSamplerType", 0) == 2):
			file.write("\"string pixelsampler\" [\"linear\"] ")

		
		file.write("\"integer pixelsamples\" [%i]\n" %(getProp(scn, "SamplerPixelsamples", 4)))
		file.write("\n")
	
		##### Write Integrator ######
		file.write("SurfaceIntegrator \"path\" \"integer maxdepth\" [%i] " %(getProp(scn, "MaxDepth", 16)))
	
		if(getProp(scn, "Metropolis", 0) == 1):
			file.write("\"bool metropolis\" [\"true\"] ")
		else:
			file.write("\"bool metropolis\" [\"false\"] ")
	
		file.write("\"integer maxconsecrejects\" [%f] " %(getProp(scn, "MetropolisMaxRejects", 128)))
		file.write("\"float largemutationprob\" [%f] " %(getProp(scn, "MetropolisLMProb", 0.25)))
	
		file.write("\"float rrcontinueprob\" [%f]\n" %(getProp(scn, "RRContinueProb", 0.5)))
		file.write("\n")
	
		##### Write Acceleration ######
		file.write("Accelerator \"kdtree\"\n")
		file.write("\n")
	
	
		########## BEGIN World
		file.write("\n")
		file.write("WorldBegin\n")
	
		file.write("\n")
	
		export.analyseScene()
	
		##### Write World Background, Sunsky or Env map ######
		if getProp(scn, "EnvType", 0) == 0:
			worldcolor = Blender.World.Get('World').getHor()
			file.write("AttributeBegin\n")
			file.write("LightSource \"infinite\" \"color L\" [%g %g %g] \"integer nsamples\" [1]\n" %(worldcolor[0], worldcolor[1], worldcolor[2]))
	
			# file.write("%s" %portalstr)
			export.exportPortals(file)
	
	
			file.write("AttributeEnd\n")
		if getProp(scn, "EnvType", 0) == 1:
			for obj in scn.objects:
				if obj.getType() == "Lamp":
					if obj.data.getType() == 1: # sun object
						invmatrix = Mathutils.Matrix(obj.getInverseMatrix())
						file.write("AttributeBegin\n")
						file.write("Rotate %d 0 0 1\n"%(getProp(scn, "EnvRotation", 0)))
						file.write("LightSource \"sunsky\" \"integer nsamples\" [1]\n")
						file.write("            \"vector sundir\" [%f %f %f]\n" %(invmatrix[0][2], invmatrix[1][2], invmatrix[2][2]))
						file.write("		\"color L\" [%f %f %f]\n" %(getProp(scn, "SkyGain", 1.0), getProp(scn, "SkyGain", 1.0), getProp(scn, "SkyGain", 1.0)))
						file.write("		\"float turbidity\" [%f]\n" %(getProp(scn, "Turbidity", 2.0)))
	
						# file.write("%s" %portalstr)
						export.exportPortals(file)
	
	
						file.write("AttributeEnd\n")
		if getProp(scn, "EnvType", 0) == 2:
			if getProp(scn, "EnvFile", "") != "":
				file.write("AttributeBegin\n")
				file.write("Rotate %d 0 0 1\n"%(getProp(scn, "EnvRotation", 0)))
				file.write("LightSource \"infinite\" \"integer nsamples\" [1]\n")
				file.write("            \"string mapname\" [\"%s\"]\n" %(getProp(scn, "EnvFile", "")) )
	
				# file.write("%s" %portalstr)
				export.exportPortals(file)
	
				file.write("AttributeEnd\n")
		file.write("\n")
	
	
		#### Write material & geometry file includes in scene file
		file.write("Include \"%s\"\n\n" %(mat_pfilename))
		file.write("Include \"%s\"\n\n" %(geom_pfilename))
		
		#### Write End Tag
		file.write("WorldEnd\n\n")
		file.close()
		
	if getProp(scn, "ExportMat", 1):
		##### Write Material file #####
		print("Exporting materials to '" + mat_filename + "'...\n")
		mat_file = open(mat_filename, 'w')
		mat_file.write("")
		export.exportMaterials(mat_file)
		mat_file.write("")
		mat_file.close()
	
	if getProp(scn, "ExportGeom", 1):
		##### Write Geometry file #####
		print("Exporting geometry to '" + geom_filename + "'...\n")
		geom_file = open(geom_filename, 'w')
		meshlist = []
		geom_file.write("")
		export.exportMeshes(geom_file)
		export.exportObjects(geom_file)
		geom_file.write("")
		geom_file.close()

	print("Finished.\n")
	del export

	time2 = Blender.sys.time()
	print("Processing time: %f\n" %(time2-time1))
	#Draw.Exit()



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
	ic = getProp(scn, "LuxPath", "")
	threads = getProp(scn, "Threads", 1)
		
	if ostype == "win32":
		
#		# create 'LuxWrapper.cmd' and write two lines of code into it
#		f = open(datadir + "\LuxWrapper.cmd", 'w')
#		f.write("cd /d " + sys.dirname(ic) + "\n")
#		f.write("start /b /belownormal " + sys.basename(ic) + " %1 \n")
#		f.close()
		
#		# call external shell script to start Lux
#		cmd= "\"" + datadir + "\LuxWrapper.cmd " + filename + "\""

		cmd = "start /b /belownormal %s \"%s\" --threads=%d"%(ic, filename, threads)		

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
	MatSaved = 0
	unindexedname = filename
	save_lux(filename, unindexedname)
	if getProp(scn, "ExecuteLux", 0) == 1:
		launchLux(filename)


######################################################
# Settings GUI
######################################################

from types import *

# get defaults
try:
	rdict = Blender.Registry.GetKey('BlenderLux', False)
	if not(type(rdict) is DictType):
		rdict = {}
except:
	rdict = {}
newrdict = rdict


# property management
def setProp(obj, name, value):
	if(obj):	
		if(value!=None):
			try:
				obj.properties['luxblend'][name] = value
			except (KeyError, TypeError):
				obj.properties['luxblend'] = {}
				obj.properties['luxblend'][name] = value
		else:
			try:
				del obj.properties['luxblend'][name]
			except:
				pass	

def getProp(obj, name, default=None):
	try:
		value = (obj.properties['luxblend'])[name]
		newrdict[name] = value
		return value
	except KeyError:
		try:
			return rdict[name]
		except KeyError:
			setProp(obj, name, default)
			return default

 
def CBsetProp(obj, name):
	return lambda evt, val: setProp(obj, name, val)

def CBsetAttr(obj, name):
	return lambda evt, val: setattr(obj, name, val)



# Assign event numbers to buttons
evtNoEvt = 0
evtRedraw = 3
evtExport = 1
evtExportAnim = 2
openCamera = 6
openEnv = 7
openRSet = 8
openSSet = 9
openTmap = 10
evtFocusS = 4
evtFocusC = 5
evtloadimg = 11
evtbrowselux = 12
evtSaveDefaults = 13


sceneSizeX = Scene.GetCurrent().getRenderingContext().imageSizeX()
sceneSizeY = Scene.GetCurrent().getRenderingContext().imageSizeY()

strScaleSize = "Scale Size %t | 100 % %x100 | 75 % %x75 | 50 % %x50 | 25 % %x25"

strEnvType = "Env Type %t | Background Color %x0 | Physical Sky %x1 | Texture Map %x2 | None %x3"

strEnvMapType = "Map type %t | LatLong %x0"

strFilterType = "Filter %t | gaussian %x0 | mitchell %x1"

strSamplerType = "Sampler %t | lowdiscrepancy %x0 | random %x1"

strPixelSamplerType = "PixelSampler %t | vegas %x0 | random %x1 | linear %x2"

strIntegratorType = "Integrator %t | path %x0"

strToneMapType = "ToneMap type %t | Reinhard %x1"

		
######  Draw Camera  ###############################################
def drawCamera():
	drawButtons()
	BGL.glColor3f(1.0,0.5,0.4)
	BGL.glRectf(10,182,90,183)
	scn = Scene.GetCurrent()
#	try:
	cam = scn.getCurrentCamera().data
	if cam:
		BGL.glColor3f(0.9,0.9,0.9); BGL.glRasterPos2i(10,165); Draw.Text("Camera-Type:")
		Draw.Menu("Camera %t| perspective %x0| orthographic %x1| environment %x2", evtRedraw, 110, 160, 140, 18, getProp(cam, "CameraType", 0), "camera type", CBsetProp(cam, "CameraType"))
		BGL.glColor3f(0.9,0.9,0.9); BGL.glRasterPos2i(10,145); Draw.Text("Clipping:")
		Draw.Number("hither: ", evtNoEvt, 110, 140, 140, 18, cam.clipStart, 0.0, 100.0, "near clip distance", CBsetAttr(cam, "clipStart"))
		Draw.Number("yon: ", evtNoEvt, 260, 140, 140, 18, cam.clipEnd, 1.0, 5000.0, "far clip distance", CBsetAttr(cam, "clipEnd"))
		BGL.glColor3f(0.9,0.9,0.9); BGL.glRasterPos2i(10,125); Draw.Text("DOF Settings:")
		Draw.Number("Lens Radius: ", evtNoEvt, 110, 120, 140, 18, getProp(cam, "LensRadius", 0.0), 0.0, 3.0, "Defines the lens radius. Values higher than 0. enable DOF and control the amount", CBsetProp(cam, "LensRadius"))
		Draw.Number("Focal Distance: ", evtNoEvt, 260, 120, 140, 18, cam.dofDist, 0.0, 5000.0, "Distance from the camera at which objects will be in focus. Has no effect if Lens Radius is 0.", CBsetAttr(cam, "dofDist"))
		Draw.Button("S", evtFocusS, 400, 120, 20, 18, "Get the distance from the selected object")
		Draw.Button("C", evtFocusC, 420, 120, 20, 18, "Get the distance from the 3d cursor")
		BGL.glColor3f(0.9,0.9,0.9); BGL.glRasterPos2i(10,105); Draw.Text("Shutter:")
		Draw.Number("Open: ", evtNoEvt, 110, 100, 140, 18, getProp(cam, "ShutterOpen", 0.0), 0.0, 100.0, "The time in seconds at which the virtual shutter opens", CBsetProp(cam, "ShutterOpen"))
		Draw.Number("Close: ", evtNoEvt, 260, 100, 140, 18, getProp(cam, "ShutterClose", 1.0), 0.0, 100.0, "The time in seconds at which the virtual shutter closes", CBsetProp(cam, "ShutterClose"))
		t = getProp(cam, "CameraType", 0)
		if t==0: # perspective
			BGL.glColor3f(0.9,0.9,0.9); BGL.glRasterPos2i(10,85); Draw.Text("Perspective:")
			Draw.Number("FOV: ", evtNoEvt, 110, 80, 140, 18, cam.angle, 7.323871, 172.847331, "Field Of View", CBsetAttr(cam, "angle"))
		elif t==1: # orthographic
			BGL.glColor3f(0.9,0.9,0.9); BGL.glRasterPos2i(10,85); Draw.Text("Orthographic:")
			Draw.Number("Scale: ", evtNoEvt, 110, 80, 140, 18, cam.scale, 0.01, 1000.00, "Orthographic scale", CBsetAttr(cam, "scale"))

#	except:
#		pass

#	BGL.glColor3f(0.9,0.9,0.9) ; BGL.glRasterPos2i(10,100) ; Draw.Text("Size:")
#	Draw.Number("X: ", evtNoEvt, 10, 75, 95, 18, scn.getRenderingContext().sizeX, 1, 4096, "Width of the render", CBsetAttr(scn.getRenderingContext(), "sizeX"))
#	Draw.Number("Y: ", evtNoEvt, 115, 75, 95, 18, scn.getRenderingContext().sizeY, 1, 3072, "Height of the render", CBsetAttr(scn.getRenderingContext(), "sizeY"))
#	Draw.Menu(strScaleSize, evtNoEvt, 215, 75, 65, 18, getProp(scn, "ScaleSize", 100), "Scale Image Size of ...", CBsetProp(scn, "ScaleSize"))

##############  Draw Environment  #######################################
def drawEnv():
	drawButtons()
	BGL.glColor3f(1.0,0.5,0.4)
	BGL.glRectf(90,182,170,183)
	BGL.glColor3f(0.9,0.9,0.9)
	scn = Scene.GetCurrent()
	Draw.Menu(strEnvType, evtRedraw, 10, 150, 150, 18, getProp(scn, "EnvType", 0), "Set the Environment type", CBsetProp(scn, "EnvType"))
	if getProp(scn, "EnvType", 0) == 2:
		Draw.String("Image: ", evtNoEvt, 10, 130, 255, 18, getProp(scn, "EnvFile", ""), 50, "the file name of the EXR latlong map", CBsetProp(scn, "EnvFile"))
		Draw.Button("...", evtloadimg, 270, 130, 20, 18, "Load Env Map")
		Draw.Menu(strEnvMapType, evtNoEvt, 10, 110, 150, 18, getProp(scn, "EnvMapType", 0), "Set the map type of the probe", CBsetProp(scn, "EnvMapType"))
		Draw.Number("Rotation", evtNoEvt, 10, 90, 150, 18, getProp(scn, "EnvRotation", 0), 0.0, 360.0, "Set Environment rotation", CBsetProp(scn, "EnvRotation"))
	if getProp(scn, "EnvType", 0) == 1:
		Draw.Number("Sky Turbidity", evtNoEvt, 10, 130, 150, 18, getProp(scn, "Turbidity", 2.0), 1.5, 5.0, "Sky Turbidity", CBsetProp(scn, "Turbidity"))
		Draw.Number("Sky Gain", evtNoEvt, 10, 110, 150, 18, getProp(scn, "SkyGain", 1.0), 0.0, 5.0, "Sky Gain", CBsetProp(scn, "SkyGain"))
		Draw.Number("Rotation", evtNoEvt, 10, 90, 150, 18, getProp(scn, "EnvRotation", 0), 0.0, 360.0, "Set Environment rotation", CBsetProp(scn, "EnvRotation"))
	
###############  Draw Rendersettings   ###################################
def drawSettings():
	drawButtons()
	BGL.glColor3f(1.0,0.5,0.4)
	BGL.glRectf(170,182,250,183)
	BGL.glColor3f(0.9,0.9,0.9)
	scn = Scene.GetCurrent()
	Draw.Menu(strIntegratorType, evtNoEvt, 10, 150, 100, 18, getProp(scn, "IntegratorType", 0), "Engine Integrator type", CBsetProp(scn, "IntegratorType"))
	Draw.Toggle("MLT", evtNoEvt, 120, 150, 60, 18, getProp(scn, "Metropolis", 0), "use Metropolis Light Transport", CBsetProp(scn, "Metropolis"))
	Draw.Number("MaxRejects:", evtNoEvt, 180, 150, 120, 18, getProp(scn, "MetropolisMaxRejects", 128), 1, 1024, "Maximum nr of consecutive rejections for Metropolis accept", CBsetProp(scn, "MetropolisMaxRejects"))
	Draw.Number("LMprob:", evtNoEvt, 300, 150, 120, 18, getProp(scn, "MetropolisLMProb", 0.25), 0, 1, "Probability of using a large mutation for Metropolis", CBsetProp(scn, "MetropolisLMProb"))
	Draw.Number("Maxdepth:", evtNoEvt, 120, 130, 120, 18, getProp(scn, "MaxDepth", 16), 1, 1024, "Maximum path depth (bounces)", CBsetProp(scn, "MaxDepth"))
	Draw.Number("RRprob:", evtNoEvt, 240, 130, 120, 18, getProp(scn, "RRContinueProb", 0.5), 0.01, 1.0, "Russian Roulette continue probability", CBsetProp(scn, "RRContinueProp"))

	Draw.Menu(strSamplerType, evtNoEvt, 10, 100, 120, 18, getProp(scn, "SamplerType", 1), "Engine Sampler type", CBsetProp(scn, "SamplerType"))
	Draw.Menu(strPixelSamplerType, evtNoEvt, 140, 100, 120, 18, getProp(scn, "PixelSamplerType", 0), "Engine PixelSampler type", CBsetProp(scn, "PixelSamplerType"))
	Draw.Number("Pixelsamples:", evtNoEvt, 260, 100, 150, 18, getProp(scn, "SamplerPixelsamples", 4), 1, 512, "Number of samples per pixel", CBsetProp(scn, "SamplerPixelsamples"))

	Draw.Menu(strFilterType, evtNoEvt, 10, 70, 120, 18, getProp(scn, "FilterType", 0), "Engine pixel reconstruction filter type", CBsetProp(scn, "FilterType"))
	Draw.Number("X width:", evtNoEvt, 140, 70, 120, 18, getProp(scn, "FilterXWidth", 2), 1, 4, "Horizontal filter width", CBsetProp(scn, "FilterXWidth"))
	Draw.Number("Y width:", evtNoEvt, 260, 70, 120, 18, getProp(scn, "FilterYWidth", 2), 1, 4, "Vertical filter width", CBsetProp(scn, "FilterYWidth"))

##################  Draw RSettings  #########################	
def drawSystem():
	drawButtons()
	BGL.glColor3f(1.0,0.5,0.4)
	BGL.glRectf(330,182,410,183)
	BGL.glColor3f(0.9,0.9,0.9)
	scn = Scene.GetCurrent()
	Draw.String("Lux: ", evtNoEvt, 10, 160, 380, 18, getProp(scn, "LuxPath", ""), 50, "the file name of the Lux executable", CBsetProp(scn, "LuxPath"))
	Draw.Button("...", evtbrowselux, 392, 160, 20, 18, "Browse for the Lux executable")
	Draw.Number("Threads", evtNoEvt, 292, 130, 120, 18, getProp(scn, "Threads", 1), 1, 16, "Number of Threads used in Lux", CBsetProp(scn, "Threads"))
	Draw.Button("Save Defaults", evtSaveDefaults, 292, 80, 120, 38, "Save current settings as defaults for new scenes")
	Draw.Toggle("Save IGI", evtNoEvt, 10, 130, 80, 18, getProp(scn, "SaveIGI", 0), "Save untonemapped IGI file", CBsetProp(scn, "SaveIGI"))
	Draw.Number("Interval", evtNoEvt, 100, 130, 150, 18, getProp(scn, "SaveIGIInterval", 120), 20, 10000, "Set Interval for IGI file write (seconds)", CBsetProp(scn, "SaveIGIInterval"))
	Draw.Toggle("Save EXR", evtNoEvt, 10, 110, 80, 18, getProp(scn, "SaveEXR", 0), "Save untonemapped EXR file", CBsetProp(scn, "SaveEXR"))
	Draw.Number("Interval", evtNoEvt, 100,110,150,18, getProp(scn, "SaveEXRInterval", 120), 20, 10000, "Set Interval for EXR file write (seconds)", CBsetProp(scn, "SaveEXRInterval"))
	Draw.Toggle("Save TGA", evtNoEvt, 10, 90, 80, 18, getProp(scn, "SaveTGA", 0), "Save tonemapped TGA file", CBsetProp(scn, "SaveTGA"))
	Draw.Number("Interval", evtNoEvt, 100,90,150,18, getProp(scn, "SaveTGAInterval", 120), 20, 10000, "Set Interval for TGA file write (seconds)", CBsetProp(scn, "SaveTGAInterval"))
	BGL.glRasterPos2i(10, 70); Draw.Text("Display:", "small")	
	Draw.Number("Interval", evtNoEvt, 100, 70, 150, 18, getProp(scn, "DisplayInterval", 12), 5, 10000, "Set Interval for Display (seconds)", CBsetProp(scn, "DisplayInterval"))


#################  Draw Tonemapping  #########################
def drawTonemap():
	drawButtons()
	BGL.glColor3f(1.0,0.5,0.4)
	BGL.glRectf(250,182,330,183)
	BGL.glColor3f(0.9,0.9,0.9)
	scn = Scene.GetCurrent()
	Draw.Menu(strToneMapType, evtRedraw, 10, 150, 85, 18, getProp(scn, "ToneMapType", 1), "Set the type of the tonemapping", CBsetProp(scn, "ToneMapType"))
	if getProp(scn, "ToneMapType", 1) == 1:
		Draw.Number("Burn: ", evtNoEvt, 95, 150, 135, 18, getProp(scn, "ToneMapBurn", 6.0), 0.1, 12.0, "12.0: no burn out, 0.1 lot of burn out", CBsetProp(scn, "ToneMapBurn"))
		Draw.Number("PreS: ", evtNoEvt, 10, 130, 110, 18, getProp(scn, "ToneMapPreScale", 1.0), 0.01,100.0, "Pre Scale: See Lux Manual ;)", CBsetProp(scn, "ToneMapPreScale"))
		Draw.Number("PostS: ", evtNoEvt, 120, 130, 110, 18, getProp(scn, "ToneMapPostScale", 1.0), 0.01,100.0, "Post Scale: See Lux Manual ;)", CBsetProp(scn, "ToneMapPostScale"))
	
	Draw.Number("Output Gamma: ", evtNoEvt, 10, 100, 170, 18, getProp(scn, "OutputGamma", 2.2), 0.0, 6.0, "Output and RGC Gamma", CBsetProp(scn, "OutputGamma"))
	Draw.Toggle("RGC", evtNoEvt, 180, 100, 30, 18, getProp(scn, "RGC", 1), "Use reverse gamma correction for rgb values", CBsetProp(scn, "RGC"))
	Draw.Toggle("ColClamp", evtNoEvt, 210, 100, 60, 18, getProp(scn, "ColClamp", 0), "Scale/Clamp all colours to 0.0 - 0.9", CBsetProp(scn, "ColClamp"))
	Draw.Number("Output Dither: ", evtNoEvt, 270, 100, 150, 18, getProp(scn, "OutputDither", 0.0), 0.0, 1.0, "Output Image Dither", CBsetProp(scn, "OutputDither"))

	Draw.Toggle("Bloom", evtNoEvt, 10, 70, 80, 18, getProp(scn, "Bloom", 0), "Enable HDR Bloom", CBsetProp(scn, "Bloom"))
	Draw.Number("Width: ", evtNoEvt, 90, 70, 120, 18, getProp(scn, "BloomWidth", 0.1), 0.1, 2.0, "Amount of bloom", CBsetProp(scn, "BloomWidth"))
	Draw.Number("Radius: ", evtNoEvt, 210, 70, 120, 18, getProp(scn, "BloomRadius", 0.1), 0.1, 2.0, "Radius of the bloom filter", CBsetProp(scn, "BloomRadius"))

	
##############
def drawGUI():
##############

	global Screen
	
	if Screen==0:
		drawCamera()
 	if Screen==1:
 		drawEnv()
	if Screen==2:
		drawSettings()
 	if Screen==3:
   		drawSystem()
 	if Screen==4:
 		drawTonemap()

##################
def drawButtons():
##################

      ## buttons
	BGL.glColor3f(0.2,0.2,0.2)
	BGL.glRectf(0,0,440,230)
	BGL.glColor3f(0.9,0.9,0.9);BGL.glRasterPos2i(10,205); Draw.Text("LuxBlend v0.1alphaCVS", "small")
	scn = Scene.GetCurrent()
	
	Draw.Button("Render", evtExport, 10, 25, 100, 30, "Open file dialog and export")
	if getProp(scn, "ExecuteLux", 0) == 0:
		Draw.Button("Export Anim", evtExportAnim, 112, 25, 100, 30, "Open file dialog and export animation (careful: takes a lot of diskspace!!!)")
	Draw.Button("Camera", openCamera, 10, 185, 80, 13, "Open Camera Dialog")
	Draw.Button("Environment", openEnv, 90, 185, 80, 13, "Open Environment Dialog")
	Draw.Button("Renderer", openRSet, 170, 185, 80, 13, "Open Rendersettings Dialog")
	Draw.Button("Tonemap", openTmap, 250, 185, 80, 13, "open Tonemap Settings")
	Draw.Button("System", openSSet, 330, 185, 80, 13, "open System Settings")
	
	Draw.Toggle("Run", evtRedraw, 10, 5, 30, 13, getProp(scn, "ExecuteLux", 0), "Execute Lux after saving", CBsetProp(scn, "ExecuteLux"))
	Draw.Toggle("def",evtNoEvt,41,5,30,13, getProp(scn, "DefaultExport", 0), "Save as default.lxs to a temporary directory", CBsetProp(scn, "DefaultExport"))
	Draw.Toggle(".lxs" ,evtNoEvt,77,5,30,13, getProp(scn, "ExportScene", 1), "Export Scenefile", CBsetProp(scn, "ExportScene"))
	Draw.Toggle(".lxo" ,evtNoEvt,107,5,30,13, getProp(scn, "ExportGeom", 1), "Export Geometryfile", CBsetProp(scn, "ExportGeom"))
	Draw.Toggle(".lxm" ,evtNoEvt,137,5,30,13, getProp(scn, "ExportMat", 1), "Export Materialfile", CBsetProp(scn, "ExportMat"))
	BGL.glColor3f(0.9, 0.9, 0.9) ; BGL.glRasterPos2i(340,7) ; Draw.Text("Press Q or ESC to quit.", "tiny")
	
		
def event(evt, val):  # function that handles keyboard and mouse events
	if evt == Draw.ESCKEY or evt == Draw.QKEY:
		stop = Draw.PupMenu("OK?%t|Cancel export %x1")
		if stop == 1:
			Draw.Exit()
			return

def setEnvMap(efilename):
	setProp(Scene.GetCurrent(), "EnvFile", efilename)

def setLuxPath(efilename):
	setProp(Scene.GetCurrent(), "LuxPath", efilename)
	
def buttonEvt(evt):  # function that handles button events
	
	global Screen, EnFile
	
	if evt == evtRedraw:
		Draw.Redraw()

	if evt == evtExport:
		if getProp(Scene.GetCurrent(), "DefaultExport", 0) == 0:
			Blender.Window.FileSelector(save_still, "Export", newFName('lxs'))
		else:
			datadir=Blender.Get("datadir")
			filename = datadir + os.sep + "default.lxs"
			save_still(filename)
	
	if evt == evtExportAnim:
		Blender.Window.FileSelector(save_anim, "Export Animation", newFName('lxs'))
		Draw.Redraw()
				
	if evt == openCamera:
		Screen = 0
		Draw.Redraw()
	
	if evt == openEnv:
		Screen = 1
		Draw.Redraw()
		
	if evt == openRSet:
		Screen = 2
		Draw.Redraw()
	
	if evt == openSSet:
		Screen = 3
		Draw.Redraw()
	
	if evt == openTmap:
		Screen = 4
		Draw.Redraw()
	
	if evt == evtloadimg:
		Blender.Window.FileSelector(setEnvMap, "Load Environment Map", ('.exr'))
		Draw.Redraw()
	
	if evt == evtFocusS:
		setFocus("S")
		Draw.Redraw()

	if evt == evtFocusC:
		setFocus("C")
		Draw.Redraw()

	if evt == evtbrowselux:
		Blender.Window.FileSelector(setLuxPath, "Lux executable", ('.exe'))
		Draw.Redraw()

	if evt == evtSaveDefaults:
		Blender.Registry.SetKey('BlenderLux', newrdict, True)
		rdict = newrdict


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
	camObj.data.dofDist = (camDir[0]*dist[0]+camDir[1]*dist[1]+camDir[2]*dist[2])/camDir.length


Screen = 0
Draw.Register(drawGUI, event, buttonEvt)
if sys.exists(getProp(Scene.GetCurrent(), "LuxPath", ""))<=0:
	Screen = 3
	Draw.Redraw()
	Draw.PupMenu("Please setup path to the lux render software and press \"save defaults\" button%t|Ok")

