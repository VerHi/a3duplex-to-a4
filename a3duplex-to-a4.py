import argparse
import copy
import cv2
import img2pdf
import logging
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(
        description='A3 duplex scanned PDF to A4 PDF.')
    parser.add_argument('-v', '--verbose',
                        help='Print more data.', action='store_true')
    parser.add_argument('-c', '--corrupted',
                        help='Parse files with ImageMagick if JPGs are corrupted.', action='store_true')
    parser.add_argument('-r', '--rotate', nargs='?', type=int,
                        choices=range(0, 3), help='Rotate PDF by 90(0)|180(1)|270(2) degrees clockwise.')
    parser.add_argument('-q', '--quality', nargs='?', type=int,
                        default=90, help='JPEG compression quality.')
    parser.add_argument('--dpi', nargs='?', type=int,
                        default=300, help='Source DPI.')
    parser.add_argument('--raw', nargs='?', type=str,
                        help='Folder to store cropped image files in. Disables PDF creation.')
    parser.add_argument('input', nargs='+', help='Input PDF file(s).')
    args = parser.parse_args()

    if args.verbose:
        logging.basicConfig(level=logging.INFO)

    for file in args.input:
        print('Source file: ' + file)
        filePath = Path(file).resolve()
        output = Path(filePath.parent, filePath.stem+'_c.pdf')
        with tempfile.TemporaryDirectory() as tmp:
            print('Extracting images.')
            subprocess.run(['pdfimages', '-all', str(filePath),
                            str(Path(tmp, 'source'))])
            if args.corrupted:
                for f in Path(tmp).glob('source-*'):
                    logging.info(f'Reprocessing image {f}.')
                    subprocess.run(
                        ['magick', 'mogrify', '-strip', str(Path(tmp, f))], stderr=subprocess.DEVNULL)
            print('Cropping images.')
            cropimages(tmp, args.quality, args.rotate)
            if args.raw:
                outfolder = Path(args.raw, filePath.stem).resolve()
                print('Copying files.')
                os.makedirs(outfolder, exist_ok=True)
                for f in Path(tmp).glob('crop-*'):
                    shutil.copy(f, outfolder)
                    logging.info(f'{f} to {outfolder}')
            else:
                print('Creating PDF.')
                createpdf([str(file) for file in Path(
                    tmp).glob('crop-*.*')], output, args.dpi)


def cropimages(folder, quality, rotate):
    files = [file for file in Path(folder).glob('*.*')]

    realPages = len(files) * 2
    mappedPages = {}
    i_lower = 0
    i_upper = realPages - 1

    for i in range(realPages):
        if i % 4 == 0 or i % 4 == 3:
            mappedPages[i_upper] = i
            i_upper -= 1
        elif i % 4 == 1 or i % 4 == 2:
            mappedPages[i_lower] = i
            i_lower += 1

    for i in range(realPages):
        logging.info(
            f'Creating page {i} from image {mappedPages[i]//2:03d}, quality {quality:03d}.')
        file = files[mappedPages[i]//2]
        img = cv2.imread(str(Path(folder, file)))
        if rotate:
            img = cv2.rotate(img, rotate)
        height, width, _ = img.shape

        crop = img[0:height, 0:int(
            width*0.5)] if mappedPages[i] % 2 == 0 else img[0:height, int(width*0.5):width]
        encode_param = [int(cv2.IMWRITE_JPEG_QUALITY), quality]
        cv2.imwrite(
            str(Path(folder, f'crop-{i:03d}'+file.suffix)), crop, encode_param)


def createpdf(input, output, dpi):
    a4inpt = (img2pdf.mm_to_pt(210), img2pdf.mm_to_pt(297))
    layout_fun = img2pdf.get_layout_fun(a4inpt)
    with open(output, 'wb') as f:
        f.write(img2pdf.convert(input, layout_fun=layout_fun))


if __name__ == '__main__':
    main()
