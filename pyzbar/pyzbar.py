from __future__ import print_function
from collections import namedtuple
from contextlib import contextmanager
from ctypes import cast, byref, c_char_p, c_int, c_uint, c_void_p, string_at

from .pyzbar_error import PyZbarError
from .wrapper import (
    c_ubyte_p, c_ulong_p, zbar_set_verbosity,
    zbar_parse_config, zbar_image_scanner_set_config,
    zbar_image_scanner_create, zbar_image_scanner_destroy,
    zbar_image_create, zbar_image_destroy, zbar_image_set_format,
    zbar_image_set_size, zbar_image_set_data, zbar_scan_image,
    zbar_image_first_symbol, zbar_symbol_get_data_length, zbar_symbol_get_data,
    zbar_symbol_next, ZBarConfig, ZBarSymbol
)


# Results of reading a barcode
Decoded = namedtuple('Decoded', ['data', 'type'])

# ZBar's magic 'fourcc' numbers that represent image formats
FOURCC = {
    'L800': 808466521,
    'GRAY': 1497715271
}


@contextmanager
def zbar_image():
    """A context manager for `zbar_image`, created and destoyed by
    `zbar_image_create` and `zbar_image_destroy`.

    Args:

    Yields:
        zbar_image: The created image

    Raises:
        PyZbarError: If the image could not be created.
    """
    image = zbar_image_create()
    if not image:
        raise PyZbarError('Could not create image')
    else:
        try:
            yield image
        finally:
            zbar_image_destroy(image)


@contextmanager
def zbar_image_scanner():
    """A context manager for `zbar_image_scanner`, created and destroyed by
    `zbar_image_scanner_create` and `zbar_image_scanner_destroy`.

    Args:

    Yields:
        zbar_image_scanner: The created scanner

    Raises:
        PyZbarError: If the decoder could not be created.
    """
    scanner = zbar_image_scanner_create()
    if not scanner:
        raise PyZbarError('Could not create decoder')
    else:
        try:
            yield scanner
        finally:
            zbar_image_scanner_destroy(scanner)


def decode(image):
    """Decodes datamatrix barcodes in `image`.

    Args:
        image: `numpy.ndarray`, `PIL.Image` or tuple (pixels, width, height)

    Returns:
        :obj:`list` of :obj:`Decoded`: The values decoded from barcodes.
    """

    # Test for PIL.Image and numpy.ndarray without requiring that cv2 or PIL
    # are installed.
    if 'PIL.' in str(type(image)):
        pixels = image.convert('L').tobytes()
        width, height = image.size
    elif 'numpy.ndarray' in str(type(image)):
        pixels = image[:, :, 0].astype('uint8').tobytes()
        height, width = image.shape[:2]
    else:
        # image should be a tuple (pixels, width, height)
        pixels, width, height = image

    # Compute bits-per-pixel
    bpp = 8 * len(pixels) / (width * height)
    if 8 != bpp:
        raise PyZbarError('Unsupported bits-per-pixel [{0}]'.format(bpp))

    results = []
    with zbar_image_scanner() as scanner:
        zbar_image_scanner_set_config(
            scanner, ZBarSymbol.QRCODE, ZBarConfig.CFG_ENABLE, 1
        )
        zbar_image_scanner_set_config(
            scanner, ZBarSymbol.CODE128, ZBarConfig.CFG_ENABLE, 1
        )
        with zbar_image() as img:
            zbar_image_set_format(img, FOURCC['L800'])
            zbar_image_set_size(img, width, height)
            zbar_image_set_data(img, cast(pixels, c_void_p), len(pixels), None)
            decoded = zbar_scan_image(scanner, img)
            if decoded < 0:
                raise PyZbarError('Unsupported image format')
            else:
                symbol = zbar_image_first_symbol(img)
                while symbol:
                    data = string_at(zbar_symbol_get_data(symbol))
                    symbol_type = ZBarSymbol(symbol.contents.value).name
                    results.append(Decoded(
                        data=data,
                        type=symbol_type
                    ))

                    symbol = zbar_symbol_next(symbol)

    return results