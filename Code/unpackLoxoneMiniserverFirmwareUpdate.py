#!/usr/bin/python
# -*- coding: utf-8 -*-

import struct,os,sys,binascii

# This script takes a Miniserver update file and unpacks it as a folder structure
# in the current directory. It validates the checksum and applies the special
# decompression.

updateFilename = '10031127_8F6AB916DF16FC7733441B8EAE503565.upd'

# This script analyzes a folder structure, which was generated by the unpack
# script. It tries to provide information about the firmware (Server, Extensions)
# - filename of the firmware
# - CPU for the firmware
# - ROM area used
# - RAM area used
# - Category (Server,Legacy,Tree,NAT or Air)
# - Version number of the firmware version
# - Product name

# RC6 encryption/decryption <https://en.wikipedia.org/wiki/RC6>
def ROR(x, n, bits=32):
  """rotate right input x, by n bits"""
  mask = (2L**n) - 1
  mask_bits = x & mask
  return (x >> n) | (mask_bits << (bits - n))
def ROL(x, n, bits=32):
  """rotate left input x, by n bits"""
  return ROR(x, bits - n,bits)
def RC6_PrepareKey(str):
  key = sum(ord(c) for c in str)
  return key | 0xFEED0000
def RC6_GenerateKey(initKey):
  """generate key s[0... 2r+3] from given input userkey"""
  L = (((initKey << 8) & 0x100) | (initKey << 24) | (initKey >> 24) | ((initKey >> 8) & 0x10)) & 0xFFFFFFFF
  r=16 # rounds
  w=32 # width in bits
  modulo = 2**32
  context_s=(2*r+4)*[0]
  context_s[0]=0xB7E15163
  for i in range(1,2*r+4):
    context_s[i]=(context_s[i-1]+0x9E3779B9)%(2**w)
  l = [L]
  enlength = 1
  v = 3*max(enlength,2*r+4)
  A=B=i=j=0
  for _ in range(v):
    A = context_s[i] = ROL((context_s[i] + A + B)%modulo,3)
    B = l[j] = ROL((l[j] + A + B)%modulo,(A+B)%32)
    i = (i + 1) % (2*r + 4)
    j = (j + 1) % enlength
  return context_s
def RC6_EncryptBlock(context,encoded):
  A,B,C,D = struct.unpack('<IIII', encoded)
  r=16
  w=32
  modulo = 2**32
  lgw = 5
  C = (C - context[2*r+3])%modulo
  A = (A - context[2*r+2])%modulo
  for j in range(1,r+1):
    i = r+1-j
    (A, B, C, D) = (D, A, B, C)
    u_temp = (D*(2*D + 1))%modulo
    u = ROL(u_temp,lgw)
    t_temp = (B*(2*B + 1))%modulo 
    t = ROL(t_temp,lgw)
    tmod=t%32
    umod=u%32
    C = (ROR((C-context[2*i+1])%modulo,tmod)  ^u)  
    A = (ROR((A-context[2*i])%modulo,umod)   ^t) 
  D = (D - context[1])%modulo 
  B = (B - context[0])%modulo
  return struct.pack('<IIII', A,B,C,D)
def RC6_DecryptBlock(context,encoded):
  A,B,C,D = struct.unpack('<IIII', encoded)
  r=16
  w=32
  modulo = 2**32
  lgw = 5
  B = (B + context[0])%modulo
  D = (D + context[1])%modulo 
  for i in range(1,r+1):
    t_temp = (B*(2*B + 1))%modulo 
    t = ROL(t_temp,lgw)
    u_temp = (D*(2*D + 1))%modulo
    u = ROL(u_temp,lgw)
    tmod=t%32
    umod=u%32
    A = (ROL(A^t,umod) + context[2*i])%modulo 
    C = (ROL(C^u,tmod) + context[2*i+ 1])%modulo
    (A, B, C, D)  =  (B, C, D, A)
  A = (A + context[2*r + 2])%modulo 
  C = (C + context[2*r + 3])%modulo
  return struct.pack('<IIII', A,B,C,D)
def RC6_Encrypt(context,data):
  blockSize = 16
  data += '\0' * (blockSize-1)
  data = data[:(len(data) / blockSize) * blockSize]
  return ''.join(
      RC6_EncryptBlock(context, block) for block in
      [data[i:i + blockSize] for i in range(0, len(data), blockSize)])
def RC6_Decrypt(context,data):
  blockSize = 16
  return ''.join(
      RC6_DecryptBlock(context, block) for block in
      [data[i:i + blockSize] for i in range(0, len(data), blockSize)])
def LoxDecryptFilename(hexstr):
    RC6context = RC6_GenerateKey(0x254A21) # a constant for firmware name names
    return RC6_Decrypt(RC6context,binascii.unhexlify(hexstr)).rstrip('\0')


# decompress a file inside the update image
def FDecompress(compressedData):
    destBuffer = bytearray()
    index = 0
    while index < len(compressedData):
        packageHeaderByte = ord(compressedData[index])
        index += 1
        if packageHeaderByte > 0x1F:
            byteCount = packageHeaderByte >> 5
            if byteCount == 7:
                byteCount += ord(compressedData[index])
                index += 1
            byteCount += 2
            byteOffset = ((packageHeaderByte & 0x1F) << 8) + ord(compressedData[index])
            index += 1
            backindex = len(destBuffer) - byteOffset - 1
            while byteCount > 0:
                destBuffer.append(destBuffer[backindex])
                backindex += 1
                byteCount -= 1
        else:
            while packageHeaderByte >= 0:
                destBuffer.append(compressedData[index])
                index += 1
                packageHeaderByte -= 1
    return destBuffer

f = open(updateFilename, "rb") # notice the b for binary mode
updateFileData = f.read()
f.close()
fileSize = len(updateFileData)

header = struct.unpack_from("<L", updateFileData, 0)[0]
if header == 0xc2c101ac:
    print('Miniserver 1 update file detected')
    msversion = ''
elif header == 0x9181a2b3:
    print('Miniserver 2 update file detected')
    msversion = '_ms2'
else:
    print("Miniserver Update Header (%#08x) not detect" % header)
    sys.exit(1)
print "File length                 : %ld bytes" % fileSize

def cleanupFilename(filename):
  try:
    fname,ext = filename.split('.')
    version,hexstr = fname.split('_')
    return f'{version}_{LoxDecryptFilename(hexstr)}.{ext}'
  except:
      return filename

version = updateFilename.split('_')[0]
subdir = 'update%s_%s' % (msversion,version)
if not os.path.exists(subdir):
    os.makedirs(subdir)
os.chdir(subdir)

header = struct.unpack_from("<L", updateFileData, 0)[0]
fileOffset = 0
if header == 0xc2c101ac: # Miniserver Gen 1 header
    fileHeaderSize = 0x0200 # the header is always 512 bytes long
    header,blockCount,version,checksum,comprByteCount,byteCount = struct.unpack_from("<6L", updateFileData, 0)
    if header != 0xc2c101ac:
        print "Miniserver Update Header not detect"
        sys.exit(-1)
    fileOffset = blockCount * 0x200 + fileHeaderSize
    print "Update files offset         : 0x%lx" % (fileOffset)
    print "Firmware Version            : %ld" % version
    print "Firmware Compressed Bytes   : %ld bytes" % comprByteCount
    print "Firmware Uncompressed Bytes : %ld bytes" % byteCount

    # the image of the firmware is directly after the header
    firmwareData = updateFileData[fileHeaderSize:fileHeaderSize+comprByteCount]

    # the checksum is a trivial little endian XOR32 over the data
    xorValue = 0x00000000
    alignedFirmwareData = firmwareData + b'\0\0\0' # make sure the data allows 4-byte aligned access for the checksum
    for offset in range(0, len(firmwareData), 4):
        xorValue ^= struct.unpack_from("<L", alignedFirmwareData, offset)[0]
    if xorValue == checksum:
        newFile = open(cleanupFilename(os.path.splitext(updateFilename)[0] + ".bin"), "wb")
        newFile.write(FDecompress(firmwareData))
    else:
        print "Firmware Checksum WRONG     : %#08lx != %#08lx" % (checksum,xorValue)

# iterate over the other files in the update image
while fileOffset < fileSize:
    header,uncompressedSize,compressedSize = struct.unpack_from("<3L", updateFileData, fileOffset)
    headerUnscrambled = (header+0x6E7E5D4D) & 0xFFFFFFFF
    if headerUnscrambled > 1: # header valid?
        break
    fileOffset += 12
    # the full (UNIX-style) pathname after the header plus a single zero byte to terminate the string
    pathname = ''
    while ord(updateFileData[fileOffset]) != 0:
        pathname += updateFileData[fileOffset]
        fileOffset += 1
    fileOffset += 1
    pathname = '.' + pathname # prefix a '.' to the pathname to make it relative (otherwise we would try to write into root)
    directory,filename = os.path.split(pathname)
    if compressedSize: # file is compressed?
        filedata = FDecompress(updateFileData[fileOffset:fileOffset+compressedSize])
        fileOffset += compressedSize
        print 'Write %s [%d bytes, %d compressed bytes]' % (pathname, uncompressedSize, compressedSize)
        if not os.path.exists(directory):
            os.makedirs(directory)
        newFile = open(os.path.join(directory,cleanupFilename(filename)), "wb")
        newFile.write(filedata)
    elif uncompressedSize: # file not compressed?
        filedata = updateFileData[fileOffset:fileOffset+uncompressedSize]
        fileOffset += uncompressedSize
        print 'Write %s [%d bytes, uncompressed]' % (pathname, uncompressedSize)
        if not os.path.exists(directory):
            os.makedirs(directory)
        newFile = open(os.path.join(directory,cleanupFilename(filename)), "wb")
        newFile.write(filedata)
    elif headerUnscrambled == 1: # delete files in the Miniserver filesystem (used to e.g. flush caches)
        print 'Delete %s' % pathname
# we really don't want an update file deleting stuff on our disk...
#        if os.path.exists(pathname):
#            os.remove(pathname)
    else: # headerUnscrambled == 0 # create empty directories
        print 'Create %s' % pathname
        if not os.path.exists(directory):
            os.makedirs(directory)
    # round to the next 32-bit
    fileOffset = ((fileOffset + 3) & ~3)
