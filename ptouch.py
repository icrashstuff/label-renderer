# -*- coding: utf-8 -*-
# SPDX-License-Identifier: MIT
#
# SPDX-FileCopyrightText: Copyright (c) 2026 Ian Hangartner <icrashstuff at outlook dot com>
#
# Permission is hereby granted, free of charge, to any person obtaining a
# copy of this software and associated documentation files (the "Software"),
# to deal in the Software without restriction, including without limitation
# the rights to use, copy, modify, merge, publish, distribute, sublicense,
# and/or sell copies of the Software, and to permit persons to whom the
# Software is furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in
# all copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING
# FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER
# DEALINGS IN THE SOFTWARE.
#
# Requires:
# - Python standard library
# - pillow
# - ptouch-print (Command from ptouch-print)
#   - NOTE: Requires a version of ptouch-print that has the --timeout option
#     (introduced with commit #d8a4ed71e27591b95d6302664e9ac73f9d9c01aa)
#   - NOTE: Requires a version of ptouch-print that has the --precut option
#     (introduced with commit #d2a3bac46ee833ac966ae2f9a145d12fe556fb5b)
from dataclasses import dataclass
from PIL import Image
import subprocess
import logging
import io
import re
logger = logging.getLogger(__name__)

ENV_C = {"LANG": "C.UTF-8",
         "LANGUAGE": "C",
         "LC_CTYPE": "C.UTF-8",
         "LC_NUMERIC": "C.UTF-8",
         "LC_TIME": "C.UTF-8",
         "LC_COLLATE": "C.UTF-8",
         "LC_MONETARY": "C.UTF-8",
         "LC_MESSAGES": "C.UTF-8",
         "LC_PAPER": "C.UTF-8",
         "LC_NAME": "C.UTF-8",
         "LC_ADDRESS": "C.UTF-8",
         "LC_TELEPHONE": "C.UTF-8",
         "LC_MEASUREMENT": "C.UTF-8",
         "LC_IDENTIFICATION": "C.UTF-8",
         "LC_ALL": "C.UTF-8",
         }


@dataclass
class ptouch_info_t():
    printer_width_px: int
    media_width_px: int
    media_width_mm: int
    media_type: str
    col_bg: str
    col_fg: str


def ptouch_get_info(timeout=0) -> ptouch_info_t | int:
    """Get tape and printer info from ptouch printer"""
    proc = subprocess.run(["ptouch-print",
                           "--timeout", str(timeout),
                           "--info"],
                          capture_output=True,
                          env=ENV_C)
    if (proc.returncode != 0):
        return None

    stdout = proc.stdout.decode("utf-8")

    def search(pattern):
        return re.search(pattern, stdout, flags=re.M)

    m_printer_width_px = search(r"print.* (?P<num>\d+)px")
    m_media_width_px = search(r"tape.* (?P<num>\d+)px")
    m_media_width_mm = search(r"media width = (?P<num>\d*) mm")
    m_media_type = search(r"media type = 0x(?P<hex>\d*) \((?P<str>[^\)]*)\)")
    m_col_bg = search(r"tape color = 0x(?P<hex>\d*) \((?P<str>[^\)]*)\)")
    m_col_fg = search(r"text color = 0x(?P<hex>\d*) \((?P<str>[^\)]*)\)")

    ret = ptouch_info_t(printer_width_px=int(m_printer_width_px.group("num")),
                        media_width_px=int(m_media_width_px.group("num")),
                        media_width_mm=int(m_media_width_mm.group("num")),
                        media_type=m_media_type.group("str"),
                        col_bg=m_col_bg.group("str"),
                        col_fg=m_col_fg.group("str"))
    return ret


def ptouch_print(im: Image.Image,
                 copies=1,
                 timeout=0,
                 pad=0,
                 chain=False,
                 cutmark=False):
    """Send PIL Image to ptouch printer"""
    im_data_io = io.BytesIO()
    im.save(im_data_io, format='PNG')
    im_data = im_data_io.getvalue()

    while (copies := copies - 1) >= 0:
        args = []
        args.extend(["ptouch-print", "--timeout", str(timeout), "--precut"])
        # Enable chain for multiple copies to save tape
        if (chain or copies > 0):
            args.append("--chain")
        if (cutmark):
            args.append("--cutmark")
        args.extend(["-i", "-"])
        proc = subprocess.run(args,
                              input=im_data,
                              capture_output=True,
                              env=ENV_C)
