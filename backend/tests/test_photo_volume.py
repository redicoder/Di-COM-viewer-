"""Photographed body: tissue / gelatin colours, orientation, cavities, colour bleeding (synthetic photo slices)."""
import json
import sys
from pathlib import Path

import numpy as np
from pydicom.dataset import Dataset, FileMetaDataset
from pydicom.uid import ExplicitVRLittleEndian, generate_uid

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))

from make_test_series import _save                                         # noqa: E402
import prepare_photo_volume as ppv                                          # noqa: E402

GEL = (30, 60, 90)          # blue gelatin
SKIN = (200, 160, 120)
MARK = (230, 40, 40)        # red marker: front, patient's left


def write_photo(path: Path, rgb_back_to_front: np.ndarray, loc: int) -> None:
    ds = Dataset()
    ds.file_meta = FileMetaDataset()
    ds.file_meta.MediaStorageSOPClassUID = "1.2.840.10008.5.1.4.1.1.7"
    ds.file_meta.MediaStorageSOPInstanceUID = generate_uid()
    ds.file_meta.TransferSyntaxUID = ExplicitVRLittleEndian
    ds.SOPClassUID = ds.file_meta.MediaStorageSOPClassUID
    ds.SOPInstanceUID = ds.file_meta.MediaStorageSOPInstanceUID
    ds.Modality = "XC"
    ds.SliceLocation = loc
    ds.Rows, ds.Columns = rgb_back_to_front.shape[:2]
    ds.SamplesPerPixel, ds.PhotometricInterpretation, ds.PlanarConfiguration = 3, "RGB", 0
    ds.BitsAllocated, ds.BitsStored, ds.HighBit, ds.PixelRepresentation = 8, 8, 7, 0
    ds.PixelData = np.ascontiguousarray(rgb_back_to_front).tobytes()
    _save(ds, path)


def phantom(folder: Path, n: int = 12, h: int = 96, w: int = 120) -> list[Path]:
    """A skin-coloured cylinder in blue gelatin, a gelatin-filled cavity inside, a red marker at the front-left.
    Written like the Visible Human photos: rows run from the back (row 0) to the front."""
    yy, xx = np.mgrid[0:h, 0:w]
    files = []
    for k in range(n):
        img = np.empty((h, w, 3), np.uint8)
        img[:] = GEL
        body = ((yy - h / 2) / 34) ** 2 + ((xx - w / 2) / 44) ** 2 <= 1
        img[body] = SKIN
        img[((yy - h / 2) / 8) ** 2 + ((xx - w / 2) / 8) ** 2 <= 1] = GEL       # sinus-like cavity
        img[(yy > h / 2 + 22) & (yy < h / 2 + 30) & (xx > w / 2 + 20) & (xx < w / 2 + 30)] = MARK
        img[:4] = 0                                                              # black frame edge
        f = folder / f"p{k}.dcm"
        write_photo(f, img, 1000 + k)
        files.append(f)
    return files


def test_tissue_and_gel_colours():
    rgb = np.array([[SKIN, GEL, MARK, (0, 0, 0), (250, 250, 245)]], np.uint8)
    assert ppv.tissue_mask(rgb).tolist() == [[True, False, True, False, False]]
    assert ppv.gel_mask(rgb).tolist() == [[False, True, False, False, False]]


def test_block_mean():
    a = np.arange(4 * 6 * 3, dtype=np.uint8).reshape(4, 6, 3)
    b = ppv.block_mean(a, 2)
    assert b.shape == (2, 3, 3) and b[0, 0, 0] == int(a[:2, :2, 0].mean())


def test_build_orientation_cavity_and_bleed(tmp_path):
    files = phantom(tmp_path)
    vol, meta = ppv.build(list(reversed(files)), factor=1)        # bottom to top
    d, h, w, _ = vol.shape
    assert meta["dims"] == [w, h, d]
    alpha = vol[..., 3] > 127
    # Rows now run front to back: the red marker (written near the photo's last rows = the front) is at low rows,
    # and on the patient's left (high x).
    red = (vol[..., 0] > 200) & (vol[..., 1] < 80) & alpha
    ys, xs = np.nonzero(red[d // 2])
    assert ys.mean() < h / 2 and xs.mean() > w / 2
    # The gelatin-filled cavity in the middle stays empty, the tissue around it is solid.
    assert not alpha[d // 2, h // 2, w // 2] and alpha[d // 2, h // 2, w // 2 + 20]
    # Outside the body the colour is bled from the skin: no blue next to the surface.
    outside = ~alpha[d // 2] & ~(vol[d // 2, ..., 3] > 0)
    rgb = vol[d // 2][outside].astype(int)
    assert (rgb[:, 2] < rgb[:, 0]).all()


def test_slice_index_reads_slice_numbers(tmp_path):
    files = phantom(tmp_path, n=3)
    found = ppv.index_slices(tmp_path)
    assert sorted(found) == [1000, 1001, 1002] and found[1001] == files[1]


def test_build_meta_is_plain_json(tmp_path):
    _, meta = ppv.build(list(reversed(phantom(tmp_path, n=4))), factor=2)
    json.dumps(meta)                                       # numpy integers would raise here
    assert meta["spacing_mm"] == [0.66, 0.66, 1.0]


def test_skin_depth_grows_inwards_and_ignores_inner_air(tmp_path):
    vol, meta = ppv.build(list(reversed(phantom(tmp_path))), factor=1)
    depth = ppv.skin_depth(vol[..., 3], meta["spacing_mm"][0]).astype(float) * ppv.SKIN_DEPTH_UNIT_MM
    d, h, w = depth.shape
    mid = d // 2
    assert depth[mid, 0, 0] == 0                                    # outside
    row = depth[mid, h // 2]                                        # left-right through the middle
    xs = np.nonzero(row)[0]
    assert row[xs[0]] < 1.0 and row[xs[-1]] < 1.0                   # just under the skin on both sides
    # The gelatin-filled cavity in the middle is not "outside": depth keeps growing towards the centre.
    assert depth[mid, h // 2, w // 2] > depth[mid, h // 2, xs[0] + 5] > 0


def test_unity_export_layout(tmp_path):
    photos = tmp_path / "photos"
    photos.mkdir()
    vol, meta = ppv.build(list(reversed(phantom(photos, n=6))), factor=1)
    body = ppv.export_unity(vol, meta, tmp_path)
    W, Dy, H = body["dims"]
    assert (W, Dy, H) == (vol.shape[2], vol.shape[0], vol.shape[1])          # x, up (slices), back (rows)
    raw = np.fromfile(tmp_path / "body.raw", np.uint8).reshape(H, Dy, W, 4)  # z (back) slowest, x fastest
    assert (raw[:, 2] == vol[2]).all()                                       # photo slice 2 = texture y 2
    assert (tmp_path / "depth.raw").stat().st_size == W * Dy * H
    assert body["skin_depth_unit_mm"] == 0.25
