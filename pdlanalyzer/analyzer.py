#
# pkpgcounter : a generic Page Description Language parser
#
# (c) 2003,2004,2005 Jerome Alet <alet@librelogiciel.com>
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
# 
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 59 Temple Place, Suite 330, Boston, MA 02111-1307, USA.
#
# $Id$
#

import sys
import tempfile

from pdlanalyzer import pdlparser, postscript, pdf, pcl345, pclxl, escp2

KILOBYTE = 1024    
MEGABYTE = 1024 * KILOBYTE    
LASTBLOCKSIZE = int(KILOBYTE / 4)

class PDLAnalyzer :    
    """Class for PDL autodetection."""
    def __init__(self, filename, debug=0) :
        """Initializes the PDL analyzer.
        
           filename is the name of the file or '-' for stdin.
           filename can also be a file-like object which 
           supports read() and seek().
        """
        self.debug = debug
        self.filename = filename
        try :
            import psyco 
        except ImportError :    
            sys.stderr.write("pkpgcounter : you should install psyco if possible, this would greatly speedup parsing.\n")
            pass # Psyco is not installed
        else :    
            # Psyco is installed, tell it to compile
            # the CPU intensive methods : PCL and PCLXL
            # parsing will greatly benefit from this, 
            # for PostScript and PDF the difference is
            # barely noticeable since they are already
            # almost optimal, and much more speedy anyway.
            psyco.bind(postscript.PostScriptParser.getJobSize)
            psyco.bind(pdf.PDFParser.getJobSize)
            psyco.bind(escp2.ESCP2Parser.getJobSize)
            psyco.bind(pcl345.PCL345Parser.getJobSize)
            psyco.bind(pclxl.PCLXLParser.getJobSize)
        
    def getJobSize(self) :    
        """Returns the job's size."""
        self.openFile()
        try :
            pdlhandler = self.detectPDLHandler()
        except pdlparser.PDLParserError, msg :    
            self.closeFile()
            raise pdlparser.PDLParserError, "ERROR : Unknown file format for %s (%s)" % (self.filename, msg)
        else :
            try :
                size = pdlhandler(self.infile, self.debug).getJobSize()
            finally :    
                self.closeFile()
            return size
        
    def openFile(self) :    
        """Opens the job's data stream for reading."""
        self.mustclose = 0  # by default we don't want to close the file when finished
        if hasattr(self.filename, "read") and hasattr(self.filename, "seek") :
            # filename is in fact a file-like object 
            infile = self.filename
        elif self.filename == "-" :
            # we must read from stdin
            infile = sys.stdin
        else :    
            # normal file
            self.infile = open(self.filename, "rb")
            self.mustclose = 1
            return
            
        # Use a temporary file, always seekable contrary to standard input.
        self.infile = tempfile.TemporaryFile(mode="w+b")
        while 1 :
            data = infile.read(MEGABYTE) 
            if not data :
                break
            self.infile.write(data)
        self.infile.flush()    
        self.infile.seek(0)
            
    def closeFile(self) :        
        """Closes the job's data stream if we can close it."""
        if self.mustclose :
            self.infile.close()    
        else :    
            # if we don't have to close the file, then
            # ensure the file pointer is reset to the 
            # start of the file in case the process wants
            # to read the file again.
            try :
                self.infile.seek(0)
            except :    
                pass    # probably stdin, which is not seekable
        
    def isPostScript(self, sdata, edata) :    
        """Returns 1 if data is PostScript, else 0."""
        if sdata.startswith("%!") or \
           sdata.startswith("\004%!") or \
           sdata.startswith("\033%-12345X%!PS") or \
           ((sdata[:128].find("\033%-12345X") != -1) and \
             ((sdata.find("LANGUAGE=POSTSCRIPT") != -1) or \
              (sdata.find("LANGUAGE = POSTSCRIPT") != -1) or \
              (sdata.find("LANGUAGE = Postscript") != -1))) or \
              (sdata.find("%!PS-Adobe") != -1) :
            if self.debug :  
                sys.stderr.write("%s is a PostScript file\n" % str(self.filename))
            return 1
        else :    
            return 0
        
    def isPDF(self, sdata, edata) :    
        """Returns 1 if data is PDF, else 0."""
        if sdata.startswith("%PDF-") or \
           sdata.startswith("\033%-12345X%PDF-") or \
           ((sdata[:128].find("\033%-12345X") != -1) and (sdata.upper().find("LANGUAGE=PDF") != -1)) or \
           (sdata.find("%PDF-") != -1) :
            if self.debug :  
                sys.stderr.write("%s is a PDF file\n" % str(self.filename))
            return 1
        else :    
            return 0
        
    def isPCL(self, sdata, edata) :    
        """Returns 1 if data is PCL, else 0."""
        if sdata.startswith("\033E\033") or \
           (sdata.startswith("\033*rbC") and (not edata[-3:] == "\f\033@")) or \
           sdata.startswith("\033%8\033") or \
           (sdata.find("\033%-12345X") != -1) :
            if self.debug :  
                sys.stderr.write("%s is a PCL3/4/5 file\n" % str(self.filename))
            return 1
        else :    
            return 0
        
    def isPCLXL(self, sdata, edata) :    
        """Returns 1 if data is PCLXL aka PCL6, else 0."""
        if ((sdata[:128].find("\033%-12345X") != -1) and \
             (sdata.find(" HP-PCL XL;") != -1) and \
             ((sdata.find("LANGUAGE=PCLXL") != -1) or \
              (sdata.find("LANGUAGE = PCLXL") != -1))) :
            if self.debug :  
                sys.stderr.write("%s is a PCLXL (aka PCL6) file\n" % str(self.filename))
            return 1
        else :    
            return 0
            
    def isESCP2(self, sdata, edata) :        
        """Returns 1 if data is ESC/P2, else 0."""
        if sdata.startswith("\033@") or \
           sdata.startswith("\033*") or \
           sdata.startswith("\n\033@") or \
           sdata.startswith("\0\0\0\033\1@EJL") : # ESC/P Raster ??? Seen on Stylus Photo 1284
            if self.debug :  
                sys.stderr.write("%s is an ESC/P2 file\n" % str(self.filename))
            return 1
        else :    
            return 0
    
    def detectPDLHandler(self) :    
        """Tries to autodetect the document format.
        
           Returns the correct PDL handler class or None if format is unknown
        """   
        # Try to detect file type by reading first block of datas    
        self.infile.seek(0)
        firstblock = self.infile.read(4 * KILOBYTE)
        try :
            self.infile.seek(-LASTBLOCKSIZE, 2)
            lastblock = self.infile.read(LASTBLOCKSIZE)
        except IOError :    
            lastblock = ""
        self.infile.seek(0)
        if self.isPostScript(firstblock, lastblock) :
            return postscript.PostScriptParser
        elif self.isPCLXL(firstblock, lastblock) :    
            return pclxl.PCLXLParser
        elif self.isPDF(firstblock, lastblock) :    
            return pdf.PDFParser
        elif self.isPCL(firstblock, lastblock) :    
            return pcl345.PCL345Parser
        elif self.isESCP2(firstblock, lastblock) :    
            return escp2.ESCP2Parser
        else :    
            raise pdlparser.PDLParserError, "Analysis of first data block failed."
            
def main() :    
    """Entry point for PDL Analyzer."""
    if (len(sys.argv) < 2) or ((not sys.stdin.isatty()) and ("-" not in sys.argv[1:])) :
        sys.argv.append("-")
        
    if ("-h" in sys.argv[1:]) or ("--help" in sys.argv[1:]) :
        print "usage : pkpgcounter file1 file2 ... fileN"
    elif ("-v" in sys.argv[1:]) or ("--version" in sys.argv[1:]) :
        print "%s" % version.__version__
    else :
        totalsize = 0    
        debug = 0
        minindex = 1
        if sys.argv[1] == "--debug" :
            minindex = 2
            debug = 1
        for arg in sys.argv[minindex:] :
            try :
                parser = PDLAnalyzer(arg, debug)
                totalsize += parser.getJobSize()
            except pdlparser.PDLParserError, msg :    
                sys.stderr.write("ERROR: %s\n" % msg)
                sys.stderr.flush()
        print "%s" % totalsize
    
if __name__ == "__main__" :    
    main()