#!/usr/bin/python
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
from MyUtils import clamp
from vision import drectangle_to_tuple
from concurrent.futures import ProcessPoolExecutor

TIME=True
stats=defaultdict(list)

def timeit(profile=False):
    def decorator(func):
        if profile:
            def func_wrapper(*args, **kwargs):
                ts=time.time()                
                result=func(*args,**kwargs)
                cost=time.time()-ts
                stats[func.__name__].append(cost)
                return result
            return func_wrapper
        else:
            def func_wrapper(*args, **kwargs):
                return func(*args,**kwargs)
            return func_wrapper
    return decorator

def get_image_region(img, drect):
    (x1,y1,x2,y2) = drectangle_to_tuple(drect)
    h,w,_ =img.shape
    x1=clamp(x1,0,w-1)
    y1=clamp(y1,0,h-1)
    x2=clamp(x2,0,w-1)
    y2=clamp(y2,0,h-1)            
    return img[y1:y2+1, x1:x2+1]    

def get_largest_bb(dets, skipMulti=False):
    if (not skipMulti and len(dets) > 0) or len(dets) == 1:
        return max(dets, key=lambda rect: rect.width() * rect.height())
    else:
        return None
    
@timeit(profile=TIME)    
def track_img(tracker, img):
    tracker.update(img)
    return tracker.get_position()
    
def track(imgs, init_bx):
    pos=[init_bx]
    tracker=dlib.correlation_tracker()
    for idx, img in enumerate(imgs):
        if idx == 0:
            tracker.start_track(img, init_bx)
        else:
            pos.append(track_img(tracker,img))
    return pos

@timeit(profile=TIME)
def detect_img(detector, img, upsample=0, threshold=0, verbose=False):
    dets, scores, idx = detector.run(img, upsample, threshold)
    if verbose:
        for i, d in enumerate(dets):
            print("Detection {}, score: {}, face_type:{}".format(
                d, scores[i], idx[i]))    
    return dets    

def detect(imgs, verbose=False):
    detector=dlib.get_frontal_face_detector()
    dets=[]
    for img in imgs:
        dets.append(detect_img(detector, img, upsample=1, verbose=verbose))
    return dets

def load_imgs(img_paths):
    imgs=[]
    for img_path in img_paths:
        imgs.append(io.imread(img_path))
    return imgs

def det_vid(video_folder):    
    img_paths=get_img_paths(video_folder, 0)
    imgs=load_imgs(img_paths)
    rets=detect(imgs)
    return rets

# 1 based, exclusive
def get_img_paths(video_folder, idx, end_idx=None):
    items=os.listdir(video_folder)
    img_paths=[]
    if end_idx == None:
        end_idx=len(items)
    # the image directory is 1 based
    idx+=1
    start_idx=idx    
    end_idx+=1
    for idx in range(idx, end_idx):
        img_paths.append(os.path.join(video_folder, '{}.jpg'.format(idx)))
    print 'get path in {} from {} to {} ' \
          'within total {} frames'.format(video_folder,
                                          start_idx,
                                          end_idx-1,
                                          len(items))
    return img_paths
    
def track_det_in_vid(video_folder, idx, init_bx):
    img_paths=get_img_paths(video_folder, idx)
    print 'tracking {} from idx {} # imgs:{}'.format(video_folder, idx, len(img_paths))
    imgs=load_imgs(img_paths)
    tracks=track(imgs, init_bx)
    return tracks
    
def track_all_det_in_vid(video_folder, det_path):
    dets=pickle.load(open(det_path,'r'))
    trackss={}
    for idx, det in enumerate(dets):
        if len(det) > 0:
            print 'valid det at: {}'.format(idx)
            tracks=track_det_in_vid(video_folder, idx, det[0])
            trackss[idx]=tracks
    return trackss

def visual_single_dets_trackes(win, video_folder, idx, dets, tracks):
    img_paths=get_img_paths(video_folder, idx)
    imgs=load_imgs(img_paths)
    for img_idx, img in enumerate(imgs):
        win.clear_overlay()
        win.set_image(img)
        win.add_overlay(tracks[img_idx])
        win.add_overlay(dets[img_idx], color=dlib.rgb_pixel(0,255,0))
        time.sleep(0.05)
    
def visual_dets_tracks(video_folder, det_path, track_path):
    dets=pickle.load(open(det_path,'r'))
    tracks=pickle.load(open(track_path,'r'))
    win = dlib.image_window() 
#    pdb.set_trace()
    if isinstance(tracks, dict):
        trackss=tracks
        for idx, tracks in sorted(trackss.iteritems()):
            print 'showing tracking results starting at idx:{}'.format(idx)
            visual_single_dets_trackes(win, video_folder, idx, dets[idx:], tracks)
    elif isinstance(tracks, list):
        visual_single_dets_trackes(win, video_folder, 0, dets, tracks)        
    else:
        raise TypeError('track_path is not a valid tracks pickle file')

def iou_area(a, b):  # returns None if rectangles don't intersect
    # compute overlaps
    # intersection
    a=drectangle_to_tuple(a)
    b=drectangle_to_tuple(b)
    ixmin = np.maximum(a[0], b[0])
    iymin = np.maximum(a[1], b[1])
    ixmax = np.minimum(a[2], b[2])
    iymax = np.minimum(a[3], b[3])
    iw = np.maximum(ixmax - ixmin + 1., 0.)
    ih = np.maximum(iymax - iymin + 1., 0.)
    inters = iw * ih

    uni = ((b[2] - b[0] + 1.) * (b[3] - b[1] + 1.) +
           (a[2] - a[0] + 1.) *
           (a[3] - a[1] + 1.) - inters)

    overlaps = 1.0*inters / uni
    return overlaps

def iou_tracks(dets, tracks):
    ious=[]
    for idx, det in enumerate(dets):
        if len(det) > 0:
            if len(det) > 1:
                print 'det length larger than 1!'
                pdb.set_trace()
            iou=iou_area(det[0], tracks[idx])
            ious.append(iou)
    return ious

def iou_trackss(dets, trackss):
    ious={}
    for idx, tracks in sorted(trackss.iteritems()):
        partial_dets=dets[idx:]
        ious[idx]=iou_tracks(partial_dets, tracks)
    return ious

def iou_vid(det_path, trackss_path):
    dets=pickle.load(open(det_path,'r'))
    trackss=pickle.load(open(trackss_path,'r'))
    return iou_trackss(dets,trackss)

def det_vid_and_output(video_folder_output_path):
    video_folder, output_path=video_folder_output_path
    print 'detecting images from: {}'.format(video_folder)    
    rets=det_vid(video_folder)
    with open(output_path, 'w+') as f:
        pickle.dump(rets, f)
    print 'finished: {}'.format(video_folder) 
    
def det_vids():
    # vids=[
    #     '1593_01_001_ronald_reagan.avi',
    #     '0302_03_006_angelina_jolie.avi',
    #     '0805_01_014_hugh_grant.avi',
    #     '1830_02_008_tony_blair.avi',
    #     '1263_01_005_kevin_costner.avi',
    #     '1195_01_009_julia_roberts.avi',
    #     '1762_03_004_steven_spielberg.avi',
    #     '1780_01_007_sylvester_stallone.avi',
    #     '0094_03_002_al_gore.avi',
    #     '1413_01_013_meryl_streep.avi',
    #     '0349_02_001_ashley_judd.avi',
    #     '1728_01_001_steven_spielberg.avi',
    #     '0111_03_019_al_gore.avi',
    #     '0192_01_003_alanis_morissette.avi',
    #     '0845_03_015_hugh_grant.avi',
    #     '1033_03_005_jet_li.avi',
    #     '1620_02_016_ronald_reagan.avi',
    #     '0874_02_020_jacques_chirac.avi',
    #     '0917_03_008_jennifer_aniston.avi',
    #     '1429_02_012_meryl_streep.avi'
    # ]
    
    dataset_prefix=sys.argv[1]
    if len(sys.argv) > 2:
        output_dir=sys.argv[2]
        prefix=sys.argv[3]
    vids=os.listdir(dataset_prefix)
    concurrent_input=[]
    for vid in vids:
        output_path=os.path.join(output_dir, '{}.{}.pkl'.format(prefix, vid))
        if output_path and os.path.isfile(output_path):
            print '{} exist. skip detection'.format(output_path)
            continue
        video_folder=os.path.join(dataset_prefix, vid)
        concurrent_input.append((video_folder, output_path))

    with ProcessPoolExecutor(max_workers=8) as executor:
        executor.map(det_vid_and_output, concurrent_input)
        
    if TIME:
        output_path=os.path.join(output_dir, 'stats.pkl')
        with open(output_path, 'w+') as f:
            pickle.dump(stats, f)

def visual(vids, dets_dir_name, tracks_dir_name):            
    dataset_prefix=sys.argv[1]
    if len(sys.argv) > 2:
        output_dir=sys.argv[2]
        prefix=sys.argv[3]
    for vid in vids:
        video_folder=os.path.join(dataset_prefix, vid)
        det_path=os.path.join(dataset_prefix, '..', dets_dir_name, 'dets.{}.pkl'.format(vid))
        trackss_path=os.path.join(dataset_prefix, '..', tracks_dir_name, 'tracks_all_dets.{}.pkl'.format(vid))
#        trackss_path=os.path.join(dataset_prefix, '..', tracks_dir_name, '{}.pkl'.format(vid))
        visual_dets_tracks(video_folder, det_path, trackss_path)

def trackss_vids():        
    dataset_prefix=sys.argv[1]
    if len(sys.argv) > 2:
        output_dir=sys.argv[2]
        prefix=sys.argv[3]
    vids=[
        '1593_01_001_ronald_reagan.avi',
        '0302_03_006_angelina_jolie.avi',
        '0805_01_014_hugh_grant.avi',
        '1830_02_008_tony_blair.avi',
        '1263_01_005_kevin_costner.avi',
        '1195_01_009_julia_roberts.avi',
        '1762_03_004_steven_spielberg.avi',
        '1780_01_007_sylvester_stallone.avi',
        '0094_03_002_al_gore.avi',
        '1413_01_013_meryl_streep.avi',
        '0349_02_001_ashley_judd.avi',
        '1728_01_001_steven_spielberg.avi',
        '0111_03_019_al_gore.avi',
        '0192_01_003_alanis_morissette.avi',
        '0845_03_015_hugh_grant.avi',
        '1033_03_005_jet_li.avi',
        '1620_02_016_ronald_reagan.avi',
        '0874_02_020_jacques_chirac.avi',
        '0917_03_008_jennifer_aniston.avi',
        '1429_02_012_meryl_streep.avi'
        ]
    for vid in vids:
        video_folder=os.path.join(dataset_prefix, vid)
        det_path=os.path.join(dataset_prefix, '..', 'dets_20', 'dets.{}.pkl'.format(vid))
        print 'tracking images from: {}'.format(video_folder)
        print 'det_path at: {}'.format(det_path)
        rets=track_all_det_in_vid(video_folder, det_path)
        with open(os.path.join(output_dir, '{}.{}.pkl'.format(prefix, vid)), 'w+') as f:
            pickle.dump(rets, f)

def ious_by_frame_interval():
    dataset_prefix=sys.argv[1]
    if len(sys.argv) > 2:
        output_dir=sys.argv[2]
        prefix=sys.argv[3]
    vids=[
        '1593_01_001_ronald_reagan.avi',
        '0302_03_006_angelina_jolie.avi',
        '0805_01_014_hugh_grant.avi',
        '1830_02_008_tony_blair.avi',
        '1263_01_005_kevin_costner.avi',
        '1195_01_009_julia_roberts.avi',
        '1762_03_004_steven_spielberg.avi',
        '1780_01_007_sylvester_stallone.avi',
        '0094_03_002_al_gore.avi',
        '1413_01_013_meryl_streep.avi',
        '0349_02_001_ashley_judd.avi',
        '1728_01_001_steven_spielberg.avi',
        '0111_03_019_al_gore.avi',
        '0192_01_003_alanis_morissette.avi',
        '0845_03_015_hugh_grant.avi',
        '1033_03_005_jet_li.avi',
        '1620_02_016_ronald_reagan.avi',
        '0874_02_020_jacques_chirac.avi',
        '0917_03_008_jennifer_aniston.avi',
        '1429_02_012_meryl_streep.avi'
        ]
    ious_fr_itv=defaultdict(list)
    for vid in vids:
        det_path=os.path.join(dataset_prefix, '..', 'dets_20', 'dets.{}.pkl'.format(vid))
        trackss_path=os.path.join(dataset_prefix, '..', 'tracks_20', 'tracks_all_dets.{}.pkl'.format(vid))
        print 'det_path at: {}'.format(det_path)
        print 'trackss_path at: {}'.format(trackss_path)
        iouss=iou_vid(det_path, trackss_path)
        for idx, ious in sorted(iouss.iteritems()):
            for idx, iou in enumerate(ious):
                ious_fr_itv[idx].append(iou)
    with open(os.path.join(output_dir, '{}.{}.pkl'.format(prefix, 20)), 'w+') as f:
        pickle.dump(ious_fr_itv, f)

def plot_ious_vids():        
    dataset_prefix=sys.argv[1]
    if len(sys.argv) > 2:
        output_dir=sys.argv[2]
        prefix=sys.argv[3]
    ious_path=os.path.join(dataset_prefix, '..', 'ious_20','ious_fr_itv.20.pkl')
    ious_fr_itv=pickle.load(open(ious_path,'r'))
    ious_fr_itvs=[]
    ious_avgs=[]
    ious_mins=[] 
    ious_maxs=[]
    ious_extra_dict=defaultdict(list)
    for fr_itv, ious in sorted(ious_fr_itv.iteritems()):
        iou_avg = np.mean(ious)
        iou_min = np.min(ious)
        iou_max = np.max(ious)
        ious_extra_dict['median'].append(np.median(ious))
        ious_extra_dict['90 percentile'].append(np.percentile(ious,90))
        ious_fr_itvs.append(fr_itv)
        ious_avgs.append(iou_avg)
        ious_mins.append(iou_min)
        ious_maxs.append(iou_max)
#        print 'frame interval: {}, avg: {}, min: {}, max: {}, # pts: {}'.format(fr_itv, iou_avg, iou_min, iou_max, len(ious))
    for lim in [50,100,200,350]:
        plot.plot_error_bar(ious_fr_itvs, ious_avgs, (ious_mins, ious_maxs), ious_extra_dict, output='frame-interval-vs-effectiveness/frame-interval-vs-effectiveness-{}.pdf'.format(lim), xlim=[0, lim])

def det_vids_info(dets_dir_name):        
    dataset_prefix=sys.argv[1]
    if len(sys.argv) > 2:
        output_dir=sys.argv[2]
        prefix=sys.argv[3]
    vids=[
        '1593_01_001_ronald_reagan.avi',
        '0302_03_006_angelina_jolie.avi',
        '0805_01_014_hugh_grant.avi',
        '1830_02_008_tony_blair.avi',
        '1263_01_005_kevin_costner.avi',
        '1195_01_009_julia_roberts.avi',
        '1762_03_004_steven_spielberg.avi',
        '1780_01_007_sylvester_stallone.avi',
        '0094_03_002_al_gore.avi',
        '1413_01_013_meryl_streep.avi',
        '0349_02_001_ashley_judd.avi',
        '1728_01_001_steven_spielberg.avi',
        '0111_03_019_al_gore.avi',
        '0192_01_003_alanis_morissette.avi',
        '0845_03_015_hugh_grant.avi',
        '1033_03_005_jet_li.avi',
        '1620_02_016_ronald_reagan.avi',
        '0874_02_020_jacques_chirac.avi',
        '0917_03_008_jennifer_aniston.avi',
        '1429_02_012_meryl_streep.avi'
        ]
    ious_fr_itv=defaultdict(list)
    for vid in vids:
        det_path=os.path.join(dataset_prefix, '..', dets_dir_name, 'dets.{}.pkl'.format(vid))
        dets=pickle.load(open(det_path,'r'))        
        v_dets=[det for det in dets if len(det) > 0]
        print 'vid: {} # detections: {}'.format(vid, len(v_dets))
        
if __name__ == '__main__':
#    det_vids()
#    det_vids_info('dets_20')
    # with open('stats','r') as f:
    #     stats=pickle.load(f)
    # pdb.set_trace()
    # times=stats['detect_img']
    # print 'avg detection time: {} std: {}'.format(np.mean(times), np.std(times))
#    vids=[
#        '1830_02_008_tony_blair.avi',
#        '0349_02_001_ashley_judd.avi',
#        '1263_01_005_kevin_costner.avi',
#        '1429_02_012_meryl_streep.avi',
#         ]
#    visual(vids, 'dets_20_1', 'tracks_20')
    vids=[
        '0874_02_020_jacques_chirac.avi',
        ]
    win=dlib.image_window() 
    # visual_single_dets_trackes(win,vids,0, 'dets_1', 'tracks_1_20')
#    visual(vids, 'dets_1', 'tracks_1_20')
    visual(vids, 'dets_1', 'opencv_run1/results1')    
