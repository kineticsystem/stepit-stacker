"""The quilt for the Looking Glass Portrait, from the graded images of a session.

1. Every graded image is cropped at its centre to the aspect of a view, 3:4,
   and scaled down to a view, 420 x 560.
2. The views are retimed to the number of views of the quilt, 48: a view that
   falls between two angles is made by warping an angle toward it along the
   optical flow between them. With quilt.interpolation "nearest", only the
   nearer angle is warped; with "blend", both are, then blended.
3. The views are placed from the bottom-left to the top-right, the leftmost
   first, as Looking Glass expects, and saved as an 8-bit PNG named
   <session>_qs8x6a0.75.png, which tells its layout to Looking Glass's tools.

The leftmost view is the last angle: the stage turns the subject, and a subject
turned one way looks as if the camera had moved the other way. quilt.reverse
puts the first angle first, for a stage that turns the other way.
"""

import cv2
import numpy as np


def view(image, quilt):
    """A graded image as a view: cropped at its centre to the aspect of the view, then scaled down."""
    height, width = image.shape[:2]
    if width / height > quilt.aspect:
        crop = round(height * quilt.aspect)
        image = image[:, (width - crop) // 2:(width - crop) // 2 + crop]
    else:
        crop = round(width / quilt.aspect)
        image = image[(height - crop) // 2:(height - crop) // 2 + crop]
    return cv2.resize(image.astype(np.float32), (quilt.view_width, quilt.view_height), interpolation=cv2.INTER_AREA)


def _flow(a, b):
    """The dense optical flow from a to b (OpenCV's Farneback), as pixel displacements."""
    gray = [cv2.cvtColor(np.clip(v * 255, 0, 255).astype(np.uint8), cv2.COLOR_BGR2GRAY) for v in (a, b)]
    return cv2.calcOpticalFlowFarneback(gray[0], gray[1], None, 0.5, 4, 21, 5, 7, 1.5, 0)


def _warp(image, flow, fraction):
    """The image moved by `fraction` of the flow."""
    height, width = flow.shape[:2]
    x, y = np.meshgrid(np.arange(width, dtype=np.float32), np.arange(height, dtype=np.float32))
    return cv2.remap(image, x - flow[..., 0] * fraction, y - flow[..., 1] * fraction, cv2.INTER_LINEAR,
                     borderMode=cv2.BORDER_REPLICATE)


def retime(views, count, interpolation="nearest"):
    """`count` views spread evenly from the first view to the last.

    A view between two angles is the nearer angle warped toward it ("nearest"),
    or both angles warped toward it and blended ("blend"). Where the flow is
    wrong, e.g. thin legs crossing, "blend" shows the two angles at once, a
    ghost, and "nearest" a distortion of one.
    """
    if len(views) == count:
        return list(views)
    if len(views) == 1:
        return [views[0]] * count
    result = []
    for i in range(count):
        position = i * (len(views) - 1) / (count - 1)
        left = min(int(position), len(views) - 2)
        fraction = position - left
        a, b = views[left], views[left + 1]
        if fraction < 1e-6:
            result.append(a)
        elif fraction > 1 - 1e-6:
            result.append(b)
        elif interpolation == "nearest":
            result.append(_warp(a, _flow(a, b), fraction) if fraction <= 0.5 else _warp(b, _flow(b, a), 1 - fraction))
        else:
            from_a = _warp(a, _flow(a, b), fraction)
            from_b = _warp(b, _flow(b, a), 1 - fraction)
            result.append(from_a * (1 - fraction) + from_b * fraction)
    return result


def assemble(views, quilt):
    """The views in a grid: view 0 at the bottom left, rows from the bottom up."""
    height, width = views[0].shape[:2]
    grid = np.zeros((quilt.rows * height, quilt.columns * width, 3), np.float32)
    for i, image in enumerate(views):
        column, row_from_bottom = i % quilt.columns, i // quilt.columns
        top = (quilt.rows - 1 - row_from_bottom) * height
        grid[top:top + height, column * width:(column + 1) * width] = image
    return grid


def build(graded_images, path, quilt):
    """Builds the quilt of the graded images, given in the order of the angles, into path."""
    views = []
    for image_path in graded_images:
        image = cv2.imread(str(image_path), cv2.IMREAD_UNCHANGED)
        if image is None:
            raise RuntimeError(f"cannot read {image_path}")
        scale = 65535.0 if image.dtype == np.uint16 else 255.0
        views.append(view(image, quilt) / scale)
    if not quilt.reverse:
        views.reverse()
    grid = assemble(retime(views, quilt.views, quilt.interpolation), quilt)
    path.parent.mkdir(parents=True, exist_ok=True)
    cv2.imwrite(str(path), np.clip(grid * 255 + 0.5, 0, 255).astype(np.uint8))
    return path
