#!/usr/bin/env python
#######################################################################################################################
#
# Analyse texture
#
# ----------------------------------------------------------------------------------------------------------------------
# Copyright (c) 2014 Polytechnique Montreal <www.neuro.polymtl.ca>
# Author: Charley
# Modified: 2017-06-13
#
# About the license: see the file LICENSE.TXT
########################################################################################################################

import os
import shutil
import sys
import numpy as np
import itertools
from math import radians
from skimage.feature import greycomatrix, greycoprops

# import sct_maths
from msct_image import Image
from msct_parser import Parser
from sct_image import set_orientation, get_orientation
from sct_utils import (add_suffix, extract_fname, printv, run,
                       slash_at_the_end, Timer, tmp_create)

'''
TODO:
  - optimiser le temps de calcul: croper autour de la moelle
  - tester sct_extract_metric
'''


def get_parser():
    # Initialize the parser
    parser = Parser(__file__)
    parser.usage.set_description('Extraction of GLCM texture features from an image within a given mask.\n'
                                 ' It calculates the texture properties of a grey level co-occurence matrix (GLCM).'
                                 ' The textures features are those defined in the sckit-image implementation:\n'
                                 ' http://scikit-image.org/docs/dev/api/skimage.feature.html#greycoprops\n'
                                 ' This function outputs one nifti file per texture metric (contrast, dissimilarity, homogeneity, ASM, energy, correlation) and per orientation called fnameIn_property_distance_angle.nii.gz')
    parser.add_option(name="-i",
                      type_value="file",
                      description="Image to analyse",
                      mandatory=True,
                      example='t2.nii.gz')
    parser.add_option(name="-s",
                      type_value="file",
                      description="Image mask",
                      mandatory=True,
                      example='t2_seg.nii.gz')
    parser.add_option(name="-param",
                      type_value="str",
                      description="Parameters for extraction. Separate arguments with \":\".\n"
                                  "prop: <list_str> list of GLCM texture properties: "+ParamGLCM().prop+".\n Default="+ParamGLCM().prop+"\n"
                                  "distance: <int> distance offset in pixel (suggested distance values between 1 and 5).\n Default="+str(ParamGLCM().distance)+"\n"
                                  "angle: <list_int> list of angles in degrees (suggested distance values between 0 and 179).\n Default="+ParamGLCM().angle+"\n",
                      mandatory=False,
                      example="prop=energy:distance=1:angle=0,90:mean=0")
    parser.add_option(name="-mean",
                      type_value='multiple_choice',
                      description="1: Output a file averaging each metric across the angles",
                      mandatory=False,
                      default_value=int(Param().mean),
                      example=['0', '1'])
    parser.add_option(name="-dim",
                      type_value='multiple_choice',
                      description="Compute the texture on the axial (ax), sagittal (sag) or coronal (cor) slices.",
                      mandatory=False,
                      default_value=Param().dim,
                      example=['ax', 'sag', 'cor'])
    parser.add_option(name="-ofolder",
                      type_value="folder_creation",
                      description="Output folder",
                      mandatory=False,
                      default_value=Param().path_results,
                      example='/my_texture/')
    parser.add_option(name="-r",
                      type_value="multiple_choice",
                      description="Remove temporary files.",
                      mandatory=False,
                      default_value=str(int(Param().rm_tmp)),
                      example=['0', '1'])
    parser.add_option(name="-v",
                      type_value='multiple_choice',
                      description="Verbose: 0 = nothing, 1 = classic, 2 = expended",
                      mandatory=False,
                      example=['0', '1', '2'],
                      default_value=str(Param().verbose))

    return parser

class ExtractGLCM:
  def __init__(self, param=None, param_glcm=None):
    self.param = param if param is not None else Param()
    self.param_glcm = param_glcm if param_glcm is not None else ParamGLCM()

    # create tmp directory
    self.tmp_dir = tmp_create(verbose=self.param.verbose)  # path to tmp directory

    if self.param.dim == 'ax':
      self.orientation_extraction = 'RPI'
    elif self.param.dim == 'sag':
      self.orientation_extraction = 'IPR'
    else:
      self.orientation_extraction = 'IRP'

    # metric_lst=['property_distance_angle']
    self.metric_lst = []
    for m in list(itertools.product(self.param_glcm.prop.split(','), self.param_glcm.angle.split(','))):
      text_name = m[0] if m[0].upper()!='asm'.upper() else m[0].upper()
      self.metric_lst.append(text_name+'_'+str(self.param_glcm.distance)+'_'+str(m[1]))

    # dct_im_seg{'im': list_of_axial_slice, 'seg': list_of_axial_masked_slice}
    self.dct_im_seg = {'im': None, 'seg': None}

    # to re-orient the data at the end if needed
    self.orientation_im = get_orientation(Image(self.param.fname_im))

    self.fname_metric_lst = {}

  def extract(self):
    self.ifolder2tmp()

    # fill self.dct_metric --> for each key_metric: create an Image with zero values
    self.init_metric_im()
    
    # fill self.dct_im_seg --> extract axial slices from self.param.fname_im and self.param.fname_seg
    self.extract_slices()

    # compute texture
    self.compute_texture()

    # reorient data
    if self.orientation_im != self.orientation_extraction:
      self.reorient_data()

    # mean across angles
    if self.param.mean:
      self.mean_angle()

    # save results to ofolder
    self.tmp2ofolder()

    return [self.param.path_results+self.fname_metric_lst[f] for f in self.fname_metric_lst]

  def tmp2ofolder(self):

    printv('\nSave resulting files...', self.param.verbose, 'normal')
    for f in self.fname_metric_lst: # Copy from tmp folder to ofolder
      shutil.copy(self.fname_metric_lst[f], self.param.path_results+self.fname_metric_lst[f])

    os.chdir('..') # go back to original directory

  def ifolder2tmp(self):
    # copy input image
    if self.param.fname_im is not None:
      shutil.copy(self.param.fname_im, self.tmp_dir)
      self.param.fname_im = ''.join(extract_fname(self.param.fname_im)[1:])
    else:
      printv('ERROR: No input image', self.param.verbose, 'error')

    # copy masked image
    if self.param.fname_seg is not None:
      shutil.copy(self.param.fname_seg, self.tmp_dir)
      self.param.fname_seg = ''.join(extract_fname(self.param.fname_seg)[1:])
    else:
      printv('ERROR: No mask image', self.param.verbose, 'error')

    os.chdir(self.tmp_dir) # go to tmp directory

  def mean_angle(self):

    im_metric_lst = list(set([self.fname_metric_lst[f].split('_'+str(self.param_glcm.distance)+'_')[0]+'_' for f in self.fname_metric_lst]))

    printv('\nMean across angles...', self.param.verbose, 'normal')
    for im_m in im_metric_lst:     # Loop across GLCM texture properties
      # List images to mean
      im2mean_lst = [im_m+str(self.param_glcm.distance)+'_'+a+extract_fname(self.param.fname_im)[2] for a in self.param_glcm.angle.split(',')]
      
      # Average across angles and save it as wrk_folder/property_distance_mean.extension
      fname_out = im_m+'mean'+extract_fname(self.param.fname_im)[2]
      run('sct_image -i '+','.join(im2mean_lst)+' -concat t -o '+fname_out, error_exit='warning', raise_exception=True)
      run('sct_maths -i '+fname_out+' -mean t -o '+fname_out, error_exit='warning', raise_exception=True)
      self.fname_metric_lst[im_m+'mean']=fname_out

  def extract_slices(self):

    # open image and re-orient it to RPI if needed
    if self.orientation_im == self.orientation_extraction:
      im, seg = Image(self.param.fname_im), Image(self.param.fname_seg)
    else:
      im, seg = set_orientation(Image(self.param.fname_im), self.orientation_extraction), set_orientation(Image(self.param.fname_seg), self.orientation_extraction)

    # extract axial slices in self.dct_im_seg
    self.dct_im_seg['im'], self.dct_im_seg['seg'] = [im.data[:,:,z] for z in range(im.dim[2])], [seg.data[:,:,z] for z in range(im.dim[2])]

  def init_metric_im(self):

    # open image and re-orient it to RPI if needed
    im_tmp = Image(self.param.fname_im) if self.orientation_im == self.orientation_extraction else set_orientation(Image(self.param.fname_im), self.orientation_extraction)

    # create Image objects with zeros values for each output image needed
    for m in self.metric_lst:
      im_2save = im_tmp.copy()
      im_2save.changeType(type='float64')
      im_2save.data *= 0
      fname_out = add_suffix(''.join(extract_fname(self.param.fname_im)[1:]), '_'+m)
      im_2save.setFileName(fname_out)
      im_2save.save()
      self.fname_metric_lst[m] = fname_out 

  def compute_texture(self):

    offset = int(self.param_glcm.distance)

    printv('\nCompute texture metrics...', self.param.verbose, 'normal')

    dct_metric = {}
    for m in self.metric_lst:
      dct_metric[m] = Image(self.fname_metric_lst[m])

    timer = Timer(number_of_iteration=len(self.dct_im_seg['im']))
    timer.start()

    for im_z, seg_z,zz in zip(self.dct_im_seg['im'],self.dct_im_seg['seg'],range(len(self.dct_im_seg['im']))):
      for xx in range(im_z.shape[0]):
        for yy in range(im_z.shape[1]):
          if not seg_z[xx, yy]:
            continue
          if xx < offset or yy < offset:
              continue
          if xx > (im_z.shape[0] - offset-1) or yy > (im_z.shape[1] - offset-1):
              continue # to check if the whole glcm_window is in the axial_slice
          if False in np.unique(seg_z[xx-offset : xx+offset+1, yy-offset : yy+offset+1]):
              continue # to check if the whole glcm_window is in the mask of the axial_slice

          glcm_window = im_z[xx-offset : xx+offset+1, yy-offset : yy+offset+1]
          glcm_window = glcm_window.astype(np.uint8)

          dct_glcm = {}
          for a in self.param_glcm.angle.split(','): # compute the GLCM for self.param_glcm.distance and for each self.param_glcm.angle
            dct_glcm[a] = greycomatrix(glcm_window, [self.param_glcm.distance], [radians(int(a))],  symmetric = self.param_glcm.symmetric, normed = self.param_glcm.normed)

          for m in self.metric_lst: # compute the GLCM property (m.split('_')[0]) of the voxel xx,yy,zz
            dct_metric[m].data[xx,yy,zz] = greycoprops(dct_glcm[m.split('_')[2]], m.split('_')[0])[0][0]
            # im_cur = Image(self.fname_metric_lst[m])
            # im_cur.data[xx,yy,zz] = greycoprops(dct_glcm[m.split('_')[2]], m.split('_')[0])[0][0]

      timer.add_iteration()
    
    timer.stop()

    for m in self.metric_lst:
      dct_metric[m].setFileName(self.fname_metric_lst[m])
      dct_metric[m].save()


  def reorient_data(self):
    for f in self.fname_metric_lst:
      im = Image(self.fname_metric_lst[f])
      im = set_orientation(im, self.orientation_im)
      im.setFileName(self.fname_metric_lst[f])
      im.save() 

class Param:
  def __init__(self):
    self.fname_im = None
    self.fname_seg = None
    self.path_results = './texture/'
    self.verbose = '1'
    self.mean = '0'
    self.dim = 'ax'
    self.rm_tmp = True

class ParamGLCM(object):
  def __init__(self, symmetric=True, normed=True, prop='contrast,dissimilarity,homogeneity,energy,correlation,ASM', distance='1', angle='0,45,90,135', mean='0'):
    self.symmetric = True  # If True, the output matrix P[:, :, d, theta] is symmetric.
    self.normed = True  # If True, normalize each matrix P[:, :, d, theta] by dividing by the total number of accumulated co-occurrences for the given offset. The elements of the resulting matrix sum to 1.
    self.prop = 'contrast,dissimilarity,homogeneity,energy,correlation,ASM' # The property formulae are detailed here: http://scikit-image.org/docs/dev/api/skimage.feature.html#greycoprops
    self.distance = 1 # Size of the window: distance = 1 --> a reference pixel and its immediate neighbour
    self.angle = '0,45,90,135' # Rotation angles for co-occurrence matrix
    self.mean = '0' # Output or not a file averaging each metric across the angles

  # update constructor with user's parameters
  def update(self, param_user):
    param_lst = param_user.split(':')
    for param in param_lst:
      obj = param.split('=')
      setattr(self, obj[0], obj[1])

def main(args=None):
  if args is None:
    args = sys.argv[1:]

  # create param object
  param = Param()
  param_glcm = ParamGLCM()

  # get parser
  parser = get_parser()
  arguments = parser.parse(args)

  # set param arguments ad inputted by user
  param.fname_im = arguments["-i"]
  param.fname_seg = arguments["-s"]

  if '-ofolder' in arguments:
    param.path_results = slash_at_the_end(arguments["-ofolder"], slash=1)
  if not os.path.isdir(param.path_results) and os.path.exists(param.path_results):
      sct.printv("ERROR output directory %s is not a valid directory" % param.path_results, 1, 'error')
  if not os.path.exists(param.path_results):
      os.makedirs(param.path_results)

  if '-mean' in arguments:
    param.mean = bool(int(arguments['-mean']))
  if '-dim' in arguments:
    param.dim = arguments['-dim']
  if '-r' in arguments:
    param.rm_tmp = bool(int(arguments['-r']))
  if '-v' in arguments:
    param.verbose = bool(int(arguments['-v']))
  if '-param' in arguments:
    param_glcm.update(arguments['-param'])

  # create the GLCM constructor
  glcm = ExtractGLCM(param=param, param_glcm=param_glcm)
  # run the extraction
  fname_out_lst = glcm.extract()

  # remove tmp_dir
  if param.rm_tmp:
    shutil.rmtree(glcm.tmp_dir)
        
  printv('\nDone! To view results, type:', param.verbose)
  printv('fslview ' + arguments["-i"] + ' ' + ' -l Red-Yellow -t 0.7 '.join(fname_out_lst) + ' -l Red-Yellow -t 0.7 & \n', param.verbose, 'info')

    
if __name__ == "__main__":
    main()