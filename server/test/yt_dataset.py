import os
import glob

import dlib
from skimage import io
import time
import numpy as np
import time
from collections import defaultdict
import sys
import pickle
import pdb
from vision import drectangle_to_tuple
from MyUtils import create_dir
import operator
import numpy as np
from random import shuffle
import dlibutils
from skimage import io

def get_yt_vid_name(video_folder):
    if video_folder.endswith('/'):
        video_folder = video_folder_path[:-1]
    return os.path.basename(video_folder)

def get_yt_name(video_folder):
    vid_name = get_yt_vid_name(video_folder)
    vid_name_splits = vid_name.split('_')
    person_name = '_'.join(vid_name_splits[-2:])[:-4]
    return person_name

def get_yt_vid_length(video_folder):
    return (os.listdir(video_folder))

def get_yt_vids_length(video_folders):
    vids_length=[len(os.listdir(video_folder)) for video_folder in video_folders]
    return vids_length
    
def get_yt_vids_by_name(dataset_path):
    items=os.listdir(dataset_path)
    yt_info=defaultdict(list)
    for item in items:
        name=get_yt_name(item)
        video_folder=os.path.join(dataset_path, item)
        yt_info[name].append(video_folder)
    return yt_info

def get_yt_det(video_folder, dets_path_formatter):
    vid_name=get_yt_vid_name(video_folder)
    with open(dets_path_formatter.format(vid_name),'r') as f:
        dets=pickle.load(f)
    return dets

def get_yt_v_det(video_folder, dets_path_formatter):
    dets=get_yt_det(video_folder, dets_path_formatter)
    v_dets=[det for det in dets if len(det)>0]
    return v_dets
    
def get_max_det_vids_by_name(dataset_path, dets_path_formatter):
    yt_vids_by_name=get_yt_vids_by_name(dataset_path)
    max_det_vids_by_name={}
    for name, video_folders in sorted(yt_vids_by_name.iteritems()):
        vids_v_dets_num=[len(get_yt_v_det(video_folder, dets_path_formatter))
                     for video_folder in video_folders]
        max_v_dets_num=max(vids_v_dets_num)
        max_v_dets_video_name=video_folders[vids_v_dets_num.index(max_v_dets_num)]
        max_det_vids_by_name[name]=(max_v_dets_video_name, max_v_dets_num)
#        print '{}:{},{}'.format(name, max_v_dets_video_name, max_v_dets_num)
    return max_det_vids_by_name
        
    
def generate_training_sets(dataset_path, size, dets_path_formatter):
    yt_vids_by_name=get_yt_vids_by_name(dataset_path)
    training_set=defaultdict(list)
    training_set_vids=defaultdict(list)
    for name, video_folders in sorted(yt_vids_by_name.iteritems()):
        print 'generating training set for {}'.format(name)
        shuffle(video_folders)
        for video_folder in video_folders:
            dets=get_yt_det(video_folder, dets_path_formatter)
            detected_idx=[idx for idx, det in enumerate(dets) if len(det)>0]
            eligible_set=[(os.path.join(video_folder, '{}.jpg'.format(idx+1)),dets[idx][0])
                          for idx in detected_idx]
            training_set[name].extend(eligible_set)
            training_set_vids[name].append(video_folder)
            if len(training_set[name]) >= size:
                shuffle(training_set[name])
                training_set[name]=training_set[name][:size]
                break;
    return training_set, training_set_vids
    
def generate_test_sets(dataset_path, size, dets_path_formatter, training_set_path):
    training_sets, training_sets_vids=load_training_sets(training_set_path)
    yt_vids_by_name=get_yt_vids_by_name(dataset_path)
    test_set=defaultdict(list)
    for name, video_folders in sorted(yt_vids_by_name.iteritems()):
        print 'generating test set for {}'.format(name)
        shuffle(video_folders)
        testset_quota=size
        for video_folder in video_folders:
            if video_folder in training_sets_vids[name]:
                print 'skip {} for {} due to its usage in training'.format(video_folder,name)
                continue
            imgs_num=len(os.listdir(video_folder))
            dets=get_yt_det(video_folder, dets_path_formatter)
            # not used right now !!!! the number of detection matters
            detected_num=len([idx for idx, det in enumerate(dets) if len(det)>0])
            testset_quota-=imgs_num
            if testset_quota>0:
                test_set[name].append((video_folder, imgs_num))
            else:
                # now testset_quota is a negative number or 0
                test_set[name].append((video_folder,imgs_num+testset_quota))
                break
        if testset_quota>0:
            print '{} does not have enough testable points. it needs {} more data pts'.format(name, testset_quota)
            pdb.set_trace()
    return test_set
                
def get_yt_info():    
    dataset_path='yt/imgs'
    yt_vids_by_name=get_yt_vids_by_name(dataset_path)
    print 'in total there are {} peoples'.format(len(yt_vids_by_name.items()))
    for name, vids in sorted(yt_vids_by_name.items(), key=lambda x: len(x[1])):
        vids_length=get_yt_vids_length(vids)
        print 'name: {}, vids num: {}, vids length in total: {}'.format(name, len(vids),
                                                                        np.sum(vids_length))

def load_training_sets(training_set_path):
    with open(training_set_path, 'r') as f:
        (training_sets, training_sets_vids)=pickle.load(f)
    return (training_sets, training_sets_vids)

def create_training_set():
    dataset_path='yt/imgs'
    dets_path_formatter='yt/dets_1/dets.{}.pkl'
    training_sets, training_sets_vids=generate_training_sets(dataset_path,50,dets_path_formatter)
    output_dir=sys.argv[1]
    output_path=os.path.join(output_dir, 'train.pkl')
    with open(output_path,'w+') as f:
        pickle.dump((training_sets, training_sets_vids), f)

def get_most_detected_vids():
    dataset_path='yt/imgs'
    dets_path_formatter='yt/dets_1/dets.{}.pkl'
    dets_path='yt/dets_1'
    videos_folder=[video_folder for video_folder in os.listdir(dataset_path) if '.avi' in video_folder]
    dets_num_dict={}
    for video_folder in videos_folder:
        if os.path.isfile(dets_path_formatter.format(get_yt_vid_name(video_folder))):
            dets=get_yt_det(video_folder, dets_path_formatter)
            v_dets=[det for det in dets if len(det) > 0]
            # uv_dets=[det for det in dets if len(det) >1]
            # if len(uv_dets) > 0:
            #     pass
                # print '{} has more than 1 detections'.format(video_folder)
            dets_num_dict[video_folder]=len(v_dets)
    idx=0
    for video_folder, num_v_dets in reversed(sorted(dets_num_dict.items(), key=lambda x: x[1])):
#        print "'{}',".format(video_folder)
        print "{}:{}".format(video_folder, num_v_dets)        
        idx+=1
        if idx==20:
            break

def create_test_set():            
    dataset_path='yt/imgs'
    dets_path_formatter='yt/dets_1/dets.{}.pkl'
    training_set_path='yt/run_2/train.pkl'
    test_set=generate_test_sets(dataset_path,1000,dets_path_formatter, training_set_path)
    output_dir=sys.argv[1]
    output_path=os.path.join(output_dir, 'test.pkl')
    with open(output_path,'w+') as f:
        pickle.dump(test_set, f)

def get_segments_for_same_person(dataset_path, video_folder):
    vid_name = get_yt_vid_name(video_folder)
    vid_name_splits=vid_name.split('_')
    pat='*_*_*_{}_{}'.format(vid_name_splits[3], vid_name_splits[4])
    segments_videos=glob.glob(os.path.join(dataset_path, pat))
    shuffle(segments_videos)
    segments_videos=[vid for vid in segments_videos if video_folder not in vid]
    return segments_videos
        
def get_segments_in_same_video(dataset_path, video_folder):
    vid_name = get_yt_vid_name(video_folder)
    vid_name_splits=vid_name.split('_')
    pat='*_{}_*_{}_{}'.format(vid_name_splits[1], vid_name_splits[3], vid_name_splits[4])
    segments_videos=glob.glob(os.path.join(dataset_path, pat))
    shuffle(segments_videos)
    segments_videos=[vid for vid in segments_videos if video_folder not in vid]
    return segments_videos

# video_folders are test set vidoe folders    
def create_training_set_for_test_set(dataset_path,
                                     video_folders,
                                     dets_path_formatter):
    training_set=defaultdict(list)    
    for video_folder in video_folders:
        name =get_yt_name(video_folder)
        train_vids=get_segments_in_same_video(dataset_path, video_folder)
        # train_vids=get_segments_for_same_person(dataset_path, video_folder)
        for video_folder in train_vids:
            dets=get_yt_det(video_folder, dets_path_formatter)
            detected_idx=[idx for idx, det in enumerate(dets) if len(det)>0]
            eligible_set=[(os.path.join(video_folder, '{}.jpg'.format(idx+1)),
                       dlibutils.get_largest_bb(dets[idx]))
                          for idx in detected_idx]
            print '{} : {} added {}'.format(name, video_folder, len(eligible_set))
            training_set[name].extend(eligible_set)
        shuffle(training_set[name])
    return training_set, None

def load_training_set_imgs(video_folder, training_dir_name):
    name =get_yt_name(video_folder)
    train_dir=os.path.join('yt', training_dir_name, name)
    img_paths=glob.glob('{}/*.jpg'.format(train_dir))
    imgs=dlibutils.load_imgs(img_paths)
    imgs.sort(key=lambda x: -x.shape[0]*x.shape[1])
    return name, imgs
    
if __name__ == '__main__':
    if sys.argv[1] == 'most_dets':
        get_most_detected_vids()
    elif sys.argv[1] == 'most_dets_per_person':
        dataset_path='yt/imgs'
        dets_path_formatter='yt/dets_1/dets.{}.pkl'
        max_det_vids=get_max_det_vids_by_name(dataset_path, dets_path_formatter)
        test_set=[]
        for name, (video_name, max_dets_num) in reversed(sorted(max_det_vids.items(),
                                                            key=lambda x: x[1][1])):
            test_set.append(video_name)
            print "{}:{},{}".format(name, video_name, max_dets_num)
    # test_set=test_set[:10]
    # for test in test_set:
    #     print "'{}',".format(test)
    elif sys.argv[1] == 'load_training':
        load_training_set_imgs('yt/imgs/0874_02_020_jacques_chirac.avi', 'train_imgs_from_all_other_segments')
    elif sys.argv[1] == 'training_set':
        print 'creating training set'
        dataset_path='yt/imgs'
        dets_path_formatter='yt/dets_1/dets.{}.pkl'
        test_set=[
            'yt/imgs/0874_02_020_jacques_chirac.avi',
            'yt/imgs/0917_03_008_jennifer_aniston.avi',
            'yt/imgs/1033_03_005_jet_li.avi',
            'yt/imgs/0845_03_015_hugh_grant.avi',
            'yt/imgs/1413_01_013_meryl_streep.avi',
            'yt/imgs/0094_03_002_al_gore.avi',
            'yt/imgs/1780_01_007_sylvester_stallone.avi',
            'yt/imgs/1762_03_004_steven_spielberg.avi',
            'yt/imgs/1195_01_009_julia_roberts.avi',
            'yt/imgs/0302_03_006_angelina_jolie.avi',
        ]
        training_sets, _=create_training_set_for_test_set(dataset_path,
                                                          test_set,
                                                          dets_path_formatter)
        with open('yt/train-1012.pkl', 'w+') as f:
            pickle.dump((training_sets, []), f)
        
        output_imgs_dir_prefix='yt/train_imgs_from_other_segments_in_the_same_video'
        for name, training_set in training_sets.iteritems():
            output_imgs_dir=os.path.join(output_imgs_dir_prefix, name)
            create_dir(output_imgs_dir)
            for idx, (img_path, det) in enumerate(training_set[:40]):
                (x1,y1,x2,y2) = drectangle_to_tuple(det)
                frame=io.imread(img_path)
                face_data=frame[y1:y2+1, x1:x2+1]
                io.imsave(os.path.join(output_imgs_dir, '{}.jpg'.format(idx)), face_data)

            
        # output_dir=sys.argv[1]
        # output_path=os.path.join(output_dir, 'train-v2.pkl')
        # with open(output_path,'w+') as f:
        #     pickle.dump((training_sets, []), f)

#    print len(get_segments_in_same_video('yt/imgs', 'yt/imgs/0874_02_020_jacques_chirac.avi'))
#    get_most_detected_vids()
    # dataset_path='yt/imgs'
    # dets_path_formatter='yt/dets_1/dets.{}.pkl'
    # max_det_vids=get_max_det_vids_by_name(dataset_path, dets_path_formatter)
    # test_set=[]
    # for name, (video_name, max_dets_num) in reversed(sorted(max_det_vids.items(),
    #                                                         key=lambda x: x[1][1])):
    #     test_set.append(video_name)
    # test_set=test_set[:10]
    # for test in test_set:
    #     print "'{}',".format(test)
        
    
# test_set=[
# 'yt/imgs/0874_02_020_jacques_chirac.avi',
# 'yt/imgs/0917_03_008_jennifer_aniston.avi',
# 'yt/imgs/1033_03_005_jet_li.avi',
# 'yt/imgs/0845_03_015_hugh_grant.avi',
# 'yt/imgs/1413_01_013_meryl_streep.avi',
# 'yt/imgs/0094_03_002_al_gore.avi',
# 'yt/imgs/1780_01_007_sylvester_stallone.avi',
# 'yt/imgs/1762_03_004_steven_spielberg.avi',
# 'yt/imgs/1195_01_009_julia_roberts.avi',
# 'yt/imgs/0302_03_006_angelina_jolie.avi',
# ]
