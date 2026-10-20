"""
Generate a synthetic CT phantom as a DICOM series so the pipeline can be tested without patient data.

    python tools/make_test_series.py data/phantom_ct

Phantom content (HU):
    air background           -1000
    elliptical "body"           40   with a -90 fat layer and two -800 "lungs"
    posterior "spine"          900
    orientation markers       1200   R = sphere on the patient's RIGHT
                                     A = cube on the ANTERIOR side
                                     S = disc at the SUPERIOR end
Slices are written in shuffled order with random file names, so sorting by geometry is exercised.
Voxels are anisotropic on purpose (1.5 x 1.5 x 2.0 mm). Pixels are stored unsigned with
RescaleIntercept = -1024, as most scanners do.
"""
from __future__ import annotations

import random
import sys
from pathlib import Path

import numpy as np
import pydicom
from pydicom.dataset import Dataset, FileMetaDataset
from pydicom.uid import ExplicitVRLittleEndian, generate_uid

CT_IMAGE_STORAGE = "1.2.840.10008.5.1.4.1.1.2"


def build_phantom(nx=128, ny=128, nz=96, sx=1.5, sy=1.5, sz=2.0) -> np.ndarray:
    x = (np.arange(nx) - nx / 2 + 0.5) * sx      # + = patient left
    y = (np.arange(ny) - ny / 2 + 0.5) * sy      # + = posterior
    z = (np.arange(nz) - nz / 2 + 0.5) * sz      # + = superior
    Z, Y, X = np.meshgrid(z, y, x, indexing="ij")

    hu = np.full((nz, ny, nx), -1000.0, dtype=np.float32)
    body = (X / 85) ** 2 + (Y / 70) ** 2 <= 1
    hu[body] = 40
    hu[body & ((X / 85) ** 2 + (Y / 70) ** 2 > 0.82)] = -90                  # fat layer
    for side in (-38, 38):                                                      # lungs
        hu[((X - side) / 28) ** 2 + ((Y + 5) / 38) ** 2 + (Z / 70) ** 2 <= 1] = -800
    hu[(X ** 2 + (Y - 45) ** 2 <= 12 ** 2)] = 900                              # spine (posterior)

    hu[((X + 70) ** 2 + Y ** 2 + Z ** 2) <= 8 ** 2] = 1200                     # R marker (sphere)
    hu[(np.abs(X) <= 8) & (np.abs(Y + 60) <= 8) & (np.abs(Z) <= 8)] = 1200     # A marker (cube)
    hu[(X ** 2 + Y ** 2 <= 15 ** 2) & (Z >= z[-1] - 2 * sz)] = 1200            # S marker (disc)
    return hu


def _save(ds: Dataset, path: Path) -> None:
    try:
        ds.save_as(path, enforce_file_format=True)              # pydicom >= 3.0
    except TypeError:
        ds.is_little_endian, ds.is_implicit_VR = True, False
        ds.save_as(path, write_like_original=False)             # pydicom 2.x


def write_series(hu: np.ndarray, out_dir: Path, sx: float, sy: float, sz: float) -> None:
    nz, ny, nx = hu.shape
    out_dir.mkdir(parents=True, exist_ok=True)
    study_uid, series_uid, frame_uid = generate_uid(), generate_uid(), generate_uid()
    x0, y0, z0 = -nx / 2 * sx + sx / 2, -ny / 2 * sy + sy / 2, -nz / 2 * sz + sz / 2

    order = list(range(nz))
    random.Random(42).shuffle(order)
    for file_idx, k in enumerate(order):
        sop_uid = generate_uid()
        ds = Dataset()
        ds.file_meta = FileMetaDataset()
        ds.file_meta.MediaStorageSOPClassUID = CT_IMAGE_STORAGE
        ds.file_meta.MediaStorageSOPInstanceUID = sop_uid
        ds.file_meta.TransferSyntaxUID = ExplicitVRLittleEndian
        ds.file_meta.ImplementationClassUID = pydicom.uid.PYDICOM_IMPLEMENTATION_UID

        ds.SOPClassUID, ds.SOPInstanceUID = CT_IMAGE_STORAGE, sop_uid
        ds.PatientName, ds.PatientID = "PHANTOM^TEST", "PHANTOM-001"
        ds.PatientBirthDate, ds.PatientSex = "", "O"
        ds.StudyInstanceUID, ds.SeriesInstanceUID, ds.FrameOfReferenceUID = study_uid, series_uid, frame_uid
        ds.StudyDate = ds.SeriesDate = ds.ContentDate = "20260101"
        ds.StudyTime = ds.SeriesTime = ds.ContentTime = "120000"
        ds.Modality, ds.ImageType = "CT", ["ORIGINAL", "PRIMARY", "AXIAL"]
        ds.StudyID, ds.SeriesNumber, ds.AccessionNumber = "1", 1, ""
        ds.InstanceNumber = k + 1
        ds.ImagePositionPatient = [x0, y0, z0 + k * sz]
        ds.ImageOrientationPatient = [1, 0, 0, 0, 1, 0]
        ds.PixelSpacing = [sy, sx]                      # [row spacing, column spacing]
        ds.SliceThickness = ds.SpacingBetweenSlices = sz
        ds.SliceLocation = z0 + k * sz
        ds.Rows, ds.Columns = ny, nx
        ds.SamplesPerPixel, ds.PhotometricInterpretation = 1, "MONOCHROME2"
        ds.BitsAllocated, ds.BitsStored, ds.HighBit, ds.PixelRepresentation = 16, 16, 15, 0
        ds.RescaleIntercept, ds.RescaleSlope = -1024, 1
        ds.WindowCenter, ds.WindowWidth = 40, 400
        ds.PixelData = np.clip(hu[k] + 1024, 0, 65535).astype("<u2").tobytes()

        _save(ds, out_dir / f"IM_{file_idx:04d}_{random.Random(k).randint(1000, 9999)}.dcm")

    print(f"Wrote {nz} slices to {out_dir} ({nx}x{ny}x{nz}, spacing {sx}x{sy}x{sz} mm)")


if __name__ == "__main__":
    target = Path(sys.argv[1] if len(sys.argv) > 1 else "data/phantom_ct")
    sx, sy, sz = 1.5, 1.5, 2.0
    write_series(build_phantom(sx=sx, sy=sy, sz=sz), target, sx, sy, sz)
