#
#   sculptmaker.py 
#
#   Generation of Second Life terrain impostors from elevation data.
#   
#   Animats
#   October, 2020
#
#   License: GPL
#
#
import PIL
import PIL.Image
import PIL.ImageStat
import PIL.ImageFilter
import PIL.ImageOps
import math
import numpy
import argparse
import json


#   
#   TerrainSculpt -- one terrain object
#
class TerrainSculpt:
    """
    One terrain object
    """
    SCULPTDIM = 64                      # sculpt textures are always 64x64

    def __init__(self, region) :
        self.region = region
        self.image = None               # the image
        self.elevs = None               # 2D array of elevations
        self.pixels = None              # 2D array of pixel values
        self.zheight = None             # Z value range
        self.zoffset = None             # Smallest Z value 
        self.waterheight = None;        # Z < this is underwater.

    def makeimage(self) :
        """
        Process elevation info into integer form
        
        Must be in final size at this point.
        """
        maxz = self.elevs.max()                         # get bounds
        minz = self.elevs.min() 
        self.zheight = maxz - minz
        self.zoffset = minz
        print("Z bounds: %3.2f to %3.2f" % (minz, maxz))        # ***TEMP***    
        #   Create image
        img = PIL.Image.new("RGB",self.elevs.shape)             # create blank image
        pix = img.load()                                        # force into memory
        for x in range(self.elevs.shape[0]) :                   # make a pyramid 1-high
            for y in range(self.elevs.shape[1]) :
                zscaled = (self.elevs[x,y] - self.zoffset) / self.zheight # into 0..1 range
                assert(zscaled >= 0.0)                          # verify range scaling
                assert(zscaled <= 1.0)
                zpixel = max(0,min(255,math.floor(zscaled*256)))# round down
                ####print("z=",zscaled, zpixel)
                xpixel = int((x*256) / self.elevs.shape[0])
                ypixel = int((y*256) / self.elevs.shape[1])
                #   Elevs is ordered with +Y as north, but sculpt images have to be flipped in Y
                #   to get the UVs right and the sculpt not inside out.
                ####pix[x,self.elevs.shape[1]-y-1] = (xpixel, 255-ypixel, zpixel)             # into 0..255 range
                pix[x,self.elevs.shape[1]-y-1] = (xpixel, ypixel, zpixel)             # into 0..255 range
        self.image = img
        
    def setelevs(self, elevs, inputscale, inputoffset) :
        """
        Set elevation array into object.
        
        Resizes elevation array to match SCULPDTIM.
        Interpolates, but uses the minimum value so sculpt is always below real terrain
        We usually capture 65 data points in each axis when scanning a region,
        with the data points at the edges of each cell.
        Data points at the edges must be from the original data so 
        that adjacent sculpts will match.
        
        Check: x = 0, xfract must be 0
               x = SCULPTDIM, xfract must be self.elevs.scale[0]-1
        """
        if elevs.shape == (TerrainSculpt.SCULPTDIM, TerrainSculpt.SCULPTDIM) :
            self.elevs = numpy.array(elevs,dtype=float)         # use input array
            return;                                             # no need to interpolate
        newelevs = numpy.zeros((TerrainSculpt.SCULPTDIM, TerrainSculpt.SCULPTDIM),dtype=float)  # new interpolated elevs
        for x in range(TerrainSculpt.SCULPTDIM) :               # construct interpolated version
            for y in range(TerrainSculpt.SCULPTDIM) :           # iterate over output space
                xfract = (x / TerrainSculpt.SCULPTDIM) * elevs.shape[0] # fractional subscript for input
                yfract = (y / TerrainSculpt.SCULPTDIM) * elevs.shape[1] 
                xfract = min(elevs.shape[0]-1,xfract)           # avoid roundoff trouble at bounds
                yfract = min(elevs.shape[1]-1,yfract)           # avoid roundoff trouble at bounds
                z0 = elevs[math.floor(xfract), math.floor(yfract)] 
                z1 = elevs[math.floor(xfract), math.ceil(yfract)]
                z2 = elevs[math.ceil(xfract), math.floor(yfract)]
                z3 = elevs[math.ceil(xfract), math.ceil(yfract)]   
                z = min(z0,z1,z2,z3)
                newelevs[x,y] = z * (inputscale/256.0) + inputoffset    # interpolated scaled value        
        self.elevs = newelevs                                   # matrix of actual altitudes
                
    def pyramidtest(self) :
        """
        Generates dummy pyramid as a test
        """
        self.elevs = numpy.zeros((TerrainSculpt.SCULPTDIM, TerrainSculpt.SCULPTDIM))             # empty array
        halfway = TerrainSculpt.SCULPTDIM*0.5
        for x in range(TerrainSculpt.SCULPTDIM) :     # make a pyramid 1-high
            for y in range(TerrainSculpt.SCULPTDIM) :
                z1 = halfway - abs(halfway-x)
                z2 = halfway - abs(halfway-y)
                z = min(z1,z2) / halfway   # range 0..1 on output
                self.elevs[x,y] = z
                
                
def unpackelev(elev) :
    """
    Unpack elevation data stored as 2-character hex
    """
    ####print("elev: %s length: %d" % (elev, len(elev)))
    return [int(elev[n*2:n*2+2],16) for n in range(int(len(elev)/2))]
                

def handlefile(filename, outprefix) :
    """
    Process each file containing JSON from an email from the terrain scanner
    """
    with open(filename,"r") as infile :
        s = infile.read()               # read entire file
        pos = s.find("\n{")             # find beginning of JSON
        if (pos < 1) :
            raise RuntimeError("Unable to find JSON data in file \"%s\"" % (filename))
        s = s[pos-1:-1]                 # trim off beginning of email
        ####print(s)                        # ***TEMP***
        jsn = json.loads(s)             # parse into JSON.
        elevs = jsn["elevs"]            # elevation data
        scale = float(jsn["scale"])
        offset = float(jsn["offset"])
        region = jsn["region"]          # region name
        rows = [unpackelev(s) for s in elevs] # Rows, X going fastest
        ####elevarray = numpy.transpose(numpy.array(rows))   # convert to numpy array
        elevarray = numpy.array(rows)   # convert to numpy array
        ####print(elevarray)
        print("Region: %s scale: %1.3f  offset %1.3f" % (region,scale,offset))
        #   Create object for sculpt image
        sculpt = TerrainSculpt(region);       # empty object
        sculpt.setelevs(elevarray, scale,offset)      # set elevations
        sculpt.makeimage()    
        ###sculpt.image.show()  
        #   Create output file
        outfile = outprefix + region + ".png"
        sculpt.image.save(outfile,"png") # write output file  
    

        
def testmain() :
    """
    Unit test
    """
    fname = "/tmp/sculpttest.png"
    sculpt = TerrainSculpt()
    sculpt.pyramidtest()                # make a pyramid
    sculpt.makeimage()                  # process
    sculpt.image.show()
    sculpt.image.save(fname,"png")  # test output
    print("Wrote ", fname)
    
####testmain()                              # ***TEMP***
#
#   Process input files generated by LSL scans of Second Life terrain
#
def main() :
    outprefix = "/tmp/terrainsculpt-"       # output filename prefix
    parser = argparse.ArgumentParser(description='Process sim terrain scans')
    parser.add_argument('filenames', nargs='+',
                    help='Emails from terrain scans')
    args = parser.parse_args()
    print(args.filenames)
    for filename in args.filenames :        # do each file
        handlefile(filename, outprefix)

main()              
 
