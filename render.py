#!/bin/python3
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
# - fc-match (Command from fontconfig)
from PIL import Image, ImageDraw, ImageFont, ImageDraw
import subprocess
import logging
import re
logger = logging.getLogger(__name__)


class render_result_t():
    msg: str
    out: Image.Image
    col_fg: str
    col_bg: str

    @property
    def ok(self):
        return self.out is not None and self.msg == "Success"

    def __init__(self, err_msg="Image rendering in Progress"):
        self.msg = err_msg
        self.out = None
        self.col_fg = None
        self.col_bg = None


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


def fc_match(pattern):
    proc = subprocess.run(["fc-match",
                           "-f", "%{file}",
                           pattern],
                          capture_output=True,
                          env=ENV_C)
    if (proc.returncode == 0 and not proc.stdout.endswith(b"\n")):
        return proc.stdout.decode("utf-8")
    else:
        return None


def render_commands(command_list: list[str],
                    variables: dict[str],
                    tape_height: int) -> render_result_t:
    """Render label to a PIL image

    Arguments:
    command_list -- List of label renderer commands in order of execution
    variables    -- Configuration variables to pass through
    tape_height  -- Height in pixels, of the resulting image
    """
    parsed_commands = []
    for i in command_list:
        # Remove comments
        if (i.startswith("#")):
            continue

        # Remove line terminators
        if (i.endswith("\r\n")):
            i = i[:-2]
        elif (i.endswith("\n")):
            i = i[:-1]

        # Remove empty lines
        if (len(i) == 0):
            continue

        i = re.sub(r"\t+", r"\t", i)

        parsed_commands.append(i.split("\t"))

    if (len(parsed_commands) == 0):
        return render_result_t("No commands provided!")

    parsed_commands.append(["BLOCK"])  # Force rendering to happen

    ret = render_result_t()
    lines = []
    align_mode = "left"
    font = ""
    for cmd in parsed_commands:
        logger.debug(cmd)
        render_requested = False
        if (cmd[0] == "ICRASHSTUFF-LABEL-RENDERER-FILE:1"):
            pass
        elif (cmd[0] == "BACKGROUND"):
            ret.col_bg = cmd[1]
        elif (cmd[0] == "FOREGROUND"):
            ret.col_fg = cmd[1]
        elif (cmd[0] == "CONFIG"):
            vartype = cmd[1]
            varname = cmd[2]
            vardefault = cmd[3]
            if (vartype == "ENUM"):
                possible = cmd[4:]
                if (vardefault not in possible):
                    return render_result_t(f"Default value of '{vardefault}' for '{varname}' not in enumeration")
                if (varname not in variables):
                    variables[varname] = vardefault
                elif (variables[varname] not in possible):
                    return render_result_t(f"Set value of '{variables[varname]}' for '{varname}' not in enumeration")
            elif (vartype == "NUMERICAL"):
                varmin = int(cmd[4])
                varmax = int(cmd[5])
                vardefault = int(vardefault)
                if (int(vardefault) > varmax or int(vardefault) < varmin):
                    return render_result_t(f"Default value of '{vardefault}' for '{varname}' not in range")
                if (varname not in variables):
                    variables[varname] = str(vardefault)
                elif (int(variables[varname]) > varmax or int(variables[varname]) < varmin):
                    return render_result_t(f"Set value of '{variables[varname]}' for '{varname}' not in range")
            elif (vartype == "TEXT"):
                if (varname not in variables):
                    variables[varname] = vardefault
        elif (cmd[0] == "ALIGN"):
            align_mode = cmd[1].lower()
        elif (cmd[0] == "FONT"):
            font_match = fc_match(cmd[1])
            if(not font_match):
                return render_result_t(f"Unable to find font for pattern '{cmd[1]}'")
            logger.debug(f"Resolving font pattern '{cmd[1]}' to '{font_match}'")
            font = font_match
        elif (cmd[0] == "FONTFILE"):
            font = cmd[1]
        elif (cmd[0] == "NEWLINE" or (cmd[0] == "TEXT" and len(lines) == 0)):
            if (len(cmd) > 2):
                s = cmd[2]
            else:
                s = ""
            while ((m := re.search(r"\${(?P<var_name>[^}]*)}", s)) is not None):
                varname = m.group("var_name")
                if (varname not in variables):
                    return render_result_t(f"Unknown variable '{varname}'")
                value = variables[varname]
                s = s[:m.start()] + value + s[m.end():]
            lines.append({
                "align": align_mode,
                "font_file": font,
                "weight": int(cmd[1]),
                "text": s
            })
        elif (cmd[0] == "TEXT"):
            if (len(cmd) > 2):
                s = cmd[2]
            else:
                s = ""
            while ((m := re.search(r"\${(?P<var_name>[^}]*)}", s)) is not None):
                varname = m.group("var_name")
                if (varname not in variables):
                    return render_result_t(f"Unknown variable '{varname}'")
                value = variables[varname]
                s = s[:m.start()] + value + s[m.end():]
            lines[-1]["text"] += s
        elif (cmd[0] == "BLOCK" or cmd[0] == "SPACING"):
            render_requested = True
        else:
            return render_result_t(f"Unknown command: '{cmd[0]}'")

        # Render lines
        if (render_requested and len(lines) != 0):
            ret.msg = "Success"
            logger.debug("Rendering block with lines:")
            for i in lines:
                logger.debug(f" - {i}")

            # Calculate line rendering data
            line_data = []
            total_weight = 0
            for i in lines:
                total_weight += i["weight"]
            for i in lines:
                ldat = i
                ldat["height"] = tape_height * i["weight"] // total_weight
                ldat["font"] = ImageFont.truetype(
                    i["font_file"], size=ldat["height"])
                bbox = ldat["font"].getbbox(i["text"])
                ldat["length"] = bbox[0] + bbox[2]

                line_data.append(ldat)
            max_line_len = 0
            for i in line_data:
                max_line_len = max(max_line_len, i["length"])

            # Expand image
            old_width = ret.out.width
            new_width = old_width + max_line_len
            new = Image.new("1", (new_width, tape_height), 1)
            new.paste(ret.out)
            ret.out = new

            draw = ImageDraw.Draw(ret.out)
            y = 0
            for i in line_data:
                anchors = ["", "m"]
                if (i["align"] == "left"):
                    x = old_width
                    anchors[0] = "l"
                elif (i["align"] == "middle"):
                    x = (old_width + new_width) // 2
                    anchors[0] = "m"
                elif (i["align"] == "right"):
                    x = new_width
                    anchors[0] = "r"
                else:
                    return render_result_t(f"Unsupported line alignment mode: '{i["align"]}'")
                y_t = y + i["height"] // 2
                draw.text((x, y_t), i["text"],
                          font=i["font"], anchor="".join(anchors))

                y = y + i["height"]

            lines = []

        # Add spacing
        if (cmd[0] == "SPACING"):
            ret.msg = "Success"
            spacing_width = int(tape_height * float(cmd[1]))
            if (ret.out is None):
                ret.out = Image.new(
                    mode="1", size=(spacing_width, tape_height), color=1)
            else:
                new = Image.new(mode="1",
                                size=(ret.out.width +
                                      spacing_width, tape_height),
                                color=1)
                new.paste(ret.out)
                ret.out = new

    return ret


if (__name__ == "__main__"):
    logging.basicConfig()
    import argparse
    import sys
    import os

    # Argument parsing!
    parser = argparse.ArgumentParser(
        description="Renders tape labels",)
    parser.add_argument("input")
    parser.add_argument("output")
    parser.add_argument("-D", metavar="Variable", action="append",
                        dest="variables", default=[], help="Set config value")
    parser.add_argument("--debug", action="store_true",
                        help="Enable debug log level")
    parser.add_argument("--tape-width", default=76, type=int)
    args = parser.parse_args()

    # Set log levels
    if (args.debug):
        logger.info("Debug logging enabled")
        logger.setLevel(logging.DEBUG)

    # Split out config variables
    defs = {}
    for i in args.variables:
        i_split = i.split("=", 1)
        if (len(i_split) != 2):
            logger.error("Config variables be formatted as 'KEY=VALUE'!")
            logger.error(f"Offending variable: '{i}'")
            sys.exit(1)
        defs[i_split[0]] = i_split[1]

    # Check that in != out
    filename_in = os.path.abspath(args.input)
    filename_out = os.path.abspath(args.output)
    if (filename_in == filename_out):
        logger.error("Output cannot be the same as Input!")
        sys.exit(1)

    # Load command list
    commands = []
    try:
        with open(filename_in, 'r') as fd:
            for line in fd:
                commands.append(line)
    except FileNotFoundError:
        logger.error(f"Input file '{filename_in}' not found!")
        sys.exit(1)

    # Render label
    r = render_commands(commands, defs, args.tape_width)

    if (r.ok):  # Save image
        r.out.save(filename_out)
    else:  # Log rendering error
        logger.error("Error rendering commands")
        logger.error(r.msg)
        sys.exit(1)
