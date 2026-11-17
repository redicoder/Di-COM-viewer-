"""Lining the photographs up: a run's beginning is found by its lone jump, a slanting part and a blank photograph are
not taken for one, and every photograph read from a folder with a registration comes moved by it."""
import json
import sys
from pathlib import Path

import numpy as np
import pytest

pytest.importorskip("pydicom")
pytest.importorskip("scipy")
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))

import prepare_photo_volume as ppv  # noqa: E402
import register_photos  # noqa: E402


def blobs(shape=(96, 128), seed=3):
    from scipy import ndimage
    return ndimage.gaussian_filter(np.random.default_rng(seed).random(shape), 1.5)


def test_a_picture_moved_sideways_is_measured():
    a = blobs()
    rows, cols, peak = register_photos.shift_between(a, np.roll(a, (0, -6), axis=(0, 1)))      # its content six pixels to the left
    assert (rows, cols) == (0.0, -6.0) and peak > 0.5
    rows, cols, _ = register_photos.shift_between(a, np.roll(a, (3, 2), axis=(0, 1)))
    assert (rows, cols) == (3.0, 2.0)


def measured(n=120):
    """Every photograph on the one before it, measured right before it, with a clear peak."""
    shifts = np.zeros((n, 4))
    shifts[:, 2], shifts[:, 3] = 0.3, 1
    return shifts


def test_a_run_begins_at_a_lone_jump_and_everything_after_it_is_moved_back():
    shifts = measured()
    shifts[40, :2] = (0.0, -12.0)                                       # a run begins: the picture jumps 12 pixels to the left
    shifts[70, :2] = (0.0, 13.0)                                        # and another, 13 to the right
    jump = register_photos.jumps(shifts)
    assert np.flatnonzero(np.abs(jump).sum(axis=1)).tolist() == [40, 70]
    move = register_photos.moves(jump)
    assert move[39].tolist() == [0, 0] and move[40].tolist() == [0, 12] and move[69].tolist() == [0, 12] and move[70].tolist() == [0, -1]
    runs = register_photos.runs_of(list(range(2000, 2000 - 120, -1)), move)
    assert [r["from_slice"] for r in runs] == [2000, 1960, 1930] and runs[1]["move_px"] == [0, 12]


def test_a_slanting_part_is_not_a_run_and_a_jump_on_top_of_it_still_is():
    shifts = measured()
    shifts[20:60, 0] = -4.0                                             # a foot slanting through the stack: every photograph four pixels on
    assert not register_photos.jumps(shifts)[25:55].any()
    shifts[40, :2] = (-4.0, 9.0)                                        # the picture jumps sideways in the middle of it
    jump = register_photos.jumps(shifts)
    assert jump[40].tolist() == [0.0, 9.0] and np.abs(jump).sum() == 9.0


def test_what_cannot_be_measured_is_not_taken_for_a_run():
    shifts = measured()
    shifts[30] = (0.0, 40.0, 0.01, 1)                                   # no likeness at all (a photograph that is not whole)
    shifts[50] = (0.0, 0.0, -1.0, 0)                                    # a blank one
    shifts[51] = (6.0, -7.0, 0.2, 2)                                    # the first after it: measured across the gap
    shifts[80, :2] = (0.0, 2.0)                                         # two pixels: under a millimetre, left alone
    assert not register_photos.jumps(shifts).any()


def test_a_jump_counts_only_when_both_halves_of_the_picture_show_it():
    assert register_photos.agree([0.0, -13.0], [np.array([0.0, -14.0]), np.array([0.0, -13.0])])
    assert not register_photos.agree([3.0, 0.0], [np.array([0.0, -1.0]), np.array([0.0, 1.0])])       # two legs, each going its own way
    assert not register_photos.agree([0.0, -3.0], [np.array([0.0, -4.0]), np.array([0.0, 0.0])])      # one half only
    assert not register_photos.agree([0.0, -13.0], [np.array([0.0, -13.0]), None])                    # a half with no body in it: not known
    assert register_photos.agree([0.0, -13.0], [np.array([1.0, -15.5]), np.array([1.0, -13.0])])      # a big jump, measured to a few pixels on a half
    assert not register_photos.agree([0.0, -3.0], [np.array([0.5, -3.5]), np.array([1.0, -1.0])])     # a small one must be shown closely by both


def test_a_pixel_the_other_way_is_not_part_of_a_jump():
    shifts = measured()
    shifts[40, :2] = (-1.0, 12.0)
    assert register_photos.jumps(shifts)[40].tolist() == [0.0, 12.0]


def test_a_picture_is_moved_by_whole_pixels_and_black_comes_in_at_the_edge():
    a = np.arange(1, 25, dtype=np.uint8).reshape(4, 6)
    right = ppv.moved(a, 0, 2)
    assert (right[:, 2:] == a[:, :4]).all() and not right[:, :2].any()
    up_left = ppv.moved(a, -1, -2)
    assert (up_left[:3, :4] == a[1:, 2:]).all() and not up_left[3].any() and not up_left[:, 4:].any()
    assert ppv.moved(a, 0, 0) is a


def photograph(path: Path, number: int, image: np.ndarray) -> None:
    """A colour photograph as the NLM's are stored (one DICOM, its slice number as SliceLocation)."""
    from pydicom.dataset import FileDataset, FileMetaDataset
    from pydicom.uid import ExplicitVRLittleEndian, SecondaryCaptureImageStorage, generate_uid
    meta = FileMetaDataset()
    meta.MediaStorageSOPClassUID = SecondaryCaptureImageStorage
    meta.MediaStorageSOPInstanceUID = generate_uid()
    meta.TransferSyntaxUID = ExplicitVRLittleEndian
    ds = FileDataset(str(path), {}, file_meta=meta, preamble=b"\0" * 128)
    ds.SOPClassUID, ds.SOPInstanceUID = meta.MediaStorageSOPClassUID, meta.MediaStorageSOPInstanceUID
    ds.Rows, ds.Columns = image.shape[:2]
    ds.SamplesPerPixel, ds.PhotometricInterpretation, ds.PlanarConfiguration = 3, "RGB", 0
    ds.BitsAllocated = ds.BitsStored = 8
    ds.HighBit, ds.PixelRepresentation = 7, 0
    ds.SliceLocation = str(number)
    ds.PixelData = image.tobytes()
    ds.save_as(str(path))


def test_photographs_are_read_moved_by_their_folders_registration(tmp_path):
    image = np.zeros((8, 10, 3), np.uint8)
    image[2, 3] = (200, 40, 30)                                         # one red pixel; the file's own rows run back to front
    photograph(tmp_path / "slice_1500.dcm", 1500, image)
    photograph(tmp_path / "slice_1501.dcm", 1501, image)
    ppv._registrations.clear()
    plain = ppv.read_photo(tmp_path / "slice_1500.dcm")
    assert plain[5, 3, 0] == 200                                        # rows flipped: front to back
    (tmp_path / ppv.REGISTRATION).write_text(json.dumps({"move_px_by_slice": {"1500": [0, 4], "1501": [0, 0]}}))
    ppv._registrations.clear()
    assert ppv.read_photo(tmp_path / "slice_1500.dcm")[5, 7, 0] == 200 and ppv.read_photo(tmp_path / "slice_1500.dcm")[5, 3, 0] == 0
    assert ppv.read_photo(tmp_path / "slice_1501.dcm")[5, 3, 0] == 200  # a photograph of the first run stays
    assert ppv.read_photo(tmp_path / "slice_1500.dcm", registered=False)[5, 3, 0] == 200       # as it comes, for measuring
    ppv._registrations.clear()


def export_of(folder: Path, slices) -> Path:
    folder.mkdir()
    (folder / "photo.json").write_text(json.dumps({"crop_photo_px": {"rows": [240, 972], "cols": [732, 1296]}, "slices": list(slices)}))
    (folder / "labels.json").write_text(json.dumps({"objects": [], "ct_bone": {"corners_mm_by_slice": {"1010": [76.0, 200.0]}}}))
    return folder


def test_an_export_of_one_run_is_moved_to_its_place_and_one_across_two_runs_is_refused(tmp_path):
    table = {n: (0, 17) for n in range(1001, 1231)}
    table.update({n: (0, 8) for n in range(1231, 1253)})
    head = export_of(tmp_path / "head", (1001, 1225))
    assert register_photos.move_export(head, table, log=lambda *_: None) == (0, 17)
    photo = json.loads((head / "photo.json").read_text())
    assert photo["crop_photo_px"] == {"rows": [240, 972], "cols": [749, 1313]} and photo["registered"] and photo["moved"]["crop_before"]["cols"] == [732, 1296]
    corner = json.loads((head / "labels.json").read_text())["ct_bone"]["corners_mm_by_slice"]["1010"]
    assert corner == [76.0, pytest.approx(200.0 + 17 * 0.33)]           # the CT's place on it moves with it
    with pytest.raises(SystemExit):
        register_photos.move_export(head, table, log=lambda *_: None)   # not twice
    with pytest.raises(SystemExit):
        register_photos.move_export(export_of(tmp_path / "neck", (1220, 1245)), table, log=lambda *_: None)      # two runs: a step inside it
