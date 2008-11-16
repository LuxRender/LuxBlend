import Blender
from Blender import Image
from Blender import Draw, BGL

fn = "C:\\lux\\luxgui\\luxblend\\new_icons\\filter.png"

img = Image.Load(fn)
ofn = Blender.sys.makename(fn, '.txt')

def base64char(value):
       if value < 26: return chr(65+value)
       if value < 52: return chr(97-26+value)
       if value < 62: return chr(48-52+value)
       if value == 62: return '+'
       return '/'

def base64value(char):
       if ord(char) in range(65, 91): return ord(char)-65
       if ord(char) in range(97, 123): return ord(char)-97+26
       if ord(char) in range(48, 58): return ord(char)-48+52
       if char == '+': return 62
       return 63

s = ""
for y in range(16):
       for x in range(16):
	       print x
	       print y
               col = img.getPixelI(x, y)
               for c in range(4):
                       s += base64char(int(col[c]/4))

file = open(ofn, 'w')
file.write(s+"\n")
file.close()
print s
