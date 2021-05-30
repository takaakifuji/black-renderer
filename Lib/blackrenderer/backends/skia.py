from contextlib import contextmanager
import os
from fontTools.pens.basePen import BasePen
from fontTools.ttLib.tables.otTables import CompositeMode, ExtendMode
import skia
from .base import Canvas, Surface


_compositeModeMap = {
    CompositeMode.CLEAR: skia.BlendMode.kClear,
    CompositeMode.SRC: skia.BlendMode.kSrc,
    CompositeMode.DEST: skia.BlendMode.kDst,
    CompositeMode.SRC_OVER: skia.BlendMode.kSrcOver,
    CompositeMode.DEST_OVER: skia.BlendMode.kDstOver,
    CompositeMode.SRC_IN: skia.BlendMode.kSrcIn,
    CompositeMode.DEST_IN: skia.BlendMode.kDstIn,
    CompositeMode.SRC_OUT: skia.BlendMode.kSrcOut,
    CompositeMode.DEST_OUT: skia.BlendMode.kDstOut,
    CompositeMode.SRC_ATOP: skia.BlendMode.kSrcATop,
    CompositeMode.DEST_ATOP: skia.BlendMode.kDstATop,
    CompositeMode.XOR: skia.BlendMode.kXor,
    CompositeMode.SCREEN: skia.BlendMode.kScreen,
    CompositeMode.OVERLAY: skia.BlendMode.kOverlay,
    CompositeMode.DARKEN: skia.BlendMode.kDarken,
    CompositeMode.LIGHTEN: skia.BlendMode.kLighten,
    CompositeMode.COLOR_DODGE: skia.BlendMode.kColorDodge,
    CompositeMode.COLOR_BURN: skia.BlendMode.kColorBurn,
    CompositeMode.HARD_LIGHT: skia.BlendMode.kHardLight,
    CompositeMode.SOFT_LIGHT: skia.BlendMode.kSoftLight,
    CompositeMode.DIFFERENCE: skia.BlendMode.kDifference,
    CompositeMode.EXCLUSION: skia.BlendMode.kExclusion,
    CompositeMode.MULTIPLY: skia.BlendMode.kMultiply,
    CompositeMode.HSL_HUE: skia.BlendMode.kHue,
    CompositeMode.HSL_SATURATION: skia.BlendMode.kSaturation,
    CompositeMode.HSL_COLOR: skia.BlendMode.kColor,
    CompositeMode.HSL_LUMINOSITY: skia.BlendMode.kLuminosity,
}


_extendModeMap = {
    ExtendMode.PAD: skia.TileMode.kClamp,
    ExtendMode.REPEAT: skia.TileMode.kRepeat,
    ExtendMode.REFLECT: skia.TileMode.kMirror,
}


class SkiaPath(BasePen):
    def __init__(self):
        super().__init__(None)
        self.path = skia.Path()

    def _moveTo(self, pt):
        self.path.moveTo(*pt)

    def _lineTo(self, pt):
        self.path.lineTo(*pt)

    def _curveToOne(self, pt1, pt2, pt3):
        self.path.cubicTo(*pt1, *pt2, *pt3)

    def _qCurveToOne(self, pt1, pt2):
        self.path.quadTo(*pt1, *pt2)

    def _closePath(self):
        self.path.close()


class SkiaCanvas(Canvas):
    def __init__(self, canvas):
        self.canvas = canvas

    @staticmethod
    def newPath():
        return SkiaPath()

    @contextmanager
    def savedState(self):
        self.canvas.save()
        yield
        self.canvas.restore()

    @contextmanager
    def compositeMode(self, compositeMode):
        paint = skia.Paint(BlendMode=_compositeModeMap[compositeMode])
        self.canvas.saveLayer(paint=paint)
        yield
        self.canvas.restore()

    def transform(self, transform):
        matrix = skia.Matrix()
        matrix.setAffine(transform)
        self.canvas.concat(matrix)

    def clipPath(self, path):
        self.canvas.clipPath(path.path, doAntiAlias=True)

    def drawPathSolid(self, path, color):
        paint = skia.Paint(
            AntiAlias=True,
            Color=skia.Color4f(tuple(color)),
            Style=skia.Paint.kFill_Style,
        )
        self.canvas.drawPath(path.path, paint)

    def drawPathLinearGradient(
        self, path, colorLine, pt1, pt2, extendMode, gradientTransform
    ):
        matrix = skia.Matrix()
        matrix.setAffine(gradientTransform)
        colors, stops = _unpackColorLine(colorLine)
        shader = skia.GradientShader.MakeLinear(
            points=[pt1, pt2],
            colors=colors,
            positions=stops,
            mode=_extendModeMap[extendMode],
            localMatrix=matrix,
        )
        self.canvas.drawPath(path.path, skia.Paint(AntiAlias=True, Shader=shader))

    def drawPathRadialGradient(
        self,
        path,
        colorLine,
        startCenter,
        startRadius,
        endCenter,
        endRadius,
        extendMode,
        gradientTransform,
    ):
        matrix = skia.Matrix()
        matrix.setAffine(gradientTransform)
        colors, stops = _unpackColorLine(colorLine)
        shader = skia.GradientShader.MakeTwoPointConical(
            start=startCenter,
            startRadius=startRadius,
            end=endCenter,
            endRadius=endRadius,
            colors=colors,
            positions=stops,
            mode=_extendModeMap[extendMode],
            localMatrix=matrix,
        )
        self.canvas.drawPath(path.path, skia.Paint(AntiAlias=True, Shader=shader))

    def drawPathSweepGradient(
        self,
        path,
        colorLine,
        center,
        startAngle,
        endAngle,
        extendMode,
        gradientTransform,
    ):
        matrix = skia.Matrix()
        matrix.setAffine(gradientTransform)
        colors, stops = _unpackColorLine(colorLine)
        shader = skia.GradientShader.MakeSweep(
            cx=center[0],
            cy=center[1],
            colors=colors,
            positions=stops,
            mode=_extendModeMap[extendMode],
            startAngle=startAngle,
            endAngle=endAngle,
            localMatrix=matrix,
        )
        self.canvas.drawPath(path.path, skia.Paint(AntiAlias=True, Shader=shader))

    # TODO: blendMode for PaintComposite


def _unpackColorLine(colorLine):
    colors = []
    stops = []
    for stop, color in colorLine:
        colors.append(int(skia.Color4f(tuple(color))))
        stops.append(stop)
    return colors, stops


class SkiaPixelSurface(Surface):
    fileExtension = ".png"

    def __init__(self, boundingBox):
        x, y, xMax, yMax = boundingBox
        width = xMax - x
        height = yMax - y
        skCanvas = self._setupSkCanvas(x, y, width, height)
        skCanvas.translate(-x, height + y)
        skCanvas.scale(1, -1)
        self._canvas = SkiaCanvas(skCanvas)

    def _setupSkCanvas(self, x, y, width, height):
        self.surface = skia.Surface(width, height)
        return self.surface.getCanvas()

    @property
    def canvas(self):
        return self._canvas

    def saveImage(self, path, format=skia.kPNG):
        image = self.surface.makeImageSnapshot()
        image.save(os.fspath(path), format)


class SkiaPDFSurface(SkiaPixelSurface):
    fileExtension = ".pdf"

    def _setupSkCanvas(self, x, y, width, height):
        self.recorder = skia.PictureRecorder()
        return self.recorder.beginRecording(width, height)

    def saveImage(self, path):
        stream = skia.FILEWStream(os.fspath(path))
        picture = self.recorder.finishRecordingAsPicture()
        with skia.PDF.MakeDocument(stream) as document:
            x, y, width, height = picture.cullRect()
            assert x == 0 and y == 0
            with document.page(width, height) as canvas:
                canvas.drawPicture(picture)
        stream.flush()
