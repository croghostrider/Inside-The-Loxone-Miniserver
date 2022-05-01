#!/usr/bin/python3
# -*- coding: utf-8 -*-

import struct

with open('./sys/Sizes.bin', 'rb') as f:
    data = f.read()
for val in range(0,len(data),4):
    print('#%3d : %d bytes' % (val/4,struct.unpack('<I', data[val:val+4])[0]))
