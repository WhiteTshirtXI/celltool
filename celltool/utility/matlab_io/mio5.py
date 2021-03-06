''' Classes for read / write of matlab (TM) 5 files
'''

# Small fragments of current code adapted from matfile.py by Heiko
# Henkelmann

## Notice in matfile.py file

# Copyright (c) 2003 Heiko Henkelmann

# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to
# deal in the Software without restriction, including without limitation the
# rights to use, copy, modify, merge, publish, distribute, sublicense, and/or
# sell copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:

# The above copyright notice and this permission notice shall be included in
# all copies or substantial portions of the Software.

# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING
# FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER
# DEALINGS IN THE SOFTWARE.

import zlib
from copy import copy as pycopy
from cStringIO import StringIO
import numpy as N

from miobase import *

try:  # Python 2.3 support
    from sets import Set as set
except:
    pass

miINT8 = 1
miUINT8 = 2
miINT16 = 3
miUINT16 = 4
miINT32 = 5
miUINT32 = 6
miSINGLE = 7
miDOUBLE = 9
miINT64 = 12
miUINT64 = 13
miMATRIX = 14
miCOMPRESSED = 15
miUTF8 = 16
miUTF16 = 17
miUTF32 = 18

mxCELL_CLASS = 1
mxSTRUCT_CLASS = 2
mxOBJECT_CLASS = 3
mxCHAR_CLASS = 4
mxSPARSE_CLASS = 5
mxDOUBLE_CLASS = 6
mxSINGLE_CLASS = 7
mxINT8_CLASS = 8
mxUINT8_CLASS = 9
mxINT16_CLASS = 10
mxUINT16_CLASS = 11
mxINT32_CLASS = 12
mxUINT32_CLASS = 13

mdtypes_template = {
    miINT8: 'i1',
    miUINT8: 'u1',
    miINT16: 'i2',
    miUINT16: 'u2',
    miINT32: 'i4',
    miUINT32: 'u4',
    miSINGLE: 'f4',
    miDOUBLE: 'f8',
    miINT64: 'i8',
    miUINT64: 'u8',
    miUTF8: 'u1',
    miUTF16: 'u2',
    miUTF32: 'u4',
    'file_header': [('description', 'S116'),
                    ('subsystem_offset', 'i8'),
                    ('version', 'u2'),
                    ('endian_test', 'S2')],
    'tag_full': [('mdtype', 'u4'), ('byte_count', 'u4')],
    'tag_compressed':[('byte_count_mdtype', 'u4'), ('data', 'S4')],
    'array_flags': [('data_type', 'u4'),
                    ('byte_count', 'u4'),
                    ('flags_class','u4'),
                    ('nzmax', 'u4')],
    'U1': 'U1',
    }

mclass_dtypes_template = {
    mxINT8_CLASS: 'i1',
    mxUINT8_CLASS: 'u1',
    mxINT16_CLASS: 'i2',
    mxUINT16_CLASS: 'u2',
    mxINT32_CLASS: 'i4',
    mxUINT32_CLASS: 'u4',
    mxSINGLE_CLASS: 'f4',
    mxDOUBLE_CLASS: 'f8',
    }


np_to_mtypes = {
    'f8': miDOUBLE,
    'c32': miDOUBLE,
    'c24': miDOUBLE,
    'c16': miDOUBLE,
    'f4': miSINGLE,
    'c8': miSINGLE,
    'i1': miINT8,
    'i2': miINT16,
    'i4': miINT32,
    'u1': miUINT8,
    'u4': miUINT32,
    'u2': miUINT16,
    'S1': miUINT8,
    'U1': miUTF16,
    }


np_to_mxtypes = {
    'f8': mxDOUBLE_CLASS,
    'c32': mxDOUBLE_CLASS,
    'c24': mxDOUBLE_CLASS,
    'c16': mxDOUBLE_CLASS,
    'f4': mxSINGLE_CLASS,
    'c8': mxSINGLE_CLASS,
    'i4': mxINT32_CLASS,
    'i2': mxINT16_CLASS,
    'u2': mxUINT16_CLASS,
    'u1': mxUINT8_CLASS,
    'S1': mxUINT8_CLASS,
    }



''' Before release v7.1 (release 14) matlab (TM) used the system
default character encoding scheme padded out to 16-bits. Release 14
and later use Unicode. When saving character data, R14 checks if it
can be encoded in 7-bit ascii, and saves in that format if so.'''

codecs_template = {
    miUTF8: {'codec': 'utf_8', 'width': 1},
    miUTF16: {'codec': 'utf_16', 'width': 2},
    miUTF32: {'codec': 'utf_32','width': 4},
    }

miUINT16_codec = sys.getdefaultencoding()

mx_numbers = (
    mxDOUBLE_CLASS,
    mxSINGLE_CLASS,
    mxINT8_CLASS,
    mxUINT8_CLASS,
    mxINT16_CLASS,
    mxUINT16_CLASS,
    mxINT32_CLASS,
    mxUINT32_CLASS,
    )

class mat_struct(object):
    ''' Placeholder for holding read data from structs '''
    pass

class mat_obj(object):
    ''' Placeholder for holding read data from objects '''
    pass

class Mat5ArrayReader(MatArrayReader):
    ''' Class to get Mat5 arrays

    Provides element reader functions, header reader, matrix reader
    factory function
    '''

    def __init__(self, mat_stream, dtypes, processor_func, codecs, class_dtypes):
        super(Mat5ArrayReader, self).__init__(mat_stream,
                                              dtypes,
                                              processor_func,
                                              )
        self.codecs = codecs
        self.class_dtypes = class_dtypes

    def read_element(self, copy=True):
        raw_tag = self.mat_stream.read(8)
        tag = N.ndarray(shape=(),
                        dtype=self.dtypes['tag_full'],
                        buffer=raw_tag)
        mdtype = tag['mdtype'].item()
        byte_count = tag['byte_count'].item()
        
        if mdtype == miMATRIX:
            # can't fit a matrix in a 4 byte compressed element, so no 
            # need to worry about making sure that the getters handle the
            # compressed data element case properly. (I hope...)
            return self.current_getter(byte_count).get_array()
        
        upper, lower = mdtype >> 16, mdtype & 0xFFFF
        if upper != 0: # we have a compressed data element
            byte_count = upper
            if byte_count > 4:
                raise ValueError('Compressed data elements must contain 4 or fewer bytes.')
            mdtype = lower
            raw_str = raw_tag[4:byte_count+4]
        else: # regular data element
            raw_str = self.mat_stream.read(byte_count)
            # Seek to next 64-bit boundary
            mod8 = byte_count % 8
            if mod8:
                self.mat_stream.seek(8 - mod8, 1)

        if mdtype in self.codecs: # encoded char data
            codec = self.codecs[mdtype]
            if not codec:
                raise TypeError, 'Do not support encoding %d' % mdtype
            el = raw_str.decode(codec)
        else: # numeric data
            dt = self.dtypes[mdtype]
            el_count = byte_count // dt.itemsize
            el = N.ndarray(shape=(el_count,),
                         dtype=dt,
                         buffer=raw_str)
            if copy:
                el = el.copy()

        return el    

    def matrix_getter_factory(self):
        ''' Returns reader for next matrix at top level '''
        tag = self.read_dtype(self.dtypes['tag_full'])
        mdtype = tag['mdtype'].item()
        byte_count = tag['byte_count'].item()
        next_pos = self.mat_stream.tell() + byte_count
        if mdtype == miCOMPRESSED:
            getter = Mat5ZArrayReader(self, byte_count).matrix_getter_factory()
        elif not mdtype == miMATRIX:
            raise TypeError, \
                  'Expecting miMATRIX type here, got %d' %  mdtype
        else:
            getter = self.current_getter(byte_count)
        getter.next_position = next_pos
        return getter

    def current_getter(self, byte_count):
        ''' Return matrix getter for current stream position

        Returns matrix getters at top level and sub levels
        '''
        if not byte_count: # an empty miMATRIX can contain no bytes
            return Mat5EmptyMatrixGetter(self)
        af = self.read_dtype(self.dtypes['array_flags'])
        header = {}
        flags_class = af['flags_class']
        mc = flags_class & 0xFF
        header['mclass'] = mc
        header['is_logical'] = flags_class >> 9 & 1
        header['is_global'] = flags_class >> 10 & 1
        header['is_complex'] = flags_class >> 11 & 1
        header['nzmax'] = af['nzmax']
        header['dims'] = self.read_element()
        header['name'] = self.read_element().tostring()
        if mc in mx_numbers:
            return Mat5NumericMatrixGetter(self, header)
        if mc == mxSPARSE_CLASS:
            return Mat5SparseMatrixGetter(self, header)
        if mc == mxCHAR_CLASS:
            return Mat5CharMatrixGetter(self, header)
        if mc == mxCELL_CLASS:
            return Mat5CellMatrixGetter(self, header)
        if mc == mxSTRUCT_CLASS:
            return Mat5StructMatrixGetter(self, header)
        if mc == mxOBJECT_CLASS:
            return Mat5ObjectMatrixGetter(self, header)
        raise TypeError, 'No reader for class code %s' % mc


class Mat5ZArrayReader(Mat5ArrayReader):
    ''' Getter for compressed arrays

    Reads and uncompresses gzipped stream on init, providing wrapper
    for this new sub-stream.
    '''
    def __init__(self, array_reader, byte_count):
        '''Reads and uncompresses gzipped stream'''
        data = array_reader.mat_stream.read(byte_count)
        super(Mat5ZArrayReader, self).__init__(
            StringIO(zlib.decompress(data)),
            array_reader.dtypes,
            array_reader.processor_func,
            array_reader.codecs,
            array_reader.class_dtypes)


class Mat5MatrixGetter(MatMatrixGetter):
    ''' Base class for getting Mat5 matrices

    Gets current read information from passed array_reader
    '''

    def __init__(self, array_reader, header):
        super(Mat5MatrixGetter, self).__init__(array_reader, header)
        self.class_dtypes = array_reader.class_dtypes
        self.codecs = array_reader.codecs
        self.is_global = header['is_global']
        self.mat_dtype = None

    def read_element(self, *args, **kwargs):
        return self.array_reader.read_element(*args, **kwargs)


class Mat5EmptyMatrixGetter(Mat5MatrixGetter):
    ''' Dummy class to return empty array for empty matrix
    '''
    def __init__(self, array_reader):
        self.array_reader = array_reader
        self.mat_stream = array_reader.mat_stream
        self.data_position = self.mat_stream.tell()
        self.header = {}
        self.is_global = False
        self.mat_dtype = 'f8'

    def get_raw_array(self):
        return N.array([[]])


class Mat5NumericMatrixGetter(Mat5MatrixGetter):

    def __init__(self, array_reader, header):
        super(Mat5NumericMatrixGetter, self).__init__(array_reader, header)
        if header['is_logical']:
            self.mat_dtype = N.dtype('bool')
        else:
            self.mat_dtype = self.class_dtypes[header['mclass']]

    def get_raw_array(self):
        if self.header['is_complex']:
            # avoid array copy to save memory
            res = self.read_element(copy=False)
            res_j = self.read_element(copy=False)
            res = res + (res_j * 1j)
        else:
            res = self.read_element()
        return N.ndarray(shape=self.header['dims'],
                       dtype=res.dtype,
                       buffer=res,
                       order='F')


class Mat5SparseMatrixGetter(Mat5MatrixGetter):
    def get_raw_array(self):
        rowind = self.read_element()
        indptr = self.read_element()
        if self.header['is_complex']:
            # avoid array copy to save memory
            data   = self.read_element(copy=False)
            data_j = self.read_element(copy=False)
            data = data + (data_j * 1j)
        else:
            data = self.read_element()
        ''' From the matlab (TM) API documentation, last found here:
        http://www.mathworks.com/access/helpdesk/help/techdoc/matlab_external/
        rowind are simply the row indices for all the (nnz) non-zero
        entries in the sparse array.  rowind has nzmax entries, so
        may well have more entries than nnz, the actual number
        of non-zero entries, but rowind[nnz:] can be discarded
        and should be 0. indptr has length (number of columns + 1),
        and is such that, if D = diff(colind), D[j] gives the number
        of non-zero entries in column j. Because rowind values are
        stored in column order, this gives the column corresponding to
        each rowind
        '''
        M,N = self.header['dims']
        indptr = indptr[:N+1]
        nnz = indptr[-1]
        rowind = rowind[:nnz]
        data   = data[:nnz]
        # if have_sparse:
        #     from scipy.sparse import csc_matrix
        #     return csc_matrix((data,rowind,indptr), shape=(M,N))
        # else:
        #     return (dims, data, rowind, indptr)
        return (dims, data, rowind, indptr)

class Mat5CharMatrixGetter(Mat5MatrixGetter):
    def get_raw_array(self):
        res = self.read_element()
        # Convert non-string types to unicode
        if isinstance(res, N.ndarray):
            if res.dtype.type == N.uint16:
                codec = miUINT16_codec
                if self.codecs['uint16_len'] == 1:
                    res = res.astype(N.uint8)
            elif res.dtype.type in (N.uint8, N.int8):
                codec = 'ascii'
            else:
                raise TypeError, 'Did not expect type %s' % res.dtype
            res = res.tostring().decode(codec)
        return N.ndarray(shape=self.header['dims'],
                       dtype=N.dtype('U1'),
                       buffer=N.array(res),
                       order='F').copy()


class Mat5CellMatrixGetter(Mat5MatrixGetter):
    def get_raw_array(self):
        # Account for fortran indexing of cells
        tupdims = tuple(self.header['dims'][::-1])
        length = N.product(tupdims)
        result = N.empty(length, dtype=object)
        for i in range(length):
            result[i] = self.get_item()
        return result.reshape(tupdims).T

    def get_item(self):
        return self.read_element()


class Mat5StructMatrixGetter(Mat5CellMatrixGetter):
    def __init__(self, *args, **kwargs):
        super(Mat5StructMatrixGetter, self).__init__(*args, **kwargs)
        self.obj_template = mat_struct()

    def get_raw_array(self):
        namelength = self.read_element()[0]
        # get field names
        names = self.read_element()
        splitnames = [names[i:i+namelength] for i in \
                      xrange(0,len(names),namelength)]
        self.obj_template._fieldnames = [x.tostring().strip('\x00')
                                        for x in splitnames]
        return super(Mat5StructMatrixGetter, self).get_raw_array()

    def get_item(self):
        item = pycopy(self.obj_template)
        for element in item._fieldnames:
            item.__dict__[element]  = self.read_element()
        return item


class Mat5ObjectMatrixGetter(Mat5StructMatrixGetter):
    def __init__(self, *args, **kwargs):
        super(Mat5StructMatrixGetter, self).__init__(*args, **kwargs)
        self.obj_template = mat_obj()

    def get_raw_array(self):
        self.obj_template._classname = self.read_element().tostring()
        return super(Mat5ObjectMatrixGetter, self).get_raw_array()


class MatFile5Reader(MatFileReader):
    ''' Reader for Mat 5 mat files

    Adds the following attribute to base class

    uint16_codec       - char codec to use for uint16 char arrays
                          (defaults to system default codec)
   '''

    def __init__(self,
                 mat_stream,
                 byte_order=None,
                 mat_dtype=False,
                 squeeze_me=False,
                 chars_as_strings=True,
                 matlab_compatible=False,
                 uint16_codec=None
                 ):
        self.codecs = {}
        self._array_reader = Mat5ArrayReader(
            mat_stream,
            None,
            None,
            None,
            None,
            )
        super(MatFile5Reader, self).__init__(
            mat_stream,
            byte_order,
            mat_dtype,
            squeeze_me,
            chars_as_strings,
            matlab_compatible,
            )
        self._array_reader.processor_func = self.processor_func
        self.uint16_codec = uint16_codec

    def get_uint16_codec(self):
        return self._uint16_codec
    def set_uint16_codec(self, uint16_codec):
        if not uint16_codec:
            uint16_codec = sys.getdefaultencoding()
        # Set length of miUINT16 char encoding
        self.codecs['uint16_len'] = len("  ".encode(uint16_codec)) \
                               - len(" ".encode(uint16_codec))
        self.codecs['uint16_codec'] = uint16_codec
        self._array_reader.codecs = self.codecs
        self._uint16_codec = uint16_codec
    uint16_codec = property(get_uint16_codec,
                            set_uint16_codec,
                            None,
                            'get/set uint16_codec')

    def set_dtypes(self):
        ''' Set dtypes and codecs '''
        self.dtypes = self.convert_dtypes(mdtypes_template)
        self.class_dtypes = self.convert_dtypes(mclass_dtypes_template)
        codecs = {}
        postfix = self.order_code == '<' and '_le' or '_be'
        for k, v in codecs_template.items():
            codec = v['codec']
            try:
                " ".encode(codec)
            except LookupError:
                codecs[k] = None
                continue
            if v['width'] > 1:
                codec += postfix
            codecs[k] = codec
        self.codecs.update(codecs)
        self.update_array_reader()

    def update_array_reader(self):
        self._array_reader.codecs = self.codecs
        self._array_reader.dtypes = self.dtypes
        self._array_reader.class_dtypes = self.class_dtypes

    def matrix_getter_factory(self):
        return self._array_reader.matrix_getter_factory()

    def guess_byte_order(self):
        self.mat_stream.seek(126)
        mi = self.mat_stream.read(2)
        self.mat_stream.seek(0)
        return mi == 'IM' and '<' or '>'

    def file_header(self):
        ''' Read in mat 5 file header '''
        hdict = {}
        hdr = self.read_dtype(self.dtypes['file_header'])
        hdict['__header__'] = hdr['description'].item().strip(' \t\n\000')
        v_major = hdr['version'] >> 8
        v_minor = hdr['version'] & 0xFF
        hdict['__version__'] = '%d.%d' % (v_major, v_minor)
        return hdict

    def format_looks_right(self):
        # Mat4 files have a zero somewhere in first 4 bytes
        self.mat_stream.seek(0)
        mopt_bytes = N.ndarray(shape=(4,),
                             dtype=N.uint8,
                             buffer = self.mat_stream.read(4))
        self.mat_stream.seek(0)
        return 0 not in mopt_bytes


class Mat5MatrixWriter(MatStreamWriter):

    mat_tag = N.zeros((), mdtypes_template['tag_full'])
    mat_tag['mdtype'] = miMATRIX

    def __init__(self, file_stream, arr, name, is_global=False):
        super(Mat5MatrixWriter, self).__init__(file_stream, arr, name)
        self.is_global = is_global

    def write_dtype(self, arr):
        self.file_stream.write(arr.tostring())

    def write_element(self, arr, mdtype=None):
        if mdtype is None:
            mdtype = np_to_mtypes[arr.dtype.str[1:]]
        
        byte_count = arr.size*arr.itemsize
        if byte_count <= 4:
            self.write_compressed_element(arr, mdtype, byte_count)
        else:
            self.write_regular_element(arr, mdtype, byte_count)

    def write_compressed_element(self, arr, mdtype, byte_count):
        # write tag with embedded data
        tag = N.zeros((), mdtypes_template['tag_compressed'])
        tag['byte_count_mdtype'] = (byte_count << 16) + mdtype
        # if arr.tostring is < 4, the element will be zero-padded as needed.
        tag['data'] = arr.tostring(order='F')
        self.write_dtype(tag)
            
    def write_regular_element(self, arr, mdtype, byte_count):
        # write tag, data
        tag = N.zeros((), mdtypes_template['tag_full'])
        tag['mdtype'] = mdtype
        tag['byte_count'] = byte_count
        padding = (8 - tag['byte_count']) % 8

        self.write_dtype(tag)
        self.write_bytes(arr)

        # pad to next 64-bit boundary
        self.write_bytes(N.zeros((padding,),'u1'))

    def write_header(self, mclass,
                     is_global=False,
                     is_complex=False,
                     is_logical=False,
                     nzmax=0):
        ''' Write header for given data options
        mclass      - mat5 matrix class
        is_global   - True if matrix is global
        is_complex  - True is matrix is complex
        is_logical  - True if matrix is logical
        nzmax        - max non zero elements for sparse arrays
        '''
        self._mat_tag_pos = self.file_stream.tell()
        self.write_dtype(self.mat_tag)
        # write array flags (complex, global, logical, class, nzmax)
        af = N.zeros((), mdtypes_template['array_flags'])
        af['data_type'] = miUINT32
        af['byte_count'] = 8
        flags = is_complex << 3 | is_global << 2 | is_logical << 1
        af['flags_class'] = mclass | flags << 8
        af['nzmax'] = nzmax
        self.write_dtype(af)
        # write array shape
        if self.arr.ndim < 2:
            new_arr = N.atleast_2d(self.arr)
            if type(new_arr) != type(self.arr):
                raise ValueError("Array should be 2-dimensional.")
            self.arr = new_arr
        self.write_element(N.array(self.arr.shape, dtype='i4'))
        # write name
        self.write_element(N.array([ord(c) for c in self.name], 'i1'))

    def update_matrix_tag(self):
        curr_pos = self.file_stream.tell()
        self.file_stream.seek(self._mat_tag_pos)
        self.mat_tag['byte_count'] = curr_pos - self._mat_tag_pos - 8
        self.write_dtype(self.mat_tag)
        self.file_stream.seek(curr_pos)

    def write(self):
        assert False, 'Not implemented'


class Mat5NumericWriter(Mat5MatrixWriter):

    def write(self):
        imagf = self.arr.dtype.kind == 'c'
        try:
            mclass = np_to_mxtypes[self.arr.dtype.str[1:]]
        except KeyError:
            if imagf:
                self.arr = self.arr.astype('c128')
            else:
                self.arr = self.arr.astype('f8')
            mclass = mxDOUBLE_CLASS
        self.write_header(mclass=mclass,is_complex=imagf)
        if imagf:
            self.write_element(self.arr.real)
            self.write_element(self.arr.imag)
        else:
            self.write_element(self.arr)
        self.update_matrix_tag()

class Mat5CharWriter(Mat5MatrixWriter):
    codec='ascii'
    def write(self):
        self.arr_to_chars()
        self.write_header(mclass=mxCHAR_CLASS)
        if self.arr.dtype.kind == 'U':
            # Recode unicode using self.codec
            n_chars = N.product(self.arr.shape)
            st_arr = N.ndarray(shape=(),
                             dtype=self.arr_dtype_number(n_chars),
                             buffer=self.arr)
            st = st_arr.item().encode(self.codec)
            self.arr = N.ndarray(shape=(len(st)), dtype='u1', buffer=st)
        self.write_element(self.arr,mdtype=miUTF8)
        self.update_matrix_tag()

class Mat5UniCharWriter(Mat5CharWriter):
    codec='UTF8'


class Mat5SparseWriter(Mat5MatrixWriter):

    def write(self):
        ''' Sparse matrices are 2D

        '''
        A = self.arr.tocsc() # convert to sparse CSC format
        A.sort_indices()     # MATLAB expects sorted row indices
        is_complex = (A.dtype.kind == 'c')
        nz = A.nnz
        self.write_header(mclass=mxSPARSE_CLASS,
                          is_complex=is_complex,
                          nzmax=nz)
        self.write_element(A.indices.astype('i4'))
        self.write_element(A.indptr.astype('i4'))
        self.write_element(A.data.real)
        if is_complex:
            self.write_element(A.data.imag)
        self.update_matrix_tag()


class Mat5WriterGetter(object):
    ''' Wraps stream and options, provides methods for getting Writer objects '''
    def __init__(self, stream, unicode_strings):
        self.stream = stream
        self.unicode_strings = unicode_strings

    def rewind(self):
        self.stream.seek(0)

    def matrix_writer_factory(self, arr, name, is_global=False):
        ''' Factory function to return matrix writer given variable to write
        stream      - file or file-like stream to write to
        arr         - array to write
        name        - name in matlab (TM) workspace
        '''
        # if have_sparse:
        #     if scipy.sparse.issparse(arr):
        #         return Mat5SparseWriter(self.stream, arr, name, is_global)
        arr = N.array(arr)
        if arr.dtype.hasobject:
            types, arr_type = self.classify_mobjects(arr)
            if arr_type == 'c':
                return Mat5CellWriter(self.stream, arr, name, is_global, types)
            elif arr_type == 's':
                return Mat5StructWriter(self.stream, arr, name, is_global)
            elif arr_type == 'o':
                return Mat5ObjectWriter(self.stream, arr, name, is_global)
        if arr.dtype.kind in ('U', 'S'):
            if self.unicode_strings:
                return Mat5UniCharWriter(self.stream, arr, name, is_global)
            else:
                return Mat5CharWriter(self.stream, arr, name, is_global)
        else:
            return Mat5NumericWriter(self.stream, arr, name, is_global)

    def classify_mobjects(self, objarr):
        ''' Function to classify objects passed for writing
        returns
        types         - S1 array of same shape as objarr with codes for each object
                        i  - invalid object
                        a  - ndarray
                        s  - matlab struct
                        o  - matlab object
        arr_type       - one of
                        c  - cell array
                        s  - struct array
                        o  - object array
        '''
        n = objarr.size
        types = N.empty((n,), dtype='S1')
        types[:] = 'i'
        type_set = set()
        flato = objarr.flat
        for i in range(n):
            obj = flato[i]
            if isinstance(obj, N.ndarray):
                types[i] = 'a'
                continue
            try:
                fns = tuple(obj._fieldnames)
            except AttributeError:
                continue
            try:
                cn = obj._classname
            except AttributeError:
                types[i] = 's'
                type_set.add(fns)
                continue
            types[i] = 'o'
            type_set.add((cn, fns))
        arr_type = 'c'
        if len(set(types))==1 and len(type_set) == 1:
            arr_type = types[0]
        return types.reshape(objarr.shape), arr_type


class MatFile5Writer(MatFileWriter):
    ''' Class for writing mat5 files '''
    def __init__(self, file_stream,
                 do_compression=False,
                 unicode_strings=False,
                 global_vars=None):
        super(MatFile5Writer, self).__init__(file_stream)
        self.do_compression = do_compression
        if global_vars:
            self.global_vars = global_vars
        else:
            self.global_vars = []
        self.writer_getter = Mat5WriterGetter(
            StringIO(),
            unicode_strings)
        # write header
        import os, time
        hdr =  N.zeros((), mdtypes_template['file_header'])
        hdr['description']='MATLAB 5.0 MAT-file Platform: %s, Created on: %s' % (
                            os.name,time.asctime())
        hdr['version']= 0x0100
        hdr['endian_test']=N.ndarray(shape=(),dtype='S2',buffer=N.uint16(0x4d49))
        file_stream.write(hdr.tostring())

    def get_unicode_strings(self):
        return self.write_getter.unicode_strings
    def set_unicode_strings(self, unicode_strings):
        self.writer_getter.unicode_strings = unicode_strings
    unicode_strings = property(get_unicode_strings,
                               set_unicode_strings,
                               None,
                               'get/set unicode strings property')

    def put_variables(self, mdict):
        for name, var in mdict.items():
            is_global = name in self.global_vars
            self.writer_getter.rewind()
            self.writer_getter.matrix_writer_factory(
                var,
                name,
                is_global,
                ).write()
            stream = self.writer_getter.stream
            if self.do_compression:
                str = zlib.compress(stream.getvalue(stream.tell()))
                tag = N.empty((), mdtypes_template['tag_full'])
                tag['mdtype'] = miCOMPRESSED
                tag['byte_count'] = len(str)
                self.file_stream.write(tag.tostring() + str)
            else:
                self.file_stream.write(stream.getvalue(stream.tell()))
