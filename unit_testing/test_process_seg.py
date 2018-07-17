#!/usr/bin/env python
# -*- coding: utf-8
# pytest unit tests for spinalcordtoolbox.process_seg

import numpy as np
import nibabel as nib
import pytest
from spinalcordtoolbox import process_seg

@pytest.fixture(scope="session")
def dummy_segmentation():
    """Create a dummy image with a circle or ones running from top to bottom in the 3rd dimension"""
    nx, ny, nz = 20, 20, 20  # image dimension
    fname_seg = 'dummy_segmentation.nii.gz'  # output seg
    data = np.random.random((nx, ny, nz))
    xx, yy = np.mgrid[:nx, :ny]
    # loop across slices and add a circle of radius 3 pixels
    for iz in range(nz):
        data[:, :, iz] = ((xx - nx/2) ** 2 + (yy - ny/2) ** 2 <= 3 ** 2) * 1
    xform = np.eye(4)
    img = nib.nifti1.Nifti1Image(data, xform)
    nib.save(img, fname_seg)
    return fname_seg

def test_extract_centerline(dummy_segmentation):
    process_seg.extract_centerline(dummy_segmentation, 0, verbose=0, algo_fitting='hanning', type_window='hanning',
                                   window_length=80, use_phys_coord=True, file_out='centerline')
