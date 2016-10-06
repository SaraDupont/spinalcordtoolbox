#!/usr/bin/env python
#########################################################################################
#
# This module contains some functions and classes for patch-based machine learning
#
# ---------------------------------------------------------------------------------------
# Copyright (c) 2016 Polytechnique Montreal <www.neuro.polymtl.ca>
# Authors: Benjamin De Leener
# Modified: 2016-10-04
#
# About the license: see the file LICENSE.TXT
#########################################################################################

import os
import sct_utils as sct
from msct_image import Image
import numpy as np
import itertools


def extract_patches_from_image(path_dataset, fname_raw_images, fname_gold_images, patches_coordinates, patch_info, verbose=1):
    # input: list_raw_images
    # input: list_gold_images
    # output: list of patches. One patch is a pile of patches from (first) raw images and (second) gold images. Order are respected.

    # TODO: apply rotation of the image to take patches in planes event when doing the extraction in physical space

    patch_size = patch_info['patch_size']  # [int, int]
    patch_pixdim = patch_info['patch_pixdim']  # {'axial': [float, float], 'sagittal': [float, float], 'frontal': [float, float]}

    raw_images = [Image(path_dataset + fname) for fname in fname_raw_images]
    gold_images = [Image(path_dataset + fname) for fname in fname_gold_images]

    for k in range(len(patches_coordinates)):
        ind = [patches_coordinates[k][0], patches_coordinates[k][1], patches_coordinates[k][2]]
        patches_raw, patches_gold = [], []

        if 'axial' in patch_pixdim:
            range_x = np.linspace(ind[0] - (patch_size[0] / 2.0) * patch_pixdim['axial'][0], ind[0] + (patch_size[0] / 2.0) * patch_pixdim['axial'][0], patch_size[0])
            range_y = np.linspace(ind[1] - (patch_size[1] / 2.0) * patch_pixdim['axial'][1], ind[1] + (patch_size[1] / 2.0) * patch_pixdim['axial'][1], patch_size[1])
            coord_x, coord_y = np.meshgrid(range_x, range_y)
            coord_x = coord_x.ravel()
            coord_y = coord_y.ravel()
            coord_physical = [[coord_x[i], coord_y[i], ind[2]] for i in range(len(coord_x))]

            for raw_image in raw_images:
                grid_voxel = np.array(raw_image.transfo_phys2continuouspix(coord_physical))
                patch = np.reshape(raw_image.get_values(np.array([grid_voxel[:, 0], grid_voxel[:, 1], grid_voxel[:, 2]]),
                                                        interpolation_mode=1), (patch_size[0], patch_size[1]))
                patches_raw.append(np.expand_dims(patch, axis=0))

            for gold_image in gold_images:
                grid_voxel = np.array(gold_image.transfo_phys2continuouspix(coord_physical))
                patch = np.reshape(gold_image.get_values(np.array([grid_voxel[:, 0], grid_voxel[:, 1], grid_voxel[:, 2]]),
                                                         interpolation_mode=0), (patch_size[0], patch_size[1]))
                patches_gold.append(np.expand_dims(patch, axis=0))

        if 'sagittal' in patch_pixdim:
            range_x = np.linspace(ind[0] - (patch_size[0] / 2.0) * patch_pixdim['sagittal'][0], ind[0] + (patch_size[0] / 2.0) * patch_pixdim['sagittal'][0], patch_size[0])
            range_y = np.linspace(ind[1] - (patch_size[1] / 2.0) * patch_pixdim['sagittal'][1], ind[1] + (patch_size[1] / 2.0) * patch_pixdim['sagittal'][1], patch_size[1])
            coord_x, coord_y = np.meshgrid(range_x, range_y)
            coord_x = coord_x.ravel()
            coord_y = coord_y.ravel()
            coord_physical = [[ind[0], coord_x[i], coord_y[i]] for i in range(len(coord_x))]

            for raw_image in raw_images:
                grid_voxel = np.array(raw_image.transfo_phys2continuouspix(coord_physical))
                patch = np.reshape(raw_image.get_values(np.array([grid_voxel[:, 0], grid_voxel[:, 1], grid_voxel[:, 2]]),
                                                        interpolation_mode=1), (patch_size[0], patch_size[1]))
                patches_raw.append(np.expand_dims(patch, axis=0))

            for gold_image in gold_images:
                grid_voxel = np.array(gold_image.transfo_phys2continuouspix(coord_physical))
                patch = np.reshape(gold_image.get_values(np.array([grid_voxel[:, 0], grid_voxel[:, 1], grid_voxel[:, 2]]),
                                                         interpolation_mode=0), (patch_size[0], patch_size[1]))
                patches_gold.append(np.expand_dims(patch, axis=0))

        if 'frontal' in patch_pixdim:
            range_x = np.linspace(ind[0] - (patch_size[0] / 2.0) * patch_pixdim['frontal'][0], ind[0] + (patch_size[0] / 2.0) * patch_pixdim['frontal'][0], patch_size[0])
            range_y = np.linspace(ind[1] - (patch_size[1] / 2.0) * patch_pixdim['frontal'][1], ind[1] + (patch_size[1] / 2.0) * patch_pixdim['frontal'][1], patch_size[1])
            coord_x, coord_y = np.meshgrid(range_x, range_y)
            coord_x = coord_x.ravel()
            coord_y = coord_y.ravel()
            coord_physical = [[coord_x[i], ind[1], coord_y[i]] for i in range(len(coord_x))]

            for raw_image in raw_images:
                grid_voxel = np.array(raw_image.transfo_phys2continuouspix(coord_physical))
                patch = np.reshape(raw_image.get_values(np.array([grid_voxel[:, 0], grid_voxel[:, 1], grid_voxel[:, 2]]),
                                                        interpolation_mode=1), (patch_size[0], patch_size[1]))
                patches_raw.append(np.expand_dims(patch, axis=0))

            for gold_image in gold_images:
                grid_voxel = np.array(gold_image.transfo_phys2continuouspix(coord_physical))
                patch = np.reshape(gold_image.get_values(np.array([grid_voxel[:, 0], grid_voxel[:, 1], grid_voxel[:, 2]]),
                                                         interpolation_mode=0), (patch_size[0], patch_size[1]))
                patches_gold.append(np.expand_dims(patch, axis=0))

        patches_raw = np.concatenate(patches_raw, axis=0)
        patches_gold = np.concatenate(patches_gold, axis=0)

        yield {'patches_raw': patches_raw, 'patches_gold': patches_gold}


def get_minibatch(patch_iter, size):
    """Extract a minibatch of examples, return a tuple X_text, y.

    Note: size is before excluding invalid docs with no topics assigned.

    """
    data = [(patch['patches_raw'], patch['patches_gold']) for patch in itertools.islice(patch_iter, size)]
    if not len(data):
        return np.asarray([], dtype=np.float), np.asarray([], dtype=np.float)

    patches_raw, patches_gold = zip(*data)
    patches_raw, patches_gold = np.asarray(patches_raw, dtype=np.float), np.asarray(patches_gold, dtype=np.float)

    return {'patches_raw': patches_raw, 'patches_gold': patches_gold}

def iter_minibatches(patch_iter, minibatch_size):
    """Generator of minibatches."""
    data = get_minibatch(patch_iter, minibatch_size)
    while len(data['patches_raw']):
        yield data
        data = get_minibatch(patch_iter, minibatch_size)


class FileManager():
    def __init__(self, dataset_path, fct_explore_dataset, patch_extraction_parameters, fct_groundtruth_patch):
        self.dataset_path = sct.slash_at_the_end(dataset_path, slash=1)
        # This function should take the path to the dataset as input and outputs the list of files (wrt dataset path) that compose the dataset (image + groundtruth)
        self.fct_explore_dataset = fct_explore_dataset

        self.patch_extraction_parameters = patch_extraction_parameters
        # ratio_dataset represents the ratio between the training, testing and validation datasets.
        # default is: 60% training, 20% testing, 20% validation
        if 'ratio_dataset' in self.patch_extraction_parameters:
            self.ratio_dataset = self.patch_extraction_parameters['ratio_dataset']
        else:
            self.ratio_dataset = [0.6, 0.2, 0.2]
        # patch size is the number of pixels that are in a patch in each dimensions. Patches are only 2D
        # warning: patch size must correspond to the ClassificationModel
        # Example: [32, 32] means a patch with 32x32 pixels
        if 'patch_size' in self.patch_extraction_parameters:
            self.patch_size = self.patch_extraction_parameters['patch_size']
        else:
            self.patch_size = None
        # patch_pixdim represents the resolution of the patch
        if 'patch_pixdim' in self.patch_extraction_parameters:
            self.patch_pixdim = self.patch_extraction_parameters['patch_pixdim']
        else:
            self.patch_pixdim = None
        # extract_all_positive is a boolean variable. If True, the system extracts all positive patches from the dataset
        if 'extract_all_positive' in self.patch_extraction_parameters:
            self.extract_all_positive = self.patch_extraction_parameters['extract_all_positive']
        else:
            self.extract_all_positive = False
        # extract_all_negative is a boolean variable. If True, the system extracts all positive patches from the dataset
        if 'extract_all_negative' in self.patch_extraction_parameters:
            self.extract_all_negative = self.patch_extraction_parameters['extract_all_negative']
        else:
            self.extract_all_negative = False
        # ratio_patches_voxels is the ratio of patches to extract in all the possible patches in the images. Typically = 10%
        if 'ratio_patches_voxels' in self.patch_extraction_parameters:
            self.ratio_patches_voxels = self.patch_extraction_parameters['ratio_patches_voxels']
        else:
            self.ratio_patches_voxels = 0.1

        # patch_info is the structure that will be transmitted for patches extraction
        self.patch_info = {'patch_size': self.patch_size, 'patch_pixdim': self.patch_pixdim}

        # this function will be called on each patch to know its class/label
        self.fct_groundtruth_patch = fct_groundtruth_patch

        self.list_files = np.array(self.fct_explore_dataset(self.dataset_path))
        self.number_of_images = len(self.list_files)

        self.training_dataset, self.testing_dataset, self.validation_dataset = [], [], []

        # list_classes is a dictionary that contains all the classes that are present in the dataset
        # this list is filled up iteratively while exploring the dataset
        # the key is the label of the class and the element is the number of element of each class
        self.list_classes = {}

        # class_weights is a dictionary containing the ratio of each class and the most represented class
        # len(class_weights) = len(list_classes)
        self.class_weights = {}

    def decompose_dataset(self):
        array_indexes = range(self.number_of_images)
        np.random.shuffle(array_indexes)

        self.training_dataset = self.list_files[np.ix_(array_indexes[:int(self.ratio_dataset[0]*self.number_of_images)])]
        self.testing_dataset = self.list_files[np.ix_(array_indexes[int(self.ratio_dataset[0] * self.number_of_images):int((self.ratio_dataset[0] + self.ratio_dataset[1]) * self.number_of_images)])]
        self.validation_dataset = self.list_files[np.ix_(array_indexes[int((self.ratio_dataset[0] + self.ratio_dataset[1]) * self.number_of_images):])]

        return self.training_dataset, self.testing_dataset, self.validation_dataset

    def compute_patches_coordinates(self, image):
        if self.extract_all_negative or self.extract_all_positive:
            print 'Extract all negative/positive patches: feature not yet ready...'

        image_dim = image.dim

        x, y, z = np.mgrid[0:image_dim[0], 0:image_dim[1], 0:image_dim[2]]
        indexes = np.array(zip(x.ravel(), y.ravel(), z.ravel()))
        physical_coordinates = np.asarray(image.transfo_pix2phys(indexes))

        random_batch = np.random.choice(physical_coordinates.shape[0], int(round(physical_coordinates.shape[0] * self.ratio_patches_voxels)))

        return physical_coordinates[random_batch]

    def explore(self):
        # training dataset
        for i, fnames in enumerate(self.training_dataset):
            fname_raw_images = self.training_dataset[i][0]
            fname_gold_images = self.training_dataset[i][1]
            reference_image = Image(self.dataset_path + fname_raw_images[0])  # first raw image is selected as reference

            patches_coordinates = self.compute_patches_coordinates(reference_image)
            print patches_coordinates.shape

            stream_data = extract_patches_from_image(path_dataset=self.dataset_path,
                                                     fname_raw_images=fname_raw_images,
                                                     fname_gold_images=fname_gold_images,
                                                     patches_coordinates=patches_coordinates,
                                                     patch_info=self.patch_info,
                                                     verbose=1)

            minibatch_iterator_test = iter_minibatches(stream_data, 10)
            for i, data in enumerate(minibatch_iterator_test):
                pass

            print 'fin'

        return



#########################################
# USE CASE
#########################################
def extract_list_file_from_path(path_data):
    ignore_list = ['.DS_Store']
    sct.printv('Extracting ' + path_data)
    cr = '\r'

    list_data = []
    for root, dirs, files in os.walk(path_data):
        for fname_im in files:
            if fname_im in ignore_list:
                continue
            if 'seg' in fname_im or 'gmseg' in fname_im:
                continue
            f_seg = None
            for fname_seg in files:
                if fname_im[:-7] in fname_seg:
                    f_seg = fname_seg
            list_data.append([[fname_im], [f_seg]])

    return list_data


my_file_manager = FileManager(dataset_path='/Users/benjamindeleener/data/data_augmentation/large_nobrain_nopad/',
                              fct_explore_dataset=extract_list_file_from_path,
                              patch_extraction_parameters={'ratio_dataset': [0.6, 0.2, 0.2],
                                                           'patch_size': [32, 32],
                                                           'patch_pixdim': {'axial': [1.0, 1.0]},
                                                           'extract_all_positive': True,
                                                           'extract_all_negative': False},
                              fct_groundtruth_patch=None)

training_dataset, testing_dataset, validation_dataset = my_file_manager.decompose_dataset()
my_file_manager.explore()

