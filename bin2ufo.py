#!/usr/bin/env python

import sys
import os
from collections import defaultdict

from fontTools.misc.transform import Transform
from fontTools.pens.transformPen import TransformPen

from fontTools.pens.pointPen import SegmentToPointPen
from fontTools.ufoLib.glifLib import writeGlyphToString
from fontTools.ufoLib import UFOWriter
from fontmake.font_project import FontProject

__version__ = "1.0.0"

DOT_SCALE = 80
RIGHT_BEARING = 1

unicode_map = {
    "bar": ord('|'),
    "colon": ord(':'),
    "lparen": ord('('),
    "rparen": ord(')'),
    "period": ord('.'),
    "slash": ord('/'),
    "space": ord(' '),
    "hairspace": int("200A", 16),
    "thinspace": int("2009", 16),
    "comma": ord(',')}

class AttrDict(dict):
    def __init__(self, *args, **kwargs):
        super(AttrDict, self).__init__(*args, **kwargs)
        self.__dict__ = self

def make_woff2(files, destination):
  """
  Makes WOFF2 files from list of paths.

  *files* is a `list` of file paths as `string`
  *destination* is a `string` of the destination to save the WOFF files.
  """
  from fontTools.ttLib import woff2
  from fontTools.ttx import makeOutputFileName

  if not os.path.exists(destination):
    os.mkdir(destination)

  for i, file in enumerate(files):
    outfilename = makeOutputFileName(file,
                                     outputDir=destination,
                                     extension='.woff2',
                                     overWrite=True)
    if os.path.exists(outfilename):
      os.remove(outfilename)

    woff2.compress(file, outfilename)


def bin2glyph(binary_data, name, width=0, height=0, transform=None,
             version=2):
    """ Convert an SVG outline to a UFO glyph, and assign the given 'name',
    advance 'width' and 'height' (int), 'unicodes' (list of int) to the
    generated glyph.
    Return the resulting string in GLIF format (default: version 2).
    If 'transform' is provided, apply a transformation matrix before the
    conversion (must be tuple of 6 floats, or a FontTools Transform object).
    """
    right_bearing = RIGHT_BEARING
    if "space" in name:
        right_bearing = 0
    glyph = DotOutline.fromdata(binary_data, transform=transform, right_bearing=right_bearing)
    glyph.name = name
    if len(name) == 1:
        unicode = ord(name)
    elif len(name) == 2 and name[1] == "_":
        unicode = ord(name[0])
    elif name[:2] == "U+":
        unicode = int(name[2:], 16)
    else:
        unicode = unicode_map[name]
    glyph.unicodes = [unicode]
    return glyph


lines_to_data = lambda lines: [list(map(lambda char: True if char == '1' else False, list(line))) for line in lines]
class DotOutline(object):
    """ Parse SVG ``path`` elements from a file or string, and draw them
    onto a glyph object that supports the FontTools Pen protocol, or
    the ufoLib (ex RoboFab) PointPen protocol.

    For example, using a Defcon Glyph:

        import defcon

        glyph = defcon.Glyph()
        pen = glyph.getPen()
        svg = SVGOutline("path/to/a/glyph.svg")
        svg.draw(pen)

        pen = glyph.getPointPen()
        svg = SVGOutline.fromstring('<?xml version="1.0" ...')
        svg.drawPoints(pen)

    The constructor can optionally take a 'transform' matrix (6-float tuple,
    or FontTools Transform object).
    """

    def __init__(self, filename=None, transform=None, right_bearing=RIGHT_BEARING):
        if filename:
            with open(filename) as file_in:
                lines = file_in.readlines()

            self.data = lines_to_data(lines)
        else:
            self.data = []
        self.right_bearing = right_bearing
        self.transform = transform

    @classmethod
    def fromstring(cls, data, **kwargs):
        self = cls(**kwargs)
        self.data = lines_to_data(data)
        return self

    @classmethod
    def fromdata(cls, data, **kwargs):
        self = cls(**kwargs)
        self.data = data
        return self


    @property
    def width(self):
        return (len(self.data[0]) + self.right_bearing) * DOT_SCALE

    @property
    def height(self):
        return (len(self.data) + self.right_bearing) * DOT_SCALE

    def draw(self, pen):
        d = .65
        if self.transform:
            pen = TransformPen(pen, self.transform)
        pen = TransformPen(pen, Transform(dx=DOT_SCALE * d/2, dy=DOT_SCALE * d/2).scale(DOT_SCALE, DOT_SCALE))

        for j, line in enumerate(reversed(self.data)):
            for i, dot in enumerate(line):
                if not dot:
                    continue
                size_x = size_y = d / 2
                pen.moveTo((i + size_x, j))
                pen.curveTo(
                  (i + size_x, j - (0.552 * size_y)),
                  (i + (0.552 * size_x), j - size_y),
                  (i - 0, j - size_y))
                pen.curveTo(
                  (i - (0.552 * size_x), j - size_y),
                  (i - size_x, j - (0.552 * size_y)),
                  (i - size_x, j - 0))

                pen.curveTo(
                  (i - size_x, j + (0.552 * size_y)),
                  (i - (0.552 * size_x), j + size_y),
                  (i - 0, j + size_y))

                pen.curveTo(
                  (i + (0.552 * size_x), j + size_y),
                  (i + size_x, j + (0.552 * size_y)),
                  (i + size_x, j))

                pen.closePath()

    def drawPoints(self, pointPen):
        pen = SegmentToPointPen(pointPen)
        self.draw(pen)


def parse_args(args):
    import argparse

    def split(arg):
        return arg.replace(",", " ").split()

    def unicode_hex_list(arg):
        try:
            return [int(unihex, 16) for unihex in split(arg)]
        except ValueError:
            msg = "Invalid unicode hexadecimal value: %r" % arg
            raise argparse.ArgumentTypeError(msg)

    def transform_list(arg):
        try:
            return [float(n) for n in split(arg)]
        except ValueError:
            msg = "Invalid transformation matrix: %r" % arg
            raise argparse.ArgumentTypeError(msg)

    parser = argparse.ArgumentParser(
        description="Convert SVG outlines to UFO glyphs (.glif)")
    parser.add_argument(
        "outfile", metavar="out", help="Output directory")

    parser.add_argument(
        "-f", "--format", help="UFO GLIF format version (default: 2)",
        type=int, choices=(1, 2), default=2)
    parser.add_argument('--version', action='version', version=__version__)

    return parser.parse_args(args)


def load_from_txt(path):
    characters = {}
    alternative_sets = defaultdict(dict)
    for filename in os.listdir(path):
        if not filename.endswith(".txt"):
            print("Skipping", path)
            continue
        with open(f"{path}/{filename}") as fp:
            lines = fp.readlines()
        data = lines_to_data(map(str.strip, lines))
        if len(data) == 0:
            print("Skipping", path)
            continue
        components = filename.split(".")
        stylistic_set = None
        if len(components) == 3:
            character_name, stylistic_set, _ = components
        elif len(components) == 2:
            character_name, _ = components
        else:
            print("Skipping", path)
            continue
        if stylistic_set:
            alternative_sets[stylistic_set][character_name] = data
        else:
            characters[character_name] = data

    return characters, alternative_sets

def create_ufo(name, path, character_data, format, info):
    writer = UFOWriter(f"{path}/{name}.ufo")
    glyphset = writer.getGlyphSet()
    character_data, alternatives = character_data
    for character, data in character_data.items():
        try:
            glif = bin2glyph(data, character,
                             version=format)
        except:
            print("Skipping", character)
            # TODO: Need to handle stylistic alternatives
            # https://adobe-type-tools.github.io/afdko/OpenTypeFeatureFileSpecification.html#8.c
            continue
        glyphset.writeGlyph(character, glif, glif.drawPoints, format)

    glyphset.writeContents()
    writer.writeLayerContents()
    writer.writeInfo(info)
    return writer

def make_attr_dict(family_name, dot_height, x_dot_height, attrs={}):
    ascender_height = DOT_SCALE * dot_height
    descender_height = -DOT_SCALE
    # See https://googlefonts.github.io/gf-guide/metrics.html
    return AttrDict({"familyName": f"{family_name} {dot_height}",
        "versionMajor": 1,
        "versionMinor": 0,
        "copyright": "Copyright (c) 2023, Nick Walker",
        "openTypeNameVersion": "Version 1.000",
        "openTypeOS2Selection": [7], # Set "Use Typo Metrics"
        "openTypeOS2WeightClass": 5,  # Normal width
        "openTypeOS2WeightClass": 700,  # Bold
        "openTypeOS2TypoAscender": ascender_height,
        "openTypeOS2TypoDescender": descender_height,
        "openTypeOS2TypoLineGap": 0,
        "openTypeOS2WinAscent": ascender_height,
        "openTypeOS2WinDescent": -descender_height,
        "openTypeHheaAscender": ascender_height,
        "openTypeHheaDescender": descender_height,
        "openTypeHheaLineGap": 0,
        "note": "Created with bin2ufo.py and fonttools",
        "ascender": ascender_height,
        "descender": descender_height,
        "unitsPerEm": DOT_SCALE * dot_height, # Sum of metrics is expected to be 120-130% this value
        "xHeight": DOT_SCALE * x_dot_height,
        "italicAngle": 0})

def main(args=None):
    options = parse_args(args)
    st_7_info = make_attr_dict("Seattle Transit", 7, 5)
    seattle_transit_7 = load_from_txt("seattle_transit_7")
    st_7_ufo = create_ufo("seattle_transit_dot_matrix_7", "out", seattle_transit_7, options.format, st_7_info)

    st_12_info = make_attr_dict("Seattle Transit", 12, 8)
    seattle_transit_12 = load_from_txt("seattle_transit_12")
    st_12_ufo = create_ufo("seattle_transit_dot_matrix_12", "out", seattle_transit_12, options.format, st_12_info)
    st_15_info = make_attr_dict("Seattle Transit", 15, 11)
    seattle_transit_15 = load_from_txt("seattle_transit_15")
    st_15_ufo = create_ufo("seattle_transit_dot_matrix_15", "out", seattle_transit_15, options.format, st_15_info)
    st_16_info = make_attr_dict("Seattle Transit", 16, 11)
    seattle_transit_16 = load_from_txt("seattle_transit_16")
    st_16_ufo = create_ufo("seattle_transit_dot_matrix_16", "out", seattle_transit_16, options.format, st_16_info)

    FontProject().run_from_ufos("out/*.ufo", ("otf", "ttf"), output_dir="out")
    make_woff2(["out/seattle_transit_dot_matrix_7.otf"], "out")
    make_woff2(["out/seattle_transit_dot_matrix_15.otf"], "out")

if __name__ == "__main__":
    main()
