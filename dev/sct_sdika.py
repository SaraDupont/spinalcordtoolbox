#!/usr/bin/env python
#########################################################################################
#
# Pipeline for the Sdika Project
#           - Import data from /data_shared/sct_testing/large/
#           - Unification of orientation, name convention
#           - Transfert data to ferguson to be process
#           - Compute the metrics / Evaluate the performance of Sdika Algorithm
#
# ---------------------------------------------------------------------------------------
# Authors: Charley
# Modified: 2017-01-25
#
#########################################################################################


# ****************************      IMPORT      *****************************************  
# Utils Imports
import pickle
import os
import nibabel as nib #### A changer en utilisant Image
import shutil
import numpy as np
from math import sqrt
from collections import Counter
import random
import json
import argparse
import seaborn as sns
import matplotlib.pyplot as plt
import itertools
import pandas as pd
from scipy.stats import ttest_rel
# SCT Imports
from msct_image import Image
import sct_utils as sct
# ***************************************************************************************


TODO_STRING = """\n
            - Export dataset info into a excel file
            - Clean step 3
            - Set code comptatible with CNN approach
            - ...
            \n
            """


# ****************************      UTILS FUNCTIONS      ********************************

def create_folders_local(folder2create_lst):
    """
    
      Create folders if not exist
    
          Inputs:
              - folder2create_lst [list of string]: list of folder paths to create
          Outputs:
              -
    
    """           
    
    for folder2create in folder2create_lst:
        if not os.path.exists(folder2create):
            os.makedirs(folder2create)

# ***************************************************************************************



# ****************************      STEP 0 FUNCTIONS      *******************************

def find_img_testing(path_large, contrast, path_local):
    """
    
      Explore a database folder (path_large)...
      ...and extract path to images for a given contrast (contrast)
    
          Inputs:
              - path_large [string]: path to database
              - contrast [string]: contrast of interest ('t2', 't1', 't2s')
          Outputs:
              - path_img [list of string]: list of image path
              - path_seg [list of string]: list of segmentation path
    
    """   

    center_lst, pathology_lst, path_img, path_seg = [], [], [], []
    for subj_fold in os.listdir(path_large):
        path_subj_fold = path_large + subj_fold + '/'

        if os.path.isdir(path_subj_fold):
            contrast_fold_lst = [contrast_fold for contrast_fold in os.listdir(path_subj_fold) 
                                                    if os.path.isdir(path_subj_fold+contrast_fold+'/')]
            contrast_fold_lst_oI = [contrast_fold for contrast_fold in contrast_fold_lst 
                                                    if contrast_fold==contrast or contrast_fold.startswith(contrast+'_')]
            
            # If this subject folder contains a subfolder related to the contrast of interest
            if len(contrast_fold_lst_oI):

                # Depending on the number of folder of interest:
                if len(contrast_fold_lst_oI)>1:
                    # In our case, we prefer axial images when available
                    ax_candidates = [tt for tt in contrast_fold_lst_oI if 'ax' in tt]
                    if len(ax_candidates):
                        contrast_fold_oI = ax_candidates[0]
                    else:
                        contrast_fold_oI = contrast_fold_lst_oI[0]                                               
                else:
                    contrast_fold_oI = contrast_fold_lst_oI[0]

                # For each subject and for each contrast, we want to pick only one image
                path_contrast_fold = path_subj_fold+contrast_fold_oI+'/'

                # If segmentation_description.json is available
                if os.path.exists(path_contrast_fold+'segmentation_description.json'):

                    with open(path_contrast_fold+'segmentation_description.json') as data_file:    
                        data_seg_description = json.load(data_file)
                        data_file.close()

                    # If manual segmentation of the cord is available
                    if len(data_seg_description['cord']):

                        # Extract data information from the dataset_description.json
                        with open(path_subj_fold+'dataset_description.json') as data_file:    
                            data_description = json.load(data_file)
                            data_file.close()

                        path_img_cur = path_contrast_fold+contrast_fold_oI+'.nii.gz'
                        path_seg_cur = path_contrast_fold+contrast_fold_oI+'_seg_manual.nii.gz'
                        if os.path.exists(path_img_cur) and os.path.exists(path_seg_cur):
                            path_img.append(path_img_cur)
                            path_seg.append(path_seg_cur)
                            center_lst.append(data_description['Center'])
                            pathology_lst.append(data_description['Pathology'])
                        else:
                            print '\nWARNING: file lacks: ' + path_contrast_fold + '\n'


    img_patho_lstoflst = [[i.split('/')[-3].split('.nii.gz')[0].split('_t2')[0], p] for i,p in zip(path_img,pathology_lst)]
    img_patho_dct = {}
    for ii_pp in img_patho_lstoflst:
        if not ii_pp[1] in img_patho_dct:
            img_patho_dct[ii_pp[1]] = []
        img_patho_dct[ii_pp[1]].append(ii_pp[0])
    if '' in img_patho_dct:
        for ii in img_patho_dct['']:
            img_patho_dct['HC'].append(ii)
        del img_patho_dct['']

    fname_pkl_out = path_local + 'patho_dct_' + contrast + '.pkl'
    pickle.dump(img_patho_dct, open(fname_pkl_out, "wb"))

    # Remove duplicates
    center_lst = list(set(center_lst))
    center_lst = [center for center in center_lst if center != ""]
    # Remove HC and non specified pathologies
    pathology_lst = [patho for patho in pathology_lst if patho != "" and patho != "HC"]
    pathology_dct = {x:pathology_lst.count(x) for x in pathology_lst}

    print '\n\n***************Contrast of Interest: ' + contrast + ' ***************'
    print '# of Subjects: ' + str(len(path_img))
    print '# of Centers: ' + str(len(center_lst))
    print 'Centers: ' + ', '.join(center_lst)
    print 'Pathologies:'
    print pathology_dct
    print '\n'

    return path_img, path_seg

def transform_nii_img(img_lst, path_out):
    """
    
      List .nii images which need to be converted to .img format
      + set same orientation RPI
      + set same value format (int16)
    
          Inputs:
              - img_lst [list of string]: list of path to image to transform
              - path_out [string]: path to folder where to save transformed images
          Outputs:
              - path_img2convert [list of string]: list of image paths to convert
    
    """   

    path_img2convert = []
    for img_path in img_lst:
        path_cur = img_path
        path_cur_out = path_out + '_'.join(img_path.split('/')[5:7]) + '.nii.gz'
        if not os.path.isfile(path_cur_out):
            shutil.copyfile(path_cur, path_cur_out)
            sct.run('sct_image -i ' + path_cur_out + ' -type int16 -o ' + path_cur_out)
            sct.run('sct_image -i ' + path_cur_out + ' -setorient RPI -o ' + path_cur_out)
            # os.system('sct_image -i ' + path_cur_out + ' -type int16 -o ' + path_cur_out)
            # os.system('sct_image -i ' + path_cur_out + ' -setorient RPI -o ' + path_cur_out)
        path_img2convert.append(path_cur_out)

    return path_img2convert

def transform_nii_seg(seg_lst, path_out, path_gold):
    """
    
      List .nii segmentations which need to be converted to .img format
      + set same orientation RPI
      + set same value format (int16)
      + set same header than related image
      + extract centerline from '*_seg_manual.nii.gz' to create gold standard
    
          Inputs:
              - seg_lst [list of string]: list of path to segmentation to transform
              - path_out [string]: path to folder where to save transformed segmentations
              - path_gold [string]: path to folder where to save gold standard centerline
          Outputs:
              - path_segs2convert [list of string]: list of segmentation paths to convert
    
    """

    path_seg2convert = []
    for seg_path in seg_lst:
        path_cur = seg_path
        path_cur_out = path_out + '_'.join(seg_path.split('/')[5:7]) + '_seg.nii.gz'
        if not os.path.isfile(path_cur_out):
            shutil.copyfile(path_cur, path_cur_out)
            os.system('sct_image -i ' + path_cur_out + ' -setorient RPI -o ' + path_cur_out)

        path_cur_ctr = path_cur_out.split('.')[0] + '_centerline.nii.gz'
        if not os.path.isfile(path_cur_ctr):
            os.chdir(path_out)
            os.system('sct_process_segmentation -i ' + path_cur_out + ' -p centerline -ofolder ' + path_out)
            os.system('sct_image -i ' + path_cur_ctr + ' -type int16')
            path_input_header = path_cur_out.split('_seg')[0] + '.nii.gz'
            os.system('sct_image -i ' + path_input_header + ' -copy-header ' + path_cur_ctr)

        path_cur_gold = path_gold + '_'.join(seg_path.split('/')[5:7]) + '_centerline_gold.nii.gz'
        if not os.path.isfile(path_cur_gold) and os.path.isfile(path_cur_ctr):
            shutil.copyfile(path_cur_ctr, path_cur_gold)

        if os.path.isfile(path_cur_out):
            path_seg2convert.append(path_cur_out)
        if os.path.isfile(path_cur_ctr):
            path_seg2convert.append(path_cur_ctr)

    return path_seg2convert

def convert_nii2img(path_nii2convert, path_out):
    """
    
      Convert .nii images to .img format
    
          Inputs:
              - path_nii2convert [list of string]: list of path to images to convert
              - path_out [string]: path to folder where to save converted images
          Outputs:
              - fname_img [list of string]: list of converted images (.img format) paths
    
    """ 

    fname_img = []
    for img in path_nii2convert:
        path_cur = img
        path_cur_out = path_out + img.split('.')[0].split('/')[-1] + '.img'
        if not img.split('.')[0].split('/')[-1].endswith('_seg') and not img.split('.')[0].split('/')[-1].endswith('_seg_centerline'):
            fname_img.append(img.split('.')[0].split('/')[-1] + '.img')
        if not os.path.isfile(path_cur_out):
            os.system('sct_convert -i ' + path_cur + ' -o ' + path_cur_out)

    return fname_img

def prepare_dataset(path_local, constrast_lst, path_sct_testing_large):
    """
    
      MAIN FUNCTION OF STEP 0
      Create working subfolders
      + explore database and find images of interest
      + transform images (same orientation, value format...)
      + convert images to .img format
      + save image fname in 'dataset_lst_' + cc + '.pkl'
    
          Inputs:
              - path_local [string]: working folder
              - constrast_lst [list of string]: list of contrast we are interested in
              - path_sct_testing_large [path]: path to database
          Outputs:
              - 
    
    """

    for cc in constrast_lst:
    
        path_local_gold = path_local + 'gold_' + cc + '/'
        path_local_input_nii = path_local + 'input_nii_' + cc + '/'
        path_local_input_img = path_local + 'input_img_' + cc + '/'
        folder2create_lst = [path_local_input_nii, path_local_input_img, path_local_gold]
        create_folders_local(folder2create_lst)

        path_fname_img, path_fname_seg = find_img_testing(path_sct_testing_large, cc, path_local)

        path_img2convert = transform_nii_img(path_fname_img, path_local_input_nii)
        path_seg2convert = transform_nii_seg(path_fname_seg, path_local_input_nii, path_local_gold)
        path_imgseg2convert = path_img2convert + path_seg2convert
        fname_img_lst = convert_nii2img(path_imgseg2convert, path_local_input_img)

        pickle.dump(fname_img_lst, open(path_local + 'dataset_lst_' + cc + '.pkl', 'wb'))

# ******************************************************************************************



# ****************************      STEP 1 FUNCTIONS      *******************************

def panda_dataset(path_local, cc):

    if not os.path.isfile(path_local + 'test_valid_' + cc + '.pkl'):
      dct_tmp = {'subj_name': [], 'patho': [], 'resol': [], 'valid_test': []}

      with open(path_local + 'dataset_lst_' + cc + '.pkl') as outfile:    
          data_dct = pickle.load(outfile)
          outfile.close()

      with open(path_local + 'resol_dct_' + cc + '.pkl') as outfile:    
          resol_dct = pickle.load(outfile)
          outfile.close()

      with open(path_local + 'patho_dct_' + cc + '.pkl') as outfile:    
          patho_dct = pickle.load(outfile)
          outfile.close()

      data_lst = [l.split('_'+cc)[0] for l in data_dct]

      # path_25_train = path_local + 'input_train_' + cc + '_25/000/'
      # txt_lst = [f for f in os.listdir(path_25_train) if f.endswith('.txt') and not '_ctr' in f]
      # lambda_rdn = 0.23
      # random.shuffle(txt_lst, lambda: lambda_rdn)
      if cc=='t2':
        lambda_rdn = 0.23
      elif cc=='t2s':
        lambda_rdn = 0.88
      elif cc=='t1':
        lambda_rdn = 0.48

      random.shuffle(data_lst, lambda: lambda_rdn)

      testing_lst = data_lst[:int(len(data_lst)*0.5)]

      for i_d,data_cur in enumerate(data_lst):
        dct_tmp['subj_name'].append(data_cur)

        if data_cur in resol_dct['iso']:
          dct_tmp['resol'].append('iso')
        else:
          dct_tmp['resol'].append('not')

        if data_cur in patho_dct[u'HC']:
          dct_tmp['patho'].append('hc')
        else:
          dct_tmp['patho'].append('patient')

        if data_cur in testing_lst:
          dct_tmp['valid_test'].append('test')
        else:
          dct_tmp['valid_test'].append('valid')

      data_pd = pd.DataFrame.from_dict(dct_tmp)
      print '# of patient in: '
      print '... testing:' + str(len(data_pd[(data_pd.patho == 'patient') & (data_pd.valid_test == 'test')]))
      print '... validation:' + str(len(data_pd[(data_pd.patho == 'patient') & (data_pd.valid_test == 'valid')]))
      print '# of no-iso in: '
      print '... testing:' + str(len(data_pd[(data_pd.resol == 'not') & (data_pd.valid_test == 'test')]))
      print '... validation:' + str(len(data_pd[(data_pd.resol == 'not') & (data_pd.valid_test == 'valid')]))

      print data_pd
      data_pd.to_pickle(path_local + 'test_valid_' + cc + '.pkl')

def prepare_train(path_local, path_outdoor, cc, nb_img):

    path_outdoor_cur = path_outdoor + 'input_img_' + cc + '/'

    path_local_res_img = path_local + 'output_img_' + cc + '_'+ str(nb_img) + '/'
    path_local_res_nii = path_local + 'output_nii_' + cc + '_'+ str(nb_img) + '/'
    path_local_res_pkl = path_local + 'output_pkl_' + cc + '_'+ str(nb_img) + '/'
    path_local_train = path_local + 'input_train_' + cc + '_'+ str(nb_img) + '/'
    folder2create_lst = [path_local_train, path_local_res_img, path_local_res_nii, path_local_res_pkl]

    with open(path_local + 'test_valid_' + cc + '.pkl') as outfile:    
        data_pd = pickle.load(outfile)
        outfile.close()

    valid_lst = data_pd[data_pd.valid_test == 'valid']['subj_name'].values.tolist()
    test_lst = data_pd[data_pd.valid_test == 'test']['subj_name'].values.tolist()

    with open(path_local + 'dataset_lst_' + cc + '.pkl') as outfile:    
        data_dct = pickle.load(outfile)
        outfile.close()

    valid_data_lst, test_data_lst = [], []
    for dd in data_dct:
      ok_bool = 0
      for vv in valid_lst:
        if vv in dd and not ok_bool:
          valid_data_lst.append(dd)
          ok_bool = 1
      for tt in test_lst:
        if tt in dd and not ok_bool:
          test_data_lst.append(dd)
          ok_bool = 1

    print '\nExperiment: '
    print '... contrast: ' + cc
    print '... nb image used for training: ' + str(nb_img) + '\n'
    print '... nb image used for validation: ' + str(len(valid_lst)-nb_img) + '\n'
    print '... nb image used for testing: ' + str(len(test_lst)) + '\n'

    nb_img_valid = len(valid_lst)
    nb_sub_train = int(float(nb_img_valid)/(50))+1
    path_folder_sub_train = []
    for i in range(nb_sub_train):
        path2create = path_local_train + str(i).zfill(3) + '/'
        path_folder_sub_train.append(path2create)
        folder2create_lst.append(path2create)

    create_folders_local(folder2create_lst)

    train_lst = []
    while len(train_lst)<nb_img_valid:
      random.shuffle(valid_data_lst)
      for j in range(0, len(valid_data_lst), nb_img):
          s = valid_data_lst[j:j+nb_img]
          s = [ss.split('.')[0] for ss in s]
          if len(train_lst)<nb_img_valid:
            if len(s)==nb_img:
              train_lst.append(s)
          else:
            break     

    if os.listdir(path2create) == []: 
        for i, tt in enumerate(train_lst):
            stg, stg_seg = '', ''
            for tt_tt in tt:
                stg += path_outdoor_cur + tt_tt + '\n'
                stg_seg += path_outdoor_cur + tt_tt + '_seg' + '\n'
            path2save = path_folder_sub_train[int(float(i)/50)]
            with open(path2save + str(i).zfill(3) + '.txt', 'w') as text_file:
                text_file.write(stg)
                text_file.close()
            with open(path2save + str(i).zfill(3) + '_ctr.txt', 'w') as text_file:
                text_file.write(stg_seg)
                text_file.close()

    return path_local_train, valid_data_lst

def send_data2ferguson(path_local, path_ferguson, cc, nb_img):
    """
    
      MAIN FUNCTION OF STEP 1
      Prepare training strategy and save it in 'ferguson_config.pkl'
      + send data to ferguson
      + send training files to ferguson
      + send training strategy to ferguson
    
          Inputs:
              - path_local [string]: working folder
              - path_ferguson [string]: ferguson working folder
              - cc [string]: contrast of interest
              - nb_img [int]: nb of images for training
          Outputs:
              - 
    
    """

    path_local_train_cur, valid_data_lst = prepare_train(path_local, path_ferguson, cc, nb_img)

    pickle_ferguson = {
                        'contrast': cc,
                        'nb_image_train': nb_img,
                        'valid_subj': valid_data_lst,
                        'path_ferguson': '/home/neuropoly/code/spine-ms-t2/'
                        }
    path_pickle_ferguson = path_local + 'ferguson_config.pkl'
    output_file = open(path_pickle_ferguson, 'wb')
    pickle.dump(pickle_ferguson, output_file)
    output_file.close()

    # os.system('scp -r ' + path_local + 'input_img_' + contrast_of_interest + '/' + ' ferguson:/home/neuropoly/code/spine-ms-t2/')
    # os.system('scp -r ' + path_local_train_cur + ' ferguson:' + path_ferguson)
    # os.system('scp ' + path_pickle_ferguson + ' ferguson:' + path_ferguson)


    os.system('scp -r ' + path_local_train_cur + ' ferguson:/home/neuropoly/code/spine-ms-t2/')
    os.system('scp ' + path_pickle_ferguson + ' ferguson:/home/neuropoly/code/spine-ms-t2/')

# ******************************************************************************************



# ****************************      STEP 2 FUNCTIONS      *******************************

def pull_img_convert_nii_remove_img(path_local, path_ferguson, cc, nb_img):

    path_ferguson_res = path_ferguson + 'output_img_' + cc + '_'+ str(nb_img) + '/'
    path_local_res_img = path_local + 'output_img_' + cc + '_'+ str(nb_img) + '/'
    path_local_res_nii = path_local + 'output_nii_' + cc + '_'+ str(nb_img) + '/'
    path_local_res_time = path_local + 'output_time_' + cc + '_'+ str(nb_img) + '/'
    create_folders_local([path_local_res_img, path_local_res_nii, path_local_res_time])

    # Pull .img results from ferguson
    os.system('scp -r ferguson:' + path_ferguson_res + ' ' + '/'.join(path_local_res_img.split('/')[:-2]) + '/')

    # Convert .img to .nii
    # Remove .img files
    for f in os.listdir(path_local_res_img):
        if not f.startswith('.'):
            path_res_cur = path_local_res_nii + f + '/'
            path_res_cur_time = path_local_res_time + f + '/'
            create_folders_local([path_res_cur, path_res_cur_time])

            training_subj = f.split('__')

            if os.path.isdir(path_local_res_img+f):
                for ff in os.listdir(path_local_res_img+f):
                    if ff.endswith('_ctr.hdr'):

                        path_cur = path_local_res_img + f + '/' + ff
                        path_cur_out = path_res_cur + ff.split('_ctr')[0] + '_centerline_pred.nii.gz'
                        img = nib.load(path_cur)
                        nib.save(img, path_cur_out)

                    elif ff.endswith('.txt'):
                        shutil.copyfile(path_local_res_img + f + '/' + ff, path_res_cur_time + ff)
                os.system('rm -r ' + path_local_res_img + f)

# ******************************************************************************************



# ****************************      STEP 3 FUNCTIONS      *******************************

def _compute_stats(img_pred, img_true, img_seg_true):
    """
        -> mse = Mean Squared Error on distance between predicted and true centerlines
        -> maxmove = Distance max entre un point de la centerline predite et de la centerline gold standard
        -> zcoverage = Pourcentage des slices de moelle ou la centerline predite est dans la sc_seg_manual
    """

    stats_dct = {
                    'mse': None,
                    'maxmove': None,
                    'zcoverage': None
                }


    count_slice, slice_coverage = 0, 0
    mse_dist = []
    for z in range(img_true.dim[2]):

        if np.sum(img_true.data[:,:,z]):
            x_true, y_true = [np.where(img_true.data[:,:,z] > 0)[i][0] 
                                for i in range(len(np.where(img_true.data[:,:,z] > 0)))]
            x_pred, y_pred = [np.where(img_pred.data[:,:,z] > 0)[i][0]
                                for i in range(len(np.where(img_pred.data[:,:,z] > 0)))]
           
            xx_seg, yy_seg = np.where(img_seg_true.data[:,:,z]==1.0)
            xx_yy = [[x,y] for x, y in zip(xx_seg,yy_seg)]
            if [x_pred, y_pred] in xx_yy:
                slice_coverage += 1

            x_true, y_true = img_true.transfo_pix2phys([[x_true, y_true, z]])[0][0], img_true.transfo_pix2phys([[x_true, y_true, z]])[0][1]
            x_pred, y_pred = img_pred.transfo_pix2phys([[x_pred, y_pred, z]])[0][0], img_pred.transfo_pix2phys([[x_pred, y_pred, z]])[0][1]

            dist = ((x_true-x_pred))**2 + ((y_true-y_pred))**2
            mse_dist.append(dist)

            count_slice += 1

    if len(mse_dist):
        stats_dct['mse'] = sqrt(sum(mse_dist)/float(count_slice))
        stats_dct['maxmove'] = sqrt(max(mse_dist))
        stats_dct['zcoverage'] = float(slice_coverage*100.0)/count_slice

    return stats_dct

def _compute_stats_file(fname_ctr_pred, fname_ctr_true, fname_seg_true, folder_out, fname_out):

    img_pred = Image(fname_ctr_pred)
    img_true = Image(fname_ctr_true)
    img_seg_true = Image(fname_seg_true)

    stats_file_dct = _compute_stats(img_pred, img_true, img_seg_true)

    create_folders_local([folder_out])

    pickle.dump(stats_file_dct, open(fname_out, "wb"))


def compute_dataset_stats(path_local, cc, nb_img):
    """
        MAIN FUNCTION OF STEP 3
        Compute validation metrics for each subjects
        + Save avg results in a pkl file for each subject
        + Save results in a pkl for each tuple (training subj, testing subj)

        Inputs:
              - path_local [string]: working folder
              - cc [string]: contrast of interest
              - nb_img [int]: nb of images for training
        Outputs:
              - 

    """
    path_local_nii = path_local + 'output_nii_' + cc + '_'+ str(nb_img) + '/'
    path_local_res_pkl = path_local + 'output_pkl_' + cc +'/'
    create_folders_local([path_local_res_pkl])
    path_local_res_pkl = path_local_res_pkl + str(nb_img) + '/'
    create_folders_local([path_local_res_pkl])
    path_local_gold = path_local + 'gold_' + cc + '/'
    path_local_seg = path_local + 'input_nii_' + cc + '/'

    for f in os.listdir(path_local_nii):
        if not f.startswith('.'):
            path_res_cur = path_local_nii + f + '/'
            print path_res_cur
            folder_subpkl_out = path_local_res_pkl + f + '/'

            for ff in os.listdir(path_res_cur):
                if ff.endswith('_centerline_pred.nii.gz'):
                    subj_name_cur = ff.split('_centerline_pred.nii.gz')[0]
                    fname_subpkl_out = folder_subpkl_out + 'res_' + subj_name_cur + '.pkl'

                    if not os.path.isfile(fname_subpkl_out):
                        path_cur_pred = path_res_cur + ff
                        path_cur_gold = path_local_gold + subj_name_cur + '_centerline_gold.nii.gz'
                        path_cur_gold_seg = path_local_seg + subj_name_cur + '_seg.nii.gz'

                        _compute_stats_file(path_cur_pred, path_cur_gold, path_cur_gold_seg, folder_subpkl_out, fname_subpkl_out)


# ******************************************************************************************


# ****************************      STEP 4 FUNCTIONS      *******************************

def find_id_extr_df(df, mm):

  if 'zcoverage' in mm:
    return [df[mm].max(), df[df[mm] == df[mm].max()]['id'].values.tolist()[0], df[mm].min(), df[df[mm] == df[mm].min()]['id'].values.tolist()[0]]
  else:
    return [df[mm].min(), df[df[mm] == df[mm].min()]['id'].values.tolist()[0], df[mm].max(), df[df[mm] == df[mm].max()]['id'].values.tolist()[0]]

def panda_trainer(path_local, cc):

    path_folder_pkl = path_local + 'output_pkl_' + cc + '/'

    for fold in os.listdir(path_folder_pkl):
      path_nb_cur = path_folder_pkl + fold + '/'
      
      if os.path.isdir(path_nb_cur) and fold != '0' and fold != '666':
        fname_out_cur = path_folder_pkl + fold + '.pkl'
        if not os.path.isfile(fname_out_cur):
          metric_fold_dct = {'id': [], 'maxmove_moy': [], 'mse_moy': [], 'zcoverage_moy': [],
                              'maxmove_med': [], 'mse_med': [], 'zcoverage_med': []}
          
          for tr_subj in os.listdir(path_nb_cur):
            
            path_cur = path_nb_cur + tr_subj + '/'

            if os.path.isdir(path_cur):
              metric_fold_dct['id'].append(tr_subj)

              metric_cur_dct = {'maxmove': [], 'mse': [], 'zcoverage': []}
              for file in os.listdir(path_cur):
                if file.endswith('.pkl'):
                  with open(path_cur+file) as outfile:    
                    metrics = pickle.load(outfile)
                    outfile.close()
                  
                  for mm in metrics:
                    if mm in metric_cur_dct:
                      metric_cur_dct[mm].append(metrics[mm])

              metric_fold_dct['maxmove_med'].append(np.median(metric_cur_dct['maxmove']))
              metric_fold_dct['mse_med'].append(np.median(metric_cur_dct['mse']))
              metric_fold_dct['zcoverage_med'].append(np.median(metric_cur_dct['zcoverage']))

              metric_fold_dct['maxmove_moy'].append(np.mean(metric_cur_dct['maxmove']))
              metric_fold_dct['mse_moy'].append(np.mean(metric_cur_dct['mse']))
              metric_fold_dct['zcoverage_moy'].append(np.mean(metric_cur_dct['zcoverage']))

          metric_fold_pd = pd.DataFrame.from_dict(metric_fold_dct)
          metric_fold_pd.to_pickle(fname_out_cur)


          print '\nBest Trainer:'
          for mm in metric_fold_dct:
            if mm != 'id':
              find_id_extr_df(metric_fold_pd, mm)
              print '... ' + mm + ' : ' + find_id_extr_df(metric_fold_pd, mm)[1] + ' ' + str(find_id_extr_df(metric_fold_pd, mm)[0])
        
        else:
          with open(fname_out_cur) as outfile:    
            metric_fold_pd = pickle.load(outfile)
            outfile.close()
        print fold
        print metric_fold_pd

def test_trainers_best_worst(path_local, cc, mm, pp_ferg):

  path_folder_pkl = path_local + 'output_pkl_' + cc + '/'
  dct_tmp = {}
  for nn in os.listdir(path_folder_pkl):
    file_cur = path_folder_pkl + str(nn) + '.pkl'

    if os.path.isfile(file_cur):

      if nn != '0' and nn != '666':

        with open(file_cur) as outfile:    
          data_pd = pickle.load(outfile)
          outfile.close()

        if len(data_pd[data_pd[mm+'_med']==find_id_extr_df(data_pd, mm+'_med')[0]]['id'].values.tolist())>1:
          mm_avg = mm + '_moy'
        else:
          mm_avg = mm + '_med'

        fold_best, fold_worst = find_id_extr_df(data_pd, mm_avg)[1], find_id_extr_df(data_pd, mm_avg)[3]

        dct_tmp[nn] = [fold_best, fold_worst]

  path_input_train = path_local + 'input_train_' + cc + '_0/'
  path_input_train_best_worst = path_input_train + '000/'

  create_folders_local([path_input_train, path_input_train_best_worst])
  
  for nn in dct_tmp:
    path_input = path_local + 'input_train_' + cc + '_' + str(nn) + '/'
    for fold in os.listdir(path_input):
      if os.path.isfile(path_input + fold + '/' + str(dct_tmp[nn][0]).zfill(3) + '.txt'):
        file_in = path_input + fold + '/' + str(dct_tmp[nn][0]).zfill(3) + '.txt'
        file_seg_in = path_input + fold + '/' + str(dct_tmp[nn][0]).zfill(3) + '_ctr.txt'

        file_out = path_input_train_best_worst + '0_' + str(nn).zfill(3) + '.txt'
        file_seg_out = path_input_train_best_worst + '0_' + str(nn).zfill(3) + '_ctr.txt'        

        shutil.copyfile(file_in, file_out)
        shutil.copyfile(file_seg_in, file_seg_out)

      if os.path.isfile(path_input + fold + '/' + str(dct_tmp[nn][1]).zfill(3) + '.txt'):
        file_in = path_input + fold + '/' + str(dct_tmp[nn][1]).zfill(3) + '.txt'
        file_seg_in = path_input + fold + '/' + str(dct_tmp[nn][1]).zfill(3) + '_ctr.txt'

        file_out = path_input_train_best_worst + '1_' + str(nn).zfill(3) + '.txt'
        file_seg_out = path_input_train_best_worst + '1_' + str(nn).zfill(3) + '_ctr.txt'        

        shutil.copyfile(file_in, file_out)
        shutil.copyfile(file_seg_in, file_seg_out)

  with open(path_local + 'test_valid_' + cc + '.pkl') as outfile:    
      data_pd = pickle.load(outfile)
      outfile.close()

  valid_lst = data_pd[data_pd.valid_test == 'valid']['subj_name'].values.tolist()
  test_lst = data_pd[data_pd.valid_test == 'test']['subj_name'].values.tolist()

  with open(path_local + 'dataset_lst_' + cc + '.pkl') as outfile:    
      data_dct = pickle.load(outfile)
      outfile.close()

  valid_data_lst, test_data_lst = [], []
  for dd in data_dct:
    ok_bool = 0
    for vv in valid_lst:
      if vv in dd and not ok_bool:
        valid_data_lst.append(dd)
        ok_bool = 1
    for tt in test_lst:
      if tt in dd and not ok_bool:
        test_data_lst.append(dd)
        ok_bool = 1

  pickle_ferguson = {
                      'contrast': cc,
                      'nb_image_train': 0,
                      'valid_subj': test_data_lst,
                      'path_ferguson': pp_ferg
                      }
  path_pickle_ferguson = path_local + 'ferguson_config.pkl'
  output_file = open(path_pickle_ferguson, 'wb')
  pickle.dump(pickle_ferguson, output_file)
  output_file.close()

  os.system('scp -r ' + path_input_train + ' ferguson:' + pp_ferg)
  os.system('scp ' + path_pickle_ferguson + ' ferguson:' + pp_ferg)

# ******************************************************************************************

# ****************************      STEP 7 FUNCTIONS      *******************************

def create_extr_pd(path_pkl, cc, mm, best_or_worst):

  path_out = '/'.join(path_pkl.split('/')[:-2]) + '/' + best_or_worst + '_' + path_pkl.split('/')[-2].split('_0')[1] + '_' + mm + '.pkl'

  if not os.path.isfile(path_out):
    with open('/'.join(path_pkl.split('/')[:-4]) + '/test_valid_' + cc + '.pkl') as outfile:    
      all_data_pd = pickle.load(outfile)
      outfile.close()

    valid_pd = all_data_pd[all_data_pd.valid_test == 'test']

    dct_tmp = {'subj_id': [], mm: [], 'Subject': [], 'resol': [], best_or_worst: []}
    for file in os.listdir(path_pkl):
      if '.pkl' in file:
        path_pkl_cur = path_pkl + file

        subj_cur = file.split('res_')[1].split('.pkl')[0].split('_'+cc)[0]
        dct_tmp['subj_id'].append(subj_cur)
        dct_tmp[best_or_worst].append(best_or_worst + ' trainer')
        dct_tmp['Subject'].append(valid_pd[valid_pd.subj_name == subj_cur]['patho'].values.tolist()[0])
        dct_tmp['resol'].append(valid_pd[valid_pd.subj_name == subj_cur]['resol'].values.tolist()[0])

        with open(path_pkl_cur) as outfile:    
          mm_cur = pickle.load(outfile)
          outfile.close()
        dct_tmp[mm].append(mm_cur[mm])

    extr_pd = pd.DataFrame.from_dict(dct_tmp)
    print extr_pd
    extr_pd.to_pickle(path_out)

  else:
    with open(path_out) as outfile:    
      extr_pd = pickle.load(outfile)
      outfile.close()

  print extr_pd

  return extr_pd



def plot_trainers_best_worst(path_local, cc, mm):

  if mm != 'zcoverage':
    if mm == 'maxmove':
      y_label_all_stg = 'Averaged maximum displacement [mm] across validation dataset'
      y_label_stg = 'Maximum displacement [mm] per validation subject'
    else:
      y_label_all_stg = 'Averaged Mean Squared Error [mm] across validation dataset'
      y_label_stg = 'Mean Squared Error [mm] per validation subject'      

    if cc == 't2':
      y_lim_min, y_lim_max = 0.01, 30
    elif cc == 't1':
      y_lim_min, y_lim_max = 0.01, 25
    else:
      y_lim_min, y_lim_max = 0.01, 30

  else:
    y_label_all_stg = 'Averaged z-coverage [%] across validation dataset'
    y_label_stg = 'z-coverage [%] per validation subject'
    if cc == 't2':
      y_lim_min, y_lim_max = 60, 101
      y_stg_loc = y_lim_min+20
    elif cc == 't1':
      y_lim_min, y_lim_max = 79, 101
    else:
      y_lim_min, y_lim_max = 60, 101
      y_stg_loc = y_lim_min+20

  path_folder_pkl = path_local + 'output_pkl_' + cc + '/'
  for file in os.listdir(path_folder_pkl):
    if file.endswith('.pkl') and not file=='0.pkl':
      path_folder_pkl_cur = path_folder_pkl + file
      nb_img_cur = int(file.split('.pkl')[0])

      with open(path_folder_pkl_cur) as outfile:    
        data_pd = pickle.load(outfile)
        outfile.close()

      if len(data_pd[data_pd[mm+'_med']==find_id_extr_df(data_pd, mm+'_med')[0]]['id'].values.tolist())>1:
        mm_avg = mm + '_moy'
      else:
        mm_avg = mm + '_med'

      path_best = path_local + 'output_pkl_' + cc + '/' + str(0) + '/0_' + str(nb_img_cur).zfill(3) + '/'
      path_worst = path_local + 'output_pkl_' + cc + '/' + str(0) + '/1_' + str(nb_img_cur).zfill(3) + '/'

      best_pd = create_extr_pd(path_best, cc, mm, 'best')
      worst_pd = create_extr_pd(path_worst, cc, mm, 'worst')
      avg_lst = data_pd[mm_avg].values.tolist()

      sns.set(style="whitegrid", palette="Set1", font_scale=1.3)
      fig, axes = plt.subplots(1, 3, sharey='col', figsize=(24, 8))
      cmpt = 1
      color_lst = ['lightblue', 'lightgreen', 'lightsalmon']
      x_label_lst = ['Averaged by trainer', 'Best Trainer', 'Worst Trainer']
      fig.subplots_adjust(left=0.05, bottom=0.05)

      a = plt.subplot(1, 3,1)
      sns.violinplot(data=avg_lst, inner="quartile", cut=0, scale="count", 
                              sharey=True, color=color_lst[0])
      sns.swarmplot(data=avg_lst, palette='deep', size=5)
      a.set_xlabel(x_label_lst[0], fontsize=13)
      a.set_ylabel(y_label_all_stg, fontsize=13)
      a.set_ylim([y_lim_min,y_lim_max])

      b = plt.subplot(1, 3, 2)
      sns.violinplot(x='best', y=mm, data=best_pd, inner="quartile", cut=0, scale="count", 
                              sharey=True, color=color_lst[1])
      sns.swarmplot(x='best', y=mm, data=best_pd, hue='Subject', size=5)
      b.set_ylim([y_lim_min,y_lim_max])
      b.set_xlabel(x_label_lst[1], fontsize=13)
      b.set_ylabel(y_label_stg, fontsize=13)

      c = plt.subplot(1, 3, 3)
      sns.violinplot(x='worst', y=mm, data=worst_pd, inner="quartile", cut=0, scale="count", 
                              sharey=True, color=color_lst[2])
      sns.swarmplot(x='worst', y=mm, data=worst_pd, hue='Subject', size=5)
      c.set_ylim([y_lim_min,y_lim_max])
      c.set_xlabel(x_label_lst[2], fontsize=13)
      c.set_ylabel(y_label_stg, fontsize=13)

      fig.tight_layout()
      # plt.show()
      path_save_fig = path_local+'plot_best_worst/'
      create_folders_local([path_save_fig])
      fig.savefig(path_save_fig+'plot_' + cc + '_' + str(nb_img_cur) + '_' + mm + '.png')
      plt.close()

      dct_tmp = {'group':['hc', 'patient', 'iso', 'noiso'], 'ttest p-avlue':[]}
      hc_best_pd = best_pd[best_pd.Subject=='hc'][mm]
      hc_worst_pd = worst_pd[worst_pd.Subject=='hc'][mm]

      patient_best_pd = best_pd[best_pd.Subject=='patient'][mm]
      patient_worst_pd = worst_pd[worst_pd.Subject=='patient'][mm]

      dct_tmp['ttest p-avlue'].append(ttest_rel(hc_best_pd, hc_worst_pd)[1])
      dct_tmp['ttest p-avlue'].append(ttest_rel(patient_best_pd, patient_worst_pd)[1])


      iso_best_pd = best_pd[best_pd.resol=='iso'][mm]
      iso_worst_pd = worst_pd[worst_pd.resol=='iso'][mm]

      noiso_best_pd = best_pd[best_pd.resol=='not'][mm]
      noiso_worst_pd = worst_pd[worst_pd.resol=='not'][mm]

      dct_tmp['ttest p-avlue'].append(ttest_rel(iso_best_pd, iso_worst_pd)[1])
      dct_tmp['ttest p-avlue'].append(ttest_rel(noiso_best_pd, noiso_worst_pd)[1])

      stats_pd = pd.DataFrame.from_dict(dct_tmp)
      # print stats_pd
      stats_pd.to_excel(path_save_fig+'ttest_' + cc + '_' + str(nb_img_cur) + '_' + mm + '.xls', 
                          sheet_name='sheet1')

def plot_comparison_nb_train(path_local, cc, mm):

  path_output_pkl = path_local + 'output_pkl_' + cc + '/0/'

  dct_tmp = {'Subject': [], 'resol': [], 'metric': [], 'nb_train': []}
  for file in os.listdir(path_output_pkl):
    path_cur = path_output_pkl + file
    if os.path.isfile(path_cur) and '.pkl' in file and 'best_' in file and mm in file:

      with open(path_cur) as outfile:    
        pd_cur = pickle.load(outfile)
        outfile.close()

      for pp in pd_cur['Subject'].values.tolist():
        dct_tmp['Subject'].append(pp)
      for rr in pd_cur['resol'].values.tolist():
        dct_tmp['resol'].append(rr)
      for m in pd_cur[mm].values.tolist():
        dct_tmp['metric'].append(m)
      for i in range(len(pd_cur[mm].values.tolist())):
        dct_tmp['nb_train'].append(file.split('_'+mm)[0].split('best_')[1])

  pd_2plot = pd.DataFrame.from_dict(dct_tmp)
  print pd_2plot

  nb_img_train_str_lst = ['01', '05', '10', '15', '20', '25']

  if mm != 'zcoverage':
      if cc == 't2':
        y_lim_min, y_lim_max = 0.01, 22
      elif cc == 't1':
        y_lim_min, y_lim_max = 0.0, 5
      else:
        y_lim_min, y_lim_max = 0.01, 8

      if mm == 'maxmove':
        y_label_stg = 'Maximum Displacement [mm]'
      else:
        y_label_stg = 'Mean Squared Error [mm]'

  else:
      if cc == 't2':
        y_lim_min, y_lim_max = 60, 101
        y_stg_loc = y_lim_min+20
      elif cc == 't1':
        y_lim_min, y_lim_max = 85, 101
      else:
        y_lim_min, y_lim_max = 65, 101
        y_stg_loc = y_lim_min+20

      y_label_stg = 'z-coverage [%]'

  sns.set(style="whitegrid", palette="Set1", font_scale=1.3)
  fig, axes = plt.subplots(1, 1, sharey='col', figsize=(8*6, 8))
  a = plt.subplot(1, 1, 1)
  sns.violinplot(x='nb_train', y='metric', data=pd_2plot, order=nb_img_train_str_lst, 
            inner="quartile", cut=0, 
            scale="count", sharey=True, palette=sns.color_palette("Greens",10)[:6])
  sns.swarmplot(x='nb_train', y='metric', data=pd_2plot, order=nb_img_train_str_lst, 
                  hue='Subject', size=5)
  a.set_ylabel(y_label_stg, fontsize=13)
  a.set_xlabel('Number of training images', fontsize=13)
  a.set_ylim([y_lim_min,y_lim_max])

  fig.tight_layout()
  plt.show()
  fig.savefig(path_local+'plot_nb_train_img_comparison/plot_comparison_' + cc + '_' + mm + '.png')
  plt.close()

  median_lst, nb_subj_lst, std_lst, extrm_lst = [], [], [], []
  pvalue_lst, pvalue_hc_lst, pvalue_patient_lst, pvalue_iso_lst, pvalue_no_iso_lst = [], [], [], [], []

  for i_f,f in enumerate(nb_img_train_str_lst):
    if f in pd_2plot.nb_train.values.tolist():
      values_cur = pd_2plot[pd_2plot.nb_train==f]['metric'].values.tolist()
      median_lst.append(np.median(values_cur))
      nb_subj_lst.append(len(values_cur))
      std_lst.append(np.std(values_cur))
      if mm == 'zcoverage':
        extrm_lst.append(min(values_cur))
      else:
        extrm_lst.append(max(values_cur))

      if f != nb_img_train_str_lst[-1]:
        values_cur_next = pd_2plot[pd_2plot.nb_train==nb_img_train_str_lst[i_f+1]]['metric'].values.tolist()
        pvalue_lst.append(ttest_rel(values_cur, values_cur_next)[1])

        values_cur_hc = pd_2plot[(pd_2plot.nb_train==f) & (pd_2plot.Subject=='hc')]['metric'].values.tolist()
        values_cur_hc_next = pd_2plot[(pd_2plot.nb_train==nb_img_train_str_lst[i_f+1]) & (pd_2plot.Subject=='hc')]['metric'].values.tolist()
      
        values_cur_patient = pd_2plot[(pd_2plot.nb_train==f) & (pd_2plot.Subject=='patient')]['metric'].values.tolist()
        values_cur_patient_next = pd_2plot[(pd_2plot.nb_train==nb_img_train_str_lst[i_f+1]) & (pd_2plot.Subject=='patient')]['metric'].values.tolist()
      
        values_cur_iso = pd_2plot[(pd_2plot.nb_train==f) & (pd_2plot.resol=='iso')]['metric'].values.tolist()
        values_cur_iso_next = pd_2plot[(pd_2plot.nb_train==nb_img_train_str_lst[i_f+1]) & (pd_2plot.resol=='iso')]['metric'].values.tolist()
      
        values_cur_not = pd_2plot[(pd_2plot.nb_train==f) & (pd_2plot.resol=='not')]['metric'].values.tolist()
        values_cur_not_next = pd_2plot[(pd_2plot.nb_train==nb_img_train_str_lst[i_f+1]) & (pd_2plot.resol=='not')]['metric'].values.tolist()
              
        pvalue_hc_lst.append(ttest_rel(values_cur_hc, values_cur_hc_next)[1])
        pvalue_patient_lst.append(ttest_rel(values_cur_patient, values_cur_patient_next)[1])
        pvalue_iso_lst.append(ttest_rel(values_cur_iso, values_cur_iso_next)[1])
        pvalue_no_iso_lst.append(ttest_rel(values_cur_not, values_cur_not_next)[1])

      else:
        for l in [pvalue_lst, pvalue_hc_lst, pvalue_patient_lst, pvalue_iso_lst, pvalue_no_iso_lst]:
          l.append(-1.0)
    else:
      for l in [median_lst, nb_subj_lst, std_lst, extrm_lst, pvalue_lst, pvalue_hc_lst, pvalue_patient_lst, pvalue_iso_lst, pvalue_no_iso_lst]:
        l.append(-1.0)

  stats_pd = pd.DataFrame({'nb_train': nb_img_train_str_lst, 
                            'nb_test': nb_subj_lst,
                            'Median': median_lst,
                            'Std': std_lst,
                            'Extremum': extrm_lst,
                            'p-value': pvalue_lst,
                            'p-value_HC': pvalue_hc_lst,
                            'p-value_patient': pvalue_patient_lst,
                            'p-value_iso': pvalue_iso_lst,
                            'p-value_no_iso': pvalue_no_iso_lst                               
                            })
  
  stats_pd.to_excel(path_local+'plot_nb_train_img_comparison/excel_' + cc + '_' + mm + '.xls', 
                sheet_name='sheet1')


# ******************************************************************************************

# ****************************      STEP 8 FUNCTIONS      *******************************

def panda_seg(path_local, cc, mm):

    fname_out_pd = path_local + 'train_test_' + cc + '.pkl'

    train_test_dct = {'patho': [], 'resol': [], 'subj_name': [], 'train_test': [], 'nb_train': []}
    for nb_img in [1, 5, 10, 15, 20, 25]:
      fname_pd_trainer = path_local + 'output_pkl_' + cc + '/' + str(nb_img) + '.pkl'
      with open(fname_pd_trainer) as outfile:    
          score_trainers = pickle.load(outfile)
          outfile.close()

      best_trainer_idx = find_id_extr_df(score_trainers, mm+'_moy')[1]

      best_trainer_idx_test = best_trainer_idx
      while best_trainer_idx_test.startswith('0'):
        if best_trainer_idx_test.startswith('00'):
          best_trainer_idx_test = best_trainer_idx_test.split('0')[-1]
        else:
          best_trainer_idx_test = best_trainer_idx_test.split('0')[1]
      print best_trainer_idx
      print best_trainer_idx_test
      path_input_train = path_local + 'input_train_' + cc + '_' + str(nb_img) + '/' + str(int(best_trainer_idx_test)/50).zfill(3) + '/' + best_trainer_idx + '.txt'
      
      train_subj_lst = []
      text = open(path_input_train, 'r').read()
      for tt in text.split('\n'):
          name = tt.split('/')[-1]
          if len(name):
              train_subj_lst.append(name.split('_'+cc)[0])

      fname_test_valid_pd = path_local + 'test_valid_' + cc + '.pkl'
      with open(fname_test_valid_pd) as outfile:    
          test_valid_pd = pickle.load(outfile)
          outfile.close()


      for p,r in zip(test_valid_pd.patho.values.tolist(), test_valid_pd.resol.values.tolist()):
        train_test_dct['patho'].append(p)
        train_test_dct['resol'].append(r)

      subj_name_lst = test_valid_pd.subj_name.values.tolist()
      for f in subj_name_lst:
        train_test_dct['subj_name'].append(f)
        if f in train_subj_lst:
          train_test_dct['train_test'].append('train')
        else:
          train_test_dct['train_test'].append('test')
        train_test_dct['nb_train'].append(nb_img)


    train_test_pd = pd.DataFrame.from_dict(train_test_dct)
    train_test_pd.to_pickle(fname_out_pd)
    
    for nb_img in [1, 5, 10, 15, 20, 25]:
      print '\n# of training images: ' + str(nb_img)
      print '# of patient in: '
      print '... training:' + str(len(train_test_pd[(train_test_pd.patho == 'patient') & (train_test_pd.train_test == 'train') & (train_test_pd.nb_train == nb_img)]))
      print '... testing:' + str(len(train_test_pd[(train_test_pd.patho == 'patient') & (train_test_pd.train_test == 'test') & (train_test_pd.nb_train == nb_img)]))
      print '# of no-iso in: '
      print '... training:' + str(len(train_test_pd[(train_test_pd.resol == 'not') & (train_test_pd.train_test == 'train') & (train_test_pd.nb_train == nb_img)]))
      print '... testing:' + str(len(train_test_pd[(train_test_pd.resol == 'not') & (train_test_pd.train_test == 'test') & (train_test_pd.nb_train == nb_img)]))


def prepare_last_test(path_local, cc, pp_ferg):

  with open(path_local + 'dataset_lst_' + cc + '.pkl') as outfile:    
    testing_lst = pickle.load(outfile)
    outfile.close()

  path_input_train_old = path_local + 'input_train_' + cc + '_0/'
  path_input_train_best_worst_old = path_input_train_old + '000/'

  path_input_train = path_local_sdika + 'input_train_' + contrast_of_interest + '_666/'
  path_input_train_best_worst = path_input_train + '000/'
  create_folders_local([path_input_train, path_input_train_best_worst])
  for file in os.listdir(path_input_train_best_worst_old):
    if '0_0' in file:
      shutil.copyfile(path_input_train_best_worst_old+file, path_input_train_best_worst+file)

  pickle_ferguson = {
                      'contrast': cc,
                      'nb_image_train': 666,
                      'valid_subj': testing_lst,
                      'path_ferguson': pp_ferg
                      }
  path_pickle_ferguson = path_local_sdika + 'ferguson_config.pkl'
  output_file = open(path_pickle_ferguson, 'wb')
  pickle.dump(pickle_ferguson, output_file)
  output_file.close()

  os.system('scp -r ' + path_input_train + ' ferguson:' + pp_ferg)
  os.system('scp ' + path_pickle_ferguson + ' ferguson:' + pp_ferg)

def plot_comparison_classifier(path_local, cc, nb_img):

    path_pkl_sdika = path_local + 'output_pkl_' + cc + '/666/0_' + str(nb_img).zfill(3) + '/res_'
    # path_pkl_cnn = path_local + 'cnn_pkl_' + cc + '_' + str(llambda) + '/res_' + cc + '_' + str(llambda) + '_'
    path_pkl_propseg = path_local + 'propseg_pkl_' + cc + '/res_' + cc + '_'
    # classifier_name_lst = ['PropSeg', 'CNN+zRegularization', 'OptiC']
    classifier_name_lst = ['Hough', 'OptiC']

    path_output = path_local + 'plot_comparison/'
    create_folders_local([path_output])
    # fname_out = path_output + 'plot_comparison_' + cc + '_' + str(nb_img) + '_' + str(llambda)
    fname_out = path_output + 'plot_comparison_' + cc + '_' + str(nb_img)
    fname_out_pkl = fname_out + '.pkl'
 
    with open(path_local + 'dataset_lst_' + cc + '.pkl') as outfile:    
      subj_lst = pickle.load(outfile)
      outfile.close()

    with open(path_local + 'train_test_' + cc + '.pkl') as outfile:    
      data_pd = pickle.load(outfile)
      outfile.close()

    subj_lst = [t.split('.img')[0] for t in subj_lst]

    res_dct = {'id': [], 'mse': [], 'maxmove': [], 'zcoverage':[], 'Subject':[], 'resol': [], 'classifier':[]}
    # fail_dct = {'PropSeg': 0, 'CNN+zRegularization': 0, 'SVM+HOG+zRegularization':0}
    fail_dct = {'Hough': 0, 'OptiC':0}
    for classifier_path, classifier_name in zip([path_pkl_propseg, path_pkl_sdika], classifier_name_lst):
    # for classifier_path, classifier_name in zip([path_pkl_propseg, path_pkl_cnn, path_pkl_sdika], classifier_name_lst):
      for subj in subj_lst:
          fname_pkl_cur = classifier_path + subj + '.pkl'
          if os.path.isfile(fname_pkl_cur):
            with open(fname_pkl_cur) as outfile:    
                mm_cur = pickle.load(outfile)
                outfile.close()
            if mm_cur['zcoverage'] is not None and mm_cur['zcoverage'] != 0.0:
              for mm_name in ['mse', 'maxmove', 'zcoverage']:
                res_dct[mm_name].append(mm_cur[mm_name])
              res_dct['id'].append(subj.split('_'+cc)[0])
              res_dct['classifier'].append(classifier_name)
              res_dct['resol'].append(data_pd[(data_pd.subj_name == subj.split('_'+cc)[0])&(data_pd.nb_train == nb_img)]['resol'].values.tolist()[0])
              res_dct['Subject'].append(data_pd[(data_pd.subj_name == subj.split('_'+cc)[0])&(data_pd.nb_train == nb_img)]['patho'].values.tolist()[0])
            else:
              fail_dct[classifier_name] += 1
    pd_2plot = pd.DataFrame.from_dict(res_dct)
    print pd_2plot
    pickle.dump(pd_2plot, open(fname_out_pkl, "wb"))

    for mm_name in ['mse', 'maxmove', 'zcoverage']:

      if mm_name != 'zcoverage':
        if mm_name == 'maxmove':
          y_label_stg = 'Maximum displacement [mm] per testing subject'
        else:
          y_label_stg = 'Mean square error [mm] per testing subject'

        if cc == 't1':
          y_lim_min, y_lim_max = 0.01, 30
          y_stg_loc = y_lim_max-20
        elif cc == 't2s':
          if mm_name == 'maxmove':
            y_lim_min, y_lim_max = 0.01, 45
          else:
            y_lim_min, y_lim_max = 0.01, 25
          y_stg_loc = y_lim_max-10
        elif cc == 't2':
          if mm_name == 'maxmove':
            y_lim_min, y_lim_max = 0.01, 80
          else:
            y_lim_min, y_lim_max = 0.01, 55
          y_stg_loc = y_lim_max-20

      else:
        if cc == 't2':
          y_lim_min, y_lim_max = 0, 101
          y_stg_loc = y_lim_min+20
        elif cc == 't1':
          y_lim_min, y_lim_max = 55, 101
          if nb_img == 5:
            y_lim_min, y_lim_max = 80, 101
          y_stg_loc = y_lim_min+5
        else:
          y_lim_min, y_lim_max = 55, 101
          y_stg_loc = y_lim_min+5

        y_label_stg = 'Accuracy [%] per validation subject'

      sns.set(style="whitegrid", palette="Set1", font_scale=1.3)
      palette_swarm = dict(patient = 'crimson', hc = 'darkblue')
      fig, axes = plt.subplots(1, 1, sharey='col', figsize=(24, 8))
      fig.subplots_adjust(left=0.05, bottom=0.05)
      # color_lst = sns.color_palette("Set2")
      # random.shuffle(color_lst, lambda:0.01)
      color_lst = [(0.40000000596046448, 0.7607843279838562, 0.64705884456634521), (0.55432528607985565, 0.62711267120697922, 0.79595541393055635)]
      a = plt.subplot(1, 1, 1)
      sns.violinplot(x='classifier', y=mm_name, data=pd_2plot, order=classifier_name_lst,
                              inner="quartile", cut=0, scale="width",
                              sharey=True,  palette=color_lst)
      sns.swarmplot(x='classifier', y=mm_name, data=pd_2plot, order=classifier_name_lst, 
                              hue='Subject', size=5, palette=palette_swarm)

      a.set_ylabel(y_label_stg, fontsize=13)
      a.set_xlabel('Method', fontsize=13)
      a.set_ylim([y_lim_min,y_lim_max])

      nb_test_subj = len(subj_lst) - nb_img
      stg_propseg = '# of detected cord: ' + str(nb_test_subj-fail_dct['Hough']) + '/' + str(nb_test_subj)
      # stg_cnn = '# of detected cord: ' + str(len(testing_lst)-fail_dct['CNN+zRegularization']) + '/' + str(len(testing_lst))
      stg_svm = '# of detected cord: ' + str(nb_test_subj-fail_dct['OptiC']) + '/' + str(nb_test_subj)

      values_propseg = pd_2plot[pd_2plot.classifier=='Hough'][mm_name].values.tolist()
      # values_cnn = pd_2plot[pd_2plot.classifier=='CNN+zRegularization'][mm_name].values.tolist()
      values_svm = pd_2plot[pd_2plot.classifier=='OptiC'][mm_name].values.tolist()

      stg_propseg += '\nMean: ' + str(round(np.mean(values_propseg),2))
      # stg_cnn += '\nMean: ' + str(round(np.mean(values_cnn),2))
      stg_svm += '\nMean: ' + str(round(np.mean(values_svm),2))

      stg_propseg += '\nStd: ' + str(round(np.std(values_propseg),2))
      # stg_cnn += '\nStd: ' + str(round(np.std(values_cnn),2))
      stg_svm += '\nStd: ' + str(round(np.std(values_svm),2))

      if mm_name != 'zcoverage':
        stg_propseg += '\nMax: ' + str(round(np.max(values_propseg),2))
        # stg_cnn += '\nMax: ' + str(round(np.max(values_cnn),2))
        stg_svm += '\nMax: ' + str(round(np.max(values_svm),2))
      else:
        stg_propseg += '\nMin: ' + str(round(np.min(values_propseg),2))
        # stg_cnn += '\nMin: ' + str(round(np.min(values_cnn),2))
        stg_svm += '\nMin: ' + str(round(np.min(values_svm),2))

      a.text(0.03, y_stg_loc, stg_propseg, fontsize=13)
      # a.text(1.02, y_stg_loc, stg_cnn, fontsize=13)
      a.text(1.03, y_stg_loc, stg_svm, fontsize=13)

      a.set_ylim([y_lim_min,y_lim_max])
      
      # plt.show()
      fig.tight_layout()
      fname_out_png = fname_out + '_' + mm_name + '.png'
      fig.savefig(fname_out_png)
      plt.close()

    nb_test_subj = len(subj_lst) - nb_img
    labels_pie = ['SC detected', 'SC not detected']
    percent_fail_propseg = (fail_dct['Hough'])*100.0/nb_test_subj
    values_propseg = [100.0-percent_fail_propseg, percent_fail_propseg]
    percent_fail_svm = (fail_dct['OptiC'])*100.0/nb_test_subj
    values_svm = [100.0-percent_fail_svm, percent_fail_svm]

    fig, axes = plt.subplots(1, 1, figsize=(8, 8))
    colors = ['forestgreen', 'firebrick']
    patches, texts = plt.pie(values_propseg, colors=colors, shadow=True, startangle=90)
    plt.legend(patches, labels_pie, loc="best")
    fig.savefig(path_output + 'detected_' + cc + '_propseg.png')
    plt.close()

    fig, axes = plt.subplots(1, 1, figsize=(8, 8))
    colors = ['forestgreen', 'firebrick']
    patches, texts = plt.pie(values_svm, colors=colors, shadow=True, startangle=90)
    plt.legend(patches, labels_pie, loc="best")
    fig.savefig(path_output + 'detected_' + cc + '_' + str(nb_img) + '.png')
    plt.close()

# ******************************************************************************************

# ****************************      STEP 8 FUNCTIONS      *******************************

def computation_time(path_local, cc):

  path_time = path_local + 'output_time_' + cc + '_666/'
  path_dim = path_time+'dim.pkl'

  if not os.path.isfile(path_dim):
    with open(path_local + 'dataset_lst_' + cc + '.pkl') as outfile:    
      subj_lst = pickle.load(outfile)
      outfile.close()

    dct_dim = {'id': [], 'nz': []}
    for ii in subj_lst:
      img = Image(path_local + 'input_nii_' + cc + '/' + ii.split('.img')[0] + '.nii.gz')
      dct_dim['id'].append(ii.split('.img')[0])
      dct_dim['nz'].append(img.dim[2])
      del img

    dim_pd = pd.DataFrame.from_dict(dct_dim)
    dim_pd.to_pickle(path_time+'dim.pkl')
  else:
    with open(path_dim) as outfile:    
      dim_pd = pickle.load(outfile)
      outfile.close()

    dct_dim = dim_pd.to_dict(orient='list')

  dct_tmp = {'nb_train': [], 'mean': [], 'std': []}
  for fold_nb in os.listdir(path_time):
    if os.path.isdir(path_time+fold_nb):
      dct_tmp['nb_train'].append(fold_nb.split('0_0')[1])
      mean_per_slice_lst = []
      for subj, nz in zip(dct_dim['id'], dct_dim['nz']):
        time_file = path_time+fold_nb+'/'+subj+'.txt'
        if os.path.isfile(time_file):
          tps_img = float(open(time_file, 'r').read())
          mean_per_slice_lst.append(tps_img/nz)
      dct_tmp['mean'].append(np.mean(mean_per_slice_lst))
      dct_tmp['std'].append(np.std(mean_per_slice_lst))

  time_pd = pd.DataFrame.from_dict(dct_tmp)
  print time_pd
  time_pd.to_pickle(path_time+'time.pkl')




# ******************************************************************************************

# ****************************      STEP 8 FUNCTIONS      *******************************

def plot_score_nb_train(path_local, mm):

  nb_train_lst = [1, 5, 10, 15, 20, 25]
  cc_lst = ['t2', 't1', 't2s']

  res_lst_lst = []
  for cc in cc_lst:
    mean_lst, std_lst = [], []
    for nb_img in nb_train_lst:
      path_pkl_test = path_local + 'output_pkl_' + cc + '/0/best_' + str(nb_img).zfill(2) + '_' + mm + '.pkl'

      with open(path_pkl_test) as outfile:    
          score = pickle.load(outfile)
          outfile.close()

      mean_lst.append(np.mean(score[mm].values.tolist()))
      std_lst.append(np.std(score[mm].values.tolist()))

    res_lst_lst.append([mean_lst, std_lst])

  fig, axes = plt.subplots(1, 1, figsize=(8, 8))
  color_lst = ['orange', 'blue', 'green']
  label_lst = ['T2w', 'T1w', 'T2*w']
  for i in range(len(cc_lst)):

    scores_mean = res_lst_lst[i][0]
    scores_std = res_lst_lst[i][1]

    score_minus = [m-s for m,s in zip(scores_mean,scores_std)]
    score_plus = [m+s for m,s in zip(scores_mean,scores_std)]

    # plt.fill_between(nb_train_lst, score_minus, score_plus, alpha=0.25, color=color_lst[i])
    plt.plot(nb_train_lst, scores_mean, 'o-', color=color_lst[i], label=label_lst[i])

  plt.legend(loc="best", fontsize=13)

  plt.xlabel('# training images', fontsize=13)
  if mm == 'zcoverage':
    plt.ylabel('Averaged z-coverage [%] across testing data', fontsize=13)
    plt.ylim([90,100])
  elif mm == 'mse':
    plt.ylabel('Averaged MSE [mm] across testing data', fontsize=13)
    plt.ylim([0,3])
  
  plt.xlim([nb_train_lst[0]-1,nb_train_lst[-1]])

    # plt.grid()
  plt.xticks(fontsize=13)
  plt.yticks(fontsize=13)
  # plt.show()
  plt.close()
  fig.savefig(path_local+'plot_nb_train_img_comparison/'+mm+'.png')

# ****************************      OLD FUNCTIONS      *******************************

def partition_resol(path_local, cc):

    fname_pkl_out = path_local + 'resol_dct_' + cc + '.pkl'
    if not os.path.isfile(fname_pkl_out):
        path_dataset_pkl = path_local + 'dataset_lst_' + cc + '.pkl'
        dataset = pickle.load(open(path_dataset_pkl, 'r'))
        dataset_subj_lst = [f.split('.img')[0].split('_'+cc)[0] for f in dataset]
        dataset_path_lst = [path_local + 'input_nii_' + cc + '/' + f.split('.img')[0]+'.nii.gz' for f in dataset]

        resol_dct = {'sag': [], 'ax': [], 'iso': []}
        for img_path, img_subj in zip(dataset_path_lst, dataset_subj_lst):
            img = Image(img_path)

            resol_lst = [round(dd) for dd in img.dim[4:7]]
            if resol_lst.count(resol_lst[0]) == len(resol_lst):
                resol_dct['iso'].append(img_subj)
            elif resol_lst[2]<resol_lst[0] or resol_lst[2]<resol_lst[1]:
                resol_dct['sag'].append(img_subj)
            else:
                resol_dct['ax'].append(img_subj)

            del img

        pickle.dump(resol_dct, open(fname_pkl_out, "wb"))
    else:
        with open(fname_pkl_out) as outfile:    
            resol_dct = pickle.load(outfile)
            outfile.close()

    return resol_dct


def compute_best_trainer(path_local, cc, nb_img, mm_lst, img_dct):

    path_pkl = path_local + 'output_pkl_' + cc + '_' + str(nb_img) + '/'

    campeones_dct = {}

    for interest in img_dct:
        img_lst = img_dct[interest]
        test_subj_dct = {}

        for folder in os.listdir(path_pkl):
            path_folder_cur = path_pkl + folder + '/'
            if os.path.exists(path_folder_cur):

                res_mse_cur_lst, res_move_cur_lst, res_zcoverage_cur_lst = [], [], []
                for pkl_file in os.listdir(path_folder_cur):
                    if '.pkl' in pkl_file:
                        pkl_id = pkl_file.split('_'+cc)[0].split('res_')[1]
                        if pkl_id in img_lst:
                            res_cur = pickle.load(open(path_folder_cur+pkl_file, 'r'))
                            res_mse_cur_lst.append(res_cur['mse'])
                            res_move_cur_lst.append(res_cur['maxmove'])
                            res_zcoverage_cur_lst.append(res_cur['zcoverage'])
                
                test_subj_dct[folder] = {'mse': [np.mean(res_mse_cur_lst), np.std(res_mse_cur_lst)],
                                         'maxmove': [np.mean(res_move_cur_lst), np.std(res_move_cur_lst)],
                                         'zcoverage': [np.mean(res_zcoverage_cur_lst), np.std(res_zcoverage_cur_lst)]}


        candidates_dct = {}
        for mm in mm_lst:
            candidates_lst = [[ss, test_subj_dct[ss][mm][0], test_subj_dct[ss][mm][1]] for ss in test_subj_dct]
            best_candidates_lst=sorted(candidates_lst, key = lambda x: float(x[1]))
            
            if mm == 'zcoverage':
                best_candidates_lst=best_candidates_lst[::-1]
                thresh_value = 90.0
                # thresh_value = best_candidates_lst[0][1] - float(best_candidates_lst[0][2])
                # candidates_dct[mm] = [cand[0] for cand in best_candidates_lst if cand[1]>thresh_value]
                candidates_dct[mm] = {}
                for cand in best_candidates_lst:
                    if cand[1]>thresh_value:
                        candidates_dct[mm][cand[0]] = {'mean':cand[1], 'std': cand[2]}
            else:
                thresh_value = 5.0
                # thresh_value = best_candidates_lst[0][1] + float(best_candidates_lst[0][2])
                # candidates_dct[mm] = [cand[0] for cand in best_candidates_lst if cand[1]<thresh_value]
                candidates_dct[mm] = {}
                for cand in best_candidates_lst:
                    if cand[1]<thresh_value:
                        candidates_dct[mm][cand[0]] = {'mean':cand[1], 'std': cand[2]}

        campeones_dct[interest] = candidates_dct
    
    pickle.dump(campeones_dct, open(path_local + 'best_trainer_' + cc + '_' + str(nb_img) + '_' + '_'.join(list(img_dct.keys())) + '.pkl', "wb"))

def find_best_trainer(path_local, cc, nb_img, mm, criteria_lst):

    with open(path_local + 'best_trainer_' + cc + '_' + str(nb_img) + '_' + '_'.join(criteria_lst) + '.pkl') as outfile:    
        campeones_dct = pickle.load(outfile)
        outfile.close()

    with open(path_local + 'resol_dct_' + cc + '.pkl') as outfile:    
        resol_dct = pickle.load(outfile)
        outfile.close()

    with open(path_local + 'patho_dct_' + cc + '.pkl') as outfile:    
        patho_dct = pickle.load(outfile)
        outfile.close()

    tot_subj = sum([len(resol_dct[ll]) for ll in resol_dct])

    good_trainer_condition = {'mse': 'Mean MSE < 4mm', 
                                'maxmove': 'Mean max move < 4mm', 
                                'zcoverage': '90% of predicted centerline is located in the manual segmentation'}

    criteria_candidat_dct = {}
    for criteria in criteria_lst:
        good_trainer_lst = [cand.split('_'+cc)[0] for cand in campeones_dct[criteria][mm]]
        criteria_candidat_dct[criteria] = good_trainer_lst
        nb_good_trainer = len(good_trainer_lst)

        print '\nTesting Population: ' + criteria
        print 'Metric of Interest: ' + mm
        print 'Condition to be considered as a good trainer: '
        print good_trainer_condition[mm]
        print '...% of good trainers in the whole ' + cc + ' dataset ' + str(round(nb_good_trainer*100.0/tot_subj))
        print '...Are considered as good trainer: '
        for resol in resol_dct:
            tot_resol = len(resol_dct[resol])
            cur_resol = len(set(good_trainer_lst).intersection(resol_dct[resol]))
            print '... ... ' + str(round(cur_resol*100.0/tot_resol,2)) + '% of our ' + resol + ' resolution images (#=' + str(tot_resol) + ')'
        for patho in patho_dct:
            tot_patho = len(patho_dct[patho])
            cur_patho = len(set(good_trainer_lst).intersection(patho_dct[patho]))
            print '... ... ' + str(round(cur_patho*100.0/tot_patho,2)) + '% of our ' + patho + ' subjects (#=' + str(tot_patho) + ')'




    # candidat_lst = list(set([x for x in campeones_ofInterest_names_lst if campeones_ofInterest_names_lst.count(x) == len(criteria_lst)]))

def inter_group(path_local, cc, nb_img, mm, criteria_dct):

    path_pkl = path_local+'output_pkl_'+cc+'_'+str(nb_img)+'/'

    group_dct = {}
    for train_subj in os.listdir(path_pkl):
        for group_name in criteria_dct:
            if train_subj.split('_'+cc)[0] in criteria_dct[group_name]:
                if not group_name in group_dct:
                    group_dct[group_name] = []
                group_dct[group_name].append(train_subj)

    inter_group_dct = {}
    for train_group in group_dct:
        for test_group in group_dct:
            print '\nTraining group: ' + train_group
            print 'Testing group: ' + test_group

            train_group_res = []
            for i,train_subj in enumerate(group_dct[train_group]):
                path_train_cur = path_pkl + group_dct[train_group][i] + '/'

                train_cur_res = []
                for j,test_subj in enumerate(group_dct[test_group]):
                    if group_dct[train_group][i] != group_dct[test_group][j]:
                        path_pkl_cur = path_pkl + group_dct[train_group][i] + '/res_' +  group_dct[test_group][j] + '.pkl'
                        with open(path_pkl_cur) as outfile:    
                            res_dct = pickle.load(outfile)
                            outfile.close()
                        train_cur_res.append(res_dct[mm])

                train_group_res.append(np.mean(train_cur_res))

            inter_group_dct[train_group+'_'+test_group] = [np.mean(train_group_res), np.std(train_group_res)]

    print inter_group_dct

    criteria_lst = list(criteria_dct.keys())
    res_mat = np.zeros((len(criteria_dct), len(criteria_dct)))
    for inter_group_res in inter_group_dct:
        train_cur = [s for s in criteria_lst if inter_group_res.startswith(s)][0]
        test_cur = [s for s in criteria_lst if inter_group_res.endswith(s)][0]
        res_mat[criteria_lst.index(train_cur), criteria_lst.index(test_cur)] = inter_group_dct[inter_group_res][0]

    print res_mat

    fig, ax = plt.subplots()
    if mm == 'zcoverage':
        plt.imshow(res_mat, interpolation='nearest', cmap=plt.cm.Blues)
    else:
        plt.imshow(res_mat, interpolation='nearest', cmap=cm.Blues._segmentdata)
    plt.title(mm, fontsize=15)
    plt.colorbar()
    tick_marks = np.arange(len(criteria_lst))
    plt.xticks(tick_marks, criteria_lst, rotation=45)
    plt.yticks(tick_marks, criteria_lst)


    thresh = res_mat.min()+(res_mat.max()-res_mat.min()) / 2.
    print thresh
    for i, j in itertools.product(range(res_mat.shape[0]), range(res_mat.shape[1])):
        plt.text(j, i, round(res_mat[i, j],2),color="white" if res_mat[i, j] > thresh else "black")

    # plt.tight_layout()
    plt.ylabel('Training image')
    plt.xlabel('Testing dataset')
    # plt.setp(ax.get_xticklabels(),visible=False)
    # plt.setp(ax.get_yticklabels(),visible=False)
    
    plt.show()






# ******************************************************************************************


# ****************************      USER CASE      *****************************************

def readCommand(  ):
    "Processes the command used to run from the command line"
    parser = argparse.ArgumentParser('Sdika Pipeline')
    parser.add_argument('-ofolder', '--output_folder', help='Output Folder', required = False)
    parser.add_argument('-c', '--contrast', help='Contrast of Interest', required = False)
    parser.add_argument('-n', '--nb_train_img', help='Nb Training Images', required = False)
    parser.add_argument('-s', '--step', help='Prepare (step=0) or Push (step=1) or Pull (step 2) or Compute metrics (step=3) or Display results (step=4)', 
                                        required = False)
    arguments = parser.parse_args()
    return arguments


USAGE_STRING = """
  USAGE:      python sct_sdika.py -ofolder '/Users/chgroc/data/data_sdika/' <options>
  EXAMPLES:   (1) python sct_sdika.py -ofolder '/Users/chgroc/data/data_sdika/' -c t2
                  -> Run Sdika Algorithm on T2w images dataset...
              (2) python sct_sdika.py -ofolder '/Users/chgroc/data/data_sdika/' -c t2 -n 3
                  -> ...Using 3 training images...
              (3) python sct_sdika.py -ofolder '/Users/chgroc/data/data_sdika/' -c t2 -n 3 -s 1
                  -> ...s=0 >> Prepare dataset
                  -> ...s=1 >> Push data to Ferguson
                  -> ...s=2 >> Pull data from Ferguson
                  -> ...s=3 >> Evaluate Sdika algo by computing metrics
                  -> ...s=4 >> Display results
                 """

if __name__ == '__main__':

    # Read input
    parse_arg = readCommand()

    if not parse_arg.output_folder:
        print USAGE_STRING
    else:
        path_local_sdika = parse_arg.output_folder
        create_folders_local([path_local_sdika])

        # Extract config
        with open(path_local_sdika + 'config.pkl') as outfile:    
            config_file = pickle.load(outfile)
            outfile.close()
        fname_local_script = config_file['fname_local_script']
        path_ferguson = config_file['path_ferguson']
        path_sct_testing_large = config_file['path_sct_testing_large']
        contrast_lst = config_file['contrast_lst']

        if not parse_arg.contrast:
            # List and prepare available T2w, T1w, T2sw data
            prepare_dataset(path_local_sdika, contrast_lst, path_sct_testing_large)

        else:
            # Format of parser arguments
            contrast_of_interest = str(parse_arg.contrast)
            if not parse_arg.nb_train_img:
                nb_train_img = 1
            else:
                nb_train_img = int(parse_arg.nb_train_img)
            if not parse_arg.step:
                step = 0
            else:
                step = int(parse_arg.step)            

            if not step:
                # Prepare [contrast] data
                # prepare_dataset(path_local_sdika, [contrast_of_interest], path_sct_testing_large)
                
                # Send Script to Ferguson Station
                # os.system('scp ' + fname_local_script + ' ferguson:' + path_ferguson)
                os.system('scp ' + fname_local_script + ' ferguson:' + path_ferguson)

            elif step == 1:
                if not os.path.isfile(path_local_sdika+'resol_dct_'+contrast_of_interest+'.pkl'):
                  partition_resol(path_local_sdika, contrast_of_interest)

                panda_dataset(path_local_sdika, contrast_of_interest)

                # Send Data to Ferguson station
                send_data2ferguson(path_local_sdika, path_ferguson, contrast_of_interest, nb_train_img)

            elif step == 2:
                # Pull Results from ferguson
                pull_img_convert_nii_remove_img(path_local_sdika, '/home/neuropoly/code/spine-ms-t2/', contrast_of_interest, nb_train_img)

            elif step == 3:
                # Compute metrics / Evaluate performance of Sdika algorithm
                compute_dataset_stats(path_local_sdika, contrast_of_interest, nb_train_img)

            elif step == 4:
                panda_trainer(path_local_sdika, contrast_of_interest)
                test_trainers_best_worst(path_local_sdika, contrast_of_interest, 'zcoverage', path_ferguson)

            elif step == 5:
                # Pull Testing Results from ferguson
                pull_img_convert_nii_remove_img(path_local_sdika, path_ferguson, contrast_of_interest, 0)
            
            elif step == 6:
                # Compute metrics / Evaluate performance of Sdika algorithm
                compute_dataset_stats(path_local_sdika, contrast_of_interest, 0)

            elif step == 7:
                plot_trainers_best_worst(path_local_sdika, contrast_of_interest, 'zcoverage')
                plot_comparison_nb_train(path_local_sdika, contrast_of_interest, 'zcoverage')
                plot_trainers_best_worst(path_local_sdika, contrast_of_interest, 'mse')
                plot_comparison_nb_train(path_local_sdika, contrast_of_interest, 'mse')

            elif step == 8:
                panda_seg(path_local_sdika, contrast_of_interest, 'zcoverage')
                prepare_last_test(path_local_sdika, contrast_of_interest, path_ferguson)

            elif step == 9:
                create_folders_local([path_local_sdika+'output_img_'+contrast_of_interest+'_666/', path_local_sdika+'output_nii_'+contrast_of_interest+'_666/'])
                pull_img_convert_nii_remove_img(path_local_sdika, path_ferguson, contrast_of_interest, 666)
            
            elif step == 10:
                compute_dataset_stats(path_local_sdika, contrast_of_interest, 666)
            
            elif step == 11:
                plot_comparison_classifier(path_local_sdika, contrast_of_interest, nb_train_img)

            elif step == 12:
                computation_time(path_local_sdika, contrast_of_interest)

            elif step == 13:
                plot_score_nb_train(path_local_sdika, 'zcoverage')
                plot_score_nb_train(path_local_sdika, 'mse')

            elif step == 'old':
                # Partition dataset into ISO, AX and SAG
                resol_dct = partition_resol(path_local_sdika, contrast_of_interest)

                # Partition dataset into HC // DCM // MS 
                with open(path_local_sdika + 'patho_dct_' + contrast_of_interest + '.pkl') as outfile:    
                    patho_dct = pickle.load(outfile)
                    outfile.close()

                compute_best_trainer(path_local_sdika, contrast_of_interest, nb_train_img, ['mse', 'maxmove', 'zcoverage'],
                                        {'HC': patho_dct['HC'], 'MS': patho_dct['MS'], 'CSM': patho_dct['CSM']})
                find_best_trainer(path_local_sdika, contrast_of_interest, nb_train_img, 'mse', ['CSM', 'HC', 'MS'])
                
                compute_best_trainer(path_local_sdika, contrast_of_interest, nb_train_img, ['mse', 'maxmove', 'zcoverage'],
                                        {'AX': resol_dct['ax'], 'SAG': resol_dct['sag'], 'ISO': resol_dct['iso']})
                find_best_trainer(path_local_sdika, contrast_of_interest, nb_train_img, 'mse', ['AX', 'SAG', 'ISO'])


                inter_group(path_local_sdika, contrast_of_interest, nb_train_img, 'zcoverage', resol_dct)
           
            else:
                print USAGE_STRING

    print TODO_STRING
